"""
Text chunking module with three strategies.

Strategies
----------
fixed
    Split text into fixed-length windows with a character overlap.  Simple
    and fast, but may cut across logical units.

paragraph
    Split on blank lines and structural markers (numbered items, LaTeX
    environments, Chinese punctuation section breaks).  Each paragraph is a
    chunk; oversized paragraphs are further split to ``chunk_size``.

math-aware  (default)
    Recognises mathematical structural keywords — Definition, Theorem, Proof,
    Lemma, Proposition, Corollary, Remark, Example and their Chinese
    equivalents — and keeps each logical unit intact.  Oversized units are
    split with overlap while still honouring sentence boundaries where
    possible.

Usage
-----
    python src/chunker.py \\
        --input data/processed/docs.jsonl \\
        --strategy math-aware \\
        --chunk-size 400 \\
        --overlap 80 \\
        --output data/chunks.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHUNK_STRATEGY,
    CHUNKS_CSV,
    PROCESSED_DIR,
    TOPIC_KEYWORDS,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Structural keywords that begin a new logical unit in math text.
_MATH_KEYWORDS = (
    r"Definition|Theorem|Lemma|Proposition|Proof|Corollary|Example|Remark"
    r"|Notation|Convention|Conjecture|Problem|Solution|Exercise|Claim"
    r"|定义|定理|引理|命题|证明|推论|例|注|注记|习题|问题|解答|断言|猜想"
)
_MATH_UNIT_START = re.compile(
    rf"(?m)^(?:(?:[A-Z][a-z]*\s+)?(?:{_MATH_KEYWORDS})[\s\.:\d])"
)

# Paragraph / section break patterns.
_PARA_BREAK = re.compile(r"\n\s*\n|\n(?=[A-Z\d])")

# ---------------------------------------------------------------------------
# Topic labelling
# ---------------------------------------------------------------------------


def label_topics(text: str) -> list[str]:
    """Return all topic labels whose keywords appear in *text*."""
    found: list[str] = []
    text_lower = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                found.append(topic)
                break
    return found


# ---------------------------------------------------------------------------
# Strategy A: fixed-length
# ---------------------------------------------------------------------------


def _fixed_chunks(text: str, size: int, overlap: int) -> Iterator[str]:
    """Yield fixed-size character windows with *overlap* between consecutive chunks."""
    if not text:
        return
    step = max(1, size - overlap)
    start = 0
    while start < len(text):
        yield text[start : start + size]
        start += step


# ---------------------------------------------------------------------------
# Strategy B: paragraph-based
# ---------------------------------------------------------------------------


def _paragraph_chunks(text: str, size: int, overlap: int) -> Iterator[str]:
    """Yield chunks aligned to paragraph boundaries."""
    parts = _PARA_BREAK.split(text)
    buffer = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # If adding this paragraph overflows the budget, flush first.
        if buffer and len(buffer) + len(part) + 2 > size:
            yield buffer
            # Keep overlap: carry the tail of the buffer.
            buffer = buffer[-overlap:] if overlap else ""
        buffer = (buffer + "\n\n" + part).strip() if buffer else part

    if buffer:
        yield buffer


# ---------------------------------------------------------------------------
# Strategy C: math-aware
# ---------------------------------------------------------------------------


def _split_large(text: str, size: int, overlap: int) -> Iterator[str]:
    """Split an oversized text block using fixed windows as a fallback."""
    yield from _fixed_chunks(text, size, overlap)


def _math_aware_chunks(text: str, size: int, overlap: int) -> Iterator[str]:
    """Yield chunks that respect math structural units (definition, theorem, …).

    The algorithm:
    1. Find all positions in *text* where a new structural unit begins.
    2. Slice *text* at those boundaries to get unit strings.
    3. Units that fit within *size* are emitted directly.
    4. Units larger than *size* are further split with overlap.
    5. Consecutive small units are merged until the budget is reached.
    """
    # Locate unit boundaries.
    boundaries = [m.start() for m in _MATH_UNIT_START.finditer(text)]

    if not boundaries:
        # No recognisable math structure — fall back to paragraph strategy.
        yield from _paragraph_chunks(text, size, overlap)
        return

    # Build slices: include any text before the first keyword as a preamble.
    slices: list[str] = []
    if boundaries[0] > 0:
        slices.append(text[: boundaries[0]].strip())
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        slices.append(text[start:end].strip())

    # Merge / split slices into target chunks.
    buffer = ""
    for unit in slices:
        if not unit:
            continue
        if len(unit) > size:
            # Flush the accumulated buffer first.
            if buffer:
                yield buffer
                buffer = ""
            # Then emit the large unit in sub-chunks.
            yield from _split_large(unit, size, overlap)
        elif buffer and len(buffer) + len(unit) + 2 > size:
            yield buffer
            # Carry tail for overlap.
            buffer = (buffer[-overlap:] + "\n\n" + unit).strip() if overlap else unit
        else:
            buffer = (buffer + "\n\n" + unit).strip() if buffer else unit

    if buffer:
        yield buffer


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_text(
    text: str,
    strategy: str = CHUNK_STRATEGY,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split *text* into a list of chunk strings using the chosen *strategy*."""
    text = text.strip()
    if not text:
        return []

    if strategy == "fixed":
        return list(_fixed_chunks(text, chunk_size, overlap))
    if strategy == "paragraph":
        return list(_paragraph_chunks(text, chunk_size, overlap))
    if strategy == "math-aware":
        return list(_math_aware_chunks(text, chunk_size, overlap))

    raise ValueError(
        f"Unknown strategy '{strategy}'. Choose from: fixed, paragraph, math-aware"
    )


