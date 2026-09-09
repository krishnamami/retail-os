-- =====================================================================
-- STEP 5G.1: CANONICAL CANDIDATE / IDENTITY CONTEXT DISCOVERY
-- COMPREHENSIVE TEMP TABLE VERSION
-- All discovery results written to temp tables for complete analysis
-- =====================================================================

-- Create master results table
CREATE TEMP TABLE discovery_results (
    section TEXT,
    discovery_type TEXT,
    key_name TEXT,
    key_value TEXT,
    numeric_value INTEGER,
    detail TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 0. RECONCILE FOLD PROPERTY-STATE COUNT
-- =====================================================================

-- 0A: Total persisted property-state count
INSERT INTO discovery_results (section, discovery_type, key_name, numeric_value, detail)
SELECT
    '0. FOLD PROPERTY-STATE RECONCILIATION' AS section,
    'persisted_count' AS discovery_type,
    'total_persisted_properties' AS key_name,
    COUNT(*)::INTEGER AS numeric_value,
    'Snapshots at horizon 2026-06-20 10:45:00+00' AS detail
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- 0B: Subject types
INSERT INTO discovery_results (section, discovery_type, key_name, numeric_value, detail)
SELECT
    '0. FOLD PROPERTY-STATE RECONCILIATION' AS section,
    'subject_types' AS discovery_type,
    'distinct_subject_types' AS key_name,
    COUNT(DISTINCT subject_type)::INTEGER AS numeric_value,
    'Domain coverage at horizon' AS detail
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- 0C: Distinct subjects
INSERT INTO discovery_results (section, discovery_type, key_name, numeric_value, detail)
SELECT
    '0. FOLD PROPERTY-STATE RECONCILIATION' AS section,
    'subject_count' AS discovery_type,
    'distinct_subjects' AS key_name,
    COUNT(DISTINCT subject_id)::INTEGER AS numeric_value,
    'Total subjects at horizon' AS detail
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- 0D: Total expanded property states
INSERT INTO discovery_results (section, discovery_type, key_name, numeric_value, detail)
SELECT
    '0. FOLD PROPERTY-STATE RECONCILIATION' AS section,
    'expanded_property_states' AS discovery_type,
    'total_property_states' AS key_name,
    SUM(jsonb_array_length(folded_properties))::INTEGER AS numeric_value,
    'Properties expanded from JSONB folded_properties' AS detail
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- 0E: Property state distribution table
CREATE TEMP TABLE temp_property_state_distribution AS
SELECT
    props->>'fold_state' AS fold_state,
    COUNT(*)::INTEGER AS count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
GROUP BY props->>'fold_state'
ORDER BY fold_state;

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, numeric_value, detail)
SELECT
    '0. FOLD PROPERTY-STATE RECONCILIATION' AS section,
    'property_state_distribution' AS discovery_type,
    'fold_state' AS key_name,
    fold_state AS key_value,
    count AS numeric_value,
    'Property distribution across all subjects' AS detail
FROM temp_property_state_distribution;

-- =====================================================================
-- 1. INSPECT CANONICAL TABLES — READ ONLY
-- =====================================================================

-- 1A: Canonical table schemas
CREATE TEMP TABLE temp_canonical_schemas AS
SELECT
    'claris.product' AS table_name,
    column_name,
    ordinal_position,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'product'
UNION ALL
SELECT
    'claris.configuration' AS table_name,
    column_name,
    ordinal_position,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration'
UNION ALL
SELECT
    'claris.configuration_version' AS table_name,
    column_name,
    ordinal_position,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration_version'
ORDER BY table_name, ordinal_position;

-- 1B: Canonical table row counts
CREATE TEMP TABLE temp_canonical_row_counts AS
SELECT 'claris.product' AS table_name, COUNT(*)::INTEGER AS row_count FROM claris.product
UNION ALL
SELECT 'claris.configuration' AS table_name, COUNT(*)::INTEGER AS row_count FROM claris.configuration
UNION ALL
SELECT 'claris.configuration_version' AS table_name, COUNT(*)::INTEGER AS row_count FROM claris.configuration_version;

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, numeric_value, detail)
SELECT
    '1. CANONICAL TABLES' AS section,
    'table_row_count' AS discovery_type,
    'table_name' AS key_name,
    table_name AS key_value,
    row_count AS numeric_value,
    'Canonical table row count (should be 0)' AS detail
FROM temp_canonical_row_counts;

-- =====================================================================
-- 2. BUILD CANONICAL CANDIDATE INPUT FROM FOLD
-- =====================================================================

