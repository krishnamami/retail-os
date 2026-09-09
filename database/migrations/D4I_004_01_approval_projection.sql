-- ============================================================================
-- D4I_004 step 1 -- runtime.approval_projection_v1()
-- ONE STATEMENT. Deliberately.
-- ============================================================================
-- The 28 approval-chain and lifecycle mappings the deployed contract never
-- had. Pure: RETURNS TABLE, STABLE, writes nothing. Applying it is a separate
-- act (D4I_004_02), the same separation D4I_003 established.
--
-- WHY A NEW FUNCTION RATHER THAN A v3
--   evidence_projection_v1 is the frozen D4I_003 artifact and v2 is v1 plus
--   provenance. Both stay callable and unchanged, so every verifier written so
--   far keeps working and D4I_003's verdict keeps being about functions that
--   still exist. This function returns the same 16 columns, so the union of
--   v2 and this one is the whole evidence contract.
--
-- WHY NOT raw_to_evidence_FINAL.sql
--   Its 21 dormant INSERTs guard on payload.hierarchy_approvals, an array this
--   corpus does not contain -- HIERARCHY_APPROVAL carries FLAT hierarchy_code
--   and approval_authority. That one wrong guard is why those INSERTs produced
--   nothing, and why re-running that file would still produce nothing.
--
-- SUBJECTS, MEASURED NOT ASSUMED
--   sku events carry r.sku_id (column populated on all of them).
--   CON_VERIFIED and SAP_CON_TESTED carry payload.con_id -- the con_id COLUMN
--   is null on every row, exactly as SAP_CON_* already was.
--   SAP_PRD_PROMOTED carries payload.prd_id.
--   HIERARCHY_APPROVAL carries r.launch_id.
--
-- PROVENANCE: EVERY ROW IS OBSERVED, AND THAT IS EARNED
--   8 mappings assert the occurrence of their event with a constant --
--   APPROVED, UPLOADED, PUBLISHED, YES, REQUESTED, NOTIFIED, VERIFIED. Under
--   the locked rule a constant naming the event that happened is OBSERVED, not
--   DEFAULTED.
--   The other 20 read a payload key and are GUARDED on it being non-null. No
--   COALESCE appears anywhere in this file. Where a key is absent the mapping
--   emits no row at all, which the fold reads as UNREPORTED -- a different
--   state from DEFAULTED, and the honest one.
--
--   That matters most where the corpus is sparse:
--       HIERARCHY_APPROVAL   hierarchy_code / approval_authority   4 of 13
--       MATERIAL_ACTIVATED   material_status / status_changed_by   2 of 11
--       OVERNIGHT_PUSH       push_event_type / push_run_date       2 of 11
--   Those 9, 9 and 9 silent events stay silent. D4I_004 adds no DEFAULTED row.
--
-- ONE PLACE THIS EXTENDS THE BRIEF, FLAGGED FOR REVERSAL
--   CON_VERIFIED was specified as "map source facts only", but its payload
--   carries no fact beyond con_id, which is its subject. Its only assertable
--   content is that verification happened. It is mapped as an occurrence
--   constant, exactly as FULLY_APPROVED and ZUPDM_APPROVED are -- those carry
--   no status key either. Delete the CON_VERIFICATION_STATUS branch to drop
--   it; that removes 9 rows and nothing else.
--
-- NOT MAPPED, DELIBERATELY
--   FINAL_PRICING_APPROVAL is NOT mapped to pricing_confirmed. They are
--   different events over disjoint populations -- PRICING_CONFIRMED covers
--   SKU-001..003, FINAL_PRICING_APPROVAL covers SKU-004..012 -- and merging
--   them would fabricate a business fact. No mapping reads approval_authority
--   for FINAL_PRICING_APPROVAL; that key does not exist on it.
--
-- EXPECTED: 114 rows across 28 mappings, all OBSERVED.
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

