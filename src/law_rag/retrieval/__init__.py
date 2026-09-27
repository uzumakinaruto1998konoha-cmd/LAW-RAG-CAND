"""PHASE 3 retrieval package: chunking, indexing, hybrid search, and ranking."""

from .chunking import ChunkingService, chunk_legal_document
from .models import (
    Chunk,
    ChunkSet,
    IndexManifest,
    IndexStatus,
    IndexType,
    QueryType,
    RetrievalMethod,
    RetrievalResult,
    RetrievalTrace,
)
from .search import (
    BM25Index,
    DocumentMetadata,
    LegalReranker,
    RetrievalService,
    VectorSearchAdapter,
    reciprocal_rank_fusion,
    weighted_score_fusion,
)

__all__ = [
    "BM25Index",
    "Chunk",
    "ChunkSet",
    "ChunkingService",
    "DocumentMetadata",
    "IndexManifest",
    "IndexStatus",
    "IndexType",
    "LegalReranker",
    "QueryType",
    "RetrievalMethod",
    "RetrievalResult",
    "RetrievalService",
    "RetrievalTrace",
    "VectorSearchAdapter",
    "chunk_legal_document",
    "reciprocal_rank_fusion",
    "weighted_score_fusion",
]

