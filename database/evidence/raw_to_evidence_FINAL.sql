-- =====================================================================
-- Raw → Evidence Transformation Procedure (FINAL)
-- =====================================================================
-- Purpose: Transform raw.raw_event (169 rows) into runtime.evidence using
--          41 approved deterministic mappings
-- Identity: (raw_event_id, mapping_id)
-- Idempotency: ON CONFLICT (raw_event_id, mapping_id) DO NOTHING
-- Semantics: 1 Raw event → 0..N Evidence observations (contradiction-preserving)
-- Date: 2026-09-06
-- Status: FINAL - All JSONB operators fixed + NOT NULL subject_id checks + CHANGE_REQUESTED expanded to 4 mappings
-- =====================================================================
-- Function: runtime.process_raw_to_evidence()
-- Call: SELECT runtime.process_raw_to_evidence();
-- Returns: Summary of transformation results
CREATE OR REPLACE FUNCTION runtime.process_raw_to_evidence()
RETURNS TABLE (
  status_message TEXT,
  raw_count INTEGER,
  evidence_count_before INTEGER,
  evidence_count_after INTEGER,
  evidence_inserted INTEGER
) AS $$
DECLARE
  v_raw_count INTEGER;
  v_evidence_before INTEGER;
  v_evidence_after INTEGER;
