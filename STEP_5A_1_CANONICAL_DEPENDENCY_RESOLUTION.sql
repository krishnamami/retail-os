-- =====================================================================
-- STEP 5A.1 — CANONICAL IDENTITY DEPENDENCY RESOLUTION
-- Read-only preflight to validate KB + Fold capability
-- =====================================================================

-- =====================================================================
-- SECTION 1: KB IDENTITY RULES (IR-001..IR-009)
-- =====================================================================

SELECT
  'KB_IDENTITY_RULES' AS section,
  rule_id,
  rule_name,
  rule_type,
  jsonb_pretty(rule_definition) AS rule_definition,
  created_at,
  updated_at
FROM knowledge_base.rules
WHERE (rule_type LIKE '%IDENTITY%'
   OR rule_name LIKE '%IR-%'
   OR rule_id LIKE 'IR-%')
ORDER BY rule_id;

-- =====================================================================
-- SECTION 2: KB VERSIONING AND BOOTSTRAP AUTHORITY
-- =====================================================================

SELECT
  'KB_BOOTSTRAP_AUTHORITY' AS section,
  policy_id,
  policy_name,
  policy_type,
  jsonb_pretty(policy_definition) AS policy_definition
FROM knowledge_base.policies
WHERE policy_type LIKE '%BOOTSTRAP%'
   OR policy_name LIKE '%BOOTSTRAP%'
   OR policy_name LIKE '%VERSION%'
ORDER BY policy_id;

-- =====================================================================
-- SECTION 3: KB TEMPORAL SEMANTICS (valid_from, valid_to governance)
-- =====================================================================

SELECT
  'KB_TEMPORAL_GOVERNANCE' AS section,
  policy_id,
  policy_name,
  jsonb_pretty(policy_definition) AS policy_definition
FROM knowledge_base.policies
WHERE policy_type LIKE '%TEMPORAL%'
   OR policy_name LIKE '%valid_from%'
   OR policy_name LIKE '%decision_horizon%'
ORDER BY policy_id;

-- =====================================================================
-- SECTION 4: FOLD PROPERTY INVENTORY (All 177 properties)
-- =====================================================================

SELECT
  'FOLD_PROPERTY_INVENTORY' AS section,
  subject_type,
  props->>'property_name' AS property_name,
  COUNT(*) AS total_instances,
  COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED') AS established_count,
  COUNT(*) FILTER (WHERE props->>'fold_state' = 'UNREPORTED') AS unreported_count,
  COUNT(*) FILTER (WHERE props->>'fold_state' = 'EXPLICITLY_UNDEFINED') AS explicitly_undefined_count,
  COUNT(*) FILTER (WHERE props->>'fold_state' = 'CONTRADICTED') AS contradicted_count,
  CASE
    WHEN COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED') = COUNT(*) THEN 'FULLY_ESTABLISHED'
    WHEN COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED') > 0 THEN 'PARTIALLY_ESTABLISHED'
    WHEN COUNT(*) FILTER (WHERE props->>'fold_state' = 'UNREPORTED') > 0 THEN 'UNREPORTED'
    ELSE 'OTHER'
  END AS availability_status
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY subject_type, props->>'property_name'
ORDER BY subject_type, props->>'property_name';

-- =====================================================================
-- SECTION 5: CONFIGURATION-SPECIFIC PROPERTY STATUS
-- =====================================================================

SELECT
  'CONFIGURATION_PROPERTY_STATUS' AS section,
  fss.subject_id,
  fss.fold_status,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state,
  props->>'resolved_value' AS resolved_value,
  props->>'property_value_type' AS property_value_type
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND fss.subject_type = 'configuration'
ORDER BY fss.subject_id, props->>'property_name';

-- =====================================================================
-- SECTION 6: PRODUCT-RELATED PROPERTIES (Search across all subjects)
-- =====================================================================

SELECT
  'PRODUCT_RELATED_PROPERTIES' AS section,
  subject_type,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state,
  COUNT(*) AS count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND (props->>'property_name' ILIKE '%product%'
    OR props->>'property_name' ILIKE '%sku%'
    OR props->>'property_name' ILIKE '%family%'
    OR props->>'property_name' ILIKE '%type%'
    OR props->>'property_name' ILIKE '%category%')
GROUP BY subject_type, props->>'property_name', props->>'fold_state'
ORDER BY subject_type, props->>'property_name';

