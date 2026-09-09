-- =====================================================================
-- FOLD INSERTION - SIMPLE VERSION
-- Run this in pgAdmin Query Tool
-- =====================================================================

-- Step 1: Build applicable properties
CREATE TEMP TABLE applicable_properties AS
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
UNION ALL
SELECT 'launch', subject_id, 'change_requested_by'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
UNION ALL
SELECT 'launch', subject_id, 'change_requester_role'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
UNION ALL
SELECT 'launch', subject_id, 'intent_classification'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
UNION ALL
SELECT 'material', subject_id, 'material_status'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'material') a
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
UNION ALL
SELECT 'product', subject_id, 'product_name'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'product') a
UNION ALL
SELECT 'product', subject_id, 'launch_reference'
FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'product') a
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

-- Step 2: Compute fold results
CREATE TEMP TABLE property_fold_results AS
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
FROM applicable_properties ap;

-- Step 3: Build property entries
CREATE TEMP TABLE property_entries AS
SELECT
    pfr.subject_type,
    pfr.subject_id,
    jsonb_build_object(
        'property_name', pfr.property_name,
        'fold_state', pfr.fold_result->>'fold_state',
        'resolved_value', pfr.fold_result->'resolved_value',
        'property_value_type', pfr.fold_result->>'property_value_type',
        'effective_at', pfr.fold_result->>'effective_at',
        'latest_known_arrival_at', pfr.fold_result->>'latest_known_arrival_at',
        'basis_assertion_ids', pfr.fold_result->'basis_assertion_ids'
    ) AS property_json,
    COALESCE(
        (SELECT array_agg(val::uuid)
         FROM jsonb_array_elements_text(pfr.fold_result->'basis_assertion_ids') val
         WHERE val IS NOT NULL AND val != ''),
        '{}'::uuid[]
    ) AS basis_ids
FROM property_fold_results pfr;

-- Step 4: Aggregate per subject
CREATE TEMP TABLE subject_snapshots AS
SELECT
    subject_type,
    subject_id,
    jsonb_agg(property_json ORDER BY property_json->>'property_name') AS folded_properties,
    array_agg(DISTINCT u.basis_id ORDER BY u.basis_id) FILTER (WHERE u.basis_id IS NOT NULL) AS all_basis_ids,
    CASE
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'CONTRADICTED') THEN 'CONTRADICTED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'EXPLICITLY_UNDEFINED') THEN 'EXPLICITLY_UNDEFINED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'UNREPORTED') THEN 'UNREPORTED'
        ELSE 'ESTABLISHED'
    END AS computed_fold_status
FROM property_entries pe
LEFT JOIN LATERAL UNNEST(pe.basis_ids) AS u(basis_id) ON TRUE
GROUP BY subject_type, subject_id;

-- Step 5: Insert into fold_state_snapshot
INSERT INTO state.fold_state_snapshot (
    decision_horizon, subject_type, subject_id, fold_status,
    folded_properties, basis_assertion_ids, kb_version, policy_version,
    fold_computed_at
)
SELECT
    '2026-06-20 10:45:00+00'::TIMESTAMPTZ,
    ss.subject_type,
    ss.subject_id,
    ss.computed_fold_status,
    ss.folded_properties,
    ss.all_basis_ids,
    'KB-v1.0.0',
    'POLICY-v1.0.0',
    CURRENT_TIMESTAMP
FROM subject_snapshots ss
ON CONFLICT (decision_horizon, subject_type, subject_id)
DO NOTHING;

-- Step 6: Show results
SELECT 'Total snapshots after insert' AS check, COUNT(*) AS count FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

SELECT 'Product subjects created' AS check, COUNT(DISTINCT subject_id) AS count FROM state.fold_state_snapshot WHERE subject_type = 'product' AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

SELECT 'Configuration Request subjects created' AS check, COUNT(DISTINCT subject_id) AS count FROM state.fold_state_snapshot WHERE subject_type = 'configuration_request' AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

SELECT 'S6 subjects (006, 006B)' AS check, COUNT(DISTINCT subject_id) AS count FROM state.fold_state_snapshot WHERE subject_type = 'configuration_request' AND subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B') AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;

SELECT 'S7 subject (007)' AS check, COUNT(*) AS count FROM state.fold_state_snapshot WHERE subject_type = 'configuration_request' AND subject_id = 'CONFIG-REQ-2026-007' AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;
