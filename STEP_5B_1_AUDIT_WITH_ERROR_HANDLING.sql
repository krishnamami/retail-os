-- =====================================================================
-- STEP 5B.1 AUDIT WITH ERROR HANDLING
-- Executes all queries, captures results + errors in temp table
-- =====================================================================

-- Create temp results table
CREATE TEMP TABLE IF NOT EXISTS audit_results (
  execution_order INT,
  section_name TEXT,
  status TEXT,
  rows_returned INT,
  result_data TEXT,
  error_message TEXT,
  execution_time TIMESTAMP DEFAULT NOW()
);

-- Truncate if re-running
TRUNCATE audit_results;

-- Counter for execution order
CREATE TEMP SEQUENCE audit_counter START 1;

-- =====================================================================
-- SECTION 1: COMPLETE ACTUAL FOLD PROPERTY INVENTORY
-- =====================================================================
DO $$
DECLARE
  v_row_count INT;
  v_error_msg TEXT;
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_1_FOLD_PROPERTY_INVENTORY',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|occurrence_count=' || occurrence_count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS occurrence_count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY fss.subject_type, props->>'property_name', props->>'fold_state'
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_1_FOLD_PROPERTY_INVENTORY', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 2: IDENTITY INPUT AVAILABILITY MATRIX
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_2_IDENTITY_INPUT_MATRIX',
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
    WHERE concept IS NOT NULL
    ORDER BY concept, subject_type;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_2_IDENTITY_INPUT_MATRIX', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 3: PRODUCT IDENTITY AVAILABILITY
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_3_PRODUCT_IDENTITY',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|count=' || count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
        AND props->>'property_name' IN ('product_id', 'product_identifier', 'product_family', 'family_code', 'new_product_family')
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY fss.subject_type, props->>'property_name'
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_3_PRODUCT_IDENTITY', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 4: GEO AVAILABILITY
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_4_GEO_AVAILABILITY',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|count=' || count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
        AND props->>'property_name' IN ('geo', 'geography', 'market', 'region', 'market_code')
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY fss.subject_type, props->>'property_name'
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_4_GEO_AVAILABILITY', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 5: TERM AVAILABILITY
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_5_TERM_AVAILABILITY',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|count=' || count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
        AND props->>'property_name' IN ('term', 'contract_term', 'contract_duration', 'term_code')
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY fss.subject_type, props->>'property_name'
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_5_TERM_AVAILABILITY', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 6: SEGMENT AVAILABILITY
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_6_SEGMENT_AVAILABILITY',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|count=' || count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
        AND props->>'property_name' IN ('segment', 'customer_segment', 'market_segment', 'intent_classification', 'segment_code')
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY fss.subject_type, props->>'property_name'
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_6_SEGMENT_AVAILABILITY', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 7: PRICE / PRICING MAPPING
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_7_PRICE_MAPPING',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|count=' || count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
        AND props->>'property_name' IN ('price', 'pricing_value', 'pricing_value_usd', 'unit_price', 'price_change', 'pricing_confirmed', 'pricing_status')
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY fss.subject_type, props->>'property_name'
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_7_PRICE_MAPPING', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 8: HIERARCHY / SLP MAPPING
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_8_HIERARCHY_SLP_MAPPING',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|count=' || count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
        AND props->>'property_name' IN ('slp_code', 'slp_classification', 'sap_slp_code', 'hierarchy_code', 'sap_con_hierarchy_code', 'sap_prd_hierarchy_code')
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY fss.subject_type, props->>'property_name'
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_8_HIERARCHY_SLP_MAPPING', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 9: IDENTITY EFFECT RULES (KB VERIFICATION)
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_9_IDENTITY_EFFECT_RULES',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'kb_version=' || kb_version || '|rule_id=' || rule_id ||
        '|rule_name=' || rule_name || '|status=' || status,
        chr(10)
      )
    FROM claris_kb.identity_rules
    WHERE kb_version IN ('1.0', '1.0.1')
    ORDER BY kb_version, rule_id;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_9_IDENTITY_EFFECT_RULES', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 10: KB TABLE SEARCH
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_10_KB_TABLE_SEARCH',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'table_schema=' || table_schema || '|table_name=' || table_name ||
        '|row_count=' || row_count,
        chr(10)
      )
    FROM (
      SELECT
        table_schema,
        table_name,
        0 AS row_count
      FROM information_schema.tables
      WHERE table_schema IN ('claris_kb', 'ontology')
        AND (table_name ILIKE '%identity%' OR table_name ILIKE '%key%' OR table_name ILIKE '%canonical%')
      ORDER BY table_schema, table_name
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_10_KB_TABLE_SEARCH', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 11: KB ALGORITHM TABLES
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_11_KB_ALGORITHM_TABLES',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'table_schema=' || table_schema || '|table_name=' || table_name ||
        '|row_count=' || row_count,
        chr(10)
      )
    FROM (
      SELECT
        table_schema,
        table_name,
        0 AS row_count
      FROM information_schema.tables
      WHERE table_schema IN ('claris_kb', 'ontology')
        AND (table_name ILIKE '%hash%' OR table_name ILIKE '%digest%' OR table_name ILIKE '%algorithm%')
      ORDER BY table_schema, table_name
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_11_KB_ALGORITHM_TABLES', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 12: CHANGE_CLASSIFICATION RULES
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_12_RULE_INPUT_REQUIREMENTS',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'rule_id=' || rule_id || '|rule_name=' || rule_name ||
        '|status=' || status,
        chr(10)
      )
    FROM claris_kb.identity_rules
    WHERE kb_version = '1.0.1'
      AND rule_id LIKE 'IR-%'
    ORDER BY rule_id;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_12_RULE_INPUT_REQUIREMENTS', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 13: CONFIGURATION PROPERTIES
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_13_CONFIGURATION_PROPERTIES',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'subject_type=' || subject_type || '|property_name=' || property_name ||
        '|fold_state=' || fold_state || '|count=' || count,
        chr(10)
      )
    FROM (
      SELECT
        fss.subject_type,
        props->>'property_name' AS property_name,
        props->>'fold_state' AS fold_state,
        COUNT(*) AS count
      FROM state.fold_state_snapshot fss,
           LATERAL jsonb_array_elements(fss.folded_properties) AS props
      WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
        AND fss.subject_type = 'configuration'
      GROUP BY fss.subject_type, props->>'property_name', props->>'fold_state'
      ORDER BY props->>'property_name'
      LIMIT 100
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_13_CONFIGURATION_PROPERTIES', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 14: UC-18 IDENTITY COMPLETENESS
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_14_IDENTITY_COMPLETENESS',
      'SUCCESS',
      1,
      'total_configurations=' || total_configurations ||
      '|complete_identities=' || complete_identities ||
      '|incomplete_identities=' || incomplete_identities ||
      '|unique_identity_combinations=' || unique_identity_combinations
    FROM (
      WITH identity_candidates AS (
        SELECT
          fss.subject_id,
          MAX(CASE WHEN props->>'property_name' IN ('product_id', 'product_identifier')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS product_id,
          MAX(CASE WHEN props->>'property_name' IN ('geo', 'geography', 'market', 'region')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS geo,
          MAX(CASE WHEN props->>'property_name' IN ('term', 'contract_term')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS term,
          MAX(CASE WHEN props->>'property_name' IN ('segment', 'customer_segment')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS segment
        FROM state.fold_state_snapshot fss,
             LATERAL jsonb_array_elements(fss.folded_properties) AS props
        WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
          AND fss.subject_type = 'configuration'
        GROUP BY fss.subject_id
      )
      SELECT
        COUNT(*) AS total_configurations,
        COUNT(CASE WHEN product_id IS NOT NULL AND geo IS NOT NULL AND term IS NOT NULL AND segment IS NOT NULL THEN 1 END) AS complete_identities,
        COUNT(CASE WHEN product_id IS NULL OR geo IS NULL OR term IS NULL OR segment IS NULL THEN 1 END) AS incomplete_identities,
        COUNT(DISTINCT (product_id, geo, term, segment)) FILTER (WHERE product_id IS NOT NULL AND geo IS NOT NULL AND term IS NOT NULL AND segment IS NOT NULL) AS unique_identity_combinations
      FROM identity_candidates
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_14_IDENTITY_COMPLETENESS', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- SECTION 15: UC-18 IDENTITY DISTRIBUTION
-- =====================================================================
DO $$
BEGIN
  BEGIN
    INSERT INTO audit_results (execution_order, section_name, status, rows_returned, result_data)
    SELECT
      nextval('audit_counter'),
      'SECTION_15_IDENTITY_DISTRIBUTION',
      'SUCCESS',
      COUNT(*),
      string_agg(
        'product_id=' || product_id || '|geo=' || geo ||
        '|term=' || term || '|segment=' || segment ||
        '|fold_subject_count=' || fold_subject_count,
        chr(10)
      )
    FROM (
      WITH identity_candidates AS (
        SELECT
          fss.subject_id,
          MAX(CASE WHEN props->>'property_name' IN ('product_id', 'product_identifier')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS product_id,
          MAX(CASE WHEN props->>'property_name' IN ('geo', 'geography', 'market', 'region')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS geo,
          MAX(CASE WHEN props->>'property_name' IN ('term', 'contract_term')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS term,
          MAX(CASE WHEN props->>'property_name' IN ('segment', 'customer_segment')
               AND props->>'fold_state' = 'ESTABLISHED'
               THEN props->>'resolved_value' END) AS segment
        FROM state.fold_state_snapshot fss,
             LATERAL jsonb_array_elements(fss.folded_properties) AS props
        WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
          AND fss.subject_type = 'configuration'
        GROUP BY fss.subject_id
      )
      SELECT
        product_id,
        geo,
        term,
        segment,
        COUNT(*) AS fold_subject_count
      FROM identity_candidates
      WHERE product_id IS NOT NULL AND geo IS NOT NULL AND term IS NOT NULL AND segment IS NOT NULL
      GROUP BY product_id, geo, term, segment
      ORDER BY COUNT(*) DESC, product_id, geo, term, segment
    ) sub;
  EXCEPTION WHEN OTHERS THEN
    INSERT INTO audit_results (execution_order, section_name, status, error_message)
    VALUES (nextval('audit_counter'), 'SECTION_15_IDENTITY_DISTRIBUTION', 'ERROR', SQLERRM);
  END;
END $$;

-- =====================================================================
-- FINAL SUMMARY & OUTPUT
-- =====================================================================

-- Show execution summary
SELECT '=== AUDIT EXECUTION SUMMARY ===' AS summary;
SELECT
  execution_order,
  section_name,
  status,
  rows_returned,
  CASE WHEN error_message IS NOT NULL THEN 'ERROR: ' || error_message ELSE 'OK' END AS result
FROM audit_results
ORDER BY execution_order;

-- Show detailed results
SELECT '=== DETAILED RESULTS ===' AS detail;
SELECT * FROM audit_results ORDER BY execution_order;
