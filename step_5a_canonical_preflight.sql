-- =====================================================================
-- STEP 5A PREFLIGHT: CANONICAL STATE LAYER DESIGN ANALYSIS
-- =====================================================================
-- Read-only inspection of Fold state for canonical design
-- Horizon: 2026-06-20 10:45:00+00
-- =====================================================================

-- =====================================================================
-- SECTION 1: FOLD STATE INVENTORY
-- =====================================================================

-- Complete Fold snapshot summary by subject type
SELECT 
  'INVENTORY: FOLD SUBJECTS BY TYPE' AS section,
  subject_type,
  COUNT(DISTINCT subject_id) AS subject_count,
  COUNT(DISTINCT subject_id) FILTER (WHERE fold_status = 'ESTABLISHED') AS established_count,
  COUNT(DISTINCT subject_id) FILTER (WHERE fold_status = 'UNREPORTED') AS unreported_count,
  COUNT(DISTINCT subject_id) FILTER (WHERE fold_status = 'CONTRADICTED') AS contradicted_count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY subject_type
ORDER BY subject_type;

-- =====================================================================
-- SECTION 2: FOLD PROPERTIES BY SUBJECT TYPE
-- =====================================================================

-- Detailed property inventory with fold states
SELECT 
  'INVENTORY: FOLD PROPERTIES' AS section,
  subject_type,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state,
  COUNT(*) AS count_across_subjects,
  COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED') AS established_count,
  COUNT(*) FILTER (WHERE props->>'fold_state' = 'UNREPORTED') AS unreported_count,
  COUNT(*) FILTER (WHERE props->>'fold_state' = 'CONTRADICTED') AS contradicted_count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY subject_type, props->>'property_name', props->>'fold_state'
ORDER BY subject_type, props->>'property_name', fold_state;

-- =====================================================================
-- SECTION 3: SAMPLE CONFIGURATION SNAPSHOT
-- =====================================================================

-- One configuration subject with all properties
SELECT 
  'SAMPLE: CONFIGURATION (CON-001) FOLD STATE' AS section,
  subject_id,
  fold_status,
  jsonb_pretty(folded_properties) AS all_properties
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND subject_type = 'configuration'
  AND subject_id = 'CON-001'
LIMIT 1;

-- =====================================================================
-- SECTION 4: SAMPLE SKU SNAPSHOT
-- =====================================================================

-- One SKU subject with all properties
SELECT 
  'SAMPLE: SKU (SKU-006) FOLD STATE' AS section,
  subject_id,
  fold_status,
  jsonb_pretty(folded_properties) AS all_properties
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND subject_type = 'sku'
  AND subject_id = 'SKU-006'
LIMIT 1;

-- =====================================================================
-- SECTION 5: SAMPLE LAUNCH SNAPSHOT
-- =====================================================================

-- One launch subject with all properties
SELECT 
  'SAMPLE: LAUNCH (LAUNCH-001) FOLD STATE' AS section,
  subject_id,
  fold_status,
  jsonb_pretty(folded_properties) AS all_properties
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND subject_type = 'launch'
  AND subject_id = 'LAUNCH-001'
LIMIT 1;

-- =====================================================================
-- SECTION 6: KB IDENTITY RULES (Governance)
-- =====================================================================

-- Check what identity rules exist in KB
SELECT 
  'KB IDENTITY RULES' AS section,
  rule_id,
  rule_name,
  rule_type,
  jsonb_pretty(rule_definition) AS definition,
  created_at,
  updated_at
FROM knowledge_base.rules
WHERE rule_type LIKE '%IDENTITY%'
  OR rule_name LIKE '%IR-%'
ORDER BY rule_id;

-- =====================================================================
-- SECTION 7: KB PROPERTY MAPPINGS
-- =====================================================================

-- Check property classification in KB
SELECT 
  'KB PROPERTY CLASSIFICATION' AS section,
  property_name,
  subject_type,
  property_semantics,
  identity_relevance,
  version_relevance,
  jsonb_pretty(property_definition) AS definition
FROM knowledge_base.properties
WHERE subject_type IN ('product', 'configuration', 'sku', 'launch', 'material')
ORDER BY subject_type, property_name;

-- =====================================================================
-- SECTION 8: KB POLICY VERSIONING RULES
-- =====================================================================

-- Check policy for versioning semantics
SELECT 
  'KB POLICY: VERSIONING SEMANTICS' AS section,
  policy_id,
  policy_name,
  jsonb_pretty(policy_definition) AS policy
FROM knowledge_base.policies
WHERE policy_type = 'VERSIONING'
  OR policy_name LIKE '%VERSION%'
ORDER BY policy_id;

-- =====================================================================
-- SECTION 9: FOLD STATUS DISTRIBUTION
-- =====================================================================

-- Complete fold status view
SELECT 
  'FOLD STATUS DISTRIBUTION' AS section,
  subject_type,
  fold_status,
  COUNT(DISTINCT subject_id) AS subject_count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY subject_type, fold_status
ORDER BY subject_type, fold_status;

-- =====================================================================
-- SECTION 10: UNREPORTED PROPERTIES IMPACT
-- =====================================================================

-- Which subject/property pairs are UNREPORTED?
SELECT 
  'UNREPORTED PROPERTIES DETAIL' AS section,
  subject_type,
  subject_id,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND props->>'fold_state' = 'UNREPORTED'
ORDER BY subject_type, subject_id, props->>'property_name';

-- =====================================================================
-- SECTION 11: CONTRADICTED PROPERTIES
-- =====================================================================

-- Check for any contradicted properties
SELECT 
  'CONTRADICTED PROPERTIES' AS section,
  subject_type,
  subject_id,
  props->>'property_name' AS property_name,
  props->>'fold_state' AS fold_state
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-09-07 10:45:00+00'::timestamptz
  AND props->>'fold_state' = 'CONTRADICTED'
ORDER BY subject_type, subject_id, props->>'property_name';

-- =====================================================================
-- SECTION 12: MATERIAL SNAPSHOT
-- =====================================================================

-- All material subjects
SELECT 
  'MATERIALS' AS section,
  subject_id,
  fold_status,
  jsonb_pretty(folded_properties) AS properties
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
  AND subject_type = 'material'
ORDER BY subject_id;