-- 2A: Configuration request candidate matrix
CREATE TEMP TABLE temp_cr_candidate_matrix AS
WITH cr_properties AS (
  SELECT
    fss.subject_id AS configuration_request_id,
    fss.fold_status AS subject_status,
    props->>'property_name' AS property_name,
    props->>'fold_state' AS fold_state,
    props->>'resolved_value' AS resolved_value
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
)
SELECT
  configuration_request_id,
  subject_status,
  MAX(CASE WHEN property_name = 'product_reference' THEN resolved_value END) AS product_reference,
  MAX(CASE WHEN property_name = 'geography' THEN resolved_value END) AS geography,
  MAX(CASE WHEN property_name = 'term_months' THEN resolved_value END) AS term_months,
  MAX(CASE WHEN property_name = 'customer_segment' THEN resolved_value END) AS customer_segment,
  MAX(CASE WHEN property_name = 'launch_reference' THEN resolved_value END) AS launch_reference,
  MAX(CASE WHEN property_name = 'product_reference' THEN fold_state END) AS product_reference_state,
  MAX(CASE WHEN property_name = 'geography' THEN fold_state END) AS geography_state,
  MAX(CASE WHEN property_name = 'term_months' THEN fold_state END) AS term_months_state,
  MAX(CASE WHEN property_name = 'customer_segment' THEN fold_state END) AS customer_segment_state,
  MAX(CASE WHEN property_name = 'launch_reference' THEN fold_state END) AS launch_reference_state,
  COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED')::INTEGER AS established_count,
  COUNT(*)::INTEGER AS total_properties
FROM cr_properties
GROUP BY configuration_request_id, subject_status
ORDER BY configuration_request_id;

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, numeric_value, detail)
SELECT
    '2. CANDIDATE MATRIX' AS section,
    'configuration_request' AS discovery_type,
    configuration_request_id AS key_name,
    COALESCE(product_reference, 'NULL') || ' / ' ||
    COALESCE(geography, 'NULL') || ' / ' ||
    COALESCE(term_months, 'NULL') || ' / ' ||
    COALESCE(customer_segment, 'NULL') AS key_value,
    established_count AS numeric_value,
    subject_status || ' - ' || established_count || '/' || total_properties || ' properties ESTABLISHED' AS detail
FROM temp_cr_candidate_matrix
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. IDENTITY CONTEXT — LOGICAL EQUALITY TUPLES (NO ENCODING)
-- =====================================================================

-- 3A: Logical identity inputs
CREATE TEMP TABLE temp_logical_identity_inputs AS
SELECT
  configuration_request_id,
  MAX(CASE WHEN property_name = 'product_reference' THEN resolved_value END) AS product_id,
  MAX(CASE WHEN property_name = 'geography' THEN resolved_value END) AS geo,
  MAX(CASE WHEN property_name = 'term_months' THEN resolved_value END) AS term,
  MAX(CASE WHEN property_name = 'customer_segment' THEN resolved_value END) AS segment
FROM (
  SELECT
    fss.subject_id AS configuration_request_id,
    props->>'property_name' AS property_name,
    props->>'resolved_value' AS resolved_value
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
)
GROUP BY configuration_request_id
ORDER BY configuration_request_id;

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, detail)
SELECT
    '3. LOGICAL IDENTITY INPUTS' AS section,
    'identity_tuple' AS discovery_type,
    configuration_request_id AS key_name,
    '(' || COALESCE(product_id, 'NULL') || ', ' ||
    COALESCE(geo, 'NULL') || ', ' ||
    COALESCE(term, 'NULL') || ', ' ||
    COALESCE(segment, 'NULL') || ')' AS key_value,
    'Logical identity tuple (NO hash/UUID/encoding)' AS detail
FROM temp_logical_identity_inputs
ORDER BY configuration_request_id;

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY — 006 vs 006B
-- =====================================================================

-- 4A: S6 comparison
CREATE TEMP TABLE temp_s6_comparison AS
WITH s6_006 AS (
  SELECT * FROM temp_logical_identity_inputs WHERE configuration_request_id = 'CONFIG-REQ-2026-006'
),
s6_006b AS (
  SELECT * FROM temp_logical_identity_inputs WHERE configuration_request_id = 'CONFIG-REQ-2026-006B'
)
SELECT
  'CONFIG-REQ-2026-006' AS request_id_006,
  (SELECT row_to_json(s6_006) FROM s6_006)::TEXT AS identity_006,
  'CONFIG-REQ-2026-006B' AS request_id_006b,
  (SELECT row_to_json(s6_006b) FROM s6_006b)::TEXT AS identity_006b,
  CASE
    WHEN (SELECT (product_id, geo, term, segment)::TEXT FROM s6_006) =
         (SELECT (product_id, geo, term, segment)::TEXT FROM s6_006b)
    THEN 'SAME_LOGICAL_IDENTITY_INPUTS'
    ELSE 'DIFFERENT_LOGICAL_IDENTITY'
  END AS s6_verdict;

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, detail)
SELECT
    '4. S6 LOGICAL EQUALITY' AS section,
    'equality_check' AS discovery_type,
    'CONFIG-REQ-2026-006 vs 006B' AS key_name,
    s6_verdict AS key_value,
    'S6 Semantics: Two distinct requests, same logical identity' AS detail
