-- ============================================================================
-- CLARIS v0.5 PostgreSQL Runtime Architecture
-- PHASE 3: DECISION EXECUTION LOGIC
-- ============================================================================
-- Implements decision execution with ontology-governed outcomes
-- Validates decision.outcome_code against decision_type + KB/policy versions
-- Provides audit trail and lineage to evidence
-- ============================================================================

BEGIN;

-- ============================================================================
-- TABLE: ontology.decision_outputs (NEW)
-- ============================================================================
-- Registry of valid outcomes for each decision type
-- Governs: decision.outcome_code values
-- Enables: Application-layer validation of (decision_type, outcome_code)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ontology.decision_outputs (
  output_id             VARCHAR(64) PRIMARY KEY,
  decision_type         VARCHAR(64) NOT NULL,
  outcome_code          VARCHAR(64) NOT NULL,
  outcome_label         VARCHAR(256),
  description           TEXT,

  -- Version tracking
  kb_version            VARCHAR(16),
  policy_version        VARCHAR(16),
  effective_from        TIMESTAMPTZ,
  effective_to          TIMESTAMPTZ,

  -- Metadata
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Constraint: unique per (decision_type, outcome_code, kb_version, policy_version)
  UNIQUE (decision_type, outcome_code, kb_version, policy_version),

  FOREIGN KEY (kb_version) REFERENCES ontology.kb_versions(kb_version),
  FOREIGN KEY (policy_version) REFERENCES ontology.policy_versions(policy_version)
);

CREATE INDEX IF NOT EXISTS idx_decision_outputs_type_code
  ON ontology.decision_outputs(decision_type, outcome_code);

CREATE INDEX IF NOT EXISTS idx_decision_outputs_version
  ON ontology.decision_outputs(kb_version, policy_version);

-- ============================================================================
-- FUNCTION: is_valid_outcome()
-- ============================================================================
-- Validates that (decision_type, outcome_code) is valid per ontology
-- Returns: true if outcome is valid for this decision_type
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.is_valid_outcome(
  p_decision_type VARCHAR(64),
  p_outcome_code VARCHAR(64),
  p_kb_version VARCHAR(16) DEFAULT NULL,
  p_policy_version VARCHAR(16) DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM ontology.decision_outputs
    WHERE decision_type = p_decision_type
      AND outcome_code = p_outcome_code
      AND (p_kb_version IS NULL OR kb_version = p_kb_version)
      AND (p_policy_version IS NULL OR policy_version = p_policy_version)
      AND (effective_from IS NULL OR effective_from <= NOW())
      AND (effective_to IS NULL OR effective_to > NOW())
  );
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- FUNCTION: execute_decision()
-- ============================================================================
-- Executes a decision for a configuration_version
--
-- Parameters:
--   p_configuration_version_id: version to decide on
--   p_decision_type: e.g., 'IDENTITY_ASSESSMENT', 'LAUNCH_READINESS'
--   p_outcome_code: e.g., 'READY_FOR_LAUNCH', 'CANNOT_DECIDE'
--   p_kb_version: KB version used for decision
--   p_policy_version: Policy version used for decision
--   p_horizon_as_of: Evidence visibility horizon
--   p_reason_code: Optional reason code
--   p_decided_by: User/system that made decision
--   p_confidence_level: Optional confidence assessment
--   p_missing_evidence: Array of missing evidence labels
--   p_blocking_evidence: Array of blocking evidence labels
--
-- Returns: (decision_id, outcome_code, state, decided_at)
--
-- Behavior:
--   1. Validates outcome_code is valid for decision_type
--   2. Runs fold to get current state
--   3. Creates decision record (immutable)
--   4. Links evidence via decision_evidence
--   5. Marks prior decisions as superseded
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.execute_decision(
  p_configuration_version_id VARCHAR(64),
  p_decision_type VARCHAR(64),
  p_outcome_code VARCHAR(64),
  p_kb_version VARCHAR(16),
  p_policy_version VARCHAR(16),
  p_horizon_as_of TIMESTAMPTZ,
  p_reason_code VARCHAR(256) DEFAULT NULL,
  p_decided_by VARCHAR(128) DEFAULT 'SYSTEM',
  p_confidence_level VARCHAR(32) DEFAULT NULL,
  p_missing_evidence TEXT[] DEFAULT NULL,
  p_blocking_evidence TEXT[] DEFAULT NULL
)
RETURNS TABLE (
  decision_id UUID,
  outcome_code VARCHAR(64),
  state VARCHAR(32),
  decided_at TIMESTAMPTZ
) AS $$
DECLARE
  v_decision_id UUID;
  v_input_digest VARCHAR(32);
  v_is_valid BOOLEAN;
  v_evidence_row RECORD;
