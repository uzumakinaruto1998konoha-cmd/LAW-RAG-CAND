-- PHASE 4 RAG and Citations: Conversations, messages, evidence tracking, and citations
-- Migration 0006: RAG conversation management and citation infrastructure

-- ============================================
-- CONVERSATIONS
-- ============================================

CREATE TABLE IF NOT EXISTS conversation (
    conversation_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    title text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    is_archived boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS conversation_user_idx ON conversation (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS conversation_archived_idx ON conversation (is_archived, updated_at DESC);

-- ============================================
-- MESSAGES
-- ============================================

CREATE TABLE IF NOT EXISTS message (
    message_id text PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES conversation(conversation_id) ON DELETE CASCADE,
    role varchar(16) NOT NULL,
    content text NOT NULL,
    trace_id text REFERENCES retrieval_trace(trace_id),
    as_of_date date,
    insufficient_evidence boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL,
    metadata jsonb,
    CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX IF NOT EXISTS message_conversation_idx ON message (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS message_trace_idx ON message (trace_id);

-- ============================================
-- EVIDENCE
-- ============================================

-- Evidence: retrieved chunks used to ground an answer
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id text PRIMARY KEY,
    message_id text NOT NULL REFERENCES message(message_id) ON DELETE CASCADE,
    chunk_id text NOT NULL REFERENCES chunk(chunk_id),
    version_id text NOT NULL REFERENCES document_version(version_id),
    rank integer NOT NULL CHECK (rank > 0),
    score real NOT NULL CHECK (score >= 0 AND score <= 1),
    used_in_answer boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS evidence_message_idx ON evidence (message_id, rank);
CREATE INDEX IF NOT EXISTS evidence_chunk_idx ON evidence (chunk_id);

-- ============================================
-- CITATIONS
-- ============================================

-- Citation: server-generated citation linking answer to evidence
CREATE TABLE IF NOT EXISTS citation (
    citation_id text PRIMARY KEY,
    message_id text NOT NULL REFERENCES message(message_id) ON DELETE CASCADE,
    evidence_id text NOT NULL REFERENCES evidence(evidence_id),
    chunk_id text NOT NULL REFERENCES chunk(chunk_id),
    version_id text NOT NULL REFERENCES document_version(version_id),
    document_number varchar(128),
    document_title text NOT NULL,
    issuing_body varchar(255),
    structural_path text NOT NULL,
    excerpt text NOT NULL,
    page_start integer,
    page_end integer,
    source_spans text[],
    viewer_url text,
    validity_status varchar(32) NOT NULL,
    as_of_date date,
    status varchar(16) NOT NULL DEFAULT 'valid',
    created_at timestamptz NOT NULL,
    CHECK (status IN ('valid', 'invalid', 'pending'))
);

CREATE INDEX IF NOT EXISTS citation_message_idx ON citation (message_id);
CREATE INDEX IF NOT EXISTS citation_evidence_idx ON citation (evidence_id);
CREATE INDEX IF NOT EXISTS citation_version_idx ON citation (version_id);

-- ============================================
-- MESSAGE WARNINGS
-- ============================================

-- MessageWarning: structured warnings about answer limitations
CREATE TABLE IF NOT EXISTS message_warning (
    warning_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id text NOT NULL REFERENCES message(message_id) ON DELETE CASCADE,
    warning_type varchar(64) NOT NULL,
    warning_text text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS message_warning_message_idx ON message_warning (message_id);

-- ============================================
-- RAG METRICS
-- ============================================

-- RAGMetrics: quality and performance tracking
CREATE TABLE IF NOT EXISTS rag_metrics (
    metric_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    metric_date date NOT NULL,
    query_count integer NOT NULL DEFAULT 0,
    insufficient_evidence_count integer NOT NULL DEFAULT 0,
    avg_evidence_count real,
    avg_citation_count real,
    avg_latency_ms real,
    p95_latency_ms real,
    created_at timestamptz NOT NULL,
    CONSTRAINT rag_metrics_date_unique UNIQUE (metric_date)
);

CREATE INDEX IF NOT EXISTS rag_metrics_date_idx ON rag_metrics (metric_date DESC);
