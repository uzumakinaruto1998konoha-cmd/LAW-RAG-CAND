-- PHASE 3 Index and Retrieval: Chunking, manifest lifecycle, and search infrastructure
-- Migration 0005: Chunk storage, index manifests, and retrieval infrastructure

-- ============================================
-- CHUNK MANAGEMENT
-- ============================================

-- ChunkSet: versioned collection of chunks from a document version
CREATE TABLE IF NOT EXISTS chunk_set (
    chunk_set_id text PRIMARY KEY,
    version_id text NOT NULL REFERENCES document_version(version_id) ON DELETE CASCADE,
    chunker_version varchar(64) NOT NULL,
    chunker_config_hash char(64) NOT NULL,
    chunk_count integer NOT NULL CHECK (chunk_count >= 0),
    created_at timestamptz NOT NULL,
    created_by text NOT NULL REFERENCES app_user(user_id),
    is_active boolean NOT NULL DEFAULT true,
    CHECK (chunker_config_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS chunk_set_version_idx ON chunk_set (version_id, created_at DESC);
CREATE INDEX IF NOT EXISTS chunk_set_active_idx ON chunk_set (is_active) WHERE is_active = true;

-- Chunk: atomic retrieval unit with legal structure preservation
CREATE TABLE IF NOT EXISTS chunk (
    chunk_id text PRIMARY KEY,
    chunk_set_id text NOT NULL REFERENCES chunk_set(chunk_set_id) ON DELETE CASCADE,
    version_id text NOT NULL REFERENCES document_version(version_id),
    node_id text,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    content text NOT NULL,
    content_hash char(64) NOT NULL,
    structural_path text NOT NULL,
    node_kind varchar(16),
    heading text,
    page_start integer,
    page_end integer,
    page_spans text[],
    token_count integer CHECK (token_count >= 0),
    created_at timestamptz NOT NULL,
    CONSTRAINT chunk_set_index_unique UNIQUE (chunk_set_id, chunk_index),
    CHECK (content_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS chunk_version_idx ON chunk (version_id);
CREATE INDEX IF NOT EXISTS chunk_node_idx ON chunk (node_id);
CREATE INDEX IF NOT EXISTS chunk_set_idx ON chunk (chunk_set_id, chunk_index);

-- ============================================
-- INDEX MANIFESTS
-- ============================================

-- IndexManifest: versioned search index with reproducible build
CREATE TABLE IF NOT EXISTS index_manifest (
    manifest_id text PRIMARY KEY,
    manifest_version integer NOT NULL,
    index_type varchar(32) NOT NULL,
    status varchar(32) NOT NULL,
    pipeline_version varchar(64) NOT NULL,
    embedding_model varchar(128),
    embedding_dimension integer,
    lexical_analyzer varchar(64),
    chunk_set_count integer NOT NULL DEFAULT 0,
    chunk_count integer NOT NULL DEFAULT 0,
    document_count integer NOT NULL DEFAULT 0,
    build_started_at timestamptz,
    build_completed_at timestamptz,
    activated_at timestamptz,
    retired_at timestamptz,
    created_by text NOT NULL REFERENCES app_user(user_id),
    error_message text,
    config jsonb,
    CHECK (status IN ('building', 'ready', 'active', 'failed', 'retired')),
    CHECK (index_type IN ('lexical', 'vector', 'hybrid')),
    CHECK ((status = 'failed' AND error_message IS NOT NULL) OR status <> 'failed')
);

CREATE INDEX IF NOT EXISTS index_manifest_status_idx ON index_manifest (status, created_at DESC);
CREATE INDEX IF NOT EXISTS index_manifest_active_idx ON index_manifest (index_type, status) WHERE status = 'active';

-- ChunkIndexRecord: tracks which chunks are in which index
CREATE TABLE IF NOT EXISTS chunk_index_record (
    record_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_id text NOT NULL REFERENCES index_manifest(manifest_id) ON DELETE CASCADE,
    chunk_id text NOT NULL REFERENCES chunk(chunk_id) ON DELETE CASCADE,
    indexed_at timestamptz NOT NULL,
    CONSTRAINT chunk_manifest_unique UNIQUE (manifest_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS chunk_index_record_manifest_idx ON chunk_index_record (manifest_id);
CREATE INDEX IF NOT EXISTS chunk_index_record_chunk_idx ON chunk_index_record (chunk_id);

-- ============================================
-- RETRIEVAL TRACES
-- ============================================

-- RetrievalTrace: audit trail for search queries and results
CREATE TABLE IF NOT EXISTS retrieval_trace (
    trace_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_user(user_id),
    query text NOT NULL,
    query_type varchar(32) NOT NULL,
    as_of_date date,
    filters jsonb,
    manifest_id text REFERENCES index_manifest(manifest_id),
    result_count integer NOT NULL,
    latency_ms integer,
    created_at timestamptz NOT NULL,
    CHECK (query_type IN ('semantic', 'lexical', 'hybrid', 'exact'))
);

CREATE INDEX IF NOT EXISTS retrieval_trace_user_idx ON retrieval_trace (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS retrieval_trace_created_idx ON retrieval_trace (created_at DESC);

-- RetrievalResult: individual chunks returned in a retrieval trace
CREATE TABLE IF NOT EXISTS retrieval_result (
    result_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trace_id text NOT NULL REFERENCES retrieval_trace(trace_id) ON DELETE CASCADE,
    chunk_id text NOT NULL REFERENCES chunk(chunk_id),
    rank integer NOT NULL CHECK (rank > 0),
    score real NOT NULL,
    retrieval_method varchar(32) NOT NULL,
    CHECK (retrieval_method IN ('lexical', 'vector', 'fusion', 'reranked'))
);

CREATE INDEX IF NOT EXISTS retrieval_result_trace_idx ON retrieval_result (trace_id, rank);
CREATE INDEX IF NOT EXISTS retrieval_result_chunk_idx ON retrieval_result (chunk_id);

-- ============================================
-- SEARCH STATISTICS
-- ============================================

-- SearchMetrics: aggregated search quality metrics
CREATE TABLE IF NOT EXISTS search_metrics (
    metric_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_id text REFERENCES index_manifest(manifest_id),
    metric_date date NOT NULL,
    query_count integer NOT NULL DEFAULT 0,
    avg_latency_ms real,
    p95_latency_ms real,
    zero_result_rate real,
    avg_result_count real,
    created_at timestamptz NOT NULL,
    CONSTRAINT search_metrics_manifest_date_unique UNIQUE (manifest_id, metric_date)
);

CREATE INDEX IF NOT EXISTS search_metrics_date_idx ON search_metrics (metric_date DESC);
