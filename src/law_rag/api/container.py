"""Application container wiring identity, ACL, retrieval, RAG, and ingestion.

The container is the single server-side enforcement point for the API layer:
every read path applies ACL filtering before data leaves the process, and every
write path checks a permission before touching a subsystem (docs/10, docs/11).
"""

from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from law_rag.ingestion.knowledge_models import (
    AccessLevel,
    AppUser,
    CollectionAccess,
    DocumentCollection,
)
from law_rag.ingestion.models import IngestionJob, UploadReceipt
from law_rag.rag.models import Conversation, Evidence, Message, RAGResponse
from law_rag.rag.service import RAGService
from law_rag.retrieval.models import Chunk, QueryType, RetrievalResult, RetrievalTrace
from law_rag.retrieval.search import DocumentMetadata, RetrievalService

from .acl import ApiAuthorizationService, CollectionAcl
from .errors import (
    AuthenticationRequiredError,
    AuthorizationDeniedApiError,
    ResourceNotFoundApiError,
    ServiceUnavailableApiError,
)
from .security import RbacPolicy, TokenAuthenticator

if TYPE_CHECKING:  # pragma: no cover - typing only
    from law_rag.ingestion.legal_review import ReviewDecision
    from law_rag.ingestion.pipeline import IngestionPipeline, PipelineOutcome, ReleasedVersion, ReviewState

LOGGER = logging.getLogger(__name__)

_REPEALED_STATUSES = frozenset({"repealed", "expired"})

_QUERY_TYPE_MAP: dict[str, QueryType] = {
    "hybrid": QueryType.HYBRID,
    "lexical": QueryType.LEXICAL,
    "semantic": QueryType.SEMANTIC,
}


def query_type_from_name(name: str) -> QueryType:
    """Map an API query-type name to the retrieval domain enum."""
    return _QUERY_TYPE_MAP[name]


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """A released document version projected for the knowledge API."""

    metadata: DocumentMetadata
    chunks: tuple[Chunk, ...]


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    results: tuple[RetrievalResult, ...]
    evidence: tuple[Evidence, ...]
    trace: RetrievalTrace
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChatOutcome:
    conversation: Conversation
    response: RAGResponse
    trace: RetrievalTrace
    warnings: tuple[str, ...]


