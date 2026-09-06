-- POSTGRESQL RUNTIME SCHEMA DDL
-- Frozen S3 Corpus: 170 records → PostgreSQL → Evidence → Assertions → Fold
-- Schema Version: 1.0
-- Generated: 2026-09-05

-- ============================================================================
-- SCHEMA CREATION
-- ============================================================================

-- Create base schemas if they do not exist
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS runtime;
CREATE SCHEMA IF NOT EXISTS state;
CREATE SCHEMA IF NOT EXISTS audit;

-- ============================================================================
-- TABLE 1: audit.schema_version
-- Track PostgreSQL schema evolution
-- ============================================================================

CREATE TABLE audit.schema_version (
    schema_version_id SERIAL PRIMARY KEY,
    version_number INTEGER NOT NULL UNIQUE,
    version_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL,
    deployed_by VARCHAR(100),
    kb_version_aligned VARCHAR(50) NOT NULL,
    changes_from_prior TEXT,

    CONSTRAINT version_number_positive CHECK (version_number > 0)
);

COMMENT ON TABLE audit.schema_version IS
    'Audit trail for PostgreSQL schema versions. Tracks evolution of runtime data model.';
COMMENT ON COLUMN audit.schema_version.version_number IS
    'Sequential version number (1, 2, 3, ...). Incremented with each schema change.';
COMMENT ON COLUMN audit.schema_version.kb_version_aligned IS
    'KB version this schema version aligns to (e.g., "2026.10-governance").';

-- ============================================================================
-- TABLE 2: audit.ingestion_log
-- Track S3 ingestion operations
-- ============================================================================

CREATE TABLE audit.ingestion_log (
    ingestion_log_id SERIAL PRIMARY KEY,
    ingestion_run_id UUID NOT NULL UNIQUE,
    ingestion_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    s3_manifest_version VARCHAR(50) NOT NULL,
    s3_record_count INTEGER NOT NULL,
    s3_date_range_start DATE,
    s3_date_range_end DATE,
    raw_events_attempted INTEGER NOT NULL,
    raw_events_inserted INTEGER NOT NULL,
    raw_events_duplicate INTEGER DEFAULT 0,
    raw_events_failed INTEGER DEFAULT 0,
    simulator_extension_count INTEGER NOT NULL,
    claris_observed_count INTEGER NOT NULL,
    ingestion_status VARCHAR(50) NOT NULL,
    ingestion_notes TEXT,
    executed_by VARCHAR(100),

    CONSTRAINT ingestion_status_valid
        CHECK (ingestion_status IN ('started', 'completed', 'failed', 'rolled_back')),
    CONSTRAINT ingestion_counts_positive
        CHECK (raw_events_inserted >= 0 AND simulator_extension_count >= 0)
);

COMMENT ON TABLE audit.ingestion_log IS
    'Audit log for S3 ingestion operations. Tracks each bulk load attempt and result.';
COMMENT ON COLUMN audit.ingestion_log.ingestion_run_id IS
    'Unique identifier for this ingestion run. Enables idempotency tracking.';
COMMENT ON COLUMN audit.ingestion_log.simulator_extension_count IS
    'Count of records marked PROPOSED_SIMULATOR_EXTENSION (SKU-014, SKU-015).';

-- ============================================================================
-- TABLE 3: raw.raw_event
-- Lossless S3 ingestion landing
-- Purpose: Preserve original source payload + enable querying via typed columns
-- ============================================================================

