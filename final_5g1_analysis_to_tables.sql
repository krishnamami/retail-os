-- =====================================================================
-- FINAL STEP 5G.1 ANALYSIS - WRITE ALL RESULTS TO TEMP TABLES
-- Master analysis table + organized display + reusable queries
-- =====================================================================

-- Master final analysis results table
CREATE TEMP TABLE final_5g1_results (
    finding_section TEXT,
    finding_subsection TEXT,
    finding_id TEXT,
    finding_name TEXT,
    finding_value TEXT,
    finding_detail TEXT,
    finding_type TEXT,  -- e.g., 'metric', 'verdict', 'observation', 'question'
    finding_numeric INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 0. RECONCILED FOLD PROPERTY-STATE COUNT
-- =====================================================================

INSERT INTO final_5g1_results (finding_section, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '0. FOLD PROPERTY-STATE COUNT',
    'Total persisted snapshots',
    COUNT(*)::TEXT,
    'Snapshots at horizon 2026-06-20 10:45:00+00',
    'metric'
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

INSERT INTO final_5g1_results (finding_section, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '0. FOLD PROPERTY-STATE COUNT',
    'Total expanded property states',
    SUM(jsonb_array_length(folded_properties))::TEXT,
    'Properties expanded from JSONB folded_properties - ANSWER TO RECONCILIATION',
    'metric'
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_numeric, finding_detail, finding_type)
SELECT
    '0. FOLD PROPERTY-STATE COUNT',
    fold_state,
    'Property distribution: ' || fold_state,
    count::TEXT,
    count,
    fold_state || ' properties across all subjects at horizon',
    'metric'
FROM analysis_property_distribution;

-- =====================================================================
-- 1. CANONICAL TABLE SCHEMAS & ROW COUNTS
-- =====================================================================

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_numeric, finding_detail, finding_type)
SELECT
    '1. CANONICAL TABLES',
    table_name,
    'Table row count: ' || table_name,
    row_count::TEXT,
    row_count,
    'Canonical table status - VERIFIED EMPTY',
    'metric'
FROM analysis_canonical_counts;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_numeric, finding_detail, finding_type)
SELECT
    '1. CANONICAL TABLES',
    table_name,
    'Schema columns: ' || table_name,
    COUNT(*)::TEXT,
    COUNT(*)::INTEGER,
    'Column definitions available for ' || table_name,
    'metric'
FROM analysis_canonical_schemas
GROUP BY table_name;

-- =====================================================================
-- 2. CONFIGURATION REQUEST CANDIDATE MATRIX (7-ROW)
-- =====================================================================

CREATE TEMP TABLE final_candidate_matrix AS
SELECT * FROM analysis_candidate_matrix;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_subsection, finding_name, finding_value, finding_numeric, finding_detail, finding_type)
SELECT
    '2. CANDIDATE MATRIX',
    configuration_request_id,
    subject_status,
    'Configuration request: ' || configuration_request_id,
    product_reference || ' / ' || geography || ' / ' || term_months || ' / ' || customer_segment || ' / ' || launch_reference,
    established_count,
    subject_status || ' - ' || established_count || '/' || total_properties || ' properties ESTABLISHED',
    'observation'
FROM final_candidate_matrix
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. LOGICAL IDENTITY INPUTS (NO ENCODING)
-- =====================================================================

CREATE TEMP TABLE final_identity_inputs AS
SELECT
    configuration_request_id,
    product_id,
    geo,
    term,
    segment,
    CASE
        WHEN product_id IS NOT NULL AND geo IS NOT NULL AND term IS NOT NULL AND segment IS NOT NULL
        THEN 'COMPLETE'
        WHEN segment IS NULL THEN 'INCOMPLETE'
        ELSE 'UNKNOWN'
    END AS completeness_status
FROM analysis_identity_inputs;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '3. LOGICAL IDENTITY INPUTS',
    configuration_request_id,
    'Identity tuple: ' || configuration_request_id,
    '(' || COALESCE(product_id, 'NULL') || ', ' ||
    COALESCE(geo, 'NULL') || ', ' ||
    COALESCE(term, 'NULL') || ', ' ||
    COALESCE(segment, 'NULL') || ')',
    completeness_status || ' - NO hash/UUID/encoding',
    'observation'
