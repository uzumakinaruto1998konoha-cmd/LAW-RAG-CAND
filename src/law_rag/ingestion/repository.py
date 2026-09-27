"""Persistence contracts for PostgreSQL-backed ingestion records."""

from __future__ import annotations

from typing import Protocol, Sequence

from .legal_models import LegalParseResult
from .legal_review import ApprovedLegalDocument, ReviewDecision
from .models import IngestionJob, JobStatus


class JobRepository(Protocol):
    """Atomic persistence boundary; production implementation must use PostgreSQL."""

    def find_by_idempotency_key(self, key: str) -> IngestionJob | None: ...

    def find_by_sha256(self, sha256: str) -> IngestionJob | None: ...

    def register_idempotency(self, key: str, sha256: str, job_id: str) -> IngestionJob: ...

    def get(self, job_id: str) -> IngestionJob | None: ...

    def insert(self, job: IngestionJob) -> IngestionJob: ...

    def transition(self, job_id: str, status: JobStatus, *, error_code: str | None = None) -> IngestionJob: ...

    def retry(self, job_id: str) -> IngestionJob: ...


class AuditSink(Protocol):
    """Audit adapter for the project-wide AuditEvent persistence model."""

    def record(self, *, actor_id: str, action: str, object_id: str, trace_id: str, outcome: str) -> None: ...


class LegalParseRepository(Protocol):
    """Durable storage for parse runs, reviewer decisions and approvals."""

    def save_result(self, result: LegalParseResult) -> LegalParseResult: ...

    def get_latest(self, job_id: str) -> LegalParseResult | None: ...

    def save_decisions(self, job_id: str, decisions: Sequence[ReviewDecision]) -> None: ...

    def save_approval(self, approval: ApprovedLegalDocument) -> None: ...
