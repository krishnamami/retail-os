-- =====================================================================
-- EXTRACT STEP 5G.1 DISCOVERY RESULTS FROM TEMP TABLES
-- =====================================================================

SELECT '=== STEP 5G.1 FINAL ANALYSIS ===' AS heading;

-- =====================================================================
-- 0. RECONCILED FOLD PROPERTY-STATE COUNT
-- =====================================================================
SELECT '--- 0. FOLD PROPERTY-STATE COUNT ---' AS section;

SELECT
  'Total persisted snapshots' AS metric,
  (SELECT COUNT(*)::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS value;

SELECT
  'Total expanded property states' AS metric,
  (SELECT SUM(jsonb_array_length(folded_properties))::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS value;

SELECT * FROM temp_property_state_distribution;

-- =====================================================================
-- 1. CANONICAL TABLE SCHEMAS & ROW COUNTS
-- =====================================================================
SELECT '--- 1. CANONICAL TABLES (VERIFY EMPTY) ---' AS section;

SELECT * FROM temp_canonical_row_counts;

SELECT
  'claris.product columns' AS table_name,
  COUNT(*)::TEXT AS column_count
FROM temp_canonical_schemas WHERE table_name = 'claris.product'
UNION ALL
SELECT
  'claris.configuration columns' AS table_name,
  COUNT(*)::TEXT AS column_count
FROM temp_canonical_schemas WHERE table_name = 'claris.configuration'
UNION ALL
SELECT
  'claris.configuration_version columns' AS table_name,
  COUNT(*)::TEXT AS column_count
FROM temp_canonical_schemas WHERE table_name = 'claris.configuration_version';

-- =====================================================================
-- 2. CONFIGURATION REQUEST CANDIDATE MATRIX (7-ROW)
-- =====================================================================
SELECT '--- 2. CANDIDATE MATRIX (7 CONFIGURATION REQUESTS) ---' AS section;

SELECT
  configuration_request_id,
  subject_status,
  product_reference,
  geography,
  term_months,
  customer_segment,
  launch_reference,
  established_count || '/' || total_properties AS property_state
FROM temp_cr_candidate_matrix
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. LOGICAL IDENTITY INPUTS (NO ENCODING)
-- =====================================================================
SELECT '--- 3. LOGICAL IDENTITY INPUTS (product_id, geo, term, segment) ---' AS section;

SELECT
  configuration_request_id,
  product_id,
  geo,
  term,
  segment,
  '(' || COALESCE(product_id, 'NULL') || ', ' ||
  COALESCE(geo, 'NULL') || ', ' ||
  COALESCE(term, 'NULL') || ', ' ||
  COALESCE(segment, 'NULL') || ')' AS identity_tuple
FROM temp_logical_identity_inputs
ORDER BY configuration_request_id;

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY (006 vs 006B)
-- =====================================================================
SELECT '--- 4. S6 LOGICAL EQUALITY CHECK ---' AS section;

SELECT
  request_id_006,
  request_id_006b,
  s6_verdict
FROM temp_s6_comparison;

-- =====================================================================
-- 5. S7 MISSING INPUT (007)
-- =====================================================================
SELECT '--- 5. S7 MISSING INPUT STATUS ---' AS section;

SELECT
  configuration_request_id,
  subject_status,
  s7_verdict,
  property_states
FROM temp_s7_status;

-- =====================================================================
-- 6. PRODUCT CONTEXT
-- =====================================================================
SELECT '--- 6. PRODUCT CONTEXT (PROD-001) ---' AS section;

SELECT * FROM temp_product_context
ORDER BY product_id, property_name;

SELECT '--- 6B. PRODUCT REFERENCE COVERAGE ---' AS subsection;
SELECT * FROM temp_product_coverage;

-- =====================================================================
-- 7. COMPLETENESS CLASSIFICATION
-- =====================================================================
SELECT '--- 7. COMPLETENESS CLASSIFICATION ---' AS section;

SELECT
  configuration_request_id,
  subject_status,
  identity_completeness,
  established_count || '/' || total_properties AS property_count
FROM temp_completeness_classification
ORDER BY configuration_request_id;

-- Count by completeness
SELECT
  'Completeness Summary' AS type,
  identity_completeness,
  COUNT(*)::TEXT AS count
FROM temp_completeness_classification
GROUP BY identity_completeness
ORDER BY identity_completeness;

-- =====================================================================
-- 8. DECISION BOUNDARY ANALYSIS
-- =====================================================================
SELECT '--- 8. DECISION BOUNDARY ---' AS section;

SELECT
  'Fold → Candidate Context → IDENTITY_ASSESSMENT → Canonical Mutation' AS architecture,
  'Information prepared BEFORE governed IDENTITY_ASSESSMENT:' AS checkpoint;

SELECT
  'From Fold:' AS source,
  'Logical identity inputs (product_id, geo, term, segment)' AS data,
  'Completeness status (COMPLETE vs INCOMPLETE)' AS data_2,
  'Reference to Fold subject types & properties' AS data_3;

SELECT
  'What IDENTITY_ASSESSMENT service needs:' AS requires,
  'Candidate logical identity context' AS need_1,
  'Active KB rules (IR-001..IR-009)' AS need_2,
  'Decision outcome: reuse existing OR create new OR cannot-decide' AS need_3;

-- =====================================================================
-- 9. UNRESOLVED GOVERNANCE QUESTIONS
-- =====================================================================
SELECT '--- 9. GOVERNANCE QUESTIONS ---' AS section;

SELECT
  'Q1: For S6 (006 vs 006B) - exact logical identity match = reuse?' AS question,
  'Status: Same logical identity inputs observed; KB outcome NOT YET EXECUTED' AS status;

SELECT
  'Q2: For S7 (007) - missing required input = cannot-decide?' AS question,
  'Status: Missing customer_segment detected; KB outcome NOT YET EXECUTED' AS status;

SELECT
  'Q3: Readiness for IDENTITY_ASSESSMENT intake?' AS question,
  'Status: Candidate context prepared; awaiting KB-driven decision rules' AS status;

-- =====================================================================
-- FINAL COMPREHENSIVE SUMMARY
-- =====================================================================
SELECT '=== STEP 5G.1 DISCOVERY SUMMARY ===' AS heading;

SELECT
  'Fold snapshots persisted' AS metric,
  (SELECT COUNT(*)::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS result;

SELECT
  'Property states persisted (expanded from JSONB)' AS metric,
  (SELECT SUM(jsonb_array_length(folded_properties))::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS result;

SELECT
  'Configuration requests discovered' AS metric,
  (SELECT COUNT(*)::TEXT FROM temp_cr_candidate_matrix) AS result;

SELECT
  'Configuration requests - COMPLETE_IDENTITY' AS metric,
  (SELECT COUNT(*)::TEXT FROM temp_completeness_classification WHERE identity_completeness = 'COMPLETE_IDENTITY') AS result;

SELECT
  'Configuration requests - INCOMPLETE_MISSING_INPUT' AS metric,
  (SELECT COUNT(*)::TEXT FROM temp_completeness_classification WHERE identity_completeness = 'INCOMPLETE_MISSING_INPUT') AS result;

SELECT
  'S6 verdict (006 vs 006B)' AS metric,
  (SELECT s6_verdict FROM temp_s6_comparison) AS result;

SELECT
  'S7 verdict (007)' AS metric,
  (SELECT s7_verdict FROM temp_s7_status) AS result;

SELECT
  'Canonical tables row count' AS metric,
  ((SELECT SUM(row_count)::TEXT FROM temp_canonical_row_counts)) AS result;

SELECT
  'Canonical table status' AS metric,
  'ALL EMPTY - Ready for data' AS result;

SELECT '=== READINESS VERDICT ===' AS heading;
SELECT
  'STEP 5G.1 CANONICAL CANDIDATE CONTEXT READY' AS verdict,
  'Do NOT write canonical data yet' AS critical,
  'Proceed to IDENTITY_ASSESSMENT service with candidate context' AS next_step;
