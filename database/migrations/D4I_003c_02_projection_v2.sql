-- ============================================================================
-- D4I_003c step 3B -- runtime.evidence_projection_v2()
-- ONE STATEMENT. Deliberately.
-- ============================================================================
-- v2 IS v1 PLUS ONE COLUMN. Nothing else.
--
--   _v1 is NOT touched. It stays the frozen D4I_003 reproducibility artifact,
--   so D4I_003b can be re-run at any time to prove the semantic contract
--   still holds against a function that has not changed. Provenance is
--   additive; it is not a revision of what D4I_003 verified.
--
--   Every branch keeps its subject expression, property name, asserted value,
--   value type, source system, actor, three timestamps, lineage object, WHERE
--   guard and COALESCE fallback exactly as deployed. The only edit to each of
--   the 22 branches is one appended column.
--
-- HOW PROVENANCE IS DECIDED
--   18 branches emit 'OBSERVED' as a constant. That is not an assumption:
--   13 are direct extractions guarded on source presence, and 5 are event
--   occurrence mappings where the event happening IS the asserted fact
--   (MATERIAL_CREATED -> CREATED, SKU_MINTED -> MINTED, SKU_ACTIVATED ->
--   ACTIVATED, PRICING_DETERMINED -> DETERMINED, PRICING_CONFIRMED ->
--   CONFIRMED). A constant does not imply DEFAULTED.
--
--   4 branches decide per row, because their value expression is a COALESCE
--   and the fallback fires on some rows and not others:
--
--       PRODUCT_INTENT_CLASS     intent_class                 0 obs / 13 def
--       SAP_CON_LOAD_STATUS      con_status                   4 obs /  9 def
--       SAP_PRD_LOAD_STATUS      prd_status                   0 obs /  9 def
--       TECHNICAL_REVIEW_RESULT  technical_approval_status    1 obs /  8 def
--
--   The test is `payload ? key AND payload->>key IS NOT NULL`, which is the
--   exact condition under which the COALESCE does NOT fall back. A key that
--   is present but JSON null asserts no value, so it counts as DEFAULTED.
--
--   Provenance is never inferred from simulator_classification. Step 1 proved
--   the two dimensions vary independently: all 36 marked rows are OBSERVED
--   and all 39 DEFAULTED rows are unmarked.
--
-- WHAT THIS FUNCTION STILL DOES NOT DO
--   It writes nothing -- STABLE, RETURNS TABLE. It adds no mapping and no
--   approval-chain event. It does not endorse the four defaults; it makes
--   them visible, which is the entire point.
--
-- Expected: 143 rows, 104 OBSERVED, 39 DEFAULTED, 0 DERIVED, 0 NULL.
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

CREATE OR REPLACE FUNCTION runtime.evidence_projection_v2()
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
AS $projection$

-- ---------------------------------------------------------------------------
-- CHANGE_REQUESTED -> launch
-- ---------------------------------------------------------------------------
-- The requesting actor and their role. source_actor_id carries the same value
-- as the asserted change_requested_by: the person who raised the change is
-- both the fact and its source.
SELECT r.raw_event_id, 'CHANGE_REQUESTED_BY'::text, 'change_management'::varchar,
       'launch'::varchar, r.launch_id::varchar, 'change_requested_by'::varchar,
       r.payload->>'actor_id', 'string'::varchar,
       'product_intent'::varchar, (r.payload->>'actor_id')::varchar,
       'product_manager'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'CHANGE_REQUESTED_BY',
                          'source_path', 'payload.actor_id'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CHANGE_REQUESTED'
  AND r.launch_id IS NOT NULL
  AND r.payload->>'actor_id' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'CHANGE_REQUESTER_ROLE'::text, 'change_management'::varchar,
       'launch'::varchar, r.launch_id::varchar, 'change_requester_role'::varchar,
       r.payload->>'actor_role', 'string'::varchar,
       'product_intent'::varchar, (r.payload->>'actor_id')::varchar,
       'product_manager'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'CHANGE_REQUESTER_ROLE',
                          'source_path', 'payload.actor_role'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CHANGE_REQUESTED'
  AND r.launch_id IS NOT NULL
  AND r.payload->>'actor_role' IS NOT NULL

