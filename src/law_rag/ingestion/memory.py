"""In-memory ingestion adapters for development and tests.

Production deployments use the PostgreSQL adapters (ADR-003). These adapters exist
so the API layer and test suites can run without a database while keeping the
same contracts as ``JobRepository``/``AuditSink``.
"""

from __future__ import annotations

from dataclasses import replace

from .errors import IdempotencyConflictError
from .models import IngestionJob, JobStatus


class InMemoryJobRepository:
    """Process-local JobRepository implementation (not durable)."""

    def __init__(self) -> None:
        self.jobs: dict[str, IngestionJob] = {}
        self.request_keys: dict[str, tuple[str, str]] = {}

    def find_by_idempotency_key(self, key: str) -> IngestionJob | None:
        record = self.request_keys.get(key)
        return self.jobs.get(record[1]) if record else None

    def find_by_sha256(self, sha256: str) -> IngestionJob | None:
        return next((job for job in self.jobs.values() if job.sha256 == sha256), None)

    def register_idempotency(self, key: str, sha256: str, job_id: str) -> IngestionJob:
        record = self.request_keys.get(key)
        if record is not None and record[0] != sha256:
            raise IdempotencyConflictError("Idempotency key was already used for different content")
        self.request_keys[key] = (sha256, job_id)
        return self.jobs[job_id]

    def get(self, job_id: str) -> IngestionJob | None:
        return self.jobs.get(job_id)

    def insert(self, job: IngestionJob) -> IngestionJob:
        self.jobs[job.job_id] = job
        self.request_keys[job.idempotency_key] = (job.sha256, job.job_id)
        return job

    def transition(
        self, job_id: str, status: JobStatus, *, error_code: str | None = None
    ) -> IngestionJob:
        current = self.jobs[job_id]
        updated = replace(current, status=status, error_code=error_code)
        self.jobs[job_id] = updated
        return updated

    def retry(self, job_id: str) -> IngestionJob:
        current = self.jobs[job_id]
        updated = replace(
            current,
            status=JobStatus.QUEUED,
            attempt=current.attempt + 1,
            error_code=None,
        )
        self.jobs[job_id] = updated
        return updated


class InMemoryAuditSink:
    """Process-local audit sink that keeps the same record contract."""

    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def record(self, *, actor_id: str, action: str, object_id: str, trace_id: str, outcome: str) -> None:
        self.events.append(
            {
                "actor_id": actor_id,
                "action": action,
                "object_id": object_id,
                "trace_id": trace_id,
                "outcome": outcome,
            }
        )
