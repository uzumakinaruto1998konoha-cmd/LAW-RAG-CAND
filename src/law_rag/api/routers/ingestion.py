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

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, status

from law_rag.ingestion.knowledge_models import AppUser
from law_rag.ingestion.legal_review import ReviewAction, ReviewDecision, ReviewItemKind

from ..container import ApiContainer
from ..dependencies import get_container, get_current_user, get_request_id, require_permission
from ..errors import (
    FieldError,
    PayloadTooLargeApiError,
    ServiceUnavailableApiError,
    ValidationApiError,
)
from ..schemas import (
    ApprovalResponse,
    ApproveRequest,
    ErrorEnvelope,
    JobStatusResponse,
    MetadataAssertionModel,
    NodePreviewModel,
    ReviewDecisionRequest,
    ReviewStateResponse,
    ReviewTaskModel,
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
    background: BackgroundTasks,
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
    warnings: list[str] = []
    if receipt.duplicate:
        warnings.append("Bản tải lên trùng nội dung đã có; job hiện tại trỏ tới job gốc.")
    elif container.pipeline is None:
        warnings.append(
            "Pipeline ingestion chưa được cấu hình: tệp đã lưu nhưng chưa được trích xuất/parse."
        )
    else:
        # Extraction + parsing run after the response so uploads stay fast; failures
        # are recorded on the job (stable error code) and reported by /jobs/{id}.
        background.add_task(container.process_job_in_background, job_id=receipt.job.job_id)
        warnings.append("Tệp đã được xếp hàng trích xuất và phân tích cấu trúc pháp lý.")
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
        warnings=warnings,
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


def build_review_state(state) -> ReviewStateResponse:
    """Map the pipeline's review state onto the API contract."""
    return ReviewStateResponse(
        job_id=state.job.job_id,
        status=state.job.status.value,
        original_filename=state.original_filename,
        media_type=state.media_type,
        size_bytes=state.size_bytes,
        sha256=state.sha256,
        page_count=state.job.page_count,
        review_required=state.job.review_required,
        tasks=[
            ReviewTaskModel(
                item_kind=task.item_kind.value,
                item_id=task.item_id,
                summary=task.summary,
                confidence=task.confidence,
            )
            for task in state.job.tasks
        ],
        warnings=list(state.job.warnings),
        metadata=[
            MetadataAssertionModel(
                assertion_id=item.assertion_id,
                field=item.field.value,
                value=item.value,
                confidence=item.confidence,
                required=item.required,
                verification=item.verification.value,
                is_pending=item.is_pending,
                source_locator=item.provenance.source_locator,
                page_number=item.provenance.page_number,
            )
            for item in state.metadata
        ],
        preview=[
            NodePreviewModel(
                node_id=node.node_id,
                kind=node.kind.value,
                label=node.label,
                ordinal=node.ordinal,
                title=node.title,
                page_numbers=list(node.page_numbers),
                excerpt=node.content[:600],
            )
            for node in state.preview
        ],
        node_count=state.node_count,
        relation_count=state.relation_count,
        approved_version_id=state.approved_version_id,
    )


def _to_decisions(payload: ReviewDecisionRequest, reviewer_id: str) -> tuple[ReviewDecision, ...]:
    return tuple(
        ReviewDecision(
            item_kind=ReviewItemKind(decision.item_kind),
            item_id=decision.item_id,
            action=ReviewAction(decision.action),
            reviewer_id=reviewer_id,
            value=decision.value,
            target_document_number=decision.target_document_number,
            target_scope_label=decision.target_scope_label,
            comment=decision.comment,
        )
        for decision in payload.decisions
    )


@router.get(
    "/jobs/{job_id}/review",
    response_model=ReviewStateResponse,
    responses=_ERRORS,
    summary="Review state: extraction preview, metadata and pending items",
)
def job_review_state(
    job_id: str,
    user: Annotated[AppUser, Depends(get_current_user)],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> ReviewStateResponse:
    """Uploader sees their own job; reviewers/auditors see all jobs they are entitled to."""
    return build_review_state(container.review_state_for(user=user, job_id=job_id))


@router.post(
    "/jobs/{job_id}/review",
    response_model=ReviewStateResponse,
    responses=_ERRORS,
    summary="Record reviewer decisions for a parsed job",
)
def submit_job_review(
    job_id: str,
    payload: ReviewDecisionRequest,
    user: Annotated[AppUser, Depends(require_permission("document.edit_metadata"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> ReviewStateResponse:
    """Accept, correct or reject pending metadata, nodes and relation candidates."""
    state = container.submit_review(
        user=user, job_id=job_id, decisions=_to_decisions(payload, user.user_id)
    )
    return build_review_state(state)


@router.post(
    "/jobs/{job_id}/approve",
    response_model=ApprovalResponse,
    responses=_ERRORS,
    summary="Approve, release and index a reviewed document",
)
def approve_job(
    job_id: str,
    payload: ApproveRequest,
    user: Annotated[AppUser, Depends(require_permission("document.approve"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> ApprovalResponse:
    """Runs the release + indexing chain; the document becomes searchable when it returns."""
    released = container.approve_job(
        user=user,
        job_id=job_id,
        collection_id=payload.collection_id,
        acknowledged_warnings=tuple(payload.acknowledged_warnings),
    )
    LOGGER.info(
        "api.approve job_id=%s version_id=%s chunks=%d user=%s",
        released.job_id,
        released.version_id,
        released.chunk_count,
        user.user_id,
    )
    return ApprovalResponse(
        job_id=released.job_id,
        document_id=released.document_id,
        version_id=released.version_id,
        status=released.status.value,
        chunk_count=released.chunk_count,
        validity_status=released.validity_status.value,
        warnings=list(released.warnings),
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobStatusResponse,
    responses=_ERRORS,
    summary="Retry extraction and parsing for a failed job",
)
def retry_job(
    job_id: str,
    background: BackgroundTasks,
    user: Annotated[AppUser, Depends(require_permission("document.upload"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> JobStatusResponse:
    """Only failed jobs may be retried (docs/05); the job is re-queued and processed again."""
    job = container.job_for(user=user, job_id=job_id)
    if container.ingestion_service is None:
        raise ServiceUnavailableApiError(
            "Ingestion pipeline chưa được cấu hình trong môi trường này."
        )
    retried = container.ingestion_service.retry(job.job_id)
    background.add_task(container.process_job_in_background, job_id=retried.job_id)
    return JobStatusResponse(
        job_id=retried.job_id,
        status=retried.status.value,
        attempt=retried.attempt,
        error_code=retried.error_code,
        original_filename=retried.original_filename,
        media_type=retried.media_type,
        size_bytes=retried.size_bytes,
        sha256=retried.sha256,
        uploader_id=retried.uploader_id,
        trace_id=retried.trace_id,
        created_at=retried.created_at,
        updated_at=retried.updated_at,
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