BEGIN
  -- Step 1: Validate outcome is valid for this decision_type
  v_is_valid := claris.is_valid_outcome(
    p_decision_type,
    p_outcome_code,
    p_kb_version,
    p_policy_version
  );

  IF NOT v_is_valid THEN
    RAISE EXCEPTION 'Invalid outcome (%, %) for KB % / Policy %',
      p_decision_type, p_outcome_code, p_kb_version, p_policy_version;
  END IF;

  -- Step 2: Calculate input digest (for reproducibility)
  v_input_digest := MD5(
    p_configuration_version_id ||
    p_decision_type ||
    p_kb_version ||
    p_policy_version ||
    p_horizon_as_of::text
  );

  -- Step 3: Generate decision record
  v_decision_id := gen_random_uuid();

  INSERT INTO claris.decision (
    decision_id,
    decision_type,
    subject_type,
    subject_id,
    outcome_code,
    reason_code,
    policy_version,
    kb_version,
    horizon_as_of,
    input_digest,
    decided_by,
    decided_at,
    confidence_level,
    missing_evidence,
    blocking_evidence,
    state,
    data_classification
  ) VALUES (
    v_decision_id,
    p_decision_type,
    'configuration_version',
    p_configuration_version_id,
    p_outcome_code,
    p_reason_code,
    p_policy_version,
    p_kb_version,
    p_horizon_as_of,
    v_input_digest,
    p_decided_by,
    NOW(),
    p_confidence_level,
    p_missing_evidence,
    p_blocking_evidence,
    'current',
    'INTERNAL'
  );

  -- Step 4: Link evidence (fold result) to decision
  FOR v_evidence_row IN
    SELECT fs.dimension_id, fs.folded_value, UNNEST(fs.evidence_ids) as evidence_id
    FROM claris.fold_configuration_state(p_configuration_version_id, p_horizon_as_of) fs
    WHERE fs.evidence_ids IS NOT NULL
  LOOP
    INSERT INTO claris.decision_evidence (
      decision_id,
      evidence_id,
      role
    ) VALUES (
      v_decision_id,
      v_evidence_row.evidence_id,
      'INPUT'
    )
    ON CONFLICT (decision_id, evidence_id, role) DO NOTHING;
  END LOOP;

  -- Step 5: Supersede prior decisions of same type for this version
  UPDATE claris.decision d_old
  SET
    state = 'superseded',
    superseded_by = v_decision_id,
    superseded_at = NOW()
  WHERE d_old.subject_type = 'configuration_version'
    AND d_old.subject_id = p_configuration_version_id
    AND d_old.decision_type = p_decision_type
    AND d_old.state = 'current'
    AND d_old.decision_id != v_decision_id;

  -- Step 6: Return result
  decision_id := v_decision_id;
  outcome_code := p_outcome_code;
  state := 'current';
  decided_at := NOW();
  RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: get_decision_state()
