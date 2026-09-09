-- =====================================================================
-- STEP 5G.1: CANONICAL CANDIDATE / IDENTITY CONTEXT DISCOVERY
-- READ-ONLY INSPECTION ONLY
-- =====================================================================

-- =====================================================================
-- 0. RECONCILE FOLD PROPERTY-STATE COUNT
-- =====================================================================
-- Count actual persisted property states in fold_state_snapshot at horizon
SELECT
  '0. PERSISTED PROPERTY-STATE COUNT' AS section,
  COUNT(*) AS total_persisted_properties,
  COUNT(DISTINCT subject_type) AS subject_types,
  COUNT(DISTINCT subject_id) AS distinct_subjects
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- Expand: count properties per subject (from JSONB folded_properties)
SELECT
  '0. PROPERTY STATES PER SUBJECT' AS section,
  subject_type,
  subject_id,
  jsonb_array_length(folded_properties) AS property_count,
  fold_status
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
ORDER BY subject_type, subject_id;

-- Total property states (expanded from JSONB)
SELECT
  '0. TOTAL PROPERTY STATES (EXPANDED)' AS section,
  SUM(jsonb_array_length(folded_properties)) AS total_persisted_property_states,
  COUNT(*) AS snapshots
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- Property state distribution
SELECT
  '0. PROPERTY STATE DISTRIBUTION' AS section,
  props->>'fold_state' AS fold_state,
  COUNT(*) AS count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
GROUP BY props->>'fold_state'
ORDER BY fold_state;

-- =====================================================================
-- 1. INSPECT CANONICAL TABLES — READ ONLY
-- =====================================================================
SELECT
  '1. CANONICAL SCHEMAS - claris.product' AS section,
  'Column definitions' AS type
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'product'
ORDER BY ordinal_position;

SELECT
  '1. CANONICAL SCHEMAS - claris.configuration' AS section,
  'Column definitions' AS type
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration'
ORDER BY ordinal_position;

SELECT
  '1. CANONICAL SCHEMAS - claris.configuration_version' AS section,
  'Column definitions' AS type
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration_version'
ORDER BY ordinal_position;

-- Row counts
SELECT
  '1. CANONICAL TABLE ROW COUNTS' AS section,
  'claris.product' AS table_name,
  COUNT(*) AS row_count
FROM claris.product
UNION ALL
SELECT
  '1. CANONICAL TABLE ROW COUNTS' AS section,
  'claris.configuration' AS table_name,
  COUNT(*) AS row_count
FROM claris.configuration
UNION ALL
SELECT
  '1. CANONICAL TABLE ROW COUNTS' AS section,
  'claris.configuration_version' AS table_name,
  COUNT(*) AS row_count
FROM claris.configuration_version;

-- =====================================================================
-- 2. BUILD CANONICAL CANDIDATE INPUT FROM FOLD
-- =====================================================================
SELECT
  '2. CONFIGURATION REQUEST CANDIDATE MATRIX' AS section,
  fss.subject_id AS configuration_request_id,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state,
  props->>'resolved_value' AS resolved_value
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
  AND fss.subject_type = 'configuration_request'
ORDER BY fss.subject_id, props->>'property_name';

-- Pivoted candidate matrix for easier reading
WITH cr_properties AS (
  SELECT
    fss.subject_id AS configuration_request_id,
    props->>'property_name' AS property_name,
    props->>'fold_state' AS fold_state,
    props->>'resolved_value' AS resolved_value
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
)
SELECT
  '2. CANDIDATE MATRIX (PIVOTED)' AS section,
  configuration_request_id,
  MAX(CASE WHEN property_name = 'product_reference' THEN resolved_value END) AS product_reference,
  MAX(CASE WHEN property_name = 'geography' THEN resolved_value END) AS geography,
  MAX(CASE WHEN property_name = 'term_months' THEN resolved_value END) AS term_months,
  MAX(CASE WHEN property_name = 'customer_segment' THEN resolved_value END) AS customer_segment,
  MAX(CASE WHEN property_name = 'launch_reference' THEN resolved_value END) AS launch_reference,
  MAX(CASE WHEN property_name = 'product_reference' THEN fold_state END) AS product_reference_state,
  MAX(CASE WHEN property_name = 'geography' THEN fold_state END) AS geography_state,
  MAX(CASE WHEN property_name = 'term_months' THEN fold_state END) AS term_months_state,
  MAX(CASE WHEN property_name = 'customer_segment' THEN fold_state END) AS customer_segment_state,
  MAX(CASE WHEN property_name = 'launch_reference' THEN fold_state END) AS launch_reference_state
FROM cr_properties
GROUP BY configuration_request_id
ORDER BY configuration_request_id;

