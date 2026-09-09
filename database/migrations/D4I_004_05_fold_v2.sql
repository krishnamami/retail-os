-- ============================================================================
-- D4I_004 step 2c -- runtime.fold_snapshot_at_horizon_v2()
-- ONE STATEMENT. Deliberately.
-- ============================================================================
-- WHAT CHANGED, AND NOTHING ELSE DID
--   The deployed fold hard-codes its (subject_type, subject_id, property_name)
--   triples. It knows 22 property names. The evidence layer now carries 50.
--   This function is that function with 28 triples added and every other line
--   preserved: the same KB/policy resolution, the same fold_resolve_value
--   call, the same per-property JSON shape, the same subject-status
--   precedence, the same ON CONFLICT DO NOTHING, the same determinism check.
--   Each added line is marked -- D4I_004.
--
-- WHY A NEW FUNCTION RATHER THAN A REPLACEMENT
--   The original stays callable and unchanged, so the 2026-06-20 snapshot it
--   produced remains reproducible by the function that produced it. Same
--   discipline as evidence_projection_v1 and _v2.
--
-- WHY THIS COULD NOT BE RUN AT THE OLD HORIZON
--   Two independent reasons, both in the deployed body:
--     1  ON CONFLICT DO NOTHING never refreshes an existing snapshot, so a
--        same-horizon re-run cannot correct a stale one.
--     2  The determinism check RAISES when recomputed content differs from
--        what is persisted. The property set legitimately changed, so that
--        check would fire -- correctly. It is guarding immutability, and
--        honouring it means folding at a new horizon rather than overwriting
--        history.
--
-- THE BUG THIS FIXES
--   SAP_PRD_PROMOTED introduced configuration subjects PRD-001..PRD-004 whose
--   only assertions are sap_prd_promotion_*. The deployed PRD branch offers
--   only sap_prd_hierarchy_code and sap_prd_load_status, so every enumerated
--   property resolved UNREPORTED, all_basis_ids aggregated to NULL, and
--   basis_assertion_ids uuid[] NOT NULL rejected the row. That NOT NULL fires
--   before ON CONFLICT can suppress anything, which is why an idempotent
--   function aborted mid-fold.
--
--   The fix is to give those subjects the properties they actually have. The
--   NOT NULL behaviour is left exactly as deployed: a subject with nothing
--   resolvable still refuses to be written, rather than being quietly
--   recorded with an empty basis. D4I_004_05v proves no such subject exists
--   at the chosen horizon before this is ever called.
--
-- A SECOND DEFECT FOUND WHILE APPLYING THIS
--   The deployed function's final counting block reads
--       COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED')
--   over LATERAL jsonb_array_elements(...) AS props. fold_state is a key
--   inside each element, not a column, so that block raises 42703 and the
--   deployed function cannot complete a run. The existing 2026-06-20 snapshot
--   must therefore have been written by an earlier build than the one now
--   installed. v2 fixes the four predicates and the element alias and changes
--   nothing else about what is counted. The deployed function is left as it
--   is -- diagnosing it is not this phase's job, but relying on it would be.
--
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

CREATE OR REPLACE FUNCTION runtime.fold_snapshot_at_horizon_v2(
    p_decision_horizon timestamp with time zone)
 RETURNS TABLE(fold_snapshot_count integer, total_property_states integer,
               established_count integer, unreported_count integer,
               explicitly_undefined_count integer, contradicted_count integer,
               subjects_by_type text, new_snapshots_inserted integer,
               deterministic_replays integer, replay_mismatches integer)
 LANGUAGE plpgsql
AS $function$
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

  CREATE TEMP TABLE temp_subject_snapshots AS
  WITH
  applicable_properties AS (
    SELECT 'configuration' AS subject_type, subject_id,
           'sap_con_hierarchy_code' AS property_name
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
    UNION ALL
    SELECT 'configuration', subject_id, 'con_verification_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_test_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_test_actor'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
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
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_promotion_hierarchy_code'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_promotion_actor'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
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
    UNION ALL
    SELECT 'launch', subject_id, 'hierarchy_approval_code'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'hierarchy_approval_authority'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'material', subject_id, 'material_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'material'
    ) a
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
    UNION ALL
    SELECT 'sku', subject_id, 'final_pricing_approval_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_upload_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_uploaded_price_usd'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_publication_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_list_price'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_currency'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_published_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'overnight_push_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'overnight_push_run_date'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'zupdm_approval_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'all_gates_cleared'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approval_requested'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approval_level'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_requested_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approval_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approved_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'supply_chain_notification_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'supply_chain_notification_type'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'supply_chain_notified_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'material_activation_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'material_activated_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'product', subject_id, 'product_name'
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
    UNION ALL
    SELECT 'configuration_request', subject_id, 'product_reference'
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
    ) a  ),
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

  SELECT COUNT(*) INTO v_replays
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

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

  IF v_mismatches > 0 THEN
    RAISE EXCEPTION 'Deterministic replay mismatch: % snapshots produced different content on second execution at horizon %. Assertion corpus, KB version, or policy version must have changed during fold execution (immutability violated).',
      v_mismatches, p_decision_horizon;
  END IF;

  SELECT COUNT(*) INTO v_snap_count FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

  -- D4I_004 FIX: fold_state is a key inside each folded_properties element,
  -- not a column. The deployed function references it bare, so its final
  -- counting block raises 42703 and the function can never complete. The
  -- 2026-06-20 snapshot was therefore produced by an earlier build. Only the
  -- four FILTER predicates and the element alias change; the counts they
  -- produce are the ones the deployed function intended.
  SELECT
    COUNT(*) FILTER (WHERE prop->>'fold_state' = 'ESTABLISHED'),
    COUNT(*) FILTER (WHERE prop->>'fold_state' = 'UNREPORTED'),
    COUNT(*) FILTER (WHERE prop->>'fold_state' = 'EXPLICITLY_UNDEFINED'),
    COUNT(*) FILTER (WHERE prop->>'fold_state' = 'CONTRADICTED'),
    COUNT(*)
  INTO v_established_count, v_unreported_count, v_undefined_count, v_contradicted_count, v_total_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props(prop)
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
$function$;
