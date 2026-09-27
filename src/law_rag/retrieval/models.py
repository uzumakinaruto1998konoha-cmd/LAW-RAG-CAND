"""Domain models for PHASE 3 chunking, indexing, and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum


class IndexType(str, Enum):
    """Types of search indices."""
    LEXICAL = "lexical"
    VECTOR = "vector"
    HYBRID = "hybrid"


class IndexStatus(str, Enum):
    """Index build and lifecycle status."""
    BUILDING = "building"
    READY = "ready"
    ACTIVE = "active"
    FAILED = "failed"
    RETIRED = "retired"


class QueryType(str, Enum):
    """Query classification for retrieval."""
    SEMANTIC = "semantic"
    LEXICAL = "lexical"
    HYBRID = "hybrid"
    EXACT = "exact"


class RetrievalMethod(str, Enum):
    """Method used to retrieve chunks."""
    LEXICAL = "lexical"
    VECTOR = "vector"
    FUSION = "fusion"
    RERANKED = "reranked"


@dataclass(frozen=True, slots=True)
class ChunkSet:
    """Versioned collection of chunks from a document version."""

    chunk_set_id: str
    version_id: str
    chunker_version: str
    chunker_config_hash: str
    chunk_count: int
    created_at: datetime
    created_by: str
    is_active: bool = True

    def __post_init__(self) -> None:
        if self.chunk_count < 0:
            raise ValueError("Chunk count cannot be negative")
        if len(self.chunker_config_hash) != 64:
            raise ValueError("Config hash must be 64-character hex string")

    @classmethod
    def new(
        cls,
        *,
        chunk_set_id: str,
        version_id: str,
        chunker_version: str,
        chunker_config_hash: str,
        chunk_count: int,
        created_by: str,
    ) -> ChunkSet:
        return cls(
            chunk_set_id=chunk_set_id,
            version_id=version_id,
            chunker_version=chunker_version,
            chunker_config_hash=chunker_config_hash,
            chunk_count=chunk_count,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
        )


@dataclass(frozen=True, slots=True)
class Chunk:
    """Atomic retrieval unit preserving legal structure."""

    chunk_id: str
    chunk_set_id: str
    version_id: str
    node_id: str | None
    chunk_index: int
    content: str
    content_hash: str
    structural_path: str
    node_kind: str | None
    heading: str | None
    page_start: int | None
    page_end: int | None
    page_spans: tuple[str, ...]
    token_count: int | None
    created_at: datetime

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("Chunk index cannot be negative")
        if not self.content.strip():
            raise ValueError("Chunk content cannot be empty")
        if len(self.content_hash) != 64:
            raise ValueError("Content hash must be 64-character hex string")
        if not self.structural_path:
            raise ValueError("Structural path is required")

    @property
    def has_location(self) -> bool:
        """Check if chunk has page location."""
        return self.page_start is not None

    @classmethod
    def new(
        cls,
        *,
        chunk_id: str,
        chunk_set_id: str,
        version_id: str,
        node_id: str | None,
        chunk_index: int,
        content: str,
        content_hash: str,
        structural_path: str,
        node_kind: str | None = None,
        heading: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        page_spans: tuple[str, ...] = (),
        token_count: int | None = None,
    ) -> Chunk:
        return cls(
            chunk_id=chunk_id,
            chunk_set_id=chunk_set_id,
            version_id=version_id,
            node_id=node_id,
            chunk_index=chunk_index,
            content=content,
            content_hash=content_hash,
            structural_path=structural_path,
            node_kind=node_kind,
            heading=heading,
            page_start=page_start,
            page_end=page_end,
            page_spans=page_spans,
            token_count=token_count,
            created_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True, slots=True)
class IndexManifest:
    """Versioned search index with reproducible build."""

    manifest_id: str
    manifest_version: int
    index_type: IndexType
    status: IndexStatus
    pipeline_version: str
    embedding_model: str | None
    embedding_dimension: int | None
    lexical_analyzer: str | None
    chunk_set_count: int
    chunk_count: int
    document_count: int
    build_started_at: datetime | None
    build_completed_at: datetime | None
    activated_at: datetime | None
    retired_at: datetime | None
    created_by: str
    error_message: str | None = None
    config: dict | None = None

    def __post_init__(self) -> None:
        if self.status is IndexStatus.FAILED and not self.error_message:
            raise ValueError("Failed index requires error_message")
        if self.manifest_version <= 0:
            raise ValueError("Manifest version must be positive")

    @property
    def is_active(self) -> bool:
        """Check if manifest is currently active."""
        return self.status is IndexStatus.ACTIVE

    @property
    def is_building(self) -> bool:
        """Check if manifest is currently building."""
        return self.status is IndexStatus.BUILDING

    @classmethod
    def new(
        cls,
        *,
        manifest_id: str,
        manifest_version: int,
        index_type: IndexType,
        pipeline_version: str,
        created_by: str,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
        lexical_analyzer: str | None = None,
        config: dict | None = None,
    ) -> IndexManifest:
        return cls(
            manifest_id=manifest_id,
            manifest_version=manifest_version,
            index_type=index_type,
            status=IndexStatus.BUILDING,
            pipeline_version=pipeline_version,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            lexical_analyzer=lexical_analyzer,
            chunk_set_count=0,
            chunk_count=0,
            document_count=0,
            build_started_at=datetime.now(timezone.utc),
            build_completed_at=None,
            activated_at=None,
            retired_at=None,
            created_by=created_by,
            config=config,
        )


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    """Audit trail for search query and results."""

    trace_id: str
    user_id: str
    query: str
    query_type: QueryType
    as_of_date: date | None
    filters: dict | None
    manifest_id: str | None
    result_count: int
    latency_ms: int | None
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("Query cannot be empty")
        if self.result_count < 0:
            raise ValueError("Result count cannot be negative")

    @classmethod
    def new(
        cls,
        *,
        trace_id: str,
        user_id: str,
        query: str,
        query_type: QueryType,
        result_count: int,
        as_of_date: date | None = None,
        filters: dict | None = None,
        manifest_id: str | None = None,
        latency_ms: int | None = None,
    ) -> RetrievalTrace:
        return cls(
            trace_id=trace_id,
            user_id=user_id,
            query=query,
            query_type=query_type,
            as_of_date=as_of_date,
            filters=filters,
            manifest_id=manifest_id,
            result_count=result_count,
            latency_ms=latency_ms,
            created_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Individual chunk retrieved in response to a query."""

    result_id: int | None
    trace_id: str
    chunk_id: str
    rank: int
    score: float
    retrieval_method: RetrievalMethod

    def __post_init__(self) -> None:
        if self.rank <= 0:
            raise ValueError("Rank must be positive")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Score must be between 0 and 1")

    @classmethod
    def new(
        cls,
        *,
        trace_id: str,
        chunk_id: str,
        rank: int,
        score: float,
        retrieval_method: RetrievalMethod,
    ) -> RetrievalResult:
        return cls(
            result_id=None,
            trace_id=trace_id,
            chunk_id=chunk_id,
            rank=rank,
            score=score,
            retrieval_method=retrieval_method,
        )
