"""PostgreSQL adapter for knowledge base release: documents, versions, and processing runs."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence

from .kb_models import (
    Document,
    DocumentRelation,
    DocumentVersion,
    DuplicateCandidate,
    DuplicateResolution,
    ProcessingOutcome,
    ProcessingRun,
    RunStatus,
    RunType,
    VersionProcessingRecord,
)

if TYPE_CHECKING:
    from .repository import ConnectionFactory

LOGGER = logging.getLogger(__name__)


class KnowledgeBaseRepository:
    """Persists document identity, versions, deduplication and processing runs."""

    def __init__(self, *, connection_factory: "ConnectionFactory") -> None:
        self.connection_factory = connection_factory

    def save_document(self, document: Document) -> None:
        """Insert or update a document's logical identity."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO document (
                    document_id, document_number, issuing_body, document_type,
                    title, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_number, issuing_body, document_type)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    updated_at = EXCLUDED.updated_at
                RETURNING document_id
                """,
                (
                    document.document_id,
                    document.document_number,
                    document.issuing_body,
                    document.document_type,
                    document.title,
                    document.created_at,
                    document.updated_at,
                ),
            )
            conn.commit()

    def find_document(
        self,
        *,
        document_number: str,
        issuing_body: str,
        document_type: str,
    ) -> Document | None:
        """Find a document by its identity triple."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT document_id, document_number, issuing_body, document_type,
                       title, created_at, updated_at
                FROM document
                WHERE document_number = %s AND issuing_body = %s AND document_type = %s
                """,
                (document_number, issuing_body, document_type),
            )
            row = cur.fetchone()
            if not row:
                return None
            return Document(
                document_id=row[0],
                document_number=row[1],
                issuing_body=row[2],
                document_type=row[3],
                title=row[4],
                created_at=row[5],
                updated_at=row[6],
            )

    def get_document(self, document_id: str) -> Document | None:
        """Get a document by its ID."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT document_id, document_number, issuing_body, document_type,
                       title, created_at, updated_at
                FROM document
                WHERE document_id = %s
                """,
                (document_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return Document(
                document_id=row[0],
                document_number=row[1],
                issuing_body=row[2],
                document_type=row[3],
                title=row[4],
                created_at=row[5],
                updated_at=row[6],
            )

    def save_version(self, version: DocumentVersion) -> None:
        """Insert a document version (must be unique per job_id and per document+version_number)."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO document_version (
                    version_id, document_id, job_id, parse_run_id, version_number,
                    title, issue_date, effective_date, expiry_date, language,
                    source_reference, content_hash, released_at, released_by,
                    superseded_by, superseded_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    version.version_id,
                    version.document_id,
                    version.job_id,
                    version.parse_run_id,
                    version.version_number,
                    version.title,
                    version.issue_date,
                    version.effective_date,
                    version.expiry_date,
                    version.language,
                    version.source_reference,
                    version.content_hash,
                    version.released_at,
                    version.released_by,
                    version.superseded_by,
                    version.superseded_at,
                ),
            )
            conn.commit()

    def get_version_by_job(self, job_id: str) -> DocumentVersion | None:
        """Find the document version released from a given job."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT version_id, document_id, job_id, parse_run_id, version_number,
                       title, issue_date, effective_date, expiry_date, language,
                       source_reference, content_hash, released_at, released_by,
                       superseded_by, superseded_at
                FROM document_version
                WHERE job_id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_version(row)

    def get_version(self, version_id: str) -> DocumentVersion | None:
        """Get a document version by its ID."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT version_id, document_id, job_id, parse_run_id, version_number,
                       title, issue_date, effective_date, expiry_date, language,
                       source_reference, content_hash, released_at, released_by,
                       superseded_by, superseded_at
                FROM document_version
                WHERE version_id = %s
                """,
                (version_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_version(row)

    def list_versions(self, document_id: str) -> tuple[DocumentVersion, ...]:
        """List all versions of a document, newest first."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT version_id, document_id, job_id, parse_run_id, version_number,
                       title, issue_date, effective_date, expiry_date, language,
                       source_reference, content_hash, released_at, released_by,
                       superseded_by, superseded_at
                FROM document_version
                WHERE document_id = %s
                ORDER BY version_number DESC
                """,
                (document_id,),
            )
            return tuple(self._row_to_version(row) for row in cur.fetchall())

    def get_latest_version(self, document_id: str) -> DocumentVersion | None:
        """Get the most recent version of a document."""
        versions = self.list_versions(document_id)
        return versions[0] if versions else None

    def supersede_version(
        self,
        version_id: str,
        *,
        superseded_by: str,
        superseded_at: datetime,
    ) -> None:
        """Mark a version as superseded by a newer version."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE document_version
                SET superseded_by = %s, superseded_at = %s
                WHERE version_id = %s
                """,
                (superseded_by, superseded_at, version_id),
            )
            conn.commit()

    def save_relation(self, relation: DocumentRelation) -> None:
        """Insert a verified document relation."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO document_relation (
                    relation_id, source_version_id, target_version_id, relation_type,
                    source_node_id, target_scope_label, valid_from, valid_until,
                    created_at, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    relation.relation_id,
                    relation.source_version_id,
                    relation.target_version_id,
                    relation.relation_type,
                    relation.source_node_id,
                    relation.target_scope_label,
                    relation.valid_from,
                    relation.valid_until,
                    relation.created_at,
                    relation.created_by,
                ),
            )
            conn.commit()

    def list_relations(
        self,
        *,
        source_version_id: str | None = None,
        target_version_id: str | None = None,
    ) -> tuple[DocumentRelation, ...]:
        """List relations by source or target version."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            if source_version_id:
                cur.execute(
                    """
                    SELECT relation_id, source_version_id, target_version_id, relation_type,
                           source_node_id, target_scope_label, valid_from, valid_until,
                           created_at, created_by
                    FROM document_relation
                    WHERE source_version_id = %s
                    """,
                    (source_version_id,),
                )
            elif target_version_id:
                cur.execute(
                    """
                    SELECT relation_id, source_version_id, target_version_id, relation_type,
                           source_node_id, target_scope_label, valid_from, valid_until,
                           created_at, created_by
                    FROM document_relation
                    WHERE target_version_id = %s
                    """,
                    (target_version_id,),
                )
            else:
                return ()
            return tuple(self._row_to_relation(row) for row in cur.fetchall())

    def save_processing_run(self, run: ProcessingRun) -> None:
        """Insert or update a processing run."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            manifest_json = json.dumps(run.manifest) if run.manifest else None
            cur.execute(
                """
                INSERT INTO processing_run (
                    run_id, run_type, pipeline_version, started_at, completed_at,
                    status, version_count, error_code, error_message, initiated_by, manifest
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id)
                DO UPDATE SET
                    completed_at = EXCLUDED.completed_at,
                    status = EXCLUDED.status,
                    version_count = EXCLUDED.version_count,
                    error_code = EXCLUDED.error_code,
                    error_message = EXCLUDED.error_message
                """,
                (
                    run.run_id,
                    run.run_type.value,
                    run.pipeline_version,
                    run.started_at,
                    run.completed_at,
                    run.status.value,
                    run.version_count,
                    run.error_code,
                    run.error_message,
                    run.initiated_by,
                    manifest_json,
                ),
            )
            conn.commit()

    def get_processing_run(self, run_id: str) -> ProcessingRun | None:
        """Get a processing run by its ID."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, run_type, pipeline_version, started_at, completed_at,
                       status, version_count, error_code, error_message, initiated_by, manifest
                FROM processing_run
                WHERE run_id = %s
                """,
                (run_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_run(row)

    def list_processing_runs(
        self,
        *,
        run_type: RunType | None = None,
        status: RunStatus | None = None,
        limit: int = 50,
    ) -> tuple[ProcessingRun, ...]:
        """List processing runs, newest first."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            query = """
                SELECT run_id, run_type, pipeline_version, started_at, completed_at,
                       status, version_count, error_code, error_message, initiated_by, manifest
                FROM processing_run
                WHERE 1=1
            """
            params: list[Any] = []
            if run_type:
                query += " AND run_type = %s"
                params.append(run_type.value)
            if status:
                query += " AND status = %s"
                params.append(status.value)
            query += " ORDER BY started_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(query, params)
            return tuple(self._row_to_run(row) for row in cur.fetchall())

    def save_version_record(self, record: VersionProcessingRecord) -> None:
        """Insert a version processing record."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO version_processing_record (
                    run_id, version_id, processed_at, outcome, error_code
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    record.run_id,
                    record.version_id,
                    record.processed_at,
                    record.outcome.value,
                    record.error_code,
                ),
            )
            conn.commit()

    def list_version_records(
        self,
        *,
        run_id: str | None = None,
        version_id: str | None = None,
    ) -> tuple[VersionProcessingRecord, ...]:
        """List version processing records by run or version."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            if run_id:
                cur.execute(
                    """
                    SELECT record_id, run_id, version_id, processed_at, outcome, error_code
                    FROM version_processing_record
                    WHERE run_id = %s
                    ORDER BY processed_at
                    """,
                    (run_id,),
                )
            elif version_id:
                cur.execute(
                    """
                    SELECT record_id, run_id, version_id, processed_at, outcome, error_code
                    FROM version_processing_record
                    WHERE version_id = %s
                    ORDER BY processed_at DESC
                    """,
                    (version_id,),
                )
            else:
                return ()
            return tuple(self._row_to_record(row) for row in cur.fetchall())

    def save_duplicate_candidate(self, candidate: DuplicateCandidate) -> None:
        """Insert a duplicate candidate (unique constraint on version pair)."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO duplicate_candidate (
                    version_id_a, version_id_b, similarity_score, detection_method,
                    detected_at, resolution, resolved_by, resolved_at, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (version_id_a, version_id_b) DO NOTHING
                """,
                (
                    candidate.version_id_a,
                    candidate.version_id_b,
                    candidate.similarity_score,
                    candidate.detection_method,
                    candidate.detected_at,
                    candidate.resolution.value if candidate.resolution else None,
                    candidate.resolved_by,
                    candidate.resolved_at,
                    candidate.notes,
                ),
            )
            conn.commit()

    def resolve_duplicate(
        self,
        candidate_id: int,
        *,
        resolution: DuplicateResolution,
        resolved_by: str,
        resolved_at: datetime,
        notes: str | None = None,
    ) -> None:
        """Mark a duplicate candidate as resolved."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE duplicate_candidate
                SET resolution = %s, resolved_by = %s, resolved_at = %s, notes = %s
                WHERE candidate_id = %s
                """,
                (resolution.value, resolved_by, resolved_at, notes, candidate_id),
            )
            conn.commit()

    def list_unresolved_duplicates(self, limit: int = 100) -> tuple[DuplicateCandidate, ...]:
        """List unresolved duplicate candidates, newest first."""
        with self.connection_factory() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT candidate_id, version_id_a, version_id_b, similarity_score,
                       detection_method, detected_at, resolution, resolved_by, resolved_at, notes
                FROM duplicate_candidate
                WHERE resolution IS NULL
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return tuple(self._row_to_duplicate(row) for row in cur.fetchall())

    def _row_to_version(self, row: Sequence[Any]) -> DocumentVersion:
        return DocumentVersion(
            version_id=row[0],
            document_id=row[1],
            job_id=row[2],
            parse_run_id=row[3],
            version_number=row[4],
            title=row[5],
            issue_date=row[6],
            effective_date=row[7],
            expiry_date=row[8],
            language=row[9],
            source_reference=row[10],
            content_hash=row[11],
            released_at=row[12],
            released_by=row[13],
            superseded_by=row[14],
            superseded_at=row[15],
        )

    def _row_to_relation(self, row: Sequence[Any]) -> DocumentRelation:
        return DocumentRelation(
            relation_id=row[0],
            source_version_id=row[1],
            target_version_id=row[2],
            relation_type=row[3],
            source_node_id=row[4],
            target_scope_label=row[5],
            valid_from=row[6],
            valid_until=row[7],
            created_at=row[8],
            created_by=row[9],
        )

    def _row_to_run(self, row: Sequence[Any]) -> ProcessingRun:
        manifest = json.loads(row[10]) if row[10] else None
        return ProcessingRun(
            run_id=row[0],
            run_type=RunType(row[1]),
            pipeline_version=row[2],
            started_at=row[3],
            completed_at=row[4],
            status=RunStatus(row[5]),
            version_count=row[6],
            error_code=row[7],
            error_message=row[8],
            initiated_by=row[9],
            manifest=manifest,
        )

    def _row_to_record(self, row: Sequence[Any]) -> VersionProcessingRecord:
        return VersionProcessingRecord(
            record_id=row[0],
            run_id=row[1],
            version_id=row[2],
            processed_at=row[3],
            outcome=ProcessingOutcome(row[4]),
            error_code=row[5],
        )

    def _row_to_duplicate(self, row: Sequence[Any]) -> DuplicateCandidate:
        return DuplicateCandidate(
            candidate_id=row[0],
            version_id_a=row[1],
            version_id_b=row[2],
            similarity_score=row[3],
            detection_method=row[4],
            detected_at=row[5],
            resolution=DuplicateResolution(row[6]) if row[6] else None,
            resolved_by=row[7],
            resolved_at=row[8],
            notes=row[9],
        )
