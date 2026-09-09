-- =====================================================================
-- STEP 5A.1 — COMPREHENSIVE CANONICAL IMPLEMENTATION AUDIT (READ-ONLY)
-- Verify existing Canonical, Decision, Projection, Workbench implementation
-- =====================================================================

-- =====================================================================
-- SECTION 1: SCHEMA OBJECT VERIFICATION
-- =====================================================================

SELECT
  'SCHEMA_OBJECTS_VERIFICATION' AS section,
  table_schema,
  table_name,
  table_type,
  (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = t.table_schema AND table_name = t.table_name) AS column_count
FROM information_schema.tables t
WHERE table_schema = 'claris'
  AND table_name IN ('product', 'configuration', 'configuration_version', 'decision', 'action_record', 'projection')
ORDER BY table_name;

-- =====================================================================
-- SECTION 2: WORKBENCH VIEWS INVENTORY
-- =====================================================================

SELECT
  'WORKBENCH_VIEWS' AS section,
  table_name
FROM information_schema.tables
WHERE table_schema = 'claris' AND table_name LIKE 'v_workbench_%'
ORDER BY table_name;

-- =====================================================================
-- SECTION 3: ROW COUNTS (All existing Canonical tables)
-- =====================================================================

SELECT
  'CANONICAL_PRODUCT_ROWS' AS section,
  COUNT(*) AS row_count,
  COUNT(DISTINCT product_id) AS distinct_products
FROM claris.product;

SELECT
  'CANONICAL_CONFIGURATION_ROWS' AS section,
  COUNT(*) AS row_count,
  COUNT(DISTINCT configuration_id) AS distinct_configurations,
  COUNT(DISTINCT product_id) AS linked_products
FROM claris.configuration;

SELECT
  'CANONICAL_CONFIGURATION_VERSION_ROWS' AS section,
  COUNT(*) AS row_count,
  COUNT(DISTINCT version_id) AS distinct_versions,
  COUNT(DISTINCT configuration_id) AS distinct_configs_versioned,
  COUNT(DISTINCT created_by_decision) AS decisions_involved
FROM claris.configuration_version;

SELECT
  'CANONICAL_DECISION_ROWS' AS section,
  COUNT(*) AS row_count,
  COUNT(DISTINCT decision_id) AS distinct_decisions
FROM claris.decision;

SELECT
  'CANONICAL_ACTION_RECORD_ROWS' AS section,
  COUNT(*) AS row_count
FROM claris.action_record;

SELECT
  'CANONICAL_PROJECTION_ROWS' AS section,
  COUNT(*) AS row_count
FROM claris.projection;

-- =====================================================================
-- SECTION 4: CANONICAL.PRODUCT SCHEMA DEFINITION
-- =====================================================================

SELECT
  'PRODUCT_SCHEMA' AS section,
  column_name,
  data_type,
  is_nullable,
  column_default,
  ordinal_position
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'product'
ORDER BY ordinal_position;

-- =====================================================================
-- SECTION 5: CANONICAL.CONFIGURATION SCHEMA DEFINITION
-- =====================================================================

SELECT
  'CONFIGURATION_SCHEMA' AS section,
  column_name,
  data_type,
  is_nullable,
  column_default,
  ordinal_position
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration'
ORDER BY ordinal_position;

-- =====================================================================
-- SECTION 6: CANONICAL.CONFIGURATION_VERSION SCHEMA DEFINITION
-- =====================================================================

SELECT
  'CONFIGURATION_VERSION_SCHEMA' AS section,
  column_name,
  data_type,
  is_nullable,
  column_default,
  ordinal_position
FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration_version'
ORDER BY ordinal_position;

-- =====================================================================
-- SECTION 7: PRIMARY KEYS
-- =====================================================================

SELECT
  'PRIMARY_KEYS' AS section,
  tc.table_name,
  string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_schema = 'claris'
  AND tc.constraint_type = 'PRIMARY KEY'
  AND tc.table_name IN ('product', 'configuration', 'configuration_version', 'decision')
GROUP BY tc.table_name
ORDER BY tc.table_name;

-- =====================================================================
-- SECTION 8: FOREIGN KEYS
-- =====================================================================

SELECT
  'FOREIGN_KEYS' AS section,
  tc.table_name,
  kcu.column_name,
  ccu.table_name AS referenced_table,
  ccu.column_name AS referenced_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
WHERE tc.table_schema = 'claris'
  AND tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('product', 'configuration', 'configuration_version', 'decision')
ORDER BY tc.table_name, kcu.column_name;

-- =====================================================================
-- SECTION 9: SAMPLE PRODUCT DATA (If populated)
-- =====================================================================

