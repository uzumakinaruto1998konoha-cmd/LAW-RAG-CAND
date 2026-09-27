"""Domain models for PHASE 4 RAG: conversations, messages, citations, and evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum


class MessageRole(str, Enum):
    """Role of a message in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class CitationStatus(str, Enum):
    """Citation validation status."""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class Conversation:
    """User conversation thread for legal Q&A."""

    conversation_id: str
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    is_archived: bool = False

    def __post_init__(self) -> None:
        if not self.conversation_id:
            raise ValueError("Conversation ID required")

    @classmethod
    def new(
        cls,
        *,
        conversation_id: str,
        user_id: str,
        title: str | None = None,
    ) -> Conversation:
        now = datetime.now(timezone.utc)
        return cls(
            conversation_id=conversation_id,
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
        )


@dataclass(frozen=True, slots=True)
class Message:
    """Individual message in a conversation."""

    message_id: str
    conversation_id: str
    role: MessageRole
    content: str
    trace_id: str | None
    as_of_date: date | None
    insufficient_evidence: bool
    created_at: datetime
    metadata: dict | None = None

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Message content cannot be empty")

    @property
    def is_user_message(self) -> bool:
        return self.role is MessageRole.USER

    @property
    def is_assistant_message(self) -> bool:
        return self.role is MessageRole.ASSISTANT

    @classmethod
    def user_message(
        cls,
        *,
        message_id: str,
        conversation_id: str,
        content: str,
        as_of_date: date | None = None,
    ) -> Message:
        return cls(
            message_id=message_id,
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            trace_id=None,
            as_of_date=as_of_date,
            insufficient_evidence=False,
            created_at=datetime.now(timezone.utc),
        )

    @classmethod
    def assistant_message(
        cls,
        *,
        message_id: str,
        conversation_id: str,
        content: str,
        trace_id: str,
        as_of_date: date | None,
        insufficient_evidence: bool = False,
        metadata: dict | None = None,
    ) -> Message:
        return cls(
            message_id=message_id,
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            trace_id=trace_id,
            as_of_date=as_of_date,
            insufficient_evidence=insufficient_evidence,
            created_at=datetime.now(timezone.utc),
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class Evidence:
    """Retrieved evidence used to ground an answer."""

    evidence_id: str
    chunk_id: str
    version_id: str
    document_number: str | None
    document_title: str
    structural_path: str
    content: str
    page_start: int | None
    page_end: int | None
    score: float
    is_verified: bool
    validity_status: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Evidence score must be between 0 and 1")

    @property
    def has_page_location(self) -> bool:
        return self.page_start is not None


@dataclass(frozen=True, slots=True)
class Citation:
    """Citation linking answer to evidence source."""

    citation_id: str
    message_id: str
    evidence_id: str
    chunk_id: str
    version_id: str
    document_number: str | None
    document_title: str
    issuing_body: str | None
    structural_path: str
    excerpt: str
    page_start: int | None
    page_end: int | None
    source_spans: tuple[str, ...]
    viewer_url: str | None
    validity_status: str
    as_of_date: date | None
    status: CitationStatus
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.excerpt.strip():
            raise ValueError("Citation excerpt cannot be empty")

    @property
    def is_valid(self) -> bool:
        return self.status is CitationStatus.VALID

    @classmethod
    def new(
        cls,
        *,
        citation_id: str,
        message_id: str,
        evidence_id: str,
        chunk_id: str,
        version_id: str,
        document_number: str | None,
        document_title: str,
        issuing_body: str | None,
        structural_path: str,
        excerpt: str,
        page_start: int | None,
        page_end: int | None,
        source_spans: tuple[str, ...],
        viewer_url: str | None,
        validity_status: str,
        as_of_date: date | None,
    ) -> Citation:
        return cls(
            citation_id=citation_id,
            message_id=message_id,
            evidence_id=evidence_id,
            chunk_id=chunk_id,
            version_id=version_id,
            document_number=document_number,
            document_title=document_title,
            issuing_body=issuing_body,
            structural_path=structural_path,
            excerpt=excerpt,
            page_start=page_start,
            page_end=page_end,
            source_spans=source_spans,
            viewer_url=viewer_url,
            validity_status=validity_status,
            as_of_date=as_of_date,
            status=CitationStatus.VALID,
            created_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True, slots=True)
class RAGResponse:
    """Complete RAG answer with evidence and citations."""

    message_id: str
    answer: str
    evidence: tuple[Evidence, ...]
    citations: tuple[Citation, ...]
    warnings: tuple[str, ...]
    as_of_date: date | None
    insufficient_evidence: bool
    trace_id: str

    def __post_init__(self) -> None:
        if self.insufficient_evidence and not self.answer:
            raise ValueError("Insufficient evidence response must have explanation")

    @property
    def has_evidence(self) -> bool:
        return len(self.evidence) > 0

    @property
    def has_citations(self) -> bool:
        return len(self.citations) > 0

    @property
    def valid_citation_count(self) -> int:
        return sum(1 for c in self.citations if c.is_valid)
