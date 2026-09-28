"""Local ingestion pipeline: extraction → legal parsing → review → release → indexing.

The pipeline is the piece that connects the PHASE 1 building blocks (extraction,
legal parsing, review gate, release) with the PHASE 3 index, so an uploaded file
becomes a searchable document version. It runs inside the API process for the local
deployment profile (ADR-002 keeps the worker topology open; PostgreSQL remains the
knowledge base source of truth in production, ADR-003).

Every state change goes through ``IngestionService.transition`` so the job history
stays auditable, and every failure is recorded with a stable error code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Protocol, Sequence

from law_rag.retrieval.chunking import chunk_legal_document
from law_rag.retrieval.models import Chunk
from law_rag.retrieval.search import DocumentMetadata
from law_rag.retrieval.validity import derive_validity_status

from .extraction import ExtractionResult, extract_document
from .errors import IngestionError
from .kb_release import ReleaseService
from .knowledge_models import ValidityStatus
from .legal_models import LegalNode, LegalParseResult, MetadataAssertion, MetadataField
from .legal_parsing import parse_legal_document
from .legal_review import (
    LegalReviewService,
    ReviewDecision,
    ReviewItemKind,
    ReviewTask,
    pending_tasks,
)
from .models import JobStatus
from .ocr import OCRProcessor
from .repository import AuditSink, JobRepository, LegalParseRepository
from .service import IngestionService
from .storage import FileBlobStore

LOGGER = logging.getLogger(__name__)

EXTRACTION_FAILED = "EXTRACTION_FAILED"
PARSE_FAILED = "PARSE_FAILED"
RELEASE_FAILED = "RELEASE_FAILED"
INDEX_FAILED = "INDEX_FAILED"

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})


class IndexWriter(Protocol):
    """Registers a released version's chunks in the retrieval index."""

    def __call__(
        self, *, version_id: str, metadata: DocumentMetadata, chunks: Sequence[Chunk]
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    """Result of the extraction + parsing stage."""

    job_id: str
    status: JobStatus
    page_count: int | None
    review_required: bool
    tasks: tuple[ReviewTask, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviewState:
    """Everything a reviewer needs to decide on a parsed document."""

    job: PipelineOutcome
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    metadata: tuple[MetadataAssertion, ...]
    preview: tuple[LegalNode, ...]
    node_count: int
    relation_count: int
    approved_version_id: str | None


@dataclass(frozen=True, slots=True)
class ReleasedVersion:
    """Result of approving and indexing (or re-approving) a document."""

    job_id: str
    document_id: str
    version_id: str
    status: JobStatus
    chunk_count: int
    validity_status: ValidityStatus
    warnings: tuple[str, ...]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(timezone.utc).date()


class IngestionPipeline:
    """Runs the local ingestion chain for one job at a time."""

    def __init__(
        self,
        *,
        ingestion_service: IngestionService,
        blob_store: FileBlobStore,
        job_repository: JobRepository,
        legal_repository: LegalParseRepository,
        kb_repository,
        audit: AuditSink,
        index_writer: IndexWriter,
        ocr: OCRProcessor | None = None,
        clock: Callable[[], datetime] = _now,
        today: Callable[[], date] = _today,
        extractor: Callable[..., ExtractionResult] = extract_document,
        parser: Callable[..., LegalParseResult] = parse_legal_document,
        chunker: Callable[..., tuple] = chunk_legal_document,
        preview_limit: int = 20,
    ) -> None:
        self.ingestion_service = ingestion_service
        self.blob_store = blob_store
        self.job_repository = job_repository
        self.legal_repository = legal_repository
        self.audit = audit
        self.index_writer = index_writer
        self.ocr = ocr
        self.clock = clock
        self.today = today
        self.extractor = extractor
        self.parser = parser
        self.chunker = chunker
        self.preview_limit = preview_limit
        self.review_service = LegalReviewService(
            repository=legal_repository, audit=audit, clock=clock
        )
        self.release_service = ReleaseService(
            kb_repository=kb_repository,
            job_repository=job_repository,
            legal_repository=legal_repository,
            audit=audit,
            clock=clock,
        )

    # --- stage 1: extraction + parsing ------------------------------------
    def process(self, job_id: str) -> PipelineOutcome:
        """Extract and parse the uploaded blob, then park the job for review."""
        job = self.job_repository.get(job_id)
        if job is None:
            raise IngestionError("Ingestion job was not found")
        if job.status in {JobStatus.APPROVED, JobStatus.INDEXING, JobStatus.INDEXED}:
            raise IngestionError("Ingestion job has already been released")
        if job.status is JobStatus.FAILED:
            raise IngestionError("Ingestion job has failed; retry it before processing")

        if job.status is not JobStatus.QUEUED:
            self.ingestion_service.transition(job_id, JobStatus.QUEUED)
        self.ingestion_service.transition(job_id, JobStatus.EXTRACTING)

        extension = _extension_of(job.original_filename)
        if extension in IMAGE_EXTENSIONS:
            # Images always go through the OCR stage so the state history is honest.
            self.ingestion_service.transition(job_id, JobStatus.OCR)

        try:
            extraction = self.extractor(
                self.blob_store.path_for(job.storage_key),
                original_filename=job.original_filename,
                ocr=self.ocr,
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a stable error code
            LOGGER.exception("Extraction failed job_id=%s", job_id)
            self._fail(job_id, EXTRACTION_FAILED)
            raise IngestionError("Document extraction failed") from exc

        self.ingestion_service.transition(job_id, JobStatus.PARSING)
        try:
            result = self.parser(extraction, job_id=job_id, source=job.source)
        except Exception as exc:  # noqa: BLE001 - mapped to a stable error code
            LOGGER.exception("Legal parsing failed job_id=%s", job_id)
            self._fail(job_id, PARSE_FAILED)
            raise IngestionError("Legal parsing failed") from exc

        self.legal_repository.save_result(result)
        self.ingestion_service.transition(job_id, JobStatus.REVIEW_REQUIRED)

        tasks = _decidable_tasks(result)
        LOGGER.info(
            "Pipeline parked job_id=%s status=%s tasks=%d warnings=%d",
            job_id,
            JobStatus.REVIEW_REQUIRED.value,
            len(tasks),
            len(result.warnings),
        )
        return PipelineOutcome(
            job_id=job_id,
            status=JobStatus.REVIEW_REQUIRED,
            page_count=result.page_count,
            review_required=result.review_required,
            tasks=tasks,
            warnings=result.warnings,
        )

    # --- stage 2: human review --------------------------------------------
    def review_state(self, job_id: str) -> ReviewState:
        """Assemble the reviewer view for a parsed job (read-only)."""
        job = self.job_repository.get(job_id)
        if job is None:
            raise IngestionError("Ingestion job was not found")
        result = self.legal_repository.get_latest(job_id)
        if result is None:
            raise IngestionError("Ingestion job has no parse result yet")
        approval = getattr(self.legal_repository, "get_approval", lambda _job_id: None)(job_id)
        approved_version_id = None
        if approval is not None:
            version = self.release_service.kb_repository.get_version_by_job(job_id)
            approved_version_id = version.version_id if version else None
        return ReviewState(
            job=PipelineOutcome(
                job_id=job_id,
                status=job.status,
                page_count=result.page_count,
                review_required=result.review_required,
                tasks=_decidable_tasks(result),
                warnings=result.warnings,
            ),
            original_filename=job.original_filename,
            media_type=job.media_type,
            size_bytes=job.size_bytes,
            sha256=job.sha256,
            metadata=result.metadata,
            preview=tuple(result.nodes[: self.preview_limit]),
            node_count=len(result.nodes),
            relation_count=len(result.relations),
            approved_version_id=approved_version_id,
        )

    def submit_decisions(
        self, job_id: str, decisions: Sequence[ReviewDecision]
    ) -> LegalParseResult:
        """Record reviewer decisions and return the updated parse result."""
        result = self.legal_repository.get_latest(job_id)
        if result is None:
            raise IngestionError("Ingestion job has no parse result yet")
        if not decisions:
            raise IngestionError("At least one review decision is required")
        return self.review_service.review(result, decisions)

    # --- stage 3: approval, release, indexing -----------------------------
    def approve(
        self,
        job_id: str,
        *,
        reviewer_id: str,
        acknowledged_warnings: Sequence[str],
        released_by: str,
        collection_id: str,
    ) -> ReleasedVersion:
        """Approve the reviewed parse, release a version and index its chunks."""
        result = self.legal_repository.get_latest(job_id)
        if result is None:
            raise IngestionError("Ingestion job has no parse result yet")
        if not collection_id.strip():
            raise IngestionError("A target collection is required to release a document")

        approval = self.review_service.approve(
            result,
            reviewer_id=reviewer_id,
            acknowledged_warnings=acknowledged_warnings,
        )
        version = self.release_service.release_document(approval, released_by=released_by)

        _, chunks = self.chunker(approval.parse_result, version.version_id, released_by)
        validity_status = derive_validity_status(
            effective_date=version.effective_date,
            expiry_date=version.expiry_date,
            today=self.today(),
        )
        metadata = DocumentMetadata(
            document_id=version.document_id,
            version_id=version.version_id,
            document_number=approval.parse_result.verified_metadata_value(MetadataField.DOCUMENT_NUMBER) or "",
            title=version.title,
            issuing_body=approval.parse_result.verified_metadata_value(MetadataField.ISSUING_BODY) or "",
            document_type=approval.parse_result.verified_metadata_value(MetadataField.DOCUMENT_TYPE) or "",
            issue_date=version.issue_date,
            effective_date=version.effective_date,
            expiry_date=version.expiry_date,
            collection_ids=(collection_id,),
            validity_status=validity_status,
            is_verified=True,
        )
        try:
            self.index_writer(version_id=version.version_id, metadata=metadata, chunks=chunks)
        except Exception as exc:  # noqa: BLE001 - mapped to a stable error code
            LOGGER.exception("Indexing failed job_id=%s", job_id)
            self._fail(job_id, INDEX_FAILED)
            raise IngestionError("Indexing the released document failed") from exc

        self.ingestion_service.transition(job_id, JobStatus.INDEXED)
        warnings: tuple[str, ...] = ()
        if not chunks:
            warnings = (
                "Không tạo được chunk nào: văn bản không có cấu trúc Điều/Khoản nhận dạng được. "
                "Phiên bản đã release nhưng chưa truy xuất được nội dung.",
            )
        LOGGER.info(
            "Pipeline indexed job_id=%s version_id=%s chunks=%d collection=%s",
            job_id,
            version.version_id,
            len(chunks),
            collection_id,
        )
        return ReleasedVersion(
            job_id=job_id,
            document_id=version.document_id,
            version_id=version.version_id,
            status=JobStatus.INDEXED,
            chunk_count=len(chunks),
            validity_status=validity_status,
            warnings=warnings,
        )

    # --- helpers ----------------------------------------------------------
    def _fail(self, job_id: str, error_code: str) -> None:
        """Record a stable failure code, tolerating states that cannot fail."""
        try:
            self.ingestion_service.transition(job_id, JobStatus.FAILED, error_code=error_code)
        except Exception:  # noqa: BLE001 - the original failure is what matters
            LOGGER.warning(
                "Could not record failure job_id=%s error_code=%s", job_id, error_code, exc_info=True
            )


def _extension_of(filename: str) -> str:
    return ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


def _decidable_tasks(result: LegalParseResult) -> tuple[ReviewTask, ...]:
    """Review items a reviewer decides on.

    Warnings are not decisions: they are acknowledged as a batch when the reviewer
    approves (``require_approval`` enforces that), so they are reported separately.
    """
    return tuple(
        task for task in pending_tasks(result) if task.item_kind is not ReviewItemKind.WARNING
    )
