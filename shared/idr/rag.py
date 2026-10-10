"""Retrieval-Augmented Generation (RAG) knowledge engine for the IDR project.

Provides fast, deterministic hybrid retrieval over project architecture,
requirements, benchmarks, evidence reports, and edge-engine code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass(frozen=True)
class KnowledgeChunk:
    """A semantic chunk of documentation, evidence, or code."""

    chunk_id: str
    source: str
    section: str
    content: str
    chunk_type: str = "doc"  # 'doc', 'metric', 'code'

    def summary(self) -> str:
        preview = self.content.replace("\n", " ").strip()
        if len(preview) > 100:
            preview = preview[:97] + "..."
        return f"[{self.source} > {self.section}] {preview}"


@dataclass(frozen=True)
class RagResponse:
    """Grounded answer synthesized from retrieved project knowledge."""

    query: str
    answer: str
    retrieved_chunks: list[tuple[KnowledgeChunk, float]]
    sources: list[str]
    confidence_score: float

    def format_output(self, show_chunks: bool = True) -> str:
        lines = [
            "=" * 60,
            f"QUERY: {self.query}",
            "=" * 60,
            f"\nANSWER:\n{self.answer}\n",
            "-" * 60,
            f"SOURCES: {', '.join(self.sources)}",
            f"CONFIDENCE: {self.confidence_score:.2f}",
        ]
        if show_chunks and self.retrieved_chunks:
            lines.append("\nTOP RETRIEVED CONTEXT:")
            for rank, (chunk, score) in enumerate(self.retrieved_chunks, start=1):
                clean_snippet = chunk.content.strip()[:300].encode("ascii", "replace").decode("ascii")
                clean_section = chunk.section.encode("ascii", "replace").decode("ascii")
                lines.append(f"\n[{rank}] (Score: {score:.3f}) {chunk.source} > {clean_section}:")
                lines.append(f"    {clean_snippet}...")
        lines.append("=" * 60)
        text = "\n".join(lines)
        return text.encode("ascii", "replace").decode("ascii")


class IdrKnowledgeBase:
    """Parses and chunks project documents, benchmarks, and core code."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load_all_chunks(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        chunks.extend(self._load_markdown_docs())
        chunks.extend(self._load_evidence_reports())
        chunks.extend(self._load_core_code_modules())
        return chunks

    def _load_markdown_docs(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        md_paths = list((self.root / "docs").glob("**/*.md"))
        readme = self.root / "README.md"
        if readme.exists():
            md_paths.append(readme)

        for path in md_paths:
            rel_path = path.relative_to(self.root).as_posix()
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # Split by markdown headers
            sections = re.split(r"\n(?=#{1,3}\s+)", text)
            for idx, sec in enumerate(sections):
                sec = sec.strip()
                if not sec:
                    continue
                # Extract header line
                first_line = sec.split("\n")[0]
                header = first_line.lstrip("#").strip() if first_line.startswith("#") else "Overview"
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"{rel_path}:{idx}",
                        source=rel_path,
                        section=header,
                        content=sec,
                        chunk_type="doc",
                    )
                )
        return chunks

    def _load_evidence_reports(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        evidence_dir = self.root / "docs" / "evidence"
        if not evidence_dir.exists():
            return chunks

        for json_path in evidence_dir.glob("**/*.json"):
            rel_path = json_path.relative_to(self.root).as_posix()
            try:
                data = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue

            formatted = json.dumps(data, indent=2)
            dataset_val = data.get("dataset")
            dataset_name = dataset_val.get("name") if isinstance(dataset_val, dict) else dataset_val
            name = data.get("name") or dataset_name or json_path.stem
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{rel_path}:0",
                    source=rel_path,
                    section=f"Evidence Report: {name}",
                    content=f"Report file: {rel_path}\nData:\n{formatted}",
                    chunk_type="metric",
                )
            )
        return chunks

    def _load_core_code_modules(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        code_targets = [
            self.root / "edge-engine" / "idr_engine" / "fusion.py",
            self.root / "edge-engine" / "idr_engine" / "constraints.py",
            self.root / "mobile" / "app" / "src" / "main" / "java" / "org" / "sih" / "idr" / "NativeNavigationEngine.kt",
            self.root / "mobile" / "app" / "src" / "main" / "java" / "org" / "sih" / "idr" / "VehicleCalibration.kt",
            self.root / "scripts" / "train_io_vnbd.py",
            self.root / "scripts" / "release_check.py",
            self.root / "shared" / "idr" / "models.py",
        ]

        for path in code_targets:
            if not path.exists():
                continue
            rel_path = path.relative_to(self.root).as_posix()
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # Split code files by major class or function definitions
            parts = re.split(r"\n(?=(?:class\s+|def\s+|fun\s+))", text)
            for idx, part in enumerate(parts):
                part = part.strip()
                if len(part) < 40:
                    continue
                first_line = part.split("\n")[0].strip()
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"{rel_path}:{idx}",
                        source=rel_path,
                        section=first_line[:50],
                        content=part[:1200],  # bounded snippet
                        chunk_type="code",
                    )
                )
        return chunks


