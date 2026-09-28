"""In-memory ingestion adapters for development and tests.

Production deployments use the PostgreSQL adapters (ADR-003). These adapters exist
so the API layer and test suites can run without a database while keeping the
same contracts as ``JobRepository``/``AuditSink``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from dataclasses import replace

from .errors import IdempotencyConflictError
from .kb_models import (
    Document,
    DocumentRelation,
    DocumentVersion,
    DuplicateCandidate,
    DuplicateResolution,
    ProcessingRun,
    RunStatus,
    RunType,
    VersionProcessingRecord,
)
from .models import IngestionJob, JobStatus

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids import cycles
    from .legal_models import LegalParseResult
    from .legal_review import ApprovedLegalDocument, ReviewDecision


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


class InMemoryLegalParseRepository:
    """Process-local LegalParseRepository: keeps every parse revision per job."""

    def __init__(self) -> None:
        self.results: dict[str, list["LegalParseResult"]] = {}
        self.decisions: dict[str, list["ReviewDecision"]] = {}
        self.approvals: dict[str, "ApprovedLegalDocument"] = {}

    def save_result(self, result: "LegalParseResult") -> "LegalParseResult":
        self.results.setdefault(result.job_id, []).append(result)
        return result

    def get_latest(self, job_id: str) -> "LegalParseResult | None":
        revisions = self.results.get(job_id)
        return revisions[-1] if revisions else None

    def save_decisions(self, job_id: str, decisions: Sequence["ReviewDecision"]) -> None:
        self.decisions.setdefault(job_id, []).extend(decisions)

    def save_approval(self, approval: "ApprovedLegalDocument") -> None:
        self.approvals[approval.job_id] = approval

    def get_approval(self, job_id: str) -> "ApprovedLegalDocument | None":
        return self.approvals.get(job_id)


class InMemoryKnowledgeBaseRepository:
    """Process-local KnowledgeBaseRepository with the PostgreSQL adapter contract.

    Production keeps PostgreSQL as the knowledge base source of truth (ADR-003);
    this adapter lets the API and tests run the release path without a database.
    """

    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.versions: dict[str, list[DocumentVersion]] = {}
        self.relations: list[DocumentRelation] = []
        self.runs: dict[str, ProcessingRun] = {}
        self.records: list[VersionProcessingRecord] = []
        self.duplicates: list[DuplicateCandidate] = []

    # --- documents --------------------------------------------------------
    def save_document(self, document: Document) -> None:
        self.documents[document.document_id] = document

    def get_document(self, document_id: str) -> Document | None:
        return self.documents.get(document_id)

    def find_document(
        self, *, document_number: str, issuing_body: str, document_type: str
    ) -> Document | None:
        for document in self.documents.values():
            if (
                document.document_number == document_number
                and document.issuing_body == issuing_body
                and document.document_type == document_type
            ):
                return document
        return None

    # --- versions ---------------------------------------------------------
    def save_version(self, version: DocumentVersion) -> None:
        versions = self.versions.setdefault(version.document_id, [])
        versions[:] = [item for item in versions if item.version_id != version.version_id]
        versions.append(version)
        versions.sort(key=lambda item: item.version_number, reverse=True)

    def get_version(self, version_id: str) -> DocumentVersion | None:
        return next(
            (item for versions in self.versions.values() for item in versions if item.version_id == version_id),
            None,
        )

    def get_version_by_job(self, job_id: str) -> DocumentVersion | None:
        return next(
            (item for versions in self.versions.values() for item in versions if item.job_id == job_id),
            None,
        )

    def list_versions(self, document_id: str) -> tuple[DocumentVersion, ...]:
        return tuple(sorted(self.versions.get(document_id, []), key=lambda item: item.version_number, reverse=True))

    def get_latest_version(self, document_id: str) -> DocumentVersion | None:
        versions = self.list_versions(document_id)
        return versions[0] if versions else None

    def supersede_version(self, version_id: str, *, superseded_by: str, superseded_at) -> None:
        for document_id, versions in self.versions.items():
            for position, item in enumerate(versions):
                if item.version_id == version_id:
                    versions[position] = replace(
                        item, superseded_by=superseded_by, superseded_at=superseded_at
                    )
                    return
        raise KeyError(f"Unknown version: {version_id}")

    def list_all_versions(self) -> tuple[DocumentVersion, ...]:
        return tuple(
            sorted(
                (item for versions in self.versions.values() for item in versions),
                key=lambda item: (item.document_id, item.version_number),
                reverse=True,
            )
        )

    # --- relations --------------------------------------------------------
    def save_relation(self, relation: DocumentRelation) -> None:
        self.relations.append(relation)

    def list_relations(
        self, *, source_version_id: str | None = None, target_version_id: str | None = None
    ) -> tuple[DocumentRelation, ...]:
        return tuple(
            relation
            for relation in self.relations
            if (source_version_id is None or relation.source_version_id == source_version_id)
            and (target_version_id is None or relation.target_version_id == target_version_id)
        )

    # --- processing runs --------------------------------------------------
    def save_processing_run(self, run: ProcessingRun) -> None:
        self.runs[run.run_id] = run

    def get_processing_run(self, run_id: str) -> ProcessingRun | None:
        return self.runs.get(run_id)

    def list_processing_runs(
        self,
        *,
        run_type: RunType | None = None,
        status: RunStatus | None = None,
        limit: int = 100,
    ) -> tuple[ProcessingRun, ...]:
        runs = [
            run
            for run in self.runs.values()
            if (run_type is None or run.run_type is run_type) and (status is None or run.status is status)
        ]
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(runs[:limit])

    def save_version_record(self, record: VersionProcessingRecord) -> None:
        self.records.append(record)

    def list_version_records(
        self, *, run_id: str | None = None, version_id: str | None = None
    ) -> tuple[VersionProcessingRecord, ...]:
        return tuple(
            record
            for record in self.records
            if (run_id is None or record.run_id == run_id)
            and (version_id is None or record.version_id == version_id)
        )

    # --- duplicates -------------------------------------------------------
    def save_duplicate_candidate(self, candidate: DuplicateCandidate) -> None:
        self.duplicates.append(replace(candidate, candidate_id=len(self.duplicates) + 1))

    def resolve_duplicate(
        self,
        candidate_id: int,
        *,
        resolution: DuplicateResolution,
        resolved_by: str,
        resolved_at,
        notes: str | None = None,
    ) -> None:
        for position, candidate in enumerate(self.duplicates):
            if candidate.candidate_id == candidate_id:
                self.duplicates[position] = replace(
                    candidate,
                    resolution=resolution,
                    resolved_by=resolved_by,
                    resolved_at=resolved_at,
                    notes=notes,
                )
                return
        raise KeyError(f"Unknown duplicate candidate: {candidate_id}")

    def list_unresolved_duplicates(self, limit: int = 100) -> tuple[DuplicateCandidate, ...]:
        pending = [candidate for candidate in self.duplicates if candidate.resolution is None]
        return tuple(pending[:limit])
