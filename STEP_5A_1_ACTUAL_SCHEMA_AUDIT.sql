-- =====================================================================
-- STEP 5A.1 REVISED — AUDIT ACTUAL CANONICAL IMPLEMENTATION
-- Knowledge Base is in claris_kb schema
-- Canonical implementation is in claris schema
-- =====================================================================

-- =====================================================================
-- SECTION 1: ACTUAL KB IDENTITY RULES (claris_kb.identity_rules)
-- =====================================================================

SELECT
  'KB_IDENTITY_RULES' AS section,
  *
FROM claris_kb.identity_rules
ORDER BY id;

-- Alternative: Check if ontology.identity_rules exists
SELECT
  'ONTOLOGY_IDENTITY_RULES' AS section,
  *
FROM ontology.identity_rules
ORDER BY id;

-- =====================================================================
-- SECTION 2: KB CONFIGURATION DIMENSIONS (What defines configuration identity?)
-- =====================================================================

SELECT
  'KB_CONFIG_DIMENSIONS' AS section,
  *
FROM claris_kb.configuration_dimensions
ORDER BY id;

-- =====================================================================
-- SECTION 3: KB DECISION RULES (What decisions are already defined?)
-- =====================================================================

SELECT
  'KB_DECISION_RULES' AS section,
  *
FROM claris_kb.decision_rules
ORDER BY id;

-- =====================================================================
-- SECTION 4: ACTUAL CANONICAL.PRODUCT (Is it populated?)
-- =====================================================================

SELECT
  'CANONICAL_PRODUCT_COUNT' AS section,
  COUNT(*) AS total_products,
  COUNT(DISTINCT product_id) AS distinct_products
FROM claris.product;

-- Show sample products
SELECT
  'CANONICAL_PRODUCT_SAMPLES' AS section,
  *
FROM claris.product
LIMIT 10;

-- =====================================================================
-- SECTION 5: ACTUAL CANONICAL.CONFIGURATION (Is it populated?)
-- =====================================================================

SELECT
  'CANONICAL_CONFIGURATION_COUNT' AS section,
  COUNT(*) AS total_configs,
  COUNT(DISTINCT configuration_id) AS distinct_configs
FROM claris.configuration;

-- Show sample configurations
SELECT
  'CANONICAL_CONFIGURATION_SAMPLES' AS section,
  *
FROM claris.configuration
LIMIT 10;

-- =====================================================================
-- SECTION 6: ACTUAL CANONICAL.CONFIGURATION_VERSION (Is it populated?)
-- =====================================================================

SELECT
  'CANONICAL_VERSION_COUNT' AS section,
  COUNT(*) AS total_versions,
  COUNT(DISTINCT configuration_id) AS distinct_configs_versioned
FROM claris.configuration_version;

-- Show sample versions
SELECT
  'CANONICAL_VERSION_SAMPLES' AS section,
  *
FROM claris.configuration_version
LIMIT 10;

-- =====================================================================
-- SECTION 7: ACTUAL CANONICAL.DECISION (What decisions exist?)
-- =====================================================================

SELECT
  'CANONICAL_DECISION_COUNT' AS section,
  COUNT(*) AS total_decisions,
  COUNT(DISTINCT decision_id) AS distinct_decisions
FROM claris.decision;

-- Show decision types
SELECT
  'CANONICAL_DECISION_TYPES' AS section,
  decision_type,
  COUNT(*) AS count
FROM claris.decision
GROUP BY decision_type
ORDER BY count DESC;

-- =====================================================================
-- SECTION 8: FOLD VS CANONICAL COVERAGE (Which Fold subjects are in Canonical?)
-- =====================================================================

-- Count Fold configurations
SELECT
  'FOLD_CONFIGURATION_COUNT' AS section,
  COUNT(DISTINCT subject_id) AS fold_config_count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND subject_type = 'configuration';

-- Count Canonical configurations
SELECT
  'CANONICAL_CONFIGURATION_COUNT' AS section,
  COUNT(DISTINCT configuration_id) AS canonical_config_count
FROM claris.configuration;

-- Show gap: Fold subjects not in Canonical
SELECT
  'FOLD_TO_CANONICAL_GAP' AS section,
  fss.subject_id AS fold_config_id,
  'MISSING_FROM_CANONICAL' AS status
FROM state.fold_state_snapshot fss
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND fss.subject_type = 'configuration'
  AND NOT EXISTS (
    SELECT 1 FROM claris.configuration c
    WHERE c.fold_subject_id = fss.subject_id
       OR c.configuration_id::TEXT = fss.subject_id
  );

-- =====================================================================
-- SECTION 9: CANONICAL SCHEMA INTROSPECTION (What columns exist?)
-- =====================================================================

SELECT
  'CANONICAL_PRODUCT_SCHEMA' AS section,
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'product'
ORDER BY ordinal_position;

SELECT
  'CANONICAL_CONFIGURATION_SCHEMA' AS section,
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration'
ORDER BY ordinal_position;

SELECT
  'CANONICAL_VERSION_SCHEMA' AS section,
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration_version'
ORDER BY ordinal_position;

-- =====================================================================
-- SECTION 10: EXISTING DECISION TYPES & STATUSES
-- =====================================================================

SELECT
  'EXISTING_DECISION_STATUSES' AS section,
  decision_status,
  COUNT(*) AS count
FROM claris.decision
GROUP BY decision_status
ORDER BY count DESC;

-- =====================================================================
-- SECTION 11: CHECK CLARIS_KB TABLES STRUCTURE
-- =====================================================================

SELECT
  'CLARIS_KB_TABLES' AS section,
  table_name,
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'claris_kb' AND table_name = claris_kb_tables.table_name) AS column_count
FROM (
  SELECT 'identity_rules' AS table_name
  UNION ALL SELECT 'configuration_dimensions'
  UNION ALL SELECT 'decision_rules'
  UNION ALL SELECT 'decisions'
  UNION ALL SELECT 'decision_inputs'
  UNION ALL SELECT 'decision_outputs'
  UNION ALL SELECT 'projection_rules'
) claris_kb_tables
ORDER BY table_name;

-- =====================================================================
-- SECTION 12: FOLD PROPERTY INVENTORY (Still needed for comparison)
-- =====================================================================

SELECT
  'FOLD_PROPERTY_SUMMARY' AS section,
  COUNT(DISTINCT props->>'property_name') AS total_unique_properties,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'ESTABLISHED' THEN props->>'property_name' END) AS established_properties,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'UNREPORTED' THEN props->>'property_name' END) AS unreported_properties,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'CONTRADICTED' THEN props->>'property_name' END) AS contradicted_properties
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;
