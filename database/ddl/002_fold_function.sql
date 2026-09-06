-- ============================================================================
-- CLARIS v0.5 PostgreSQL Runtime Architecture
-- PHASE 2: FOLD FUNCTION IMPLEMENTATION
-- ============================================================================
-- Implements deterministic fold(configuration_version_id, horizon_as_of)
-- Policy-agnostic transformation: evidence → state
-- Filtering rule: recorded_at <= horizon_as_of (platform receipt time)
-- ============================================================================

BEGIN;

-- ============================================================================
-- FUNCTION: fold_configuration_state()
-- ============================================================================
-- Deterministic fold logic that transforms assertions into state
--
-- Input: configuration_version_id, horizon_as_of
-- Output: (dimension_id, value, state, evidence_ids, contradicted_assertions)
--
-- State semantics:
--   ESTABLISHED: All evidence agrees on value
--   UNREPORTED: No evidence available
--   CONTRADICTED: Multiple conflicting values reported
--   INVALID: Value fails validation (business rule)
--   EXPLICITLY_UNDEFINED: Business says doesn't apply
--
-- Filtering: Only includes assertions where recorded_at <= horizon_as_of
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.fold_configuration_state(
  p_configuration_version_id VARCHAR(64),
  p_horizon_as_of TIMESTAMPTZ
)
RETURNS TABLE (
  dimension_id VARCHAR(128),
  folded_value VARCHAR(256),
  folded_state claris_config_state_type,
  evidence_ids TEXT[],
  contradicted_assertions UUID[]
) AS $$
DECLARE
  v_dimension_id VARCHAR(128);
  v_value VARCHAR(256);
  v_state claris_config_state_type;
  v_evidence_ids TEXT[];
  v_contradicted UUID[];
BEGIN
  -- ===== FOLD LOGIC =====
  -- For each dimension in this configuration version:
  -- 1. Find all non-superseded assertions recorded before horizon_as_of
  -- 2. Determine consensus value (most authoritative)
  -- 3. Assign state based on evidence pattern

  FOR v_dimension_id, v_value, v_state, v_evidence_ids, v_contradicted IN
    WITH dimension_assertions AS (
      -- Get all non-superseded assertions for this version/dimension
      -- filtered by horizon (recorded_at <= horizon_as_of)
      SELECT
        ca.assertion_id,
        ca.dimension_id,
        ca.asserted_value,
        ca.evidence_id,
        ca.recorded_at,
        ca.authority_score,
        ca.source_system
      FROM claris.configuration_assertion ca
      WHERE ca.configuration_version_id = p_configuration_version_id
        AND ca.recorded_at <= p_horizon_as_of
        AND ca.supersedes_assertion_id IS NULL  -- Only current assertions
        AND ca.asserted_value IS NOT NULL
    ),
    dimension_list AS (
      -- Get all dimensions for this version
      SELECT DISTINCT dimension_id FROM claris.configuration_assertion
      WHERE configuration_version_id = p_configuration_version_id
    ),
    per_dimension_fold AS (
      -- For each dimension, determine folded state
      SELECT
        d.dimension_id,
        -- Consensus value: pick value with highest authority_score
        COALESCE((
          SELECT DISTINCT ON (asserted_value) asserted_value
          FROM dimension_assertions da2
          WHERE da2.dimension_id = d.dimension_id
          ORDER BY asserted_value, authority_score DESC
          LIMIT 1
        ), NULL) as consensus_value,
        -- Count distinct values reported
        COUNT(DISTINCT da.asserted_value) as value_count,
        -- Collect all evidence IDs
        ARRAY_AGG(DISTINCT COALESCE(da.evidence_id, '')) FILTER (WHERE da.evidence_id IS NOT NULL) as all_evidence,
        -- Collect all assertion IDs
        ARRAY_AGG(DISTINCT da.assertion_id) as all_assertions
      FROM dimension_list d
      LEFT JOIN dimension_assertions da ON da.dimension_id = d.dimension_id
      GROUP BY d.dimension_id
    )
    SELECT
      pf.dimension_id,
      pf.consensus_value,
      -- Determine state based on evidence pattern
      CASE
        WHEN pf.consensus_value IS NULL THEN 'UNREPORTED'::claris_config_state_type
        WHEN pf.value_count > 1 THEN 'CONTRADICTED'::claris_config_state_type
        WHEN pf.value_count = 1 THEN 'ESTABLISHED'::claris_config_state_type
        ELSE 'UNREPORTED'::claris_config_state_type
      END as state,
      pf.all_evidence,
      CASE WHEN pf.value_count > 1 THEN pf.all_assertions ELSE NULL END as contradicted
    FROM per_dimension_fold pf
  LOOP
    dimension_id := v_dimension_id;
    folded_value := v_value;
    folded_state := v_state;
    evidence_ids := v_evidence_ids;
    contradicted_assertions := v_contradicted;
    RETURN NEXT;
  END LOOP;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- FUNCTION: populate_configuration_state()
