-- =====================================================================
-- STEP 5F.3 DEBUG FOLD LOGIC - STEP BY STEP
-- Pure SQL - Run in pgAdmin Query Tool
-- =====================================================================

-- Create debug results table
CREATE TEMP TABLE debug_fold_results (
    step_num INT,
    step_name TEXT,
    status TEXT,
    row_count INT,
    error_msg TEXT,
    details TEXT
);

-- =====================================================================
-- STEP 1: Check subject types and counts
-- =====================================================================
INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Configuration subjects', 'OK', COUNT(*) || ' subjects'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Launch subjects', 'OK', COUNT(*) || ' subjects'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Material subjects', 'OK', COUNT(*) || ' subjects'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'material') a;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'SKU subjects', 'OK', COUNT(*) || ' subjects'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Product subjects', 'OK', COUNT(*) || ' subjects'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'product') a;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Configuration Request subjects', 'OK', COUNT(*) || ' subjects'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a;

-- =====================================================================
-- STEP 2: Build applicable_properties
-- =====================================================================
CREATE TEMP TABLE temp_applicable_properties AS
-- Configuration
SELECT 'configuration' AS subject_type, subject_id, 'sap_con_hierarchy_code' AS property_name
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a
UNION ALL
SELECT 'configuration', subject_id, 'sap_con_load_actor'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a
UNION ALL
SELECT 'configuration', subject_id, 'sap_con_load_status'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a
UNION ALL
SELECT 'configuration', subject_id, 'sap_prd_hierarchy_code'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a
UNION ALL
SELECT 'configuration', subject_id, 'sap_prd_load_status'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a
-- Launch
UNION ALL
SELECT 'launch', subject_id, 'change_requested_by'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
UNION ALL
SELECT 'launch', subject_id, 'change_requester_role'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
UNION ALL
SELECT 'launch', subject_id, 'intent_classification'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
-- Material
UNION ALL
SELECT 'material', subject_id, 'material_status'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'material') a
-- SKU
UNION ALL
SELECT 'sku', subject_id, 'pricing_confirmed'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
UNION ALL
SELECT 'sku', subject_id, 'pricing_status'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
UNION ALL
SELECT 'sku', subject_id, 'pricing_value_usd'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
UNION ALL
SELECT 'sku', subject_id, 'sku_activation_status'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
UNION ALL
SELECT 'sku', subject_id, 'sku_status'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
UNION ALL
SELECT 'sku', subject_id, 'technical_review_result'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
-- Product (extended)
UNION ALL
SELECT 'product', subject_id, 'product_name'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'product') a
UNION ALL
SELECT 'product', subject_id, 'launch_reference'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'product') a
-- Configuration Request (extended)
UNION ALL
SELECT 'configuration_request', subject_id, 'product_reference'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
UNION ALL
SELECT 'configuration_request', subject_id, 'launch_reference'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
UNION ALL
SELECT 'configuration_request', subject_id, 'geography'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
UNION ALL
SELECT 'configuration_request', subject_id, 'term_months'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
UNION ALL
SELECT 'configuration_request', subject_id, 'customer_segment'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Applicable properties built', 'OK', COUNT(*) || ' property triples'
FROM temp_applicable_properties;

-- =====================================================================
-- STEP 3: Check KB and Policy versions
-- =====================================================================
INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'KB version', 'OK', kb_version
FROM runtime.governed_knowledge_base
WHERE is_active = true
ORDER BY created_at DESC LIMIT 1;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Policy version', 'OK', policy_version
FROM runtime.governed_policy
WHERE is_active = true
ORDER BY created_at DESC LIMIT 1;

-- =====================================================================
-- STEP 4: Test fold_resolve_value on sample properties
-- =====================================================================
CREATE TEMP TABLE temp_fold_results AS
SELECT
    ap.subject_type,
    ap.subject_id,
    ap.property_name,
    runtime.fold_resolve_value(
        '2026-06-20 10:45:00+00'::TIMESTAMPTZ,
        ap.subject_type,
        ap.subject_id,
        ap.property_name
    ) AS fold_result
FROM temp_applicable_properties ap;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'fold_resolve_value executed', 'OK', COUNT(*) || ' results calculated'
FROM temp_fold_results
WHERE fold_result IS NOT NULL;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'fold_resolve_value nulls', 'WARN', COUNT(*) || ' NULL results'
FROM temp_fold_results
WHERE fold_result IS NULL;

-- =====================================================================
-- STEP 5: Check property states from fold_resolve_value
-- =====================================================================
INSERT INTO debug_fold_results (step_name, status, details)
SELECT
    'Property fold states: ' || (tfr.fold_result->>'fold_state')::TEXT || '',
    'OK',
    COUNT(*) || ' properties'
FROM temp_fold_results tfr
WHERE tfr.fold_result->>'fold_state' IS NOT NULL
GROUP BY (tfr.fold_result->>'fold_state')::TEXT;

-- =====================================================================
-- STEP 6: Verify current fold state
-- =====================================================================
INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Current fold snapshots', 'OK', COUNT(*) || ' snapshots at horizon'
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

INSERT INTO debug_fold_results (step_name, status, details)
SELECT 'Current fold subjects', 'OK', COUNT(DISTINCT (subject_type, subject_id)) || ' distinct subjects'
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

-- =====================================================================
-- STEP 7: Show current subject types in fold
-- =====================================================================
INSERT INTO debug_fold_results (step_name, status, details)
SELECT
    'Current subjects: ' || subject_type || '',
    'OK',
    COUNT(DISTINCT subject_id) || ' subjects'
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
GROUP BY subject_type;

-- =====================================================================
-- FINAL: Show all debug results
-- =====================================================================
SELECT * FROM debug_fold_results ORDER BY step_name;
