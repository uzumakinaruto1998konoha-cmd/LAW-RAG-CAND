"""Secure, local-first document upload and ingestion job primitives."""

from .models import IngestionJob, JobStatus, UploadReceipt
from .extraction import ExtractionResult, SourceSpan, extract_document
from .ocr import TesseractOCR
from .service import IngestionService

__all__ = [
    "ExtractionResult", "IngestionJob", "IngestionService", "JobStatus",
    "SourceSpan", "TesseractOCR", "UploadReceipt", "extract_document",
]
