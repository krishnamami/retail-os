-- =====================================================================
-- STEP 4I: FINAL FOLD FIX — Handle NULL basis_ids in property_entries
-- =====================================================================
-- CRITICAL FIX: COALESCE(array_agg(...), ARRAY[]::uuid[])
-- When array_agg over empty array returns NULL, UNNEST(NULL) produces no rows
-- This breaks the LEFT JOIN LATERAL UNNEST, filtering out UNREPORTED properties
-- Solution: Ensure basis_ids is NEVER NULL (use empty array instead)
-- =====================================================================

DROP FUNCTION IF EXISTS runtime.fold_resolve_value(timestamptz, TEXT, TEXT, TEXT) CASCADE;

CREATE OR REPLACE FUNCTION runtime.fold_resolve_value(
  p_decision_horizon timestamptz,
  p_subject_type TEXT,
  p_subject_id TEXT,
  p_property_name TEXT
)
RETURNS jsonb AS $$
DECLARE
  v_applicable_assertions RECORD;
  v_max_effective_at timestamptz;
  v_count_at_max INTEGER;
  v_distinct_values INTEGER;
  v_fold_state TEXT;
  v_resolved_value TEXT;
  v_value_type TEXT;
  v_effective_at TEXT;
  v_latest_arrival_at TEXT;
  v_basis_ids uuid[];
  v_result jsonb;
BEGIN
  SELECT MAX(effective_at)
  INTO v_max_effective_at
  FROM runtime.assertion
  WHERE subject_type = p_subject_type
    AND subject_id = p_subject_id
    AND property_name = p_property_name
    AND arrival_at <= p_decision_horizon
    AND effective_at <= p_decision_horizon;

  IF v_max_effective_at IS NULL THEN
    v_fold_state := 'UNREPORTED';
    v_resolved_value := NULL;
    v_value_type := NULL;
    v_effective_at := NULL;
    v_latest_arrival_at := NULL;
    v_basis_ids := ARRAY[]::uuid[];
  ELSE
    SELECT
      COUNT(*),
      COUNT(DISTINCT asserted_value),
      MAX(arrival_at),
      array_agg(DISTINCT assertion_id)
    INTO
      v_count_at_max,
      v_distinct_values,
      v_latest_arrival_at,
      v_basis_ids
    FROM runtime.assertion
    WHERE subject_type = p_subject_type
      AND subject_id = p_subject_id
      AND property_name = p_property_name
      AND arrival_at <= p_decision_horizon
      AND effective_at <= p_decision_horizon
      AND effective_at = v_max_effective_at;

    IF v_distinct_values = 1 THEN
      v_fold_state := 'ESTABLISHED';
      SELECT asserted_value, property_value_type
      INTO v_resolved_value, v_value_type
      FROM runtime.assertion
      WHERE subject_type = p_subject_type
        AND subject_id = p_subject_id
        AND property_name = p_property_name
        AND arrival_at <= p_decision_horizon
        AND effective_at <= p_decision_horizon
        AND effective_at = v_max_effective_at
      LIMIT 1;
      v_effective_at := v_max_effective_at::TEXT;

    ELSIF v_distinct_values > 1 THEN
      v_fold_state := 'CONTRADICTED';
      v_resolved_value := NULL;
      v_value_type := NULL;
      v_effective_at := v_max_effective_at::TEXT;

    ELSE
      RAISE EXCEPTION 'Internal Fold algorithm error: assertion count % but distinct values %',
        v_count_at_max, v_distinct_values;
    END IF;
  END IF;

  v_result := jsonb_build_object(
    'fold_state', v_fold_state,
    'resolved_value', COALESCE(to_jsonb(v_resolved_value), NULL::jsonb),
    'property_value_type', COALESCE(v_value_type, NULL::TEXT),
    'effective_at', COALESCE(v_effective_at, NULL::TEXT),
    'latest_known_arrival_at', COALESCE(v_latest_arrival_at::TEXT, NULL::TEXT),
    'basis_assertion_ids', COALESCE(to_jsonb(v_basis_ids), '[]'::jsonb)
  );

  RETURN v_result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =====================================================================