CREATE OR REPLACE FUNCTION runtime.approval_projection_v1()
RETURNS TABLE (
    raw_event_id             uuid,
    mapping_id               text,
    evidence_type            varchar,
    subject_type             varchar,
    subject_id               varchar,
    property_name            varchar,
    asserted_value           text,
    value_type               varchar,
    source_system            varchar,
    source_actor_id          varchar,
    source_actor_role        varchar,
    occurred_at              timestamptz,
    recorded_at              timestamptz,
    arrival_at               timestamptz,
    evidence_lineage         jsonb,
    value_provenance         varchar
)
LANGUAGE sql
STABLE
AS $approval$

SELECT r.raw_event_id, 'FINAL_PRICING_APPROVAL_STATUS'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'final_pricing_approval_status'::varchar,
       'APPROVED', 'string'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'FINAL_PRICING_APPROVAL',
                          'mapping_id', 'FINAL_PRICING_APPROVAL_STATUS',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'FINAL_PRICING_APPROVAL'
  AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_UPLOAD_STATUS'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_upload_status'::varchar,
       'UPLOADED', 'string'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'PRICING_UPLOADED',
                          'mapping_id', 'PRICING_UPLOAD_STATUS',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_UPLOADED'
  AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_UPLOADED_PRICE'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_uploaded_price_usd'::varchar,
       r.payload->>'final_price_usd', 'string'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'PRICING_UPLOADED',
                          'mapping_id', 'PRICING_UPLOADED_PRICE',
                          'source_path', 'payload.final_price_usd'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_UPLOADED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'final_price_usd' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_PUBLICATION_STATUS'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_publication_status'::varchar,
       'PUBLISHED', 'string'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'PRICING_PUBLISHED',
                          'mapping_id', 'PRICING_PUBLICATION_STATUS',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_PUBLISHED'
  AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_LIST_PRICE'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_list_price'::varchar,
       r.payload->>'list_price', 'string'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'PRICING_PUBLISHED',
                          'mapping_id', 'PRICING_LIST_PRICE',
                          'source_path', 'payload.list_price'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_PUBLISHED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'list_price' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_CURRENCY'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_currency'::varchar,
       r.payload->>'currency', 'string'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'PRICING_PUBLISHED',
                          'mapping_id', 'PRICING_CURRENCY',
                          'source_path', 'payload.currency'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_PUBLISHED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'currency' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_PUBLISHED_BY'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_published_by'::varchar,
       r.payload->>'published_by', 'string'::varchar,
       'pricing_gate'::varchar, (r.payload->>'published_by')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'PRICING_PUBLISHED',
                          'mapping_id', 'PRICING_PUBLISHED_BY',
                          'source_path', 'payload.published_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_PUBLISHED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'published_by' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'OVERNIGHT_PUSH_STATUS'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'overnight_push_status'::varchar,
       r.payload->>'push_event_type', 'string'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'OVERNIGHT_PUSH',
                          'mapping_id', 'OVERNIGHT_PUSH_STATUS',
                          'source_path', 'payload.push_event_type'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'OVERNIGHT_PUSH'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'push_event_type' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'OVERNIGHT_PUSH_RUN_DATE'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'overnight_push_run_date'::varchar,
       r.payload->>'push_run_date', 'timestamp'::varchar,
       'pricing_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'OVERNIGHT_PUSH',
                          'mapping_id', 'OVERNIGHT_PUSH_RUN_DATE',
                          'source_path', 'payload.push_run_date'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'OVERNIGHT_PUSH'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'push_run_date' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'ZUPDM_APPROVAL_STATUS'::text, 'approval_gate'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'zupdm_approval_status'::varchar,
       'APPROVED', 'string'::varchar,
       'zupdm'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'ZUPDM_APPROVED',
                          'mapping_id', 'ZUPDM_APPROVAL_STATUS',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'ZUPDM_APPROVED'
  AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'ALL_GATES_CLEARED'::text, 'approval_gate'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'all_gates_cleared'::varchar,
       'YES', 'string'::varchar,
       'approval_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'FULLY_APPROVED',
                          'mapping_id', 'ALL_GATES_CLEARED',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'FULLY_APPROVED'
  AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'GO_LIVE_APPROVAL_REQUESTED'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'go_live_approval_requested'::varchar,
       'REQUESTED', 'string'::varchar,
       'go_live_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'GO_LIVE_APPROVAL_REQUESTED',
                          'mapping_id', 'GO_LIVE_APPROVAL_REQUESTED',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'GO_LIVE_APPROVAL_REQUESTED'
  AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'GO_LIVE_APPROVAL_LEVEL'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'go_live_approval_level'::varchar,
       r.payload->>'approval_level', 'string'::varchar,
       'go_live_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'GO_LIVE_APPROVAL_REQUESTED',
                          'mapping_id', 'GO_LIVE_APPROVAL_LEVEL',
                          'source_path', 'payload.approval_level'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'GO_LIVE_APPROVAL_REQUESTED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'approval_level' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'GO_LIVE_REQUESTED_BY'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'go_live_requested_by'::varchar,
       r.payload->>'requested_by', 'string'::varchar,
       'go_live_gate'::varchar, (r.payload->>'requested_by')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'GO_LIVE_APPROVAL_REQUESTED',
                          'mapping_id', 'GO_LIVE_REQUESTED_BY',
                          'source_path', 'payload.requested_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'GO_LIVE_APPROVAL_REQUESTED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'requested_by' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'GO_LIVE_APPROVAL_STATUS'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'go_live_approval_status'::varchar,
       r.payload->>'approval_status', 'string'::varchar,
       'go_live_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'GO_LIVE_APPROVED',
                          'mapping_id', 'GO_LIVE_APPROVAL_STATUS',
                          'source_path', 'payload.approval_status'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'GO_LIVE_APPROVED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'approval_status' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'GO_LIVE_APPROVED_BY'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'go_live_approved_by'::varchar,
       r.payload->>'approved_by', 'string'::varchar,
       'go_live_gate'::varchar, (r.payload->>'approved_by')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'GO_LIVE_APPROVED',
                          'mapping_id', 'GO_LIVE_APPROVED_BY',
                          'source_path', 'payload.approved_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'GO_LIVE_APPROVED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'approved_by' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SUPPLY_CHAIN_NOTIFICATION_STATUS'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'supply_chain_notification_status'::varchar,
       'NOTIFIED', 'string'::varchar,
       'supply_chain'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'SUPPLY_CHAIN_NOTIFIED',
                          'mapping_id', 'SUPPLY_CHAIN_NOTIFICATION_STATUS',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SUPPLY_CHAIN_NOTIFIED'
  AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SUPPLY_CHAIN_NOTIFICATION_TYPE'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'supply_chain_notification_type'::varchar,
       r.payload->>'notification_type', 'string'::varchar,
       'supply_chain'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'SUPPLY_CHAIN_NOTIFIED',
                          'mapping_id', 'SUPPLY_CHAIN_NOTIFICATION_TYPE',
                          'source_path', 'payload.notification_type'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SUPPLY_CHAIN_NOTIFIED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'notification_type' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SUPPLY_CHAIN_NOTIFIED_BY'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'supply_chain_notified_by'::varchar,
       r.payload->>'notified_by', 'string'::varchar,
       'supply_chain'::varchar, (r.payload->>'notified_by')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'SUPPLY_CHAIN_NOTIFIED',
                          'mapping_id', 'SUPPLY_CHAIN_NOTIFIED_BY',
                          'source_path', 'payload.notified_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SUPPLY_CHAIN_NOTIFIED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'notified_by' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'MATERIAL_ACTIVATION_STATUS'::text, 'material'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'material_activation_status'::varchar,
       r.payload->>'material_status', 'string'::varchar,
       'material_lifecycle'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'MATERIAL_ACTIVATED',
                          'mapping_id', 'MATERIAL_ACTIVATION_STATUS',
                          'source_path', 'payload.material_status'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'MATERIAL_ACTIVATED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'material_status' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'MATERIAL_ACTIVATED_BY'::text, 'material'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'material_activated_by'::varchar,
       r.payload->>'status_changed_by', 'string'::varchar,
       'material_lifecycle'::varchar, (r.payload->>'status_changed_by')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'MATERIAL_ACTIVATED',
                          'mapping_id', 'MATERIAL_ACTIVATED_BY',
                          'source_path', 'payload.status_changed_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'MATERIAL_ACTIVATED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'status_changed_by' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'CON_VERIFICATION_STATUS'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'con_id')::varchar, 'con_verification_status'::varchar,
       'VERIFIED', 'string'::varchar,
       'sap_con'::varchar, NULL::varchar,
       'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'CON_VERIFIED',
                          'mapping_id', 'CON_VERIFICATION_STATUS',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CON_VERIFIED'
  AND (r.payload->>'con_id') IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SAP_CON_TEST_STATUS'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'con_id')::varchar, 'sap_con_test_status'::varchar,
       r.payload->>'test_status', 'string'::varchar,
       'sap_con'::varchar, NULL::varchar,
       'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'SAP_CON_TESTED',
                          'mapping_id', 'SAP_CON_TEST_STATUS',
                          'source_path', 'payload.test_status'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SAP_CON_TESTED'
  AND (r.payload->>'con_id') IS NOT NULL
  AND r.payload->>'test_status' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SAP_CON_TEST_ACTOR'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'con_id')::varchar, 'sap_con_test_actor'::varchar,
       r.payload->>'tested_by', 'string'::varchar,
       'sap_con'::varchar, (r.payload->>'tested_by')::varchar,
       'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'SAP_CON_TESTED',
                          'mapping_id', 'SAP_CON_TEST_ACTOR',
                          'source_path', 'payload.tested_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SAP_CON_TESTED'
  AND (r.payload->>'con_id') IS NOT NULL
  AND r.payload->>'tested_by' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SAP_PRD_PROMOTION_HIERARCHY'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'prd_id')::varchar, 'sap_prd_promotion_hierarchy_code'::varchar,
       r.payload->>'hierarchy_code', 'string'::varchar,
       'sap_prd'::varchar, NULL::varchar,
       'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'SAP_PRD_PROMOTED',
                          'mapping_id', 'SAP_PRD_PROMOTION_HIERARCHY',
                          'source_path', 'payload.hierarchy_code'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SAP_PRD_PROMOTED'
  AND (r.payload->>'prd_id') IS NOT NULL
  AND r.payload->>'hierarchy_code' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SAP_PRD_PROMOTION_ACTOR'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'prd_id')::varchar, 'sap_prd_promotion_actor'::varchar,
       r.payload->>'promoted_by', 'string'::varchar,
       'sap_prd'::varchar, (r.payload->>'promoted_by')::varchar,
       'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'SAP_PRD_PROMOTED',
                          'mapping_id', 'SAP_PRD_PROMOTION_ACTOR',
                          'source_path', 'payload.promoted_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SAP_PRD_PROMOTED'
  AND (r.payload->>'prd_id') IS NOT NULL
  AND r.payload->>'promoted_by' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'HIERARCHY_APPROVAL_CODE'::text, 'hierarchy_governance'::varchar,
       'launch'::varchar, r.launch_id::varchar, 'hierarchy_approval_code'::varchar,
       r.payload->>'hierarchy_code', 'string'::varchar,
       'hierarchy_gate'::varchar, NULL::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'HIERARCHY_APPROVAL',
                          'mapping_id', 'HIERARCHY_APPROVAL_CODE',
                          'source_path', 'payload.hierarchy_code'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'HIERARCHY_APPROVAL'
  AND r.launch_id IS NOT NULL
  AND r.payload->>'hierarchy_code' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'HIERARCHY_APPROVAL_AUTHORITY'::text, 'hierarchy_governance'::varchar,
       'launch'::varchar, r.launch_id::varchar, 'hierarchy_approval_authority'::varchar,
       r.payload->>'approval_authority', 'string'::varchar,
       'hierarchy_gate'::varchar, (r.payload->>'approval_authority')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', 'HIERARCHY_APPROVAL',
                          'mapping_id', 'HIERARCHY_APPROVAL_AUTHORITY',
                          'source_path', 'payload.approval_authority'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'HIERARCHY_APPROVAL'
  AND r.launch_id IS NOT NULL
  AND r.payload->>'approval_authority' IS NOT NULL

$approval$;