FROM temp_s6_comparison;

-- =====================================================================
-- 5. S7 — MISSING INPUT
-- =====================================================================

-- 5A: S7 missing input status
CREATE TEMP TABLE temp_s7_status AS
SELECT
  fss.subject_id AS configuration_request_id,
  fss.fold_status AS subject_status,
  CASE
    WHEN EXISTS (
      SELECT 1 FROM jsonb_array_elements(fss.folded_properties) props
      WHERE props->>'property_name' = 'customer_segment'
        AND props->>'fold_state' = 'UNREPORTED'
    ) THEN 'IDENTITY_INPUT_INCOMPLETE: customer_segment UNREPORTED'
    ELSE 'COMPLETE'
  END AS s7_verdict,
  (SELECT json_object_agg(
    props->>'property_name',
    props->>'fold_state'
  ) FROM jsonb_array_elements(fss.folded_properties) props)::TEXT AS property_states
FROM state.fold_state_snapshot fss
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
  AND fss.subject_type = 'configuration_request'
  AND fss.subject_id = 'CONFIG-REQ-2026-007';

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, detail)
SELECT
    '5. S7 MISSING INPUT' AS section,
    'incomplete_identity' AS discovery_type,
    'CONFIG-REQ-2026-007' AS key_name,
    s7_verdict AS key_value,
    subject_status || ' - missing required input for identity' AS detail
FROM temp_s7_status;

-- =====================================================================
-- 6. PRODUCT CONTEXT
-- =====================================================================

-- 6A: Product Fold state
CREATE TEMP TABLE temp_product_context AS
SELECT
  fss.subject_id AS product_id,
  fss.fold_status AS subject_status,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state,
  props->>'resolved_value' AS resolved_value
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
  AND fss.subject_type = 'product'
ORDER BY fss.subject_id, props->>'property_name';

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, detail)
SELECT
    '6. PRODUCT CONTEXT' AS section,
    'product_property' AS discovery_type,
    product_id AS key_name,
    property_name || ': ' || COALESCE(resolved_value, 'NULL') AS key_value,
    'Product property at horizon - ' || fold_state AS detail
FROM temp_product_context
ORDER BY product_id, property_name;

-- 6B: Product reference coverage
CREATE TEMP TABLE temp_product_coverage AS
WITH product_refs AS (
  SELECT DISTINCT
    props->>'resolved_value' AS product_reference
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
    AND props->>'property_name' = 'product_reference'
)
SELECT
  COUNT(*)::INTEGER AS product_references_count,
  string_agg(product_reference, ', ') AS product_references_list
FROM product_refs;

INSERT INTO discovery_results (section, discovery_type, key_name, numeric_value, detail)
SELECT
    '6. PRODUCT CONTEXT' AS section,
    'product_coverage' AS discovery_type,
    'all_requests_reference' AS key_name,
    product_references_count AS numeric_value,
    'All configuration requests reference: ' || product_references_list AS detail
FROM temp_product_coverage;

-- =====================================================================
-- 7. COMPLETENESS CLASSIFICATION
-- =====================================================================

-- 7A: Classify each request by identity completeness
CREATE TEMP TABLE temp_completeness_classification AS
WITH cr_properties AS (
  SELECT
    fss.subject_id AS configuration_request_id,
    fss.fold_status AS subject_status,
    props->>'property_name' AS property_name,
    props->>'fold_state' AS fold_state
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
)
SELECT
  configuration_request_id,
  subject_status,
  CASE
    WHEN COUNT(*) = 5 AND COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED') = 5
      THEN 'COMPLETE_IDENTITY'
    WHEN COUNT(*) = 5 AND COUNT(*) FILTER (WHERE fold_state IN ('ESTABLISHED', 'UNREPORTED')) = 5
      AND COUNT(*) FILTER (WHERE fold_state = 'UNREPORTED') > 0
      THEN 'INCOMPLETE_MISSING_INPUT'
    ELSE 'DEGRADED'
  END AS identity_completeness,
  COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED')::INTEGER AS established_count,
  COUNT(*)::INTEGER AS total_properties