class IdrRetriever:
    """Fast hybrid n-gram TF-IDF vector retriever."""

    def __init__(self, chunks: Sequence[KnowledgeChunk]) -> None:
        self.chunks = list(chunks)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_df=0.98,
            token_pattern=r"(?u)\b[\w-]{2,}\b",
        )
        texts = [f"{c.source} {c.section} {c.content}" for c in self.chunks]
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)

    def retrieve(self, query: str, top_k: int = 4) -> list[tuple[KnowledgeChunk, float]]:
        if not self.chunks or not query.strip():
            return []
        query_vec = self.vectorizer.transform([query])
        # Cosine similarity (L2 normalized rows in TfidfVectorizer)
        scores = (self.tfidf_matrix @ query_vec.T).toarray().ravel()
        top_indices = np.argsort(scores)[::-1][:top_k]

        results: list[tuple[KnowledgeChunk, float]] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0.01:
                results.append((self.chunks[idx], score))
        return results


class IdrRagEngine:
    """Core RAG query interface and extractive answer synthesizer."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]
        self.kb = IdrKnowledgeBase(self.root)
        self.chunks = self.kb.load_all_chunks()
        self.retriever = IdrRetriever(self.chunks)

    def query(self, question: str, top_k: int = 4) -> RagResponse:
        results = self.retriever.retrieve(question, top_k=top_k)
        if not results:
            return RagResponse(
                query=question,
                answer="No relevant documentation or evidence found for this query in the repository.",
                retrieved_chunks=[],
                sources=[],
                confidence_score=0.0,
            )

        sources = list(dict.fromkeys(chunk.source for chunk, _ in results))
        best_score = results[0][1]

        answer = self._synthesize_answer(question, results)
        return RagResponse(
            query=question,
            answer=answer,
            retrieved_chunks=results,
            sources=sources,
            confidence_score=min(1.0, best_score * 2.2),
        )

    def _synthesize_answer(
        self,
        question: str,
        results: list[tuple[KnowledgeChunk, float]],
    ) -> str:
        """Synthesize an authoritative, structured response from retrieved context."""
        points: list[str] = []
        q_lower = question.lower()

        # Check for key domain topics
        for chunk, score in results[:3]:
            content = chunk.content.strip()
            # Clean up content for display
            lines = [line.strip() for line in content.split("\n") if line.strip() and not line.startswith("```")]
            snippet = " ".join(lines[:4])
            if len(snippet) > 250:
                snippet = snippet[:247] + "..."
            points.append(f"* **From [{chunk.source} > {chunk.section}]**:\n  {snippet}")

        summary_header = "Based on verified repository evidence and architecture:\n"
        return summary_header + "\n\n".join(points)
