"""Orchestrate upload validation, blob storage and job lifecycle."""

from __future__ import annotations

import io
import logging
import re
import uuid

from .errors import IdempotencyConflictError, IngestionError, InvalidTransitionError
from .models import ALLOWED_TRANSITIONS, IngestionJob, JobStatus, UploadReceipt
from .repository import AuditSink, JobRepository
from .storage import FileBlobStore
from .validation import DEFAULT_MAX_BYTES, validate_upload

LOGGER = logging.getLogger(__name__)
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
class IngestionService:
    def __init__(
        self,
        *,
        repository: JobRepository,
        blob_store: FileBlobStore,
        audit: AuditSink,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        if max_bytes <= 0 or max_bytes > DEFAULT_MAX_BYTES:
            raise ValueError("max_bytes must be between 1 and the v1 50 MiB limit")
        self.repository = repository
        self.blob_store = blob_store
        self.audit = audit
        self.max_bytes = max_bytes

    def upload(
        self,
        *,
        filename: str,
        stream: io.BufferedIOBase,
        idempotency_key: str,
        uploader_id: str,
        source: str | None = None,
        trace_id: str | None = None,
    ) -> UploadReceipt:
        if not _IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise IdempotencyConflictError("Idempotency key is invalid")
        request_trace = trace_id or str(uuid.uuid4())
        upload = validate_upload(filename, stream, max_bytes=self.max_bytes)
        existing_key = self.repository.find_by_idempotency_key(idempotency_key)
        if existing_key is not None:
            if existing_key.sha256 != upload.sha256:
                raise IdempotencyConflictError("Idempotency key was already used for different content")
            self.audit.record(actor_id=uploader_id, action="upload", object_id=existing_key.job_id, trace_id=request_trace, outcome="idempotent_replay")
            return UploadReceipt(existing_key, duplicate=True)

        duplicate = self.repository.find_by_sha256(upload.sha256)
        storage_key = self.blob_store.put(upload.content, upload.sha256)
        if duplicate is not None:
            duplicate_job = self.repository.register_idempotency(idempotency_key, upload.sha256, duplicate.job_id)
            self.audit.record(actor_id=uploader_id, action="upload", object_id=duplicate_job.job_id, trace_id=request_trace, outcome="exact_duplicate")
            return UploadReceipt(duplicate_job, duplicate=True)

        job = IngestionJob.new(
            job_id=str(uuid.uuid4()), idempotency_key=idempotency_key, sha256=upload.sha256,
            original_filename=upload.original_filename, media_type=upload.media_type,
            size_bytes=upload.size_bytes, storage_key=storage_key, trace_id=request_trace,
            uploader_id=uploader_id, source=source,
        )
        try:
            persisted = self.repository.insert(job)
        except IngestionError:
            raise
        except Exception as exc:
            LOGGER.exception("Job persistence failed trace_id=%s", request_trace)
            raise IngestionError("Ingestion job could not be recorded") from exc
        self.audit.record(actor_id=uploader_id, action="upload", object_id=persisted.job_id, trace_id=request_trace, outcome="queued")
        LOGGER.info("Ingestion job queued job_id=%s trace_id=%s", persisted.job_id, request_trace)
        return UploadReceipt(persisted, duplicate=persisted.job_id != job.job_id)

    def transition(self, job_id: str, status: JobStatus, *, error_code: str | None = None) -> IngestionJob:
        current = self.repository.get(job_id)
        if current is None:
            raise IngestionError("Ingestion job was not found")
        if status not in ALLOWED_TRANSITIONS[current.status]:
            raise InvalidTransitionError(f"Transition from {current.status} to {status} is not allowed")
        if status == JobStatus.FAILED and (not error_code or not re.fullmatch(r"[A-Z0-9_]{2,64}", error_code)):
            raise IngestionError("A stable error code is required when failing a job")
        updated = self.repository.transition(job_id, status, error_code=error_code)
        self.audit.record(actor_id=current.uploader_id, action="job_transition", object_id=job_id, trace_id=current.trace_id, outcome=status.value)
        return updated

    def retry(self, job_id: str) -> IngestionJob:
        current = self.repository.get(job_id)
        if current is None or current.status != JobStatus.FAILED:
            raise InvalidTransitionError("Only failed jobs may be retried")
        updated = self.repository.retry(job_id)
        self.audit.record(actor_id=current.uploader_id, action="job_retry", object_id=job_id, trace_id=current.trace_id, outcome="queued")
        return updated
