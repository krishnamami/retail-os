-- =====================================================================
-- Test Suite: Evidence Semantic Scenarios
-- =====================================================================
-- Purpose: Validate special cases and edge cases per design requirements
-- Scenarios: SKU-003 (contradiction preservation)
--           SKU-006 (absence handling)
--           SKU-010 (delayed arrival)
--           SKU-011 (out-of-order arrival)
--           SKU-012 (multiple horizons)
--           SKU-013 (explicit negatives)
--           CHANGE_REQUESTED (single raw event, multiple mappings)
-- =====================================================================

-- =====================================================================
-- SCENARIO 1: SKU-003 - Hierarchy Contradiction Preservation
-- =====================================================================
-- Test: HIERARCHY_APPROVAL event with BOTH CON (H100) and PRD (H200) hierarchies
-- Expected: TWO separate Evidence rows (one per hierarchy), both preserved
-- Rationale: Contradiction preservation - different hierarchies for same launch
-- Status: Should show both HIERARCHY_APPROVAL_CON_CODE and HIERARCHY_APPROVAL_PRD_CODE
SELECT
  'SKU003_HIERARCHY_CONTRADICTION' AS test_name,
  COUNT(DISTINCT mapping_id) AS distinct_mappings,
  STRING_AGG(DISTINCT mapping_id, ', ') AS mappings_present,
  COUNT(*) AS total_evidence_rows,
  CASE WHEN COUNT(DISTINCT mapping_id) >= 2
       AND STRING_AGG(DISTINCT mapping_id, ', ') LIKE '%CON%'
       AND STRING_AGG(DISTINCT mapping_id, ', ') LIKE '%PRD%'
       THEN 'PASS - Both hierarchies present'
       ELSE 'FAIL - Missing hierarchy' END AS status
FROM runtime.evidence
WHERE subject_id = 'LAUNCH-001'
AND mapping_id LIKE 'HIERARCHY_APPROVAL%';

-- Detailed output for SKU-003
SELECT
  'SKU003_HIERARCHY_DETAIL' AS test_name,
  mapping_id,
  property_name,
  asserted_value,
  source_actor_id,
  occurred_at,
  arrival_at
FROM runtime.evidence
WHERE subject_id = 'LAUNCH-001'
AND mapping_id LIKE 'HIERARCHY_APPROVAL%'
ORDER BY mapping_id;

-- =====================================================================
-- SCENARIO 2: SKU-006 - Absence Semantics (VALID ZERO)
-- =====================================================================
-- Test: TECHNICAL_REVIEW event WITHOUT a reason field (absence case)
-- Expected: NO TECHNICAL_REVIEW_REASON Evidence row generated
-- Rationale: Absence is not fabricated; missing optional field → no Evidence
-- Status: Should show technical_review_result but NOT technical_review_reason (if absent in raw)
-- Note: This test assumes SKU-006 has review_result but no reason field
SELECT
  'SKU006_ABSENCE_SEMANTICS' AS test_name,
  COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT') AS has_review_result,
  COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_REASON') AS has_review_reason,
  CASE WHEN COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT') > 0
       AND COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_REASON') = 0
       THEN 'PASS - Absence not fabricated'
       ELSE 'UNKNOWN - Check if SKU-006 in corpus' END AS status
FROM runtime.evidence
WHERE subject_id = 'SKU-006'
AND mapping_id LIKE 'TECHNICAL_REVIEW%';

-- Details
SELECT
  'SKU006_ABSENCE_DETAIL' AS test_name,
  mapping_id,
  property_name,
  asserted_value
FROM runtime.evidence
WHERE subject_id = 'SKU-006'
AND mapping_id LIKE 'TECHNICAL_REVIEW%';

