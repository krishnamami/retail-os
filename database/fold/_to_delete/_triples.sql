    SELECT 'configuration' AS subject_type, subject_id,
           'sap_con_hierarchy_code' AS property_name
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_load_actor'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_load_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'con_verification_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_test_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_con_test_actor'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'CON-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_hierarchy_code'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_load_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_promotion_hierarchy_code'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
    UNION ALL
    SELECT 'configuration', subject_id, 'sap_prd_promotion_actor'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration' AND subject_id LIKE 'PRD-%'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'change_requested_by'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'change_requester_role'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'intent_classification'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'hierarchy_approval_code'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'launch', subject_id, 'hierarchy_approval_authority'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'launch'
    ) a
    UNION ALL
    SELECT 'material', subject_id, 'material_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'material'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_confirmed'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_value_usd'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'sku_activation_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'sku_status'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'technical_review_result'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'final_pricing_approval_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_upload_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_uploaded_price_usd'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_publication_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_list_price'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_currency'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'pricing_published_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'overnight_push_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'overnight_push_run_date'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'zupdm_approval_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'all_gates_cleared'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approval_requested'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approval_level'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_requested_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approval_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'go_live_approved_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'supply_chain_notification_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'supply_chain_notification_type'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'supply_chain_notified_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'material_activation_status'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'sku', subject_id, 'material_activated_by'   -- D4I_004
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'sku'
    ) a
    UNION ALL
    SELECT 'product', subject_id, 'product_name'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'product'
    ) a
    UNION ALL
    SELECT 'product', subject_id, 'launch_reference'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'product'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'product_reference'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'launch_reference'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'geography'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'term_months'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a
    UNION ALL
    SELECT 'configuration_request', subject_id, 'customer_segment'
    FROM (
      SELECT DISTINCT subject_id FROM runtime.assertion
      WHERE subject_type = 'configuration_request'
    ) a