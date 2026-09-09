-- =====================================================================
-- STEP 4H VERIFICATION QUERIES — Run after deployment
-- =====================================================================
-- Execute each query and provide results to continue with Step 4I
-- =====================================================================

-- =====================================================================
-- QUERY 1: Verify installed function uses LEFT JOIN LATERAL
-- =====================================================================
-- EXPECTED: Shows function definition containing "LEFT JOIN LATERAL UNNEST"
-- If it shows "FROM property_entries, LATERAL" then deployment failed
-- =====================================================================
SELECT pg_get_functiondef(oid) as fold_snapshot_definition
FROM pg_proc 
WHERE proname = 'fold_snapshot_at_horizon' 
  AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'runtime')
LIMIT 1;

-- =====================================================================
-- QUERY 2: Verify basis_ids are COALESCE'd to empty array
-- =====================================================================
-- EXPECTED: Check the property_entries section includes
-- "array_agg(DISTINCT u.basis_id ORDER BY u.basis_id) FILTER (WHERE u.basis_id IS NOT NULL)"
-- =====================================================================
SELECT pg_get_functiondef(oid) as fold_snapshot_definition
FROM pg_proc 
WHERE proname = 'fold_snapshot_at_horizon' 
  AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'runtime')
LIMIT 1;

-- =====================================================================
-- QUERY 3: Count persisted Run #1 failed snapshots
-- =====================================================================
-- EXPECTED: 51 rows (failed snapshots preserved)
-- NOTE: Replace '<decision_horizon_from_run_1>' with actual horizon timestamp
-- Example: '2026-09-06 12:00:00+00:00'
-- =====================================================================
SELECT 
  COUNT(*) as failed_run_1_snapshots,
  COUNT(DISTINCT subject_type) as subject_types,
  COUNT(DISTINCT subject_id) as distinct_subjects
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-09-06 14:30:45.123456+00:00';

-- =====================================================================
-- QUERY 4: Get actual active KB version
-- =====================================================================
-- EXPECTED: Returns single row with current KB version (e.g., 'KB-v1.2.3')
-- =====================================================================
SELECT 
  kb_version,
  is_active,
  created_at
FROM runtime.governed_knowledge_base 
WHERE is_active = true 
ORDER BY created_at DESC 
LIMIT 1;

-- =====================================================================
-- QUERY 5: Get actual active policy version
-- =====================================================================
-- EXPECTED: Returns single row with current policy version (e.g., 'POLICY-v2.1.0')
-- =====================================================================
SELECT 
  policy_version,
  is_active,
  created_at
FROM runtime.governed_policy 
WHERE is_active = true 
ORDER BY created_at DESC 
LIMIT 1;

-- =====================================================================
-- BONUS QUERY 6: Verify all 177 properties in applicable_properties
-- =====================================================================
-- EXPECTED: Returns count = 177 (all properties in property domain)
-- Shows distribution by subject_type
-- =====================================================================
WITH applicable_properties AS (
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
)
SELECT
  COUNT(*) as total_applicable_properties,
  subject_type,
  COUNT(DISTINCT property_name) as property_count_by_type
FROM applicable_properties
GROUP BY subject_type
ORDER BY subject_type;
