-- =====================================================================
-- Fold State Snapshot Module — Main Entry Point
-- =====================================================================
-- Purpose: Deterministic state computation answering "What was the
--          knowable state for subject/property at decision_horizon T?"
-- Entry Point: runtime.fold_snapshot_at_horizon(decision_horizon)
-- Physical grain: (decision_horizon, subject_type, subject_id) per row
-- Semantic grain: property-level within folded_properties JSONB
-- Identity: (decision_horizon, subject_type, subject_id)
-- Idempotency: Identical input → identical output; no duplicate rows
-- =====================================================================

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
  -- =====================================================================
  -- CRITICAL: Retrieve active KB/Policy versions (FAIL if not found)
  -- =====================================================================
  -- DO NOT use exception handler for fallback.
  -- Fold must use actual governed governance, never hardcoded versions.

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

  -- =====================================================================
  -- Build Fold snapshots using property-domain configuration
  -- =====================================================================
  -- Create temporary table for subject_snapshots (used in INSERT and later counting logic)
  CREATE TEMP TABLE temp_subject_snapshots AS
  WITH
  -- Configuration: Build applicable (subject_type, subject_id, property_name) triples
  applicable_properties AS (
    SELECT 'configuration' AS subject_type, subject_id, 'sap_con_hierarchy_code' AS property_name
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_load_actor'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_load_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    -- PRD properties
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_hierarchy_code'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_load_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
    -- Launch properties
    UNION ALL
    SELECT 'launch', subject_id, 'change_requested_by'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'change_requester_role'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'intent_classification'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    -- Material properties
    UNION ALL
    SELECT 'material', subject_id, 'material_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'material'
    ) a
    -- SKU properties
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_confirmed'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_value_usd'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'sku_activation_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'sku_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'technical_review_result'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    -- Product properties (extended domain)
    UNION ALL
    SELECT 'product' AS subject_type, subject_id, 'product_name' AS property_name
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'product'
    ) a
    UNION ALL
    SELECT 'product', subject_id, 'launch_reference'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'product'
    ) a
    -- Configuration Request properties (extended domain)
    UNION ALL
    SELECT 'configuration_request' AS subject_type, subject_id, 'product_reference' AS property_name
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'launch_reference'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'geography'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'term_months'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'customer_segment'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
  ),
  -- Evaluate each property using fold_resolve_value logic
  property_fold_results AS (
    SELECT
      ap.subject_type,
      ap.subject_id,
      ap.property_name,
      runtime.fold_resolve_value(
        p_decision_horizon,
        ap.subject_type,
        ap.subject_id,
        ap.property_name
      ) AS fold_result
    FROM applicable_properties ap
  ),
  -- Build per-property JSONB entries
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
        (SELECT array_agg(val::uuid)
         FROM jsonb_array_elements_text(pfr.fold_result->'basis_assertion_ids') val
         WHERE val IS NOT NULL AND val != ''),
        '{}'::uuid[]
      ) AS basis_ids
    FROM property_fold_results pfr
  ),
  -- Aggregate properties per subject and compute subject-level status
  subject_snapshots AS (
    SELECT
      subject_type,
      subject_id,
      jsonb_agg(property_json ORDER BY property_json->>'property_name') AS folded_properties,
      array_agg(DISTINCT u.basis_id ORDER BY u.basis_id) FILTER (WHERE u.basis_id IS NOT NULL) AS all_basis_ids,
      CASE
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'CONTRADICTED') THEN 'CONTRADICTED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'EXPLICITLY_UNDEFINED') THEN 'EXPLICITLY_UNDEFINED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'UNREPORTED') THEN 'UNREPORTED'
        ELSE 'ESTABLISHED'
      END AS computed_fold_status
    FROM property_entries pe
    LEFT JOIN LATERAL UNNEST(pe.basis_ids) AS u(basis_id) ON TRUE
    GROUP BY subject_type, subject_id
  )
  SELECT
    ss.subject_type,
    ss.subject_id,
    ss.folded_properties,
    ss.all_basis_ids,
    ss.computed_fold_status
  FROM subject_snapshots ss;

  -- Insert snapshots from temporary table
  INSERT INTO state.fold_state_snapshot (
    decision_horizon, subject_type, subject_id, fold_status,
    folded_properties, basis_assertion_ids, kb_version, policy_version,
    fold_computed_at
  )
  SELECT
    p_decision_horizon,
    subject_type,
    subject_id,
    computed_fold_status,
    folded_properties,
    all_basis_ids,
    v_kb_version,
    v_policy_version,
    CURRENT_TIMESTAMP
  FROM temp_subject_snapshots
  ON CONFLICT (decision_horizon, subject_type, subject_id)
  DO NOTHING;

  -- =====================================================================
  -- Count outcomes: new inserts vs replays vs mismatches
  -- =====================================================================

  -- Case A: Count newly inserted snapshots (no pre-existing key)
  SELECT COUNT(*) INTO v_new_inserts
  FROM (
    SELECT 1
    FROM temp_subject_snapshots ss
    LEFT JOIN state.fold_state_snapshot fss
      ON fss.decision_horizon = p_decision_horizon
      AND fss.subject_type = ss.subject_type
      AND fss.subject_id = ss.subject_id
    WHERE fss.fold_state_id IS NULL
  ) t;

  -- Case B+C: Count total existing snapshots after insert (replay count)
  SELECT COUNT(*) INTO v_replays
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

  -- Determinism Detection: Compare newly computed content against persisted content
  -- For rows that already existed, verify fold_status, folded_properties, basis_assertion_ids,
  -- kb_version, and policy_version are IDENTICAL.
  -- Exclude fold_computed_at from comparison (timestamp may differ on replays).
  SELECT COUNT(*) INTO v_mismatches
  FROM (
    SELECT ss.subject_type, ss.subject_id
    FROM temp_subject_snapshots ss
    INNER JOIN state.fold_state_snapshot fss
      ON fss.decision_horizon = p_decision_horizon
      AND fss.subject_type = ss.subject_type
      AND fss.subject_id = ss.subject_id
    WHERE ss.computed_fold_status IS DISTINCT FROM fss.fold_status
       OR ss.folded_properties IS DISTINCT FROM fss.folded_properties
       OR ss.all_basis_ids IS DISTINCT FROM fss.basis_assertion_ids
       OR v_kb_version IS DISTINCT FROM fss.kb_version
       OR v_policy_version IS DISTINCT FROM fss.policy_version
  ) t;

  -- Raise exception if deterministic replay mismatch detected
  IF v_mismatches > 0 THEN
    RAISE EXCEPTION 'Deterministic replay mismatch: % snapshots produced different content on second execution at horizon %. Assertion corpus, KB version, or policy version must have changed during fold execution (immutability violated).',
      v_mismatches, p_decision_horizon;
  END IF;

  -- =====================================================================
  -- Verify snapshot creation and return counts
  -- =====================================================================
  SELECT COUNT(*) INTO v_snap_count FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

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
