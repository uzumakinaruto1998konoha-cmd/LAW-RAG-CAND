"""Stable API error model and exception mapping for the REST API (docs/11 section 4).

Rules enforced here:
- Machine-readable, stable error codes.
- Safe client-facing messages only: no stack traces, no secrets, no internal paths.
- 401 (not authenticated) and 403 (not allowed) stay distinct.
- Resources the caller may not read are reported as 404 so the API never leaks
  the existence of restricted documents (zero ACL leakage).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from law_rag.ingestion.authorization import (
    AccessDeniedError,
    AuthorizationError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from law_rag.ingestion.errors import (
    ExtractionError,
    IdempotencyConflictError,
    IngestionError,
    InvalidTransitionError,
    LegalParsingError,
    ReleaseError,
    ReviewIncompleteError,
    ReviewItemNotFoundError,
    StorageError,
    UnsupportedFileError,
    UploadTooLargeError,
    UploadValidationError,
)


@dataclass(frozen=True, slots=True)
class FieldError:
    """Single validation/field problem returned to the caller."""

    field: str
    message: str
    code: str = "INVALID_VALUE"


class ApiError(Exception):
    """Base API error carrying a stable code, HTTP status and safe message."""

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, *, field_errors: Sequence[FieldError] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.field_errors: tuple[FieldError, ...] = tuple(field_errors)


class AuthenticationRequiredError(ApiError):
    """No usable credentials were supplied."""

    status_code = 401
    code = "AUTHENTICATION_REQUIRED"


class AuthorizationDeniedApiError(ApiError):
    """Credentials are valid but the caller is not permitted."""

    status_code = 403
    code = "AUTHORIZATION_DENIED"


class ResourceNotFoundApiError(ApiError):
    """Resource is unknown or not readable by the caller."""

    status_code = 404
    code = "RESOURCE_NOT_FOUND"


class ConflictApiError(ApiError):
    """Request conflicts with current state (idempotency, transitions)."""

    status_code = 409
    code = "RESOURCE_CONFLICT"


class PayloadTooLargeApiError(ApiError):
    """Upload exceeds the configured v1 size limit."""

    status_code = 413
    code = "UPLOAD_TOO_LARGE"


class UnsupportedMediaTypeApiError(ApiError):
    """Upload type is not accepted by the v1 ingestion contract."""

    status_code = 415
    code = "UPLOAD_UNSUPPORTED"


class ValidationApiError(ApiError):
    """Payload failed validation."""

    status_code = 422
    code = "VALIDATION_FAILED"


class ServiceUnavailableApiError(ApiError):
    """A required subsystem is not wired in this deployment."""

    status_code = 503
    code = "SERVICE_UNAVAILABLE"


def classify_error(exc: Exception) -> ApiError | None:
    """Map a domain exception to an ApiError, or return None when unknown."""
    if isinstance(exc, ApiError):
        return exc
    if isinstance(exc, ResourceNotFoundError):
        return ResourceNotFoundApiError(str(exc))
    if isinstance(exc, (AccessDeniedError, PermissionDeniedError)):
        return AuthorizationDeniedApiError(str(exc))
    if isinstance(exc, AuthorizationError):
        return AuthorizationDeniedApiError(str(exc))
    if isinstance(exc, IdempotencyConflictError):
        return ConflictApiError(str(exc))
    if isinstance(exc, InvalidTransitionError):
        return ConflictApiError(str(exc))
    if isinstance(exc, UploadTooLargeError):
        return PayloadTooLargeApiError(str(exc))
    if isinstance(exc, UnsupportedFileError):
        return UnsupportedMediaTypeApiError(str(exc))
    if isinstance(exc, UploadValidationError):
        return ValidationApiError(str(exc))
    if isinstance(exc, ReviewItemNotFoundError):
        return ValidationApiError(str(exc))
    if isinstance(exc, (ReviewIncompleteError, ReleaseError)):
        return ConflictApiError(str(exc))
    if isinstance(exc, (ExtractionError, LegalParsingError)):
        return ValidationApiError(str(exc))
    if isinstance(exc, StorageError):
        return ApiError("Lưu trữ nội bộ gặp lỗi, vui lòng thử lại sau.")
    if isinstance(exc, IngestionError):
        return ApiError("Yêu cầu ingestion không xử lý được.")
    return None


def error_body(error: ApiError, request_id: str) -> dict[str, object]:
    """Build the standard error envelope returned to clients."""
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "request_id": request_id,
            "field_errors": [
                {"field": item.field, "message": item.message, "code": item.code}
                for item in error.field_errors
            ],
        }
    }
