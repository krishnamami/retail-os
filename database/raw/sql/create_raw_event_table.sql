-- =============================================================================
-- RETAIL OS - Create raw.raw_event Table
-- Purpose: Foundation table for frozen corpus ingestion with idempotency
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS runtime;
CREATE SCHEMA IF NOT EXISTS state;

-- TABLE: raw.raw_event
-- Immutable raw source records with idempotency via UNIQUE constraint
CREATE TABLE IF NOT EXISTS raw.raw_event (
    raw_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(128) NOT NULL DEFAULT 'FROZEN',
    source_record_id VARCHAR(256) NOT NULL,
    payload JSONB NOT NULL,
    occurred_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    arrival_at TIMESTAMPTZ DEFAULT NOW(),
    ingestion_version VARCHAR(16) DEFAULT '1.0',
    ingestion_run_id UUID DEFAULT gen_random_uuid(),
    validation_status VARCHAR(32) DEFAULT 'PENDING',
    validation_errors TEXT,
    UNIQUE (source_system, source_record_id, ingestion_version),
    CONSTRAINT check_raw_event_status
        CHECK (validation_status IN ('PENDING', 'VALID', 'INVALID'))
);

CREATE INDEX IF NOT EXISTS idx_raw_event_source_system ON raw.raw_event(source_system);
CREATE INDEX IF NOT EXISTS idx_raw_event_source_record_id ON raw.raw_event(source_record_id);
CREATE INDEX IF NOT EXISTS idx_raw_event_occurred_at ON raw.raw_event(occurred_at);
CREATE INDEX IF NOT EXISTS idx_raw_event_recorded_at ON raw.raw_event(recorded_at);
CREATE INDEX IF NOT EXISTS idx_raw_event_ingestion_version ON raw.raw_event(ingestion_version);

-- TABLE: audit.ingestion_log
CREATE TABLE IF NOT EXISTS audit.ingestion_log (
    ingestion_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_version VARCHAR(16) NOT NULL,
    raw_event_id UUID NOT NULL,
    source_record_id VARCHAR(256) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) DEFAULT 'SUCCESS',
    FOREIGN KEY (raw_event_id) REFERENCES raw.raw_event(raw_event_id) ON DELETE CASCADE,
    UNIQUE (ingestion_version, raw_event_id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_version ON audit.ingestion_log(ingestion_version);

-- TABLE: audit.ingestion_file
CREATE TABLE IF NOT EXISTS audit.ingestion_file (
    ingestion_file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_key VARCHAR(1024) NOT NULL,
    ingestion_version VARCHAR(16) NOT NULL,
    record_count INTEGER DEFAULT 0,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) DEFAULT 'SUCCESS',
    UNIQUE (file_key, ingestion_version)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_file_key ON audit.ingestion_file(file_key);

-- TABLE: runtime.evidence (placeholder)
CREATE TABLE IF NOT EXISTS runtime.evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_event_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (raw_event_id) REFERENCES raw.raw_event(raw_event_id) ON DELETE CASCADE
);

-- TABLE: runtime.assertion (placeholder)
CREATE TABLE IF NOT EXISTS runtime.assertion (
    assertion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (evidence_id) REFERENCES runtime.evidence(evidence_id) ON DELETE CASCADE
);

-- TABLE: state.fold_state_snapshot (placeholder)
CREATE TABLE IF NOT EXISTS state.fold_state_snapshot (
    fold_state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assertion_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (assertion_id) REFERENCES runtime.assertion(assertion_id) ON DELETE CASCADE
);

-- TABLE: audit.schema_version
CREATE TABLE IF NOT EXISTS audit.schema_version (
    schema_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_name VARCHAR(64) NOT NULL,
    version VARCHAR(16) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (schema_name, version)
);

INSERT INTO audit.schema_version (schema_name, version) VALUES ('raw', '1.0') ON CONFLICT DO NOTHING;

COMMIT;

-- Verification
SELECT 'Tables created successfully' AS status;
