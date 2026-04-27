"""
Batch evaluation module.

Measures retrieval quality across three search modes (keyword, vector, hybrid)
using a labelled question set.

Metrics computed
----------------
- Top-1 / Top-3 / Top-5 Hit Rate (fraction of questions where a relevant chunk
  appears within the top-k results)
- MRR — Mean Reciprocal Rank (average of 1/rank of the first relevant hit)
- Average retrieval latency (ms)
- Average score of the first relevant hit

Input files
-----------
questions.csv
    ``question_id, question, topic``

labels.csv
    ``question_id, relevant_chunk_ids``
    Relevant chunk IDs are separated by semicolons, e.g. ``"C00001;C00042"``.

Output
------
results/retrieval_results.csv   — per-question, per-mode detail
results/metrics.csv             — aggregated metrics table

Usage
-----
    python src/evaluate.py \\
        --questions data/questions.csv \\
        --labels    data/labels.csv \\
        --memory    memory/math_knowledge.mv2 \\
        --output    results/metrics.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    LABELS_CSV,
    MEMORY_FILE,
    METRICS_CSV,
    QUESTIONS_CSV,
    RESULTS_DIR,
    RETRIEVAL_RESULTS_CSV,
    SEARCH_TOP_K,
)
from search import search

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

EVAL_MODES = ["keyword", "hybrid"]
EVAL_TOP_K = 5


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_questions(path: Path) -> list[dict]:
    """Load questions CSV.  Returns list of dicts with keys: question_id, question, topic."""
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_labels(path: Path) -> dict[str, list[str]]:
    """Load labels CSV.  Returns mapping question_id → list of relevant chunk_ids."""
    mapping: dict[str, list[str]] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            qid = row["question_id"].strip()
            raw = row.get("relevant_chunk_ids", "")
            chunk_ids = [c.strip() for c in raw.split(";") if c.strip()]
            mapping[qid] = chunk_ids
    return mapping


# ---------------------------------------------------------------------------
# Per-query evaluation
# ---------------------------------------------------------------------------


def _hits_at_k(results: list[dict], relevant: list[str], k: int) -> bool:
    """Return True if any of the top-k results is in *relevant*."""
    top = results[:k]
    result_ids = {r.get("chunk_id", "") for r in top}
    return bool(result_ids & set(relevant))


def _reciprocal_rank(results: list[dict], relevant: list[str]) -> float:
    """Return the reciprocal rank of the first relevant result, or 0."""
    relevant_set = set(relevant)
    for i, r in enumerate(results, start=1):
        if r.get("chunk_id", "") in relevant_set:
            return 1.0 / i
    return 0.0


def _first_relevant_score(results: list[dict], relevant: list[str]) -> float | None:
    """Return the score of the first relevant result, or None."""
    relevant_set = set(relevant)
    for r in results:
        if r.get("chunk_id", "") in relevant_set:
            return r.get("score")
    return None


# ---------------------------------------------------------------------------
# Full evaluation run
# ---------------------------------------------------------------------------


def evaluate(
    questions_path: Path,
    labels_path: Path,
    mv2_path: Path,
    output_metrics: Path,
    output_detail: Path | None = None,
    modes: list[str] | None = None,
    top_k: int = EVAL_TOP_K,
) -> dict[str, dict[str, Any]]:
    """Run the full evaluation and return a metrics dict.

    Returns
    -------
    dict mapping mode → metrics dict.
    """
    if modes is None:
        modes = EVAL_MODES

    questions = load_questions(questions_path)
    labels = load_labels(labels_path)

    if not questions:
        logger.error("No questions found in %s", questions_path)
        sys.exit(1)

    logger.info(
        "Evaluating %d questions × %d modes (top_k=%d) …",
        len(questions), len(modes), top_k,
    )

    # detail_rows collects one row per (question, mode)
    detail_rows: list[dict] = []

    # mode → accumulated metrics
    accum: dict[str, dict[str, Any]] = {
        m: {
            "hit_1": 0, "hit_3": 0, "hit_5": 0,
            "rr_sum": 0.0, "latency_sum": 0.0, "score_sum": 0.0,
            "score_count": 0, "n": 0,
        }
        for m in modes
    }

    for q in questions:
        qid = q["question_id"].strip()
        question_text = q["question"].strip()
        relevant = labels.get(qid, [])

        if not relevant:
            logger.warning("No labels for question %s — skipping.", qid)
            continue

        for mode in modes:
            t0 = time.perf_counter()
            try:
                res = search(question_text, mode=mode, top_k=top_k, mv2_path=mv2_path)
            except Exception as exc:  # noqa: BLE001
                logger.error("Search failed for q=%s mode=%s: %s", qid, mode, exc)
                continue
            latency = (time.perf_counter() - t0) * 1000

            results = res.get("results", [])
            h1 = _hits_at_k(results, relevant, 1)
            h3 = _hits_at_k(results, relevant, 3)
            h5 = _hits_at_k(results, relevant, 5)
            rr = _reciprocal_rank(results, relevant)
            fscore = _first_relevant_score(results, relevant)

            a = accum[mode]
            a["hit_1"] += int(h1)
            a["hit_3"] += int(h3)
            a["hit_5"] += int(h5)
            a["rr_sum"] += rr
            a["latency_sum"] += latency
            if fscore is not None:
                a["score_sum"] += fscore
                a["score_count"] += 1
            a["n"] += 1

            detail_rows.append(
                {
                    "question_id": qid,
                    "question": question_text,
                    "topic": q.get("topic", ""),
                    "mode": mode,
                    "hit_1": int(h1),
                    "hit_3": int(h3),
                    "hit_5": int(h5),
                    "reciprocal_rank": round(rr, 4),
                    "latency_ms": round(latency, 2),
                    "first_relevant_score": round(fscore, 4) if fscore is not None else "",
                    "relevant_chunks": ";".join(relevant),
                    "returned_chunks": ";".join(
                        r.get("chunk_id", "") for r in results
                    ),
                }
            )

    # Aggregate
    metrics: dict[str, dict[str, Any]] = {}
    for mode, a in accum.items():
        n = a["n"] or 1
        metrics[mode] = {
            "mode": mode,
            "num_questions": a["n"],
            "top1_hit_rate": round(a["hit_1"] / n, 4),
            "top3_hit_rate": round(a["hit_3"] / n, 4),
            "top5_hit_rate": round(a["hit_5"] / n, 4),
            "mrr": round(a["rr_sum"] / n, 4),
            "avg_latency_ms": round(a["latency_sum"] / n, 2),
            "avg_first_relevant_score": (
                round(a["score_sum"] / a["score_count"], 4)
                if a["score_count"] > 0
                else None
            ),
        }

    # Write metrics CSV
    output_metrics.parent.mkdir(parents=True, exist_ok=True)
    metric_fields = [
        "mode", "num_questions",
        "top1_hit_rate", "top3_hit_rate", "top5_hit_rate",
        "mrr", "avg_latency_ms", "avg_first_relevant_score",
    ]
    with output_metrics.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=metric_fields)
        writer.writeheader()
        for m in modes:
            writer.writerow(metrics[m])
    logger.info("Metrics written to %s", output_metrics)

    # Write detail CSV
    if output_detail:
        output_detail.parent.mkdir(parents=True, exist_ok=True)
        if detail_rows:
            fields = list(detail_rows[0].keys())
            with output_detail.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                writer.writerows(detail_rows)
        logger.info("Detail results written to %s", output_detail)

    return metrics


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality across search modes."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=QUESTIONS_CSV,
        help="Questions CSV (default: data/questions.csv)",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=LABELS_CSV,
        help="Labels CSV (default: data/labels.csv)",
    )
    parser.add_argument(
        "--memory",
        type=Path,
        default=MEMORY_FILE,
        help="Path to the .mv2 file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=METRICS_CSV,
        help="Output metrics CSV (default: results/metrics.csv)",
    )
    parser.add_argument(
        "--detail",
        type=Path,
        default=RETRIEVAL_RESULTS_CSV,
        help="Output per-question detail CSV (default: results/retrieval_results.csv)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=EVAL_TOP_K,
        help="Maximum number of results to consider (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    metrics = evaluate(
        questions_path=args.questions,
        labels_path=args.labels,
        mv2_path=args.memory,
        output_metrics=args.output,
        output_detail=args.detail,
        top_k=args.top_k,
    )
    print("\n=== Evaluation Results ===")
    for mode, m in metrics.items():
        print(
            f"{mode:10s}  Hit@1={m['top1_hit_rate']:.2%}  "
            f"Hit@3={m['top3_hit_rate']:.2%}  "
            f"Hit@5={m['top5_hit_rate']:.2%}  "
            f"MRR={m['mrr']:.4f}  "
            f"Latency={m['avg_latency_ms']:.1f}ms"
        )


if __name__ == "__main__":
    main()