-- ============================================================================
-- Returns current decision for a configuration_version + decision_type
-- Useful for application layer to check "what did we decide?"
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.get_decision_state(
  p_configuration_version_id VARCHAR(64),
  p_decision_type VARCHAR(64)
)
RETURNS TABLE (
  decision_id UUID,
  outcome_code VARCHAR(64),
  reason_code VARCHAR(256),
  confidence_level VARCHAR(32),
  decided_by VARCHAR(128),
  decided_at TIMESTAMPTZ,
  state VARCHAR(32)
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.decision_id,
    d.outcome_code,
    d.reason_code,
    d.confidence_level,
    d.decided_by,
    d.decided_at,
    d.state
  FROM claris.decision d
  WHERE d.subject_type = 'configuration_version'
    AND d.subject_id = p_configuration_version_id
    AND d.decision_type = p_decision_type
    AND d.state = 'current'
  ORDER BY d.decided_at DESC
  LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- FUNCTION: replay_decision()
-- ============================================================================
-- Re-executes a decision at a different horizon (time travel)
-- Useful for: "What would decision have been at earlier time?"
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.replay_decision(
  p_decision_id UUID,
  p_new_horizon_as_of TIMESTAMPTZ
)
RETURNS TABLE (
  replayed_decision_id UUID,
  original_decision_id UUID,
  outcome_code VARCHAR(64),
  horizon_as_of TIMESTAMPTZ,
  input_digest VARCHAR(32)
) AS $$
DECLARE
  v_original_decision RECORD;
  v_replayed_id UUID;
BEGIN
  -- Get original decision
  SELECT * INTO v_original_decision
  FROM claris.decision
  WHERE decision_id = p_decision_id;

  IF v_original_decision IS NULL THEN
    RAISE EXCEPTION 'Decision % not found', p_decision_id;
  END IF;

  -- Re-execute with new horizon
  SELECT ed.decision_id INTO v_replayed_id
  FROM claris.execute_decision(
    v_original_decision.subject_id,
    v_original_decision.decision_type,
    v_original_decision.outcome_code,
    v_original_decision.kb_version,
    v_original_decision.policy_version,
    p_new_horizon_as_of,
    v_original_decision.reason_code,
    v_original_decision.decided_by,
    v_original_decision.confidence_level,
    v_original_decision.missing_evidence,
    v_original_decision.blocking_evidence
  ) ed;

  -- Return both original and replayed
  replayed_decision_id := v_replayed_id;
  original_decision_id := p_decision_id;
  outcome_code := v_original_decision.outcome_code;
  horizon_as_of := p_new_horizon_as_of;
  input_digest := MD5(
    v_original_decision.subject_id ||
    v_original_decision.decision_type ||
    v_original_decision.kb_version ||
    v_original_decision.policy_version ||
    p_new_horizon_as_of::text
  );
  RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: get_decision_lineage()
-- ============================================================================
-- Returns complete lineage: decision → evidence → assertions
-- Useful for audit & compliance
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.get_decision_lineage(
  p_decision_id UUID
)
RETURNS TABLE (
  evidence_id VARCHAR(256),
  evidence_role VARCHAR(32),
  assertion_count INT,
  evidence_source VARCHAR(128)
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    de.evidence_id,
    de.role,
    COUNT(DISTINCT ca.assertion_id)::INT,
    MAX(ca.source_system)
  FROM claris.decision_evidence de
  LEFT JOIN claris.configuration_assertion ca ON ca.evidence_id = de.evidence_id
  WHERE de.decision_id = p_decision_id
  GROUP BY de.evidence_id, de.role;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- PERFORMANCE INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_decision_subject ON claris.decision(subject_type, subject_id, state);
CREATE INDEX IF NOT EXISTS idx_decision_type_state ON claris.decision(decision_type, state);
CREATE INDEX IF NOT EXISTS idx_decision_superseded ON claris.decision(superseded_by);
CREATE INDEX IF NOT EXISTS idx_decision_decided_at ON claris.decision(decided_at DESC);

-- ============================================================================
-- VIEWS: Decision Summary
-- ============================================================================

CREATE OR REPLACE VIEW claris.decision_summary AS
SELECT
  d.decision_id,
  d.decision_type,
  d.subject_id,
  d.outcome_code,
  d.state,
  d.decided_by,
  d.decided_at,
  COUNT(DISTINCT de.evidence_id) as evidence_count,
  d.confidence_level
FROM claris.decision d
LEFT JOIN claris.decision_evidence de ON de.decision_id = d.decision_id
GROUP BY d.decision_id, d.decision_type, d.subject_id, d.outcome_code,
         d.state, d.decided_by, d.decided_at, d.confidence_level;

-- ============================================================================
-- END OF DECISION EXECUTION LAYER
-- ============================================================================

COMMIT;

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================
--
-- Example 1: Populate decision_outputs ontology
-- INSERT INTO ontology.decision_outputs (
--   output_id, decision_type, outcome_code, outcome_label, kb_version, policy_version
-- ) VALUES (
--   'out_001', 'IDENTITY_ASSESSMENT', 'READY_FOR_LAUNCH', 'Ready for launch', '1.0', '1.0'
-- );
--
-- Example 2: Execute a decision
-- SELECT * FROM claris.execute_decision(
--   'version_001',                    -- configuration_version_id
--   'IDENTITY_ASSESSMENT',            -- decision_type
--   'READY_FOR_LAUNCH',               -- outcome_code
--   '1.0',                            -- kb_version
--   '1.0',                            -- policy_version
--   NOW(),                            -- horizon_as_of
--   'All dimensions established',     -- reason_code
--   'service_identity_assessment',    -- decided_by
--   '0.95'                            -- confidence_level
-- );
--
-- Example 3: Get current decision
-- SELECT * FROM claris.get_decision_state('version_001', 'IDENTITY_ASSESSMENT');
--
-- Example 4: Get decision lineage
-- SELECT * FROM claris.get_decision_lineage('decision_uuid_here');
--
-- Example 5: View decision summary
-- SELECT * FROM claris.decision_summary WHERE state = 'current';
--
-- ============================================================================
-- VERIFICATION AFTER DEPLOYMENT
-- ============================================================================
--
-- SELECT * FROM ontology.decision_outputs LIMIT 5;
-- SELECT proname FROM pg_proc WHERE proname LIKE 'execute_decision%';
-- SELECT * FROM claris.decision_summary;
--
-- ============================================================================
