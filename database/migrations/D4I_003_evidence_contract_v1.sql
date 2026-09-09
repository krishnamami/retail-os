-- ============================================================================
-- D4I_003 -- the deployed Raw -> Evidence contract, reconstructed and made
--            reproducible
-- ============================================================================
-- WHY THIS EXISTS
--   runtime.evidence holds 143 rows produced by FOUR separate projection runs
--   on 2026-09-06 and 2026-09-07, and no artifact in the working tree
--   reproduces them. raw_to_evidence_FINAL.sql maps TECHNICAL_REVIEW to
--   subject 'configuration' via COALESCE(con_id, prd_id) reading
--   payload.review_result; the deployed row is subject 'sku' reading
--   payload.technical_approval_status. That mapping was run once, alone, at
--   18:05:42, and never written back.
--
--   So the evidence layer -- the foundation the Fold, every governed decision
--   and the whole canonical layer rest on -- could not be rebuilt from source.
--   This file fixes that, and adds nothing.
--
-- WHAT IS AND IS NOT IN HERE
--   IN:  exactly the 22 mappings measured in the deployed database, with every
--        subject expression, value expression, source field and timestamp
--        verified against the rows they actually produced.
--   OUT: the approval-chain repair. That is D4I_004, deliberately separate, so
--        this file can be proven against data that already exists before any
--        new semantics are introduced.
--
-- THE PROJECTION IS A PURE FUNCTION
--   runtime.evidence_projection_v1() RETURNS the rows it would produce and
--   writes nothing. Applying them is a second, separate act. This is the same
--   separation the D.4G.4 compiler uses -- compile, verify the artifact, then
--   publish -- and it exists for the same reason: a projection you cannot
--   inspect before it writes is a projection you cannot verify.
--
--   It also makes the acceptance test a genuine full-column diff. An
--   INSERT ... ON CONFLICT (raw_event_id, mapping_id) DO NOTHING would report
--   zero inserts whether the reconstruction were right OR wrong about a value,
--   because the conflict key does not include the value.
--
-- SUBJECT EXPRESSIONS ARE MEASURED, NOT ASSUMED
--   Each was confirmed by comparing the deployed subject_id against every
--   candidate raw column and payload key. Three are not what any repository
--   file says:
--       SAP_PRD_*    payload->>'prd_id'                    (r.prd_id is NULL)
--       CONF_REQ_*   payload->'payload'->>'configuration_request_id'  (nested)
--       PRODUCT_DEF_* payload->>'product_id'               (top level)
--
-- ONE MAPPING IS RECONSTRUCTED FROM DEPLOYED METADATA RATHER THAN FOUND
--   TECHNICAL_REVIEW_RESULT. Everything about it here comes from the deployed
--   rows and their evidence_lineage, not from a file. It yields PASS or
--   REJECTED -- two values -- so it is an extraction, not the constant the
--   repository assumed.
--
-- OPTIONAL KEYS WITH CONSTANT FALLBACKS -- A FINDING, NOT A DESIGN CHOICE
--   Four deployed mappings read a payload key that is present on only SOME
--   events and fall back to a constant for the rest. Reproducing them means
--   reproducing that:
--
--       PRODUCT_INTENT_CLASS     'intent_class' exists on 0 of 13 events;
--                                all 13 rows say 'market_expansion'
--       SAP_CON_LOAD_STATUS      'con_status' exists on 4 of 13;
--                                4 rows say ACTIVE, 9 say the default SUCCESS
--       SAP_PRD_LOAD_STATUS      'prd_status' exists on 0 of 9;
--                                all 9 say the default SUCCESS
--       TECHNICAL_REVIEW_RESULT  'technical_approval_status' exists on 1 of 9;
--                                1 says REJECTED, 8 say the default PASS
--
--   So a substantial part of the evidence layer records ASSUMED values that no
--   source event asserted. 'SAP_CON_LOAD_STATUS = SUCCESS' on nine
--   configurations is not an observation -- it is what the projection decided
--   when the source was silent, and it is indistinguishable in
--   runtime.evidence from the four rows that were genuinely observed.
--
--   This file reproduces that behaviour exactly, because its job is
--   reproducibility, not correction. But it is recorded here because a
--   governed readiness decision reading 'technical_review_result = PASS'
--   cannot currently tell whether a review happened or whether nobody said
--   otherwise -- and that distinction is the whole point of the Fold's
--   UNREPORTED state. Correcting it is a separate, deliberate act.
--
-- STALE ARTIFACT
--   database/evidence/raw_to_evidence_FINAL.sql and database/evidence/
--   mappings.sql are HISTORICAL. They are not deleted -- they record what was
--   intended, and the difference between intent and deployment is itself worth
--   keeping -- but they are not authoritative. This function is.
--
-- APPLY IN ONE TRANSACTION. Creates a function; writes no evidence.
-- ============================================================================

