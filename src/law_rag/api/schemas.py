"""Request/response contracts for the REST API (docs/11 sections 3 and 5).

Dates and timestamps are ISO-8601; every collection response carries ACL-filtered
content only, so these models never receive unauthorized material.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QueryTypeName = Literal["hybrid", "lexical", "semantic"]

_FORBID = ConfigDict(extra="forbid")


class FieldErrorModel(BaseModel):
    field: str
    message: str
    code: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    field_errors: list[FieldErrorModel] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    """Standard error envelope (docs/11 section 4)."""

    error: ErrorDetail


class ReviewTaskModel(BaseModel):
    """One item a reviewer must resolve before approval (docs/05 review gate)."""

    item_kind: str
    item_id: str
    summary: str
    confidence: float | None = None


class MetadataAssertionModel(BaseModel):
    assertion_id: str
    field: str
    value: str
    confidence: float
    required: bool
    verification: str
    is_pending: bool
    source_locator: str
    page_number: int | None = None


class NodePreviewModel(BaseModel):
    """Parsed hierarchy node preview used as the extraction preview in the UI."""

    node_id: str
    kind: str
    label: str
    ordinal: str
    title: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    excerpt: str


class ReviewStateResponse(BaseModel):
    """Reviewer view of an ingested job after extraction and parsing."""

    job_id: str
    status: str
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    page_count: int | None = None
    review_required: bool
    tasks: list[ReviewTaskModel] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: list[MetadataAssertionModel] = Field(default_factory=list)
    preview: list[NodePreviewModel] = Field(default_factory=list)
    node_count: int
    relation_count: int
    approved_version_id: str | None = None


class ReviewDecisionModel(BaseModel):
    model_config = _FORBID

    item_kind: Literal["metadata", "node", "relation"]
    item_id: str = Field(min_length=1, max_length=200)
    action: Literal["accept", "correct", "reject"]
    value: str | None = Field(default=None, max_length=2000)
    target_document_number: str | None = Field(default=None, max_length=200)
    target_scope_label: str | None = Field(default=None, max_length=200)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewDecisionRequest(BaseModel):
    model_config = _FORBID

    decisions: list[ReviewDecisionModel] = Field(min_length=1, max_length=200)


class ApproveRequest(BaseModel):
    """Approve a reviewed job and release it into one collection."""

    model_config = _FORBID

    collection_id: str = Field(min_length=1, max_length=200)
    acknowledged_warnings: list[str] = Field(default_factory=list, max_length=100)


class ApprovalResponse(BaseModel):
    job_id: str
    document_id: str
    version_id: str
    status: str
    chunk_count: int
    validity_status: str
    warnings: list[str] = Field(default_factory=list)


class CollectionModel(BaseModel):
    collection_id: str
    name: str
    description: str | None = None
    is_public: bool
    access_level: str


class CollectionListResponse(BaseModel):
    count: int
    collections: list[CollectionModel] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    phase: str
    architecture_version: str


class ReadinessCheck(BaseModel):
    name: str
    status: Literal["ok", "degraded"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: list[ReadinessCheck]
    indexed_chunk_count: int
    indexed_version_count: int


class SearchRequest(BaseModel):
    model_config = _FORBID

    query: str = Field(min_length=1, max_length=2000)
    as_of_date: date | None = None
    filters: dict[str, str] | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    query_type: QueryTypeName = "hybrid"


class SearchResultModel(BaseModel):
    rank: int
    chunk_id: str
    version_id: str
    document_id: str
    document_number: str
    document_title: str
    issuing_body: str
    structural_path: str
    heading: str | None = None
    snippet: str
    page_start: int | None = None
    page_end: int | None = None
    score: float
    validity_status: str
    is_verified: bool


class SearchResponse(BaseModel):
    query: str
    trace_id: str
    query_type: str
    as_of_date: date | None = None
    result_count: int
    latency_ms: int | None = None
    results: list[SearchResultModel]
    warnings: list[str] = Field(default_factory=list)


class EvidenceModel(BaseModel):
    evidence_id: str
    chunk_id: str
    version_id: str
    document_number: str | None = None
    document_title: str
    structural_path: str
    excerpt: str
    page_start: int | None = None
    page_end: int | None = None
    score: float
    is_verified: bool
    validity_status: str


class CitationModel(BaseModel):
    citation_id: str
    message_id: str
    evidence_id: str
    chunk_id: str
    version_id: str
    document_number: str | None = None
    document_title: str
    issuing_body: str | None = None
    structural_path: str
    excerpt: str
    page_start: int | None = None
    page_end: int | None = None
    viewer_url: str | None = None
    validity_status: str
    as_of_date: date | None = None
    status: str


class ChatRequest(BaseModel):
    model_config = _FORBID

    question: str = Field(min_length=1, max_length=4000)
    as_of_date: date | None = None
    filters: dict[str, str] | None = None
    conversation_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    query_type: QueryTypeName = "hybrid"


class ConversationCreateRequest(BaseModel):
    model_config = _FORBID

    title: str | None = Field(default=None, max_length=200)


class ConversationModel(BaseModel):
    conversation_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    is_archived: bool


class MessageModel(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    trace_id: str | None = None
    as_of_date: date | None = None
    insufficient_evidence: bool
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation: ConversationModel
    messages: list[MessageModel]


class UserModel(BaseModel):
    user_id: str
    username: str
    display_name: str
    is_system: bool
    permissions: list[str]


class ChunkModel(BaseModel):
    chunk_id: str
    chunk_index: int
    structural_path: str
    heading: str | None = None
    node_kind: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    content: str
    token_count: int | None = None


class DocumentSummaryModel(BaseModel):
    document_id: str
    version_id: str
    document_number: str
    title: str
    issuing_body: str
    document_type: str
    issue_date: date
    effective_date: date | None = None
    expiry_date: date | None = None
    validity_status: str
    is_verified: bool
    collection_ids: list[str]
    chunk_count: int


class DocumentListResponse(BaseModel):
    count: int
    documents: list[DocumentSummaryModel]


class DocumentDetailResponse(BaseModel):
    document: DocumentSummaryModel
    chunks: list[ChunkModel]


class UploadResponse(BaseModel):
    """Upload acknowledgement (docs/11 section 3).

    ``document_id``/``version_id`` stay null until the version is approved and
    released into the knowledge base, so no unapproved content is addressable.
    """

    job_id: str
    status: str
    document_id: str | None = None
    version_id: str | None = None
    duplicate_match: bool
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    trace_id: str
    warnings: list[str] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    attempt: int
    error_code: str | None = None
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    uploader_id: str
    trace_id: str
    created_at: datetime
    updated_at: datetime


class TraceResultModel(BaseModel):
    rank: int
    chunk_id: str
    score: float
    retrieval_method: str


class TraceResponse(BaseModel):
    trace_id: str
    user_id: str
    query: str
    query_type: str
    as_of_date: date | None = None
    filters: dict | None = None
    manifest_id: str | None = None
    result_count: int
    latency_ms: int | None = None
    created_at: datetime
    results: list[TraceResultModel]


class ChatResponse(BaseModel):
    """Chat answer contract (docs/11 section 3)."""

    message_id: str
    conversation_id: str
    answer: str
    insufficient_evidence: bool
    as_of_date: date | None = None
    citations: list[CitationModel]
    evidence: list[EvidenceModel]
    warnings: list[str]
    trace_id: str
