"""PostgreSQL adapters using an injected psycopg-compatible connection factory.

The database driver is intentionally supplied by deployment wiring so this
package does not silently add an unreviewed runtime dependency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, ContextManager, Protocol, cast

from .errors import IdempotencyConflictError, IngestionError, InvalidTransitionError
from .models import ALLOWED_TRANSITIONS, IngestionJob, JobStatus


class Cursor(Protocol):
    def fetchone(self) -> tuple[Any, ...] | None: ...


class Connection(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Cursor: ...


ConnectionFactory = Callable[[], ContextManager[Connection]]
_COLUMNS = "job_id, idempotency_key, sha256, original_filename, media_type, size_bytes, storage_key, status, trace_id, uploader_id, source, created_at, updated_at, attempt, error_code"
def _job(row: tuple[Any, ...] | None) -> IngestionJob | None:
    if row is None:
        return None
    return IngestionJob(
        job_id=str(row[0]), idempotency_key=str(row[1]), sha256=str(row[2]),
        original_filename=str(row[3]), media_type=str(row[4]), size_bytes=int(row[5]),
        storage_key=str(row[6]), status=JobStatus(row[7]), trace_id=str(row[8]),
        uploader_id=str(row[9]), source=cast(str | None, row[10]),
        created_at=cast(datetime, row[11]), updated_at=cast(datetime, row[12]),
        attempt=int(row[13]), error_code=cast(str | None, row[14]),
    )


class PostgresJobRepository:
    """Durable job store; unique DB constraints serialize upload races."""

    def __init__(self, connect: ConnectionFactory) -> None:
        self._connect = connect

    def _find(self, clause: str, value: str) -> IngestionJob | None:
        with self._connect() as connection:
            return _job(connection.execute(f"SELECT {_COLUMNS} FROM ingestion_job WHERE {clause}", (value,)).fetchone())

    def find_by_idempotency_key(self, key: str) -> IngestionJob | None:
        with self._connect() as connection:
            return _job(connection.execute(
                f"SELECT j.{_COLUMNS.replace(', ', ', j.')} FROM ingestion_job j JOIN ingestion_request r ON r.job_id=j.job_id WHERE r.idempotency_key=%s",
                (key,),
            ).fetchone())

    def find_by_sha256(self, sha256: str) -> IngestionJob | None:
        return self._find("sha256 = %s", sha256)

    def get(self, job_id: str) -> IngestionJob | None:
        return self._find("job_id = %s", job_id)

    def register_idempotency(self, key: str, sha256: str, job_id: str) -> IngestionJob:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO ingestion_request (idempotency_key, sha256, job_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (key, sha256, job_id),
                )
            existing = self.find_by_idempotency_key(key)
            if existing is None or existing.sha256 != sha256:
                raise IdempotencyConflictError("Idempotency key was already used for different content")
            return existing
        except IdempotencyConflictError:
            raise
        except Exception as exc:
            raise IngestionError("Idempotency record could not be saved") from exc

    def insert(self, job: IngestionJob) -> IngestionJob:
        values = (
            job.job_id, job.idempotency_key, job.sha256, job.original_filename,
            job.media_type, job.size_bytes, job.storage_key, job.status.value,
            job.trace_id, job.uploader_id, job.source, job.created_at, job.updated_at,
        )
        query = f"""INSERT INTO ingestion_job
            (job_id, idempotency_key, sha256, original_filename, media_type, size_bytes,
             storage_key, status, trace_id, uploader_id, source, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING RETURNING {_COLUMNS}"""
        try:
            with self._connect() as connection:
                row = connection.execute(query, values).fetchone()
                if row is not None:
                    result = _job(row)
                    assert result is not None
                    connection.execute(
                        "INSERT INTO ingestion_request (idempotency_key, sha256, job_id) VALUES (%s,%s,%s)",
                        (job.idempotency_key, job.sha256, job.job_id),
                    )
                    return result
        except Exception as exc:
            raise IngestionError("Ingestion job could not be recorded") from exc
        existing = self.find_by_idempotency_key(job.idempotency_key)
        if existing is not None:
            if existing.sha256 != job.sha256:
                raise IdempotencyConflictError("Idempotency key was already used for different content")
            return existing
        existing = self.find_by_sha256(job.sha256)
        if existing is not None:
            return self.register_idempotency(job.idempotency_key, job.sha256, existing.job_id)
        raise IngestionError("Ingestion job conflicted with an existing record")

    def transition(self, job_id: str, status: JobStatus, *, error_code: str | None = None) -> IngestionJob:
        try:
            with self._connect() as connection:
                current_row = connection.execute(
                    f"SELECT {_COLUMNS} FROM ingestion_job WHERE job_id = %s FOR UPDATE", (job_id,)
                ).fetchone()
                current = _job(current_row)
                if current is None:
                    raise IngestionError("Ingestion job was not found")
                if status not in ALLOWED_TRANSITIONS[current.status]:
                    raise InvalidTransitionError(f"Transition from {current.status} to {status} is not allowed")
                row = connection.execute(
                    f"UPDATE ingestion_job SET status=%s, error_code=%s, updated_at=now() WHERE job_id=%s RETURNING {_COLUMNS}",
                    (status.value, error_code, job_id),
                ).fetchone()
                result = _job(row)
                assert result is not None
                return result
        except (IngestionError, InvalidTransitionError):
            raise
        except Exception as exc:
            raise IngestionError("Ingestion job could not be updated") from exc

    def retry(self, job_id: str) -> IngestionJob:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    f"UPDATE ingestion_job SET status='queued', error_code=NULL, attempt=attempt+1, updated_at=now() WHERE job_id=%s AND status='failed' RETURNING {_COLUMNS}",
                    (job_id,),
                ).fetchone()
                result = _job(row)
                if result is None:
                    raise InvalidTransitionError("Only failed jobs may be retried")
                return result
        except InvalidTransitionError:
            raise
        except Exception as exc:
            raise IngestionError("Ingestion job could not be retried") from exc


class PostgresAuditSink:
    """Write minimal administrative audit records without file content."""

    def __init__(self, connect: ConnectionFactory) -> None:
        self._connect = connect

    def record(self, *, actor_id: str, action: str, object_id: str, trace_id: str, outcome: str) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO audit_event (actor_id, action, object_id, trace_id, outcome, occurred_at) VALUES (%s,%s,%s,%s,%s,now())",
                    (actor_id, action, object_id, trace_id, outcome),
                )
        except Exception as exc:
            raise IngestionError("Audit event could not be recorded") from exc