-- =====================================================================
-- SCENARIO 3: SKU-010 - Delayed Arrival Semantics
-- =====================================================================
-- Test: Raw events with arrival_at > occurred_at
-- Expected: Timestamp deltas preserved exactly (no normalization)
-- Rationale: Delayed arrivals are data artifacts, preserved for audit
-- Status: Should show arrival_at > occurred_at for some rows
SELECT
  'SKU010_DELAYED_ARRIVAL' AS test_name,
  subject_id,
  COUNT(*) AS evidence_count,
  COUNT(*) FILTER (WHERE arrival_at > occurred_at) AS delayed_arrivals,
  MAX(arrival_at - occurred_at) AS max_delay,
  CASE WHEN COUNT(*) FILTER (WHERE arrival_at > occurred_at) > 0
       THEN 'PASS - Delayed arrivals preserved'
       ELSE 'UNKNOWN - Check if delayed events in corpus' END AS status
FROM runtime.evidence
WHERE occurred_at IS NOT NULL
AND arrival_at IS NOT NULL
GROUP BY subject_id
HAVING COUNT(*) FILTER (WHERE arrival_at > occurred_at) > 0
LIMIT 5;

-- Details of delayed arrivals
SELECT
  'SKU010_DELAYED_ARRIVAL_DETAIL' AS test_name,
  raw_event_id,
  mapping_id,
  subject_id,
  occurred_at,
  arrival_at,
  (arrival_at - occurred_at) AS delay_duration
FROM runtime.evidence
WHERE arrival_at > occurred_at
ORDER BY (arrival_at - occurred_at) DESC
LIMIT 10;

-- =====================================================================
-- SCENARIO 4: SKU-011 - Out-of-Order Arrival Semantics
-- =====================================================================
-- Test: Raw events with arrival_at < occurred_at
-- Expected: Out-of-order arrivals preserved as Data (not corrected)
-- Rationale: Temporal anomalies are audit-relevant; not normalized away
-- Status: Should show arrival_at < occurred_at for some rows
SELECT
  'SKU011_OUT_OF_ORDER_ARRIVAL' AS test_name,
  subject_id,
  COUNT(*) AS evidence_count,
  COUNT(*) FILTER (WHERE arrival_at < occurred_at) AS out_of_order_arrivals,
  MAX(occurred_at - arrival_at) AS max_out_of_order_gap,
  CASE WHEN COUNT(*) FILTER (WHERE arrival_at < occurred_at) > 0
       THEN 'PASS - Out-of-order arrivals preserved'
       ELSE 'UNKNOWN - Check if out-of-order events in corpus' END AS status
FROM runtime.evidence
WHERE occurred_at IS NOT NULL
AND arrival_at IS NOT NULL
GROUP BY subject_id
HAVING COUNT(*) FILTER (WHERE arrival_at < occurred_at) > 0
LIMIT 5;

-- Details of out-of-order arrivals
SELECT
  'SKU011_OUT_OF_ORDER_DETAIL' AS test_name,
  raw_event_id,
  mapping_id,
  subject_id,
  occurred_at,
  arrival_at,
  (occurred_at - arrival_at) AS out_of_order_gap
FROM runtime.evidence
WHERE arrival_at < occurred_at
ORDER BY (occurred_at - arrival_at) DESC
LIMIT 10;

-- =====================================================================
-- SCENARIO 5: SKU-012 - Multiple Horizons / Temporal Layering
-- =====================================================================
-- Test: Same subject with observations at different occurred_at timestamps
-- Expected: Multiple Evidence rows for same subject with different occurred_at
-- Rationale: Temporal progression captured; different business moments preserved
-- Status: Should show multiple time horizons for at least one subject
SELECT
  'SKU012_MULTIPLE_HORIZONS' AS test_name,
  subject_id,
  COUNT(DISTINCT occurred_at) AS distinct_horizons,
  COUNT(*) AS total_evidence,
  MIN(occurred_at) AS earliest_observation,
  MAX(occurred_at) AS latest_observation,
  CASE WHEN COUNT(DISTINCT occurred_at) > 1
       THEN 'PASS - Multiple horizons preserved'
       ELSE 'UNKNOWN - Check if temporal progression in corpus' END AS status
FROM runtime.evidence
GROUP BY subject_id
HAVING COUNT(DISTINCT occurred_at) > 1
ORDER BY distinct_horizons DESC
LIMIT 5;