CREATE TABLE raw.raw_event (
    -- Identity
    raw_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event classification
    event_type VARCHAR(100) NOT NULL,

    -- Timestamps (all three preserved independently)
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_at TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_date DATE GENERATED ALWAYS AS (DATE(arrival_at AT TIME ZONE 'UTC')) STORED NOT NULL,

    -- Actor information
    actor_id VARCHAR(200),
    actor_role VARCHAR(100),

    -- Source system provenance
    source_system VARCHAR(100) NOT NULL DEFAULT '',
    source_record_id VARCHAR(500),
    source_version INTEGER NOT NULL DEFAULT 1,

    -- Business object identifiers
    -- IMPORTANT: All identity fields are NULLABLE to support pre-S9 records (e.g., SKU-015)
    launch_id VARCHAR(100),
    con_id VARCHAR(100),
    prd_id VARCHAR(100),
    sku_id VARCHAR(100),
    material_id VARCHAR(100),
    configuration_id VARCHAR(100),

    -- Lineage & correlation
    correlation_id VARCHAR(500),
    causation_id UUID,

    -- Simulator extension classification (CRITICAL)
    simulator_classification VARCHAR(50),
    simulator_note TEXT,

    -- Original source payload (JSONB preserves fidelity)
    payload JSONB NOT NULL,

    -- Ingestion metadata
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ingestion_version INTEGER NOT NULL DEFAULT 1,

    -- Constraints
    CONSTRAINT raw_event_simulator_classification_valid
        CHECK (simulator_classification IN ('OBSERVED', 'PROPOSED_SIMULATOR_EXTENSION')
               OR simulator_classification IS NULL),
    CONSTRAINT raw_event_source_version_positive
        CHECK (source_version > 0),
    CONSTRAINT raw_event_ingestion_version_positive
        CHECK (ingestion_version > 0),
    CONSTRAINT raw_event_source_dedup
        UNIQUE (source_system, source_record_id, source_version)
);

COMMENT ON TABLE raw.raw_event IS
    'Immutable landing table for frozen S3 corpus (170 records). '
    'Preserves original payload + typed columns for querying. Append-only after initial ingestion.';
COMMENT ON COLUMN raw.raw_event.raw_event_id IS
    'Primary key UUID. Generated at ingestion.';
COMMENT ON COLUMN raw.raw_event.occurred_at IS
    'When the business/source event happened (from S3).';
COMMENT ON COLUMN raw.raw_event.recorded_at IS
    'When the source system persisted the fact (from S3).';
COMMENT ON COLUMN raw.raw_event.arrival_at IS
    'When the simulator/platform received the record (from S3). Used for historical replay: arrival_at <= decision_horizon.';
COMMENT ON COLUMN raw.raw_event.arrival_date IS
    'Generated column: DATE(arrival_at). Supports partition pruning if partitioned.';
COMMENT ON COLUMN raw.raw_event.sku_id IS
    'NULLABLE. Pre-S9 records (e.g., SKU-015 CONFIGURATION_REQUEST) have sku_id = NULL.';
COMMENT ON COLUMN raw.raw_event.material_id IS
    'NULLABLE. May not exist for pre-activation events.';
COMMENT ON COLUMN raw.raw_event.simulator_classification IS
    'Values: "OBSERVED" (Claris source), "PROPOSED_SIMULATOR_EXTENSION" (simulator extension), NULL (default). '
    'SKU-014 and SKU-015 marked PROPOSED_SIMULATOR_EXTENSION.';
COMMENT ON COLUMN raw.raw_event.payload IS
    'JSONB: Original source payload preserved exactly. Enables reconstruction of original S3 record.';
COMMENT ON CONSTRAINT raw_event_source_dedup ON raw.raw_event IS
    'Deduplication key: (source_system, source_record_id, source_version). '
    'Allows idempotent reingestion of same record (version incremented if source provides correction).';

-- Indexes on raw.raw_event (essential prototype indexes)
CREATE INDEX idx_raw_event_arrival_at ON raw.raw_event(arrival_at);
CREATE INDEX idx_raw_event_arrival_date ON raw.raw_event(arrival_date);
CREATE INDEX idx_raw_event_source_system ON raw.raw_event(source_system);
CREATE INDEX idx_raw_event_launch_id ON raw.raw_event(launch_id) WHERE launch_id IS NOT NULL;
CREATE INDEX idx_raw_event_configuration_id ON raw.raw_event(configuration_id) WHERE configuration_id IS NOT NULL;
CREATE INDEX idx_raw_event_sku_id ON raw.raw_event(sku_id) WHERE sku_id IS NOT NULL;
CREATE INDEX idx_raw_event_event_type ON raw.raw_event(event_type);
CREATE INDEX idx_raw_event_simulator ON raw.raw_event(simulator_classification) WHERE simulator_classification IS NOT NULL;

