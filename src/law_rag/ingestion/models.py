"""Domain models for upload validation and ingestion job tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class JobStatus(str, Enum):
    UPLOADED = "uploaded"
    QUARANTINED = "quarantined"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    OCR = "ocr"
    PARSING = "parsing"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.EXTRACTING, JobStatus.FAILED, JobStatus.ARCHIVED}),
    JobStatus.EXTRACTING: frozenset({JobStatus.OCR, JobStatus.PARSING, JobStatus.REVIEW_REQUIRED, JobStatus.FAILED}),
    JobStatus.OCR: frozenset({JobStatus.PARSING, JobStatus.REVIEW_REQUIRED, JobStatus.FAILED}),
    JobStatus.PARSING: frozenset({JobStatus.REVIEW_REQUIRED, JobStatus.APPROVED, JobStatus.FAILED}),
    JobStatus.REVIEW_REQUIRED: frozenset({JobStatus.APPROVED, JobStatus.FAILED, JobStatus.ARCHIVED}),
    JobStatus.APPROVED: frozenset({JobStatus.INDEXING, JobStatus.SUPERSEDED, JobStatus.ARCHIVED}),
    JobStatus.INDEXING: frozenset({JobStatus.INDEXED, JobStatus.FAILED}),
    JobStatus.INDEXED: frozenset({JobStatus.SUPERSEDED, JobStatus.ARCHIVED}),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED, JobStatus.ARCHIVED}),
    JobStatus.UPLOADED: frozenset({JobStatus.QUARANTINED, JobStatus.QUEUED, JobStatus.FAILED}),
    JobStatus.QUARANTINED: frozenset({JobStatus.QUEUED, JobStatus.FAILED, JobStatus.ARCHIVED}),
    JobStatus.SUPERSEDED: frozenset({JobStatus.ARCHIVED}),
    JobStatus.ARCHIVED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class IngestionJob:
    job_id: str
    idempotency_key: str
    sha256: str
    original_filename: str
    media_type: str
    size_bytes: int
    storage_key: str
    status: JobStatus
    trace_id: str
    uploader_id: str
    source: str | None
    created_at: datetime
    updated_at: datetime
    attempt: int = 0
    error_code: str | None = None

    @classmethod
    def new(
        cls,
        *,
        job_id: str,
        idempotency_key: str,
        sha256: str,
        original_filename: str,
        media_type: str,
        size_bytes: int,
        storage_key: str,
        trace_id: str,
        uploader_id: str,
        source: str | None,
    ) -> IngestionJob:
        now = datetime.now(timezone.utc)
        return cls(
            job_id=job_id,
            idempotency_key=idempotency_key,
            sha256=sha256,
            original_filename=original_filename,
            media_type=media_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            status=JobStatus.QUEUED,
            trace_id=trace_id,
            uploader_id=uploader_id,
            source=source,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class UploadReceipt:
    job: IngestionJob
    duplicate: bool