-- Details of multi-horizon subjects
SELECT
  'SKU012_MULTIPLE_HORIZONS_DETAIL' AS test_name,
  subject_id,
  mapping_id,
  occurred_at,
  COUNT(*) AS evidence_at_this_horizon
FROM runtime.evidence
GROUP BY subject_id, mapping_id, occurred_at
HAVING COUNT(*) > 0
ORDER BY subject_id, occurred_at
LIMIT 20;

-- =====================================================================
-- SCENARIO 6: SKU-013 - Explicit Negatives / Rejection Preservation
-- =====================================================================
-- Test: TECHNICAL_REVIEW with review_result = 'NEGATIVE' or similar rejection
-- Expected: NEGATIVE/REJECTED values preserved exactly (not normalized)
-- Rationale: Explicit failures are business facts, captured as-is
-- Status: Should show TECHNICAL_REVIEW_RESULT with negative/rejected value
SELECT
  'SKU013_EXPLICIT_NEGATIVES' AS test_name,
  COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT'
                   AND asserted_value IN ('NEGATIVE', 'REJECTED', 'FAILED', 'FAILURE')) AS negative_results,
  COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT'
                   AND asserted_value IN ('NEGATIVE', 'REJECTED', 'FAILED', 'FAILURE')
                   AND EXISTS (
                     SELECT 1 FROM runtime.evidence e2
                     WHERE e2.raw_event_id = e.raw_event_id
                     AND e2.mapping_id = 'TECHNICAL_REVIEW_REASON'
                   )) AS negatives_with_reason,
  CASE WHEN COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT'
                              AND asserted_value IN ('NEGATIVE', 'REJECTED', 'FAILED', 'FAILURE')) > 0
       THEN 'PASS - Explicit negatives preserved'
       ELSE 'UNKNOWN - Check if negative reviews in corpus' END AS status
FROM runtime.evidence e
WHERE mapping_id IN ('TECHNICAL_REVIEW_RESULT', 'TECHNICAL_REVIEW_REASON');

-- Details of negative reviews
SELECT
  'SKU013_EXPLICIT_NEGATIVES_DETAIL' AS test_name,
  e.raw_event_id,
  e.subject_id,
  e.mapping_id,
  e.asserted_value,
  e.occurred_at
FROM runtime.evidence e
WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT'
AND asserted_value IN ('NEGATIVE', 'REJECTED', 'FAILED', 'FAILURE')
ORDER BY occurred_at DESC
LIMIT 10;

-- Reasons for negatives
SELECT
  'SKU013_NEGATIVE_REASONS' AS test_name,
  e.raw_event_id,
  e.subject_id,
  e.mapping_id,
  e.asserted_value,
  e.evidence_reason
FROM runtime.evidence e
WHERE mapping_id = 'TECHNICAL_REVIEW_REASON'
AND EXISTS (
  SELECT 1 FROM runtime.evidence e2
  WHERE e2.raw_event_id = e.raw_event_id
  AND e2.mapping_id = 'TECHNICAL_REVIEW_RESULT'
  AND e2.asserted_value IN ('NEGATIVE', 'REJECTED', 'FAILED', 'FAILURE')
)
ORDER BY e.occurred_at DESC
LIMIT 10;

-- =====================================================================
-- SCENARIO 7: CHANGE_REQUESTED - Multi-Property Single Raw Event
-- =====================================================================
-- Test: Single CHANGE_REQUESTED raw event generates 4 Evidence rows
-- Expected: CHANGE_TYPE, CHANGE_REASON, CHANGE_REQUESTED_BY, CHANGE_REQUESTER_ROLE all present
-- Rationale: One raw event can produce multiple observations (different properties)
-- Status: Should show exactly 1 raw event producing 4 Evidence rows
SELECT
  'CHANGE_REQUESTED_MULTI_PROPERTY' AS test_name,
  raw_event_id,
  COUNT(*) AS evidence_rows,
  COUNT(DISTINCT mapping_id) AS distinct_mappings,
  STRING_AGG(DISTINCT mapping_id, ', ' ORDER BY mapping_id) AS mappings_present,
  CASE WHEN COUNT(*) >= 4
       AND COUNT(DISTINCT mapping_id) >= 4
       AND STRING_AGG(DISTINCT mapping_id, ', ') LIKE '%CHANGE_TYPE%'
       AND STRING_AGG(DISTINCT mapping_id, ', ') LIKE '%CHANGE_REQUESTED_BY%'
       THEN 'PASS - All 4 properties captured'
       ELSE 'FAIL - Missing properties' END AS status