SELECT
  'SAMPLE_PRODUCT_DATA' AS section,
  *
FROM claris.product
LIMIT 5;

-- =====================================================================
-- SECTION 10: SAMPLE CONFIGURATION DATA (If populated)
-- =====================================================================

SELECT
  'SAMPLE_CONFIGURATION_DATA' AS section,
  *
FROM claris.configuration
LIMIT 5;

-- =====================================================================
-- SECTION 11: SAMPLE CONFIGURATION_VERSION DATA (If populated)
-- =====================================================================

SELECT
  'SAMPLE_CONFIGURATION_VERSION_DATA' AS section,
  *
FROM claris.configuration_version
LIMIT 5;

-- =====================================================================
-- SECTION 12: KB IDENTITY RULES (claris_kb.identity_rules)
-- =====================================================================

SELECT
  'KB_IDENTITY_RULES' AS section,
  *
FROM claris_kb.identity_rules
ORDER BY id
LIMIT 20;

-- =====================================================================
-- SECTION 13: KB CONFIGURATION DIMENSIONS
-- =====================================================================

SELECT
  'KB_CONFIGURATION_DIMENSIONS' AS section,
  *
FROM claris_kb.configuration_dimensions
ORDER BY id;

-- =====================================================================
-- SECTION 14: KB CONFIGURATION DIMENSION VALUES
-- =====================================================================

SELECT
  'KB_DIMENSION_VALUES_SAMPLE' AS section,
  dimension_id,
  dimension_value,
  COUNT(*) AS count
FROM claris_kb.configuration_dimension_values
GROUP BY dimension_id, dimension_value
ORDER BY dimension_id
LIMIT 20;

-- =====================================================================
-- SECTION 15: KB DECISION RULES
-- =====================================================================

SELECT
  'KB_DECISION_RULES' AS section,
  *
FROM claris_kb.decision_rules
LIMIT 20;

-- =====================================================================
-- SECTION 16: FOLD SUBJECT COUNT
-- =====================================================================

SELECT
  'FOLD_SUBJECT_COUNT' AS section,
  subject_type,
  COUNT(DISTINCT subject_id) AS subject_count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY subject_type
ORDER BY subject_type;

-- =====================================================================
-- SECTION 17: FOLD vs CANONICAL MAPPING (Configuration subjects)
-- =====================================================================

SELECT
  'FOLD_CONFIG_SUBJECTS' AS section,
  COUNT(DISTINCT fss.subject_id) AS fold_config_count
FROM state.fold_state_snapshot fss
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND fss.subject_type = 'configuration';

-- =====================================================================
-- SECTION 18: GAP ANALYSIS - Fold configs not in Canonical
-- =====================================================================

SELECT
  'GAP_FOLD_CONFIGS_NOT_IN_CANONICAL' AS section,
  fss.subject_id AS fold_config_id,
  'MISSING' AS canonical_status,
  fss.fold_status
FROM state.fold_state_snapshot fss
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND fss.subject_type = 'configuration'
  AND NOT EXISTS (
    SELECT 1 FROM claris.configuration cc
    WHERE cc.fold_subject_id = fss.subject_id OR cc.configuration_id::TEXT LIKE '%' || fss.subject_id || '%'
  )
LIMIT 20;

-- =====================================================================
-- SECTION 19: CANONICAL CONFIGURATIONS WITH LINEAGE
-- =====================================================================

SELECT
  'CANONICAL_CONFIG_LINEAGE_SAMPLE' AS section,
  configuration_id,
  fold_subject_id,
  product_id,
  configuration_status,
  created_at,
  created_by_decision
FROM claris.configuration
LIMIT 10;

-- =====================================================================
-- SECTION 20: EXISTING DECISION TYPES
-- =====================================================================

SELECT
  'DECISION_TYPES' AS section,
  decision_type,
  COUNT(*) AS count,
  MIN(created_at) AS first_decision,
  MAX(created_at) AS latest_decision
FROM claris.decision
GROUP BY decision_type
ORDER BY count DESC;

-- =====================================================================
-- SECTION 21: EXISTING DECISION SUBJECTS
-- =====================================================================

SELECT
  'DECISION_SUBJECTS' AS section,
  subject_type,
  COUNT(*) AS count
FROM claris.decision
GROUP BY subject_type
ORDER BY count DESC;

-- =====================================================================
-- SECTION 22: DECISION AUTHORITY CHECK - Products
-- =====================================================================

SELECT
  'PRODUCT_DECISION_BACKED' AS section,
  COUNT(*) AS count,
  COUNT(DISTINCT created_by_decision) AS distinct_decisions
