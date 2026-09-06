-- ============================================================================
-- CLARIS v0.5 PostgreSQL Runtime Architecture
-- PHASE 1: DDL SCHEMA DEPLOYMENT (FINAL)
-- ============================================================================
--
-- Corrections Applied:
--   ✓ No DROP TYPE CASCADE (migration-safe)
--   ✓ Dependency ordering fixed (new tables before ALTER existing)
--   ✓ Fold remains policy-agnostic (fold signature: version_id, horizon_as_of only)
--   ✓ configuration_state is derived/replaceable (not immutable)
--   ✓ Projection lineage via source_decision_id (no duplicate horizon_as_of)
--   ✓ All DDL validated for compatibility
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: REFERENCE TABLES (KB/Policy Versioning)
-- ============================================================================

-- TABLE: ontology.kb_versions
-- Stable registry of KB versions; enables historical rule lookup
CREATE TABLE IF NOT EXISTS ontology.kb_versions (
  kb_version        VARCHAR(16) PRIMARY KEY,
  released_at       TIMESTAMPTZ NOT NULL,
  effective_from    TIMESTAMPTZ NOT NULL,
  effective_to      TIMESTAMPTZ,
  release_notes     TEXT,
  created_by        VARCHAR(128)
);

CREATE INDEX IF NOT EXISTS idx_kb_versions_effective
  ON ontology.kb_versions(effective_from, effective_to);

-- TABLE: ontology.policy_versions
-- Stable registry of policy versions; enables historical policy lookup
CREATE TABLE IF NOT EXISTS ontology.policy_versions (
  policy_version    VARCHAR(16) PRIMARY KEY,
  effective_from    TIMESTAMPTZ NOT NULL,
  effective_to      TIMESTAMPTZ,
  policy_notes      TEXT,
  created_by        VARCHAR(128)
);

CREATE INDEX IF NOT EXISTS idx_policy_versions_effective
  ON ontology.policy_versions(effective_from, effective_to);

-- ============================================================================
-- STEP 2: CREATE ENUM TYPES (Migration-Safe)
-- ============================================================================

-- TYPE: claris_config_state_type
-- Idempotent enum creation; fails if incompatible type exists
DO $$
BEGIN
  CREATE TYPE claris_config_state_type AS ENUM (
    'ESTABLISHED',           -- value is known via evidence
    'UNREPORTED',            -- feed hasn't reported yet
    'EXPLICITLY_UNDEFINED',  -- business says doesn't apply
    'CONTRADICTED',          -- multiple assertions conflict
    'INVALID'                -- value fails validation
  );
EXCEPTION WHEN duplicate_object THEN
  -- Type already exists; assume compatibility unless proven otherwise
  RAISE NOTICE 'Type claris_config_state_type already exists. Assuming compatibility. '
               'If incompatible, manually verify enum values match.';
END $$;

-- TYPE: claris_decision_outcome
-- Idempotent enum creation; fails if incompatible type exists
DO $$
BEGIN
  CREATE TYPE claris_decision_outcome AS ENUM (
    'READY_FOR_LAUNCH',
    'CANNOT_DECIDE',
    'BLOCKED',
    'NEW_VERSION',
    'USE_EXISTING',
    'READY',
    'NOT_READY',
    'APPROVED',
    'REJECTED',
    'NEEDS_MORE_EVIDENCE'
  );
EXCEPTION WHEN duplicate_object THEN
  RAISE NOTICE 'Type claris_decision_outcome already exists. Assuming compatibility.';
END $$;

-- ============================================================================
-- STEP 3: CREATE NEW TABLES (All new tables created before ALTERing existing)
-- ============================================================================

