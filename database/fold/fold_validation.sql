-- =====================================================================
-- Fold Validation Module
-- =====================================================================
-- Purpose: Validate Fold snapshot correctness across:
-- - row counts
-- - property counts
-- - state distributions
-- - temporal constraints
-- - lineage integrity
-- =====================================================================

CREATE OR REPLACE FUNCTION runtime.validate_fold_snapshot(
  p_decision_horizon timestamptz
)
RETURNS TABLE (
  validation_name TEXT,
  check_result TEXT,
  expected_value TEXT,
  actual_value TEXT,
  status TEXT
) AS $$
DECLARE
  v_snapshot_count INTEGER;
  v_property_count INTEGER;
  v_established_count INTEGER;
  v_unreported_count INTEGER;
  v_undefined_count INTEGER;
  v_contradicted_count INTEGER;
  v_con_subjects INTEGER;
  v_prd_subjects INTEGER;
  v_launch_subjects INTEGER;
  v_material_subjects INTEGER;
  v_sku_subjects INTEGER;
  v_con_properties INTEGER;
  v_prd_properties INTEGER;
  v_launch_properties INTEGER;
  v_material_properties INTEGER;
  v_sku_properties INTEGER;
  v_duplicate_keys INTEGER;
  v_null_subject_ids INTEGER;
  v_malformed_json INTEGER;
  v_orphan_basis_count INTEGER;
  v_invalid_future_assertions INTEGER;
  v_invalid_effective_assertions INTEGER;
