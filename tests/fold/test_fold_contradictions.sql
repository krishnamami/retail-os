-- =====================================================================
-- Fold Test Fixtures: Contradiction Detection
-- =====================================================================
-- Purpose: Validate CONTRADICTED state detection
-- Note: Current production corpus may not have contradictions
-- This test identifies scenarios that WOULD produce CONTRADICTED
-- =====================================================================

-- =====================================================================
-- Test 1: Contradiction Definition
-- =====================================================================
-- Identify properties with multiple distinct values at same MAX(effective_at)

SELECT 'TEST: Contradiction Scenarios' AS test_name;

WITH property_value_counts AS (
  SELECT
    subject_type, subject_id, property_name,
    effective_at,
    COUNT(*) AS assertion_count,
    COUNT(DISTINCT asserted_value) AS distinct_value_count,
    string_agg(DISTINCT asserted_value, ', ') AS values_at_this_time
  FROM runtime.assertion
  WHERE arrival_at <= '2026-06-20 10:45:00+00'
    AND effective_at <= '2026-06-20 10:45:00+00'
  GROUP BY subject_type, subject_id, property_name, effective_at
),
max_effective_per_property AS (
  SELECT
    subject_type, subject_id, property_name,
    MAX(effective_at) AS max_effective_at
  FROM property_value_counts
  GROUP BY subject_type, subject_id, property_name
),
contradictions AS (
  SELECT
    pvc.subject_type, pvc.subject_id, pvc.property_name,
    pvc.effective_at, pvc.assertion_count, pvc.distinct_value_count,
    pvc.values_at_this_time
  FROM property_value_counts pvc
  INNER JOIN max_effective_per_property mep
    ON pvc.subject_type = mep.subject_type
    AND pvc.subject_id = mep.subject_id
    AND pvc.property_name = mep.property_name
    AND pvc.effective_at = mep.max_effective_at
  WHERE pvc.distinct_value_count > 1
)
SELECT
  COUNT(*) AS contradiction_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: No contradictions in production corpus'
       ELSE 'INFO: ' || COUNT(*) || ' properties WOULD be CONTRADICTED'
  END AS status,
  'If present, these properties should fold_state = CONTRADICTED' AS note
FROM contradictions;

-- =====================================================================
-- Test 2: Contradicted Properties Detail
-- =====================================================================
-- If contradictions exist, show their details

SELECT 'TEST: Contradiction Details' AS test_name;

WITH property_value_counts AS (
  SELECT
    subject_type, subject_id, property_name,
    effective_at,
    COUNT(*) AS assertion_count,
    COUNT(DISTINCT asserted_value) AS distinct_value_count,
    string_agg(DISTINCT asserted_value, ' | ') AS values_at_this_time,
    array_agg(DISTINCT assertion_id) AS assertion_ids
  FROM runtime.assertion
  WHERE arrival_at <= '2026-06-20 10:45:00+00'
    AND effective_at <= '2026-06-20 10:45:00+00'
  GROUP BY subject_type, subject_id, property_name, effective_at
),
max_effective_per_property AS (
  SELECT
    subject_type, subject_id, property_name,
    MAX(effective_at) AS max_effective_at
  FROM property_value_counts
  GROUP BY subject_type, subject_id, property_name
),
contradictions AS (
  SELECT
    pvc.subject_type, pvc.subject_id, pvc.property_name,
    pvc.effective_at, pvc.assertion_count, pvc.distinct_value_count,
    pvc.values_at_this_time, pvc.assertion_ids
  FROM property_value_counts pvc
  INNER JOIN max_effective_per_property mep
    ON pvc.subject_type = mep.subject_type
    AND pvc.subject_id = mep.subject_id
    AND pvc.property_name = mep.property_name
    AND pvc.effective_at = mep.max_effective_at
  WHERE pvc.distinct_value_count > 1
)
SELECT
  subject_type, subject_id, property_name,
  effective_at, assertion_count, distinct_value_count,
  values_at_this_time,
  'fold_state = CONTRADICTED' AS expected_fold_state,
  'resolved_value = NULL' AS expected_value,
  assertion_ids AS basis_assertion_ids
FROM contradictions
ORDER BY subject_type, subject_id, property_name;

-- =====================================================================
-- Test 3: Single-Value Properties (ESTABLISHED)
-- =====================================================================
-- Count properties that have exactly one distinct value at MAX(effective_at)

SELECT 'TEST: Single-Value (ESTABLISHED) Properties' AS test_name;

WITH property_value_counts AS (
  SELECT
    subject_type, subject_id, property_name,
    effective_at,
    COUNT(DISTINCT asserted_value) AS distinct_value_count
  FROM runtime.assertion
  WHERE arrival_at <= '2026-06-20 10:45:00+00'
    AND effective_at <= '2026-06-20 10:45:00+00'
  GROUP BY subject_type, subject_id, property_name, effective_at
),
max_effective_per_property AS (
  SELECT
    subject_type, subject_id, property_name,
    MAX(effective_at) AS max_effective_at
  FROM property_value_counts
  GROUP BY subject_type, subject_id, property_name
),
established_properties AS (
  SELECT
    pvc.subject_type, pvc.subject_id, pvc.property_name,
    pvc.distinct_value_count
  FROM property_value_counts pvc
  INNER JOIN max_effective_per_property mep
    ON pvc.subject_type = mep.subject_type
    AND pvc.subject_id = mep.subject_id
    AND pvc.property_name = mep.property_name
    AND pvc.effective_at = mep.max_effective_at
  WHERE pvc.distinct_value_count = 1
)
SELECT
  COUNT(*) AS established_property_count,
  CASE WHEN COUNT(*) = 107 THEN 'PASS: All 107 are single-valued'
       ELSE 'EXPECTED: 107, got ' || COUNT(*)
  END AS status
FROM established_properties;

-- =====================================================================
-- Test 4: No Internal Algorithm Errors
-- =====================================================================
-- Verify no assertion records have NULL assertion_id

SELECT 'TEST: Data Integrity' AS test_name;

SELECT
  COUNT(*) AS records_with_null_id,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: No NULL assertion_ids'
       ELSE 'FAIL: Integrity violation'
  END AS status
FROM runtime.assertion
WHERE assertion_id IS NULL;

-- =====================================================================
-- Test 5: Authority Consistency in Contradictions
-- =====================================================================
-- If contradictions exist, verify authority is consistent (no precedence info)

SELECT 'TEST: Authority Consistency' AS test_name;

WITH contradicted_assertions AS (
  SELECT
    a.assertion_id, a.authority,
    COUNT(DISTINCT a.asserted_value) OVER (
      PARTITION BY a.subject_type, a.subject_id, a.property_name
      ORDER BY a.effective_at DESC
      ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS distinct_values
  FROM runtime.assertion a
  WHERE arrival_at <= '2026-06-20 10:45:00+00'
    AND effective_at <= '2026-06-20 10:45:00+00'
)
SELECT
  COUNT(DISTINCT authority) AS authority_types,
  CASE WHEN COUNT(DISTINCT authority) = 1 THEN 'PASS: Single authority in corpus'
       ELSE 'INFO: Multiple authorities present'
  END AS status,
  'Current: evidence_direct (no precedence)' AS note
FROM contradicted_assertions
WHERE distinct_values > 1;

-- =====================================================================
-- Test Summary
-- =====================================================================
SELECT 'Contradiction detection tests completed. No contradictions expected in production corpus.' AS summary;
