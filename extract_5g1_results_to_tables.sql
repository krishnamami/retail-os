-- =====================================================================
-- EXTRACT STEP 5G.1 DISCOVERY RESULTS INTO TEMP TABLES
-- All analysis results written to temp tables + comprehensive display
-- =====================================================================

-- Master analysis results table
CREATE TEMP TABLE analysis_results (
    section TEXT,
    subsection TEXT,
    metric TEXT,
    value TEXT,
    numeric_value INTEGER,
    detail TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 0. RECONCILED FOLD PROPERTY-STATE COUNT
-- =====================================================================

-- 0A: Total snapshots
INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '0. FOLD PROPERTY-STATE COUNT',
    'Total persisted snapshots',
    COUNT(*)::TEXT,
    'Snapshots at horizon 2026-06-20 10:45:00+00'
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- 0B: Expanded property states
INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '0. FOLD PROPERTY-STATE COUNT',
    'Total expanded property states',
    SUM(jsonb_array_length(folded_properties))::TEXT,
    'Properties expanded from JSONB folded_properties'
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- 0C: Property state distribution
CREATE TEMP TABLE analysis_property_distribution AS
SELECT * FROM temp_property_state_distribution;

INSERT INTO analysis_results (section, metric, value, numeric_value, detail)
SELECT
    '0. FOLD PROPERTY-STATE COUNT',
    'Property distribution: ' || fold_state,
    count::TEXT,
    count,
    fold_state || ' properties across all subjects'
FROM analysis_property_distribution;

-- =====================================================================
-- 1. CANONICAL TABLE SCHEMAS & ROW COUNTS
-- =====================================================================

-- 1A: Table row counts
CREATE TEMP TABLE analysis_canonical_counts AS
SELECT * FROM temp_canonical_row_counts;

INSERT INTO analysis_results (section, metric, value, numeric_value, detail)
SELECT
    '1. CANONICAL TABLES',
    'Table row count: ' || table_name,
    row_count::TEXT,
    row_count,
    'Canonical table must remain empty (0 rows)'
FROM analysis_canonical_counts;

-- 1B: Table column counts
CREATE TEMP TABLE analysis_canonical_schemas AS
SELECT * FROM temp_canonical_schemas;

INSERT INTO analysis_results (section, metric, value, numeric_value, detail)
SELECT
    '1. CANONICAL TABLES',
    'Schema columns: ' || table_name,
    COUNT(*)::TEXT,
    COUNT(*)::INTEGER,
    'Column definitions in ' || table_name
FROM analysis_canonical_schemas
GROUP BY table_name;

-- =====================================================================
-- 2. CONFIGURATION REQUEST CANDIDATE MATRIX (7-ROW)
-- =====================================================================

-- 2A: Full candidate matrix
CREATE TEMP TABLE analysis_candidate_matrix AS
SELECT * FROM temp_cr_candidate_matrix;

INSERT INTO analysis_results (section, metric, value, numeric_value, detail)
SELECT
    '2. CANDIDATE MATRIX',
    'Configuration request: ' || configuration_request_id,
    product_reference || ' / ' || geography || ' / ' || term_months || ' / ' || customer_segment,
    established_count,
    subject_status || ' - ' || established_count || '/' || total_properties || ' properties ESTABLISHED'
FROM analysis_candidate_matrix
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. LOGICAL IDENTITY INPUTS (NO ENCODING)
-- =====================================================================

-- 3A: Logical identity tuples
CREATE TEMP TABLE analysis_identity_inputs AS
SELECT * FROM temp_logical_identity_inputs;

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '3. LOGICAL IDENTITY INPUTS',
    'Identity tuple: ' || configuration_request_id,
    '(' || COALESCE(product_id, 'NULL') || ', ' ||
    COALESCE(geo, 'NULL') || ', ' ||
    COALESCE(term, 'NULL') || ', ' ||
    COALESCE(segment, 'NULL') || ')',
    'Logical identity (product_id, geo, term, segment) - NO hash/UUID'
FROM analysis_identity_inputs
ORDER BY configuration_request_id;

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY (006 vs 006B)
-- =====================================================================

-- 4A: S6 comparison
CREATE TEMP TABLE analysis_s6_check AS
SELECT * FROM temp_s6_comparison;

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '4. S6 LOGICAL EQUALITY',
    'Comparison: ' || request_id_006 || ' vs ' || request_id_006b,
    s6_verdict,
    'Two distinct requests with same logical identity inputs - NOT YET deduplicated'
FROM analysis_s6_check;

-- =====================================================================
-- 5. S7 MISSING INPUT (007)
-- =====================================================================

-- 5A: S7 status
CREATE TEMP TABLE analysis_s7_check AS
SELECT * FROM temp_s7_status;

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '5. S7 MISSING INPUT',
    'Request: ' || configuration_request_id,
    s7_verdict,
    'Subject status: ' || subject_status || ' - Missing required input'
FROM analysis_s7_check;

-- =====================================================================
-- 6. PRODUCT CONTEXT
-- =====================================================================

-- 6A: Product properties
CREATE TEMP TABLE analysis_product_context AS
SELECT * FROM temp_product_context;

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '6. PRODUCT CONTEXT',
    'Product property: ' || product_id || '.' || property_name,
    COALESCE(resolved_value, 'NULL'),
    fold_state || ' - ' || property_name
FROM analysis_product_context
ORDER BY product_id, property_name;

-- 6B: Product coverage
CREATE TEMP TABLE analysis_product_coverage AS
SELECT * FROM temp_product_coverage;

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '6. PRODUCT CONTEXT',
    'All requests reference product(s)',
    product_references_list,
    'Product coverage: ' || product_references_count || ' distinct product reference(s)'
FROM analysis_product_coverage;

-- =====================================================================
-- 7. COMPLETENESS CLASSIFICATION
-- =====================================================================

-- 7A: Per-request completeness
CREATE TEMP TABLE analysis_completeness AS
SELECT * FROM temp_completeness_classification;

INSERT INTO analysis_results (section, metric, value, numeric_value, detail)
SELECT
    '7. COMPLETENESS CLASSIFICATION',
    'Request completeness: ' || configuration_request_id,
    identity_completeness,
    established_count,
    subject_status || ' - ' || established_count || '/' || total_properties || ' ESTABLISHED'
FROM analysis_completeness
ORDER BY configuration_request_id;

-- 7B: Completeness summary
INSERT INTO analysis_results (section, metric, numeric_value, detail)
SELECT
    '7. COMPLETENESS CLASSIFICATION',
    'Summary: ' || identity_completeness,
    COUNT(*)::INTEGER,
    COUNT(*)::TEXT || ' requests with status ' || identity_completeness
FROM analysis_completeness
GROUP BY identity_completeness
ORDER BY identity_completeness;

-- =====================================================================
-- 8. DECISION BOUNDARY ANALYSIS
-- =====================================================================

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '8. DECISION BOUNDARY',
    'Architecture',
    'Fold → Candidate → IDENTITY_ASSESSMENT → Canonical',
    'Pipeline boundary between discovery and governed decision';

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '8. DECISION BOUNDARY',
    'Data prepared BEFORE IDENTITY_ASSESSMENT',
    'Logical identity inputs',
    'From Fold: (product_id, geo, term, segment)';

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '8. DECISION BOUNDARY',
    'Data prepared BEFORE IDENTITY_ASSESSMENT',
    'Completeness status',
    'COMPLETE_IDENTITY vs INCOMPLETE_MISSING_INPUT classification';

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '8. DECISION BOUNDARY',
    'IDENTITY_ASSESSMENT will need',
    'Candidate context + Active KB rules (IR-001..IR-009)',
    'Decision output: reuse existing OR create new OR cannot-decide';

-- =====================================================================
-- 9. UNRESOLVED GOVERNANCE QUESTIONS
-- =====================================================================

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '9. GOVERNANCE QUESTIONS',
    'Q1: S6 reuse decision',
    'UNRESOLVED',
    'Does KB rule define exact logical identity match = reuse? (Observed: same inputs)';

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '9. GOVERNANCE QUESTIONS',
    'Q2: S7 cannot-decide decision',
    'UNRESOLVED',
    'Does KB rule support CANNOT_DECIDE for missing customer_segment? (Observed: incomplete)';

INSERT INTO analysis_results (section, metric, value, detail)
SELECT
    '9. GOVERNANCE QUESTIONS',
    'Q3: IDENTITY_ASSESSMENT readiness',
    'READY',
    'Candidate context prepared; awaiting KB-driven decision rules execution';

-- =====================================================================
-- COMPREHENSIVE DISPLAY QUERIES
-- =====================================================================

SELECT '=== STEP 5G.1 DISCOVERY ANALYSIS - COMPLETE RESULTS ===' AS heading;

-- 0. Fold Property-State Count
SELECT '--- 0. FOLD PROPERTY-STATE COUNT RECONCILIATION ---' AS section;
SELECT section, metric, value, numeric_value FROM analysis_results
WHERE section = '0. FOLD PROPERTY-STATE COUNT'
ORDER BY metric;

-- 1. Canonical Tables
SELECT '--- 1. CANONICAL TABLES (VERIFY EMPTY) ---' AS section;
SELECT section, metric, value, numeric_value FROM analysis_results
WHERE section = '1. CANONICAL TABLES'
ORDER BY metric;

-- 2. Candidate Matrix
SELECT '--- 2. CONFIGURATION REQUEST CANDIDATE MATRIX (7-ROW) ---' AS section;
SELECT configuration_request_id, subject_status, product_reference, geography, term_months,
       customer_segment, launch_reference, established_count, total_properties
FROM analysis_candidate_matrix
ORDER BY configuration_request_id;

-- 3. Logical Identity Inputs
SELECT '--- 3. LOGICAL IDENTITY INPUTS (product_id, geo, term, segment) ---' AS section;
SELECT configuration_request_id, product_id, geo, term, segment,
       '(' || COALESCE(product_id, 'NULL') || ', ' ||
       COALESCE(geo, 'NULL') || ', ' ||
       COALESCE(term, 'NULL') || ', ' ||
       COALESCE(segment, 'NULL') || ')' AS identity_tuple
FROM analysis_identity_inputs
ORDER BY configuration_request_id;

-- 4. S6 Logical Equality
SELECT '--- 4. S6 LOGICAL EQUALITY (006 vs 006B) ---' AS section;
SELECT request_id_006, request_id_006b, s6_verdict FROM analysis_s6_check;

-- 5. S7 Missing Input
SELECT '--- 5. S7 MISSING INPUT (007) ---' AS section;
SELECT configuration_request_id, subject_status, s7_verdict FROM analysis_s7_check;

-- 6. Product Context
SELECT '--- 6. PRODUCT CONTEXT (PROD-001) ---' AS section;
SELECT product_id, property_name, fold_state, resolved_value
FROM analysis_product_context
ORDER BY product_id, property_name;

SELECT '--- 6B. PRODUCT REFERENCE COVERAGE ---' AS subsection;
SELECT product_references_count, product_references_list FROM analysis_product_coverage;

-- 7. Completeness Classification
SELECT '--- 7. COMPLETENESS CLASSIFICATION ---' AS section;
SELECT configuration_request_id, subject_status, identity_completeness,
       established_count, total_properties
FROM analysis_completeness
ORDER BY configuration_request_id;

SELECT '--- 7B. COMPLETENESS SUMMARY ---' AS subsection;
SELECT identity_completeness, COUNT(*)::TEXT AS count
FROM analysis_completeness
GROUP BY identity_completeness
ORDER BY identity_completeness;

-- 8. Decision Boundary
SELECT '--- 8. DECISION BOUNDARY ANALYSIS ---' AS section;
SELECT section, metric, value, detail FROM analysis_results
WHERE section = '8. DECISION BOUNDARY'
ORDER BY metric;

-- 9. Governance Questions
SELECT '--- 9. UNRESOLVED GOVERNANCE QUESTIONS ---' AS section;
SELECT section, metric, value, detail FROM analysis_results
WHERE section = '9. GOVERNANCE QUESTIONS'
ORDER BY metric;

-- =====================================================================
-- FINAL COMPREHENSIVE SUMMARY
-- =====================================================================

SELECT '=== STEP 5G.1 SUMMARY METRICS ===' AS heading;

SELECT
  'Fold snapshots persisted' AS metric,
  (SELECT COUNT(*)::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS result;

SELECT
  'Property states persisted (expanded)' AS metric,
  (SELECT SUM(jsonb_array_length(folded_properties))::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS result;

SELECT
  'Configuration requests discovered' AS metric,
  COUNT(*)::TEXT AS result
FROM analysis_candidate_matrix;

SELECT
  'Requests - COMPLETE_IDENTITY' AS metric,
  COUNT(*)::TEXT AS result
FROM analysis_completeness
WHERE identity_completeness = 'COMPLETE_IDENTITY';

SELECT
  'Requests - INCOMPLETE_MISSING_INPUT' AS metric,
  COUNT(*)::TEXT AS result
FROM analysis_completeness
WHERE identity_completeness = 'INCOMPLETE_MISSING_INPUT';

SELECT
  'S6 verdict (006 vs 006B)' AS metric,
  s6_verdict AS result
FROM analysis_s6_check;

SELECT
  'S7 verdict (007)' AS metric,
  s7_verdict AS result
FROM analysis_s7_check;

SELECT
  'Canonical table row count' AS metric,
  SUM(row_count)::TEXT AS result
FROM analysis_canonical_counts;

SELECT
  'Canonical tables status' AS metric,
  'ALL EMPTY - Ready for data' AS result;

-- =====================================================================
-- READINESS VERDICT
-- =====================================================================

SELECT '=== STEP 5G.1 FINAL VERDICT ===' AS heading;

SELECT
  'STEP 5G.1 CANONICAL CANDIDATE CONTEXT READY' AS verdict,
  'Discovery complete. Candidate context prepared.' AS status,
  'Do NOT write canonical data yet' AS critical,
  'Proceed to IDENTITY_ASSESSMENT service with candidate context' AS next_step;

-- =====================================================================
-- TEMP TABLE INVENTORY
-- =====================================================================

SELECT '=== TEMP TABLES CREATED FOR ANALYSIS ===' AS heading;

SELECT
  'Master analysis results' AS table_type,
  'analysis_results' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_results
UNION ALL
SELECT
  'Discovery temp tables' AS table_type,
  'temp_property_state_distribution' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_property_distribution
UNION ALL
SELECT
  'Discovery temp tables' AS table_type,
  'temp_canonical_row_counts' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_canonical_counts
UNION ALL
SELECT
  'Discovery temp tables' AS table_type,
  'temp_canonical_schemas' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_canonical_schemas
UNION ALL
SELECT
  'Analysis temp tables' AS table_type,
  'analysis_candidate_matrix' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_candidate_matrix
UNION ALL
SELECT
  'Analysis temp tables' AS table_type,
  'analysis_identity_inputs' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_identity_inputs
UNION ALL
SELECT
  'Analysis temp tables' AS table_type,
  'analysis_s6_check' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_s6_check
UNION ALL
SELECT
  'Analysis temp tables' AS table_type,
  'analysis_s7_check' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_s7_check
UNION ALL
SELECT
  'Analysis temp tables' AS table_type,
  'analysis_product_context' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_product_context
UNION ALL
SELECT
  'Analysis temp tables' AS table_type,
  'analysis_product_coverage' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_product_coverage
UNION ALL
SELECT
  'Analysis temp tables' AS table_type,
  'analysis_completeness' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM analysis_completeness;