-- ============================================================================
-- TABLE 4: runtime.evidence
-- Runtime facts derived from raw source events
-- Purpose: Bridge between immutable raw facts and normalized assertions
-- ============================================================================

CREATE TABLE runtime.evidence (
    -- Identity
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source lineage (mandatory foreign key)
    raw_event_id UUID NOT NULL REFERENCES raw.raw_event(raw_event_id),

    -- Evidence classification
    evidence_type VARCHAR(100) NOT NULL,

    -- Subject (what this evidence is about)
    subject_type VARCHAR(100) NOT NULL,
    subject_id VARCHAR(200) NOT NULL,
    property_name VARCHAR(100) NOT NULL,

    -- Asserted value
    -- Design choice: Support strings, numbers, booleans, nulls, arrays, JSON structures
    -- Value stored as TEXT for display + value_type descriptor
    -- Structured values preserved in value_json JSONB
    asserted_value TEXT,
    value_type VARCHAR(50) NOT NULL,
    value_json JSONB,

    -- Source provenance
    source_system VARCHAR(100) NOT NULL,
    source_actor_id VARCHAR(200),
    source_actor_role VARCHAR(100),

    -- Timestamps (inherited from raw event)
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Simulator marking (inherited from raw event)
    simulator_classification VARCHAR(50),

    -- Derivation/lineage
    evidence_reason TEXT,
    evidence_lineage JSONB,

    -- Ingestion metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT evidence_value_type_valid
        CHECK (value_type IN ('string', 'integer', 'number', 'boolean', 'timestamp', 'json', 'null', 'array')),
    CONSTRAINT evidence_subject_property_arrival
        UNIQUE (subject_type, subject_id, property_name, arrival_at)
);

COMMENT ON TABLE runtime.evidence IS
    'Append-only runtime evidence derived from raw_event. '
    'One raw_event may produce multiple evidence facts. '
    'Supports multiple evidence facts for same subject/property at different timestamps (no forced uniqueness across time).';
COMMENT ON COLUMN runtime.evidence.evidence_id IS
    'Primary key UUID. Generated at evidence extraction.';
COMMENT ON COLUMN runtime.evidence.raw_event_id IS
    'Foreign key to raw.raw_event. Enables traceability back to source.';
COMMENT ON COLUMN runtime.evidence.evidence_type IS
    'Fine-grained evidence classification (e.g., "hierarchy_change_requested", "configuration_activated").';
COMMENT ON COLUMN runtime.evidence.value_type IS
    'Descriptor of value semantics. Enables later Fold logic to distinguish NULL (not reported) from explicit falsehood from undefined.';
COMMENT ON COLUMN runtime.evidence.value_json IS
    'For complex/structured values, preserve as JSONB (e.g., hierarchy change {from: H100, to: H200}).';
COMMENT ON COLUMN runtime.evidence.simulator_classification IS
    'Inherited from raw_event. Distinguishes PROPOSED_SIMULATOR_EXTENSION from OBSERVED.';
COMMENT ON CONSTRAINT evidence_subject_property_arrival ON runtime.evidence IS
    'Allows multiple evidence facts for same property at different arrival times, but not duplicates at same arrival time. '
    'Supports historical replay without overwriting.';

-- Indexes on runtime.evidence
CREATE INDEX idx_evidence_raw_event_id ON runtime.evidence(raw_event_id);
CREATE INDEX idx_evidence_subject ON runtime.evidence(subject_type, subject_id, property_name);
CREATE INDEX idx_evidence_subject_id ON runtime.evidence(subject_type, subject_id);
CREATE INDEX idx_evidence_arrival_at ON runtime.evidence(arrival_at);
CREATE INDEX idx_evidence_property_name ON runtime.evidence(property_name);

-- ============================================================================
-- TABLE 5: runtime.assertion
-- Append-only normalized claims about business objects
-- Purpose: Represent business facts after normalization and conflict resolution
-- ============================================================================