class ApiContainer:
    """Owns the in-process service graph exposed by the REST API."""

    def __init__(
        self,
        *,
        architecture_version: str = "1.0-retrieval-rag",
        display_phase: str = "PHASE 5 - Web Application / API",
        rbac: RbacPolicy | None = None,
        ingestion_service=None,
        pipeline: "IngestionPipeline | None" = None,
        kb_repository=None,
        legal_repository=None,
    ) -> None:
        self.architecture_version = architecture_version
        self.display_phase = display_phase
        self.authenticator = TokenAuthenticator()
        self.acl = CollectionAcl()
        self.authorization = ApiAuthorizationService(acl=self.acl, rbac=rbac)
        self.retrieval = RetrievalService(auth_service=self.authorization)
        self.rag = RAGService()
        self.ingestion_service = ingestion_service
        self.pipeline = pipeline
        self.kb_repository = kb_repository
        self.legal_repository = legal_repository
        # Set by the deployment bootstrap once an AuditSink is wired.
        self.audit = None
        self._users: dict[str, AppUser] = {}
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[Message]] = {}


    # --- identity ---------------------------------------------------------
    def register_user(self, user: AppUser) -> AppUser:
        self._users[user.user_id] = user
        return user

    def user(self, user_id: str) -> AppUser | None:
        return self._users.get(user_id)

    def register_token(self, *, user_id: str, token: str) -> None:
        if user_id not in self._users:
            raise ValueError(f"Unknown user: {user_id}")
        self.authenticator.register_token(user_id, token)

    def issue_token(self, user_id: str) -> str:
        if user_id not in self._users:
            raise ValueError(f"Unknown user: {user_id}")
        return self.authenticator.issue_token(user_id)

    def authenticate(self, token: str | None) -> AppUser:
        """Resolve a bearer token to an active user or raise 401/403."""
        user_id = self.authenticator.authenticate(token)
        user = self._users.get(user_id)
        if user is None:
            raise AuthenticationRequiredError("Bearer token is not valid.")
        if not user.is_active:
            raise AuthorizationDeniedApiError("Tài khoản đã bị vô hiệu hóa.")
        if user.is_locked:
            raise AuthorizationDeniedApiError("Tài khoản đang bị tạm khóa.")
        return user

    def authorize(self, user: AppUser, permission: str) -> None:
        """Enforce a server-side RBAC permission (deny by default)."""
        self.authorization.check_permission(user, permission)

    def authorize_any(self, user: AppUser, permissions: tuple[str, ...]) -> None:
        """Enforce that at least one of the given permissions is granted."""
        granted = self.authorization.get_user_permissions(user)
        if not any(permission in granted for permission in permissions):
            raise AuthorizationDeniedApiError("Bạn không có quyền thực hiện thao tác này.")

    def has_permission(self, user: AppUser, permission: str) -> bool:
        return permission in self.authorization.get_user_permissions(user)

    def assign_role(self, *, user_id: str, role_name: str) -> None:
        self.authorization.assign_role(user_id, role_name)

    def permissions_for(self, user: AppUser) -> tuple[str, ...]:
        return tuple(sorted(self.authorization.get_user_permissions(user)))

    # --- collections / ACL ------------------------------------------------
    def register_collection(
        self,
        *,
        collection_id: str,
        collection_name: str,
        is_public: bool,
        created_by: str,
        description: str | None = None,
    ) -> DocumentCollection:
        collection = DocumentCollection.new(
            collection_id=collection_id,
            collection_name=collection_name,
            description=description,
            is_public=is_public,
            created_by=created_by,
        )
        return self.acl.register_collection(collection)

    def grant_collection_access(
        self,
        *,
        user_id: str,
        collection_id: str,
        access_level: AccessLevel = AccessLevel.READ,
        granted_by: str,
    ) -> CollectionAccess:
        return self.acl.grant(
            user_id=user_id,
            collection_id=collection_id,
            access_level=access_level,
            granted_by=granted_by,
        )

    def readable_collection_ids(self, user: AppUser) -> tuple[str, ...]:
        return tuple(sorted(self.authorization.get_user_collections(user)))

    # --- knowledge base projection ----------------------------------------
    def index_chunk(
        self, chunk: Chunk, metadata: DocumentMetadata, vector: list[float] | None = None
    ) -> None:
        """Register a released chunk; ACL is enforced on every read path."""
        self.retrieval.index_chunk(chunk, metadata, vector)

    def metadata_for_version(self, version_id: str) -> DocumentMetadata | None:
        return self.retrieval.metadata_for_version(version_id)

    def document_records(self, user: AppUser) -> tuple[DocumentRecord, ...]:
        """Document versions the user may read, most recently issued first."""
        records = [
            DocumentRecord(
                metadata=metadata,
                chunks=self.retrieval.chunks_for_version(metadata.version_id),
            )
            for metadata in self.retrieval.all_metadata()
            if self.authorization.check_collection_ids(user, metadata.collection_ids)
        ]
        records.sort(
            key=lambda record: (record.metadata.issue_date, record.metadata.version_id),
            reverse=True,
        )
        return tuple(records)

    def document_record(self, user: AppUser, document_id: str) -> DocumentRecord:
        """Readable version of a document, else 404 without revealing existence."""
        candidates = [
            record for record in self.document_records(user) if record.metadata.document_id == document_id
        ]
        if not candidates:
            raise ResourceNotFoundApiError(f"Document {document_id} was not found.")
        return candidates[0]

    def chunk_for(self, user: AppUser, chunk_id: str) -> Chunk:
        chunk = self.retrieval.chunk(chunk_id)
        if chunk is None:
            raise ResourceNotFoundApiError(f"Chunk {chunk_id} was not found.")
        metadata = self.retrieval.metadata_for_version(chunk.version_id)
        if metadata is None or not self.authorization.check_collection_ids(user, metadata.collection_ids):
            raise ResourceNotFoundApiError(f"Chunk {chunk_id} was not found.")
        return chunk

    # --- search / chat ----------------------------------------------------
    def search(
        self,
        *,
        user: AppUser,
        query: str,
        top_k: int = 10,
        query_type: str = "hybrid",
        as_of_date: date | None = None,
        filters: dict[str, str] | None = None,
        query_vector: list[float] | None = None,
    ) -> SearchOutcome:
        """Run hybrid retrieval with server-side ACL and validity filtering."""
        results, evidence, trace = self.retrieval.retrieve(
            query=query,
            user=user,
            as_of_date=as_of_date,
            query_vector=query_vector,
            query_type=query_type_from_name(query_type),
            filters=dict(filters) if filters else None,
            top_k=top_k,
        )
        LOGGER.info(
            "api.search trace_id=%s user=%s results=%d",
            trace.trace_id,
            user.user_id,
            len(results),
        )
        return SearchOutcome(
            results=results,
            evidence=evidence,
            trace=trace,
            warnings=self._validity_warnings(evidence),
        )

    def chat(
        self,
        *,
        user: AppUser,
        question: str,
        conversation_id: str | None = None,
        as_of_date: date | None = None,
        top_k: int = 5,
        query_type: str = "hybrid",
        filters: dict[str, str] | None = None,
    ) -> ChatOutcome:
        """Answer a legal question from retrieved evidence only (grounded RAG)."""
        conversation = self.conversation_for(
            user=user, conversation_id=conversation_id, new_title=question
        )
        outcome = self.search(
            user=user,
            query=question,
            top_k=top_k,
            query_type=query_type,
            as_of_date=as_of_date,
            filters=filters,
        )
        response = self.rag.generate_answer(
            question=question,
            evidence=list(outcome.evidence),
            as_of_date=as_of_date,
            user_id=user.user_id,
            conversation_id=conversation.conversation_id,
        )
        self._append_message(
            conversation,
            Message.user_message(
                message_id=f"msg_{outcome.trace.trace_id[6:]}_u",
                conversation_id=conversation.conversation_id,
                content=question,
                as_of_date=as_of_date,
            ),
        )
        self._append_message(
            conversation,
            Message.assistant_message(
                message_id=response.message_id,
                conversation_id=conversation.conversation_id,
                content=response.answer,
                trace_id=response.trace_id,
                as_of_date=as_of_date,
                insufficient_evidence=response.insufficient_evidence,
            ),
        )
        return ChatOutcome(
            conversation=conversation,
            response=response,
            trace=outcome.trace,
            warnings=outcome.warnings + response.warnings,
        )

    # --- conversations ----------------------------------------------------
    def create_conversation(self, *, user: AppUser, title: str | None = None) -> Conversation:
        conversation_id = f"conv_{uuid.uuid4().hex[:16]}"
        conversation = Conversation.new(
            conversation_id=conversation_id, user_id=user.user_id, title=title
        )
        self._conversations[conversation_id] = conversation
        self._messages[conversation_id] = []
        return conversation

    def conversation_for(
        self,
        *,
        user: AppUser,
        conversation_id: str | None,
        new_title: str | None = None,
    ) -> Conversation:
        """Return an owned conversation or 404 (never disclose other users' ids)."""
        if conversation_id is None:
            title = new_title.strip()[:80] if new_title else None
            return self.create_conversation(user=user, title=title or None)
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.user_id != user.user_id:
            raise ResourceNotFoundApiError(f"Conversation {conversation_id} was not found.")
        return conversation

    def messages_for(self, *, user: AppUser, conversation_id: str) -> tuple[Message, ...]:
        self.conversation_for(user=user, conversation_id=conversation_id)
        return tuple(self._messages.get(conversation_id, ()))

    def _append_message(self, conversation: Conversation, message: Message) -> None:
        self._messages.setdefault(conversation.conversation_id, []).append(message)
        updated = replace(conversation, updated_at=message.created_at)
        self._conversations[conversation.conversation_id] = updated

    # --- ingestion --------------------------------------------------------
    def upload(
        self,
        *,
        user: AppUser,
        filename: str,
        stream: io.BufferedIOBase,
        idempotency_key: str,
        source: str | None = None,
        trace_id: str | None = None,
    ) -> UploadReceipt:
        """Queue an upload through the ingestion service; requires wiring."""
        if self.ingestion_service is None:
            raise ServiceUnavailableApiError("Ingestion pipeline chưa được cấu hình trong môi trường này.")
        return self.ingestion_service.upload(
            filename=filename,
            stream=stream,
            idempotency_key=idempotency_key,
            uploader_id=user.user_id,
            source=source,
            trace_id=trace_id,
        )

    def job_for(
        self, *, user: AppUser, job_id: str, allow_review_roles: bool = False
    ) -> IngestionJob:
        """Return a job to its uploader, to audit roles, or to the review roles.

        ``allow_review_roles`` lets document reviewers work on jobs uploaded by someone
        else (the review workflow crosses roles); other callers still get 404 so job
        existence is not disclosed.
        """
        if self.ingestion_service is None:
            raise ServiceUnavailableApiError("Ingestion pipeline chưa được cấu hình trong môi trường này.")
        job = self.ingestion_service.repository.get(job_id)
        if job is None:
            raise ResourceNotFoundApiError(f"Job {job_id} was not found.")
        if job.uploader_id == user.user_id:
            return job
        allowed = {"audit.view"}
        if allow_review_roles:
            allowed |= {"document.edit_metadata", "document.approve"}
        if not any(self.has_permission(user, permission) for permission in allowed):
            raise ResourceNotFoundApiError(f"Job {job_id} was not found.")
        return job

    # --- ingestion pipeline (review / approve / release) ------------------
    def process_job_in_background(self, *, job_id: str) -> None:
        """Run extraction + parsing after the upload response; failures stay on the job."""
        if self.pipeline is None:
            return
        try:
            self.pipeline.process(job_id)
        except Exception:  # noqa: BLE001 - the job already records the error code
            LOGGER.exception("Background ingestion processing failed job_id=%s", job_id)

    def process_job(self, *, user: AppUser, job_id: str) -> "PipelineOutcome":
        """Process an uploaded job on demand (uploader or audit/administration)."""
        self.authorize_any(user, ("document.upload", "document.approve", "audit.view"))
        job = self.job_for(user=user, job_id=job_id)
        return self._require_pipeline().process(job.job_id)

    def review_state_for(self, *, user: AppUser, job_id: str) -> "ReviewState":
        """Reviewer view of a parsed job; other users get 404 as with any job read."""
        self.authorize_any(
            user, ("document.upload", "document.edit_metadata", "document.approve", "audit.view")
        )
        job = self.job_for(user=user, job_id=job_id, allow_review_roles=True)
        return self._require_pipeline().review_state(job.job_id)

    def submit_review(
        self, *, user: AppUser, job_id: str, decisions: tuple[ReviewDecision, ...]
    ) -> "ReviewState":
        """Record reviewer decisions for a parsed job and return the updated state."""
        self.authorize(user, "document.edit_metadata")
        job = self.job_for(user=user, job_id=job_id, allow_review_roles=True)
        pipeline = self._require_pipeline()
        pipeline.submit_decisions(job.job_id, decisions)
        return pipeline.review_state(job.job_id)

    def approve_job(
        self,
        *,
        user: AppUser,
        job_id: str,
        collection_id: str,
        acknowledged_warnings: tuple[str, ...] = (),
    ) -> "ReleasedVersion":
        """Approve, release and index an ingested document into a collection."""
        self.authorize(user, "document.approve")
        job = self.job_for(user=user, job_id=job_id, allow_review_roles=True)
        # Releasing writes into the knowledge base: require write access, not just read.
        self.authorization.check_collection_access(
            user, collection_id, min_access_level=AccessLevel.WRITE
        )
        return self._require_pipeline().approve(
            job.job_id,
            reviewer_id=user.user_id,
            acknowledged_warnings=acknowledged_warnings,
            released_by=user.user_id,
            collection_id=collection_id,
        )

    def collections_for(self, user: AppUser) -> tuple[tuple[DocumentCollection, AccessLevel], ...]:
        """Collections the caller can read, with the effective access level."""
        readable = self.acl.readable_collection_ids(user=user)
        result = []
        for collection_id in sorted(readable):
            collection = self.acl.collection(collection_id)
            level = self.acl.effective_level(user_id=user.user_id, collection_id=collection_id)
            if collection is not None and level is not None:
                result.append((collection, level))
        return tuple(result)

    def _require_pipeline(self) -> "IngestionPipeline":
        if self.pipeline is None:
            raise ServiceUnavailableApiError(
                "Ingestion pipeline chưa được cấu hình trong môi trường này."
            )
        return self.pipeline

    # --- traces -----------------------------------------------------------
    def trace_for(
        self, *, user: AppUser, trace_id: str
    ) -> tuple[RetrievalTrace, tuple[RetrievalResult, ...]]:
        """Retrieval trace readable by its owner or by audit roles."""
        trace = self.retrieval.get_trace(trace_id)
        if trace is None:
            raise ResourceNotFoundApiError(f"Trace {trace_id} was not found.")
        if trace.user_id != user.user_id and not self.has_permission(user, "audit.view"):
            raise ResourceNotFoundApiError(f"Trace {trace_id} was not found.")
        return trace, self.retrieval.get_trace_results(trace_id)

    # --- readiness --------------------------------------------------------
    def readiness_checks(self) -> tuple[tuple[str, str, str | None], ...]:
        """(name, status, detail) tuples used by the readiness endpoint."""
        return (
            ("retrieval_index", "ok", None),
            (
                "ingestion_pipeline",
                "ok" if self.ingestion_service is not None else "degraded",
                None if self.ingestion_service is not None else "not wired in this deployment",
            ),
            ("acl_store", "ok" if self.acl.collection_ids() else "degraded",
             None if self.acl.collection_ids() else "no collections registered"),
        )

    # --- helpers ----------------------------------------------------------
    @staticmethod
    def _validity_warnings(evidence: tuple[Evidence, ...]) -> tuple[str, ...]:
        """Warn when retrieved evidence is repealed, unverified, or unclear."""
        warnings: list[str] = []
        repealed = sorted({ev.document_title for ev in evidence if ev.validity_status in _REPEALED_STATUSES})
        if repealed:
            warnings.append(
                "Có tài liệu đã hết hiệu lực trong kết quả: " + "; ".join(repealed) + "."
            )
        unverified = sum(1 for ev in evidence if not ev.is_verified)
        if unverified:
            warnings.append(f"Có {unverified} kết quả chưa được xác minh đầy đủ.")
        unknown = sum(1 for ev in evidence if ev.validity_status == "unknown")
        if unknown:
            warnings.append(f"Có {unknown} kết quả chưa xác định trạng thái hiệu lực.")
        return tuple(warnings)

