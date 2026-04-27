"""
Document ingestion module.

Reads PDF, Markdown, and plain-text files from a source directory and writes
a JSONL file where each line is a JSON object with the fields::

    {
        "doc_id": "D001",
        "title":  "Riemannian Geometry Notes",
        "source_path": "/path/to/file.pdf",
        "page": 1,
        "subject": "Riemannian Geometry",
        "source_type": "pdf",
        "created_time": "2024-01-15T10:00:00",
        "text": "..."
    }

Usage
-----
    python src/ingest.py --input data/raw_docs --output data/processed/docs.jsonl
    python src/ingest.py --input data/raw_docs  # writes to default path from config

The ``--subject`` flag can override the inferred subject for all documents in
a single run (useful when processing a themed folder).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATA_DIR, PROCESSED_DIR, RAW_DOCS_DIR

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# PDF extraction helpers
# ---------------------------------------------------------------------------


def _extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """Return a list of (page_number, text) pairs from a PDF file.

    Tries pypdf first (pure Python, no native deps), then falls back to the
    ``pdfminer`` package if available.  Page numbers are 1-based.
    """
    pages: list[tuple[int, str]] = []
    try:
        import pypdf  # type: ignore[import]

        reader = pypdf.PdfReader(str(path))
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((i, text))
        return pages
    except ImportError:
        pass

    try:
        from pdfminer.high_level import extract_pages  # type: ignore[import]
        from pdfminer.layout import LTAnon, LTChar, LTTextBox  # type: ignore[import]

        for i, page_layout in enumerate(extract_pages(str(path)), start=1):
            tokens = []
            for element in page_layout:
                if isinstance(element, LTTextBox):
                    tokens.append(element.get_text())
            text = "\n".join(tokens)
            if text.strip():
                pages.append((i, text))
        return pages
    except ImportError:
        pass

    logger.warning(
        "Neither 'pypdf' nor 'pdfminer' is installed; cannot extract text from %s",
        path,
    )
    return []


# ---------------------------------------------------------------------------
# Markdown / plain-text helpers
# ---------------------------------------------------------------------------


def _extract_text_file(path: Path) -> list[tuple[int, str]]:
    """Return a single (page=1, text) pair from a plain text or Markdown file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("Cannot read %s: %s", path, exc)
        return []
    return [(1, text)] if text.strip() else []


# ---------------------------------------------------------------------------
# Subject inference
# ---------------------------------------------------------------------------

_SUBJECT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"riemannian|黎曼|geodesic|测地|riemann\b", re.IGNORECASE), "Riemannian Geometry"),
    (re.compile(r"\bricci\b", re.IGNORECASE), "Riemannian Geometry"),
    (re.compile(r"pde|partial differential|偏微分", re.IGNORECASE), "PDE"),
    (re.compile(r"harmonic|调和", re.IGNORECASE), "Harmonic Analysis"),
    (re.compile(r"topology|拓扑", re.IGNORECASE), "Topology"),
    (re.compile(r"algebra|代数", re.IGNORECASE), "Algebra"),
    (re.compile(r"calculus|微积分|analysis|分析", re.IGNORECASE), "Analysis"),
    (re.compile(r"probability|概率|stochastic|随机", re.IGNORECASE), "Probability"),
    (re.compile(r"number theory|数论", re.IGNORECASE), "Number Theory"),
]


def _infer_subject(title: str, text_sample: str) -> str:
    """Return a coarse subject label for a document."""
    combined = f"{title} {text_sample[:500]}"
    for pattern, subject in _SUBJECT_PATTERNS:
        if pattern.search(combined):
            return subject
    return "Mathematics"


# ---------------------------------------------------------------------------
# Title inference
# ---------------------------------------------------------------------------


def _infer_title(path: Path) -> str:
    """Derive a human-readable title from the file name."""
    stem = path.stem
    # Replace underscores and hyphens with spaces, title-case.
    return re.sub(r"[_\-]+", " ", stem).strip().title()


# ---------------------------------------------------------------------------
# Core ingestion logic
# ---------------------------------------------------------------------------


def ingest_file(
    path: Path,
    doc_id: str,
    subject_override: str | None = None,
) -> list[dict]:
    """Ingest a single file and return a list of page records."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = _extract_pdf_pages(path)
        source_type = "pdf"
    elif suffix in {".md", ".markdown"}:
        pages = _extract_text_file(path)
        source_type = "markdown"
    elif suffix in {".txt", ".text"}:
        pages = _extract_text_file(path)
        source_type = "text"
    else:
        logger.warning("Unsupported file type: %s — skipping", path)
        return []

    title = _infer_title(path)
    created_time = datetime.now(timezone.utc).isoformat()

    records: list[dict] = []
    for page_num, text in pages:
        subject = subject_override or _infer_subject(title, text)
        records.append(
            {
                "doc_id": doc_id,
                "title": title,
                "source_path": str(path.resolve()),
                "page": page_num,
                "subject": subject,
                "source_type": source_type,
                "created_time": created_time,
                "text": text,
            }
        )

    logger.info("Ingested %s: %d page(s)", path.name, len(records))
    return records


def ingest_directory(
    input_dir: Path,
    output_path: Path,
    subject_override: str | None = None,
) -> int:
    """Ingest all supported files in *input_dir* into a JSONL file at *output_path*.

    Returns the total number of page records written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    supported_suffixes = {".pdf", ".md", ".markdown", ".txt", ".text"}
    files = sorted(
        f for f in input_dir.rglob("*") if f.suffix.lower() in supported_suffixes
    )

    if not files:
        logger.warning("No supported files found in %s", input_dir)
        return 0

    total = 0
    with output_path.open("w", encoding="utf-8") as fout:
        for idx, file_path in enumerate(files, start=1):
            doc_id = f"D{idx:04d}"
            records = ingest_file(file_path, doc_id, subject_override)
            for rec in records:
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += len(records)

    logger.info("Wrote %d records to %s", total, output_path)
    return total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest math learning materials (PDF/MD/TXT) into JSONL."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=RAW_DOCS_DIR,
        help="Directory containing raw documents (default: data/raw_docs)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROCESSED_DIR / "docs.jsonl",
        help="Output JSONL file path (default: data/processed/docs.jsonl)",
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="Override inferred subject label for all documents",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    count = ingest_directory(args.input, args.output, args.subject)
    print(f"Ingestion complete: {count} page records → {args.output}")


if __name__ == "__main__":
    main()