-- ---------------------------------------------------------------------------
-- PRODUCT_INTENT_CREATED -> launch
-- ---------------------------------------------------------------------------
UNION ALL
SELECT r.raw_event_id, 'PRODUCT_INTENT_CLASS'::text, 'product_intent'::varchar,
       'launch'::varchar, r.launch_id::varchar, 'intent_classification'::varchar,
       COALESCE(r.payload->>'intent_class', 'market_expansion'),
       'string'::varchar,
       'product_intent'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'PRODUCT_INTENT_CLASS',
                          'source_path', 'payload.intent_class'),
       CASE WHEN r.payload ? 'intent_class'
                 AND r.payload->>'intent_class' IS NOT NULL
            THEN 'OBSERVED'::varchar
            ELSE 'DEFAULTED'::varchar END
FROM raw.raw_event r
WHERE r.event_type = 'PRODUCT_INTENT_CREATED'
  AND r.launch_id IS NOT NULL

-- ---------------------------------------------------------------------------
-- SAP_CON_LOADED -> configuration (r.con_id)
-- ---------------------------------------------------------------------------
-- Three properties from one event. con_status yields ACTIVE or SUCCESS -- two
-- values across the corpus, so this is an extraction and not a constant.
UNION ALL
SELECT r.raw_event_id, 'SAP_CON_LOAD_STATUS'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'con_id')::varchar,
       'sap_con_load_status'::varchar,
       COALESCE(r.payload->>'con_status', 'SUCCESS'), 'string'::varchar,
       'sap_con'::varchar, (r.payload->>'loaded_by')::varchar, 'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'SAP_CON_LOAD_STATUS',
                          'source_path', 'payload.con_status'),
       CASE WHEN r.payload ? 'con_status'
                 AND r.payload->>'con_status' IS NOT NULL
            THEN 'OBSERVED'::varchar
            ELSE 'DEFAULTED'::varchar END
FROM raw.raw_event r
WHERE r.event_type = 'SAP_CON_LOADED'
  AND r.payload->>'con_id' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SAP_CON_HIERARCHY'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'con_id')::varchar,
       'sap_con_hierarchy_code'::varchar,
       r.payload->>'hierarchy_code', 'string'::varchar,
       'sap_con'::varchar, (r.payload->>'loaded_by')::varchar, 'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'SAP_CON_HIERARCHY',
                          'source_path', 'payload.hierarchy_code'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SAP_CON_LOADED'
  AND r.payload->>'con_id' IS NOT NULL
  AND r.payload->>'hierarchy_code' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SAP_CON_LOAD_ACTOR'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'con_id')::varchar,
       'sap_con_load_actor'::varchar,
       r.payload->>'loaded_by', 'string'::varchar,
       'sap_con'::varchar, (r.payload->>'loaded_by')::varchar, 'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'SAP_CON_LOAD_ACTOR',
                          'source_path', 'payload.loaded_by'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SAP_CON_LOADED'
  AND r.payload->>'con_id' IS NOT NULL
  AND r.payload->>'loaded_by' IS NOT NULL

-- ---------------------------------------------------------------------------
-- SAP_PRD_LOADED -> configuration (payload->>'prd_id')
-- ---------------------------------------------------------------------------
-- MEASURED, NOT ASSUMED. r.prd_id is NULL on every one of these events; the
-- identifier lives in the payload. Every repository file reads the column and
-- therefore produces nothing.
UNION ALL
SELECT r.raw_event_id, 'SAP_PRD_LOAD_STATUS'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'prd_id')::varchar,
       'sap_prd_load_status'::varchar,
       COALESCE(r.payload->>'prd_status', 'SUCCESS'), 'string'::varchar,
       'sap_prd'::varchar, NULL::varchar, 'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'SAP_PRD_LOAD_STATUS',
                          'source_path', 'payload.prd_status'),
       CASE WHEN r.payload ? 'prd_status'
                 AND r.payload->>'prd_status' IS NOT NULL
            THEN 'OBSERVED'::varchar
            ELSE 'DEFAULTED'::varchar END
FROM raw.raw_event r
WHERE r.event_type = 'SAP_PRD_LOADED'
  AND r.payload->>'prd_id' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SAP_PRD_HIERARCHY'::text, 'sap_load'::varchar,
       'configuration'::varchar, (r.payload->>'prd_id')::varchar,
       'sap_prd_hierarchy_code'::varchar,
       r.payload->>'hierarchy_code', 'string'::varchar,
       'sap_prd'::varchar, NULL::varchar, 'system'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'SAP_PRD_HIERARCHY',
                          'source_path', 'payload.hierarchy_code'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SAP_PRD_LOADED'
  AND r.payload->>'prd_id' IS NOT NULL
  AND r.payload->>'hierarchy_code' IS NOT NULL

