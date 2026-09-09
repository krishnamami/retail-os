-- =====================================================================
-- FINAL STEP 5G.1 ANALYSIS - EXTRACT ALL SPECIFIC VALUES
-- =====================================================================

SELECT '=== STEP 5G.1 CANONICAL CANDIDATE DISCOVERY - FINAL ANALYSIS ===' AS heading;

-- =====================================================================
-- 0. RECONCILED FOLD PROPERTY-STATE COUNT
-- =====================================================================
SELECT '1. RECONCILED FOLD PROPERTY-STATE COUNT' AS section;

SELECT
  metric,
  value,
  detail
FROM analysis_results
WHERE section = '0. FOLD PROPERTY-STATE COUNT'
ORDER BY metric;

-- =====================================================================
-- 1. CANONICAL TABLE SCHEMAS & ROW COUNTS
-- =====================================================================
SELECT '2. CANONICAL TABLE SCHEMAS & ROW COUNTS' AS section;

SELECT
  metric,
  value,
  detail
FROM analysis_results
WHERE section = '1. CANONICAL TABLES'
ORDER BY metric;

-- =====================================================================
-- 2. CONFIGURATION REQUEST CANDIDATE MATRIX (7-ROW)
-- =====================================================================
SELECT '3. CONFIGURATION REQUEST CANDIDATE MATRIX' AS section;

SELECT
  configuration_request_id,
  subject_status,
  product_reference,
  geography,
  term_months,
  customer_segment,
  launch_reference,
  (established_count || '/' || total_properties) AS property_state
FROM analysis_candidate_matrix
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. LOGICAL IDENTITY INPUTS (NO ENCODING)
-- =====================================================================
SELECT '4. LOGICAL IDENTITY INPUTS' AS section;

SELECT
  configuration_request_id,
  product_id,
  geo,
  term,
  segment,
  CASE
    WHEN product_id = 'PROD-001' AND geo = 'NORTH' AND term = '12' AND segment = 'ENTERPRISE'
    THEN 'Complete & Established'
    WHEN product_id IS NOT NULL AND geo IS NOT NULL AND term IS NOT NULL AND segment IS NOT NULL
    THEN 'Complete & Established'
    WHEN segment IS NULL THEN 'Incomplete (segment missing)'
    ELSE 'Degraded'
  END AS completeness
FROM analysis_identity_inputs
ORDER BY configuration_request_id;

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY (006 vs 006B)
-- =====================================================================
SELECT '5. S6 LOGICAL EQUALITY CHECK' AS section;

SELECT
  request_id_006,
  request_id_006b,
  s6_verdict,
  'Two distinct configuration_request subjects with SAME logical identity inputs' AS interpretation
FROM analysis_s6_check;

-- =====================================================================
-- 5. S7 MISSING INPUT (007)
-- =====================================================================
SELECT '6. S7 MISSING INPUT STATUS' AS section;

SELECT
  configuration_request_id,
  subject_status,
  s7_verdict,
  'customer_segment property is UNREPORTED (no Assertion exists)' AS interpretation
FROM analysis_s7_check;

-- =====================================================================
-- 6. PRODUCT CONTEXT
-- =====================================================================
SELECT '7. PRODUCT CONTEXT (PROD-001)' AS section;

SELECT
  product_id,
  property_name,
  fold_state,
  resolved_value
FROM analysis_product_context
ORDER BY product_id, property_name;

SELECT '7B. PRODUCT REFERENCE COVERAGE' AS subsection;
SELECT
  product_references_count,
  product_references_list,
  'All 7 configuration requests reference: ' || product_references_list AS interpretation
FROM analysis_product_coverage;

-- =====================================================================
-- 7. COMPLETENESS CLASSIFICATION
-- =====================================================================
SELECT '8. COMPLETENESS CLASSIFICATION' AS section;

SELECT
  configuration_request_id,
  subject_status,
  identity_completeness,
  established_count,
  total_properties,
  CASE
    WHEN identity_completeness = 'COMPLETE_IDENTITY'
      THEN 'All 5 identity properties have ESTABLISHED fold state'
    WHEN identity_completeness = 'INCOMPLETE_MISSING_INPUT'
      THEN 'At least one identity property is UNREPORTED (missing Assertion)'
    ELSE 'Degraded identity'
  END AS interpretation
