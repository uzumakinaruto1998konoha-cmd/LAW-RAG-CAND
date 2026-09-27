"""Unit tests for PHASE 3 Hybrid Retrieval: BM25, Vector Search, Fusion, ACL, and Reranking."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from law_rag.ingestion.authorization import AuthorizationService
from law_rag.ingestion.knowledge_models import AccessLevel, AppUser, ValidityStatus
from law_rag.retrieval.models import Chunk, QueryType, RetrievalMethod
from law_rag.retrieval.search import (
    BM25Index,
    DocumentMetadata,
    LegalReranker,
    RetrievalService,
    VectorSearchAdapter,
    cosine_similarity,
    reciprocal_rank_fusion,
    tokenize,
    weighted_score_fusion,
)

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def _make_chunk(
    chunk_id: str,
    version_id: str,
    structural_path: str,
    content: str,
    heading: str | None = None,
    page_start: int = 1,
) -> Chunk:
    return Chunk.new(
        chunk_id=chunk_id,
        chunk_set_id="cs1",
        version_id=version_id,
        node_id=f"node_{chunk_id}",
        chunk_index=1,
        content=content,
        content_hash="a" * 64,
        structural_path=structural_path,
        heading=heading,
        page_start=page_start,
        page_end=page_start,
    )


def _make_meta(
    version_id: str,
    document_number: str = "184/2024/QĐ-TTg",
    title: str = "Quy định thẩm quyền điều tra hình sự",
    document_type: str = "Quyết định",
    issuing_body: str = "Thủ tướng Chính phủ",
    collection_ids: tuple[str, ...] = ("coll_public",),
    validity_status: ValidityStatus = ValidityStatus.IN_FORCE,
    effective_date: date | None = date(2024, 1, 1),
    expiry_date: date | None = None,
) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=f"doc_{version_id}",
        version_id=version_id,
        document_number=document_number,
        title=title,
        issuing_body=issuing_body,
        document_type=document_type,
        issue_date=date(2024, 1, 1),
        effective_date=effective_date,
        expiry_date=expiry_date,
        collection_ids=collection_ids,
        validity_status=validity_status,
        is_verified=True,
    )


class BM25IndexTests(unittest.TestCase):
    def test_empty_search_returns_empty(self) -> None:
        idx = BM25Index()
        self.assertEqual(idx.search("thẩm quyền"), [])

    def test_scores_and_ranks_relevant_document(self) -> None:
        idx = BM25Index()
        idx.index("c1", "Thẩm quyền điều tra thuộc về cơ quan an ninh điều tra")
        idx.index("c2", "Quy định về thời hạn tạm giam bị can trong vụ án")
        results = idx.search("thẩm quyền điều tra", top_k=2)

        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0][0], "c1")
        self.assertGreater(results[0][1], 0.0)


class VectorSearchAdapterTests(unittest.TestCase):
    def test_cosine_similarity(self) -> None:
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v1, v2), 1.0)
        self.assertAlmostEqual(cosine_similarity(v1, v3), 0.0)

    def test_vector_search_top_k(self) -> None:
        adapter = VectorSearchAdapter()
        adapter.index_vector("c1", [0.9, 0.1, 0.0])
        adapter.index_vector("c2", [0.0, 0.8, 0.2])

        results = adapter.search_vector([1.0, 0.0, 0.0], top_k=2)
        self.assertEqual(results[0][0], "c1")


class FusionAlgorithmsTests(unittest.TestCase):
    def test_reciprocal_rank_fusion(self) -> None:
        list1 = ["d1", "d2", "d3"]
        list2 = ["d2", "d1", "d4"]
        fused = reciprocal_rank_fusion([list1, list2], k=60)

        top_ids = [doc_id for doc_id, _ in fused[:2]]
        self.assertIn("d1", top_ids)
        self.assertIn("d2", top_ids)

    def test_weighted_fusion(self) -> None:
        lex = {"d1": 10.0, "d2": 5.0}
        vec = {"d1": 0.8, "d2": 0.9}
        fused = weighted_score_fusion(lex, vec, weight_lexical=0.7, weight_vector=0.3)
        self.assertEqual(fused[0][0], "d1")


class LegalRerankerTests(unittest.TestCase):
    def test_boosts_exact_article_and_document_number(self) -> None:
        reranker = LegalReranker()
        meta = _make_meta("v1", document_number="184/2024/QĐ-TTg")
        c1 = _make_chunk("c1", "v1", "Chương I / Điều 5", "Nội dung điều 5 thẩm quyền...")
        c2 = _make_chunk("c2", "v1", "Chương I / Điều 12", "Nội dung điều 12 thời hạn...")

        candidates = [("c2", 0.5), ("c1", 0.5)]
        results = reranker.rerank(
            query="quy định tại Điều 5 Quyết định 184/2024/QĐ-TTg",
            candidates=candidates,
            chunk_map={"c1": c1, "c2": c2},
            meta_map={"v1": meta},
        )

        self.assertEqual(results[0][0], "c1")
        self.assertGreater(results[0][1], results[1][1])

    def test_penalizes_repealed_documents(self) -> None:
        reranker = LegalReranker()
        meta_active = _make_meta("v1", validity_status=ValidityStatus.IN_FORCE)
        meta_repealed = _make_meta("v2", validity_status=ValidityStatus.REPEALED)

        c1 = _make_chunk("c1", "v1", "Điều 1", "Quy định đang hiệu lực")
        c2 = _make_chunk("c2", "v2", "Điều 1", "Quy định đã bãi bỏ")

        candidates = [("c2", 0.6), ("c1", 0.6)]
        results = reranker.rerank(
            query="quy định",
            candidates=candidates,
            chunk_map={"c1": c1, "c2": c2},
            meta_map={"v1": meta_active, "v2": meta_repealed},
        )

        self.assertEqual(results[0][0], "c1")



class HybridRetrievalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.auth_service = AuthorizationService()
        self.service = RetrievalService(auth_service=self.auth_service)

        self.normal_user = AppUser.new(
            user_id="u_normal",
            username="analyst",
            email="analyst@cand.vn",
            display_name="Legal Analyst",
        )
        self.admin_user = AppUser.new(
            user_id="u_admin",
            username="admin",
            email="admin@cand.vn",
            display_name="System Admin",
            is_system=True,
        )

        self.c1 = _make_chunk("c1", "v1", "Điều 5", "Thẩm quyền điều tra các tội xâm phạm an ninh quốc gia")
        self.m1 = _make_meta(
            "v1",
            document_number="184/2024/QĐ-TTg",
            collection_ids=("coll_public",),
            validity_status=ValidityStatus.IN_FORCE,
        )
        self.service.index_chunk(self.c1, self.m1, vector=[0.9, 0.1, 0.0])

        self.c2 = _make_chunk("c2", "v2", "Điều 10", "Biện pháp nghiệp vụ đặc biệt trong điều tra")
        self.m2 = _make_meta(
            "v2",
            document_number="01/2024/TT-BCA",
            collection_ids=("coll_secret",),
            validity_status=ValidityStatus.IN_FORCE,
        )
        self.service.index_chunk(self.c2, self.m2, vector=[0.8, 0.2, 0.0])

    def test_acl_leakage_is_zero_for_unauthorized_user(self) -> None:
        def mock_check_collection_access(user: AppUser, collection_id: str, min_access_level: AccessLevel = AccessLevel.READ) -> None:
            if not user.is_system and collection_id == "coll_secret":
                from law_rag.ingestion.authorization import AccessDeniedError
                raise AccessDeniedError("Access denied to secret collection")

        self.auth_service.check_collection_access = mock_check_collection_access  # type: ignore

        results, evidence, trace = self.service.retrieve(
            query="biện pháp nghiệp vụ đặc biệt",
            user=self.normal_user,
            query_type=QueryType.HYBRID,
        )

        retrieved_chunk_ids = [r.chunk_id for r in results]
        self.assertNotIn("c2", retrieved_chunk_ids)
        self.assertTrue(all(ev.chunk_id != "c2" for ev in evidence))
        self.assertEqual(trace.user_id, "u_normal")

    def test_system_admin_retrieves_all_accessible_collections(self) -> None:
        results, evidence, trace = self.service.retrieve(
            query="biện pháp nghiệp vụ đặc biệt",
            user=self.admin_user,
            query_type=QueryType.HYBRID,
        )

        retrieved_chunk_ids = [r.chunk_id for r in results]
        self.assertIn("c2", retrieved_chunk_ids)

    def test_hybrid_search_generates_evidence_and_trace(self) -> None:
        results, evidence, trace = self.service.retrieve(
            query="thẩm quyền điều tra an ninh quốc gia",
            user=self.admin_user,
            query_vector=[0.9, 0.1, 0.0],
            query_type=QueryType.HYBRID,
            as_of_date=date(2024, 6, 1),
        )

        self.assertTrue(len(results) > 0)
        self.assertEqual(len(results), len(evidence))
        self.assertIsNotNone(trace.trace_id)
        self.assertEqual(trace.query, "thẩm quyền điều tra an ninh quốc gia")
        self.assertEqual(trace.as_of_date, date(2024, 6, 1))

        ev = evidence[0]
        self.assertEqual(ev.chunk_id, "c1")
        self.assertEqual(ev.document_number, "184/2024/QĐ-TTg")
        self.assertEqual(ev.structural_path, "Điều 5")
        self.assertTrue(ev.is_verified)

        saved_trace = self.service.get_trace(trace.trace_id)
        self.assertIsNotNone(saved_trace)
        self.assertEqual(saved_trace.result_count, len(results))

    def test_metadata_filters_applied_correctly(self) -> None:
        results, _, _ = self.service.retrieve(
            query="thẩm quyền",
            user=self.admin_user,
            filters={"document_type": "Thông tư"},
        )
        retrieved_chunk_ids = [r.chunk_id for r in results]
        self.assertNotIn("c1", retrieved_chunk_ids)


if __name__ == "__main__":
    unittest.main()