BEGIN
  -- Log transformation start
  RAISE NOTICE '================================================================';
  RAISE NOTICE 'RAW → EVIDENCE TRANSFORMATION STARTED';
  RAISE NOTICE '================================================================';
  -- Get baseline counts
  SELECT COUNT(*) INTO v_raw_count FROM raw.raw_event;
  SELECT COUNT(*) INTO v_evidence_before FROM runtime.evidence;
  RAISE NOTICE 'Raw events: %', v_raw_count;
  RAISE NOTICE 'Evidence before transformation: %', v_evidence_before;
  -- =====================================================================
  -- TRANSFORMATION: Apply all 41 approved mappings deterministically
  -- =====================================================================
  -- 1. PRODUCT_INTENT_CREATED → 2 Evidence rows (PRODUCT_INTENT_ID, PRODUCT_INTENT_CLASS)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'PRODUCT_INTENT_ID'::TEXT,
    'product_intent',
    'launch',
    r.launch_id,
    'product_intent_id',
    r.payload->>'product_intent_id',
    'string',
    'product_intent',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'PRODUCT_INTENT_CREATED',
      'mapping_id', 'PRODUCT_INTENT_ID',
      'source_path', 'payload.product_intent_id'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'PRODUCT_INTENT_CREATED'
    AND r.payload->>'product_intent_id' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'PRODUCT_INTENT_CLASS'::TEXT,
    'product_intent',
    'launch',
    r.launch_id,
    'intent_classification',
    COALESCE(r.payload->>'intent_class', 'market_expansion'),
    'string',
    'product_intent',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'PRODUCT_INTENT_CREATED',
      'mapping_id', 'PRODUCT_INTENT_CLASS',
      'source_path', 'payload.intent_class'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'PRODUCT_INTENT_CREATED'
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 2. HIERARCHY_APPROVAL → 4 Evidence rows (CON code, CON auth, PRD code, PRD auth)
  -- CORRECTED: Changed record operator (->) to record field accessor (.)
  -- Handle CON hierarchy code
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'HIERARCHY_APPROVAL_CON_CODE'::TEXT,
    'hierarchy',
    'launch',
    r.launch_id,
    'hierarchy_code_con',
    con_approval.hierarchy_code->>'value',
    'string',
    'approval_workflow',
    con_approval."approval_authority"->>'value',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'HIERARCHY_APPROVAL',
      'mapping_id', 'HIERARCHY_APPROVAL_CON_CODE',
      'source_path', 'payload.hierarchy_approvals[CON].hierarchy_code'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r,
    jsonb_to_record(r.payload->'hierarchy_approvals') AS con_approval(
      hierarchy_code jsonb, approval_authority jsonb, environment TEXT
    )
  WHERE r.event_type = 'HIERARCHY_APPROVAL'
    AND (r.payload->'hierarchy_approvals'->>'environment' = 'CON'
         OR r.payload->'hierarchy_approvals' @> '[{"environment":"CON"}]')
    AND con_approval.hierarchy_code->>'value' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- Handle CON hierarchy auth
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'HIERARCHY_APPROVAL_CON_AUTH'::TEXT,
    'hierarchy',
    'launch',
    r.launch_id,
    'hierarchy_auth_con',
    con_approval."approval_authority"->>'value',
    'string',
    'approval_workflow',
    con_approval."approval_authority"->>'value',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'HIERARCHY_APPROVAL',
      'mapping_id', 'HIERARCHY_APPROVAL_CON_AUTH',
      'source_path', 'payload.hierarchy_approvals[CON].approval_authority'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r,
    jsonb_to_record(r.payload->'hierarchy_approvals') AS con_approval(
      hierarchy_code jsonb, approval_authority jsonb, environment TEXT
    )
  WHERE r.event_type = 'HIERARCHY_APPROVAL'
    AND (r.payload->'hierarchy_approvals'->>'environment' = 'CON'
         OR r.payload->'hierarchy_approvals' @> '[{"environment":"CON"}]')
    AND con_approval."approval_authority"->>'value' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- Handle PRD hierarchy code
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'HIERARCHY_APPROVAL_PRD_CODE'::TEXT,
    'hierarchy',
    'launch',
    r.launch_id,
    'hierarchy_code_prd',
    prd_approval.hierarchy_code->>'value',
    'string',
    'approval_workflow',
    prd_approval."approval_authority"->>'value',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'HIERARCHY_APPROVAL',
      'mapping_id', 'HIERARCHY_APPROVAL_PRD_CODE',
      'source_path', 'payload.hierarchy_approvals[PRD].hierarchy_code'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r,
    jsonb_to_record(r.payload->'hierarchy_approvals') AS prd_approval(
      hierarchy_code jsonb, approval_authority jsonb, environment TEXT
    )
  WHERE r.event_type = 'HIERARCHY_APPROVAL'
    AND (r.payload->'hierarchy_approvals'->>'environment' = 'PRD'
         OR r.payload->'hierarchy_approvals' @> '[{"environment":"PRD"}]')
    AND prd_approval.hierarchy_code->>'value' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- Handle PRD hierarchy auth
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'HIERARCHY_APPROVAL_PRD_AUTH'::TEXT,
    'hierarchy',
    'launch',
    r.launch_id,
    'hierarchy_auth_prd',
    prd_approval."approval_authority"->>'value',
    'string',
    'approval_workflow',
    prd_approval."approval_authority"->>'value',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'HIERARCHY_APPROVAL',
      'mapping_id', 'HIERARCHY_APPROVAL_PRD_AUTH',
      'source_path', 'payload.hierarchy_approvals[PRD].approval_authority'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r,
    jsonb_to_record(r.payload->'hierarchy_approvals') AS prd_approval(
      hierarchy_code jsonb, approval_authority jsonb, environment TEXT
    )
  WHERE r.event_type = 'HIERARCHY_APPROVAL'
    AND (r.payload->'hierarchy_approvals'->>'environment' = 'PRD'
         OR r.payload->'hierarchy_approvals' @> '[{"environment":"PRD"}]')
    AND prd_approval."approval_authority"->>'value' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 3. SAP_CON_LOADED → 3 Evidence rows (FIXED: Added con_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_CON_LOAD_STATUS'::TEXT,
    'sap_load',
    'configuration',
    r.con_id,
    'sap_con_load_status',
    COALESCE(r.payload->>'con_status', 'SUCCESS'),
    'string',
    'sap_con',
    r.payload->>'loaded_by',
    'system',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_CON_LOADED',
      'mapping_id', 'SAP_CON_LOAD_STATUS',
      'source_path', 'payload.con_status'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_CON_LOADED'
    AND r.con_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_CON_LOAD_ACTOR'::TEXT,
    'sap_load',
    'configuration',
    r.con_id,
    'sap_con_load_actor',
    r.payload->>'loaded_by',
    'string',
    'sap_con',
    r.payload->>'loaded_by',
    'system',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_CON_LOADED',
      'mapping_id', 'SAP_CON_LOAD_ACTOR',
      'source_path', 'payload.loaded_by'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_CON_LOADED'
    AND r.con_id IS NOT NULL
    AND r.payload->>'loaded_by' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_CON_HIERARCHY'::TEXT,
    'sap_load',
    'configuration',
    r.con_id,
    'sap_con_hierarchy_code',
    r.payload->>'hierarchy_code',
    'string',
    'sap_con',
    r.payload->>'loaded_by',
    'system',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_CON_LOADED',
      'mapping_id', 'SAP_CON_HIERARCHY',
      'source_path', 'payload.hierarchy_code'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_CON_LOADED'
    AND r.con_id IS NOT NULL
    AND r.payload->>'hierarchy_code' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 4. SAP_PRD_LOADED → 3 Evidence rows (FIXED: Added prd_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_PRD_LOAD_STATUS'::TEXT,
    'sap_load',
    'configuration',
    r.prd_id,
    'sap_prd_load_status',
    COALESCE(r.payload->>'prd_status', 'SUCCESS'),
    'string',
    'sap_prd',
    r.payload->>'loaded_by',
    'system',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_PRD_LOADED',
      'mapping_id', 'SAP_PRD_LOAD_STATUS',
      'source_path', 'payload.prd_status'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_PRD_LOADED'
    AND r.prd_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_PRD_LOAD_ACTOR'::TEXT,
    'sap_load',
    'configuration',
    r.prd_id,
    'sap_prd_load_actor',
    r.payload->>'loaded_by',
    'string',
    'sap_prd',
    r.payload->>'loaded_by',
    'system',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_PRD_LOADED',
      'mapping_id', 'SAP_PRD_LOAD_ACTOR',
      'source_path', 'payload.loaded_by'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_PRD_LOADED'
    AND r.prd_id IS NOT NULL
    AND r.payload->>'loaded_by' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_PRD_HIERARCHY'::TEXT,
    'sap_load',
    'configuration',
    r.prd_id,
    'sap_prd_hierarchy_code',
    r.payload->>'hierarchy_code',
    'string',
    'sap_prd',
    r.payload->>'loaded_by',
    'system',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_PRD_LOADED',
      'mapping_id', 'SAP_PRD_HIERARCHY',
      'source_path', 'payload.hierarchy_code'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_PRD_LOADED'
    AND r.prd_id IS NOT NULL
    AND r.payload->>'hierarchy_code' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 5. CON_VERIFIED → 1 Evidence row
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'CON_VERIFIED'::TEXT,
    'verification',
    'configuration',
    r.con_id,
    'con_verification_status',
    'VERIFIED',
    'string',
    'verification_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'CON_VERIFIED',
      'mapping_id', 'CON_VERIFIED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'CON_VERIFIED'
    AND r.con_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 6. SAP_CON_TESTED → 2 Evidence rows
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_CON_TEST_RESULT'::TEXT,
    'testing',
    'configuration',
    r.con_id,
    'sap_con_test_result',
    COALESCE(r.payload->>'test_result', 'PASS'),
    'string',
    'sap_con',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_CON_TESTED',
      'mapping_id', 'SAP_CON_TEST_RESULT',
      'source_path', 'payload.test_result'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_CON_TESTED'
    AND r.con_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SAP_CON_TEST_ENV'::TEXT,
    'testing',
    'configuration',
    r.con_id,
    'sap_con_test_environment',
    r.payload->>'test_environment',
    'string',
    'sap_con',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SAP_CON_TESTED',
      'mapping_id', 'SAP_CON_TEST_ENV',
      'source_path', 'payload.test_environment'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SAP_CON_TESTED'
    AND r.con_id IS NOT NULL
    AND r.payload->>'test_environment' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 7. MATERIAL_CREATED → 1 Evidence row
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'MATERIAL_CREATED'::TEXT,
    'material',
    'material',
    r.material_id,
    'material_status',
    'CREATED',
    'string',
    'material_lifecycle',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'MATERIAL_CREATED',
      'mapping_id', 'MATERIAL_CREATED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'MATERIAL_CREATED'
    AND r.material_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 8. MATERIAL_ACTIVATED → 2 Evidence rows
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'MATERIAL_ACTIVATION_STATUS'::TEXT,
    'material',
    'material',
    r.material_id,
    'material_activation_status',
    COALESCE(r.payload->>'material_status', 'ACTIVE'),
    'string',
    'material_lifecycle',
    r.payload->>'status_changed_by',
    'actor',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'MATERIAL_ACTIVATED',
      'mapping_id', 'MATERIAL_ACTIVATION_STATUS',
      'source_path', 'payload.material_status'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'MATERIAL_ACTIVATED'
    AND r.material_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'MATERIAL_ACTIVATION_ACTOR'::TEXT,
    'material',
    'material',
    r.material_id,
    'material_activated_by',
    r.payload->>'status_changed_by',
    'string',
    'material_lifecycle',
    r.payload->>'status_changed_by',
    'actor',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'MATERIAL_ACTIVATED',
      'mapping_id', 'MATERIAL_ACTIVATION_ACTOR',
      'source_path', 'payload.status_changed_by'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'MATERIAL_ACTIVATED'
    AND r.material_id IS NOT NULL
    AND r.payload->>'status_changed_by' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 9. SKU_MINTED → 1 Evidence row
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SKU_MINTED'::TEXT,
    'activation',
    'sku',
    r.sku_id,
    'sku_status',
    'MINTED',
    'string',
    'sku_lifecycle',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SKU_MINTED',
      'mapping_id', 'SKU_MINTED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SKU_MINTED'
    AND r.sku_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 10. SKU_ACTIVATED → 1 Evidence row
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SKU_ACTIVATED'::TEXT,
    'activation',
    'sku',
    r.sku_id,
    'sku_activation_status',
    'ACTIVATED',
    'string',
    'sku_lifecycle',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SKU_ACTIVATED',
      'mapping_id', 'SKU_ACTIVATED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SKU_ACTIVATED'
    AND r.sku_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 11. TECHNICAL_REVIEW → 1-2 Evidence rows (VALID ZERO for missing review reason, FIXED: Added subject_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'TECHNICAL_REVIEW_RESULT'::TEXT,
    'technical_gate',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'technical_review_result',
    COALESCE(r.payload->>'review_result', 'PASS'),
    'string',
    'technical_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'TECHNICAL_REVIEW',
      'mapping_id', 'TECHNICAL_REVIEW_RESULT',
      'source_path', 'payload.review_result'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'TECHNICAL_REVIEW'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- TECHNICAL_REVIEW_REASON: Only if review_result = NEGATIVE and reason present (SKU-013)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'TECHNICAL_REVIEW_REASON'::TEXT,
    'technical_gate',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'technical_review_reason',
    r.payload->>'review_reason',
    'text',
    'technical_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'TECHNICAL_REVIEW',
      'mapping_id', 'TECHNICAL_REVIEW_REASON',
      'source_path', 'payload.review_reason',
      'note', 'VALID ZERO - only if review_result = NEGATIVE'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'TECHNICAL_REVIEW'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
    AND (r.payload->>'review_result' = 'NEGATIVE' OR r.payload->>'review_result' ILIKE '%REJECT%')
    AND r.payload->>'review_reason' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 12. PRICING_DETERMINED → 2 Evidence rows
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'PRICING_VALUE'::TEXT,
    'pricing',
    'sku',
    r.sku_id,
    'pricing_value_usd',
    r.payload->>'determined_price_usd',
    'string',
    'pricing_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'PRICING_DETERMINED',
      'mapping_id', 'PRICING_VALUE',
      'source_path', 'payload.determined_price_usd'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'PRICING_DETERMINED'
    AND r.sku_id IS NOT NULL
    AND r.payload->>'determined_price_usd' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'PRICING_STATUS'::TEXT,
    'pricing',
    'sku',
    r.sku_id,
    'pricing_status',
    'DETERMINED',
    'string',
    'pricing_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'PRICING_DETERMINED',
      'mapping_id', 'PRICING_STATUS',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'PRICING_DETERMINED'
    AND r.sku_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 13. PRICING_UPLOADED → 1 Evidence row (FIXED: Added subject_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'PRICING_UPLOAD_STATUS'::TEXT,
    'pricing',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'pricing_upload_status',
    'UPLOADED',
    'string',
    'pricing_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'PRICING_UPLOADED',
      'mapping_id', 'PRICING_UPLOAD_STATUS',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'PRICING_UPLOADED'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 14. PRICING_CONFIRMED → 1 Evidence row
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'PRICING_CONFIRMED'::TEXT,
    'pricing',
    'sku',
    r.sku_id,
    'pricing_confirmed',
    'CONFIRMED',
    'string',
    'pricing_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'PRICING_CONFIRMED',
      'mapping_id', 'PRICING_CONFIRMED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'PRICING_CONFIRMED'
    AND r.sku_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 15. PRICING_PUBLISHED → 1 Evidence row (FIXED: Added subject_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'PRICING_PUBLISHED'::TEXT,
    'pricing',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'pricing_publication_status',
    'PUBLISHED',
    'string',
    'pricing_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'PRICING_PUBLISHED',
      'mapping_id', 'PRICING_PUBLISHED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'PRICING_PUBLISHED'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 16. FINAL_PRICING_APPROVAL → 2 Evidence rows
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'FINAL_PRICING_APPROVAL'::TEXT,
    'gates',
    'launch',
    r.launch_id,
    'final_pricing_approval_status',
    'APPROVED',
    'string',
    'approval_gate',
    r.payload->>'approval_authority',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'FINAL_PRICING_APPROVAL',
      'mapping_id', 'FINAL_PRICING_APPROVAL',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'FINAL_PRICING_APPROVAL'
    AND r.launch_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'FINAL_PRICING_AUTH'::TEXT,
    'gates',
    'launch',
    r.launch_id,
    'final_pricing_approval_authority',
    r.payload->>'approval_authority',
    'string',
    'approval_gate',
    r.payload->>'approval_authority',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'FINAL_PRICING_APPROVAL',
      'mapping_id', 'FINAL_PRICING_AUTH',
      'source_path', 'payload.approval_authority'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'FINAL_PRICING_APPROVAL'
    AND r.launch_id IS NOT NULL
    AND r.payload->>'approval_authority' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 17. ZUPDM_APPROVED → 1 Evidence row (FIXED: Added subject_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'ZUPDM_APPROVED'::TEXT,
    'supply_chain',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'zupdm_approval_status',
    'APPROVED',
    'string',
    'supply_chain_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'ZUPDM_APPROVED',
      'mapping_id', 'ZUPDM_APPROVED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'ZUPDM_APPROVED'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 18. FULLY_APPROVED → 1 Evidence row
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'FULLY_APPROVED'::TEXT,
    'gates',
    'launch',
    r.launch_id,
    'all_gates_cleared',
    'APPROVED',
    'string',
    'composite_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'FULLY_APPROVED',
      'mapping_id', 'FULLY_APPROVED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'FULLY_APPROVED'
    AND r.launch_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 19. GO_LIVE_APPROVAL_REQUESTED → 1 Evidence row
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'GO_LIVE_APPROVAL_REQUESTED'::TEXT,
    'gates',
    'launch',
    r.launch_id,
    'go_live_approval_requested',
    'REQUESTED',
    'string',
    'approval_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'GO_LIVE_APPROVAL_REQUESTED',
      'mapping_id', 'GO_LIVE_APPROVAL_REQUESTED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'GO_LIVE_APPROVAL_REQUESTED'
    AND r.launch_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 20. GO_LIVE_APPROVED → 2 Evidence rows (FIXED: Added subject_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'GO_LIVE_APPROVED'::TEXT,
    'gates',
    'launch',
    r.launch_id,
    'go_live_approval_status',
    'APPROVED',
    'string',
    'approval_gate',
    r.payload->>'approval_authority',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'GO_LIVE_APPROVED',
      'mapping_id', 'GO_LIVE_APPROVED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'GO_LIVE_APPROVED'
    AND r.launch_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'GO_LIVE_AUTH'::TEXT,
    'gates',
    'launch',
    r.launch_id,
    'go_live_approval_authority',
    r.payload->>'approval_authority',
    'string',
    'approval_gate',
    r.payload->>'approval_authority',
    'approver',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'GO_LIVE_APPROVED',
      'mapping_id', 'GO_LIVE_AUTH',
      'source_path', 'payload.approval_authority'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'GO_LIVE_APPROVED'
    AND r.launch_id IS NOT NULL
    AND r.payload->>'approval_authority' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 21. SUPPLY_CHAIN_NOTIFIED → 1 Evidence row (FIXED: Added subject_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'SUPPLY_CHAIN_NOTIFIED'::TEXT,
    'supply_chain',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'supply_chain_notification_status',
    'NOTIFIED',
    'string',
    'supply_chain_gate',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'SUPPLY_CHAIN_NOTIFIED',
      'mapping_id', 'SUPPLY_CHAIN_NOTIFIED',
      'source_path', 'constant'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'SUPPLY_CHAIN_NOTIFIED'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 22. OVERNIGHT_PUSH → 2 Evidence rows (FIXED: Added subject_id NOT NULL check)
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'OVERNIGHT_PUSH_STATUS'::TEXT,
    'data_push',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'overnight_push_status',
    COALESCE(r.payload->>'push_event_type', 'EXECUTED'),
    'string',
    'data_push',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'OVERNIGHT_PUSH',
      'mapping_id', 'OVERNIGHT_PUSH_STATUS',
      'source_path', 'payload.push_event_type'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'OVERNIGHT_PUSH'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'OVERNIGHT_PUSH_DATE'::TEXT,
    'data_push',
    'configuration',
    COALESCE(r.con_id, r.prd_id),
    'overnight_push_run_date',
    r.payload->>'push_run_date',
    'string',
    'data_push',
    r.payload->>'process_step',
    'process',
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'OVERNIGHT_PUSH',
      'mapping_id', 'OVERNIGHT_PUSH_DATE',
      'source_path', 'payload.push_run_date'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'OVERNIGHT_PUSH'
    AND COALESCE(r.con_id, r.prd_id) IS NOT NULL
    AND r.payload->>'push_run_date' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- 23. CHANGE_REQUESTED → 4 Evidence rows (CORRECTED: Split into 4 distinct mappings)
  -- Mapping 1: CHANGE_TYPE
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'CHANGE_TYPE'::TEXT,
    'change_management',
    'launch',
    r.launch_id,
    'change_type',
    r.payload->>'change_type',
    'string',
    'product_intent',
    r.actor_id,
    r.actor_role,
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'CHANGE_REQUESTED',
      'mapping_id', 'CHANGE_TYPE',
      'source_path', 'payload.change_type'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'CHANGE_REQUESTED'
    AND r.launch_id IS NOT NULL
    AND r.payload->>'change_type' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- Mapping 2: CHANGE_REASON
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'CHANGE_REASON'::TEXT,
    'change_management',
    'launch',
    r.launch_id,
    'change_reason',
    r.payload->>'change_reason',
    'text',
    'product_intent',
    r.actor_id,
    r.actor_role,
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'CHANGE_REQUESTED',
      'mapping_id', 'CHANGE_REASON',
      'source_path', 'payload.change_reason'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'CHANGE_REQUESTED'
    AND r.launch_id IS NOT NULL
    AND r.payload->>'change_reason' IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- Mapping 3: CHANGE_REQUESTED_BY
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'CHANGE_REQUESTED_BY'::TEXT,
    'change_management',
    'launch',
    r.launch_id,
    'change_requested_by',
    r.actor_id,
    'string',
    'product_intent',
    r.actor_id,
    r.actor_role,
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'CHANGE_REQUESTED',
      'mapping_id', 'CHANGE_REQUESTED_BY',
      'source_path', 'actor_id'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'CHANGE_REQUESTED'
    AND r.launch_id IS NOT NULL
    AND r.actor_id IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- Mapping 4: CHANGE_REQUESTER_ROLE
  INSERT INTO runtime.evidence (
    raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
    property_name, asserted_value, value_type, source_system, source_actor_id,
    source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage, created_at
  )
  SELECT
    r.raw_event_id,
    'CHANGE_REQUESTER_ROLE'::TEXT,
    'change_management',
    'launch',
    r.launch_id,
    'change_requester_role',
    r.actor_role,
    'string',
    'product_intent',
    r.actor_id,
    r.actor_role,
    r.occurred_at,
    r.recorded_at,
    r.arrival_at,
    jsonb_build_object(
      'raw_event_id', r.raw_event_id::TEXT,
      'event_type', 'CHANGE_REQUESTED',
      'mapping_id', 'CHANGE_REQUESTER_ROLE',
      'source_path', 'actor_role'
    ),
    CURRENT_TIMESTAMP
  FROM raw.raw_event r
  WHERE r.event_type = 'CHANGE_REQUESTED'
    AND r.launch_id IS NOT NULL
    AND r.actor_role IS NOT NULL
  ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
  -- Count results
  SELECT COUNT(*) INTO v_evidence_after FROM runtime.evidence;
  RAISE NOTICE '================================================================';
  RAISE NOTICE 'Evidence before transformation: %', v_evidence_before;
  RAISE NOTICE 'Evidence after transformation: %', v_evidence_after;
  RAISE NOTICE 'Evidence rows inserted: %', (v_evidence_after - v_evidence_before);
  RAISE NOTICE '================================================================';
  RAISE NOTICE '✓ RAW → EVIDENCE TRANSFORMATION COMPLETE';
  RAISE NOTICE '================================================================';
  -- Return summary
  RETURN QUERY SELECT
    'Raw → Evidence transformation complete'::TEXT,
    v_raw_count,
    v_evidence_before,
    v_evidence_after,
    (v_evidence_after - v_evidence_before);
END;
$$ LANGUAGE plpgsql;
-- Execute the transformation
SELECT * FROM runtime.process_raw_to_evidence();
