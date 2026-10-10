#!/usr/bin/env python3
"""IDR RAG CLI: Retrieval-Augmented Generation query engine for ISRO PS 26168.

Provides grounded question answering and evidence search across project architecture,
requirements, benchmark reports, and fusion algorithms.

Usage:
    python scripts/idr_rag.py --query "What is the synthetic benchmark drift?"
    python scripts/idr_rag.py --stats
    python scripts/idr_rag.py --interactive
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.idr import IdrRagEngine


def run_query(engine: IdrRagEngine, question: str, top_k: int = 4, as_json: bool = False) -> None:
    response = engine.query(question, top_k=top_k)
    if as_json:
        data = {
            "query": response.query,
            "answer": response.answer,
            "sources": response.sources,
            "confidence_score": response.confidence_score,
            "retrieved_chunks": [
                {
                    "source": chunk.source,
                    "section": chunk.section,
                    "chunk_type": chunk.chunk_type,
                    "score": round(score, 4),
                    "snippet": chunk.content[:300],
                }
                for chunk, score in response.retrieved_chunks
            ],
        }
        print(json.dumps(data, indent=2))
    else:
        print(response.format_output())


def run_interactive(engine: IdrRagEngine, top_k: int = 4) -> None:
    print("=" * 65)
    print("  ISRO PS 26168: IDR Intelligent Dead Reckoning RAG Assistant")
    print("=" * 65)
    print(f"Indexed {len(engine.chunks)} knowledge chunks from docs, reports, and code.")
    print("Type your question below (or 'exit' / 'quit' to leave):\n")

    while True:
        try:
            sys.stdout.write("rag> ")
            sys.stdout.flush()
            question = sys.stdin.readline()
            if not question:
                break
            question = question.strip()
            if not question:
                continue
            if question.lower() in ("exit", "quit", "q"):
                print("Exiting RAG assistant. Goodbye!")
                break
            run_query(engine, question, top_k=top_k)
            print()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting RAG assistant.")
            break


def run_stats(engine: IdrRagEngine) -> None:
    print("=" * 60)
    print("IDR RAG Knowledge Base Index Statistics")
    print("=" * 60)
    total_chunks = len(engine.chunks)
    types: dict[str, int] = {}
    sources: dict[str, int] = {}
    for c in engine.chunks:
        types[c.chunk_type] = types.get(c.chunk_type, 0) + 1
        sources[c.source] = sources.get(c.source, 0) + 1

    print(f"Total indexed chunks: {total_chunks}")
    print("\nChunks by type:")
    for ctype, count in sorted(types.items()):
        print(f"  - {ctype:<10}: {count:>3} chunks")

    print(f"\nIndexed files ({len(sources)} total):")
    for src, count in sorted(sources.items()):
        print(f"  - {src:<45}: {count:>3} chunks")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IDR RAG Engine: Grounded search & synthesis over SIH 2026 project evidence."
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Question or query string to ask the IDR knowledge base.",
    )
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=4,
        help="Number of relevant chunks to retrieve (default: 4).",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run interactive command line query session.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display statistics about the indexed knowledge base.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output response as formatted JSON.",
    )

    args = parser.parse_args()

    engine = IdrRagEngine(root=REPO_ROOT)

    if args.stats:
        run_stats(engine)
    elif args.query:
        run_query(engine, args.query, top_k=args.top_k, as_json=args.json)
    elif args.interactive or len(sys.argv) == 1:
        run_interactive(engine, top_k=args.top_k)


if __name__ == "__main__":
    main()
