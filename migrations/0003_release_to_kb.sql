-- PHASE 1 Release to Knowledge Base: Document identity, versions, deduplication and processing runs
-- Migration 0003: Release approved documents to the retrievable knowledge base

-- Document: logical identity across versions (by document_number + issuing_body + type)
-- A document may have multiple versions over time (amendments, re-publications)
CREATE TABLE IF NOT EXISTS document (
    document_id text PRIMARY KEY,
    document_number varchar(128) NOT NULL,
    issuing_body varchar(255) NOT NULL,
    document_type varchar(128) NOT NULL,
    title text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    -- Unique constraint: one logical document per (number, body, type)
    -- This enforces document identity across versions
    CONSTRAINT document_identity_unique UNIQUE (document_number, issuing_body, document_type)
);

CREATE INDEX IF NOT EXISTS document_type_idx ON document (document_type);
CREATE INDEX IF NOT EXISTS document_number_idx ON document (document_number);

-- DocumentVersion: immutable snapshot released from an approved ingestion job
-- Each version references the logical document and carries effective dates
CREATE TABLE IF NOT EXISTS document_version (
    version_id text PRIMARY KEY,
    document_id text NOT NULL REFERENCES document(document_id) ON DELETE CASCADE,
    job_id text NOT NULL REFERENCES ingestion_job(job_id),
    parse_run_id text NOT NULL REFERENCES legal_parse_run(parse_run_id),
    version_number integer NOT NULL CHECK (version_number > 0),
    title text NOT NULL,
    issue_date date NOT NULL,
    effective_date date,
    expiry_date date,
    language varchar(16) NOT NULL DEFAULT 'vi',
    source_reference text,
    content_hash char(64) NOT NULL,
    released_at timestamptz NOT NULL,
    released_by varchar(255) NOT NULL,
    superseded_by text REFERENCES document_version(version_id),
    superseded_at timestamptz,
    -- Unique: one job produces at most one version
    CONSTRAINT document_version_job_unique UNIQUE (job_id),
    -- Version numbers increment per document
    CONSTRAINT document_version_number_unique UNIQUE (document_id, version_number),
    CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    CHECK (effective_date IS NULL OR effective_date >= issue_date),
    CHECK (expiry_date IS NULL OR expiry_date > issue_date),
    CHECK ((superseded_by IS NULL AND superseded_at IS NULL) OR (superseded_by IS NOT NULL AND superseded_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS document_version_document_idx ON document_version (document_id, version_number DESC);
CREATE INDEX IF NOT EXISTS document_version_effective_idx ON document_version (effective_date, expiry_date) WHERE superseded_by IS NULL;
CREATE INDEX IF NOT EXISTS document_version_parse_run_idx ON document_version (parse_run_id);

-- DocumentRelation: verified relations between document versions
-- Only accepted/corrected relations from review are stored here
CREATE TABLE IF NOT EXISTS document_relation (
    relation_id text PRIMARY KEY,
    source_version_id text NOT NULL REFERENCES document_version(version_id) ON DELETE CASCADE,
    target_version_id text REFERENCES document_version(version_id) ON DELETE CASCADE,
    relation_type varchar(16) NOT NULL,
    source_node_id text,
    target_scope_label varchar(64),
    valid_from date,
    valid_until date,
    created_at timestamptz NOT NULL,
    created_by varchar(255) NOT NULL,
    -- Either target_version_id (internal) or target_scope_label (external/future) must be set
    CHECK (target_version_id IS NOT NULL OR target_scope_label IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS document_relation_source_idx ON document_relation (source_version_id);
CREATE INDEX IF NOT EXISTS document_relation_target_idx ON document_relation (target_version_id);
CREATE INDEX IF NOT EXISTS document_relation_type_idx ON document_relation (relation_type);

-- ProcessingRun: tracks release and indexing operations
-- Each run is immutable; reindex creates a new run
CREATE TABLE IF NOT EXISTS processing_run (
    run_id text PRIMARY KEY,
    run_type varchar(32) NOT NULL, -- 'release' or 'index'
    pipeline_version varchar(64) NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    status varchar(32) NOT NULL, -- 'running', 'completed', 'failed'
    version_count integer NOT NULL DEFAULT 0 CHECK (version_count >= 0),
    error_code varchar(64),
    error_message text,
    initiated_by varchar(255) NOT NULL,
    manifest jsonb,
    CHECK (status IN ('running', 'completed', 'failed')),
    CHECK ((status = 'completed' AND completed_at IS NOT NULL) OR status <> 'completed'),
    CHECK ((status = 'failed' AND error_code IS NOT NULL) OR status <> 'failed')
);

CREATE INDEX IF NOT EXISTS processing_run_type_status_idx ON processing_run (run_type, status, started_at DESC);

-- VersionProcessingRecord: links document versions to processing runs
-- Tracks which versions were included in which runs (for rollback/audit)
CREATE TABLE IF NOT EXISTS version_processing_record (
    record_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL REFERENCES processing_run(run_id) ON DELETE CASCADE,
    version_id text NOT NULL REFERENCES document_version(version_id) ON DELETE CASCADE,
    processed_at timestamptz NOT NULL,
    outcome varchar(32) NOT NULL, -- 'success', 'skipped', 'error'
    error_code varchar(64),
    CONSTRAINT version_run_unique UNIQUE (run_id, version_id),
    CHECK (outcome IN ('success', 'skipped', 'error')),
    CHECK ((outcome = 'error' AND error_code IS NOT NULL) OR outcome <> 'error')
);

CREATE INDEX IF NOT EXISTS version_processing_record_version_idx ON version_processing_record (version_id, processed_at DESC);
CREATE INDEX IF NOT EXISTS version_processing_record_run_idx ON version_processing_record (run_id, outcome);

-- DuplicateCandidate: tracks near-duplicate documents detected during release
-- Stores evidence for manual deduplication decisions
CREATE TABLE IF NOT EXISTS duplicate_candidate (
    candidate_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id_a text NOT NULL REFERENCES document_version(version_id) ON DELETE CASCADE,
    version_id_b text NOT NULL REFERENCES document_version(version_id) ON DELETE CASCADE,
    similarity_score numeric(5,4) NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1),
    detection_method varchar(64) NOT NULL,
    detected_at timestamptz NOT NULL,
    resolution varchar(32), -- NULL (pending), 'duplicate', 'distinct', 'merge'
    resolved_by varchar(255),
    resolved_at timestamptz,
    notes text,
    CONSTRAINT duplicate_candidate_pair_unique UNIQUE (version_id_a, version_id_b),
    CHECK (version_id_a < version_id_b), -- enforce ordering to prevent (A,B) and (B,A)
    CHECK ((resolution IS NULL AND resolved_by IS NULL) OR (resolution IS NOT NULL AND resolved_by IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS duplicate_candidate_unresolved_idx ON duplicate_candidate (detected_at DESC) WHERE resolution IS NULL;