-- ---------------------------------------------------------------------------
-- MATERIAL_CREATED -> material
-- ---------------------------------------------------------------------------
-- Constant: the event's occurrence is the fact. It proves a material was
-- created, not the state it was created in.
UNION ALL
SELECT r.raw_event_id, 'MATERIAL_CREATED'::text, 'material'::varchar,
       'material'::varchar, r.material_id::varchar, 'material_status'::varchar,
       'CREATED', 'string'::varchar,
       'material_lifecycle'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'MATERIAL_CREATED',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'MATERIAL_CREATED'
  AND r.material_id IS NOT NULL

-- ---------------------------------------------------------------------------
-- SKU lifecycle -> sku
-- ---------------------------------------------------------------------------
UNION ALL
SELECT r.raw_event_id, 'SKU_MINTED'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'sku_status'::varchar,
       'MINTED', 'string'::varchar,
       'sku_lifecycle'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'SKU_MINTED',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SKU_MINTED' AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'SKU_ACTIVATED'::text, 'activation'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'sku_activation_status'::varchar,
       'ACTIVATED', 'string'::varchar,
       'sku_lifecycle'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'SKU_ACTIVATED',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'SKU_ACTIVATED' AND r.sku_id IS NOT NULL

-- ---------------------------------------------------------------------------
-- TECHNICAL_REVIEW -> sku
-- ---------------------------------------------------------------------------
-- RECONSTRUCTED FROM DEPLOYED METADATA. No repository artifact produces this.
-- Deployed lineage names payload.technical_approval_status, and the corpus
-- yields PASS and REJECTED -- so it is read, not asserted. Every file in the
-- working tree instead reads payload.review_result against subject
-- 'configuration', which is why they would produce nothing here.
UNION ALL
SELECT r.raw_event_id, 'TECHNICAL_REVIEW_RESULT'::text, 'technical_gate'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'technical_review_result'::varchar,
       COALESCE(r.payload->>'technical_approval_status', 'PASS'),
       'string'::varchar,
       'technical_gate'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'TECHNICAL_REVIEW_RESULT',
                          'source_path', 'payload.technical_approval_status'),
       CASE WHEN r.payload ? 'technical_approval_status'
                 AND r.payload->>'technical_approval_status' IS NOT NULL
            THEN 'OBSERVED'::varchar
            ELSE 'DEFAULTED'::varchar END
FROM raw.raw_event r
WHERE r.event_type = 'TECHNICAL_REVIEW'
  AND r.sku_id IS NOT NULL

-- ---------------------------------------------------------------------------
-- PRICING_DETERMINED / PRICING_CONFIRMED -> sku
-- ---------------------------------------------------------------------------
-- These two event types are DISTINCT business facts on disjoint SKU
-- populations, and neither is FINAL_PRICING_APPROVAL. See D4I_004.
UNION ALL
SELECT r.raw_event_id, 'PRICING_STATUS'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_status'::varchar,
       'DETERMINED', 'string'::varchar,
       'pricing_gate'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'PRICING_STATUS',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_DETERMINED' AND r.sku_id IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_VALUE'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_value_usd'::varchar,
       r.payload->>'determined_price_usd', 'string'::varchar,
       'pricing_gate'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'PRICING_VALUE',
                          'source_path', 'payload.determined_price_usd'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_DETERMINED'
  AND r.sku_id IS NOT NULL
  AND r.payload->>'determined_price_usd' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRICING_CONFIRMED'::text, 'pricing'::varchar,
       'sku'::varchar, r.sku_id::varchar, 'pricing_confirmed'::varchar,
       'CONFIRMED', 'string'::varchar,
       'pricing_gate'::varchar, (r.payload->>'process_step')::varchar,
       'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'PRICING_CONFIRMED',
                          'source_path', 'constant'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRICING_CONFIRMED' AND r.sku_id IS NOT NULL

