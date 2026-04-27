"""
Build a Memvid `.mv2` memory file from a chunks CSV.

Each row in the CSV becomes one frame in the memory file.  The frame body is
the chunk text; all other CSV columns are stored as ``extra_metadata`` tags
so that they surface in search results.

Usage
-----
    python src/build_memory.py \\
        --chunks data/chunks.csv \\
        --output memory/math_knowledge.mv2

    # overwrite an existing file
    python src/build_memory.py --chunks data/chunks.csv --force
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CHUNKS_CSV, MEMVID_CLI, MEMORY_DIR, MEMORY_FILE

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# Columns that should NOT be stored as extra_metadata (they are either redundant
# or too large).
_SKIP_METADATA_COLS = {"text", "chunk_id"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(cmd: list[str], stdin_text: str | None = None) -> dict:
    """Run *cmd* as a subprocess and return the parsed JSON output."""
    try:
        result = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout.strip())
    except FileNotFoundError:
        logger.error(
            "memvid-cli not found at '%s'.\n"
            "Build it first:  cd <repo_root> && cargo build --bin memvid-cli\n"
            "Then set MEMVID_CLI=/path/to/memvid-cli",
            MEMVID_CLI,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        logger.error("CLI error (exit %d): %s", exc.returncode, exc.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        logger.error("Unexpected CLI output (not JSON): %s", exc)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Core build logic
# ---------------------------------------------------------------------------


def build_memory(
    chunks_csv: Path,
    output_mv2: Path,
    force: bool = False,
) -> int:
    """Write every chunk from *chunks_csv* into a new `.mv2` at *output_mv2*.

    Returns the number of frames written.
    """
    if output_mv2.exists():
        if force:
            output_mv2.unlink()
            logger.info("Removed existing memory file: %s", output_mv2)
        else:
            logger.error(
                "%s already exists. Use --force to overwrite.", output_mv2
            )
            sys.exit(1)

    output_mv2.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: create the memory file.
    _run_cli([MEMVID_CLI, "create", str(output_mv2)])
    logger.info("Created memory file: %s", output_mv2)

    # Step 2: read chunks and write each as a frame.
    with chunks_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    total = len(rows)
    logger.info("Inserting %d chunks …", total)
    start_time = time.perf_counter()

    for i, row in enumerate(rows, start=1):
        text = row.get("text", "").strip()
        if not text:
            continue

        extra_metadata = {
            k: str(v)
            for k, v in row.items()
            if k not in _SKIP_METADATA_COLS and v
        }
        # chunk_id is stored as the URI for easy retrieval.
        chunk_id = row.get("chunk_id", f"C{i:05d}")
        title = row.get("title", "")

        put_input = {
            "text": text,
            "title": title,
            "uri": f"chunk://{chunk_id}",
            "extra_metadata": extra_metadata,
        }

        _run_cli(
            [MEMVID_CLI, "put", str(output_mv2)],
            stdin_text=json.dumps(put_input, ensure_ascii=False),
        )

        if i % 50 == 0 or i == total:
            elapsed = time.perf_counter() - start_time
            logger.info("  %d / %d  (%.1fs)", i, total, elapsed)

    elapsed = time.perf_counter() - start_time
    logger.info(
        "Build complete: %d frames in %.1fs → %s", total, elapsed, output_mv2
    )
    return total


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Memvid .mv2 memory file from a chunks CSV."
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=CHUNKS_CSV,
        help="Input chunks CSV (default: data/chunks.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MEMORY_FILE,
        help="Output .mv2 path (default: memory/math_knowledge.mv2)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    count = build_memory(args.chunks, args.output, force=args.force)
    print(f"Memory build complete: {count} frames → {args.output}")


if __name__ == "__main__":
    main()