-- Completeness/State for each request
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
  '2. CANDIDATE COMPLETENESS' AS section,
  configuration_request_id,
  subject_status,
  CASE
    WHEN COUNT(*) = 5 AND COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED') = 5 THEN 'COMPLETE_IDENTITY'
    WHEN COUNT(*) = 5 AND COUNT(*) FILTER (WHERE fold_state IN ('ESTABLISHED', 'UNREPORTED')) = 5
      AND COUNT(*) FILTER (WHERE fold_state = 'UNREPORTED') > 0 THEN 'INCOMPLETE_MISSING_INPUT'
    ELSE 'DEGRADED'
  END AS identity_completeness,
  COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED') || '/' || COUNT(*) AS established_count
FROM cr_properties
GROUP BY configuration_request_id, subject_status
ORDER BY configuration_request_id;

-- =====================================================================
-- 3. IDENTITY CONTEXT — LOGICAL EQUALITY TUPLES (NO ENCODING)
-- =====================================================================
SELECT
  '3. LOGICAL IDENTITY INPUTS (NO HASH/UUID)' AS section,
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

-- =====================================================================
-- 4. S6 LOGICAL EQUALITY — 006 vs 006B
-- =====================================================================
WITH s6_006 AS (
  SELECT
    MAX(CASE WHEN property_name = 'product_reference' THEN resolved_value END) AS product_id,
    MAX(CASE WHEN property_name = 'geography' THEN resolved_value END) AS geo,
    MAX(CASE WHEN property_name = 'term_months' THEN resolved_value END) AS term,
    MAX(CASE WHEN property_name = 'customer_segment' THEN resolved_value END) AS segment
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
    AND fss.subject_id = 'CONFIG-REQ-2026-006'
),
s6_006b AS (
  SELECT
    MAX(CASE WHEN property_name = 'product_reference' THEN resolved_value END) AS product_id,
    MAX(CASE WHEN property_name = 'geography' THEN resolved_value END) AS geo,
    MAX(CASE WHEN property_name = 'term_months' THEN resolved_value END) AS term,
    MAX(CASE WHEN property_name = 'customer_segment' THEN resolved_value END) AS segment
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
    AND fss.subject_id = 'CONFIG-REQ-2026-006B'
)
SELECT
  '4. S6 LOGICAL EQUALITY CHECK' AS section,
  'CONFIG-REQ-2026-006' AS request_006_id,
  (SELECT row_to_json(s6_006) FROM s6_006)::TEXT AS identity_006,
  'CONFIG-REQ-2026-006B' AS request_006b_id,
  (SELECT row_to_json(s6_006b) FROM s6_006b)::TEXT AS identity_006b,
  CASE
    WHEN (SELECT s6_006.*::TEXT FROM s6_006) = (SELECT s6_006b.*::TEXT FROM s6_006b)
    THEN 'SAME_LOGICAL_IDENTITY_INPUTS'
    ELSE 'DIFFERENT_LOGICAL_IDENTITY'
  END AS s6_equality_verdict;

-- =====================================================================
-- 5. S7 — MISSING INPUT
-- =====================================================================
SELECT
  '5. S7 IDENTITY INPUT STATUS' AS section,
  fss.subject_id AS configuration_request_id,
  fss.fold_status AS subject_status,
  CASE
    WHEN EXISTS (
      SELECT 1 FROM jsonb_array_elements(fss.folded_properties) props
      WHERE props->>'property_name' = 'customer_segment'
        AND props->>'fold_state' = 'UNREPORTED'
    ) THEN 'IDENTITY_INPUT_INCOMPLETE: customer_segment UNREPORTED'
    ELSE 'COMPLETE'
  END AS s7_missing_input_verdict
FROM state.fold_state_snapshot fss
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
  AND fss.subject_type = 'configuration_request'
  AND fss.subject_id = 'CONFIG-REQ-2026-007';

-- =====================================================================
-- 6. PRODUCT CONTEXT
-- =====================================================================
SELECT
  '6. PRODUCT CONTEXT' AS section,
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

-- Product reference coverage
SELECT
  '6. PRODUCT REFERENCE COVERAGE' AS section,
  'All configuration requests reference PROD-001?' AS check_type,
  COUNT(DISTINCT
    MAX(CASE WHEN property_name = 'product_reference' THEN resolved_value END)
  ) AS product_references_count,
  string_agg(
    DISTINCT MAX(CASE WHEN property_name = 'product_reference' THEN resolved_value END),
    ', '
  ) AS product_references_list
FROM (
  SELECT
    fss.subject_id AS configuration_request_id,
    props->>'property_name' AS property_name,
    props->>'fold_state' AS fold_state,
    props->>'resolved_value' AS resolved_value
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
    AND fss.subject_type = 'configuration_request'
);

-- =====================================================================
-- 7. SUMMARY TABLE
-- =====================================================================
SELECT
  '=== STEP 5G.1 DISCOVERY COMPLETE ===' AS status,
  'Read-only inspection of Fold-derived canonical candidate context' AS type,
  'Ready for IDENTITY_ASSESSMENT service intake' AS next_step;