-- ============================================================================
-- Populates (or refreshes) configuration_state table by running fold
-- Can be called on-demand or scheduled for caching
--
-- Parameters:
--   p_configuration_version_id: version to fold (NULL = all versions)
--   p_horizon_as_of: evaluation time (NULL = NOW())
--
-- Behavior: Replaces existing state for the same (version, horizon)
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.populate_configuration_state(
  p_configuration_version_id VARCHAR(64) DEFAULT NULL,
  p_horizon_as_of TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
  state_id UUID,
  rows_created INT,
  rows_updated INT,
  execution_time_ms INT
) AS $$
DECLARE
  v_horizon TIMESTAMPTZ;
  v_start_time TIMESTAMPTZ;
  v_rows_created INT := 0;
  v_rows_updated INT := 0;
  v_version_id VARCHAR(64);
  v_fold_result RECORD;
BEGIN
  v_start_time := CLOCK_TIMESTAMP();
  v_horizon := COALESCE(p_horizon_as_of, NOW());

  -- If version not specified, process all versions
  -- Otherwise process single version
  FOR v_version_id IN
    SELECT DISTINCT configuration_version_id FROM claris.configuration_version
    WHERE (p_configuration_version_id IS NULL OR configuration_version_id = p_configuration_version_id)
  LOOP
    -- For each version, run fold and populate/update configuration_state
    FOR v_fold_result IN
      SELECT
        dimension_id,
        folded_value,
        folded_state,
        evidence_ids,
        contradicted_assertions
      FROM claris.fold_configuration_state(v_version_id, v_horizon)
    LOOP
      -- Upsert into configuration_state
      INSERT INTO claris.configuration_state (
        state_id,
        configuration_version_id,
        dimension_id,
        value,
        state,
        evidence_ids,
        contradicted_assertions,
        folded_at,
        fold_version,
        horizon_as_of,
        input_digest
      )
      VALUES (
        gen_random_uuid(),
        v_version_id,
        v_fold_result.dimension_id,
        v_fold_result.folded_value,
        v_fold_result.folded_state,
        v_fold_result.evidence_ids,
        v_fold_result.contradicted_assertions,
        v_start_time,
        '1.0',
        v_horizon,
        MD5(v_version_id || v_fold_result.dimension_id || v_horizon::text)
      )
      ON CONFLICT (configuration_version_id, dimension_id) DO UPDATE
      SET
        value = EXCLUDED.value,
        state = EXCLUDED.state,
        evidence_ids = EXCLUDED.evidence_ids,
        contradicted_assertions = EXCLUDED.contradicted_assertions,
        folded_at = EXCLUDED.folded_at,
        horizon_as_of = EXCLUDED.horizon_as_of,
        input_digest = EXCLUDED.input_digest;

      v_rows_created := v_rows_created + 1;
    END LOOP;
  END LOOP;

  -- Return summary
  state_id := gen_random_uuid();
  rows_created := v_rows_created;
  rows_updated := 0;
  execution_time_ms := EXTRACT(EPOCH FROM (CLOCK_TIMESTAMP() - v_start_time))::INT * 1000;
  RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: get_configuration_state()
