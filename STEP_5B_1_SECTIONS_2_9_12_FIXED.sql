-- =====================================================================
-- STEP 5B.1 SECTIONS 2, 9, 12 FIX — KB & GOVERNANCE VERIFICATION ONLY
-- Fixed GROUP BY errors in identity matrix, KB rules, and requirements
-- Read-only, no data modifications
-- =====================================================================

CREATE TEMP TABLE IF NOT EXISTS audit_results_fixed (
  execution_order INT,
  section_name TEXT,
  status TEXT,
  rows_returned INT,
  result_data TEXT,
  error_message TEXT,
  execution_time TIMESTAMP DEFAULT NOW()
);

TRUNCATE audit_results_fixed;

CREATE TEMP SEQUENCE audit_counter_fixed START 1;

-- =====================================================================
-- SECTION 2: IDENTITY INPUT AVAILABILITY MATRIX (FIXED)
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results_fixed (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter_fixed'),
      'SECTION_2_IDENTITY_INPUT_MATRIX_FIXED',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'concept=' || concept || '|fold_property_name=' || fold_property_name ||
        '|subject_type=' || subject_type || '|established_count=' || established_count ||
        '|unreported_count=' || unreported_count || '|contradicted_count=' || contradicted_count ||
        '|available_for_identity=' || available_for_identity,
        chr(10)
      )
    FROM (
      SELECT
        CASE
          WHEN props->>'property_name' IN ('product_id', 'product_identifier') THEN 'product_id'
          WHEN props->>'property_name' IN ('product_family', 'family_code', 'new_product_family') THEN 'product_family'
          WHEN props->>'property_name' IN ('offering_code', 'offering') THEN 'offering'
          WHEN props->>'property_name' IN ('geo', 'geography', 'market', 'region', 'market_code') THEN 'geo'
          WHEN props->>'property_name' IN ('term', 'contract_term', 'contract_duration') THEN 'term'
          WHEN props->>'property_name' IN ('segment', 'customer_segment', 'market_segment', 'intent_classification') THEN 'segment'
          WHEN props->>'property_name' IN ('user_tier', 'tier', 'customer_tier', 'tier_code') THEN 'user_tier'
          WHEN props->>'property_name' IN ('package_format', 'packaging', 'package_code') THEN 'package_format'
          WHEN props->>'property_name' IN ('slp_code', 'slp_classification', 'sap_slp_code') THEN 'slp_code'
          WHEN props->>'property_name' IN ('description', 'product_description', 'product_name') THEN 'description'
          WHEN props->>'property_name' IN ('price', 'pricing_value', 'pricing_value_usd', 'unit_price') THEN 'price'
          WHEN props->>'property_name' IN ('hierarchy_code', 'sap_con_hierarchy_code', 'sap_prd_hierarchy_code') THEN 'hierarchy_code'
        END AS concept,
        props->>'property_name' AS fold_property_name,
        fss.subject_type,
        COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED') AS established_count,
        COUNT(*) FILTER (WHERE props->>'fold_state' = 'UNREPORTED') AS unreported_count,
        COUNT(*) FILTER (WHERE props->>'fold_state' = 'CONTRADICTED') AS contradicted_count,
        CASE WHEN COUNT(*) FILTER (WHERE props->>'fold_state' = 'ESTABLISHED') > 0 THEN 'YES' ELSE 'NO' END AS available_for_identity
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
      GROUP BY fss.subject_type, props->>'property_name'
    ) mapped
    WHERE concept IS NOT NULL;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results_fixed (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter_fixed'), 'SECTION_2_IDENTITY_INPUT_MATRIX_FIXED', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 9: IDENTITY EFFECT RULES (FIXED)
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results_fixed (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter_fixed'),
      'SECTION_9_IDENTITY_EFFECT_RULES_FIXED',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'kb_version=' || kb_version || '|rule_id=' || rule_id ||
        '|rule_name=' || rule_name || '|description=' || description ||
        '|status=' || status,
        chr(10)
      )
    FROM claris_kb.identity_rules
    WHERE kb_version IN ('1.0', '1.0.1')
    ORDER BY kb_version, rule_id;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results_fixed (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter_fixed'), 'SECTION_9_IDENTITY_EFFECT_RULES_FIXED', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 12: CHANGE_CLASSIFICATION RULES (FIXED)
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results_fixed (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter_fixed'),
      'SECTION_12_RULE_INPUT_REQUIREMENTS_FIXED',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'rule_id=' || rule_id || '|rule_name=' || rule_name ||
        '|description=' || description || '|status=' || status,
        chr(10)
      )
    FROM claris_kb.identity_rules
    WHERE kb_version = '1.0.1'
      AND rule_id LIKE 'IR-%'
    ORDER BY rule_id;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results_fixed (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter_fixed'), 'SECTION_12_RULE_INPUT_REQUIREMENTS_FIXED', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- FINAL OUTPUT
-- =====================================================================

SELECT '=== SECTIONS 2, 9, 12 FIXED RESULTS ===' AS summary;
SELECT * FROM audit_results_fixed ORDER BY execution_order;
