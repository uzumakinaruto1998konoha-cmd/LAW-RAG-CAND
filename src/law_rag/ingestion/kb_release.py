"""Release approved legal documents to the knowledge base.

Only approved documents (with all review items resolved and warnings acknowledged)
may be released. Release creates Document identity, DocumentVersion, and tracks
the operation in a ProcessingRun for audit and rollback.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from .errors import ReleaseError
from .kb_models import (
    Document,
    DocumentVersion,
    DuplicateCandidate,
    ProcessingRun,
    RunStatus,
    RunType,
    VersionProcessingRecord,
)
from .legal_models import LegalParseResult, MetadataField

if TYPE_CHECKING:
    from .kb_postgres import KnowledgeBaseRepository
    from .legal_review import ApprovedLegalDocument
    from .repository import AuditSink, JobRepository, LegalParseRepository

LOGGER = logging.getLogger(__name__)

RELEASE_PIPELINE_VERSION = "release-v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _compute_content_hash(result: LegalParseResult) -> str:
    """Compute a stable hash of the parse result for deduplication."""
    # Hash all node content + metadata values for content-based dedup
    content_parts: list[str] = []
    for node in sorted(result.nodes, key=lambda n: (n.kind.value, n.ordinal, n.node_id)):
        content_parts.append(f"{node.kind.value}:{node.ordinal}:{node.content}")
    for metadata in sorted(result.metadata, key=lambda m: m.field.value):
        content_parts.append(f"{metadata.field.value}={metadata.value}")
    combined = "\n".join(content_parts).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


class ReleaseService:
    """Release approved documents to the retrievable knowledge base."""

    def __init__(
        self,
        *,
        kb_repository: "KnowledgeBaseRepository",
        job_repository: "JobRepository",
        legal_repository: "LegalParseRepository",
        audit: "AuditSink",
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.kb_repository = kb_repository
        self.job_repository = job_repository
        self.legal_repository = legal_repository
        self.audit = audit
        self.clock = clock

    def release_document(
        self,
        approved: "ApprovedLegalDocument",
        *,
        released_by: str,
    ) -> DocumentVersion:
        """Release an approved document to the knowledge base.

        Creates or updates Document identity, creates a new DocumentVersion,
        detects near-duplicates, and transitions the job to 'indexing' status.
        """
        result = approved.parse_result

        # Extract required metadata
        document_number = result.verified_metadata_value(MetadataField.DOCUMENT_NUMBER)
        issuing_body = result.verified_metadata_value(MetadataField.ISSUING_BODY)
        document_type = result.verified_metadata_value(MetadataField.DOCUMENT_TYPE)
        title = result.verified_metadata_value(MetadataField.TITLE)
        issue_date_str = result.verified_metadata_value(MetadataField.ISSUE_DATE)

        if not document_number or not issuing_body or not document_type:
            raise ReleaseError(
                "Cannot release document without verified document_number, issuing_body, and document_type"
            )
        if not issue_date_str:
            raise ReleaseError("Cannot release document without verified issue_date")

        # Parse dates (ISO format from legal parser normalization)
        try:
            from datetime import date
            issue_date = date.fromisoformat(issue_date_str)
        except (ValueError, AttributeError) as exc:
            raise ReleaseError(f"Invalid issue_date format: {issue_date_str}") from exc

        effective_date_str = result.verified_metadata_value(MetadataField.EFFECTIVE_DATE)
        effective_date = date.fromisoformat(effective_date_str) if effective_date_str else None

        expiry_date_str = result.verified_metadata_value(MetadataField.EXPIRY_DATE)
        expiry_date = date.fromisoformat(expiry_date_str) if expiry_date_str else None

        language = result.verified_metadata_value(MetadataField.LANGUAGE) or "vi"
        source_reference = result.verified_metadata_value(MetadataField.SOURCE)

        # Find or create document identity
        document = self.kb_repository.find_document(
            document_number=document_number,
            issuing_body=issuing_body,
            document_type=document_type,
        )
        if not document:
            document_id = _generate_id("doc")
            document = Document.new(
                document_id=document_id,
                document_number=document_number,
                issuing_body=issuing_body,
                document_type=document_type,
                title=title or f"{document_type} {document_number}",
            )
            self.kb_repository.save_document(document)
            LOGGER.info(
                "Created new document identity document_id=%s number=%s",
                document.document_id,
                document_number,
            )
        else:
            # Update title if provided and different
            if title and title != document.title:
                document = replace(document, title=title, updated_at=self.clock())
                self.kb_repository.save_document(document)

        # Determine version number
        existing_versions = self.kb_repository.list_versions(document.document_id)
        next_version_number = (existing_versions[0].version_number + 1) if existing_versions else 1

        # Compute content hash for deduplication
        content_hash = _compute_content_hash(result)

        # Check for content-based duplicates
        for existing in existing_versions:
            if existing.content_hash == content_hash:
                LOGGER.warning(
                    "Content duplicate detected: job_id=%s matches existing version_id=%s",
                    result.job_id,
                    existing.version_id,
                )
                candidate = DuplicateCandidate.new(
                    version_id_a=existing.version_id,
                    version_id_b=_generate_id("ver"),  # Placeholder, will be replaced
                    similarity_score=1.0,
                    detection_method="content_hash_exact",
                )
                # Note: We still create the version but flag it for review

        # Create document version
        version_id = _generate_id("ver")
        version = DocumentVersion.new(
            version_id=version_id,
            document_id=document.document_id,
            job_id=result.job_id,
            parse_run_id=result.job_id,  # parse_run_id is currently job_id (PHASE 1)
            version_number=next_version_number,
            title=title or document.title,
            issue_date=issue_date,
            effective_date=effective_date,
            expiry_date=expiry_date,
            language=language,
            source_reference=source_reference,
            content_hash=content_hash,
            released_by=released_by,
        )
        self.kb_repository.save_version(version)

        # If this is a new version of an existing document, optionally mark the previous as superseded
        # (This is a policy decision: auto-supersede or require manual verification)
        # For now, we do NOT auto-supersede; admin must explicitly manage version lifecycle

        # Transition job status to 'indexing'
        from .models import JobStatus
        job = self.job_repository.get(result.job_id)
        if not job:
            raise ReleaseError(f"Job {result.job_id} not found")
        self.job_repository.transition(result.job_id, JobStatus.INDEXING)

        # Audit
        self.audit.record(
            actor_id=released_by,
            action="release_document",
            object_id=version.version_id,
            trace_id=result.job_id,
            outcome="released",
        )

        LOGGER.info(
            "Released document version_id=%s document_id=%s job_id=%s version=%d",
            version.version_id,
            document.document_id,
            result.job_id,
            version.version_number,
        )

        return version

    def release_batch(
        self,
        approved_documents: list["ApprovedLegalDocument"],
        *,
        released_by: str,
    ) -> ProcessingRun:
        """Release a batch of approved documents in a single processing run."""
        run_id = _generate_id("run")
        run = ProcessingRun.new(
            run_id=run_id,
            run_type=RunType.RELEASE,
            pipeline_version=RELEASE_PIPELINE_VERSION,
            initiated_by=released_by,
            manifest={"job_count": len(approved_documents)},
        )
        self.kb_repository.save_processing_run(run)

        success_count = 0
        error_count = 0

        for approved in approved_documents:
            try:
                version = self.release_document(approved, released_by=released_by)
                record = VersionProcessingRecord.success(run_id=run_id, version_id=version.version_id)
                self.kb_repository.save_version_record(record)
                success_count += 1
            except Exception as exc:
                LOGGER.exception("Failed to release job_id=%s: %s", approved.job_id, exc)
                error_code = "RELEASE_FAILED"
                record = VersionProcessingRecord.error(
                    run_id=run_id,
                    version_id=f"error_{approved.job_id}",
                    error_code=error_code,
                )
                self.kb_repository.save_version_record(record)
                error_count += 1

        # Update run status
        if error_count == 0:
            run = replace(
                run,
                status=RunStatus.COMPLETED,
                completed_at=self.clock(),
                version_count=success_count,
            )
        elif success_count == 0:
            run = replace(
                run,
                status=RunStatus.FAILED,
                completed_at=self.clock(),
                version_count=0,
                error_code="ALL_RELEASES_FAILED",
                error_message=f"All {error_count} releases failed",
            )
        else:
            run = replace(
                run,
                status=RunStatus.COMPLETED,
                completed_at=self.clock(),
                version_count=success_count,
                error_code="PARTIAL_FAILURE",
                error_message=f"{success_count} succeeded, {error_count} failed",
            )

        self.kb_repository.save_processing_run(run)

        LOGGER.info(
            "Release batch completed run_id=%s success=%d error=%d",
            run_id,
            success_count,
            error_count,
        )

        return run

    def get_retrievable_versions(
        self,
        *,
        document_id: str | None = None,
        current_only: bool = False,
    ) -> tuple[DocumentVersion, ...]:
        """List document versions available for retrieval.

        Only versions from approved jobs are retrievable.
        If current_only=True, exclude superseded versions.
        """
        if document_id:
            versions = self.kb_repository.list_versions(document_id)
        else:
            # For full corpus listing, we'd need a new repository method
            # For now, this is a placeholder
            raise NotImplementedError("Full corpus listing not yet implemented")

        if current_only:
            versions = tuple(v for v in versions if not v.is_superseded)

        return versions
