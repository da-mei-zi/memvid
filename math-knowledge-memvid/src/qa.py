"""
Question-answering module.

Retrieves the top-k most relevant knowledge fragments for a user question and
either (a) generates a natural-language answer using an LLM API or (b) returns
a retrieval-only answer that cites sources without generating new text.

Two answer modes
----------------
retrieval
    Returns the top-3 most relevant chunks with source citations.  No LLM
    dependency — works entirely offline.

generative
    Calls the OpenAI Chat Completions API (or any OpenAI-compatible endpoint)
    with the retrieved context as the system prompt.  Set the environment
    variable ``OPENAI_API_KEY`` before using this mode.  Falls back to
    retrieval mode if the API key is not set.

Usage
-----
    python src/qa.py \\
        --question "Bochner 公式在调和函数估计中有什么作用？" \\
        --mode retrieval

    python src/qa.py \\
        --question "What is the Laplacian comparison theorem?" \\
        --mode generative
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MEMORY_FILE, SEARCH_TOP_K
from search import pretty_print, search

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a mathematics tutor specialising in Riemannian geometry, PDEs, and \
harmonic analysis.  The user has asked a question about their study materials.

Below are the most relevant excerpts from their personal knowledge base.  \
Use ONLY the information in these excerpts to answer the question.  \
If the excerpts do not contain enough information, say so clearly.  \
Always cite which excerpt(s) your answer draws from.
"""


def _build_context(results: list[dict]) -> str:
    """Assemble a numbered context block from search results."""
    lines: list[str] = []
    for i, r in enumerate(results, start=1):
        source = f"{r.get('title', 'Unknown')}  p.{r.get('page', '?')}"
        score_str = (
            f"  (similarity {r['score']:.3f})" if r.get("score") is not None else ""
        )
        lines.append(f"[{i}] {source}{score_str}")
        lines.append(r.get("text", "")[:600])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Retrieval-only answer
# ---------------------------------------------------------------------------


def _retrieval_answer(question: str, results: list[dict]) -> dict[str, Any]:
    """Build a retrieval-only answer dict without calling any LLM."""
    references: list[str] = []
    for i, r in enumerate(results, start=1):
        score_str = (
            f"，相似度 {r['score']:.2f}" if r.get("score") is not None else ""
        )
        ref = f"[{i}] {r.get('title', 'Unknown')}, p.{r.get('page', '?')}{score_str}"
        references.append(ref)

    answer_lines = ["以下是与问题最相关的知识片段：\n"]
    for i, r in enumerate(results, start=1):
        snippet = r.get("text", "")[:400].replace("\n", " ")
        answer_lines.append(f"[{i}] {snippet}…\n")

    return {
        "question": question,
        "mode": "retrieval",
        "answer": "\n".join(answer_lines),
        "references": references,
        "num_sources": len(results),
    }


# ---------------------------------------------------------------------------
# Generative answer
# ---------------------------------------------------------------------------


def _generative_answer(
    question: str,
    results: list[dict],
    model: str = "gpt-4o-mini",
    api_base: str = "https://api.openai.com/v1",
) -> dict[str, Any]:
    """Call an OpenAI-compatible API to generate a grounded answer."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPENAI_API_KEY not set — falling back to retrieval mode."
        )
        return _retrieval_answer(question, results)

    try:
        import openai  # type: ignore[import]
    except ImportError:
        logger.warning(
            "'openai' package not installed — falling back to retrieval mode. "
            "Install it with: pip install openai"
        )
        return _retrieval_answer(question, results)

    context = _build_context(results)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT + "\n\n" + context},
        {"role": "user", "content": question},
    ]

    try:
        client = openai.OpenAI(api_key=api_key, base_url=api_base)
        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.2,
            max_tokens=800,
        )
        answer = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenAI API error: %s — falling back to retrieval mode.", exc)
        return _retrieval_answer(question, results)

    references = [
        f"[{i}] {r.get('title', 'Unknown')}, p.{r.get('page', '?')}"
        + (f"，相似度 {r['score']:.2f}" if r.get("score") is not None else "")
        for i, r in enumerate(results, start=1)
    ]

    return {
        "question": question,
        "mode": "generative",
        "answer": answer,
        "references": references,
        "num_sources": len(results),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ask(
    question: str,
    mode: str = "retrieval",
    top_k: int = SEARCH_TOP_K,
    search_mode: str = "hybrid",
    mv2_path: Path | None = None,
    llm_model: str = "gpt-4o-mini",
    llm_api_base: str = "https://api.openai.com/v1",
) -> dict[str, Any]:
    """Answer *question* using the knowledge base.

    Parameters
    ----------
    question:    The user's natural-language question.
    mode:        ``"retrieval"`` or ``"generative"``.
    top_k:       Number of knowledge fragments to retrieve.
    search_mode: Search strategy passed to :func:`search.search`.
    mv2_path:    Override the default ``.mv2`` file path.
    llm_model:   LLM model name (only used in generative mode).
    llm_api_base: OpenAI-compatible API base URL.
    """
    if mv2_path is None:
        mv2_path = MEMORY_FILE

    search_result = search(question, mode=search_mode, top_k=top_k, mv2_path=mv2_path)
    results = search_result.get("results", [])

    if mode == "retrieval":
        return _retrieval_answer(question, results)
    if mode == "generative":
        return _generative_answer(question, results, model=llm_model, api_base=llm_api_base)

    raise ValueError(f"Unknown mode '{mode}'. Choose from: retrieval, generative")


def pretty_print_answer(response: dict) -> None:
    print(f"\n{'='*60}")
    print(f"问题：{response['question']}")
    print(f"\n回答 ({response['mode']})：")
    print(response["answer"])
    if response.get("references"):
        print("\n参考片段：")
        for ref in response["references"]:
            print(f"  {ref}")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask a question and get an answer from the knowledge base."
    )
    parser.add_argument(
        "--question", "-q", required=True, help="The question to answer"
    )
    parser.add_argument(
        "--mode",
        choices=["retrieval", "generative"],
        default="retrieval",
        help="Answer mode (default: retrieval)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=SEARCH_TOP_K,
        help="Number of knowledge fragments to retrieve (default: %(default)s)",
    )
    parser.add_argument(
        "--search-mode",
        choices=["keyword", "vector", "hybrid"],
        default="hybrid",
        help="Underlying search strategy (default: hybrid)",
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
    response = ask(
        args.question,
        mode=args.mode,
        top_k=args.top_k,
        search_mode=args.search_mode,
        mv2_path=args.memory,
    )
    if args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        pretty_print_answer(response)


if __name__ == "__main__":
    main()
