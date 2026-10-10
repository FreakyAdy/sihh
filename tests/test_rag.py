import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from idr.rag import IdrKnowledgeBase, IdrRagEngine, IdrRetriever, KnowledgeChunk, RagResponse


class RagSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = IdrRagEngine(root=REPO_ROOT)

    def test_knowledge_base_indexes_docs_evidence_and_code(self) -> None:
        chunks = self.engine.chunks
        self.assertGreater(len(chunks), 50, "Knowledge base should index at least 50 chunks")

        types = {c.chunk_type for c in chunks}
        self.assertIn("doc", types)
        self.assertIn("metric", types)
        self.assertIn("code", types)

        sources = {c.source for c in chunks}
        self.assertTrue(any("README.md" in s for s in sources))
        self.assertTrue(any("synthetic-1km-report.json" in s for s in sources))
        self.assertTrue(any("fusion.py" in s for s in sources))

    def test_retriever_ranks_drift_query_accurately(self) -> None:
        results = self.engine.retriever.retrieve("synthetic 1km drift percentage", top_k=5)
        self.assertGreater(len(results), 0)

        # Top results should have positive scores and relate to benchmark/reports
        top_chunk, score = results[0]
        self.assertGreater(score, 0.05)
        self.assertIsInstance(top_chunk, KnowledgeChunk)

        # Check retrieval relevance
        combined_text = " ".join(c.content.lower() for c, _ in results)
        self.assertTrue("drift" in combined_text or "benchmark" in combined_text)

    def test_rag_engine_synthesizes_grounded_answer(self) -> None:
        response = self.engine.query("What is the outage recovery hysteresis duration?")
        self.assertIsInstance(response, RagResponse)
        self.assertGreater(response.confidence_score, 0.0)
        self.assertGreater(len(response.sources), 0)
        self.assertIn("Based on verified repository evidence", response.answer)

        formatted = response.format_output()
        self.assertIn("QUERY:", formatted)
        self.assertIn("SOURCES:", formatted)
        self.assertIn("CONFIDENCE:", formatted)

    def test_empty_or_whitespace_query_returns_fallback(self) -> None:
        response = self.engine.query("   ")
        self.assertEqual(len(response.retrieved_chunks), 0)
        self.assertEqual(response.confidence_score, 0.0)
        self.assertIn("No relevant documentation", response.answer)


if __name__ == "__main__":
    unittest.main()
