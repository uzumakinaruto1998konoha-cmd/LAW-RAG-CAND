"""Domain models for knowledge base release: documents, versions, and processing runs.

A Document is the logical identity (number + issuing body + type).
A DocumentVersion is an immutable snapshot released from an approved parse.
Only approved documents may be released; unapproved documents cannot be retrieved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum


class RunType(str, Enum):
    RELEASE = "release"
    INDEX = "index"


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingOutcome(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


class DuplicateResolution(str, Enum):
    DUPLICATE = "duplicate"
    DISTINCT = "distinct"
    MERGE = "merge"


@dataclass(frozen=True, slots=True)
class Document:
    """Logical document identity across versions."""

    document_id: str
    document_number: str
    issuing_body: str
    document_type: str
    title: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.document_number.strip():
            raise ValueError("Document requires a document number")
        if not self.issuing_body.strip():
            raise ValueError("Document requires an issuing body")
        if not self.document_type.strip():
            raise ValueError("Document requires a document type")

    @classmethod
    def new(
        cls,
        *,
        document_id: str,
        document_number: str,
        issuing_body: str,
        document_type: str,
        title: str,
    ) -> Document:
        now = datetime.now(timezone.utc)
        return cls(
            document_id=document_id,
            document_number=document_number,
            issuing_body=issuing_body,
            document_type=document_type,
            title=title,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    """Immutable document version released from an approved ingestion job."""

    version_id: str
    document_id: str
    job_id: str
    parse_run_id: str
    version_number: int
    title: str
    issue_date: date
    effective_date: date | None
    expiry_date: date | None
    language: str
    source_reference: str | None
    content_hash: str
    released_at: datetime
    released_by: str
    superseded_by: str | None = None
    superseded_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.version_number <= 0:
            raise ValueError("Version number must be positive")
        if not self.content_hash or len(self.content_hash) != 64:
            raise ValueError("Content hash must be a 64-character hex string")
        if self.effective_date and self.effective_date < self.issue_date:
            raise ValueError("Effective date cannot be before issue date")
        if self.expiry_date and self.expiry_date <= self.issue_date:
            raise ValueError("Expiry date must be after issue date")
        if (self.superseded_by is None) != (self.superseded_at is None):
            raise ValueError("superseded_by and superseded_at must both be set or both be None")

    @property
    def is_superseded(self) -> bool:
        return self.superseded_by is not None

    @property
    def is_current(self) -> bool:
        return not self.is_superseded

    @classmethod
    def new(
        cls,
        *,
        version_id: str,
        document_id: str,
        job_id: str,
        parse_run_id: str,
        version_number: int,
        title: str,
        issue_date: date,
        effective_date: date | None,
        expiry_date: date | None,
        language: str,
        source_reference: str | None,
        content_hash: str,
        released_by: str,
    ) -> DocumentVersion:
        return cls(
            version_id=version_id,
            document_id=document_id,
            job_id=job_id,
            parse_run_id=parse_run_id,
            version_number=version_number,
            title=title,
            issue_date=issue_date,
            effective_date=effective_date,
            expiry_date=expiry_date,
            language=language,
            source_reference=source_reference,
            content_hash=content_hash,
            released_at=datetime.now(timezone.utc),
            released_by=released_by,
        )


@dataclass(frozen=True, slots=True)
class DocumentRelation:
    """Verified relation between document versions (from approved relation candidates)."""

    relation_id: str
    source_version_id: str
    target_version_id: str | None
    relation_type: str
    source_node_id: str | None
    target_scope_label: str | None
    valid_from: date | None
    valid_until: date | None
    created_at: datetime
    created_by: str

    def __post_init__(self) -> None:
        if not self.target_version_id and not self.target_scope_label:
            raise ValueError("Relation must have either target_version_id or target_scope_label")


@dataclass(frozen=True, slots=True)
class ProcessingRun:
    """Tracks release and indexing operations."""

    run_id: str
    run_type: RunType
    pipeline_version: str
    started_at: datetime
    completed_at: datetime | None
    status: RunStatus
    version_count: int
    error_code: str | None
    error_message: str | None
    initiated_by: str
    manifest: dict | None

    def __post_init__(self) -> None:
        if self.status is RunStatus.COMPLETED and not self.completed_at:
            raise ValueError("Completed run requires completed_at timestamp")
        if self.status is RunStatus.FAILED and not self.error_code:
            raise ValueError("Failed run requires error_code")
        if self.version_count < 0:
            raise ValueError("Version count cannot be negative")

    @classmethod
    def new(
        cls,
        *,
        run_id: str,
        run_type: RunType,
        pipeline_version: str,
        initiated_by: str,
        manifest: dict | None = None,
    ) -> ProcessingRun:
        return cls(
            run_id=run_id,
            run_type=run_type,
            pipeline_version=pipeline_version,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            status=RunStatus.RUNNING,
            version_count=0,
            error_code=None,
            error_message=None,
            initiated_by=initiated_by,
            manifest=manifest,
        )


@dataclass(frozen=True, slots=True)
class VersionProcessingRecord:
    """Links document versions to processing runs for audit and rollback."""

    record_id: int | None
    run_id: str
    version_id: str
    processed_at: datetime
    outcome: ProcessingOutcome
    error_code: str | None

    def __post_init__(self) -> None:
        if self.outcome is ProcessingOutcome.ERROR and not self.error_code:
            raise ValueError("Error outcome requires error_code")

    @classmethod
    def success(
        cls,
        *,
        run_id: str,
        version_id: str,
    ) -> VersionProcessingRecord:
        return cls(
            record_id=None,
            run_id=run_id,
            version_id=version_id,
            processed_at=datetime.now(timezone.utc),
            outcome=ProcessingOutcome.SUCCESS,
            error_code=None,
        )

    @classmethod
    def error(
        cls,
        *,
        run_id: str,
        version_id: str,
        error_code: str,
    ) -> VersionProcessingRecord:
        return cls(
            record_id=None,
            run_id=run_id,
            version_id=version_id,
            processed_at=datetime.now(timezone.utc),
            outcome=ProcessingOutcome.ERROR,
            error_code=error_code,
        )


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    """Near-duplicate document version pair detected during release."""

    candidate_id: int | None
    version_id_a: str
    version_id_b: str
    similarity_score: float
    detection_method: str
    detected_at: datetime
    resolution: DuplicateResolution | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.similarity_score <= 1.0:
            raise ValueError("Similarity score must be between 0 and 1")
        if self.version_id_a >= self.version_id_b:
            raise ValueError("version_id_a must be less than version_id_b for uniqueness")
        if (self.resolution is None) != (self.resolved_by is None):
            raise ValueError("resolution and resolved_by must both be set or both be None")

    @property
    def is_resolved(self) -> bool:
        return self.resolution is not None

    @classmethod
    def new(
        cls,
        *,
        version_id_a: str,
        version_id_b: str,
        similarity_score: float,
        detection_method: str,
    ) -> DuplicateCandidate:
        # Enforce ordering
        if version_id_a > version_id_b:
            version_id_a, version_id_b = version_id_b, version_id_a
        return cls(
            candidate_id=None,
            version_id_a=version_id_a,
            version_id_b=version_id_b,
            similarity_score=similarity_score,
            detection_method=detection_method,
            detected_at=datetime.now(timezone.utc),
        )