BEGIN
  -- =====================================================================
  -- Count snapshots
  -- =====================================================================
  SELECT COUNT(*) INTO v_snapshot_count
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

  RETURN QUERY
  SELECT 'Snapshot Count'::TEXT, 'CHECK', '51'::TEXT, v_snapshot_count::TEXT,
    CASE WHEN v_snapshot_count = 51 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Count total property states
  -- =====================================================================
  SELECT COUNT(*)
  INTO v_property_count
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon;

  RETURN QUERY
  SELECT 'Property State Count'::TEXT, 'CALCULATED', '177'::TEXT, v_property_count::TEXT,
    CASE WHEN v_property_count = 177 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Count state distribution
  -- =====================================================================
  SELECT
    COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED'),
    COUNT(*) FILTER (WHERE fold_state = 'UNREPORTED'),
    COUNT(*) FILTER (WHERE fold_state = 'EXPLICITLY_UNDEFINED'),
    COUNT(*) FILTER (WHERE fold_state = 'CONTRADICTED')
  INTO v_established_count, v_unreported_count, v_undefined_count, v_contradicted_count
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon;

  RETURN QUERY
  SELECT 'ESTABLISHED State Count'::TEXT, 'DISTRIBUTION', '107'::TEXT, v_established_count::TEXT,
    CASE WHEN v_established_count = 107 THEN 'PASS' ELSE 'FAIL' END;

  RETURN QUERY
  SELECT 'UNREPORTED State Count'::TEXT, 'DISTRIBUTION', '70'::TEXT, v_unreported_count::TEXT,
    CASE WHEN v_unreported_count = 70 THEN 'PASS' ELSE 'FAIL' END;

  RETURN QUERY
  SELECT 'EXPLICITLY_UNDEFINED State Count'::TEXT, 'DISTRIBUTION', '0'::TEXT, v_undefined_count::TEXT,
    CASE WHEN v_undefined_count = 0 THEN 'PASS' ELSE 'FAIL' END;

  RETURN QUERY
  SELECT 'CONTRADICTED State Count'::TEXT, 'DISTRIBUTION', '0'::TEXT, v_contradicted_count::TEXT,
    CASE WHEN v_contradicted_count = 0 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Count subjects by type
  -- =====================================================================
  SELECT COUNT(DISTINCT subject_id) INTO v_con_subjects
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon
    AND subject_type = 'configuration' AND subject_id LIKE 'CON-%';

  RETURN QUERY
  SELECT 'CON Subject Count'::TEXT, 'INVENTORY', '13'::TEXT, v_con_subjects::TEXT,
    CASE WHEN v_con_subjects = 13 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(DISTINCT subject_id) INTO v_prd_subjects
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon
    AND subject_type = 'configuration' AND subject_id LIKE 'PRD-%';

  RETURN QUERY
  SELECT 'PRD Subject Count'::TEXT, 'INVENTORY', '9'::TEXT, v_prd_subjects::TEXT,
    CASE WHEN v_prd_subjects = 9 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(DISTINCT subject_id) INTO v_launch_subjects
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon
    AND subject_type = 'launch';

  RETURN QUERY
  SELECT 'Launch Subject Count'::TEXT, 'INVENTORY', '13'::TEXT, v_launch_subjects::TEXT,
    CASE WHEN v_launch_subjects = 13 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(DISTINCT subject_id) INTO v_material_subjects
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon
    AND subject_type = 'material';

  RETURN QUERY
  SELECT 'Material Subject Count'::TEXT, 'INVENTORY', '3'::TEXT, v_material_subjects::TEXT,
    CASE WHEN v_material_subjects = 3 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(DISTINCT subject_id) INTO v_sku_subjects
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon
    AND subject_type = 'sku';

  RETURN QUERY
  SELECT 'SKU Subject Count'::TEXT, 'INVENTORY', '13'::TEXT, v_sku_subjects::TEXT,
    CASE WHEN v_sku_subjects = 13 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Property counts by domain
  -- =====================================================================
  SELECT COUNT(*)
  INTO v_con_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon
    AND fss.subject_type = 'configuration' AND fss.subject_id LIKE 'CON-%';

  RETURN QUERY
  SELECT 'CON Property State Count'::TEXT, 'DOMAIN', '39'::TEXT, v_con_properties::TEXT,
    CASE WHEN v_con_properties = 39 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(*)
  INTO v_prd_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon
    AND fss.subject_type = 'configuration' AND fss.subject_id LIKE 'PRD-%';

  RETURN QUERY
  SELECT 'PRD Property State Count'::TEXT, 'DOMAIN', '18'::TEXT, v_prd_properties::TEXT,
    CASE WHEN v_prd_properties = 18 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(*)
  INTO v_launch_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon
    AND fss.subject_type = 'launch';

  RETURN QUERY
  SELECT 'Launch Property State Count'::TEXT, 'DOMAIN', '39'::TEXT, v_launch_properties::TEXT,
    CASE WHEN v_launch_properties = 39 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(*)
  INTO v_material_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon
    AND fss.subject_type = 'material';

  RETURN QUERY
  SELECT 'Material Property State Count'::TEXT, 'DOMAIN', '3'::TEXT, v_material_properties::TEXT,
    CASE WHEN v_material_properties = 3 THEN 'PASS' ELSE 'FAIL' END;

  SELECT COUNT(*)
  INTO v_sku_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon
    AND fss.subject_type = 'sku';

  RETURN QUERY
  SELECT 'SKU Property State Count'::TEXT, 'DOMAIN', '78'::TEXT, v_sku_properties::TEXT,
    CASE WHEN v_sku_properties = 78 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Check for duplicate snapshot keys
  -- =====================================================================
  SELECT COUNT(*)
  INTO v_duplicate_keys
  FROM (
    SELECT decision_horizon, subject_type, subject_id, COUNT(*)
    FROM state.fold_state_snapshot
    WHERE decision_horizon = p_decision_horizon
    GROUP BY decision_horizon, subject_type, subject_id
    HAVING COUNT(*) > 1
  ) t;

  RETURN QUERY
  SELECT 'Duplicate Snapshot Keys'::TEXT, 'INTEGRITY', '0'::TEXT, v_duplicate_keys::TEXT,
    CASE WHEN v_duplicate_keys = 0 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Check for NULL subject_ids
  -- =====================================================================
  SELECT COUNT(*)
  INTO v_null_subject_ids
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon
    AND subject_id IS NULL;

  RETURN QUERY
  SELECT 'NULL Subject IDs'::TEXT, 'INTEGRITY', '0'::TEXT, v_null_subject_ids::TEXT,
    CASE WHEN v_null_subject_ids = 0 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Check folded_properties is valid JSON
  -- =====================================================================
  SELECT COUNT(*)
  INTO v_malformed_json
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon
    AND (folded_properties IS NULL OR NOT (folded_properties @> '{}'::jsonb));

  RETURN QUERY
  SELECT 'Malformed folded_properties JSON'::TEXT, 'STRUCTURE', '0'::TEXT, v_malformed_json::TEXT,
    CASE WHEN v_malformed_json = 0 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Check temporal constraints: assertions arriving after horizon
  -- =====================================================================
  SELECT COUNT(DISTINCT a.assertion_id)
  INTO v_invalid_future_assertions
  FROM state.fold_state_snapshot fss
  CROSS JOIN LATERAL (
    SELECT * FROM jsonb_array_elements(fss.basis_assertion_ids)::uuid AS id
  ) AS basis
  INNER JOIN runtime.assertion a ON a.assertion_id = basis.id
  WHERE fss.decision_horizon = p_decision_horizon
    AND a.arrival_at > p_decision_horizon;

  RETURN QUERY
  SELECT 'Assertions with arrival_at > horizon'::TEXT, 'TEMPORAL', '0'::TEXT, v_invalid_future_assertions::TEXT,
    CASE WHEN v_invalid_future_assertions = 0 THEN 'PASS' ELSE 'FAIL' END;

  -- =====================================================================
  -- Subject-level fold_status aggregation
  -- =====================================================================
  RETURN QUERY
  SELECT 'Subject fold_status = ESTABLISHED'::TEXT, 'AGGREGATION',
    (v_snapshot_count - COALESCE((SELECT COUNT(*) FROM state.fold_state_snapshot WHERE decision_horizon = p_decision_horizon AND fold_status != 'ESTABLISHED'), 0))::TEXT,
    (SELECT COUNT(*) FROM state.fold_state_snapshot WHERE decision_horizon = p_decision_horizon AND fold_status = 'ESTABLISHED')::TEXT,
    'INFO';

