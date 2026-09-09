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