CREATE OR REPLACE FUNCTION runtime.evidence_projection_v1()
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
    evidence_lineage         jsonb
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
                          'source_path', 'payload.actor_id')
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
                          'source_path', 'payload.actor_role')
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
                          'source_path', 'payload.intent_class')
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
                          'source_path', 'payload.con_status')
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
                          'source_path', 'payload.hierarchy_code')
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
                          'source_path', 'payload.loaded_by')
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
                          'source_path', 'payload.prd_status')
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
                          'source_path', 'payload.hierarchy_code')
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
                          'source_path', 'constant')
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
                          'source_path', 'constant')
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
                          'source_path', 'constant')
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
                          'source_path', 'payload.technical_approval_status')
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
                          'source_path', 'constant')
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
                          'source_path', 'payload.determined_price_usd')
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
                          'source_path', 'constant')
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
                          'source_path', 'payload.launch_id')
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
                          'source_path', 'payload.payload.product_name')
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
                          'source_path', 'payload.payload.product_id')
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
                          'source_path', 'payload.payload.geo')
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
                          'source_path', 'payload.payload.term')
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
                          'source_path', 'payload.payload.segment')
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
                          'source_path', 'payload.payload.launch_id')
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'configuration_request_id' IS NOT NULL
  AND r.payload->'payload'->>'launch_id' IS NOT NULL

$projection$;

COMMENT ON FUNCTION runtime.evidence_projection_v1 IS
  'The deployed Raw -> Evidence contract as measured from runtime.evidence on '
  '2026-09-08: 22 mappings, 143 rows. Pure -- returns rows, writes nothing. '
  'Subject expressions were verified against the rows they produced, not read '
  'from a file: SAP_PRD_* uses payload.prd_id (the column is NULL), CONF_REQ_* '
  'uses the NESTED payload.payload.configuration_request_id, and '
  'TECHNICAL_REVIEW_RESULT was reconstructed from deployed metadata because no '
  'repository artifact produces it. database/evidence/raw_to_evidence_FINAL.sql '
  'and mappings.sql are historical, not authoritative.';

-- ---------------------------------------------------------------------------
-- applying the projection -- a separate act from computing it
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION runtime.apply_evidence_projection_v1()
RETURNS integer
LANGUAGE plpgsql
AS $apply$
DECLARE
    inserted integer;
BEGIN
    INSERT INTO runtime.evidence (
        raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
        property_name, asserted_value, value_type, source_system,
        source_actor_id, source_actor_role, occurred_at, recorded_at,
        arrival_at, evidence_lineage)
    SELECT p.raw_event_id, p.mapping_id, p.evidence_type, p.subject_type,
           p.subject_id, p.property_name, p.asserted_value, p.value_type,
           p.source_system, p.source_actor_id, p.source_actor_role,
           p.occurred_at, p.recorded_at, p.arrival_at, p.evidence_lineage
    FROM   runtime.evidence_projection_v1() p
    ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
    GET DIAGNOSTICS inserted = ROW_COUNT;
    RETURN inserted;
END
$apply$;

COMMENT ON FUNCTION runtime.apply_evidence_projection_v1 IS
  'Applies runtime.evidence_projection_v1() idempotently on '
  '(raw_event_id, mapping_id). Returns rows inserted. NOTE: a zero return does '
  'NOT prove the projection is correct -- the conflict key excludes the value, '
  'so a wrong asserted_value would also insert nothing. Correctness is proven '
  'by the full-column diff in vslice_evidence_contract_verify.py.';

-- ---------------------------------------------------------------------------
-- proof: the projection reproduces the deployed distribution
-- ---------------------------------------------------------------------------
SELECT 'deployed' AS side, mapping_id, count(*) AS rows,
       count(DISTINCT subject_id) AS subjects
FROM   runtime.evidence GROUP BY 1,2
UNION ALL
SELECT 'projected', mapping_id, count(*), count(DISTINCT subject_id)
FROM   runtime.evidence_projection_v1() GROUP BY 1,2
ORDER  BY 2, 1;

SELECT (SELECT count(*) FROM runtime.evidence)                  AS deployed_rows,
       (SELECT count(*) FROM runtime.evidence_projection_v1())  AS projected_rows;