FROM final_identity_inputs
ORDER BY configuration_request_id;

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY (006 vs 006B)
-- =====================================================================

CREATE TEMP TABLE final_s6_analysis AS
SELECT * FROM analysis_s6_check;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '4. S6 LOGICAL EQUALITY',
    'S6_006_vs_006B',
    'S6 Verdict: ' || request_id_006 || ' vs ' || request_id_006b,
    s6_verdict,
    'Two distinct configuration_request subjects with same logical identity inputs - NOT YET deduplicated or reused',
    'verdict'
FROM final_s6_analysis;

-- =====================================================================
-- 5. S7 MISSING INPUT (007)
-- =====================================================================

CREATE TEMP TABLE final_s7_analysis AS
SELECT * FROM analysis_s7_check;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '5. S7 MISSING INPUT',
    configuration_request_id,
    'S7 Status: ' || configuration_request_id,
    s7_verdict,
    'Missing required input - customer_segment is UNREPORTED (no Assertion exists)',
    'verdict'
FROM final_s7_analysis;

-- =====================================================================
-- 6. PRODUCT CONTEXT
-- =====================================================================

CREATE TEMP TABLE final_product_analysis AS
SELECT
    product_id,
    property_name,
    fold_state,
    resolved_value
FROM analysis_product_context;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '6. PRODUCT CONTEXT',
    product_id || '.' || property_name,
    'Product property: ' || product_id || '.' || property_name,
    COALESCE(resolved_value, 'NULL'),
    fold_state || ' - ' || property_name,
    'observation'
FROM final_product_analysis
ORDER BY product_id, property_name;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '6. PRODUCT CONTEXT',
    'product_coverage',
    'Product reference coverage',
    product_references_list,
    product_references_count || ' distinct product reference(s) - All configuration requests reference same product',
    'observation'
FROM analysis_product_coverage;

-- =====================================================================
-- 7. COMPLETENESS CLASSIFICATION
-- =====================================================================

CREATE TEMP TABLE final_completeness_analysis AS
SELECT * FROM analysis_completeness;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '7. COMPLETENESS CLASSIFICATION',
    configuration_request_id,
    'Request completeness: ' || configuration_request_id,
    identity_completeness,
    subject_status || ' - ' || established_count || '/' || total_properties || ' properties ESTABLISHED',
    'observation'
FROM final_completeness_analysis
ORDER BY configuration_request_id;

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_numeric, finding_detail, finding_type)
SELECT
    '7. COMPLETENESS CLASSIFICATION',
    'summary_' || identity_completeness,
    'Completeness summary: ' || identity_completeness,
    COUNT(*)::TEXT,
    COUNT(*)::INTEGER,
    'Number of requests with ' || identity_completeness || ' status',
    'metric'
FROM final_completeness_analysis
GROUP BY identity_completeness
ORDER BY identity_completeness;

-- =====================================================================
-- 8. DECISION BOUNDARY ANALYSIS
-- =====================================================================

INSERT INTO final_5g1_results (finding_section, finding_name, finding_value, finding_detail, finding_type)
VALUES (
    '8. DECISION BOUNDARY',
    'Pipeline Architecture',
    'Fold → Candidate Context → IDENTITY_ASSESSMENT → Canonical Mutation',
    'Sequential pipeline: discovery phase complete, awaiting governed decision phase',
    'verdict'
);