CREATE TABLE runtime.assertion (
    -- Identity
    assertion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Assertion classification
    assertion_type VARCHAR(100) NOT NULL,

    -- Subject/property/value triple
    subject_type VARCHAR(100) NOT NULL,
    subject_id VARCHAR(200) NOT NULL,
    property_name VARCHAR(100) NOT NULL,
    asserted_value TEXT,
    property_value_type VARCHAR(50) NOT NULL,
    property_value_json JSONB,

    -- Source lineage
    source_evidence_id UUID REFERENCES runtime.evidence(evidence_id),

    -- Assertion supersession (for update semantics without actual updates)
    -- New assertion may reference previous assertion if it supersedes it
    supersedes_assertion_id UUID REFERENCES runtime.assertion(assertion_id),

    -- Authority and governance
    authority VARCHAR(100) NOT NULL,
    authority_policy_id VARCHAR(200),

    -- Temporal scope
    effective_at TIMESTAMP WITH TIME ZONE NOT NULL,
    superseded_at TIMESTAMP WITH TIME ZONE,
    validity_horizon TIMESTAMP WITH TIME ZONE,
    arrival_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Simulator marking (inherited)
    simulator_classification VARCHAR(50),

    -- Ingestion metadata
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT assertion_property_value_type_valid
        CHECK (property_value_type IN ('string', 'integer', 'number', 'boolean', 'timestamp', 'json', 'null', 'array')),
    CONSTRAINT assertion_authority_valid
        CHECK (authority IN ('kb_rule', 'fold_computation', 'user_assertion', 'simulator_default', 'evidence_direct')),
    CONSTRAINT assertion_supersession_order
        CHECK (superseded_at IS NULL OR superseded_at > effective_at),
    CONSTRAINT assertion_no_circular_supersession
        CHECK (assertion_id != supersedes_assertion_id)
);

COMMENT ON TABLE runtime.assertion IS
    'Append-only normalized claims about business objects. '
    'Old assertions NOT deleted; marked superseded_at when replaced. '
    'Supports point-in-time queries via effective_at and arrival_at for historical replay.';
COMMENT ON COLUMN runtime.assertion.assertion_id IS
    'Primary key UUID. Generated at assertion normalization.';
COMMENT ON COLUMN runtime.assertion.source_evidence_id IS
    'Foreign key to runtime.evidence. NULL if assertion is synthetic (KB-derived).';
COMMENT ON COLUMN runtime.assertion.supersedes_assertion_id IS
    'If this assertion replaces a prior one, this FK points to the old assertion. '
    'Enables audit trail without in-place updates.';
COMMENT ON COLUMN runtime.assertion.authority IS
    'Source of authority for this claim: KB rule, Fold computation, simulator default, etc.';
COMMENT ON COLUMN runtime.assertion.effective_at IS
    'When this assertion became valid/active (typically arrival_at or fold horizon).';
COMMENT ON COLUMN runtime.assertion.superseded_at IS
    'When this assertion was replaced/retracted. NULL if still active.';
COMMENT ON COLUMN runtime.assertion.validity_horizon IS
    'When assertion expires (if time-bounded). Used by Fold to age out stale claims.';
COMMENT ON COLUMN runtime.assertion.arrival_at IS
    'Timestamp for replay filtering: "what was known at T?" uses arrival_at <= T.';
COMMENT ON TABLE runtime.assertion IS
    'Append-only assertions: multiple independent sources may produce '
    'contradictory assertions for same subject/property/effective_at. '
    'Both survive; Fold determines CONTRADICTED status.';

-- Indexes on runtime.assertion
CREATE INDEX idx_assertion_evidence_id ON runtime.assertion(source_evidence_id);
CREATE INDEX idx_assertion_supersedes_id ON runtime.assertion(supersedes_assertion_id);
CREATE INDEX idx_assertion_subject ON runtime.assertion(subject_type, subject_id, property_name);
CREATE INDEX idx_assertion_subject_property_effective ON runtime.assertion(subject_type, subject_id, property_name, effective_at);
CREATE INDEX idx_assertion_subject_id ON runtime.assertion(subject_type, subject_id);
CREATE INDEX idx_assertion_effective_at ON runtime.assertion(effective_at);
CREATE INDEX idx_assertion_arrival_at ON runtime.assertion(arrival_at);
CREATE INDEX idx_assertion_property ON runtime.assertion(property_name);

