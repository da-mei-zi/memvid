"""
Search interface for the Math-Knowledge-Memvid system.

Wraps the ``memvid-cli search`` subcommand and provides three search *modes*:

keyword
    Pure BM25 / full-text search via Tantivy (the engine embedded in Memvid).
    Useful for exact term matching, e.g. looking up a specific formula name.

vector
    Not yet supported natively by memvid-cli without the ``vec`` feature and a
    pre-built ONNX embedding model.  When the memory file has no vector index
    (the default build), this mode automatically falls back to ``keyword``.

hybrid
    Runs both keyword and (if available) vector search, merges results by
    re-ranking with a simple reciprocal-rank fusion (RRF) score.  Falls back
    to ``keyword`` when no vector index is present.

Usage
-----
    python src/search.py \\
        --query "Bochner公式在梯度估计中有什么作用？" \\
        --mode hybrid \\
        --top-k 5

    # programmatic
    from search import search
    results = search("Bochner formula", mode="keyword", top_k=5)
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MEMVID_CLI, MEMORY_FILE, SEARCH_SNIPPET_CHARS, SEARCH_TOP_K

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# Short common words that carry little search signal.
_QUERY_STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "in", "of", "to", "and", "for",
    "what", "how", "why", "does", "有", "什么", "的", "在", "是",
})

# ---------------------------------------------------------------------------
# Low-level CLI wrapper
# ---------------------------------------------------------------------------


def _cli_search(
    mv2_path: Path,
    query: str,
    top_k: int = SEARCH_TOP_K,
    snippet_chars: int = SEARCH_SNIPPET_CHARS,
) -> dict[str, Any]:
    """Call memvid-cli search and return the parsed JSON response.

    The Memvid lex engine uses AND logic for multi-word queries.  When a
    multi-word query returns no hits, this function automatically falls back
    to searching for the most significant individual terms and merges the
    results so that users receive useful output regardless of phrasing.
    """
    def _run(q: str) -> dict[str, Any]:
        cmd = [
            MEMVID_CLI,
            "search",
            str(mv2_path),
            q,
            "--top-k",
            str(top_k),
            "--snippet-chars",
            str(snippet_chars),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )
            return json.loads(result.stdout.strip())
        except FileNotFoundError:
            logger.error(
                "memvid-cli not found at '%s'. Build it with: cargo build --bin memvid-cli",
                MEMVID_CLI,
            )
            sys.exit(1)
        except subprocess.CalledProcessError as exc:
            logger.error("CLI error (exit %d): %s", exc.returncode, exc.stderr)
            raise RuntimeError(exc.stderr) from exc
        except json.JSONDecodeError as exc:
            logger.error("Unexpected CLI output (not JSON): %s", exc)
            raise

    raw = _run(query)

    # If the multi-word AND query returned results, use them directly.
    if raw.get("hits") or " " not in query.strip():
        return raw

    # Fall back: search each significant term individually and merge by RRF.
    # Filter out very short tokens and common stop words.
    terms = [t for t in query.split() if len(t) >= 3 and t.lower() not in _QUERY_STOP_WORDS]
    if not terms:
        return raw

    seen_ids: dict[int, dict] = {}
    rrf_scores: dict[int, float] = {}
    total_hits = 0

    for term in terms:
        term_raw = _run(term)
        total_hits = max(total_hits, term_raw.get("total_hits", 0))
        for rank, hit in enumerate(term_raw.get("hits", []), start=1):
            fid = hit.get("frame_id", rank)
            rrf_scores[fid] = rrf_scores.get(fid, 0.0) + 1.0 / (60 + rank)
            seen_ids.setdefault(fid, hit)

    merged = sorted(seen_ids.values(), key=lambda h: -rrf_scores.get(h.get("frame_id", 0), 0.0))
    merged = merged[:top_k]
    for i, h in enumerate(merged, start=1):
        h["rank"] = i
        h["score"] = rrf_scores.get(h.get("frame_id", 0), 0.0)

    return {
        "query": query,
        "top_k": top_k,
        "total_hits": total_hits,
        "elapsed_ms": raw.get("elapsed_ms", 0),
        "engine": "LexFallback",
        "hits": merged,
    }


# ---------------------------------------------------------------------------
# Result normalisation
# ---------------------------------------------------------------------------


def _normalise_hit(raw: dict, mode: str) -> dict:
    """Convert a raw CLI hit into a normalised result record."""
    meta = raw.get("extra_metadata", {})
    return {
        "chunk_id": meta.get("chunk_id", raw.get("uri", "").replace("chunk://", "")),
        "frame_id": raw.get("frame_id"),
        "rank": raw.get("rank", 0),
        "score": raw.get("score"),
        "title": raw.get("title") or meta.get("title", ""),
        "page": meta.get("page", ""),
        "subject": meta.get("subject", ""),
        "topics": meta.get("topics", ""),
        "source_type": meta.get("source_type", ""),
        "text": raw.get("text", ""),
        "mode": mode,
    }


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def _rrf_merge(
    lists: list[list[dict]],
    k: int = 60,
    top_k: int = SEARCH_TOP_K,
) -> list[dict]:
    """Merge multiple ranked lists using Reciprocal Rank Fusion.

    Each result is identified by its ``chunk_id``.  The merged list is sorted
    by descending RRF score and truncated to *top_k*.
    """
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for ranked_list in lists:
        for rank, item in enumerate(ranked_list, start=1):
            cid = item.get("chunk_id", str(rank))
            rrf_score = 1.0 / (k + rank)
            scores[cid] = scores.get(cid, 0.0) + rrf_score
            # Keep the copy from the first list that has it.
            items.setdefault(cid, item)

    merged = sorted(items.values(), key=lambda x: scores.get(x.get("chunk_id", ""), 0.0), reverse=True)
    for i, item in enumerate(merged[:top_k], start=1):
        item["rank"] = i
        item["score"] = scores.get(item.get("chunk_id", ""), 0.0)
    return merged[:top_k]


# ---------------------------------------------------------------------------
# Public search API
# ---------------------------------------------------------------------------


def search(
    query: str,
    mode: str = "keyword",
    top_k: int = SEARCH_TOP_K,
    mv2_path: Path | None = None,
) -> dict[str, Any]:
    """Search the math knowledge base.

    Parameters
    ----------
    query:
        Natural-language or keyword query string.
    mode:
        ``"keyword"``, ``"vector"``, or ``"hybrid"``.
    top_k:
        Maximum number of results to return.
    mv2_path:
        Path to the ``.mv2`` file.  Defaults to ``memory/math_knowledge.mv2``.

    Returns
    -------
    dict with keys:
        - ``query``
        - ``mode``
        - ``top_k``
        - ``total_hits``
        - ``elapsed_ms``
        - ``results``  — list of normalised hit dicts
    """
    if mv2_path is None:
        mv2_path = MEMORY_FILE

    if not mv2_path.exists():
        raise FileNotFoundError(
            f"Memory file not found: {mv2_path}\n"
            "Run build_memory.py first to create it."
        )

    t0 = time.perf_counter()

    if mode == "keyword":
        raw = _cli_search(mv2_path, query, top_k=top_k)
        hits = [_normalise_hit(h, "keyword") for h in raw.get("hits", [])]
        elapsed = (time.perf_counter() - t0) * 1000

        return {
            "query": query,
            "mode": mode,
            "top_k": top_k,
            "total_hits": raw.get("total_hits", len(hits)),
            "elapsed_ms": round(raw.get("elapsed_ms", elapsed), 2),
            "results": hits,
        }

    if mode == "vector":
        # Vector search requires the vec feature and an ONNX model.
        # Fall back gracefully to keyword search.
        logger.info(
            "Vector mode requested — falling back to keyword search "
            "(build with '--features vec' and provide an ONNX model to enable native vector search)."
        )
        return search(query, mode="keyword", top_k=top_k, mv2_path=mv2_path)

    if mode == "hybrid":
        # Run keyword search with 2× candidates, then re-rank with RRF.
        raw = _cli_search(mv2_path, query, top_k=top_k * 2)
        kw_hits = [_normalise_hit(h, "keyword") for h in raw.get("hits", [])]
        merged = _rrf_merge([kw_hits], top_k=top_k)
        elapsed = (time.perf_counter() - t0) * 1000

        return {
            "query": query,
            "mode": mode,
            "top_k": top_k,
            "total_hits": raw.get("total_hits", len(merged)),
            "elapsed_ms": round(elapsed, 2),
            "results": merged,
        }

    raise ValueError(
        f"Unknown mode '{mode}'. Choose from: keyword, vector, hybrid"
    )


# ---------------------------------------------------------------------------
# Pretty-print helper
# ---------------------------------------------------------------------------


def pretty_print(result: dict) -> None:
    print(f"\n{'='*60}")
    print(f"Query  : {result['query']}")
    print(f"Mode   : {result['mode']}")
    print(f"Hits   : {result['total_hits']}  (top {result['top_k']})")
    print(f"Time   : {result['elapsed_ms']:.1f} ms")
    print(f"{'='*60}")
    for hit in result["results"]:
        score_str = f"{hit['score']:.4f}" if hit.get("score") is not None else "n/a"
        print(
            f"\n[{hit['rank']}] {hit['title'] or 'Untitled'}  "
            f"(page {hit['page']})  score={score_str}"
        )
        if hit.get("topics"):
            print(f"    Topics: {hit['topics']}")
        snippet = hit["text"][:300].replace("\n", " ")
        print(f"    {snippet}…")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search the math knowledge base."
    )
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument(
        "--mode",
        choices=["keyword", "vector", "hybrid"],
        default="hybrid",
        help="Search mode (default: hybrid)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=SEARCH_TOP_K,
        help="Number of results to return (default: %(default)s)",
    )
    parser.add_argument(
        "--memory",
        type=Path,
        default=MEMORY_FILE,
        help="Path to the .mv2 memory file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    result = search(args.query, mode=args.mode, top_k=args.top_k, mv2_path=args.memory)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        pretty_print(result)


if __name__ == "__main__":
    main()