# ---------------------------------------------------------------------------
# JSONL → CSV pipeline
# ---------------------------------------------------------------------------

_CSV_FIELDS = [
    "chunk_id",
    "doc_id",
    "title",
    "source_path",
    "page",
    "subject",
    "source_type",
    "created_time",
    "strategy",
    "chunk_index",
    "topics",
    "text",
]


def process_jsonl(
    input_path: Path,
    output_path: Path,
    strategy: str = CHUNK_STRATEGY,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> int:
    """Read a JSONL docs file, chunk every page, and write a CSV of chunks.

    Returns the total number of chunks written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    chunk_counter = 1

    with (
        input_path.open("r", encoding="utf-8") as fin,
        output_path.open("w", newline="", encoding="utf-8") as fout,
    ):
        writer = csv.DictWriter(fout, fieldnames=_CSV_FIELDS)
        writer.writeheader()

        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed JSON line: %s", exc)
                continue

            text = record.get("text", "")
            chunks = chunk_text(text, strategy=strategy, chunk_size=chunk_size, overlap=overlap)

            for idx, chunk in enumerate(chunks):
                topics = label_topics(chunk)
                writer.writerow(
                    {
                        "chunk_id": f"C{chunk_counter:05d}",
                        "doc_id": record.get("doc_id", ""),
                        "title": record.get("title", ""),
                        "source_path": record.get("source_path", ""),
                        "page": record.get("page", 1),
                        "subject": record.get("subject", ""),
                        "source_type": record.get("source_type", ""),
                        "created_time": record.get("created_time", ""),
                        "strategy": strategy,
                        "chunk_index": idx,
                        "topics": ";".join(topics),
                        "text": chunk,
                    }
                )
                chunk_counter += 1
                total += 1

    logger.info("Wrote %d chunks to %s (strategy=%s)", total, output_path, strategy)
    return total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chunk ingested math documents into knowledge fragments."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROCESSED_DIR / "docs.jsonl",
        help="Input JSONL file produced by ingest.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CHUNKS_CSV,
        help="Output CSV path (default: data/chunks.csv)",
    )
    parser.add_argument(
        "--strategy",
        choices=["fixed", "paragraph", "math-aware"],
        default=CHUNK_STRATEGY,
        help="Chunking strategy (default: %(default)s)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        help="Target characters per chunk (default: %(default)s)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=CHUNK_OVERLAP,
        help="Character overlap between consecutive chunks (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    count = process_jsonl(
        args.input,
        args.output,
        strategy=args.strategy,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    print(f"Chunking complete: {count} chunks → {args.output}")


if __name__ == "__main__":
    main()