-- ============================================================================
-- TABLE 6: state.fold_state_snapshot
-- Materialized folded state at decision horizons
-- Purpose: Cache deterministic Fold output to avoid recomputation
-- ============================================================================

CREATE TABLE state.fold_state_snapshot (
    -- Identity
    fold_state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Decision horizon for this snapshot
    decision_horizon TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Subject being folded
    subject_type VARCHAR(100) NOT NULL,
    subject_id VARCHAR(200) NOT NULL,

    -- Folded result
    fold_status VARCHAR(50) NOT NULL,

    -- Materialized folded state
    -- Structure: property_name -> { status, value, confidence, metadata }
    -- Enables efficient queries without re-Fold computation
    folded_properties JSONB NOT NULL,

    -- Lineage: which assertions informed this Fold?
    basis_assertion_ids UUID[] NOT NULL,

    -- Governance
    kb_version VARCHAR(50) NOT NULL,
    policy_version VARCHAR(50) NOT NULL,

    -- Metadata
    fold_computed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT fold_status_valid
        CHECK (fold_status IN ('ESTABLISHED', 'UNREPORTED', 'EXPLICITLY_UNDEFINED', 'CONTRADICTED')),
    CONSTRAINT fold_temporal_order
        CHECK (fold_computed_at >= decision_horizon),
    CONSTRAINT fold_state_unique_horizon
        UNIQUE (decision_horizon, subject_type, subject_id)
);

COMMENT ON TABLE state.fold_state_snapshot IS
    'Materialized Fold snapshots at decision horizons. Immutable after creation. '
    'Append-only: new horizons added, past horizons never modified. '
    'Derived state, not a source of truth (source is runtime.assertion).';
COMMENT ON COLUMN state.fold_state_snapshot.fold_state_id IS
    'Primary key UUID.';
COMMENT ON COLUMN state.fold_state_snapshot.decision_horizon IS
    'Timestamp T: Fold computed for facts with arrival_at <= T.';
COMMENT ON COLUMN state.fold_state_snapshot.fold_status IS
    'ESTABLISHED: value confidently known. '
    'UNREPORTED: no evidence received for this property. '
    'EXPLICITLY_UNDEFINED: evidence explicitly states property is undefined. '
    'CONTRADICTED: conflicting evidence for same property (no single winner).';
COMMENT ON COLUMN state.fold_state_snapshot.folded_properties IS
    'JSONB structure preserving: { property_name: { status, value, contributing_assertions, ... } }. '
    'For CONTRADICTED: lists all conflicting values without choosing winner.';
COMMENT ON COLUMN state.fold_state_snapshot.basis_assertion_ids IS
    'UUID array: assertions that informed this Fold. Enables audit trail.';
COMMENT ON CONSTRAINT fold_state_unique_horizon ON state.fold_state_snapshot IS
    'At each decision_horizon, subject_type/subject_id has exactly one folded state. '
    'Prevents accidental duplicates; supports point-in-time queries.';

-- Indexes on state.fold_state_snapshot
CREATE UNIQUE INDEX idx_fold_state_horizon_subject
    ON state.fold_state_snapshot(decision_horizon, subject_type, subject_id);
CREATE INDEX idx_fold_state_subject_latest
    ON state.fold_state_snapshot(subject_type, subject_id, decision_horizon DESC);

-- ============================================================================
-- SCHEMA INITIALIZATION
-- ============================================================================

-- Record this schema version in audit table
INSERT INTO audit.schema_version
    (version_number, description, kb_version_aligned)
VALUES
    (1, 'Initial schema: raw → evidence → assertion → fold_state. S3 frozen corpus (170 records).', '2026.10-governance');