FROM cr_properties
GROUP BY configuration_request_id, subject_status
ORDER BY configuration_request_id;

INSERT INTO discovery_results (section, discovery_type, key_name, key_value, numeric_value, detail)
SELECT
    '7. COMPLETENESS CLASSIFICATION' AS section,
    'request_status' AS discovery_type,
    configuration_request_id AS key_name,
    identity_completeness AS key_value,
    established_count AS numeric_value,
    subject_status || ' - ' || established_count || '/' || total_properties || ' ESTABLISHED' AS detail
FROM temp_completeness_classification
ORDER BY configuration_request_id;

-- =====================================================================
-- COMPREHENSIVE SUMMARY QUERIES
-- =====================================================================

SELECT '=== STEP 5G.1 DISCOVERY RESULTS ===' AS heading;

-- Summary 1: Fold Reconciliation
SELECT
  '--- 0. FOLD PROPERTY-STATE RECONCILIATION ---' AS section;

SELECT * FROM discovery_results
WHERE section = '0. FOLD PROPERTY-STATE RECONCILIATION'
ORDER BY discovery_type, key_name;

-- Summary 2: Canonical Tables
SELECT
  '--- 1. CANONICAL TABLES (SHOULD BE EMPTY) ---' AS section;

SELECT * FROM discovery_results
WHERE section = '1. CANONICAL TABLES'
ORDER BY key_value;

-- Summary 3: Candidate Matrix
SELECT
  '--- 2. CONFIGURATION REQUEST CANDIDATE MATRIX ---' AS section;

SELECT * FROM temp_cr_candidate_matrix
ORDER BY configuration_request_id;

-- Summary 4: Logical Identity Inputs
SELECT
  '--- 3. LOGICAL IDENTITY INPUTS (product_id, geo, term, segment) ---' AS section;

SELECT * FROM temp_logical_identity_inputs
ORDER BY configuration_request_id;

-- Summary 5: S6 Logical Equality
SELECT
  '--- 4. S6 LOGICAL EQUALITY (006 vs 006B) ---' AS section;

SELECT * FROM temp_s6_comparison;

-- Summary 6: S7 Missing Input
SELECT
  '--- 5. S7 MISSING INPUT (007) ---' AS section;

SELECT * FROM temp_s7_status;

-- Summary 7: Product Context
SELECT
  '--- 6. PRODUCT CONTEXT ---' AS section;

SELECT * FROM temp_product_context
ORDER BY product_id, property_name;

SELECT '--- 6B. PRODUCT REFERENCE COVERAGE ---' AS subsection;
SELECT * FROM temp_product_coverage;

-- Summary 8: Completeness Classification
SELECT
  '--- 7. COMPLETENESS CLASSIFICATION ---' AS section;

SELECT * FROM temp_completeness_classification
ORDER BY configuration_request_id;

-- Final Summary
SELECT
  '=== STEP 5G.1 DISCOVERY SUMMARY ===' AS heading;

SELECT
  (SELECT COUNT(*)::TEXT FROM temp_cr_candidate_matrix) || ' configuration requests discovered' AS discovery_1,
  (SELECT SUM(numeric_value) FROM discovery_results WHERE section = '0. FOLD PROPERTY-STATE RECONCILIATION' AND key_name = 'total_property_states')::TEXT || ' total property states persisted' AS discovery_2,
  (SELECT COUNT(*)::TEXT FROM temp_completeness_classification WHERE identity_completeness = 'COMPLETE_IDENTITY') || ' complete identity requests' AS discovery_3,
  (SELECT COUNT(*)::TEXT FROM temp_completeness_classification WHERE identity_completeness = 'INCOMPLETE_MISSING_INPUT') || ' incomplete identity requests' AS discovery_4;

SELECT
  'All canonical tables remain empty' AS canonical_status,
  'Ready for IDENTITY_ASSESSMENT service intake' AS next_step,
  'Do NOT write canonical data yet' AS critical_reminder;

-- Cleanup verification
SELECT
  'Temporary tables created for analysis:' AS note,
  'temp_property_state_distribution' AS table_1,
  'temp_canonical_schemas' AS table_2,
  'temp_canonical_row_counts' AS table_3,
  'temp_cr_candidate_matrix' AS table_4,
  'temp_logical_identity_inputs' AS table_5,
  'temp_s6_comparison' AS table_6,
  'temp_s7_status' AS table_7,
  'temp_product_context' AS table_8,
  'temp_product_coverage' AS table_9,
  'temp_completeness_classification' AS table_10,
  'discovery_results' AS master_table;
