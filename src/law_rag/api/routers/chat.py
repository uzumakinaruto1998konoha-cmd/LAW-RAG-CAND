"""Chat and conversation endpoints (docs/11 section 3)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from law_rag.ingestion.knowledge_models import AppUser
from law_rag.rag.models import Citation, Conversation, Evidence, Message, RAGResponse

from ..container import ApiContainer, ChatOutcome
from ..dependencies import get_container, require_permission
from ..schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationModel,
    ErrorEnvelope,
    EvidenceModel,
    CitationModel,
    MessageModel,
)

router = APIRouter(tags=["chat"])

_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorEnvelope, "description": "Chưa xác thực"},
    403: {"model": ErrorEnvelope, "description": "Không đủ quyền"},
    404: {"model": ErrorEnvelope, "description": "Hội thoại không tồn tại hoặc không thuộc người gọi"},
    422: {"model": ErrorEnvelope, "description": "Dữ liệu yêu cầu không hợp lệ"},
}


def build_evidence(evidence: tuple[Evidence, ...]) -> list[EvidenceModel]:
    return [
        EvidenceModel(
            evidence_id=item.evidence_id,
            chunk_id=item.chunk_id,
            version_id=item.version_id,
            document_number=item.document_number,
            document_title=item.document_title,
            structural_path=item.structural_path,
            excerpt=item.content,
            page_start=item.page_start,
            page_end=item.page_end,
            score=item.score,
            is_verified=item.is_verified,
            validity_status=item.validity_status,
        )
        for item in evidence
    ]


def build_citations(citations: tuple[Citation, ...]) -> list[CitationModel]:
    return [
        CitationModel(
            citation_id=item.citation_id,
            message_id=item.message_id,
            evidence_id=item.evidence_id,
            chunk_id=item.chunk_id,
            version_id=item.version_id,
            document_number=item.document_number,
            document_title=item.document_title,
            issuing_body=item.issuing_body,
            structural_path=item.structural_path,
            excerpt=item.excerpt,
            page_start=item.page_start,
            page_end=item.page_end,
            viewer_url=item.viewer_url,
            validity_status=item.validity_status,
            as_of_date=item.as_of_date,
            status=item.status.value,
        )
        for item in citations
    ]


def build_conversation(conversation: Conversation) -> ConversationModel:
    return ConversationModel(
        conversation_id=conversation.conversation_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        is_archived=conversation.is_archived,
    )


def build_message(message: Message) -> MessageModel:
    return MessageModel(
        message_id=message.message_id,
        conversation_id=message.conversation_id,
        role=message.role.value,
        content=message.content,
        trace_id=message.trace_id,
        as_of_date=message.as_of_date,
        insufficient_evidence=message.insufficient_evidence,
        created_at=message.created_at,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses=_ERRORS,
    summary="Ask a grounded legal question",
)
def chat(
    payload: ChatRequest,
    user: Annotated[AppUser, Depends(require_permission("chat.query"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> ChatResponse:
    """Answer using retrieved evidence only; citations are generated server-side."""
    outcome: ChatOutcome = container.chat(
        user=user,
        question=payload.question,
        conversation_id=payload.conversation_id,
        as_of_date=payload.as_of_date,
        top_k=payload.top_k,
        query_type=payload.query_type,
        filters=payload.filters,
    )
    response: RAGResponse = outcome.response
    return ChatResponse(
        message_id=response.message_id,
        conversation_id=outcome.conversation.conversation_id,
        answer=response.answer,
        insufficient_evidence=response.insufficient_evidence,
        as_of_date=response.as_of_date,
        citations=build_citations(response.citations),
        evidence=build_evidence(response.evidence),
        warnings=list(outcome.warnings),
        trace_id=response.trace_id,
    )


@router.post(
    "/conversations",
    response_model=ConversationModel,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
    summary="Create a conversation",
)
def create_conversation(
    payload: ConversationCreateRequest,
    user: Annotated[AppUser, Depends(require_permission("chat.query"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> ConversationModel:
    return build_conversation(container.create_conversation(user=user, title=payload.title))


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    responses=_ERRORS,
    summary="Read a conversation with its messages",
)
def get_conversation(
    conversation_id: str,
    user: Annotated[AppUser, Depends(require_permission("chat.query"))],
    container: Annotated[ApiContainer, Depends(get_container)],
) -> ConversationDetailResponse:
    conversation = container.conversation_for(user=user, conversation_id=conversation_id)
    messages = container.messages_for(user=user, conversation_id=conversation_id)
    return ConversationDetailResponse(
        conversation=build_conversation(conversation),
        messages=[build_message(message) for message in messages],
    )
