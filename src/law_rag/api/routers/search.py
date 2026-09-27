"""Hybrid search endpoint (docs/11 retrieval/chat group)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from law_rag.ingestion.knowledge_models import AppUser

from ..container import ApiContainer, SearchOutcome
from ..dependencies import get_container, require_permission
from ..schemas import (
    ErrorEnvelope,
    SearchRequest,
    SearchResponse,
    SearchResultModel,
)

router = APIRouter(tags=["retrieval"])

_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorEnvelope, "description": "Chưa xác thực"},
    403: {"model": ErrorEnvelope, "description": "Không đủ quyền"},
    422: {"model": ErrorEnvelope, "description": "Dữ liệu yêu cầu không hợp lệ"},
}


def snippet(content: str, limit: int = 400) -> str:
    """Excerpt that keeps the source wording and only truncates with an ellipsis."""
    text = " ".join(content.split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def build_search_results(
    container: ApiContainer, user: AppUser, outcome: SearchOutcome
) -> list[SearchResultModel]:
    """Map retrieval results to API models, re-checking ACL for every chunk."""
    results: list[SearchResultModel] = []
    for result in outcome.results:
        chunk = container.chunk_for(user, result.chunk_id)
        metadata = container.metadata_for_version(chunk.version_id)
        if metadata is None:  # defensive: never emit results without metadata
            continue
        results.append(
            SearchResultModel(
                rank=result.rank,
                chunk_id=chunk.chunk_id,
                version_id=chunk.version_id,
                document_id=metadata.document_id,
                document_number=metadata.document_number,
                document_title=metadata.title,
                issuing_body=metadata.issuing_body,
                structural_path=chunk.structural_path,
                heading=chunk.heading,
                snippet=snippet(chunk.content),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                score=result.score,
                validity_status=metadata.validity_status.value,
                is_verified=metadata.is_verified,
            )
        )
    return results


@router.post(
    "/search",
    response_model=SearchResponse,
    responses=_ERRORS,
    summary="Search the knowledge base with hybrid retrieval",
)
def search(
    payload: SearchRequest,
    user: Annotated[AppUser, Depends(require_permission("search.query"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> SearchResponse:
    """Run ACL-filtered hybrid search and return ranked excerpts with a trace id."""
    outcome = container.search(
        user=user,
        query=payload.query,
        top_k=payload.top_k,
        query_type=payload.query_type,
        as_of_date=payload.as_of_date,
        filters=payload.filters,
    )
    results = build_search_results(container, user, outcome)
    return SearchResponse(
        query=payload.query,
        trace_id=outcome.trace.trace_id,
        query_type=outcome.trace.query_type.value,
        as_of_date=outcome.trace.as_of_date,
        result_count=len(results),
        latency_ms=outcome.trace.latency_ms,
        results=results,
        warnings=list(outcome.warnings),
    )
