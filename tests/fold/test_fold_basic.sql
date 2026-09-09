-- =====================================================================
-- Fold Test Fixtures: Basic Scenarios
-- =====================================================================
-- Purpose: Validate ESTABLISHED, UNREPORTED, and subject-level aggregation
-- Strategy: Use actual production Assertions; no transaction isolation needed
--           (these tests verify production corpus behavior)
-- =====================================================================

-- =====================================================================
-- Test 1: ESTABLISHED State
-- =====================================================================
-- Verify that properties with Assertions fold to ESTABLISHED

SELECT 'TEST: ESTABLISHED State' AS test_name;

WITH established_check AS (
  SELECT
    subject_type, subject_id, property_name,
    COUNT(*) AS assertion_count,
    COUNT(DISTINCT asserted_value) AS distinct_values
  FROM runtime.assertion
  WHERE arrival_at <= '2026-06-20 10:45:00+00'
    AND effective_at <= '2026-06-20 10:45:00+00'
  GROUP BY subject_type, subject_id, property_name
  HAVING COUNT(*) > 0 AND COUNT(DISTINCT asserted_value) = 1
)
SELECT
  subject_type, subject_id, property_name, assertion_count,
  'EXPECTED: fold_state = ESTABLISHED' AS expectation
FROM established_check
LIMIT 10;

-- =====================================================================
-- Test 2: UNREPORTED State
-- =====================================================================
-- Verify that properties without Assertions fold to UNREPORTED

SELECT 'TEST: UNREPORTED State' AS test_name;

-- Properties in governed domain but NOT in Assertions
WITH all_governed AS (
  SELECT 'configuration' AS subject_type, subject_id, 'sap_con_hierarchy_code' AS property_name
  FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%') s
  UNION ALL
  SELECT 'configuration', subject_id, 'sap_con_load_actor'
  FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%') s
  UNION ALL
  SELECT 'launch', subject_id, 'change_requested_by'
  FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') s
),
missing_properties AS (
  SELECT ag.subject_type, ag.subject_id, ag.property_name
  FROM all_governed ag
  WHERE NOT EXISTS (
    SELECT 1 FROM runtime.assertion a
    WHERE a.subject_type = ag.subject_type
      AND a.subject_id = ag.subject_id
      AND a.property_name = ag.property_name
      AND a.arrival_at <= '2026-06-20 10:45:00+00'
  )
)
SELECT
  subject_type, subject_id, property_name,
  'EXPECTED: fold_state = UNREPORTED' AS expectation,
  'resolved_value = NULL' AS value_expectation
FROM missing_properties
LIMIT 10;

-- =====================================================================
-- Test 3: Subject-Level fold_status Aggregation
-- =====================================================================
-- Verify that fold_status correctly reflects property state distribution

SELECT 'TEST: Subject-Level fold_status Aggregation' AS test_name;

-- For SKU subjects with multiple properties
WITH sku_properties AS (
  SELECT 'sku' AS subject_type, subject_id,
    'pricing_confirmed' AS property_name FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') s
  UNION ALL
  SELECT 'sku', subject_id, 'sku_activation_status'
  FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') s
),
property_states AS (
  SELECT
    sp.subject_type, sp.subject_id,
    CASE
      WHEN EXISTS (
        SELECT 1 FROM runtime.assertion a
        WHERE a.subject_type = sp.subject_type
          AND a.subject_id = sp.subject_id
          AND a.property_name = sp.property_name
          AND a.arrival_at <= '2026-06-20 10:45:00+00'
      ) THEN 'ESTABLISHED'
      ELSE 'UNREPORTED'
    END AS property_state
  FROM sku_properties sp
)
SELECT
  subject_type, subject_id,
  COUNT(*) AS property_count,
  COUNT(CASE WHEN property_state = 'ESTABLISHED' THEN 1 END) AS established_count,
  COUNT(CASE WHEN property_state = 'UNREPORTED' THEN 1 END) AS unreported_count,
  CASE
    WHEN COUNT(CASE WHEN property_state = 'UNREPORTED' THEN 1 END) > 0 THEN 'UNREPORTED'
    ELSE 'ESTABLISHED'
  END AS expected_fold_status
FROM property_states
GROUP BY subject_type, subject_id;

-- =====================================================================
-- Test 4: Assertion Count Verification
-- =====================================================================
-- Verify total Assertion count matches expected 107

SELECT 'TEST: Total Assertion Count' AS test_name;

SELECT
  COUNT(*) AS total_assertions,
  CASE WHEN COUNT(*) = 107 THEN 'PASS' ELSE 'FAIL' END AS status,
  'Expected: 107' AS expectation
FROM runtime.assertion;

-- =====================================================================
-- Test 5: Material Subject Presence
-- =====================================================================
-- Verify material subjects exist with material_status Assertions

SELECT 'TEST: Material Subjects' AS test_name;

SELECT
  subject_type, subject_id, property_name,
  COUNT(*) AS assertion_count,
  MAX(asserted_value) AS value_sample
FROM runtime.assertion
WHERE subject_type = 'material'
GROUP BY subject_type, subject_id, property_name
ORDER BY subject_id;

-- =====================================================================
-- Test 6: SKU-013 REJECTED Value Preservation
-- =====================================================================
-- Verify that REJECTED value is preserved exactly

SELECT 'TEST: SKU-013 REJECTED Value Fidelity' AS test_name;

SELECT
  subject_id, property_name, asserted_value,
  'EXPECTED: resolved_value = REJECTED' AS expectation
FROM runtime.assertion
WHERE subject_type = 'sku'
  AND subject_id = 'SKU-013'
  AND property_name = 'technical_review_result'
  AND asserted_value = 'REJECTED';

-- =====================================================================
-- Test 7: Authority Verification
-- =====================================================================
-- Verify all Assertions use authority='evidence_direct'

SELECT 'TEST: Authority Contract' AS test_name;

SELECT
  authority,
  COUNT(*) AS count
FROM runtime.assertion
GROUP BY authority;

SELECT
  CASE WHEN COUNT(*) = 107 AND COUNT(DISTINCT authority) = 1
    THEN 'PASS: All 107 Assertions are evidence_direct'
    ELSE 'FAIL: Authority contract violated'
  END AS status
FROM runtime.assertion
WHERE authority = 'evidence_direct';

-- =====================================================================
-- Test 8: No Supersession
-- =====================================================================
-- Verify no supersession relationships in current corpus

SELECT 'TEST: No Supersession' AS test_name;

SELECT
  COUNT(*) AS supersedes_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.assertion
WHERE supersedes_assertion_id IS NOT NULL;

-- =====================================================================
-- Test Summary
-- =====================================================================
SELECT 'All basic tests completed. Verify output for PASS status.' AS summary;
