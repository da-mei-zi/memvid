"""
Visualisation module.

Reads evaluation results and chunk statistics to produce publication-quality
matplotlib charts saved under ``results/figures/``.

Charts generated
----------------
topic_distribution.png
    Bar chart of how many chunks belong to each topic label.

topk_hit_rate.png
    Grouped bar chart comparing Top-1 / Top-3 / Top-5 hit rates across
    keyword and hybrid search modes.

mrr_comparison.png
    Bar chart of Mean Reciprocal Rank per search mode.

latency_comparison.png
    Bar chart of average retrieval latency (ms) per search mode.

chunk_size_distribution.png
    Histogram of chunk lengths (characters) in the knowledge base.

Usage
-----
    python src/visualize.py \\
        --chunks   data/chunks.csv \\
        --metrics  results/metrics.csv \\
        --output   results/figures
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CHUNKS_CSV, FIGURES_DIR, METRICS_CSV, TOPIC_KEYWORDS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Plotting helpers — lazy import so the module is importable without matplotlib
# ---------------------------------------------------------------------------


def _get_plt():
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend for headless environments
        import matplotlib.pyplot as plt  # type: ignore[import]
        return plt
    except ImportError:
        logger.error(
            "matplotlib is not installed. Install it with: pip install matplotlib"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def _load_chunks(chunks_csv: Path) -> list[dict]:
    if not chunks_csv.exists():
        logger.warning("chunks.csv not found: %s", chunks_csv)
        return []
    with chunks_csv.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _load_metrics(metrics_csv: Path) -> list[dict]:
    if not metrics_csv.exists():
        logger.warning("metrics.csv not found: %s", metrics_csv)
        return []
    with metrics_csv.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Individual chart generators
# ---------------------------------------------------------------------------


def plot_topic_distribution(chunks: list[dict], out_dir: Path) -> Path:
    """Bar chart: number of chunks per topic label."""
    plt = _get_plt()

    # Count unique topics (a chunk can have multiple topics separated by ';').
    topic_counts: dict[str, int] = {}
    for row in chunks:
        for topic in row.get("topics", "").split(";"):
            topic = topic.strip()
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

    if not topic_counts:
        logger.warning("No topic data found — skipping topic_distribution chart.")
        return out_dir / "topic_distribution.png"

    topics = sorted(topic_counts, key=lambda t: -topic_counts[t])
    counts = [topic_counts[t] for t in topics]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(topics, counts, color="#4C72B0", edgecolor="white")
    ax.bar_label(bars, padding=3, fontsize=9)
    ax.set_xlabel("Number of Chunks", fontsize=11)
    ax.set_title("Knowledge Base: Chunk Distribution by Topic", fontsize=13)
    ax.invert_yaxis()
    plt.tight_layout()

    path = out_dir / "topic_distribution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved %s", path)
    return path


def plot_topk_hit_rate(metrics: list[dict], out_dir: Path) -> Path:
    """Grouped bar chart: Top-1 / Top-3 / Top-5 hit rates per mode."""
    plt = _get_plt()
    import numpy as np  # type: ignore[import]

    if not metrics:
        logger.warning("No metrics data — skipping topk_hit_rate chart.")
        return out_dir / "topk_hit_rate.png"

    modes = [m["mode"] for m in metrics]
    hit1 = [float(m.get("top1_hit_rate", 0)) for m in metrics]
    hit3 = [float(m.get("top3_hit_rate", 0)) for m in metrics]
    hit5 = [float(m.get("top5_hit_rate", 0)) for m in metrics]

    x = np.arange(len(modes))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width, hit1, width, label="Top-1", color="#4C72B0")
    ax.bar(x, hit3, width, label="Top-3", color="#55A868")
    ax.bar(x + width, hit5, width, label="Top-5", color="#C44E52")

    ax.set_ylabel("Hit Rate", fontsize=11)
    ax.set_title("Retrieval Hit Rate by Search Mode", fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([m.upper() for m in modes], fontsize=11)
    ax.set_ylim(0, 1.15)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{v:.0%}")
    )
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    path = out_dir / "topk_hit_rate.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved %s", path)
    return path


def plot_mrr_comparison(metrics: list[dict], out_dir: Path) -> Path:
    """Bar chart: MRR per search mode."""
    plt = _get_plt()

    if not metrics:
        logger.warning("No metrics data — skipping mrr_comparison chart.")
        return out_dir / "mrr_comparison.png"

    modes = [m["mode"].upper() for m in metrics]
    mrrs = [float(m.get("mrr", 0)) for m in metrics]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(modes, mrrs, color=["#4C72B0", "#55A868", "#C44E52"][:len(modes)],
                  edgecolor="white", width=0.4)
    ax.bar_label(bars, labels=[f"{v:.4f}" for v in mrrs], padding=3, fontsize=10)
    ax.set_ylabel("MRR", fontsize=11)
    ax.set_title("Mean Reciprocal Rank by Search Mode", fontsize=13)
    ax.set_ylim(0, max(mrrs) * 1.3 if mrrs else 1.0)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    path = out_dir / "mrr_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved %s", path)
    return path


def plot_latency_comparison(metrics: list[dict], out_dir: Path) -> Path:
    """Bar chart: average retrieval latency per mode."""
    plt = _get_plt()

    if not metrics:
        logger.warning("No metrics data — skipping latency_comparison chart.")
        return out_dir / "latency_comparison.png"

    modes = [m["mode"].upper() for m in metrics]
    latencies = [float(m.get("avg_latency_ms", 0)) for m in metrics]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(modes, latencies, color=["#4C72B0", "#55A868", "#C44E52"][:len(modes)],
                  edgecolor="white", width=0.4)
    ax.bar_label(bars, labels=[f"{v:.1f} ms" for v in latencies], padding=3, fontsize=10)
    ax.set_ylabel("Average Latency (ms)", fontsize=11)
    ax.set_title("Average Retrieval Latency by Search Mode", fontsize=13)
    ax.set_ylim(0, max(latencies) * 1.3 if latencies else 100)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    path = out_dir / "latency_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved %s", path)
    return path


def plot_chunk_size_distribution(chunks: list[dict], out_dir: Path) -> Path:
    """Histogram of chunk lengths in characters."""
    plt = _get_plt()

    if not chunks:
        logger.warning("No chunk data — skipping chunk_size_distribution chart.")
        return out_dir / "chunk_size_distribution.png"

    lengths = [len(row.get("text", "")) for row in chunks]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(lengths, bins=40, color="#4C72B0", edgecolor="white", alpha=0.85)
    ax.axvline(sum(lengths) / len(lengths), color="red", linestyle="--",
               label=f"Mean: {sum(lengths)/len(lengths):.0f} chars")
    ax.set_xlabel("Chunk Length (characters)", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title("Distribution of Chunk Lengths", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    path = out_dir / "chunk_size_distribution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved %s", path)
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_all(
    chunks_csv: Path = CHUNKS_CSV,
    metrics_csv: Path = METRICS_CSV,
    out_dir: Path = FIGURES_DIR,
) -> list[Path]:
    """Generate all charts and return the list of saved file paths."""
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks = _load_chunks(chunks_csv)
    metrics = _load_metrics(metrics_csv)

    paths: list[Path] = [
        plot_topic_distribution(chunks, out_dir),
        plot_chunk_size_distribution(chunks, out_dir),
        plot_topk_hit_rate(metrics, out_dir),
        plot_mrr_comparison(metrics, out_dir),
        plot_latency_comparison(metrics, out_dir),
    ]
    return paths


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate evaluation and knowledge-base visualisation charts."
    )
    parser.add_argument(
        "--chunks",
        type=Path,
        default=CHUNKS_CSV,
        help="Chunks CSV (default: data/chunks.csv)",
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        default=METRICS_CSV,
        help="Metrics CSV produced by evaluate.py (default: results/metrics.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FIGURES_DIR,
        help="Output directory for figures (default: results/figures)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    saved = generate_all(
        chunks_csv=args.chunks,
        metrics_csv=args.metrics,
        out_dir=args.output,
    )
    print(f"Generated {len(saved)} figure(s) in {args.output}")
    for p in saved:
        print(f"  {p}")


if __name__ == "__main__":
    main()
