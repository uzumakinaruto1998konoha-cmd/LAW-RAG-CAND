CREATE TABLE IF NOT EXISTS ingestion_job (
    job_id text PRIMARY KEY,
    idempotency_key varchar(128) NOT NULL UNIQUE,
    sha256 char(64) NOT NULL UNIQUE,
    original_filename varchar(255) NOT NULL,
    media_type varchar(128) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    storage_key char(64) NOT NULL,
    status varchar(32) NOT NULL,
    trace_id varchar(128) NOT NULL,
    uploader_id varchar(255) NOT NULL,
    source text,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    error_code varchar(64),
    CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (storage_key ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS ingestion_job_status_created_idx ON ingestion_job (status, created_at);

CREATE TABLE IF NOT EXISTS ingestion_request (
    idempotency_key varchar(128) PRIMARY KEY,
    sha256 char(64) NOT NULL,
    job_id text NOT NULL REFERENCES ingestion_job(job_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS audit_event (
    audit_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id varchar(255) NOT NULL,
    action varchar(64) NOT NULL,
    object_id varchar(255) NOT NULL,
    trace_id varchar(128) NOT NULL,
    outcome varchar(64) NOT NULL,
    occurred_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS audit_event_object_time_idx ON audit_event (object_id, occurred_at);