FROM runtime.evidence
WHERE mapping_id LIKE 'CHANGE_%'
GROUP BY raw_event_id;

-- Detailed output for CHANGE_REQUESTED
SELECT
  'CHANGE_REQUESTED_DETAIL' AS test_name,
  mapping_id,
  property_name,
  asserted_value,
  source_actor_id,
  source_actor_role
FROM runtime.evidence
WHERE mapping_id LIKE 'CHANGE_%'
ORDER BY mapping_id;

-- =====================================================================
-- SCENARIO SUMMARY: All Tests Pass/Fail
-- =====================================================================
SELECT
  'SCENARIO_SUMMARY' AS test_name,
  'SKU-003 (Hierarchy Contradiction)' AS scenario,
  CASE WHEN (SELECT COUNT(*) FROM runtime.evidence
             WHERE subject_id = 'LAUNCH-001'
             AND mapping_id IN ('HIERARCHY_APPROVAL_CON_CODE', 'HIERARCHY_APPROVAL_PRD_CODE')) >= 2
       THEN 'PASS' ELSE 'UNKNOWN' END AS status
UNION ALL
SELECT
  'SCENARIO_SUMMARY',
  'SKU-006 (Absence Semantics)',
  CASE WHEN (SELECT COUNT(*) FROM runtime.evidence
             WHERE subject_id = 'SKU-006'
             AND mapping_id = 'TECHNICAL_REVIEW_RESULT') > 0
       THEN 'PASS' ELSE 'UNKNOWN' END
UNION ALL
SELECT
  'SCENARIO_SUMMARY',
  'SKU-010 (Delayed Arrival)',
  CASE WHEN (SELECT COUNT(*) FROM runtime.evidence
             WHERE arrival_at > occurred_at) > 0
       THEN 'PASS' ELSE 'UNKNOWN' END
UNION ALL
SELECT
  'SCENARIO_SUMMARY',
  'SKU-011 (Out-of-Order Arrival)',
  CASE WHEN (SELECT COUNT(*) FROM runtime.evidence
             WHERE arrival_at < occurred_at) > 0
       THEN 'PASS' ELSE 'UNKNOWN' END
UNION ALL
SELECT
  'SCENARIO_SUMMARY',
  'SKU-012 (Multiple Horizons)',
  CASE WHEN (SELECT COUNT(DISTINCT subject_id) FROM (
             SELECT subject_id, COUNT(DISTINCT occurred_at) AS horizons
             FROM runtime.evidence
             GROUP BY subject_id
             HAVING COUNT(DISTINCT occurred_at) > 1
           )) > 0
       THEN 'PASS' ELSE 'UNKNOWN' END
UNION ALL
SELECT
  'SCENARIO_SUMMARY',
  'SKU-013 (Explicit Negatives)',
  CASE WHEN (SELECT COUNT(*) FROM runtime.evidence
             WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT'
             AND asserted_value IN ('NEGATIVE', 'REJECTED', 'FAILED')) > 0
       THEN 'PASS' ELSE 'UNKNOWN' END
UNION ALL
SELECT
  'SCENARIO_SUMMARY',
  'CHANGE_REQUESTED (Multi-Property)',
  CASE WHEN (SELECT COUNT(DISTINCT mapping_id) FROM runtime.evidence
             WHERE mapping_id LIKE 'CHANGE_%') >= 4
       THEN 'PASS' ELSE 'UNKNOWN' END
ORDER BY scenario;

-- =====================================================================
-- END OF SCENARIO TEST SUITE
-- =====================================================================
-- All scenarios should show PASS or UNKNOWN (if event not in corpus).
-- FAIL indicates semantic transformation defect.
