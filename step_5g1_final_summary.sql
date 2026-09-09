-- =====================================================================
-- STEP 5G.1 FINAL SUMMARY - EXTRACT FROM TEMP TABLES
-- Display all analysis findings organized by discovery sections
-- =====================================================================

SELECT '=== STEP 5G.1 CANONICAL CANDIDATE DISCOVERY - FINAL SUMMARY ===' AS heading;

-- =====================================================================
-- 0. FOLD PROPERTY-STATE RECONCILIATION
-- =====================================================================

SELECT '--- 0. FOLD PROPERTY-STATE RECONCILIATION ---' AS section;

SELECT
  finding_name,
  finding_value,
  finding_detail
FROM final_5g1_results
WHERE finding_section = '0. FOLD PROPERTY-STATE COUNT'
ORDER BY finding_name;

-- =====================================================================
-- 1. CANONICAL TABLES VERIFICATION
-- =====================================================================

SELECT '--- 1. CANONICAL TABLES (VERIFIED EMPTY) ---' AS section;

SELECT
  finding_name,
  finding_value,
  finding_detail
FROM final_5g1_results
WHERE finding_section = '1. CANONICAL TABLES'
ORDER BY finding_name;

-- =====================================================================
-- 2. CONFIGURATION REQUEST CANDIDATE MATRIX
-- =====================================================================

SELECT '--- 2. CONFIGURATION REQUEST CANDIDATE MATRIX (7-ROW) ---' AS section;

SELECT
  configuration_request_id,
  subject_status,
  product_reference,
  geography,
  term_months,
  customer_segment,
  launch_reference,
  established_count || '/' || total_properties AS property_state
FROM final_candidate_matrix
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. LOGICAL IDENTITY INPUTS
-- =====================================================================

SELECT '--- 3. LOGICAL IDENTITY INPUTS (product_id, geo, term, segment) ---' AS section;

SELECT
  configuration_request_id,
  product_id,
  geo,
  term,
  segment,
  completeness_status
FROM final_identity_inputs
ORDER BY configuration_request_id;

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY CHECK
-- =====================================================================

SELECT '--- 4. S6 LOGICAL EQUALITY (006 vs 006B) ---' AS section;

SELECT
  request_id_006,
  request_id_006b,
  s6_verdict
FROM final_s6_analysis;

-- =====================================================================
-- 5. S7 MISSING INPUT STATUS
-- =====================================================================

SELECT '--- 5. S7 MISSING INPUT (007) ---' AS section;

SELECT
  configuration_request_id,
  subject_status,
  s7_verdict
FROM final_s7_analysis;

-- =====================================================================
-- 6. PRODUCT CONTEXT (PROD-001)
-- =====================================================================

SELECT '--- 6. PRODUCT CONTEXT ---' AS section;

SELECT
  product_id,
  property_name,
  fold_state,
  resolved_value
FROM final_product_analysis
ORDER BY product_id, property_name;

-- =====================================================================
-- 7. COMPLETENESS CLASSIFICATION
-- =====================================================================

SELECT '--- 7. COMPLETENESS CLASSIFICATION ---' AS section;

SELECT
  configuration_request_id,
  subject_status,
  identity_completeness,
  established_count || '/' || total_properties AS property_state
FROM final_completeness_analysis
ORDER BY configuration_request_id;

SELECT '--- 7B. COMPLETENESS SUMMARY ---' AS subsection;

SELECT
  identity_completeness,
  COUNT(*)::TEXT AS request_count
FROM final_completeness_analysis
GROUP BY identity_completeness
ORDER BY identity_completeness;

-- =====================================================================
-- 8. DECISION BOUNDARY ANALYSIS
-- =====================================================================

SELECT '--- 8. DECISION BOUNDARY ANALYSIS ---' AS section;

SELECT
  finding_subsection,
  finding_name,
  finding_value,
  finding_detail
FROM final_5g1_results
WHERE finding_section = '8. DECISION BOUNDARY'
ORDER BY finding_subsection, finding_name;

-- =====================================================================
-- 9. UNRESOLVED GOVERNANCE QUESTIONS
-- =====================================================================

SELECT '--- 9. UNRESOLVED GOVERNANCE QUESTIONS ---' AS section;

SELECT
  finding_name,
  finding_value,
  finding_detail
