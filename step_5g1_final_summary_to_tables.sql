-- =====================================================================
-- STEP 5G.1 FINAL SUMMARY - WRITE ALL RESULTS TO TEMP TABLES
-- Extract from analysis tables + write comprehensive summary to temp table
-- =====================================================================

-- Master final summary results table
CREATE TEMP TABLE final_summary_results (
    summary_section TEXT,
    summary_subsection TEXT,
    summary_item TEXT,
    summary_value TEXT,
    summary_detail TEXT,
    summary_numeric INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 0. FOLD PROPERTY-STATE RECONCILIATION
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
SELECT
    '0. FOLD PROPERTY-STATE RECONCILIATION',
    finding_name,
    finding_value,
    finding_detail
FROM final_5g1_results
WHERE finding_section = '0. FOLD PROPERTY-STATE COUNT'
ORDER BY finding_name;

-- =====================================================================
-- 1. CANONICAL TABLES VERIFICATION
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
SELECT
    '1. CANONICAL TABLES VERIFICATION',
    finding_name,
    finding_value,
    finding_detail
FROM final_5g1_results
WHERE finding_section = '1. CANONICAL TABLES'
ORDER BY finding_name;

-- =====================================================================
-- 2. CONFIGURATION REQUEST CANDIDATE MATRIX
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail, summary_numeric)
SELECT
    '2. CANDIDATE MATRIX',
    'Request: ' || configuration_request_id,
    product_reference || ' / ' || geography || ' / ' || term_months || ' / ' || customer_segment,
    subject_status || ' - ' || established_count || '/' || total_properties || ' properties ESTABLISHED',
    established_count
FROM final_candidate_matrix
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. LOGICAL IDENTITY INPUTS
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
SELECT
    '3. LOGICAL IDENTITY INPUTS',
    'Identity: ' || configuration_request_id,
    '(' || COALESCE(product_id, 'NULL') || ', ' ||
    COALESCE(geo, 'NULL') || ', ' ||
    COALESCE(term, 'NULL') || ', ' ||
    COALESCE(segment, 'NULL') || ')',
    completeness_status || ' - NO hash/UUID/encoding'
FROM final_identity_inputs
ORDER BY configuration_request_id;

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY CHECK
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
SELECT
    '4. S6 LOGICAL EQUALITY',
    'Comparison: ' || request_id_006 || ' vs ' || request_id_006b,
    s6_verdict,
    'Two distinct configuration_request subjects with SAME logical identity inputs'
FROM final_s6_analysis;

-- =====================================================================
-- 5. S7 MISSING INPUT STATUS
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
SELECT
    '5. S7 MISSING INPUT',
    'Request: ' || configuration_request_id,
    s7_verdict,
    'Subject status: ' || subject_status || ' - Missing required input'
FROM final_s7_analysis;

-- =====================================================================
-- 6. PRODUCT CONTEXT (PROD-001)
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
SELECT
    '6. PRODUCT CONTEXT',
    'Product property: ' || product_id || '.' || property_name,
    COALESCE(resolved_value, 'NULL'),
    fold_state || ' - ' || property_name
FROM final_product_analysis
ORDER BY product_id, property_name;

-- =====================================================================
-- 7. COMPLETENESS CLASSIFICATION
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail, summary_numeric)
SELECT
    '7. COMPLETENESS CLASSIFICATION',
    'Request: ' || configuration_request_id,
    identity_completeness,
    subject_status || ' - ' || established_count || '/' || total_properties || ' properties ESTABLISHED',
    established_count
FROM final_completeness_analysis
ORDER BY configuration_request_id;

-- Completeness summary
INSERT INTO final_summary_results (summary_section, summary_subsection, summary_item, summary_value, summary_numeric)
SELECT
    '7. COMPLETENESS CLASSIFICATION',
    'Summary',
    'Count: ' || identity_completeness,
    COUNT(*)::TEXT,
    COUNT(*)::INTEGER
FROM final_completeness_analysis
GROUP BY identity_completeness
ORDER BY identity_completeness;

-- =====================================================================
-- 8. DECISION BOUNDARY ANALYSIS
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_subsection, summary_item, summary_value, summary_detail)
SELECT
    '8. DECISION BOUNDARY',
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

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
SELECT
    '9. GOVERNANCE QUESTIONS',
    finding_name,
    finding_value,
    finding_detail
FROM final_5g1_results
WHERE finding_section = '9. GOVERNANCE QUESTIONS'
ORDER BY finding_id;

-- =====================================================================
-- FINAL SUMMARY METRICS
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value)
VALUES
    ('METRICS', 'Fold snapshots persisted', (SELECT finding_value FROM final_5g1_results WHERE finding_section = '0. FOLD PROPERTY-STATE COUNT' AND finding_name = 'Total persisted snapshots')),
    ('METRICS', 'Property states (expanded)', (SELECT finding_value FROM final_5g1_results WHERE finding_section = '0. FOLD PROPERTY-STATE COUNT' AND finding_name = 'Total expanded property states')),
    ('METRICS', 'Configuration requests', (SELECT COUNT(*)::TEXT FROM final_candidate_matrix)),
    ('METRICS', 'Requests - COMPLETE_IDENTITY', (SELECT COUNT(*)::TEXT FROM final_completeness_analysis WHERE identity_completeness = 'COMPLETE_IDENTITY')),
    ('METRICS', 'Requests - INCOMPLETE_MISSING_INPUT', (SELECT COUNT(*)::TEXT FROM final_completeness_analysis WHERE identity_completeness = 'INCOMPLETE_MISSING_INPUT')),
    ('METRICS', 'S6 verdict (006 vs 006B)', (SELECT s6_verdict FROM final_s6_analysis)),
    ('METRICS', 'S7 verdict (007)', (SELECT s7_verdict FROM final_s7_analysis)),
    ('METRICS', 'Canonical tables status', 'ALL EMPTY - Ready for data');

