"""Stable, safe errors exposed by the ingestion boundary."""


class IngestionError(Exception):
    """Base error with a stable machine-readable code."""

    code = "INGESTION_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class UploadValidationError(IngestionError):
    code = "UPLOAD_INVALID"


class UploadTooLargeError(UploadValidationError):
    code = "UPLOAD_TOO_LARGE"


class UnsupportedFileError(UploadValidationError):
    code = "UPLOAD_UNSUPPORTED"


class IdempotencyConflictError(IngestionError):
    code = "IDEMPOTENCY_CONFLICT"


class InvalidTransitionError(IngestionError):
    code = "INVALID_JOB_TRANSITION"


class StorageError(IngestionError):
    code = "STORAGE_FAILURE"


class ExtractionError(IngestionError):
    code = "EXTRACTION_FAILURE"


class EncryptedDocumentError(ExtractionError):
    code = "DOCUMENT_ENCRYPTED"


class OCRUnavailableError(ExtractionError):
    code = "OCR_UNAVAILABLE"


class LegalParsingError(IngestionError):
    code = "LEGAL_PARSING_FAILURE"


class ReviewItemNotFoundError(IngestionError):
    code = "REVIEW_ITEM_NOT_FOUND"


class ReviewIncompleteError(IngestionError):
    code = "REVIEW_INCOMPLETE"


class ReleaseError(IngestionError):
    code = "RELEASE_FAILURE"