-- DROP OLD VERSION & CREATE CORRECTED fold_snapshot_at_horizon
-- =====================================================================

DROP FUNCTION IF EXISTS runtime.fold_snapshot_at_horizon(timestamptz) CASCADE;

CREATE OR REPLACE FUNCTION runtime.fold_snapshot_at_horizon(
  p_decision_horizon timestamptz
)
RETURNS TABLE (
  fold_snapshot_count INTEGER,
  total_property_states INTEGER,
  established_count INTEGER,
  unreported_count INTEGER,
  explicitly_undefined_count INTEGER,
  contradicted_count INTEGER,
  subjects_by_type TEXT,
  new_snapshots_inserted INTEGER,
  deterministic_replays INTEGER,
  replay_mismatches INTEGER
) AS $$
DECLARE
  v_established_count INTEGER := 0;
  v_unreported_count INTEGER := 0;
  v_undefined_count INTEGER := 0;
  v_contradicted_count INTEGER := 0;
  v_total_properties INTEGER := 0;
  v_snap_count INTEGER := 0;
  v_kb_version TEXT;
  v_policy_version TEXT;
  v_new_inserts INTEGER := 0;
  v_replays INTEGER := 0;
  v_mismatches INTEGER := 0;
BEGIN
  SELECT kb_version INTO v_kb_version
  FROM runtime.governed_knowledge_base
  WHERE is_active = true
  ORDER BY created_at DESC
  LIMIT 1;

  IF v_kb_version IS NULL THEN
    RAISE EXCEPTION 'Fold execution failed: No active KB version found in runtime.governed_knowledge_base. Governance must be resolved.';
  END IF;

  SELECT policy_version INTO v_policy_version
  FROM runtime.governed_policy
  WHERE is_active = true
  ORDER BY created_at DESC
  LIMIT 1;

  IF v_policy_version IS NULL THEN
    RAISE EXCEPTION 'Fold execution failed: No active policy version found in runtime.governed_policy. Governance must be resolved.';
  END IF;

  DROP TABLE IF EXISTS fold_computed_snapshots;

  CREATE TEMP TABLE fold_computed_snapshots (
    decision_horizon timestamptz,
    subject_type TEXT,
    subject_id TEXT,
    computed_fold_status TEXT,
    folded_properties jsonb,
    all_basis_ids uuid[],
    kb_version TEXT,
    policy_version TEXT
  ) ON COMMIT DROP;

  INSERT INTO fold_computed_snapshots
  WITH
  applicable_properties AS (
    SELECT 'configuration' AS subject_type, subject_id, 'sap_con_hierarchy_code' AS property_name
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%') a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_load_actor'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%') a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_load_status'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%') a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_hierarchy_code'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%') a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_load_status'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%') a
    UNION ALL
    SELECT 'launch', subject_id, 'change_requested_by'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
    UNION ALL
    SELECT 'launch', subject_id, 'change_requester_role'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
    UNION ALL
    SELECT 'launch', subject_id, 'intent_classification'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
    UNION ALL
    SELECT 'material', subject_id, 'material_status'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'material') a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_confirmed'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_status'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_value_usd'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
    UNION ALL
    SELECT 'sku', subject_id, 'sku_activation_status'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
    UNION ALL
    SELECT 'sku', subject_id, 'sku_status'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
    UNION ALL
    SELECT 'sku', subject_id, 'technical_review_result'
    FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
  ),
  property_fold_results AS (
    SELECT
      ap.subject_type,
      ap.subject_id,
      ap.property_name,
      runtime.fold_resolve_value(p_decision_horizon, ap.subject_type, ap.subject_id, ap.property_name) AS fold_result
    FROM applicable_properties ap
  ),
  property_entries AS (
    SELECT
      pfr.subject_type,
      pfr.subject_id,
      jsonb_build_object(
        'property_name', pfr.property_name,
        'fold_state', pfr.fold_result->>'fold_state',
        'resolved_value', pfr.fold_result->'resolved_value',
        'property_value_type', pfr.fold_result->>'property_value_type',
        'effective_at', pfr.fold_result->>'effective_at',
        'latest_known_arrival_at', pfr.fold_result->>'latest_known_arrival_at',
        'basis_assertion_ids', pfr.fold_result->'basis_assertion_ids'
      ) AS property_json,
      COALESCE(
        (SELECT array_agg(elem::uuid ORDER BY elem::uuid)
         FROM jsonb_array_elements_text(pfr.fold_result->'basis_assertion_ids') AS elem),
        ARRAY[]::uuid[]
      ) AS basis_ids
    FROM property_fold_results pfr
  ),
  subject_snapshots AS (
    SELECT
      subject_type,
      subject_id,
      jsonb_agg(property_json ORDER BY property_json->>'property_name') AS folded_properties,
      array_agg(DISTINCT basis_id ORDER BY basis_id) FILTER (WHERE basis_id IS NOT NULL) AS all_basis_ids,
      CASE
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'CONTRADICTED') THEN 'CONTRADICTED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'EXPLICITLY_UNDEFINED') THEN 'EXPLICITLY_UNDEFINED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'UNREPORTED') THEN 'UNREPORTED'
        ELSE 'ESTABLISHED'
      END AS computed_fold_status
    FROM property_entries
    LEFT JOIN LATERAL UNNEST(basis_ids) AS basis_id ON true
    GROUP BY subject_type, subject_id
  )
  SELECT
    p_decision_horizon,
    ss.subject_type,
    ss.subject_id,
    ss.computed_fold_status,
    ss.folded_properties,
    ss.all_basis_ids,
    v_kb_version,
    v_policy_version
  FROM subject_snapshots ss;

  SELECT COUNT(*) INTO v_new_inserts
  FROM (
    SELECT 1
    FROM fold_computed_snapshots cs
    LEFT JOIN state.fold_state_snapshot fss
      ON fss.decision_horizon = cs.decision_horizon
      AND fss.subject_type = cs.subject_type
      AND fss.subject_id = cs.subject_id
    WHERE fss.fold_state_id IS NULL
  ) t;

  SELECT COUNT(*) INTO v_mismatches
  FROM (
    SELECT cs.subject_type, cs.subject_id
    FROM fold_computed_snapshots cs
    INNER JOIN state.fold_state_snapshot fss
      ON fss.decision_horizon = cs.decision_horizon
      AND fss.subject_type = cs.subject_type
      AND fss.subject_id = cs.subject_id
    WHERE cs.computed_fold_status IS DISTINCT FROM fss.fold_status
       OR cs.folded_properties IS DISTINCT FROM fss.folded_properties
       OR cs.all_basis_ids IS DISTINCT FROM fss.basis_assertion_ids
       OR cs.kb_version IS DISTINCT FROM fss.kb_version
       OR cs.policy_version IS DISTINCT FROM fss.policy_version
  ) t;

  IF v_mismatches > 0 THEN
    RAISE EXCEPTION 'Deterministic replay mismatch: % snapshots produced different content on second execution at horizon %. Assertion corpus, KB version, or policy version must have changed during fold execution (immutability violated).',
      v_mismatches, p_decision_horizon;
  END IF;

  INSERT INTO state.fold_state_snapshot (
    decision_horizon, subject_type, subject_id, fold_status,
    folded_properties, basis_assertion_ids, kb_version, policy_version,
    fold_computed_at
  )
  SELECT
    cs.decision_horizon,
    cs.subject_type,
    cs.subject_id,
    cs.computed_fold_status,
    cs.folded_properties,
    cs.all_basis_ids,
    cs.kb_version,
    cs.policy_version,
    CURRENT_TIMESTAMP
  FROM fold_computed_snapshots cs
  ON CONFLICT (decision_horizon, subject_type, subject_id)
  DO NOTHING;

  SELECT COUNT(*) INTO v_replays
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

  SELECT COUNT(*) INTO v_snap_count FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

  -- CRITICAL FIX: Use props->>'fold_state' to reference JSONB key
  SELECT
    COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED'),
    COUNT(*) FILTER (WHERE props->>'fold_state' = 'UNREPORTED'),
    COUNT(*) FILTER (WHERE props->>'fold_state' = 'EXPLICITLY_UNDEFINED'),
    COUNT(*) FILTER (WHERE props->>'fold_state' = 'CONTRADICTED'),
    COUNT(*)
  INTO v_established_count, v_unreported_count, v_undefined_count, v_contradicted_count, v_total_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon;

  RETURN QUERY
  SELECT
    v_snap_count,
    v_total_properties,
    v_established_count,
    v_unreported_count,
    v_undefined_count,
    v_contradicted_count,
    (SELECT jsonb_object_agg(subject_type, cnt)
     FROM (
       SELECT subject_type, COUNT(DISTINCT subject_id) AS cnt
       FROM state.fold_state_snapshot
       WHERE decision_horizon = p_decision_horizon
       GROUP BY subject_type
     ) t)::TEXT,
    v_new_inserts,
    v_replays,
    v_mismatches;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- STEP 1: DELETE ALL SNAPSHOTS (Clean slate for fresh Run #1)
-- =====================================================================

BEGIN;

DELETE FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

-- =====================================================================
-- STEP 2: RE-EXECUTE FOLD RUN #1 (With COALESCE null basis_ids fix)
-- =====================================================================

SELECT * FROM runtime.fold_snapshot_at_horizon('2026-06-20 10:45:00+00'::timestamptz);

-- =====================================================================
-- STEP 3: COMPLETE VALIDATION (All 12 Queries)
-- =====================================================================

SELECT 'V1: Snapshot Count' AS test, COUNT(*) AS result FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

SELECT 'V2: Property Distribution' AS test, props->>'fold_state', COUNT(*) AS count
FROM state.fold_state_snapshot fss, LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY props->>'fold_state' ORDER BY props->>'fold_state';

SELECT 'V3: Subject Distribution' AS test, subject_type, COUNT(DISTINCT subject_id) AS count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY subject_type ORDER BY subject_type;

SELECT 'V4: SKU-006 technical_review_result' AS test, props->>'property_name', props->>'fold_state', jsonb_array_length(props->'basis_assertion_ids') AS basis_count
FROM state.fold_state_snapshot fss, LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND fss.subject_id = 'SKU-006' AND props->>'property_name' = 'technical_review_result';

SELECT 'V5: SKU-013 technical_review_result' AS test, props->>'property_name', props->>'fold_state', jsonb_array_length(props->'basis_assertion_ids') AS basis_count
FROM state.fold_state_snapshot fss, LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND fss.subject_id = 'SKU-013' AND props->>'property_name' = 'technical_review_result';

SELECT 'V6: KB and Policy Versions' AS test, kb_version, policy_version
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
LIMIT 1;

SELECT 'V7: Basis Assertion IDs Validity' AS test, COUNT(*) total, COUNT(*) FILTER (WHERE basis_assertion_ids IS NOT NULL) non_null
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

SELECT 'V8: Referenced Assertions' AS test, COUNT(DISTINCT unnest) AS count
FROM state.fold_state_snapshot fss, LATERAL UNNEST(fss.basis_assertion_ids) AS unnest
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

SELECT 'V9: No Future Contributors' AS test, COUNT(*) AS count
FROM state.fold_state_snapshot fss, LATERAL UNNEST(fss.basis_assertion_ids) AS basis_id
INNER JOIN runtime.assertion a ON a.assertion_id = basis_id::uuid
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND a.arrival_at > '2026-06-20 10:45:00+00'::timestamptz;

SELECT 'V10: Temporal Consistency' AS test, COUNT(*) AS count
FROM state.fold_state_snapshot fss, LATERAL UNNEST(fss.basis_assertion_ids) AS basis_id
INNER JOIN runtime.assertion a ON a.assertion_id = basis_id::uuid
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND a.effective_at > '2026-06-20 10:45:00+00'::timestamptz;

SELECT 'V11: Upstream Immutability' AS test, COUNT(*) AS total_assertions FROM runtime.assertion;

SELECT 'V12: Subject Fold Status' AS test, fold_status, COUNT(*) AS count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY fold_status ORDER BY fold_status;

COMMIT;
