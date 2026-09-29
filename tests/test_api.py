"""Tests for PHASE 5 REST API: authn, RBAC, ACL filtering, chat, and ingestion.

Fixtures are synthetic placeholders; no real legal content is embedded here.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from law_rag.api import ApiContainer, create_app
from law_rag.api.errors import FieldError, classify_error, error_body
from law_rag.ingestion.errors import UnsupportedFileError
from law_rag.ingestion.knowledge_models import AccessLevel, AppUser, ValidityStatus
from law_rag.ingestion.memory import InMemoryAuditSink, InMemoryJobRepository
from law_rag.ingestion.service import IngestionService
from law_rag.ingestion.storage import FileBlobStore
from law_rag.retrieval.models import Chunk
from law_rag.retrieval.search import DocumentMetadata

API = "/api/v1"

TOKENS = {
    "u_system": "token-system-000000000001",
    "u_admin": "token-admin-0000000000002",
    "u_admin2": "token-admin2-000000000002",
    "u_reviewer": "token-reviewer-00000000003",
    "u_user": "token-user-000000000000004",
    "u_auditor": "token-auditor-000000000005",
    "u_stranger": "token-stranger-00000000006",
}


def _auth(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKENS[user_id]}"}


def pdf_bytes(body: bytes = b"synthetic fixture") -> bytes:
    return b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n" + body + b"\nstartxref\n0\n%%EOF"


def _make_chunk(
    chunk_id: str,
    version_id: str,
    structural_path: str,
    content: str,
    *,
    page_start: int = 1,
    index: int = 0,
) -> Chunk:
    return Chunk.new(
        chunk_id=chunk_id,
        chunk_set_id="cs_test",
        version_id=version_id,
        node_id=f"node_{chunk_id}",
        chunk_index=index,
        content=content,
        content_hash="a" * 64,
        structural_path=structural_path,
        heading=None,
        page_start=page_start,
        page_end=page_start,
    )


def _make_metadata(
    version_id: str,
    *,
    document_number: str,
    title: str,
    collection_ids: tuple[str, ...],
    validity_status: ValidityStatus = ValidityStatus.IN_FORCE,
) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=f"doc_{version_id}",
        version_id=version_id,
        document_number=document_number,
        title=title,
        issuing_body="Cơ quan thử nghiệm nội bộ",
        document_type="Quyết định thử nghiệm",
        issue_date=date(2025, 1, 1),
        effective_date=date(2025, 1, 1),
        expiry_date=None,
        collection_ids=collection_ids,
        validity_status=validity_status,
        is_verified=True,
    )


def build_container(*, with_ingestion: bool = True, max_bytes: int | None = None) -> ApiContainer:
    """Container wired with synthetic users, ACL, and an indexed corpus."""
    container = ApiContainer()
    for user_id, username in (
        ("u_system", "system"),
        ("u_admin", "admin.user"),
        ("u_admin2", "admin2.user"),
        ("u_reviewer", "reviewer.user"),
        ("u_user", "reader.user"),
        ("u_auditor", "auditor.user"),
        ("u_stranger", "stranger.user"),
    ):
        user = AppUser.new(
            user_id=user_id,
            username=username,
            email=f"{username}@local.test",
            display_name=username.title(),
            is_system=user_id == "u_system",
        )
        container.register_user(user)
        container.register_token(user_id=user_id, token=TOKENS[user_id])

    for user_id, role in (
        ("u_admin", "knowledge_admin"),
        ("u_admin2", "knowledge_admin"),
        ("u_reviewer", "reviewer"),
        ("u_user", "user"),
        ("u_auditor", "auditor"),
    ):
        container.assign_role(user_id=user_id, role_name=role)

    container.register_collection(
        collection_id="coll_public",
        collection_name="Văn bản công khai",
        is_public=True,
        created_by="u_system",
    )
    container.register_collection(
        collection_id="coll_restricted",
        collection_name="Văn bản hạn chế",
        is_public=False,
        created_by="u_system",
    )
    container.grant_collection_access(
        user_id="u_reviewer", collection_id="coll_restricted", granted_by="u_system"
    )

    container.index_chunk(
        _make_chunk(
            "chunk_public",
            "ver_public",
            "Điều 5",
            "Quy định về thẩm quyền xử lý thông tin điện tử trong hồ sơ.",
        ),
        _make_metadata(
            "ver_public",
            document_number="TEST-001/2025",
            title="Văn bản thử nghiệm công khai",
            collection_ids=("coll_public",),
        ),
    )
    container.index_chunk(
        _make_chunk(
            "chunk_restricted",
            "ver_restricted",
            "Điều 9",
            "Quy định về thẩm quyền xử lý thông tin điện tử hạn chế.",
        ),
        _make_metadata(
            "ver_restricted",
            document_number="TEST-002/2025",
            title="Văn bản thử nghiệm hạn chế",
            collection_ids=("coll_restricted",),
        ),
    )
    container.index_chunk(
        _make_chunk(
            "chunk_repealed",
            "ver_repealed",
            "Điều 2",
            "Quy định về thẩm quyền đã hết hiệu lực trong hồ sơ.",
        ),
        _make_metadata(
            "ver_repealed",
            document_number="TEST-003/2025",
            title="Văn bản thử nghiệm hết hiệu lực",
            collection_ids=("coll_public",),
            validity_status=ValidityStatus.REPEALED,
        ),
    )

    if with_ingestion:
        temp_dir = tempfile.TemporaryDirectory(prefix="law-rag-api-test-")
        # keep a reference so the directory is not removed mid-test
        container.blob_store_temp = temp_dir
        container.ingestion_service = IngestionService(
            repository=InMemoryJobRepository(),
            blob_store=FileBlobStore(Path(temp_dir.name)),
            audit=InMemoryAuditSink(),
            **({} if max_bytes is None else {"max_bytes": max_bytes}),
        )
    return container


class ApiTestCase(unittest.TestCase):
    """Shared container/client fixture."""

    def _make_client(self, container: ApiContainer) -> TestClient:
        """Create a client and release container-owned temp resources on teardown."""
        client = TestClient(create_app(container), raise_server_exceptions=False)
        self.addCleanup(client.close)
        temp_dir = getattr(container, "blob_store_temp", None)
        if temp_dir is not None:
            self.addCleanup(temp_dir.cleanup)
        return client

    def setUp(self) -> None:
        self.container = build_container()
        self.client = self._make_client(self.container)


class OperationsApiTests(ApiTestCase):
    def test_health_is_public_and_reports_architecture(self) -> None:
        response = self.client.get(f"{API}/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("architecture_version", body)

    def test_ready_reports_checks_and_index_size(self) -> None:
        response = self.client.get(f"{API}/ready")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["status"], {"ready", "degraded"})
        self.assertEqual(body["indexed_chunk_count"], 3)
        names = {check["name"] for check in body["checks"]}
        self.assertIn("retrieval_index", names)
        self.assertIn("ingestion_pipeline", names)

    def test_ready_is_degraded_when_ingestion_is_not_wired(self) -> None:
        client = self._make_client(build_container(with_ingestion=False))
        body = client.get(f"{API}/ready").json()
        self.assertEqual(body["status"], "degraded")

    def test_openapi_contract_is_served_under_version_prefix(self) -> None:
        response = self.client.get(f"{API}/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for path in ("/api/v1/chat", "/api/v1/search", "/api/v1/documents", "/api/v1/documents/upload"):
            self.assertIn(path, paths)
        self.assertEqual(self.client.get(f"{API}/docs").status_code, 200)

    def test_request_id_header_is_echoed(self) -> None:
        response = self.client.get(f"{API}/health", headers={"X-Request-ID": "req-test-1"})
        self.assertEqual(response.headers.get("X-Request-ID"), "req-test-1")

    def test_spa_root_and_static_serving(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("LAW-RAG", response.text)



class AuthenticationApiTests(ApiTestCase):
    def test_missing_token_returns_401_envelope(self) -> None:
        response = self.client.post(f"{API}/search", json={"query": "thẩm quyền"})
        self.assertEqual(response.status_code, 401)
        error = response.json()["error"]
        self.assertEqual(error["code"], "AUTHENTICATION_REQUIRED")
        self.assertIn("request_id", error)
        self.assertEqual(error["field_errors"], [])

    def test_invalid_token_returns_401_without_detail(self) -> None:
        response = self.client.post(
            f"{API}/search", json={"query": "thẩm quyền"}, headers={"Authorization": "Bearer wrong"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTHENTICATION_REQUIRED")

    def test_malformed_authorization_header_returns_401(self) -> None:
        response = self.client.post(
            f"{API}/search", json={"query": "thẩm quyền"}, headers={"Authorization": TOKENS["u_user"]}
        )
        self.assertEqual(response.status_code, 401)

    def test_me_returns_effective_permissions(self) -> None:
        response = self.client.get(f"{API}/me", headers=_auth("u_auditor"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user_id"], "u_auditor")
        self.assertIn("audit.view", body["permissions"])
        self.assertNotIn("document.upload", body["permissions"])

    def test_search_without_permission_returns_403(self) -> None:
        response = self.client.post(
            f"{API}/search", json={"query": "thẩm quyền"}, headers=_auth("u_stranger")
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "AUTHORIZATION_DENIED")

    def test_malformed_body_is_422_even_without_credentials(self) -> None:
        """Documented behaviour: FastAPI decodes the body before dependency solving.

        The response exposes nothing about the corpus, users, or permissions.
        """
        response = self.client.post(
            f"{API}/search",
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_FAILED")


class SearchApiTests(ApiTestCase):
    def test_search_returns_ranked_results_and_trace(self) -> None:
        response = self.client.post(
            f"{API}/search",
            json={"query": "thẩm quyền xử lý thông tin điện tử"},
            headers=_auth("u_user"),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result_count"], len(body["results"]))
        self.assertTrue(body["results"])
        self.assertEqual(body["results"][0]["rank"], 1)
        self.assertTrue(body["trace_id"].startswith("trace_"))
        self.assertIn("snippet", body["results"][0])
        self.assertIn("page_start", body["results"][0])

    def test_acl_leakage_is_zero_for_restricted_collection(self) -> None:
        response = self.client.post(
            f"{API}/search",
            json={"query": "thẩm quyền xử lý thông tin điện tử"},
            headers=_auth("u_user"),
        )
        chunk_ids = {item["chunk_id"] for item in response.json()["results"]}
        self.assertNotIn("chunk_restricted", chunk_ids)

    def test_granted_role_sees_restricted_document(self) -> None:
        response = self.client.post(
            f"{API}/search",
            json={"query": "thẩm quyền xử lý thông tin điện tử hạn chế"},
            headers=_auth("u_reviewer"),
        )
        self.assertEqual(response.status_code, 200)
        chunk_ids = {item["chunk_id"] for item in response.json()["results"]}
        self.assertIn("chunk_restricted", chunk_ids)

    def test_repealed_evidence_produces_warning(self) -> None:
        response = self.client.post(
            f"{API}/search",
            json={"query": "thẩm quyền đã hết hiệu lực"},
            headers=_auth("u_user"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("hết hiệu lực" in warning for warning in response.json()["warnings"]))

    def test_invalid_payload_returns_422_with_field_errors(self) -> None:
        response = self.client.post(f"{API}/search", json={"query": ""}, headers=_auth("u_user"))
        self.assertEqual(response.status_code, 422)
        error = response.json()["error"]
        self.assertEqual(error["code"], "VALIDATION_FAILED")
        self.assertTrue(error["field_errors"])

    def test_unknown_field_is_rejected(self) -> None:
        response = self.client.post(
            f"{API}/search", json={"query": "abc", "unexpected": 1}, headers=_auth("u_user")
        )
        self.assertEqual(response.status_code, 422)

    def test_trace_is_readable_by_owner_and_auditor(self) -> None:
        search = self.client.post(
            f"{API}/search", json={"query": "thẩm quyền điện tử"}, headers=_auth("u_user")
        ).json()
        trace_id = search["trace_id"]
        owner = self.client.get(f"{API}/traces/{trace_id}", headers=_auth("u_user"))
        self.assertEqual(owner.status_code, 200)
        self.assertEqual(owner.json()["user_id"], "u_user")
        self.assertEqual(owner.json()["result_count"], search["result_count"])
        auditor = self.client.get(f"{API}/traces/{trace_id}", headers=_auth("u_auditor"))
        self.assertEqual(auditor.status_code, 200)
        other = self.client.get(f"{API}/traces/{trace_id}", headers=_auth("u_reviewer"))
        self.assertEqual(other.status_code, 404)
        self.assertEqual(other.json()["error"]["code"], "RESOURCE_NOT_FOUND")


class DocumentsApiTests(ApiTestCase):
    def test_document_list_is_acl_filtered(self) -> None:
        response = self.client.get(f"{API}/documents", headers=_auth("u_user"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        numbers = {doc["document_number"] for doc in body["documents"]}
        self.assertIn("TEST-001/2025", numbers)
        self.assertNotIn("TEST-002/2025", numbers)
        self.assertEqual(body["count"], len(body["documents"]))

    def test_document_detail_returns_chunks(self) -> None:
        listing = self.client.get(f"{API}/documents", headers=_auth("u_user")).json()
        document_id = listing["documents"][0]["document_id"]
        response = self.client.get(f"{API}/documents/{document_id}", headers=_auth("u_user"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["document"]["document_id"], document_id)
        self.assertTrue(body["chunks"])
        self.assertIn("structural_path", body["chunks"][0])

    def test_restricted_document_is_reported_as_404(self) -> None:
        response = self.client.get(f"{API}/documents/doc_ver_restricted", headers=_auth("u_user"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "RESOURCE_NOT_FOUND")

    def test_reviewer_with_grant_can_read_restricted_document(self) -> None:
        response = self.client.get(f"{API}/documents/doc_ver_restricted", headers=_auth("u_reviewer"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["document"]["collection_ids"], ["coll_restricted"])

    def test_document_list_supports_pagination(self) -> None:
        response = self.client.get(f"{API}/documents?limit=1&offset=0", headers=_auth("u_user"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["limit"], 1)
        self.assertEqual(body["offset"], 0)
        self.assertLessEqual(len(body["documents"]), 1)
        self.assertGreaterEqual(body["count"], len(body["documents"]))



class ChatApiTests(ApiTestCase):
    def test_chat_returns_grounded_answer_with_server_citations(self) -> None:
        response = self.client.post(
            f"{API}/chat",
            json={
                "question": "Quy định về thẩm quyền xử lý thông tin điện tử là gì?",
                "as_of_date": "2025-06-01",
            },
            headers=_auth("u_user"),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["insufficient_evidence"])
        self.assertTrue(body["answer"])
        self.assertTrue(body["citations"], "grounded answers must carry citations")
        citation = body["citations"][0]
        self.assertTrue(citation["citation_id"].startswith("cite_"))
        self.assertTrue(citation["excerpt"])
        self.assertEqual(citation["status"], "valid")
        self.assertTrue(body["evidence"])
        self.assertEqual(body["as_of_date"], "2025-06-01")
        self.assertTrue(body["trace_id"].startswith("trace_"))

    def test_chat_without_evidence_reports_insufficient_evidence(self) -> None:
        response = self.client.post(
            f"{API}/chat",
            json={"question": "kxyzqwerty zzzqqqxyzzy"},
            headers=_auth("u_user"),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["insufficient_evidence"])
        self.assertEqual(body["citations"], [])
        self.assertTrue(body["answer"])

    def test_chat_never_exposes_restricted_evidence(self) -> None:
        response = self.client.post(
            f"{API}/chat",
            json={"question": "thẩm quyền xử lý thông tin điện tử hạn chế"},
            headers=_auth("u_user"),
        )
        self.assertEqual(response.status_code, 200)
        chunk_ids = {item["chunk_id"] for item in response.json()["evidence"]}
        self.assertNotIn("chunk_restricted", chunk_ids)

    def test_conversation_is_created_and_reusable(self) -> None:
        first = self.client.post(
            f"{API}/chat",
            json={"question": "thẩm quyền xử lý thông tin điện tử trong hồ sơ"},
            headers=_auth("u_user"),
        ).json()
        conversation_id = first["conversation_id"]
        second = self.client.post(
            f"{API}/chat",
            json={
                "question": "thẩm quyền đã hết hiệu lực",
                "conversation_id": conversation_id,
            },
            headers=_auth("u_user"),
        ).json()
        self.assertEqual(second["conversation_id"], conversation_id)

        detail = self.client.get(f"{API}/conversations/{conversation_id}", headers=_auth("u_user"))
        self.assertEqual(detail.status_code, 200)
        messages = detail.json()["messages"]
        self.assertEqual(len(messages), 4)
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"] * 2)

    def test_conversation_of_another_user_is_reported_as_404(self) -> None:
        created = self.client.post(
            f"{API}/conversations", json={"title": "Phiên riêng"}, headers=_auth("u_reviewer")
        )
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["conversation_id"]
        forbidden = self.client.get(f"{API}/conversations/{conversation_id}", headers=_auth("u_user"))
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(forbidden.json()["error"]["code"], "RESOURCE_NOT_FOUND")

    def test_conversation_list_returns_owned_conversations_with_pagination(self) -> None:
        c1 = self.client.post(
            f"{API}/conversations", json={"title": "Hội thoại 1"}, headers=_auth("u_user")
        ).json()["conversation_id"]
        c2 = self.client.post(
            f"{API}/conversations", json={"title": "Hội thoại 2"}, headers=_auth("u_user")
        ).json()["conversation_id"]
        c_rev = self.client.post(
            f"{API}/conversations", json={"title": "Hội thoại Reviewer"}, headers=_auth("u_reviewer")
        ).json()["conversation_id"]

        response = self.client.get(f"{API}/conversations", headers=_auth("u_user"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        ids = [item["conversation_id"] for item in body["conversations"]]
        self.assertIn(c1, ids)
        self.assertIn(c2, ids)
        self.assertNotIn(c_rev, ids)
        self.assertEqual(body["count"], len(body["conversations"]))

        page = self.client.get(f"{API}/conversations?limit=1&offset=0", headers=_auth("u_user")).json()
        self.assertEqual(page["limit"], 1)
        self.assertEqual(len(page["conversations"]), 1)
        self.assertEqual(page["count"], body["count"])

    def test_conversation_list_without_permission_returns_403(self) -> None:
        response = self.client.get(f"{API}/conversations", headers=_auth("u_stranger"))
        self.assertEqual(response.status_code, 403)

    def test_chat_without_permission_returns_403(self) -> None:
        response = self.client.post(
            f"{API}/chat", json={"question": "thẩm quyền"}, headers=_auth("u_stranger")
        )
        self.assertEqual(response.status_code, 403)


class IngestionApiTests(ApiTestCase):
    def _upload(
        self,
        *,
        user: str = "u_admin",
        name: str = "van-ban.pdf",
        key: str = "key-1",
        body: bytes | None = None,
    ):
        headers = {**_auth(user), "Idempotency-Key": key}
        return self.client.post(
            f"{API}/documents/upload",
            params={"filename": name, "source": "test-suite"},
            content=pdf_bytes() if body is None else body,
            headers=headers,
        )

    def test_upload_queues_job_without_exposing_document_ids(self) -> None:
        response = self._upload()
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertTrue(body["job_id"])
        self.assertEqual(body["status"], "queued")
        self.assertFalse(body["duplicate_match"])
        self.assertIsNone(body["document_id"])
        self.assertIsNone(body["version_id"])
        self.assertEqual(body["media_type"], "application/pdf")
        self.assertTrue(body["sha256"])

    def test_identical_content_is_reported_as_duplicate(self) -> None:
        first = self._upload(key="key-a").json()
        second = self._upload(key="key-b").json()
        self.assertEqual(second["job_id"], first["job_id"])
        self.assertTrue(second["duplicate_match"])
        self.assertTrue(second["warnings"])

    def test_same_key_different_content_conflicts(self) -> None:
        self._upload(key="key-c")
        response = self._upload(key="key-c", body=pdf_bytes(b"other"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "RESOURCE_CONFLICT")

    def test_missing_idempotency_key_returns_422(self) -> None:
        response = self.client.post(
            f"{API}/documents/upload",
            params={"filename": "van-ban.pdf"},
            content=pdf_bytes(),
            headers=_auth("u_admin"),
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["field_errors"][0]["field"], "Idempotency-Key")

    def test_unsupported_file_type_returns_415(self) -> None:
        response = self._upload(name="payload.exe", key="key-d", body=b"MZ\x90\x00binary")
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_UNSUPPORTED")

    def test_empty_body_returns_422(self) -> None:
        response = self._upload(key="key-e", body=b"")
        self.assertEqual(response.status_code, 422)

    def test_upload_requires_permission(self) -> None:
        response = self._upload(user="u_user", key="key-f")
        self.assertEqual(response.status_code, 403)

    def test_document_list_is_unchanged_by_unapproved_upload(self) -> None:
        self._upload(user="u_admin", key="key-i")
        listing = self.client.get(f"{API}/documents", headers=_auth("u_user")).json()
        self.assertEqual(listing["count"], 2)

    def test_job_status_visible_to_uploader_and_hidden_from_others(self) -> None:
        job_id = self._upload(user="u_admin", key="key-g").json()["job_id"]
        owner = self.client.get(f"{API}/jobs/{job_id}", headers=_auth("u_admin"))
        self.assertEqual(owner.status_code, 200)
        self.assertEqual(owner.json()["status"], "queued")
        self.assertEqual(owner.json()["uploader_id"], "u_admin")

        other_admin = self.client.get(f"{API}/jobs/{job_id}", headers=_auth("u_admin2"))
        self.assertEqual(other_admin.status_code, 404)
        denied = self.client.get(f"{API}/jobs/{job_id}", headers=_auth("u_user"))
        self.assertEqual(denied.status_code, 403)

    def test_auditor_role_can_read_job_status(self) -> None:
        job_id = self._upload(user="u_admin", key="key-h").json()["job_id"]
        response = self.client.get(f"{API}/jobs/{job_id}", headers=_auth("u_auditor"))
        self.assertEqual(response.status_code, 200)

    def test_unknown_job_returns_404(self) -> None:
        response = self.client.get(f"{API}/jobs/does-not-exist", headers=_auth("u_admin"))
        self.assertEqual(response.status_code, 404)

    def test_oversized_upload_returns_413(self) -> None:
        client = self._make_client(build_container(max_bytes=256))
        response = client.post(
            f"{API}/documents/upload",
            params={"filename": "lon.pdf"},
            content=pdf_bytes(b"x" * 512),
            headers={**_auth("u_admin"), "Idempotency-Key": "key-size"},
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_TOO_LARGE")

    def test_upload_returns_503_when_ingestion_is_not_wired(self) -> None:
        client = self._make_client(build_container(with_ingestion=False))
        response = client.post(
            f"{API}/documents/upload",
            params={"filename": "van-ban.pdf"},
            content=pdf_bytes(),
            headers={**_auth("u_admin"), "Idempotency-Key": "key-unwired"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "SERVICE_UNAVAILABLE")


class ErrorMappingTests(unittest.TestCase):
    def test_unsupported_file_error_maps_to_415(self) -> None:
        mapped = classify_error(UnsupportedFileError("File format is not supported"))
        self.assertIsNotNone(mapped)
        self.assertEqual(mapped.status_code, 415)
        self.assertEqual(mapped.code, "UPLOAD_UNSUPPORTED")

    def test_unknown_error_is_not_mapped(self) -> None:
        self.assertIsNone(classify_error(RuntimeError("boom")))

    def test_error_body_contains_stable_shape(self) -> None:
        error = classify_error(UnsupportedFileError("File format is not supported"))
        body = error_body(error, "req-123")
        self.assertEqual(sorted(body["error"]), ["code", "field_errors", "message", "request_id"])
        self.assertEqual(body["error"]["request_id"], "req-123")

    def test_field_error_defaults_to_safe_code(self) -> None:
        self.assertEqual(FieldError(field="query", message="Giá trị không hợp lệ.").code, "INVALID_VALUE")


class UnexpectedFailureTests(ApiTestCase):
    def test_unexpected_error_returns_safe_500_envelope(self) -> None:
        def explode(**_: object) -> None:
            raise RuntimeError("internal detail with secret token=hunter2")

        self.container.search = explode  # type: ignore[method-assign]
        with self.assertLogs("law_rag.api.app", level="ERROR") as captured:
            response = self.client.post(
                f"{API}/search", json={"query": "thẩm quyền"}, headers=_auth("u_user")
            )
        self.assertEqual(response.status_code, 500)
        message = response.json()["error"]["message"]
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("hunter2", message)
        self.assertNotIn("Traceback", message)
        logged = "\n".join(captured.output)
        self.assertIn("RuntimeError", logged)
        self.assertNotIn("hunter2", logged)


if __name__ == "__main__":
    unittest.main()