END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- Lineage Validation: Fold → Assertion → Evidence → Raw
-- =====================================================================
CREATE OR REPLACE FUNCTION runtime.validate_fold_lineage(
  p_decision_horizon timestamptz
)
RETURNS TABLE (
  lineage_check TEXT,
  orphan_fold_ids INTEGER,
  orphan_assertion_ids INTEGER,
  orphan_evidence_ids INTEGER,
  status TEXT
) AS $$
DECLARE
  v_orphan_folds INTEGER;
  v_orphan_assertions INTEGER;
  v_orphan_evidence INTEGER;
BEGIN
  -- Check Fold → Assertion lineage
  SELECT COUNT(*)
  INTO v_orphan_folds
  FROM state.fold_state_snapshot fss
  WHERE fss.decision_horizon = p_decision_horizon
    AND EXISTS (
      SELECT 1 FROM UNNEST(fss.basis_assertion_ids) AS id
      WHERE NOT EXISTS (SELECT 1 FROM runtime.assertion WHERE assertion_id = id)
    );

  -- Check Assertion → Evidence lineage
  SELECT COUNT(*)
  INTO v_orphan_assertions
  FROM runtime.assertion a
  WHERE NOT EXISTS (SELECT 1 FROM runtime.evidence WHERE evidence_id = a.source_evidence_id);

  -- Check Evidence → Raw lineage
  SELECT COUNT(*)
  INTO v_orphan_evidence
  FROM runtime.evidence e
  WHERE NOT EXISTS (SELECT 1 FROM raw.raw_event WHERE raw_event_id = e.raw_event_id);

  RETURN QUERY
  SELECT 'Fold→Assertion→Evidence→Raw', v_orphan_folds, v_orphan_assertions, v_orphan_evidence,
    CASE WHEN v_orphan_folds = 0 AND v_orphan_assertions = 0 AND v_orphan_evidence = 0
      THEN 'PASS' ELSE 'FAIL' END;
END;
$$ LANGUAGE plpgsql;
