-- ============================================================================
-- TABLE: audit.ingestion_file
-- File-level processing state for idempotent S3 ingestion
-- ============================================================================

CREATE TABLE audit.ingestion_file (
    -- Identity
    ingestion_file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- S3 Object Identity (deterministic physical-object-version)
    bucket_name VARCHAR(255) NOT NULL,
    object_key VARCHAR(1024) NOT NULL,
    object_version VARCHAR(512) NOT NULL,
    
    -- Source Metadata (retained for audit/debugging)
    etag VARCHAR(255),
    last_modified TIMESTAMP WITH TIME ZONE,
    size_bytes BIGINT,

    -- Processing State
    status VARCHAR(50) NOT NULL DEFAULT 'DISCOVERED',
    first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,

    -- Processing Results
    records_discovered INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_duplicate INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,

    -- Metadata & Lineage
    processed_by VARCHAR(255),
    ingestion_run_id UUID REFERENCES audit.ingestion_log(ingestion_run_id),

    -- Constraints
    CONSTRAINT ingestion_file_status_valid
        CHECK (status IN ('DISCOVERED', 'PROCESSING', 'SUCCESS', 'FAILED')),
    CONSTRAINT ingestion_file_records_positive
        CHECK (records_discovered >= 0 AND records_inserted >= 0 
               AND records_duplicate >= 0 AND records_failed >= 0),
    CONSTRAINT ingestion_file_object_identity
        UNIQUE (bucket_name, object_key, object_version)
);

COMMENT ON TABLE audit.ingestion_file IS
    'File-level processing state for S3 ingestion. Tracks which physical S3 objects '
    'have been processed to enable idempotent re-runs and avoid reprocessing same files.';

COMMENT ON COLUMN audit.ingestion_file.bucket_name IS
    'S3 bucket name.';

COMMENT ON COLUMN audit.ingestion_file.object_key IS
    'S3 object key/path.';

COMMENT ON COLUMN audit.ingestion_file.object_version IS
    'Canonical physical-object-version identifier. '
    'If S3 Versioning enabled: S3 VersionId. '
    'If S3 Versioning disabled: Deterministic hash of (ETag + last_modified + size_bytes), '
    'e.g., "<etag>:<last_modified_iso>:<size_bytes>". '
    'NOT NULL to ensure UNIQUE constraint properly prevents duplicates (PostgreSQL UNIQUE permits multiple NULLs).';

COMMENT ON COLUMN audit.ingestion_file.etag IS
    'S3 object ETag. Retained for audit trail even though object_version is the '
    'canonical checkpoint identity. Useful for debugging and verifying object identity.';

COMMENT ON COLUMN audit.ingestion_file.last_modified IS
    'S3 object LastModified timestamp. Retained for audit trail.';

COMMENT ON COLUMN audit.ingestion_file.size_bytes IS
    'S3 object size in bytes. Retained for audit trail.';

COMMENT ON COLUMN audit.ingestion_file.status IS
    'DISCOVERED: found in S3, not yet processed. '
    'PROCESSING: ingestion started. '
    'SUCCESS: all records from file processed successfully. '
    'FAILED: ingestion failed; see error_message for diagnostic.';

COMMENT ON COLUMN audit.ingestion_file.records_discovered IS
    'How many records were found/parsed in this file.';

COMMENT ON COLUMN audit.ingestion_file.records_inserted IS
    'How many new records were inserted into raw.raw_event.';

COMMENT ON COLUMN audit.ingestion_file.records_duplicate IS
    'How many records matched existing (source_system, source_record_id, source_version) '
    'in raw.raw_event and were rejected by ON CONFLICT DO NOTHING.';

COMMENT ON COLUMN audit.ingestion_file.records_failed IS
    'How many records failed to parse, validate, or insert due to schema/data errors.';

COMMENT ON COLUMN audit.ingestion_file.error_message IS
    'If status = FAILED, detailed error information for investigation/retry.';

COMMENT ON COLUMN audit.ingestion_file.ingestion_run_id IS
    'Foreign key to audit.ingestion_log.ingestion_run_id. '
    'Links this file-level processing to the run-level audit record. '
    'NULL if file discovered but run not yet started/linked.';

COMMENT ON CONSTRAINT ingestion_file_object_identity ON audit.ingestion_file IS
    'Ensures each physical S3 object version is tracked exactly once. '
    'Enables idempotent file-level checkpointing. '
    'NOT NULL object_version required so UNIQUE constraint works (PostgreSQL UNIQUE permits multiple NULLs).';

-- Indexes for operational queries
CREATE INDEX idx_ingestion_file_status ON audit.ingestion_file(status);
CREATE INDEX idx_ingestion_file_object_key ON audit.ingestion_file(bucket_name, object_key);
CREATE INDEX idx_ingestion_file_run_id ON audit.ingestion_file(ingestion_run_id) WHERE ingestion_run_id IS NOT NULL;
CREATE INDEX idx_ingestion_file_processing ON audit.ingestion_file(processing_started_at DESC) 
    WHERE status IN ('PROCESSING', 'DISCOVERED');
