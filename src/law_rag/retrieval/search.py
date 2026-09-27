"""PHASE 3 Hybrid Retrieval: BM25 lexical search, vector similarity, fusion, ACL, and reranking.

Per docs/08:
1. Authenticate and enforce server-side ACL (ACL leakage = 0).
2. Lexical (BM25) and Vector search run with matching ACL and validity conditions.
3. Merge lists using Reciprocal Rank Fusion (RRF) or Weighted Fusion.
4. Rerank preserving legal structure and validity signals without heuristic masking of conflicts.
5. Record complete RetrievalTrace and RetrievalResult audit trail.
6. Return structured Evidence items ready for RAG grounding.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Sequence

from law_rag.ingestion.authorization import AuthorizationService
from law_rag.ingestion.knowledge_models import AccessLevel, AppUser, ValidityStatus
from law_rag.rag.models import Evidence
from law_rag.retrieval.models import (
    Chunk,
    QueryType,
    RetrievalMethod,
    RetrievalResult,
    RetrievalTrace,
)

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words/terms."""
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


class BM25Index:
    """In-memory BM25Okapi implementation for lexical search."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avg_doc_len: float = 0.0
        self.doc_lengths: dict[str, int] = {}
        self.doc_freqs: dict[str, int] = {}
        self.term_freqs: dict[str, Counter[str]] = {}

    def index(self, chunk_id: str, text: str) -> None:
        """Add or update a document in the BM25 index."""
        tokens = tokenize(text)
        doc_len = len(tokens)
        self.doc_lengths[chunk_id] = doc_len
        tf = Counter(tokens)
        self.term_freqs[chunk_id] = tf

        for term in tf:
            self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.corpus_size = len(self.doc_lengths)
        total_len = sum(self.doc_lengths.values())
        self.avg_doc_len = total_len / self.corpus_size if self.corpus_size > 0 else 0.0

    def search(self, query: str, top_k: int = 50) -> list[tuple[str, float]]:
        """Score all documents against query and return (chunk_id, score) sorted desc."""
        query_terms = tokenize(query)
        if not query_terms or self.corpus_size == 0:
            return []

        scores: dict[str, float] = {}
        for term in query_terms:
            n_q = self.doc_freqs.get(term, 0)
            if n_q == 0:
                continue
            idf = math.log((self.corpus_size - n_q + 0.5) / (n_q + 0.5) + 1.0)
            for chunk_id, tf_map in self.term_freqs.items():
                f_q = tf_map.get(term, 0)
                if f_q == 0:
                    continue
                d_len = self.doc_lengths.get(chunk_id, 0)
                numerator = f_q * (self.k1 + 1.0)
                denominator = f_q + self.k1 * (1.0 - self.b + self.b * (d_len / self.avg_doc_len))
                score_term = idf * (numerator / denominator)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + score_term

        return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Compute cosine similarity between two numeric vectors in [-1, 1]."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    sim = dot / (norm1 * norm2)
    return max(-1.0, min(1.0, sim))


class VectorSearchAdapter:
    """Vector search adapter for chunk embeddings with cosine similarity."""

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}

    def index_vector(self, chunk_id: str, vector: list[float]) -> None:
        self._vectors[chunk_id] = vector

    def search_vector(
        self, query_vector: list[float], top_k: int = 50
    ) -> list[tuple[str, float]]:
        """Return (chunk_id, similarity) sorted by similarity desc."""
        if not query_vector or not self._vectors:
            return []

        results: list[tuple[str, float]] = []
        for chunk_id, vec in self._vectors.items():
            sim = cosine_similarity(query_vector, vec)
            norm_score = max(0.0, (sim + 1.0) / 2.0)
            results.append((chunk_id, norm_score))

        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion (RRF) algorithm across ranked lists of chunk IDs."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank))
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def weighted_score_fusion(
    lexical_scores: dict[str, float],
    vector_scores: dict[str, float],
    weight_lexical: float = 0.5,
    weight_vector: float = 0.5,
) -> list[tuple[str, float]]:
    """Weighted score fusion with min-max normalization."""
    all_keys = set(lexical_scores.keys()) | set(vector_scores.keys())
    if not all_keys:
        return []

    def normalize(score_map: dict[str, float]) -> dict[str, float]:
        if not score_map:
            return {}
        vals = score_map.values()
        min_v, max_v = min(vals), max(vals)
        if max_v == min_v:
            return {k: 1.0 for k in score_map}
        return {k: (v - min_v) / (max_v - min_v) for k, v in score_map.items()}

    norm_lex = normalize(lexical_scores)
    norm_vec = normalize(vector_scores)

    combined: dict[str, float] = {}
    for doc_id in all_keys:
        s_lex = norm_lex.get(doc_id, 0.0)
        s_vec = norm_vec.get(doc_id, 0.0)
        combined[doc_id] = weight_lexical * s_lex + weight_vector * s_vec

    return sorted(combined.items(), key=lambda x: x[1], reverse=True)


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Document metadata needed for ACL and temporal filtering."""

    document_id: str
    version_id: str
    document_number: str
    title: str
    issuing_body: str
    document_type: str
    issue_date: date
    effective_date: date | None
    expiry_date: date | None
    collection_ids: tuple[str, ...]
    validity_status: ValidityStatus
    is_verified: bool = True

    def is_effective_at(self, as_of: date) -> bool:
        """Evaluate whether document is effective at a given date."""
        if self.effective_date and as_of < self.effective_date:
            return False
        if self.expiry_date and as_of > self.expiry_date:
            return False
        return True