-- =====================================================================
-- READINESS VERDICT
-- =====================================================================

INSERT INTO final_summary_results (summary_section, summary_item, summary_value, summary_detail)
VALUES
    ('READINESS_VERDICT', 'Status', 'STEP 5G.1 CANONICAL CANDIDATE CONTEXT READY', 'Fold-derived canonical candidate context fully discovered'),
    ('READINESS_VERDICT', 'Discovery_1', 'All 7 configuration requests analyzed', 'Complete matrix extraction'),
    ('READINESS_VERDICT', 'Discovery_2', 'S6 logical equality verified', 'SAME_LOGICAL_IDENTITY_INPUTS'),
    ('READINESS_VERDICT', 'Discovery_3', 'S7 missing input detected', 'customer_segment UNREPORTED'),
    ('READINESS_VERDICT', 'Discovery_4', 'Product context verified', 'all requests reference PROD-001'),
    ('READINESS_VERDICT', 'Critical_Reminder', 'Do NOT write canonical data yet', 'Awaiting governed decision phase'),
    ('READINESS_VERDICT', 'Next_Action', 'Proceed to IDENTITY_ASSESSMENT service', 'KB-driven decision rules execution'),
    ('READINESS_VERDICT', 'Handoff_Status', 'Candidate context ready for intake', 'logical identity inputs + completeness status');

-- =====================================================================
-- COMPREHENSIVE DISPLAY FROM TEMP TABLE
-- =====================================================================

SELECT '=== STEP 5G.1 CANONICAL CANDIDATE DISCOVERY - FINAL SUMMARY ===' AS heading;

-- 0. Fold Property-State Reconciliation
SELECT '--- 0. FOLD PROPERTY-STATE RECONCILIATION ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '0. FOLD PROPERTY-STATE RECONCILIATION'
ORDER BY summary_item;

-- 1. Canonical Tables
SELECT '--- 1. CANONICAL TABLES (VERIFIED EMPTY) ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '1. CANONICAL TABLES VERIFICATION'
ORDER BY summary_item;

-- 2. Candidate Matrix
SELECT '--- 2. CONFIGURATION REQUEST CANDIDATE MATRIX (7-ROW) ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '2. CANDIDATE MATRIX'
ORDER BY summary_item;

-- 3. Logical Identity Inputs
SELECT '--- 3. LOGICAL IDENTITY INPUTS (product_id, geo, term, segment) ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '3. LOGICAL IDENTITY INPUTS'
ORDER BY summary_item;

-- 4. S6 Logical Equality
SELECT '--- 4. S6 LOGICAL EQUALITY (006 vs 006B) ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '4. S6 LOGICAL EQUALITY';

-- 5. S7 Missing Input
SELECT '--- 5. S7 MISSING INPUT (007) ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '5. S7 MISSING INPUT';

-- 6. Product Context
SELECT '--- 6. PRODUCT CONTEXT (PROD-001) ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '6. PRODUCT CONTEXT'
ORDER BY summary_item;

-- 7. Completeness Classification
SELECT '--- 7. COMPLETENESS CLASSIFICATION ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '7. COMPLETENESS CLASSIFICATION' AND summary_subsection IS NULL
ORDER BY summary_item;

SELECT '--- 7B. COMPLETENESS SUMMARY ---' AS subsection;
SELECT summary_item, summary_value FROM final_summary_results
WHERE summary_section = '7. COMPLETENESS CLASSIFICATION' AND summary_subsection = 'Summary'
ORDER BY summary_item;

-- 8. Decision Boundary
SELECT '--- 8. DECISION BOUNDARY ANALYSIS ---' AS section;
SELECT summary_subsection, summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '8. DECISION BOUNDARY'
ORDER BY summary_subsection, summary_item;

-- 9. Governance Questions
SELECT '--- 9. UNRESOLVED GOVERNANCE QUESTIONS ---' AS section;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = '9. GOVERNANCE QUESTIONS'
ORDER BY summary_item;

-- Final Metrics
SELECT '=== FINAL SUMMARY METRICS ===' AS heading;
SELECT summary_item, summary_value FROM final_summary_results
WHERE summary_section = 'METRICS'
ORDER BY summary_item;

-- Readiness Verdict
SELECT '=== STEP 5G.1 READINESS VERDICT ===' AS heading;
SELECT summary_item, summary_value, summary_detail FROM final_summary_results
WHERE summary_section = 'READINESS_VERDICT'
ORDER BY summary_item;

-- =====================================================================
-- FINAL TEMP TABLE INVENTORY
-- =====================================================================

SELECT '=== FINAL TEMP TABLE INVENTORY ===' AS heading;

SELECT
  'Master final analysis' AS table_type,
  'final_5g1_results' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_5g1_results
UNION ALL
SELECT
  'Master final summary' AS table_type,
  'final_summary_results' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_summary_results
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

SELECT '=== STEP 5G.1 COMPLETE - All findings written to final_summary_results temp table ===' AS note;
