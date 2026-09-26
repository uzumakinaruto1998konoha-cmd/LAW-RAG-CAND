from __future__ import annotations

import io
import sys
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from law_rag.ingestion.errors import IdempotencyConflictError, InvalidTransitionError, UnsupportedFileError, UploadTooLargeError, UploadValidationError
from law_rag.ingestion.models import IngestionJob, JobStatus
from law_rag.ingestion.service import IngestionService
from law_rag.ingestion.storage import FileBlobStore
from law_rag.ingestion.validation import validate_upload


def docx_bytes() -> bytes:
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return result.getvalue()


def pdf_bytes(body: bytes = b"fixture") -> bytes:
    return b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n" + body + b"\nstartxref\n0\n%%EOF"


class MemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, IngestionJob] = {}
        self.request_keys: dict[str, tuple[str, str]] = {}

    def find_by_idempotency_key(self, key: str) -> IngestionJob | None:
        record = self.request_keys.get(key)
        return self.jobs.get(record[1]) if record else None

    def find_by_sha256(self, sha256: str) -> IngestionJob | None:
        return next((job for job in self.jobs.values() if job.sha256 == sha256), None)

    def register_idempotency(self, key: str, sha256: str, job_id: str) -> IngestionJob:
        if key in self.request_keys and self.request_keys[key][0] != sha256:
            raise IdempotencyConflictError("key conflict")
        self.request_keys[key] = (sha256, job_id)
        return self.jobs[job_id]

    def get(self, job_id: str) -> IngestionJob | None:
        return self.jobs.get(job_id)

    def insert(self, job: IngestionJob) -> IngestionJob:
        self.jobs[job.job_id] = job
        self.request_keys[job.idempotency_key] = (job.sha256, job.job_id)
        return job

    def transition(self, job_id: str, status: JobStatus, *, error_code: str | None = None) -> IngestionJob:
        from dataclasses import replace
        job = replace(self.jobs[job_id], status=status, error_code=error_code)
        self.jobs[job_id] = job
        return job

    def retry(self, job_id: str) -> IngestionJob:
        from dataclasses import replace
        job = replace(self.jobs[job_id], status=JobStatus.QUEUED, attempt=self.jobs[job_id].attempt + 1, error_code=None)
        self.jobs[job_id] = job
        return job


class MemoryAudit:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def record(self, **event: str) -> None:
        self.events.append(event)


class UploadValidationTests(unittest.TestCase):
    def test_accepts_pdf_and_calculates_sha256(self) -> None:
        import hashlib
        content = pdf_bytes()
        upload = validate_upload("law.PDF", io.BytesIO(content))
        self.assertEqual(upload.media_type, "application/pdf")
        self.assertEqual(upload.sha256, hashlib.sha256(content).hexdigest())

    def test_accepts_docx_container(self) -> None:
        upload = validate_upload("report.docx", io.BytesIO(docx_bytes()))
        self.assertIn("wordprocessingml", upload.media_type)

    def test_accepts_png_and_jpeg_headers_with_dimensions(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 1, 1) + b"\x08\x02\x00\x00\x00"
        jpeg = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x03\x01\x11\x00\xff\xd9"
        self.assertEqual(validate_upload("photo.png", io.BytesIO(png)).media_type, "image/png")
        self.assertEqual(validate_upload("photo.jpg", io.BytesIO(jpeg)).media_type, "image/jpeg")

    def test_rejects_image_over_pixel_limit(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 5000, 5000) + b"\x08\x02\x00\x00\x00"
        with self.assertRaises(UploadValidationError):
            validate_upload("large.png", io.BytesIO(png))

    def test_rejects_mime_extension_mismatch(self) -> None:
        with self.assertRaises(UnsupportedFileError):
            validate_upload("fake.pdf", io.BytesIO(b"plain text"))

    def test_rejects_truncated_pdf(self) -> None:
        with self.assertRaises(UnsupportedFileError):
            validate_upload("broken.pdf", io.BytesIO(b"%PDF-1.7 truncated"))

    def test_rejects_invalid_utf8(self) -> None:
        with self.assertRaises(UploadValidationError):
            validate_upload("bad.txt", io.BytesIO(b"\xff"))

    def test_rejects_oversized_content_while_reading(self) -> None:
        with self.assertRaises(UploadTooLargeError):
            validate_upload("big.txt", io.BytesIO(b"12345"), max_bytes=4)

    def test_rejects_traversal_extension_that_is_not_supported(self) -> None:
        with self.assertRaises(UnsupportedFileError):
            validate_upload("../../evil.exe", io.BytesIO(b"MZ"))


class IngestionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = MemoryRepository()
        self.audit = MemoryAudit()
        self.store = FileBlobStore(Path(self.temp_dir.name))
        self.service = IngestionService(repository=self.repo, blob_store=self.store, audit=self.audit)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def upload(self, key: str, content: bytes | None = None):
        content = content if content is not None else pdf_bytes()
        return self.service.upload(filename="../../source.pdf", stream=io.BytesIO(content), idempotency_key=key, uploader_id="user-1", trace_id="trace-1")

    def test_upload_stores_blob_and_queues_job(self) -> None:
        receipt = self.upload("request-1")
        self.assertEqual(receipt.job.status, JobStatus.QUEUED)
        self.assertTrue(self.store.path_for(receipt.job.storage_key).exists())
        self.assertEqual(receipt.job.original_filename, "../../source.pdf")
        self.assertEqual(self.audit.events[0]["outcome"], "queued")

    def test_same_idempotency_key_replays_without_new_job(self) -> None:
        first = self.upload("request-1")
        second = self.upload("request-1")
        self.assertEqual(first.job.job_id, second.job.job_id)
        self.assertTrue(second.duplicate)
        self.assertEqual(len(self.repo.jobs), 1)

    def test_reused_idempotency_key_with_different_content_conflicts(self) -> None:
        self.upload("request-1")
        with self.assertRaises(IdempotencyConflictError):
            self.upload("request-1", pdf_bytes(b"different"))

    def test_exact_hash_duplicate_is_not_enqueued_twice(self) -> None:
        first = self.upload("request-1")
        second = self.upload("request-2")
        self.assertEqual(first.job.job_id, second.job.job_id)
        self.assertTrue(second.duplicate)
        self.assertEqual(len(self.repo.jobs), 1)
        with self.assertRaises(IdempotencyConflictError):
            self.upload("request-2", pdf_bytes(b"different"))

    def test_transition_and_retry_are_guarded_and_audited(self) -> None:
        job = self.upload("request-1").job
        with self.assertRaises(InvalidTransitionError):
            self.service.transition(job.job_id, JobStatus.INDEXED)
        failed = self.service.transition(job.job_id, JobStatus.FAILED, error_code="EXTRACTION_FAILED")
        retried = self.service.retry(job.job_id)
        self.assertEqual(failed.status, JobStatus.FAILED)
        self.assertEqual(retried.status, JobStatus.QUEUED)
        self.assertEqual(retried.attempt, 1)


if __name__ == "__main__":
    unittest.main()