FROM claris.product
WHERE created_by_decision IS NOT NULL;

SELECT
  'PRODUCT_NO_DECISION' AS section,
  COUNT(*) AS count
FROM claris.product
WHERE created_by_decision IS NULL;

-- =====================================================================
-- SECTION 23: DECISION AUTHORITY CHECK - Configurations
-- =====================================================================

SELECT
  'CONFIGURATION_DECISION_BACKED' AS section,
  COUNT(*) AS count,
  COUNT(DISTINCT created_by_decision) AS distinct_decisions
FROM claris.configuration
WHERE created_by_decision IS NOT NULL;

SELECT
  'CONFIGURATION_NO_DECISION' AS section,
  COUNT(*) AS count
FROM claris.configuration
WHERE created_by_decision IS NULL;

-- =====================================================================
-- SECTION 24: SKU vs CONFIGURATION PROLIFERATION CHECK
-- =====================================================================

SELECT
  'SKU_CONFIGURATION_RATIO' AS section,
  (SELECT COUNT(DISTINCT subject_id) FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND subject_type = 'sku') AS fold_sku_count,
  (SELECT COUNT(*) FROM claris.configuration) AS canonical_config_count,
  (SELECT COUNT(*) FROM claris.product) AS canonical_product_count;

-- =====================================================================
-- SECTION 25: CONFIGURATION_VERSION CHANGE TYPES
-- =====================================================================

SELECT
  'VERSION_CHANGE_TYPES' AS section,
  COALESCE(change_type, 'NULL') AS change_type,
  COUNT(*) AS count
FROM claris.configuration_version
GROUP BY change_type
ORDER BY count DESC;

-- =====================================================================
-- SECTION 26: PROJECTION TARGET SYSTEMS
-- =====================================================================

SELECT
  'PROJECTION_TARGETS' AS section,
  target_system,
  COUNT(*) AS count
FROM claris.projection
GROUP BY target_system
ORDER BY target_system;

-- =====================================================================
-- SECTION 27: PROJECTION SAMPLE (If populated)
-- =====================================================================

SELECT
  'PROJECTION_SAMPLE' AS section,
  *
FROM claris.projection
LIMIT 5;

-- =====================================================================
-- SECTION 28: WORKBENCH VIEW DEFINITIONS (Check dependencies)
-- =====================================================================

SELECT
  'WORKBENCH_VIEW_SAMPLE' AS section,
  table_name,
  definition
FROM information_schema.views
WHERE table_schema = 'claris' AND table_name LIKE 'v_workbench_%'
LIMIT 3;

-- =====================================================================
-- SECTION 29: FOLD PROPERTY COUNT
-- =====================================================================

SELECT
  'FOLD_PROPERTY_STATISTICS' AS section,
  COUNT(DISTINCT props->>'property_name') AS total_unique_properties,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'ESTABLISHED' THEN props->>'property_name' END) AS established_properties,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'UNREPORTED' THEN props->>'property_name' END) AS unreported_properties,
  COUNT(DISTINCT CASE WHEN props->>'fold_state' = 'CONTRADICTED' THEN props->>'property_name' END) AS contradicted_properties
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

-- =====================================================================
-- SECTION 30: CANONICAL CONSISTENCY CHECK
-- =====================================================================

SELECT
  'CANONICAL_CONSISTENCY_CHECK' AS section,
  'Total Fold Subjects (Configuration)' AS check_description,
  (SELECT COUNT(DISTINCT subject_id) FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND subject_type = 'configuration')::TEXT AS value

UNION ALL

SELECT
  'CANONICAL_CONSISTENCY_CHECK' AS section,
  'Total Canonical Configurations' AS check_description,
  COUNT(*)::TEXT
FROM claris.configuration

UNION ALL

SELECT
  'CANONICAL_CONSISTENCY_CHECK' AS section,
  'Canonical Configurations with Product Link' AS check_description,
  COUNT(CASE WHEN product_id IS NOT NULL THEN 1 END)::TEXT
FROM claris.configuration

UNION ALL

SELECT
  'CANONICAL_CONSISTENCY_CHECK' AS section,
  'Canonical Versions with Change Type' AS check_description,
  COUNT(CASE WHEN change_type IS NOT NULL THEN 1 END)::TEXT
FROM claris.configuration_version

UNION ALL

SELECT
  'CANONICAL_CONSISTENCY_CHECK' AS section,
  'Canonical Versions with Decision Link' AS check_description,
  COUNT(CASE WHEN created_by_decision IS NOT NULL THEN 1 END)::TEXT
FROM claris.configuration_version;
