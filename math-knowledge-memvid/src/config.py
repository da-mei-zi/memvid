"""
Configuration for Math-Knowledge-Memvid.

All tunable parameters and paths are centralised here so that individual
scripts can simply ``from config import cfg`` and read what they need.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
MEMORY_DIR: Path = BASE_DIR / "memory"
RESULTS_DIR: Path = BASE_DIR / "results"
FIGURES_DIR: Path = RESULTS_DIR / "figures"

RAW_DOCS_DIR: Path = DATA_DIR / "raw_docs"
PROCESSED_DIR: Path = DATA_DIR / "processed"

CHUNKS_CSV: Path = DATA_DIR / "chunks.csv"
QUESTIONS_CSV: Path = DATA_DIR / "questions.csv"
LABELS_CSV: Path = DATA_DIR / "labels.csv"
RETRIEVAL_RESULTS_CSV: Path = RESULTS_DIR / "retrieval_results.csv"
METRICS_CSV: Path = RESULTS_DIR / "metrics.csv"

MEMORY_FILE: Path = MEMORY_DIR / "math_knowledge.mv2"

# ---------------------------------------------------------------------------
# Memvid CLI binary
# ---------------------------------------------------------------------------
# Default location after `cargo build --bin memvid-cli` from the repo root.
# Override with the MEMVID_CLI environment variable.

MEMVID_CLI: str = os.environ.get(
    "MEMVID_CLI",
    str(BASE_DIR.parent / "target" / "debug" / "memvid-cli"),
)

# ---------------------------------------------------------------------------
# Chunking defaults
# ---------------------------------------------------------------------------

CHUNK_STRATEGY: str = "math-aware"   # fixed | paragraph | math-aware
CHUNK_SIZE: int = 400                 # target characters per chunk
CHUNK_OVERLAP: int = 80              # character overlap between consecutive chunks

# ---------------------------------------------------------------------------
# Search defaults
# ---------------------------------------------------------------------------

SEARCH_TOP_K: int = 5
SEARCH_SNIPPET_CHARS: int = 400

# ---------------------------------------------------------------------------
# Subject / topic keyword map used by the labeller in chunker.py
# ---------------------------------------------------------------------------

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Bochner formula": [
        "Bochner", "Bochner formula", "Bochner identity", "Bochner公式",
    ],
    "Ricci curvature": [
        "Ricci", "Ricci curvature", "Ricci曲率", "Ricci tensor",
    ],
    "Laplacian comparison": [
        "Laplacian comparison", "拉普拉斯比较", "comparison theorem",
    ],
    "harmonic function": [
        "harmonic function", "调和函数", "harmonic map", "harmonic",
    ],
    "maximum principle": [
        "maximum principle", "最大值原理", "Hopf maximum", "strong maximum",
    ],
    "gradient estimate": [
        "gradient estimate", "梯度估计", "Yau gradient", "Cheng-Yau",
    ],
    "Sobolev inequality": [
        "Sobolev", "Sobolev inequality", "Sobolev不等式",
    ],
    "eigenvalue estimate": [
        "eigenvalue", "first eigenvalue", "特征值", "Cheeger", "Lichnerowicz",
    ],
    "heat kernel": [
        "heat kernel", "heat equation", "热核", "热方程",
    ],
    "curvature": [
        "sectional curvature", "截面曲率", "Gaussian curvature", "scalar curvature",
        "曲率", "curvature tensor",
    ],
    "PDE": [
        "partial differential equation", "PDE", "elliptic", "parabolic",
        "偏微分方程",
    ],
    "Riemannian geometry": [
        "Riemannian", "Riemannian manifold", "黎曼几何", "geodesic",
        "测地线",
    ],
}