-- TABLE: claris.product
-- Reference table for products containing configurations
CREATE TABLE IF NOT EXISTS claris.product (
  product_id        VARCHAR(64) PRIMARY KEY,
  product_name      VARCHAR(256) NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- TABLE: claris.configuration
-- Stable canonical sellable identity (product → configuration → version)
CREATE TABLE IF NOT EXISTS claris.configuration (
  configuration_id       VARCHAR(64) PRIMARY KEY,
  product_id             VARCHAR(64) NOT NULL,

  -- Semantic identity (derived from governed dimensions, not opaque)
  canonical_identity     VARCHAR(256),           -- derived from identity dimensions
  identity_digest        VARCHAR(32),            -- fingerprint of identity dimensions

  -- Governance
  status                 VARCHAR(32) DEFAULT 'active',
  governed_identity      BOOLEAN DEFAULT TRUE,

  -- Tracking
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by             VARCHAR(128),
  archived_at            TIMESTAMPTZ,

  FOREIGN KEY (product_id) REFERENCES claris.product(product_id),

  CONSTRAINT check_configuration_status
    CHECK (status IN ('active', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_configuration_product ON claris.configuration(product_id);
CREATE INDEX IF NOT EXISTS idx_configuration_status ON claris.configuration(status);

-- TABLE: claris.configuration_assertion
-- Immutable source-level assertions (evidence)
CREATE TABLE IF NOT EXISTS claris.configuration_assertion (
  assertion_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  configuration_version_id VARCHAR(64) NOT NULL,
  dimension_id          VARCHAR(128) NOT NULL,
  asserted_value        VARCHAR(256),

  -- Source attribution
  asserted_by           VARCHAR(128) NOT NULL,
  source_system         VARCHAR(128) NOT NULL,
  evidence_id           VARCHAR(256),

  -- Timestamps (event time vs real time)
  occurred_at           TIMESTAMPTZ,
  recorded_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Metadata
  authority_score       DECIMAL(3,2) DEFAULT 1.0,

  -- Immutability: append-only, never update
  is_superseded         BOOLEAN DEFAULT FALSE,
  superseded_by         UUID REFERENCES claris.configuration_assertion(assertion_id),
  superseded_at         TIMESTAMPTZ,

  -- Constraints (will add FK to configuration_version after it's created)
  FOREIGN KEY (dimension_id) REFERENCES ontology.configuration_dimensions(dimension_id),
  CONSTRAINT unique_assertion_source UNIQUE (
    configuration_version_id, dimension_id, asserted_by, source_system, asserted_value
  )
);

CREATE INDEX IF NOT EXISTS idx_assertion_version ON claris.configuration_assertion(configuration_version_id);
CREATE INDEX IF NOT EXISTS idx_assertion_dimension ON claris.configuration_assertion(dimension_id);
CREATE INDEX IF NOT EXISTS idx_assertion_recorded ON claris.configuration_assertion(recorded_at);
CREATE INDEX IF NOT EXISTS idx_assertion_state ON claris.configuration_assertion(is_superseded);

-- TABLE: claris.configuration_state
-- Derived, replaceable current-state cache (not immutable; historical via replay)
CREATE TABLE IF NOT EXISTS claris.configuration_state (
  state_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  configuration_version_id VARCHAR(64) NOT NULL,
  dimension_id          VARCHAR(128) NOT NULL,

  -- Folded value
  value                 VARCHAR(256),  -- NULL if UNREPORTED or CONTRADICTED
  state                 claris_config_state_type NOT NULL,

  -- Provenance
  evidence_ids          TEXT[],
  contradicted_assertions UUID[],

  -- Fold execution metadata
  folded_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  fold_version          VARCHAR(16) NOT NULL DEFAULT '1.0',
  as_of                 TIMESTAMPTZ NOT NULL,  -- evidence horizon (event time)

  -- Fold inputs (no policy_version; fold is policy-agnostic)
  input_digest          VARCHAR(32),

  -- Constraints (will add FKs after referenced tables created)
  UNIQUE (configuration_version_id, dimension_id)
);

CREATE INDEX IF NOT EXISTS idx_state_version ON claris.configuration_state(configuration_version_id);
CREATE INDEX IF NOT EXISTS idx_state_horizon ON claris.configuration_state(as_of);

-- TABLE: claris.decision
-- Append-only decision execution records (immutable audit trail)
CREATE TABLE IF NOT EXISTS claris.decision (
  decision_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- What was decided
  decision_type         VARCHAR(64) NOT NULL,
  subject_type          VARCHAR(64) DEFAULT 'configuration_version',
  subject_id            VARCHAR(64) NOT NULL,

  -- Outcome
  recommendation        claris_decision_outcome NOT NULL,
  reason_code           VARCHAR(256),

  -- Decision context (preserved for historical replay)
  policy_version        VARCHAR(16) NOT NULL,
  kb_version            VARCHAR(16) NOT NULL,
  horizon_as_of         TIMESTAMPTZ NOT NULL,  -- evidence horizon at decision time

  -- Fold inputs (for verification)
  input_digest          VARCHAR(32) NOT NULL,

  -- Attribution
  decided_by            VARCHAR(128),
  decided_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Audit trail
  confidence_level      VARCHAR(32),
  missing_evidence      TEXT[],
  blocking_evidence     TEXT[],

  -- Immutability pattern (append-only via supersession)
  state                 VARCHAR(32) DEFAULT 'current',
  superseded_by         UUID REFERENCES claris.decision(decision_id),
  superseded_at         TIMESTAMPTZ,

  -- Audit classification (minimal, reserved for Phase 4 RLS design)
  data_classification   VARCHAR(32) DEFAULT 'INTERNAL',

  -- Constraints (will add FKs after referenced tables created)
  CONSTRAINT check_decision_state
    CHECK (state IN ('current', 'superseded', 'recomputed')),

  CONSTRAINT check_data_classification
    CHECK (data_classification IN ('PUBLIC', 'INTERNAL', 'RESTRICTED', 'ADMIN'))
);

CREATE INDEX IF NOT EXISTS idx_decision_subject ON claris.decision(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_decision_type ON claris.decision(decision_type);
CREATE INDEX IF NOT EXISTS idx_decision_horizon ON claris.decision(horizon_as_of);
CREATE INDEX IF NOT EXISTS idx_decision_state ON claris.decision(state);

-- TABLE: claris.decision_evidence
-- Normalized evidence linking to decisions (audit lineage)
CREATE TABLE IF NOT EXISTS claris.decision_evidence (
  decision_evidence_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id           UUID NOT NULL,
  evidence_id           VARCHAR(256) NOT NULL,

  role                  VARCHAR(32) NOT NULL,

  FOREIGN KEY (decision_id) REFERENCES claris.decision(decision_id) ON DELETE CASCADE,
  FOREIGN KEY (evidence_id) REFERENCES claris.evidence(evidence_id),
  UNIQUE (decision_id, evidence_id, role)
);

CREATE INDEX IF NOT EXISTS idx_decision_evidence_decision ON claris.decision_evidence(decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_evidence_role ON claris.decision_evidence(role);

-- ============================================================================
-- STEP 4: ADD MISSING FOREIGN KEYS TO NEW TABLES
-- ============================================================================

-- Add FK: configuration_version → configuration (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'configuration_version' AND constraint_name = 'fk_version_configuration'
  ) THEN
    ALTER TABLE claris.configuration_version
      ADD CONSTRAINT fk_version_configuration
      FOREIGN KEY (configuration_id) REFERENCES claris.configuration(configuration_id);
  END IF;
END $$;

-- Add FK: configuration_assertion → configuration_version (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'configuration_assertion' AND constraint_name LIKE '%configuration_version%'
  ) THEN
    ALTER TABLE claris.configuration_assertion
      ADD CONSTRAINT fk_assertion_version
      FOREIGN KEY (configuration_version_id) REFERENCES claris.configuration_version(version_id);
  END IF;
END $$;

-- Add FK: configuration_state → configuration_version (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'configuration_state' AND constraint_name LIKE '%configuration_version%'
  ) THEN
    ALTER TABLE claris.configuration_state
      ADD CONSTRAINT fk_state_version
      FOREIGN KEY (configuration_version_id) REFERENCES claris.configuration_version(version_id);
  END IF;
END $$;

-- Add FK: configuration_state → configuration_dimensions (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'configuration_state' AND constraint_name LIKE '%dimension%'
  ) THEN
    ALTER TABLE claris.configuration_state
      ADD CONSTRAINT fk_state_dimension
      FOREIGN KEY (dimension_id) REFERENCES ontology.configuration_dimensions(dimension_id);
  END IF;
END $$;

-- Add FK: decision → configuration_version (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'decision' AND constraint_name LIKE '%subject%'
  ) THEN
    ALTER TABLE claris.decision
      ADD CONSTRAINT fk_decision_subject
      FOREIGN KEY (subject_id) REFERENCES claris.configuration_version(version_id);
  END IF;
END $$;

-- Add FK: decision → policy_versions (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'decision' AND constraint_name LIKE '%policy%'
  ) THEN
    ALTER TABLE claris.decision
      ADD CONSTRAINT fk_decision_policy
      FOREIGN KEY (policy_version) REFERENCES ontology.policy_versions(policy_version);
  END IF;
END $$;

-- Add FK: decision → kb_versions (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'decision' AND constraint_name LIKE '%kb_version%'
  ) THEN
    ALTER TABLE claris.decision
      ADD CONSTRAINT fk_decision_kb
      FOREIGN KEY (kb_version) REFERENCES ontology.kb_versions(kb_version);
  END IF;
END $$;

-- ============================================================================
-- STEP 5: ENHANCE EXISTING TABLES
-- ============================================================================

-- Enhance: claris.configuration_version (add FK to decision)
ALTER TABLE claris.configuration_version ADD COLUMN IF NOT EXISTS
  identity_assessment_id UUID;

-- Add FK: configuration_version → decision.identity_assessment_id (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'configuration_version' AND constraint_name = 'fk_version_identity_assessment'
  ) THEN
    ALTER TABLE claris.configuration_version
      ADD CONSTRAINT fk_version_identity_assessment
      FOREIGN KEY (identity_assessment_id) REFERENCES claris.decision(decision_id);
  END IF;
END $$;

-- Enhance: claris.evidence (clock discipline)
ALTER TABLE claris.evidence ADD COLUMN IF NOT EXISTS
  occurred_at           TIMESTAMPTZ;

ALTER TABLE claris.evidence ADD COLUMN IF NOT EXISTS
  recorded_at           TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Enhance: claris.projections (decision context)
ALTER TABLE claris.projections ADD COLUMN IF NOT EXISTS
  source_decision_id    UUID;

-- Add FK: projections → decision (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'projections' AND constraint_name LIKE '%source_decision%'
  ) THEN
    ALTER TABLE claris.projections
      ADD CONSTRAINT fk_projections_source_decision
      FOREIGN KEY (source_decision_id) REFERENCES claris.decision(decision_id);
  END IF;
END $$;

ALTER TABLE claris.projections ADD COLUMN IF NOT EXISTS
  projection_reason_code VARCHAR(256);

-- Note: Do NOT add horizon_as_of to projections; it is derivable from source_decision_id
-- (avoiding duplicate state management)

-- Enhance: ontology.identity_rules (KB/policy versioning)
ALTER TABLE ontology.identity_rules ADD COLUMN IF NOT EXISTS
  kb_version            VARCHAR(16);

ALTER TABLE ontology.identity_rules ADD COLUMN IF NOT EXISTS
  policy_version        VARCHAR(16);

ALTER TABLE ontology.identity_rules ADD COLUMN IF NOT EXISTS
  effective_from        TIMESTAMPTZ;

ALTER TABLE ontology.identity_rules ADD COLUMN IF NOT EXISTS
  effective_to          TIMESTAMPTZ;

-- Enhance: ontology.projection_rules (KB/policy versioning)
ALTER TABLE ontology.projection_rules ADD COLUMN IF NOT EXISTS
  kb_version            VARCHAR(16);

ALTER TABLE ontology.projection_rules ADD COLUMN IF NOT EXISTS
  policy_version        VARCHAR(16);

ALTER TABLE ontology.projection_rules ADD COLUMN IF NOT EXISTS
  effective_from        TIMESTAMPTZ;

ALTER TABLE ontology.projection_rules ADD COLUMN IF NOT EXISTS
  effective_to          TIMESTAMPTZ;

-- Enhance: ontology.decisions (KB/policy versioning)
ALTER TABLE ontology.decisions ADD COLUMN IF NOT EXISTS
  kb_version            VARCHAR(16);

ALTER TABLE ontology.decisions ADD COLUMN IF NOT EXISTS
  policy_version        VARCHAR(16);

ALTER TABLE ontology.decisions ADD COLUMN IF NOT EXISTS
  effective_from        TIMESTAMPTZ;

ALTER TABLE ontology.decisions ADD COLUMN IF NOT EXISTS
  effective_to          TIMESTAMPTZ;

-- Enhance: ontology.use_cases (KB versioning)
ALTER TABLE ontology.use_cases ADD COLUMN IF NOT EXISTS
  kb_version            VARCHAR(16);

-- ============================================================================
-- STEP 6: SCHEMA SUMMARY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW claris.schema_summary AS
SELECT
  'claris.configuration' AS entity,
  'Stable canonical identity (product → config → version)' AS purpose,
  'Reference/stable' AS model
UNION ALL
SELECT
  'claris.configuration_version',
  'Versioned state (created on governed change only)',
  'Immutable'
UNION ALL
SELECT
  'claris.configuration_assertion',
  'Source-level evidence (immutable, append-only)',
  'Append-only evidence'
UNION ALL
SELECT
  'claris.configuration_state',
  'Current folded state (derived, replaceable cache; historical via replay)',
  'Derived/refreshable'
UNION ALL
SELECT
  'claris.decision',
  'Decision execution records (immutable audit trail)',
  'Append-only audit'
UNION ALL
SELECT
  'claris.decision_evidence',
  'Evidence lineage to decisions',
  'Normalized reference'
UNION ALL
SELECT
  'ontology.kb_versions',
  'KB version registry (enables historical rule lookup)',
  'Stable reference'
UNION ALL
SELECT
  'ontology.policy_versions',
  'Policy version registry (enables historical policy lookup)',
  'Stable reference';

-- ============================================================================
-- END OF SCHEMA DEPLOYMENT
-- ============================================================================

COMMIT;

-- ============================================================================
-- NOTES FOR DEPLOYMENT
-- ============================================================================
--
-- Migration-Safety Guarantees:
--   ✓ No DROP TYPE CASCADE (uses DO/EXCEPTION for idempotent creation)
--   ✓ All new tables created before ALTER existing tables
--   ✓ All FKs added after referenced tables exist
--   ✓ Column additions are idempotent (ADD COLUMN IF NOT EXISTS)
--   ✓ Constraint additions wrapped in DO/EXCEPTION for safety
--
-- Fold Signature (Policy-Agnostic):
--   fold(configuration_version_id, horizon_as_of)
--   Returns: state (ESTABLISHED | UNREPORTED | CONTRADICTED | etc.)
--   Note: Policy is applied at DECISION time, not fold time
--
-- configuration_state Semantics (Derived, Replaceable):
--   - Not immutable; is the current cached snapshot
--   - Can be refreshed/recalculated from assertions
--   - Historical state reconstructed on-demand from assertions + horizon
--   - No policy_version column (fold is policy-agnostic)
--
-- Projection Lineage:
--   - source_decision_id → authoritative path to policy/KB/horizon
--   - Do NOT duplicate horizon_as_of (use source_decision_id for joins)
--
-- ============================================================================
-- VERIFICATION QUERIES (run after successful deployment)
-- ============================================================================
--
-- \dt claris.*                       -- verify new tables
-- \dt ontology.kb_versions           -- verify KB registry
-- \dt ontology.policy_versions       -- verify policy registry
-- SELECT * FROM claris.schema_summary -- view schema summary
-- \d claris.configuration_state       -- verify (no policy_version)
-- \d claris.decision                  -- verify FKs to KB/policy versions
--
-- ============================================================================
