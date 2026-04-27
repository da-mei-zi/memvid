"""
Interactive command-line demo for Math-Knowledge-Memvid.

Provides a simple REPL where the user can ask questions and switch between
search modes without restarting the script.

Usage
-----
    python app/demo.py
    python app/demo.py --memory memory/math_knowledge.mv2 --mode hybrid
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the app/ subdirectory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import MEMORY_FILE, SEARCH_TOP_K
from qa import ask, pretty_print_answer
from search import search, pretty_print as pretty_print_search

BANNER = """
╔══════════════════════════════════════════════════════════╗
║       Math-Knowledge-Memvid  —  Interactive Demo         ║
╠══════════════════════════════════════════════════════════╣
║  Commands:                                               ║
║    <question>         — ask a question (retrieval mode)  ║
║    /mode <mode>       — switch mode: keyword|hybrid      ║
║    /top-k <n>         — change top-k (default: 5)        ║
║    /answer <mode>     — answer mode: retrieval|generative║
║    /search <query>    — raw search result                ║
║    /help              — show this help                   ║
║    /quit              — exit                             ║
╚══════════════════════════════════════════════════════════╝
"""


def run_demo(
    mv2_path: Path = MEMORY_FILE,
    default_mode: str = "hybrid",
    default_top_k: int = SEARCH_TOP_K,
    default_answer_mode: str = "retrieval",
) -> None:
    print(BANNER)

    if not mv2_path.exists():
        print(
            f"[ERROR] Memory file not found: {mv2_path}\n"
            "Build the knowledge base first:\n"
            "  1. python src/ingest.py\n"
            "  2. python src/chunker.py\n"
            "  3. python src/build_memory.py\n"
        )
        sys.exit(1)

    mode = default_mode
    top_k = default_top_k
    answer_mode = default_answer_mode

    print(f"[Memory file] {mv2_path}")
    print(f"[Search mode] {mode}   [Top-k] {top_k}   [Answer mode] {answer_mode}")
    print()

    while True:
        try:
            user_input = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input == "/quit" or user_input == "/exit":
            print("Goodbye!")
            break

        if user_input == "/help":
            print(BANNER)
            continue

        if user_input.startswith("/mode "):
            new_mode = user_input.split(None, 1)[1].strip()
            if new_mode in {"keyword", "vector", "hybrid"}:
                mode = new_mode
                print(f"[Search mode] switched to: {mode}")
            else:
                print("Unknown mode. Choose: keyword | vector | hybrid")
            continue

        if user_input.startswith("/top-k "):
            try:
                top_k = int(user_input.split(None, 1)[1])
                print(f"[Top-k] set to: {top_k}")
            except ValueError:
                print("Usage: /top-k <integer>")
            continue

        if user_input.startswith("/answer "):
            new_am = user_input.split(None, 1)[1].strip()
            if new_am in {"retrieval", "generative"}:
                answer_mode = new_am
                print(f"[Answer mode] switched to: {answer_mode}")
            else:
                print("Unknown answer mode. Choose: retrieval | generative")
            continue

        if user_input.startswith("/search "):
            query = user_input.split(None, 1)[1].strip()
            try:
                result = search(query, mode=mode, top_k=top_k, mv2_path=mv2_path)
                pretty_print_search(result)
            except Exception as exc:  # noqa: BLE001
                print(f"[Error] {exc}")
            continue

        # Default: treat input as a question.
        try:
            response = ask(
                user_input,
                mode=answer_mode,
                top_k=top_k,
                search_mode=mode,
                mv2_path=mv2_path,
            )
            pretty_print_answer(response)
        except Exception as exc:  # noqa: BLE001
            print(f"[Error] {exc}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive Math-Knowledge-Memvid demo."
    )
    parser.add_argument(
        "--memory",
        type=Path,
        default=MEMORY_FILE,
        help="Path to the .mv2 file (default: memory/math_knowledge.mv2)",
    )
    parser.add_argument(
        "--mode",
        choices=["keyword", "vector", "hybrid"],
        default="hybrid",
        help="Default search mode (default: hybrid)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=SEARCH_TOP_K,
        help="Default top-k (default: %(default)s)",
    )
    parser.add_argument(
        "--answer",
        choices=["retrieval", "generative"],
        default="retrieval",
        help="Default answer mode (default: retrieval)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    run_demo(
        mv2_path=args.memory,
        default_mode=args.mode,
        default_top_k=args.top_k,
        default_answer_mode=args.answer,
    )


if __name__ == "__main__":
    main()