-- =====================================================================
-- SECTION 7: CONFIGURATION IDENTITY CANDIDATE PROPERTIES
-- =====================================================================

SELECT
  'CONFIGURATION_IDENTITY_CANDIDATES' AS section,
  subject_type,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state,
  COUNT(*) AS count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND (props->>'property_name' ILIKE '%identity%'
    OR props->>'property_name' ILIKE '%code%'
    OR props->>'property_name' ILIKE '%key%'
    OR props->>'property_name' ILIKE '%name%'
    OR props->>'property_name' ILIKE '%channel%'
    OR props->>'property_name' ILIKE '%market%'
    OR props->>'property_name' ILIKE '%segment%'
    OR props->>'property_name' ILIKE '%tier%'
    OR props->>'property_name' ILIKE '%term%')
GROUP BY subject_type, props->>'property_name', props->>'fold_state'
ORDER BY subject_type, props->>'property_name';

-- =====================================================================
-- SECTION 8: UNREPORTED CONFIGURATION PROPERTIES
-- =====================================================================

SELECT
  'UNREPORTED_CONFIGURATION_PROPERTIES' AS section,
  fss.subject_id,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND fss.subject_type = 'configuration'
  AND props->>'fold_state' = 'UNREPORTED'
ORDER BY fss.subject_id, props->>'property_name';

-- =====================================================================
-- SECTION 9: CONTRADICTED CONFIGURATION PROPERTIES
-- =====================================================================

SELECT
  'CONTRADICTED_CONFIGURATION_PROPERTIES' AS section,
  fss.subject_id,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND fss.subject_type = 'configuration'
  AND props->>'fold_state' = 'CONTRADICTED'
ORDER BY fss.subject_id, props->>'property_name';

-- =====================================================================
-- SECTION 10: SUBJECT TYPE RELATIONSHIPS (SKU vs Product vs Config vs Launch)
-- =====================================================================

SELECT
  'SUBJECT_TYPE_RELATIONSHIPS' AS section,
  fss.subject_type,
  fss.subject_id,
  fss.fold_status,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'ESTABLISHED' THEN props->>'property_name' END) AS established_property_count,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'UNREPORTED' THEN props->>'property_name' END) AS unreported_property_count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY fss.subject_type, fss.subject_id, fss.fold_status
ORDER BY fss.subject_type, fss.subject_id;

-- =====================================================================
-- SECTION 11: KB REFERENCE DATA (Properties, Mappings)
-- =====================================================================

SELECT
  'KB_PROPERTY_SEMANTICS' AS section,
  property_name,
  subject_type,
  property_semantics,
  identity_relevance,
  version_relevance,
  jsonb_pretty(property_definition) AS definition
FROM knowledge_base.properties
WHERE subject_type IN ('product', 'configuration', 'configuration_version', 'sku', 'launch', 'material')
ORDER BY subject_type, property_name;

-- =====================================================================
-- SECTION 12: SUMMARY VALIDATION (Are required KB properties in Fold?)
-- =====================================================================

SELECT
  'SUMMARY_KB_VS_FOLD_COVERAGE' AS section,
  kbp.subject_type,
  kbp.property_name,
  kbp.identity_relevance,
  kbp.version_relevance,
  CASE
    WHEN fss.property_count IS NOT NULL THEN 'FOUND_IN_FOLD'
    ELSE 'NOT_FOUND_IN_FOLD'
  END AS coverage,
  COALESCE(fss.established_count, 0) AS established_in_fold,
  COALESCE(fss.unreported_count, 0) AS unreported_in_fold
FROM knowledge_base.properties kbp
LEFT JOIN (
  SELECT
    subject_type,
    props->>'property_name' AS property_name,
    COUNT(*) AS property_count,
    COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED') AS established_count,
    COUNT(*) FILTER (WHERE props->>'fold_state' = 'UNREPORTED') AS unreported_count
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  GROUP BY subject_type, props->>'property_name'
) fss
ON kbp.subject_type = fss.subject_type AND kbp.property_name = fss.property_name
WHERE kbp.subject_type IN ('product', 'configuration', 'configuration_version', 'sku', 'launch')
  AND (kbp.identity_relevance = TRUE OR kbp.version_relevance = TRUE)
ORDER BY kbp.subject_type, kbp.property_name;