@dataclass
class LegalReranker:
    """Reranker that boosts exact legal matches and penalizes repealed documents."""

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, float]],
        chunk_map: dict[str, Chunk],
        meta_map: dict[str, DocumentMetadata],
        as_of_date: date | None = None,
    ) -> list[tuple[str, float]]:
        """Rerank candidates based on legal hierarchy, query match, and temporal signals."""
        query_lower = query.lower()
        reranked: list[tuple[str, float]] = []

        for chunk_id, base_score in candidates:
            chunk = chunk_map.get(chunk_id)
            if not chunk:
                continue
            meta = meta_map.get(chunk.version_id)
            score = base_score

            # Boost exact document number or structural path match
            if meta and meta.document_number.lower() in query_lower:
                score += 0.25
            path_segments = [seg.strip().lower() for seg in chunk.structural_path.split("/") if seg.strip()]
            if any(seg in query_lower for seg in path_segments):
                score += 0.20
            elif chunk.structural_path.lower() in query_lower:
                score += 0.20
            if chunk.heading and chunk.heading.lower() in query_lower:
                score += 0.15

            # Temporal & validity adjustment
            if meta:
                if meta.validity_status is ValidityStatus.IN_FORCE:
                    score += 0.05
                elif meta.validity_status is ValidityStatus.REPEALED:
                    score -= 0.15

                if as_of_date and not meta.is_effective_at(as_of_date):
                    score -= 0.10

            normalized = max(0.01, min(1.0, score))
            reranked.append((chunk_id, normalized))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked



