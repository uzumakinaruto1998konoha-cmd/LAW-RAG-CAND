"""Unit tests for PHASE 3 retrieval models and chunking."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from law_rag.retrieval.models import (
    Chunk,
    ChunkSet,
    IndexManifest,
    IndexStatus,
    IndexType,
    QueryType,
    RetrievalMethod,
    RetrievalResult,
    RetrievalTrace,
)

NOW = datetime(2026, 9, 27, 11, 30, tzinfo=timezone.utc)


class ChunkSetTests(unittest.TestCase):
    def test_requires_positive_chunk_count(self) -> None:
        with self.assertRaises(ValueError):
            ChunkSet.new(
                chunk_set_id="cs1",
                version_id="v1",
                chunker_version="chunker-v1",
                chunker_config_hash="a" * 64,
                chunk_count=-1,
                created_by="user1",
            )

    def test_requires_64_char_config_hash(self) -> None:
        with self.assertRaises(ValueError):
            ChunkSet.new(
                chunk_set_id="cs1",
                version_id="v1",
                chunker_version="chunker-v1",
                chunker_config_hash="abc",
                chunk_count=10,
                created_by="user1",
            )

    def test_creates_active_chunk_set(self) -> None:
        chunk_set = ChunkSet.new(
            chunk_set_id="cs1",
            version_id="v1",
            chunker_version="chunker-v1",
            chunker_config_hash="a" * 64,
            chunk_count=10,
            created_by="user1",
        )

        self.assertEqual(chunk_set.chunk_count, 10)
        self.assertTrue(chunk_set.is_active)


class ChunkTests(unittest.TestCase):
    def test_requires_non_negative_index(self) -> None:
        with self.assertRaises(ValueError):
            Chunk.new(
                chunk_id="ch1",
                chunk_set_id="cs1",
                version_id="v1",
                node_id="n1",
                chunk_index=-1,
                content="Test content",
                content_hash="a" * 64,
                structural_path="Điều 1",
            )

    def test_requires_non_empty_content(self) -> None:
        with self.assertRaises(ValueError):
            Chunk.new(
                chunk_id="ch1",
                chunk_set_id="cs1",
                version_id="v1",
                node_id="n1",
                chunk_index=0,
                content="   ",
                content_hash="a" * 64,
                structural_path="Điều 1",
            )

    def test_requires_structural_path(self) -> None:
        with self.assertRaises(ValueError):
            Chunk.new(
                chunk_id="ch1",
                chunk_set_id="cs1",
                version_id="v1",
                node_id="n1",
                chunk_index=0,
                content="Test content",
                content_hash="a" * 64,
                structural_path="",
            )

    def test_creates_chunk_with_location(self) -> None:
        chunk = Chunk.new(
            chunk_id="ch1",
            chunk_set_id="cs1",
            version_id="v1",
            node_id="n1",
            chunk_index=0,
            content="Điều này quy định phạm vi áp dụng.",
            content_hash="a" * 64,
            structural_path="Chương I / Điều 1",
            page_start=1,
            page_end=1,
            page_spans=("page:1/para:1",),
        )

        self.assertTrue(chunk.has_location)
        self.assertEqual(chunk.page_start, 1)


class IndexManifestTests(unittest.TestCase):
    def test_requires_positive_version(self) -> None:
        with self.assertRaises(ValueError):
            IndexManifest.new(
                manifest_id="m1",
                manifest_version=0,
                index_type=IndexType.HYBRID,
                pipeline_version="index-v1",
                created_by="admin",
            )

    def test_failed_index_requires_error_message(self) -> None:
        with self.assertRaises(ValueError):
            IndexManifest(
                manifest_id="m1",
                manifest_version=1,
                index_type=IndexType.HYBRID,
                status=IndexStatus.FAILED,
                pipeline_version="index-v1",
                embedding_model=None,
                embedding_dimension=None,
                lexical_analyzer=None,
                chunk_set_count=0,
                chunk_count=0,
                document_count=0,
                build_started_at=NOW,
                build_completed_at=None,
                activated_at=None,
                retired_at=None,
                created_by="admin",
                error_message=None,
            )

    def test_creates_building_manifest(self) -> None:
        manifest = IndexManifest.new(
            manifest_id="m1",
            manifest_version=1,
            index_type=IndexType.HYBRID,
            pipeline_version="index-v1",
            created_by="admin",
            embedding_model="bge-m3",
            embedding_dimension=1024,
        )

        self.assertEqual(manifest.status, IndexStatus.BUILDING)
        self.assertTrue(manifest.is_building)
        self.assertFalse(manifest.is_active)


class RetrievalTraceTests(unittest.TestCase):
    def test_requires_non_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalTrace.new(
                trace_id="t1",
                user_id="u1",
                query="   ",
                query_type=QueryType.SEMANTIC,
                result_count=0,
            )

    def test_requires_non_negative_result_count(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalTrace.new(
                trace_id="t1",
                user_id="u1",
                query="test query",
                query_type=QueryType.SEMANTIC,
                result_count=-1,
            )

    def test_creates_trace_with_filters(self) -> None:
        trace = RetrievalTrace.new(
            trace_id="t1",
            user_id="u1",
            query="Quyết định 184/2024",
            query_type=QueryType.EXACT,
            result_count=5,
            as_of_date=date(2024, 12, 31),
            filters={"document_type": "Quyết định"},
            manifest_id="m1",
            latency_ms=150,
        )

        self.assertEqual(trace.query_type, QueryType.EXACT)
        self.assertEqual(trace.result_count, 5)
        self.assertIsNotNone(trace.filters)


class RetrievalResultTests(unittest.TestCase):
    def test_requires_positive_rank(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalResult.new(
                trace_id="t1",
                chunk_id="ch1",
                rank=0,
                score=0.95,
                retrieval_method=RetrievalMethod.FUSION,
            )

    def test_requires_score_between_0_and_1(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalResult.new(
                trace_id="t1",
                chunk_id="ch1",
                rank=1,
                score=1.5,
                retrieval_method=RetrievalMethod.FUSION,
            )

    def test_creates_retrieval_result(self) -> None:
        result = RetrievalResult.new(
            trace_id="t1",
            chunk_id="ch1",
            rank=1,
            score=0.95,
            retrieval_method=RetrievalMethod.RERANKED,
        )

        self.assertEqual(result.rank, 1)
        self.assertEqual(result.score, 0.95)
        self.assertEqual(result.retrieval_method, RetrievalMethod.RERANKED)


if __name__ == "__main__":
    unittest.main()
