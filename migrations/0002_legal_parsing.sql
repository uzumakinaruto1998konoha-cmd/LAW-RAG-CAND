CREATE TABLE IF NOT EXISTS legal_parse_run (
    parse_run_id text PRIMARY KEY,
    job_id text NOT NULL REFERENCES ingestion_job(job_id),
    pipeline_version varchar(64) NOT NULL,
    parser_version varchar(64) NOT NULL,
    parser_config_hash char(64) NOT NULL,
    page_count integer,
    review_required boolean NOT NULL,
    warnings text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK (parser_config_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS legal_parse_run_job_time_idx ON legal_parse_run (job_id, created_at DESC);

CREATE TABLE IF NOT EXISTS legal_node (
    node_id text NOT NULL,
    parse_run_id text NOT NULL REFERENCES legal_parse_run(parse_run_id) ON DELETE CASCADE,
    kind varchar(16) NOT NULL,
    label varchar(64) NOT NULL,
    ordinal varchar(32) NOT NULL,
    title text,
    content text NOT NULL,
    parent_id text,
    confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    page_numbers integer[] NOT NULL DEFAULT '{}',
    source_locators text[] NOT NULL,
    source_locator text NOT NULL,
    source_page integer,
    source_method varchar(32) NOT NULL,
    source_detector varchar(64) NOT NULL,
    requires_verification boolean NOT NULL,
    verification varchar(16) NOT NULL,
    reviewer_id varchar(255),
    reviewed_at timestamptz,
    PRIMARY KEY (parse_run_id, node_id),
    CHECK ((verification = 'unverified' AND reviewer_id IS NULL) OR (verification <> 'unverified' AND reviewer_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS legal_node_parent_idx ON legal_node (parse_run_id, parent_id);

CREATE TABLE IF NOT EXISTS metadata_assertion (
    assertion_id text NOT NULL,
    parse_run_id text NOT NULL REFERENCES legal_parse_run(parse_run_id) ON DELETE CASCADE,
    field varchar(32) NOT NULL,
    value text NOT NULL,
    raw_value text NOT NULL,
    confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    required boolean NOT NULL,
    requires_verification boolean NOT NULL,
    verification varchar(16) NOT NULL,
    source_locator text NOT NULL,
    source_page integer,
    detector varchar(64) NOT NULL,
    method varchar(32) NOT NULL,
    reviewer_id varchar(255),
    reviewed_at timestamptz,
    PRIMARY KEY (parse_run_id, assertion_id),
    CHECK ((verification = 'unverified' AND reviewer_id IS NULL) OR (verification <> 'unverified' AND reviewer_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS document_relation_candidate (
    relation_id text NOT NULL,
    parse_run_id text NOT NULL REFERENCES legal_parse_run(parse_run_id) ON DELETE CASCADE,
    relation_type varchar(16) NOT NULL,
    source_node_id text,
    target_reference text NOT NULL,
    target_document_number varchar(128),
    target_scope_label varchar(64),
    confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    requires_verification boolean NOT NULL,
    verification varchar(16) NOT NULL,
    source_locator text NOT NULL,
    source_page integer,
    detector varchar(64) NOT NULL,
    method varchar(32) NOT NULL,
    reviewer_id varchar(255),
    reviewed_at timestamptz,
    PRIMARY KEY (parse_run_id, relation_id),
    CHECK ((verification = 'unverified' AND reviewer_id IS NULL) OR (verification <> 'unverified' AND reviewer_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS document_relation_candidate_target_idx
    ON document_relation_candidate (target_document_number, verification);

CREATE TABLE IF NOT EXISTS review_decision (
    review_decision_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id text NOT NULL REFERENCES ingestion_job(job_id),
    parse_run_id text NOT NULL REFERENCES legal_parse_run(parse_run_id) ON DELETE CASCADE,
    item_kind varchar(16) NOT NULL,
    item_id varchar(64) NOT NULL,
    action varchar(16) NOT NULL,
    reviewer_id varchar(255) NOT NULL,
    corrected_value text,
    target_document_number varchar(128),
    target_scope_label varchar(64),
    comment text,
    decided_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS review_decision_run_idx ON review_decision (parse_run_id, decided_at);

CREATE TABLE IF NOT EXISTS document_approval (
    job_id text PRIMARY KEY REFERENCES ingestion_job(job_id),
    parse_run_id text NOT NULL REFERENCES legal_parse_run(parse_run_id),
    approved_by varchar(255) NOT NULL,
    approved_at timestamptz NOT NULL,
    acknowledged_warnings text[] NOT NULL DEFAULT '{}'
);