class RetrievalService:
    """Service orchestrating hybrid retrieval with ACL filtering, temporal check, and audit trail."""

    def __init__(
        self,
        *,
        auth_service: AuthorizationService | None = None,
        reranker: LegalReranker | None = None,
    ) -> None:
        self.auth_service = auth_service or AuthorizationService()
        self.reranker = reranker or LegalReranker()
        self.bm25 = BM25Index()
        self.vector_adapter = VectorSearchAdapter()

        # In-memory stores
        self._chunks: dict[str, Chunk] = {}
        self._metadata: dict[str, DocumentMetadata] = {}
        self._traces: dict[str, RetrievalTrace] = {}
        self._trace_results: dict[str, list[RetrievalResult]] = {}

    def index_chunk(
        self,
        chunk: Chunk,
        metadata: DocumentMetadata,
        vector: list[float] | None = None,
    ) -> None:
        """Register a chunk in BM25, vector, and internal stores."""
        self._chunks[chunk.chunk_id] = chunk
        self._metadata[metadata.version_id] = metadata
        self.bm25.index(
            chunk.chunk_id,
            f"{chunk.structural_path} {chunk.heading or ''} {chunk.content}",
        )
        if vector:
            self.vector_adapter.index_vector(chunk.chunk_id, vector)

    def retrieve(
        self,
        *,
        query: str,
        user: AppUser,
        as_of_date: date | None = None,
        query_vector: list[float] | None = None,
        query_type: QueryType = QueryType.HYBRID,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
        manifest_id: str | None = None,
    ) -> tuple[tuple[RetrievalResult, ...], tuple[Evidence, ...], RetrievalTrace]:
        """Execute hybrid search with strict server-side ACL, validity evaluation, and audit trace."""
        start_time = datetime.now(timezone.utc)
        trace_id = f"trace_{uuid.uuid4().hex[:16]}"

        if not query.strip():
            raise ValueError("Query cannot be empty")

        # 1. ACL Filtering candidates (Zero ACL Leakage)
        accessible_chunk_ids: set[str] = set()
        for chunk_id, chunk in self._chunks.items():
            meta = self._metadata.get(chunk.version_id)
            if not meta:
                continue

            has_access = False
            if user.is_system:
                has_access = True
            else:
                for coll_id in meta.collection_ids:
                    try:
                        self.auth_service.check_collection_access(
                            user=user,
                            collection_id=coll_id,
                            min_access_level=AccessLevel.READ,
                        )
                        has_access = True
                        break
                    except Exception:
                        continue

            if not has_access:
                continue

            if filters:
                if "document_type" in filters and meta.document_type != filters["document_type"]:
                    continue
                if "issuing_body" in filters and meta.issuing_body != filters["issuing_body"]:
                    continue
                if "collection_id" in filters and filters["collection_id"] not in meta.collection_ids:
                    continue

            accessible_chunk_ids.add(chunk_id)

        # 2. Search lexical & vector
        bm25_raw = self.bm25.search(query, top_k=top_k * 3)
        bm25_filtered = [(c_id, score) for c_id, score in bm25_raw if c_id in accessible_chunk_ids]

        vector_filtered: list[tuple[str, float]] = []
        if query_vector:
            vec_raw = self.vector_adapter.search_vector(query_vector, top_k=top_k * 3)
            vector_filtered = [(c_id, score) for c_id, score in vec_raw if c_id in accessible_chunk_ids]

        # 3. Fusion
        method_used = RetrievalMethod.FUSION
        fused_candidates: list[tuple[str, float]]

        if query_type == QueryType.LEXICAL or not vector_filtered:
            method_used = RetrievalMethod.LEXICAL
            if bm25_filtered:
                max_s = max(s for _, s in bm25_filtered)
                fused_candidates = [(c_id, s / max_s if max_s > 0 else 1.0) for c_id, s in bm25_filtered]
            else:
                fused_candidates = []
        elif query_type == QueryType.SEMANTIC or not bm25_filtered:
            method_used = RetrievalMethod.VECTOR
            fused_candidates = vector_filtered
        else:
            ranked_lex = [c_id for c_id, _ in bm25_filtered]
            ranked_vec = [c_id for c_id, _ in vector_filtered]
            rrf_res = reciprocal_rank_fusion([ranked_lex, ranked_vec], k=60)
            max_rrf = max((s for _, s in rrf_res), default=1.0)
            fused_candidates = [(c_id, s / max_rrf if max_rrf > 0 else 0.0) for c_id, s in rrf_res]

        # 4. Rerank
        if fused_candidates:
            reranked_scores = self.reranker.rerank(
                query=query,
                candidates=fused_candidates[: top_k * 2],
                chunk_map=self._chunks,
                meta_map=self._metadata,
                as_of_date=as_of_date,
            )
            final_candidates = reranked_scores[:top_k]
            method_used = RetrievalMethod.RERANKED
        else:
            final_candidates = []

        # 5. Build results & Evidence
        retrieval_results: list[RetrievalResult] = []
        evidence_list: list[Evidence] = []

        for rank, (chunk_id, score) in enumerate(final_candidates, start=1):
            chunk = self._chunks[chunk_id]
            meta = self._metadata[chunk.version_id]

            res = RetrievalResult.new(
                trace_id=trace_id,
                chunk_id=chunk_id,
                rank=rank,
                score=round(score, 4),
                retrieval_method=method_used,
            )
            retrieval_results.append(res)

            ev = Evidence(
                evidence_id=f"ev_{uuid.uuid4().hex[:16]}",
                chunk_id=chunk_id,
                version_id=chunk.version_id,
                document_number=meta.document_number,
                document_title=meta.title,
                structural_path=chunk.structural_path,
                content=chunk.content,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                score=round(score, 4),
                is_verified=meta.is_verified,
                validity_status=meta.validity_status.value,
            )
            evidence_list.append(ev)

        end_time = datetime.now(timezone.utc)
        latency_ms = int((end_time - start_time).total_seconds() * 1000)

        trace = RetrievalTrace.new(
            trace_id=trace_id,
            user_id=user.user_id,
            query=query,
            query_type=query_type,
            as_of_date=as_of_date,
            filters=filters,
            manifest_id=manifest_id,
            result_count=len(retrieval_results),
            latency_ms=latency_ms,
        )

        self._traces[trace_id] = trace
        self._trace_results[trace_id] = retrieval_results

        return tuple(retrieval_results), tuple(evidence_list), trace

    def get_trace(self, trace_id: str) -> RetrievalTrace | None:
        return self._traces.get(trace_id)

    def get_trace_results(self, trace_id: str) -> tuple[RetrievalResult, ...]:
        return tuple(self._trace_results.get(trace_id, []))

