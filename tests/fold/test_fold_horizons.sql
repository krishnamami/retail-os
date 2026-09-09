-- =====================================================================
-- Fold Test Fixtures: Temporal Horizons
-- =====================================================================
-- Purpose: Validate temporal replay and delayed arrival scenarios
-- Strategy: Analyze production Assertions by effective_at and arrival_at
-- =====================================================================

-- =====================================================================
-- Test 1: Delayed Arrival Scenario
-- =====================================================================
-- Verify that Assertions arriving AFTER decision_horizon are excluded

SELECT 'TEST: Delayed Arrival Exclusion' AS test_name;

WITH delayed_assertions AS (
  SELECT
    subject_type, subject_id, property_name,
    effective_at, arrival_at,
    '2026-06-20 10:45:00+00'::timestamptz AS decision_horizon
  FROM runtime.assertion
  WHERE arrival_at > '2026-06-20 10:45:00+00'
)
SELECT
  COUNT(*) AS delayed_assertion_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: No Assertions arrive after horizon'
       ELSE 'WARN: ' || COUNT(*) || ' Assertions arrive after horizon'
  END AS status,
  'These should NOT be included in Fold at horizon 2026-06-20 10:45' AS note
FROM delayed_assertions;

-- =====================================================================
-- Test 2: Future effective_at Exclusion
-- =====================================================================
-- Verify that Assertions with effective_at > decision_horizon are excluded

SELECT 'TEST: Future effective_at Exclusion' AS test_name;

WITH future_assertions AS (
  SELECT
    subject_type, subject_id, property_name,
    effective_at, arrival_at,
    '2026-06-20 10:45:00+00'::timestamptz AS decision_horizon
  FROM runtime.assertion
  WHERE effective_at > '2026-06-20 10:45:00+00'
)
SELECT
  COUNT(*) AS future_assertion_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: No Assertions effective after horizon'
       ELSE 'WARN: ' || COUNT(*) || ' Assertions effective after horizon'
  END AS status,
  'These should NOT be included in Fold at horizon 2026-06-20 10:45' AS note
FROM future_assertions;

-- =====================================================================
-- Test 3: Eligible Assertions at Horizon
-- =====================================================================
-- Verify Assertions actually eligible for Fold evaluation

SELECT 'TEST: Eligible Assertions at Horizon' AS test_name;

WITH eligible_assertions AS (
  SELECT COUNT(*) AS count
  FROM runtime.assertion
  WHERE arrival_at <= '2026-06-20 10:45:00+00'
    AND effective_at <= '2026-06-20 10:45:00+00'
)
SELECT
  count,
  CASE WHEN count = 107 THEN 'PASS: All 107 production Assertions eligible'
       ELSE 'FAIL: Expected 107, got ' || count
  END AS status
FROM eligible_assertions;

-- =====================================================================
-- Test 4: Effective_at Diversity
-- =====================================================================
-- Analyze the range of effective_at timestamps in corpus

SELECT 'TEST: effective_at Temporal Distribution' AS test_name;

SELECT
  DATE_TRUNC('day', effective_at) AS day,
  COUNT(*) AS assertion_count,
  MIN(effective_at) AS earliest,
  MAX(effective_at) AS latest
FROM runtime.assertion
WHERE arrival_at <= '2026-06-20 10:45:00+00'
  AND effective_at <= '2026-06-20 10:45:00+00'
GROUP BY DATE_TRUNC('day', effective_at)
ORDER BY day;

-- =====================================================================
-- Test 5: Arrival_at Diversity
-- =====================================================================
-- Analyze the range of arrival_at timestamps in corpus

SELECT 'TEST: arrival_at Temporal Distribution' AS test_name;

SELECT
  DATE_TRUNC('day', arrival_at) AS day,
  COUNT(*) AS assertion_count,
  MIN(arrival_at) AS earliest,
  MAX(arrival_at) AS latest
FROM runtime.assertion
WHERE arrival_at <= '2026-06-20 10:45:00+00'
GROUP BY DATE_TRUNC('day', arrival_at)
ORDER BY day;

-- =====================================================================
-- Test 6: MAX(effective_at) Per Property
-- =====================================================================
-- Verify that properties have deterministic MAX(effective_at)

SELECT 'TEST: Deterministic MAX(effective_at)' AS test_name;

WITH max_effective_dates AS (
  SELECT
    subject_type, subject_id, property_name,
    MAX(effective_at) AS max_effective_at,
    COUNT(*) AS assertion_at_max
  FROM runtime.assertion
  WHERE arrival_at <= '2026-06-20 10:45:00+00'
    AND effective_at <= '2026-06-20 10:45:00+00'
  GROUP BY subject_type, subject_id, property_name
  HAVING COUNT(*) > 0
)
SELECT
  COUNT(*) AS properties_with_assertions,
  COUNT(CASE WHEN assertion_at_max = 1 THEN 1 END) AS properties_with_single_assertion,
  COUNT(CASE WHEN assertion_at_max > 1 THEN 1 END) AS properties_with_multiple_at_same_effective_at,
  'Multiple Assertions at same effective_at → check for CONTRADICTED state' AS note
FROM max_effective_dates;

-- =====================================================================
-- Test 7: No Future Horizons in Corpus
-- =====================================================================
-- Verify that no Assertions have effective_at beyond maximum horizon

SELECT 'TEST: Maximum Effective_at' AS test_name;

SELECT
  MAX(effective_at) AS latest_effective_at,
  MIN(effective_at) AS earliest_effective_at,
  MAX(arrival_at) AS latest_arrival_at,
  '2026-06-20 10:45:00+00'::timestamptz AS decision_horizon,
  CASE WHEN MAX(effective_at) <= '2026-06-20 10:45:00+00'
       AND MAX(arrival_at) <= '2026-06-20 10:45:00+00'
    THEN 'PASS: All timestamps <= horizon'
    ELSE 'FAIL: Some timestamps exceed horizon'
  END AS status
FROM runtime.assertion;

-- =====================================================================
-- Test 8: Temporal Consistency Check
-- =====================================================================
-- Verify that arrival_at >= effective_at (platform learns after fact occurs)

SELECT 'TEST: Temporal Consistency (arrival_at >= effective_at)' AS test_name;

WITH temporal_violations AS (
  SELECT COUNT(*) AS count
  FROM runtime.assertion
  WHERE arrival_at < effective_at
)
SELECT
  count,
  CASE WHEN count = 0 THEN 'PASS: All arrival_at >= effective_at'
       ELSE 'FAIL: ' || count || ' Assertions violate temporal ordering'
  END AS status
FROM temporal_violations;

-- =====================================================================
-- Test Summary
-- =====================================================================
SELECT 'Temporal horizon tests completed. Verify output for PASS status.' AS summary;
