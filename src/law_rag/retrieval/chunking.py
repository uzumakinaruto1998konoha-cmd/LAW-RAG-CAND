"""Chunking service for PHASE 3: Generate retrieval chunks from legal nodes."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import TYPE_CHECKING

from law_rag.ingestion.legal_models import LegalNode, LegalParseResult, NodeKind
from law_rag.retrieval.models import Chunk, ChunkSet

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)

CHUNKER_VERSION = "chunker-v1"


def _compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of chunk content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _build_structural_path(node: LegalNode, nodes_by_id: dict[str, LegalNode]) -> str:
    """Build hierarchical path for a node (e.g., 'Chương I/Mục 1/Điều 5')."""
    path_parts: list[str] = []
    current = node
    
    while current:
        label = f"{current.kind.value} {current.ordinal}".strip()
        if current.title:
            label = f"{label}. {current.title}"
        path_parts.insert(0, label)
        
        if current.parent_id:
            current = nodes_by_id.get(current.parent_id)  # type: ignore
        else:
            break
    
    return " / ".join(path_parts) if path_parts else "Document"


def _should_chunk_node(node: LegalNode) -> bool:
    """Determine if a node should be included as a chunk."""
    # Include articles, clauses, and points as chunks
    # Skip document-level and chapter/section nodes (too large)
    return node.kind in (NodeKind.ARTICLE, NodeKind.CLAUSE, NodeKind.POINT, NodeKind.APPENDIX)


def chunk_legal_document(
    parse_result: LegalParseResult,
    version_id: str,
    created_by: str,
) -> tuple[ChunkSet, tuple[Chunk, ...]]:
    """Generate chunks from a legal parse result.
    
    Chunks are created at article/clause/point level, preserving legal structure.
    Per docs/07: legal boundaries take priority over token length.
    """
    # Build node lookup
    nodes_by_id = {node.node_id: node for node in parse_result.nodes}
    
    # Filter nodes to chunk (articles, clauses, points)
    chunkable_nodes = [node for node in parse_result.nodes if _should_chunk_node(node)]
    
    chunks: list[Chunk] = []
    chunk_set_id = f"cs_{uuid.uuid4().hex[:16]}"
    
    # Compute config hash (for now, simple hash of chunker version)
    config_hash = hashlib.sha256(CHUNKER_VERSION.encode("utf-8")).hexdigest()
    
    for idx, node in enumerate(chunkable_nodes):
        # Build structural path
        structural_path = _build_structural_path(node, nodes_by_id)
        
        # Create chunk
        chunk_id = f"ch_{uuid.uuid4().hex[:16]}"
        content_hash = _compute_content_hash(node.content)
        
        # Extract page information
        page_start = node.page_numbers[0] if node.page_numbers else None
        page_end = node.page_numbers[-1] if node.page_numbers else None
        
        chunk = Chunk.new(
            chunk_id=chunk_id,
            chunk_set_id=chunk_set_id,
            version_id=version_id,
            node_id=node.node_id,
            chunk_index=idx,
            content=node.content,
            content_hash=content_hash,
            structural_path=structural_path,
            node_kind=node.kind.value,
            heading=node.title,
            page_start=page_start,
            page_end=page_end,
            page_spans=node.source_locators,
            token_count=None,  # Will be computed when embedding
        )
        chunks.append(chunk)
    
    # Create chunk set
    chunk_set = ChunkSet.new(
        chunk_set_id=chunk_set_id,
        version_id=version_id,
        chunker_version=CHUNKER_VERSION,
        chunker_config_hash=config_hash,
        chunk_count=len(chunks),
        created_by=created_by,
    )
    
    LOGGER.info(
        f"Generated {len(chunks)} chunks from {len(parse_result.nodes)} nodes for version {version_id}"
    )
    
    return chunk_set, tuple(chunks)


class ChunkingService:
    """Generate and manage document chunks for retrieval."""

    def __init__(self) -> None:
        pass

    def create_chunks(
        self,
        parse_result: LegalParseResult,
        version_id: str,
        created_by: str,
    ) -> tuple[ChunkSet, tuple[Chunk, ...]]:
        """Generate chunks from a legal parse result."""
        return chunk_legal_document(parse_result, version_id, created_by)

    def get_chunk_context(
        self,
        chunk: Chunk,
        all_chunks: list[Chunk],
        context_window: int = 1,
    ) -> tuple[str, str, str]:
        """Get surrounding context for a chunk (previous, current, next).
        
        Used for display and citation building.
        """
        # Sort chunks by index
        sorted_chunks = sorted(
            [c for c in all_chunks if c.chunk_set_id == chunk.chunk_set_id],
            key=lambda c: c.chunk_index
        )
        
        current_idx = next(
            (i for i, c in enumerate(sorted_chunks) if c.chunk_id == chunk.chunk_id),
            -1
        )
        
        if current_idx == -1:
            return "", chunk.content, ""
        
        # Get previous context
        prev_content = ""
        if current_idx > 0 and context_window > 0:
            prev_chunks = sorted_chunks[max(0, current_idx - context_window):current_idx]
            prev_content = "\n\n".join(c.content for c in prev_chunks)
        
        # Get next context
        next_content = ""
        if current_idx < len(sorted_chunks) - 1 and context_window > 0:
            next_chunks = sorted_chunks[current_idx + 1:min(len(sorted_chunks), current_idx + 1 + context_window)]
            next_content = "\n\n".join(c.content for c in next_chunks)
        
        return prev_content, chunk.content, next_content
