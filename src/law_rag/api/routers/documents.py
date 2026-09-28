"""Knowledge base read endpoints (ACL-filtered documents, versions, chunks)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from law_rag.ingestion.knowledge_models import AppUser

from ..container import ApiContainer, DocumentRecord
from ..dependencies import get_container, get_current_user, require_permission
from ..schemas import (
    ChunkModel,
    CollectionListResponse,
    CollectionModel,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentSummaryModel,
    ErrorEnvelope,
)

router = APIRouter(tags=["knowledge"])

_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorEnvelope, "description": "Chưa xác thực"},
    403: {"model": ErrorEnvelope, "description": "Không đủ quyền"},
    404: {"model": ErrorEnvelope, "description": "Tài liệu không tồn tại hoặc ngoài quyền đọc"},
}


def build_document_summary(record: DocumentRecord) -> DocumentSummaryModel:
    metadata = record.metadata
    return DocumentSummaryModel(
        document_id=metadata.document_id,
        version_id=metadata.version_id,
        document_number=metadata.document_number,
        title=metadata.title,
        issuing_body=metadata.issuing_body,
        document_type=metadata.document_type,
        issue_date=metadata.issue_date,
        effective_date=metadata.effective_date,
        expiry_date=metadata.expiry_date,
        validity_status=metadata.validity_status.value,
        is_verified=metadata.is_verified,
        collection_ids=list(metadata.collection_ids),
        chunk_count=len(record.chunks),
    )


@router.get(
    "/collections",
    response_model=CollectionListResponse,
    responses=_ERRORS,
    summary="List collections the caller can read",
)
def list_collections(
    user: Annotated[AppUser, Depends(get_current_user)],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> CollectionListResponse:
    """Collection registry with the caller's effective access level (ACL-filtered)."""
    entries = container.collections_for(user)
    return CollectionListResponse(
        count=len(entries),
        collections=[
            CollectionModel(
                collection_id=collection.collection_id,
                name=collection.collection_name,
                description=collection.description,
                is_public=collection.is_public,
                access_level=level.value,
            )
            for collection, level in entries
        ],
    )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    responses=_ERRORS,
    summary="List readable documents",
)
def list_documents(
    user: Annotated[AppUser, Depends(require_permission("document.view"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> DocumentListResponse:
    """List only the document versions the caller is allowed to read."""
    records = container.document_records(user)
    return DocumentListResponse(
        count=len(records),
        documents=[build_document_summary(record) for record in records],
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    responses=_ERRORS,
    summary="Read a document version with its chunks",
)
def get_document(
    document_id: str,
    user: Annotated[AppUser, Depends(require_permission("document.view"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> DocumentDetailResponse:
    """Return a readable document version; unauthorized ids report 404."""
    record = container.document_record(user, document_id)
    return DocumentDetailResponse(
        document=build_document_summary(record),
        chunks=[
            ChunkModel(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                structural_path=chunk.structural_path,
                heading=chunk.heading,
                node_kind=chunk.node_kind,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                content=chunk.content,
                token_count=chunk.token_count,
            )
            for chunk in record.chunks
        ],
    )
