"""Ingestion endpoints: upload, job status, and retrieval traces.

Upload transport is the raw request body: the original file name travels as the
``filename`` query parameter and ``Idempotency-Key`` is required. This keeps the
endpoint dependency-free and keeps the blob immutable (storage keys are derived
from the content hash, never from the uploaded name).
"""

from __future__ import annotations

import io
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status

from law_rag.ingestion.knowledge_models import AppUser

from ..container import ApiContainer
from ..dependencies import get_container, get_current_user, get_request_id, require_permission
from ..errors import (
    FieldError,
    PayloadTooLargeApiError,
    ServiceUnavailableApiError,
    ValidationApiError,
)
from ..schemas import (
    ErrorEnvelope,
    JobStatusResponse,
    TraceResponse,
    TraceResultModel,
    UploadResponse,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])

_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorEnvelope, "description": "Chưa xác thực"},
    403: {"model": ErrorEnvelope, "description": "Không đủ quyền"},
    404: {"model": ErrorEnvelope, "description": "Job không tồn tại hoặc ngoài quyền đọc"},
    409: {"model": ErrorEnvelope, "description": "Xung đột idempotency hoặc trạng thái"},
    413: {"model": ErrorEnvelope, "description": "Tệp vượt giới hạn"},
    415: {"model": ErrorEnvelope, "description": "Loại tệp không được hỗ trợ"},
    422: {"model": ErrorEnvelope, "description": "Dữ liệu yêu cầu không hợp lệ"},
    503: {"model": ErrorEnvelope, "description": "Pipeline ingestion chưa được cấu hình"},
}


@router.post(
    "/documents/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERRORS,
    summary="Upload a legal document for ingestion",
)
async def upload_document(
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    user: Annotated[AppUser, Depends(require_permission("document.upload"))],
    container: Annotated[ApiContainer, Depends(get_container)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    source: Annotated[str | None, Query(max_length=200)] = None,
) -> UploadResponse:
    """Validate and queue an upload; duplicates are reported, never re-ingested."""
    if container.ingestion_service is None:
        raise ServiceUnavailableApiError("Ingestion pipeline chưa được cấu hình trong môi trường này.")
    if not idempotency_key:
        raise ValidationApiError(
            "Thiếu header Idempotency-Key.",
            field_errors=(FieldError(field="Idempotency-Key", message="Bắt buộc có."),),
        )

    max_bytes = container.ingestion_service.max_bytes
    buffer = io.BytesIO()
    total = 0
    async for part in request.stream():
        total += len(part)
        if total > max_bytes:
            raise PayloadTooLargeApiError(f"Tệp vượt giới hạn {max_bytes} byte của ingestion v1.")
        buffer.write(part)
    if total == 0:
        raise ValidationApiError(
            "Nội dung tệp rỗng.",
            field_errors=(FieldError(field="body", message="Tệp rỗng."),),
        )
    buffer.seek(0)

    receipt = container.upload(
        user=user,
        filename=filename,
        stream=buffer,
        idempotency_key=idempotency_key,
        source=source,
        trace_id=get_request_id(request),
    )
    LOGGER.info(
        "api.upload job_id=%s user=%s duplicate=%s trace_id=%s",
        receipt.job.job_id,
        user.user_id,
        receipt.duplicate,
        receipt.job.trace_id,
    )
    return UploadResponse(
        job_id=receipt.job.job_id,
        status=receipt.job.status.value,
        document_id=None,
        version_id=None,
        duplicate_match=receipt.duplicate,
        original_filename=receipt.job.original_filename,
        media_type=receipt.job.media_type,
        size_bytes=receipt.job.size_bytes,
        sha256=receipt.job.sha256,
        trace_id=receipt.job.trace_id,
        warnings=["Bản tải lên trùng nội dung đã có; job hiện tại trỏ tới job gốc."]
        if receipt.duplicate
        else [],
    )



@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    responses=_ERRORS,
    summary="Read ingestion job status",
)
def job_status(
    job_id: str,
    user: Annotated[AppUser, Depends(get_current_user)],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> JobStatusResponse:
    """Uploader or audit role only; other callers get 404 to avoid leaking jobs."""
    container.authorize_any(user, ("document.upload", "audit.view"))
    job = container.job_for(user=user, job_id=job_id)
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        attempt=job.attempt,
        error_code=job.error_code,
        original_filename=job.original_filename,
        media_type=job.media_type,
        size_bytes=job.size_bytes,
        sha256=job.sha256,
        uploader_id=job.uploader_id,
        trace_id=job.trace_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/traces/{trace_id}",
    response_model=TraceResponse,
    responses=_ERRORS,
    summary="Read a retrieval trace for audit",
)
def trace_detail(
    trace_id: str,
    user: Annotated[AppUser, Depends(get_current_user)],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> TraceResponse:
    """Trace owner or audit role only; results are chunk ids, never raw content."""
    trace, results = container.trace_for(user=user, trace_id=trace_id)
    return TraceResponse(
        trace_id=trace.trace_id,
        user_id=trace.user_id,
        query=trace.query,
        query_type=trace.query_type.value,
        as_of_date=trace.as_of_date,
        filters=trace.filters,
        manifest_id=trace.manifest_id,
        result_count=trace.result_count,
        latency_ms=trace.latency_ms,
        created_at=trace.created_at,
        results=[
            TraceResultModel(
                rank=item.rank,
                chunk_id=item.chunk_id,
                score=item.score,
                retrieval_method=item.retrieval_method.value,
            )
            for item in results
        ],
    )