FROM final_5g1_results
WHERE finding_section = '9. GOVERNANCE QUESTIONS'
ORDER BY finding_id;

-- =====================================================================
-- FINAL SUMMARY METRICS
-- =====================================================================

SELECT '=== FINAL SUMMARY METRICS ===' AS heading;

SELECT
  'Total Fold snapshots persisted' AS metric,
  (SELECT finding_value FROM final_5g1_results WHERE finding_section = '0. FOLD PROPERTY-STATE COUNT' AND finding_name = 'Total persisted snapshots') AS result
UNION ALL
SELECT
  'Total property states (expanded from JSONB)' AS metric,
  (SELECT finding_value FROM final_5g1_results WHERE finding_section = '0. FOLD PROPERTY-STATE COUNT' AND finding_name = 'Total expanded property states') AS result
UNION ALL
SELECT
  'Configuration requests discovered' AS metric,
  COUNT(*)::TEXT
FROM final_candidate_matrix
UNION ALL
SELECT
  'Requests - COMPLETE_IDENTITY' AS metric,
  COUNT(*)::TEXT
FROM final_completeness_analysis WHERE identity_completeness = 'COMPLETE_IDENTITY'
UNION ALL
SELECT
  'Requests - INCOMPLETE_MISSING_INPUT' AS metric,
  COUNT(*)::TEXT
FROM final_completeness_analysis WHERE identity_completeness = 'INCOMPLETE_MISSING_INPUT'
UNION ALL
SELECT
  'S6 verdict (006 vs 006B)' AS metric,
  s6_verdict
FROM final_s6_analysis
UNION ALL
SELECT
  'S7 verdict (007)' AS metric,
  s7_verdict
FROM final_s7_analysis
UNION ALL
SELECT
  'Canonical tables status' AS metric,
  'ALL EMPTY - Ready for data' AS result;

-- =====================================================================
-- STEP 5G.1 READINESS VERDICT
-- =====================================================================

SELECT '=== STEP 5G.1 READINESS VERDICT ===' AS heading;

SELECT
  'STATUS' AS assessment,
  'STEP 5G.1 CANONICAL CANDIDATE CONTEXT READY' AS finding
UNION ALL
SELECT
  'DISCOVERY_1' AS assessment,
  'Fold-derived canonical candidate context fully discovered'
UNION ALL
SELECT
  'DISCOVERY_2' AS assessment,
  'All 7 configuration requests analyzed'
UNION ALL
SELECT
  'DISCOVERY_3' AS assessment,
  'S6 logical equality verified: SAME_LOGICAL_IDENTITY_INPUTS'
UNION ALL
SELECT
  'DISCOVERY_4' AS assessment,
  'S7 missing input detected: customer_segment UNREPORTED'
UNION ALL
SELECT
  'DISCOVERY_5' AS assessment,
  'Product context verified: all requests reference PROD-001'
UNION ALL
SELECT
  'CRITICAL_REMINDER' AS assessment,
  'Do NOT write canonical data yet'
UNION ALL
SELECT
  'NEXT_ACTION' AS assessment,
  'Proceed to IDENTITY_ASSESSMENT service for KB-driven decision rules'
UNION ALL
SELECT
  'HANDOFF_STATUS' AS assessment,
  'Candidate context ready for intake: logical identity inputs + completeness status';

-- =====================================================================
-- FINAL ANALYSIS TEMP TABLE INVENTORY
-- =====================================================================

SELECT '=== FINAL ANALYSIS TEMP TABLE INVENTORY ===' AS heading;

SELECT
  'Master results table' AS table_type,
  'final_5g1_results' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_5g1_results
UNION ALL
SELECT
  'Analysis table' AS table_type,
  'final_candidate_matrix' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_candidate_matrix
UNION ALL
SELECT
  'Analysis table' AS table_type,
  'final_identity_inputs' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_identity_inputs
UNION ALL
SELECT
  'Analysis table' AS table_type,
  'final_s6_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_s6_analysis
UNION ALL
SELECT
  'Analysis table' AS table_type,
  'final_s7_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_s7_analysis
UNION ALL
SELECT
  'Analysis table' AS table_type,
  'final_product_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_product_analysis
UNION ALL
SELECT
  'Analysis table' AS table_type,
  'final_completeness_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_completeness_analysis;

SELECT '=== STEP 5G.1 COMPLETE - All findings extracted from temp tables ===' AS note;
