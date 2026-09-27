"""Unit tests for knowledge base domain models."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from law_rag.ingestion.kb_models import (
    Document,
    DocumentVersion,
    DuplicateCandidate,
    ProcessingOutcome,
    ProcessingRun,
    RunStatus,
    RunType,
    VersionProcessingRecord,
)

NOW = datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc)


class DocumentTests(unittest.TestCase):
    def test_document_requires_document_number(self) -> None:
        with self.assertRaises(ValueError):
            Document.new(
                document_id="doc-1",
                document_number="",
                issuing_body="Thủ tướng Chính phủ",
                document_type="Quyết định",
                title="Test Document",
            )

    def test_document_requires_issuing_body(self) -> None:
        with self.assertRaises(ValueError):
            Document.new(
                document_id="doc-1",
                document_number="184/2024/QĐ-TTg",
                issuing_body="",
                document_type="Quyết định",
                title="Test Document",
            )

    def test_document_requires_document_type(self) -> None:
        with self.assertRaises(ValueError):
            Document.new(
                document_id="doc-1",
                document_number="184/2024/QĐ-TTg",
                issuing_body="Thủ tướng Chính phủ",
                document_type="",
                title="Test Document",
            )

    def test_creates_document_with_timestamps(self) -> None:
        doc = Document.new(
            document_id="doc-1",
            document_number="184/2024/QĐ-TTg",
            issuing_body="Thủ tướng Chính phủ",
            document_type="Quyết định",
            title="Test Document",
        )
        
        self.assertEqual(doc.document_id, "doc-1")
        self.assertEqual(doc.document_number, "184/2024/QĐ-TTg")
        self.assertIsNotNone(doc.created_at)
        self.assertIsNotNone(doc.updated_at)


class DocumentVersionTests(unittest.TestCase):
    def test_version_requires_positive_version_number(self) -> None:
        with self.assertRaises(ValueError):
            DocumentVersion.new(
                version_id="ver-1",
                document_id="doc-1",
                job_id="job-1",
                parse_run_id="run-1",
                version_number=0,
                title="Test",
                issue_date=date(2024, 12, 22),
                effective_date=None,
                expiry_date=None,
                language="vi",
                source_reference=None,
                content_hash="a" * 64,
                released_by="admin@test",
            )

    def test_version_requires_64_char_hash(self) -> None:
        with self.assertRaises(ValueError):
            DocumentVersion.new(
                version_id="ver-1",
                document_id="doc-1",
                job_id="job-1",
                parse_run_id="run-1",
                version_number=1,
                title="Test",
                issue_date=date(2024, 12, 22),
                effective_date=None,
                expiry_date=None,
                language="vi",
                source_reference=None,
                content_hash="abc",
                released_by="admin@test",
            )

    def test_effective_date_cannot_precede_issue_date(self) -> None:
        with self.assertRaises(ValueError):
            DocumentVersion.new(
                version_id="ver-1",
                document_id="doc-1",
                job_id="job-1",
                parse_run_id="run-1",
                version_number=1,
                title="Test",
                issue_date=date(2024, 12, 22),
                effective_date=date(2024, 12, 21),
                expiry_date=None,
                language="vi",
                source_reference=None,
                content_hash="a" * 64,
                released_by="admin@test",
            )

    def test_expiry_date_must_be_after_issue_date(self) -> None:
        with self.assertRaises(ValueError):
            DocumentVersion.new(
                version_id="ver-1",
                document_id="doc-1",
                job_id="job-1",
                parse_run_id="run-1",
                version_number=1,
                title="Test",
                issue_date=date(2024, 12, 22),
                effective_date=None,
                expiry_date=date(2024, 12, 22),
                language="vi",
                source_reference=None,
                content_hash="a" * 64,
                released_by="admin@test",
            )

    def test_creates_version_with_valid_dates(self) -> None:
        version = DocumentVersion.new(
            version_id="ver-1",
            document_id="doc-1",
            job_id="job-1",
            parse_run_id="run-1",
            version_number=1,
            title="Test Document",
            issue_date=date(2024, 12, 22),
            effective_date=date(2025, 1, 1),
            expiry_date=date(2026, 12, 31),
            language="vi",
            source_reference="https://example.com/doc",
            content_hash="a" * 64,
            released_by="admin@test",
        )
        
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.issue_date, date(2024, 12, 22))
        self.assertEqual(version.effective_date, date(2025, 1, 1))
        self.assertIsNotNone(version.released_at)
        self.assertFalse(version.is_superseded)
        self.assertTrue(version.is_current)

    def test_superseded_version_properties(self) -> None:
        version = DocumentVersion.new(
            version_id="ver-1",
            document_id="doc-1",
            job_id="job-1",
            parse_run_id="run-1",
            version_number=1,
            title="Test",
            issue_date=date(2024, 12, 22),
            effective_date=None,
            expiry_date=None,
            language="vi",
            source_reference=None,
            content_hash="a" * 64,
            released_by="admin@test",
        )
        
        # Simulate superseding
        from dataclasses import replace
        superseded = replace(version, superseded_by="ver-2", superseded_at=NOW)
        
        self.assertTrue(superseded.is_superseded)
        self.assertFalse(superseded.is_current)


class ProcessingRunTests(unittest.TestCase):
    def test_processing_run_starts_running(self) -> None:
        run = ProcessingRun.new(
            run_id="run-1",
            run_type=RunType.RELEASE,
            pipeline_version="release-v1",
            initiated_by="admin@test",
        )
        
        self.assertEqual(run.status, RunStatus.RUNNING)
        self.assertEqual(run.version_count, 0)
        self.assertIsNotNone(run.started_at)
        self.assertIsNone(run.completed_at)
        self.assertIsNone(run.error_code)

    def test_completed_run_requires_completed_at(self) -> None:
        with self.assertRaises(ValueError):
            ProcessingRun(
                run_id="run-1",
                run_type=RunType.RELEASE,
                pipeline_version="release-v1",
                started_at=NOW,
                completed_at=None,
                status=RunStatus.COMPLETED,
                version_count=5,
                error_code=None,
                error_message=None,
                initiated_by="admin@test",
                manifest=None,
            )

    def test_failed_run_requires_error_code(self) -> None:
        with self.assertRaises(ValueError):
            ProcessingRun(
                run_id="run-1",
                run_type=RunType.RELEASE,
                pipeline_version="release-v1",
                started_at=NOW,
                completed_at=NOW,
                status=RunStatus.FAILED,
                version_count=0,
                error_code=None,
                error_message=None,
                initiated_by="admin@test",
                manifest=None,
            )


class VersionProcessingRecordTests(unittest.TestCase):
    def test_success_record(self) -> None:
        record = VersionProcessingRecord.success(
            run_id="run-1",
            version_id="ver-1",
        )
        
        self.assertEqual(record.run_id, "run-1")
        self.assertEqual(record.version_id, "ver-1")
        self.assertEqual(record.outcome, ProcessingOutcome.SUCCESS)
        self.assertIsNone(record.error_code)

    def test_error_record_requires_error_code(self) -> None:
        record = VersionProcessingRecord.error(
            run_id="run-1",
            version_id="ver-1",
            error_code="RELEASE_FAILED",
        )
        
        self.assertEqual(record.outcome, ProcessingOutcome.ERROR)
        self.assertEqual(record.error_code, "RELEASE_FAILED")


class DuplicateCandidateTests(unittest.TestCase):
    def test_similarity_score_must_be_between_0_and_1(self) -> None:
        with self.assertRaises(ValueError):
            DuplicateCandidate.new(
                version_id_a="ver-1",
                version_id_b="ver-2",
                similarity_score=1.5,
                detection_method="content_hash",
            )

    def test_enforces_version_id_ordering(self) -> None:
        candidate = DuplicateCandidate.new(
            version_id_a="ver-2",
            version_id_b="ver-1",
            similarity_score=0.95,
            detection_method="content_hash",
        )
        
        # Should swap to enforce ver-1 < ver-2
        self.assertEqual(candidate.version_id_a, "ver-1")
        self.assertEqual(candidate.version_id_b, "ver-2")

    def test_unresolved_candidate(self) -> None:
        candidate = DuplicateCandidate.new(
            version_id_a="ver-1",
            version_id_b="ver-2",
            similarity_score=0.95,
            detection_method="content_hash",
        )
        
        self.assertFalse(candidate.is_resolved)
        self.assertIsNone(candidate.resolution)


if __name__ == "__main__":
    unittest.main()