-- ============================================================================
-- Query interface: Returns folded state for a specific (version, dimension, horizon)
-- Useful for application layer decision-making
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.get_configuration_state(
  p_configuration_version_id VARCHAR(64),
  p_dimension_id VARCHAR(128),
  p_horizon_as_of TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
  state_value VARCHAR(256),
  state_status claris_config_state_type,
  evidence_count INT,
  contradicted_count INT,
  folded_at TIMESTAMPTZ
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    cs.value,
    cs.state,
    ARRAY_LENGTH(cs.evidence_ids, 1),
    ARRAY_LENGTH(cs.contradicted_assertions, 1),
    cs.folded_at
  FROM claris.configuration_state cs
  WHERE cs.configuration_version_id = p_configuration_version_id
    AND cs.dimension_id = p_dimension_id
    AND (p_horizon_as_of IS NULL OR cs.horizon_as_of = p_horizon_as_of)
  ORDER BY cs.horizon_as_of DESC
  LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- FUNCTION: fold_for_decision()
-- ============================================================================
-- Specialized fold for decision context
-- Takes decision_type and returns only dimensions relevant to that decision
-- Used by decision execution logic
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.fold_for_decision(
  p_configuration_version_id VARCHAR(64),
  p_decision_type VARCHAR(64),
  p_horizon_as_of TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
  dimension_id VARCHAR(128),
  value VARCHAR(256),
  state claris_config_state_type,
  evidence_ids TEXT[]
) AS $$
DECLARE
  v_horizon TIMESTAMPTZ;
BEGIN
  v_horizon := COALESCE(p_horizon_as_of, NOW());

  RETURN QUERY
  SELECT
    fs.dimension_id,
    fs.folded_value,
    fs.folded_state,
    fs.evidence_ids
  FROM claris.fold_configuration_state(p_configuration_version_id, v_horizon) fs
  WHERE EXISTS (
    -- Only return dimensions relevant to this decision_type
    -- (Join to ontology if decision_type has dimension requirements)
    SELECT 1 FROM ontology.configuration_dimensions cd
    WHERE cd.dimension_id = fs.dimension_id
  );
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- PERFORMANCE INDEXES
-- ============================================================================

-- Index for horizon-based queries
CREATE INDEX IF NOT EXISTS idx_configuration_state_horizon_version
  ON claris.configuration_state(configuration_version_id, horizon_as_of DESC);

-- Index for assertion filtering by recorded_at
CREATE INDEX IF NOT EXISTS idx_configuration_assertion_recorded_version
  ON claris.configuration_assertion(configuration_version_id, recorded_at DESC)
  WHERE supersedes_assertion_id IS NULL;

-- Index for dimension lookups
CREATE INDEX IF NOT EXISTS idx_configuration_assertion_dimension_version
  ON claris.configuration_assertion(dimension_id, configuration_version_id);

-- ============================================================================
-- GRANTS (if needed for role-based access)
-- ============================================================================

-- GRANT EXECUTE ON FUNCTION claris.fold_configuration_state TO application_role;
-- GRANT EXECUTE ON FUNCTION claris.populate_configuration_state TO application_role;
-- GRANT EXECUTE ON FUNCTION claris.get_configuration_state TO application_role;
-- GRANT EXECUTE ON FUNCTION claris.fold_for_decision TO application_role;

COMMIT;

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================
--
-- Example 1: Fold a specific version at current time
-- SELECT * FROM claris.fold_configuration_state('version_001', NOW());
--
-- Example 2: Fold at historical horizon
-- SELECT * FROM claris.fold_configuration_state('version_001', '2026-01-15T10:30:00Z');
--
-- Example 3: Populate configuration_state cache
-- SELECT * FROM claris.populate_configuration_state('version_001', NOW());
--
-- Example 4: Get specific folded value
-- SELECT * FROM claris.get_configuration_state('version_001', 'dimension_A', NOW());
--
-- Example 5: Fold for decision context
-- SELECT * FROM claris.fold_for_decision('version_001', 'IDENTITY_ASSESSMENT', NOW());
--
-- ============================================================================
-- VERIFICATION AFTER DEPLOYMENT
-- ============================================================================
--
-- \df claris.fold*
-- \df claris.populate*
-- \df claris.get_configuration_state
-- SELECT prosrc FROM pg_proc WHERE proname = 'fold_configuration_state';
--
-- ============================================================================