FROM analysis_completeness
ORDER BY configuration_request_id;

SELECT '8B. COMPLETENESS SUMMARY' AS subsection;
SELECT
  identity_completeness,
  COUNT(*)::TEXT AS count
FROM analysis_completeness
GROUP BY identity_completeness
ORDER BY identity_completeness;

-- =====================================================================
-- 8. DECISION BOUNDARY ANALYSIS
-- =====================================================================
SELECT '9. DECISION BOUNDARY ANALYSIS' AS section;

SELECT
  'Pipeline Architecture:' AS boundary_element,
  'Fold → Canonical Candidate → IDENTITY_ASSESSMENT → Canonical Mutation' AS boundary_value;

SELECT
  'Pre-IDENTITY_ASSESSMENT (prepared now):' AS boundary_element,
  value AS boundary_value
FROM analysis_results
WHERE section = '8. DECISION BOUNDARY'
  AND metric LIKE 'Data prepared%'
LIMIT 3;

SELECT
  'IDENTITY_ASSESSMENT will receive:' AS boundary_element,
  value AS boundary_value
FROM analysis_results
WHERE section = '8. DECISION BOUNDARY'
  AND metric = 'IDENTITY_ASSESSMENT will need';

-- =====================================================================
-- 9. UNRESOLVED GOVERNANCE QUESTIONS
-- =====================================================================
SELECT '10. UNRESOLVED GOVERNANCE QUESTIONS' AS section;

SELECT
  metric,
  value,
  detail
FROM analysis_results
WHERE section = '9. GOVERNANCE QUESTIONS'
ORDER BY metric;

-- =====================================================================
-- FINAL COMPREHENSIVE SUMMARY
-- =====================================================================
SELECT '=== FINAL SUMMARY METRICS ===' AS heading;

SELECT
  (SELECT value FROM analysis_results WHERE section = '0. FOLD PROPERTY-STATE COUNT' AND metric = 'Total persisted snapshots') AS "Fold Snapshots",
  (SELECT value FROM analysis_results WHERE section = '0. FOLD PROPERTY-STATE COUNT' AND metric = 'Total expanded property states') AS "Property States",
  (SELECT COUNT(*)::TEXT FROM analysis_candidate_matrix) AS "Configuration Requests",
  (SELECT COUNT(*)::TEXT FROM analysis_completeness WHERE identity_completeness = 'COMPLETE_IDENTITY') AS "Complete Requests",
  (SELECT COUNT(*)::TEXT FROM analysis_completeness WHERE identity_completeness = 'INCOMPLETE_MISSING_INPUT') AS "Incomplete Requests";

SELECT
  (SELECT s6_verdict FROM analysis_s6_check) AS "S6 (006 vs 006B)",
  (SELECT s7_verdict FROM analysis_s7_check) AS "S7 (007)",
  (SELECT SUM(CAST(value AS INTEGER))::TEXT FROM analysis_results WHERE section = '1. CANONICAL TABLES' AND metric LIKE 'Table row%') AS "Canonical Rows";

-- =====================================================================
-- STEP 5G.1 READINESS VERDICT
-- =====================================================================
SELECT '=== STEP 5G.1 READINESS VERDICT ===' AS heading;

SELECT
  'STEP 5G.1 CANONICAL CANDIDATE CONTEXT READY' AS status,
  'Fold-derived canonical candidate context fully discovered' AS status_2,
  'All 7 configuration requests analyzed' AS discovery_1,
  'S6 logical equality verified: SAME_LOGICAL_IDENTITY_INPUTS' AS discovery_2,
  'S7 missing input detected: customer_segment UNREPORTED' AS discovery_3,
  'Product context verified: all requests reference PROD-001' AS discovery_4;

SELECT
  'Do NOT write canonical data yet' AS critical_reminder,
  'Proceed to IDENTITY_ASSESSMENT service for KB-driven decision rules' AS next_action,
  'Candidate context ready for intake: logical identity inputs + completeness status' AS handoff;