-- ---------------------------------------------------------------------------
-- PRODUCT_DEFINED -> product (payload->>'product_id')
-- ---------------------------------------------------------------------------
-- The payload carries product_id both at the top level and nested; the
-- deployed subject matches the top-level key, and that is what is used.
-- product_name, however, is only nested -- the nesting is not uniform even
-- within one event type.
UNION ALL
SELECT r.raw_event_id, 'PRODUCT_DEF_LAUNCH'::text, 'product_definition'::varchar,
       'product'::varchar, (r.payload->>'product_id')::varchar,
       'launch_reference'::varchar,
       r.payload->>'launch_id', 'string'::varchar,
       'product_definition'::varchar, NULL::varchar, 'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'PRODUCT_DEF_LAUNCH',
                          'source_path', 'payload.launch_id'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRODUCT_DEFINED'
  AND r.payload->>'product_id' IS NOT NULL
  AND r.payload->>'launch_id' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'PRODUCT_DEF_NAME'::text, 'product_definition'::varchar,
       'product'::varchar, (r.payload->>'product_id')::varchar,
       'product_name'::varchar,
       r.payload->'payload'->>'product_name', 'string'::varchar,
       'product_definition'::varchar, NULL::varchar, 'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'PRODUCT_DEF_NAME',
                          'source_path', 'payload.payload.product_name'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'PRODUCT_DEFINED'
  AND r.payload->>'product_id' IS NOT NULL
  AND r.payload->'payload'->>'product_name' IS NOT NULL

-- ---------------------------------------------------------------------------
-- CONFIGURATION_REQUESTED -> configuration_request (NESTED payload)
-- ---------------------------------------------------------------------------
-- The loader stored the whole generator record, so the business fields sit at
-- payload->'payload'. Every repository mapping that reads the top level finds
-- nothing. This is the shape that actually produced the deployed 34 rows, and
-- it is the shape the entire vertical slice depends on.
--
-- CONF_REQ_SEGMENT yields 6 rows against 7 requests: CONFIG-REQ-2026-007 omits
-- segment entirely, which is what makes its identity UNREPORTED and its
-- governed decision CANNOT_DECIDE. The absence is the business fact.
UNION ALL
SELECT r.raw_event_id, 'CONF_REQ_PRODUCT'::text, 'configuration_request'::varchar,
       'configuration_request'::varchar,
       (r.payload->'payload'->>'configuration_request_id')::varchar,
       'product_reference'::varchar,
       r.payload->'payload'->>'product_id', 'string'::varchar,
       'configuration_governance'::varchar, NULL::varchar, 'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'CONF_REQ_PRODUCT',
                          'source_path', 'payload.payload.product_id'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'configuration_request_id' IS NOT NULL
  AND r.payload->'payload'->>'product_id' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'CONF_REQ_GEO'::text, 'configuration_request'::varchar,
       'configuration_request'::varchar,
       (r.payload->'payload'->>'configuration_request_id')::varchar,
       'geography'::varchar,
       r.payload->'payload'->>'geo', 'string'::varchar,
       'configuration_governance'::varchar, NULL::varchar, 'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'CONF_REQ_GEO',
                          'source_path', 'payload.payload.geo'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'configuration_request_id' IS NOT NULL
  AND r.payload->'payload'->>'geo' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'CONF_REQ_TERM'::text, 'configuration_request'::varchar,
       'configuration_request'::varchar,
       (r.payload->'payload'->>'configuration_request_id')::varchar,
       'term_months'::varchar,
       r.payload->'payload'->>'term', 'integer'::varchar,
       'configuration_governance'::varchar, NULL::varchar, 'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'CONF_REQ_TERM',
                          'source_path', 'payload.payload.term'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'configuration_request_id' IS NOT NULL
  AND r.payload->'payload'->>'term' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'CONF_REQ_SEGMENT'::text, 'configuration_request'::varchar,
       'configuration_request'::varchar,
       (r.payload->'payload'->>'configuration_request_id')::varchar,
       'customer_segment'::varchar,
       r.payload->'payload'->>'segment', 'string'::varchar,
       'configuration_governance'::varchar, NULL::varchar, 'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'CONF_REQ_SEGMENT',
                          'source_path', 'payload.payload.segment'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'configuration_request_id' IS NOT NULL
  AND r.payload->'payload'->>'segment' IS NOT NULL

UNION ALL
SELECT r.raw_event_id, 'CONF_REQ_LAUNCH'::text, 'configuration_request'::varchar,
       'configuration_request'::varchar,
       (r.payload->'payload'->>'configuration_request_id')::varchar,
       'launch_reference'::varchar,
       r.payload->'payload'->>'launch_id', 'string'::varchar,
       'configuration_governance'::varchar, NULL::varchar, 'process'::varchar,
       r.occurred_at, r.recorded_at, r.arrival_at,
       jsonb_build_object('raw_event_id', r.raw_event_id::text,
                          'event_type', r.event_type,
                          'mapping_id', 'CONF_REQ_LAUNCH',
                          'source_path', 'payload.payload.launch_id'),
       'OBSERVED'::varchar
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'configuration_request_id' IS NOT NULL
  AND r.payload->'payload'->>'launch_id' IS NOT NULL

$projection$;