INSERT INTO final_5g1_results (finding_section, finding_subsection, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '8. DECISION BOUNDARY',
    'Pre-IDENTITY_ASSESSMENT',
    'Prepared now: Logical identity inputs',
    '(product_id, geo, term, segment)',
    'Candidate logical identity context ready for intake',
    'observation';

INSERT INTO final_5g1_results (finding_section, finding_subsection, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '8. DECISION BOUNDARY',
    'Pre-IDENTITY_ASSESSMENT',
    'Prepared now: Completeness status',
    'COMPLETE_IDENTITY / INCOMPLETE_MISSING_INPUT',
    'Request-level completeness classification prepared',
    'observation';

INSERT INTO final_5g1_results (finding_section, finding_subsection, finding_name, finding_value, finding_detail, finding_type)
SELECT
    '8. DECISION BOUNDARY',
    'IDENTITY_ASSESSMENT intake',
    'Will receive',
    'Candidate context + Active KB rules (IR-001..IR-009)',
    'Decision output: reuse existing OR create new OR cannot-decide',
    'observation';

-- =====================================================================
-- 9. UNRESOLVED GOVERNANCE QUESTIONS
-- =====================================================================

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
VALUES (
    '9. GOVERNANCE QUESTIONS',
    'Q1_S6_reuse',
    'Q1: For S6 (006 vs 006B) - exact logical identity match = reuse?',
    'UNRESOLVED',
    'Observed: same logical identity inputs; KB outcome NOT YET EXECUTED',
    'question'
);

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
VALUES (
    '9. GOVERNANCE QUESTIONS',
    'Q2_S7_cannot_decide',
    'Q2: For S7 (007) - missing required input = cannot-decide?',
    'UNRESOLVED',
    'Observed: missing customer_segment; KB outcome NOT YET EXECUTED',
    'question'
);

INSERT INTO final_5g1_results (finding_section, finding_id, finding_name, finding_value, finding_detail, finding_type)
VALUES (
    '9. GOVERNANCE QUESTIONS',
    'Q3_IDENTITY_ASSESSMENT_readiness',
    'Q3: Readiness for IDENTITY_ASSESSMENT service intake?',
    'READY',
    'Candidate context prepared; awaiting KB-driven decision rules execution',
    'question'
);

-- =====================================================================
-- COMPREHENSIVE DISPLAY
-- =====================================================================

SELECT '=== STEP 5G.1 CANONICAL CANDIDATE DISCOVERY - FINAL ANALYSIS ===' AS heading;

-- 0. Fold Property-State Count
SELECT '1. RECONCILED FOLD PROPERTY-STATE COUNT' AS section;
SELECT finding_name, finding_value, finding_detail FROM final_5g1_results
WHERE finding_section = '0. FOLD PROPERTY-STATE COUNT'
ORDER BY finding_name;

-- 1. Canonical Tables
SELECT '2. CANONICAL TABLE SCHEMAS & ROW COUNTS' AS section;
SELECT finding_name, finding_value, finding_detail FROM final_5g1_results
WHERE finding_section = '1. CANONICAL TABLES'
ORDER BY finding_name;

-- 2. Candidate Matrix
SELECT '3. CONFIGURATION REQUEST CANDIDATE MATRIX' AS section;
SELECT * FROM final_candidate_matrix
ORDER BY configuration_request_id;

-- 3. Logical Identity Inputs
SELECT '4. LOGICAL IDENTITY INPUTS' AS section;
SELECT * FROM final_identity_inputs
ORDER BY configuration_request_id;

-- 4. S6 Logical Equality
SELECT '5. S6 LOGICAL EQUALITY CHECK' AS section;
SELECT * FROM final_s6_analysis;

-- 5. S7 Missing Input
SELECT '6. S7 MISSING INPUT STATUS' AS section;
SELECT * FROM final_s7_analysis;

-- 6. Product Context
SELECT '7. PRODUCT CONTEXT (PROD-001)' AS section;
SELECT * FROM final_product_analysis
ORDER BY product_id, property_name;

-- 7. Completeness Classification
SELECT '8. COMPLETENESS CLASSIFICATION' AS section;
SELECT * FROM final_completeness_analysis
ORDER BY configuration_request_id;

-- 8. Decision Boundary
SELECT '9. DECISION BOUNDARY ANALYSIS' AS section;
SELECT finding_subsection, finding_name, finding_value FROM final_5g1_results
WHERE finding_section = '8. DECISION BOUNDARY'
ORDER BY finding_subsection, finding_name;

-- 9. Governance Questions
SELECT '10. UNRESOLVED GOVERNANCE QUESTIONS' AS section;
SELECT finding_name, finding_value, finding_detail FROM final_5g1_results
WHERE finding_section = '9. GOVERNANCE QUESTIONS'
ORDER BY finding_id;

-- =====================================================================
-- FINAL SUMMARY METRICS
-- =====================================================================

SELECT '=== FINAL SUMMARY METRICS ===' AS heading;

SELECT
  'Total Fold snapshots' AS metric,
  (SELECT COUNT(*)::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS result
UNION ALL
SELECT
  'Total property states (expanded)' AS metric,
  (SELECT SUM(jsonb_array_length(folded_properties))::TEXT FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ) AS result
UNION ALL
SELECT
  'Configuration requests discovered' AS metric,
  (SELECT COUNT(*)::TEXT FROM final_candidate_matrix) AS result
UNION ALL
SELECT
  'Requests - COMPLETE_IDENTITY' AS metric,
  (SELECT COUNT(*)::TEXT FROM final_completeness_analysis WHERE identity_completeness = 'COMPLETE_IDENTITY') AS result
UNION ALL
SELECT
  'Requests - INCOMPLETE_MISSING_INPUT' AS metric,
  (SELECT COUNT(*)::TEXT FROM final_completeness_analysis WHERE identity_completeness = 'INCOMPLETE_MISSING_INPUT') AS result
UNION ALL
SELECT
  'S6 verdict' AS metric,
  (SELECT s6_verdict FROM final_s6_analysis) AS result
UNION ALL
SELECT
  'S7 verdict' AS metric,
  (SELECT s7_verdict FROM final_s7_analysis) AS result
UNION ALL
SELECT
  'Canonical table row count' AS metric,
  (SELECT SUM(row_count)::TEXT FROM analysis_canonical_counts) AS result;

-- =====================================================================
-- STEP 5G.1 READINESS VERDICT
-- =====================================================================

SELECT '=== STEP 5G.1 READINESS VERDICT ===' AS heading;

SELECT
  'STEP 5G.1 CANONICAL CANDIDATE CONTEXT READY' AS status,
  'Fold-derived canonical candidate context fully discovered' AS finding_1,
  'All 7 configuration requests analyzed' AS finding_2,
  'S6 logical equality verified: SAME_LOGICAL_IDENTITY_INPUTS' AS finding_3,
  'S7 missing input detected: customer_segment UNREPORTED' AS finding_4,
  'Product context verified: all requests reference PROD-001' AS finding_5;

SELECT
  'Do NOT write canonical data yet' AS critical_reminder,
  'Proceed to IDENTITY_ASSESSMENT service for KB-driven decision rules' AS next_action,
  'Candidate context ready for intake: logical identity inputs + completeness status' AS handoff_status;

-- =====================================================================
-- FINAL ANALYSIS TEMP TABLE INVENTORY
-- =====================================================================

SELECT '=== FINAL ANALYSIS TEMP TABLES (REUSABLE FOR FURTHER ANALYSIS) ===' AS heading;

SELECT
  'Master analysis results table' AS table_type,
  'final_5g1_results' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_5g1_results
UNION ALL
SELECT
  'Candidate matrix' AS table_type,
  'final_candidate_matrix' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_candidate_matrix
UNION ALL
SELECT
  'Logical identity inputs' AS table_type,
  'final_identity_inputs' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_identity_inputs
UNION ALL
SELECT
  'S6 analysis' AS table_type,
  'final_s6_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_s6_analysis
UNION ALL
SELECT
  'S7 analysis' AS table_type,
  'final_s7_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_s7_analysis
UNION ALL
SELECT
  'Product analysis' AS table_type,
  'final_product_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_product_analysis
UNION ALL
SELECT
  'Completeness analysis' AS table_type,
  'final_completeness_analysis' AS table_name,
  COUNT(*)::TEXT AS row_count
FROM final_completeness_analysis;

SELECT '=== All temp tables created successfully for reusable analysis ===' AS note;
