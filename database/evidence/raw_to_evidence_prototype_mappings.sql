-- =====================================================================
-- Raw → Evidence Transformation for PRODUCT_DEFINED and CONFIGURATION_REQUESTED
-- STEP 5E.3C Implementation (Corrected Extraction Paths)
-- =====================================================================
-- Purpose: Add 36 Evidence rows from 8 prototype Raw events
-- Current Evidence: 107 rows
-- New Evidence: 36 rows
-- Expected Total: 143 rows
-- Identity: (raw_event_id, mapping_id)
-- Idempotency: ON CONFLICT (raw_event_id, mapping_id) DO NOTHING
-- Execution: NOT EXECUTED (design/specification only)
-- =====================================================================
-- CORRECTION: Live Raw contract verified
-- PRODUCT_DEFINED: payload fields at top level
-- CONFIGURATION_REQUESTED: payload fields nested under payload->'payload'
-- =====================================================================

-- =====================================================================
-- PRODUCT_DEFINED MAPPINGS (1 Raw → 2 Evidence rows)
-- =====================================================================

-- ---------------------------------------------------------------------------
-- D4I_003c -- value_provenance added to all seven mappings, always 'OBSERVED'
-- ---------------------------------------------------------------------------
-- runtime.evidence.value_provenance is now NOT NULL with no DEFAULT, so every
-- INSERT here must state how its value came to exist or be refused.
--
-- All seven are OBSERVED, and that is proved rather than assumed: each INSERT
-- already carries a WHERE guard requiring its source field to be non-null
-- (product_name, launch_id, product_id, geo, term, segment,
-- configuration_request_id), so a row exists here only when the source
-- asserted the value. There is no COALESCE anywhere in this file -- a missing
-- source produces no evidence row, which the fold reads as UNREPORTED. That
-- is a different state from DEFAULTED and the distinction is deliberate.
--
-- Provenance is NOT derived from simulator_classification. That column keeps
-- reading r.payload->>'simulator_classification' exactly as before. The two
-- dimensions were measured as independent: all 36 marked rows are OBSERVED
-- and all 39 DEFAULTED rows in the corpus are unmarked, so inferring one from
-- the other would have produced 36/107 instead of the verified 104/39.
--
-- The authoritative specification for provenance is
-- runtime.evidence_projection_v2(), not this file.
-- ---------------------------------------------------------------------------

-- Mapping 1: PRODUCT_DEF_NAME
-- Extracts: product_name property
INSERT INTO runtime.evidence (
  raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
  property_name, asserted_value, value_type, source_system, source_actor_id,
  source_actor_role, occurred_at, recorded_at, arrival_at,
  simulator_classification, evidence_lineage, created_at,
  value_provenance
)
SELECT
  r.raw_event_id,
  'PRODUCT_DEF_NAME'::TEXT,
  'product_definition',
  'product',
  r.payload->>'product_id',
  'product_name',
  r.payload->'payload'->>'product_name',
  'string',
  r.source_system,
  NULL,
  'process',
  r.occurred_at,
  r.recorded_at,
  r.arrival_at,
  r.payload->>'simulator_classification',
  jsonb_build_object(
    'raw_event_id', r.raw_event_id::TEXT,
    'event_type', 'PRODUCT_DEFINED',
    'mapping_id', 'PRODUCT_DEF_NAME',
    'source_path', 'payload.payload.product_name'
  ),
  CURRENT_TIMESTAMP,
  'OBSERVED'   -- D4I_003c: see the header note
FROM raw.raw_event r
WHERE r.event_type = 'PRODUCT_DEFINED'
  AND r.payload->'payload'->>'product_name' IS NOT NULL
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;

-- Mapping 2: PRODUCT_DEF_LAUNCH
-- Extracts: launch_reference property (relationship to Launch)
INSERT INTO runtime.evidence (
  raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
  property_name, asserted_value, value_type, source_system, source_actor_id,
  source_actor_role, occurred_at, recorded_at, arrival_at,
  simulator_classification, evidence_lineage, created_at,
  value_provenance
)
SELECT
  r.raw_event_id,
  'PRODUCT_DEF_LAUNCH'::TEXT,
  'product_definition',
  'product',
  r.payload->>'product_id',
  'launch_reference',
  r.payload->>'launch_id',
  'string',
  r.source_system,
  NULL,
  'process',
  r.occurred_at,
  r.recorded_at,
  r.arrival_at,
  r.payload->>'simulator_classification',
  jsonb_build_object(
    'raw_event_id', r.raw_event_id::TEXT,
    'event_type', 'PRODUCT_DEFINED',
    'mapping_id', 'PRODUCT_DEF_LAUNCH',
    'source_path', 'payload.launch_id'
  ),
  CURRENT_TIMESTAMP,
  'OBSERVED'   -- D4I_003c: see the header note
FROM raw.raw_event r
WHERE r.event_type = 'PRODUCT_DEFINED'
  AND r.payload->>'launch_id' IS NOT NULL
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;

-- =====================================================================
-- CONFIGURATION_REQUESTED MAPPINGS (6-7 Raw → 30-34 Evidence rows)
-- CORRECTED: Nested business payload at r.payload->'payload'
-- Standard records (S1, S2, S3, S5, S6a, S6b): 5 Evidence each
-- S7 (incomplete identity): 4 Evidence (no segment)
-- =====================================================================

-- Mapping 1: CONF_REQ_PRODUCT
-- Extracts: product_reference property from nested payload
INSERT INTO runtime.evidence (
  raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
  property_name, asserted_value, value_type, source_system, source_actor_id,
  source_actor_role, occurred_at, recorded_at, arrival_at,
  simulator_classification, evidence_lineage, created_at,
  value_provenance
)
SELECT
  r.raw_event_id,
  'CONF_REQ_PRODUCT'::TEXT,
  'configuration_request',
  'configuration_request',
  r.payload->'payload'->>'configuration_request_id',
  'product_reference',
  r.payload->'payload'->>'product_id',
  'string',
  r.source_system,
  NULL,
  'process',
  r.occurred_at,
  r.recorded_at,
  r.arrival_at,
  r.payload->>'simulator_classification',
  jsonb_build_object(
    'raw_event_id', r.raw_event_id::TEXT,
    'event_type', 'CONFIGURATION_REQUESTED',
    'mapping_id', 'CONF_REQ_PRODUCT',
    'source_path', 'payload.payload.product_id'
  ),
  CURRENT_TIMESTAMP,
  'OBSERVED'   -- D4I_003c: see the header note
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'product_id' IS NOT NULL
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;

-- Mapping 2: CONF_REQ_LAUNCH
-- Extracts: launch_reference property from nested payload
INSERT INTO runtime.evidence (
  raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
  property_name, asserted_value, value_type, source_system, source_actor_id,
  source_actor_role, occurred_at, recorded_at, arrival_at,
  simulator_classification, evidence_lineage, created_at,
  value_provenance
)
SELECT
  r.raw_event_id,
  'CONF_REQ_LAUNCH'::TEXT,
  'configuration_request',
  'configuration_request',
  r.payload->'payload'->>'configuration_request_id',
  'launch_reference',
  r.payload->'payload'->>'launch_id',
  'string',
  r.source_system,
  NULL,
  'process',
  r.occurred_at,
  r.recorded_at,
  r.arrival_at,
  r.payload->>'simulator_classification',
  jsonb_build_object(
    'raw_event_id', r.raw_event_id::TEXT,
    'event_type', 'CONFIGURATION_REQUESTED',
    'mapping_id', 'CONF_REQ_LAUNCH',
    'source_path', 'payload.payload.launch_id'
  ),
  CURRENT_TIMESTAMP,
  'OBSERVED'   -- D4I_003c: see the header note
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'launch_id' IS NOT NULL
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;

-- Mapping 3: CONF_REQ_GEO
-- Extracts: geography property from nested payload
INSERT INTO runtime.evidence (
  raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
  property_name, asserted_value, value_type, source_system, source_actor_id,
  source_actor_role, occurred_at, recorded_at, arrival_at,
  simulator_classification, evidence_lineage, created_at,
  value_provenance
)
SELECT
  r.raw_event_id,
  'CONF_REQ_GEO'::TEXT,
  'configuration_request',
  'configuration_request',
  r.payload->'payload'->>'configuration_request_id',
  'geography',
  r.payload->'payload'->>'geo',
  'string',
  r.source_system,
  NULL,
  'process',
  r.occurred_at,
  r.recorded_at,
  r.arrival_at,
  r.payload->>'simulator_classification',
  jsonb_build_object(
    'raw_event_id', r.raw_event_id::TEXT,
    'event_type', 'CONFIGURATION_REQUESTED',
    'mapping_id', 'CONF_REQ_GEO',
    'source_path', 'payload.payload.geo'
  ),
  CURRENT_TIMESTAMP,
  'OBSERVED'   -- D4I_003c: see the header note
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'geo' IS NOT NULL
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;

-- Mapping 4: CONF_REQ_TERM
-- Extracts: term_months property from nested payload
INSERT INTO runtime.evidence (
  raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
  property_name, asserted_value, value_type, source_system, source_actor_id,
  source_actor_role, occurred_at, recorded_at, arrival_at,
  simulator_classification, evidence_lineage, created_at,
  value_provenance
)
SELECT
  r.raw_event_id,
  'CONF_REQ_TERM'::TEXT,
  'configuration_request',
  'configuration_request',
  r.payload->'payload'->>'configuration_request_id',
  'term_months',
  (r.payload->'payload'->>'term')::TEXT,
  'integer',
  r.source_system,
  NULL,
  'process',
  r.occurred_at,
  r.recorded_at,
  r.arrival_at,
  r.payload->>'simulator_classification',
  jsonb_build_object(
    'raw_event_id', r.raw_event_id::TEXT,
    'event_type', 'CONFIGURATION_REQUESTED',
    'mapping_id', 'CONF_REQ_TERM',
    'source_path', 'payload.payload.term'
  ),
  CURRENT_TIMESTAMP,
  'OBSERVED'   -- D4I_003c: see the header note
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'term' IS NOT NULL
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;

-- Mapping 5: CONF_REQ_SEGMENT
-- Extracts: customer_segment property from nested payload
-- CRITICAL: Only if segment IS NOT NULL (S7 has segment=NULL, so no Evidence row for S7)
INSERT INTO runtime.evidence (
  raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
  property_name, asserted_value, value_type, source_system, source_actor_id,
  source_actor_role, occurred_at, recorded_at, arrival_at,
  simulator_classification, evidence_lineage, created_at,
  value_provenance
)
SELECT
  r.raw_event_id,
  'CONF_REQ_SEGMENT'::TEXT,
  'configuration_request',
  'configuration_request',
  r.payload->'payload'->>'configuration_request_id',
  'customer_segment',
  r.payload->'payload'->>'segment',
  'string',
  r.source_system,
  NULL,
  'process',
  r.occurred_at,
  r.recorded_at,
  r.arrival_at,
  r.payload->>'simulator_classification',
  jsonb_build_object(
    'raw_event_id', r.raw_event_id::TEXT,
    'event_type', 'CONFIGURATION_REQUESTED',
    'mapping_id', 'CONF_REQ_SEGMENT',
    'source_path', 'payload.payload.segment'
  ),
  CURRENT_TIMESTAMP,
  'OBSERVED'   -- D4I_003c: see the header note
FROM raw.raw_event r
WHERE r.event_type = 'CONFIGURATION_REQUESTED'
  AND r.payload->'payload'->>'segment' IS NOT NULL  -- Excludes S7 where segment=NULL
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;

-- =====================================================================
-- SUMMARY OF IMPLEMENTATION
-- =====================================================================
--
-- This SQL fragment implements the STEP 5E.3C corrected extraction paths:
--
-- PRODUCT_DEFINED (1 Raw event):
--   → 2 Evidence rows (product_name, launch_reference)
--   → mapping_ids: PRODUCT_DEF_NAME, PRODUCT_DEF_LAUNCH
--   → top-level payload access
--
-- CONFIGURATION_REQUESTED (7 Raw events):
--   S1, S2, S3, S5, S6a, S6b (6 complete): 5 Evidence rows each = 30 total
--   → mapping_ids: CONF_REQ_PRODUCT, CONF_REQ_LAUNCH, CONF_REQ_GEO, CONF_REQ_TERM, CONF_REQ_SEGMENT
--   → nested payload access: r.payload->'payload'->>'field_name'
--
--   S7 (incomplete): 4 Evidence rows (no segment)
--   → mapping_ids: CONF_REQ_PRODUCT, CONF_REQ_LAUNCH, CONF_REQ_GEO, CONF_REQ_TERM (no CONF_REQ_SEGMENT)
--
-- Total new Evidence: 2 + 30 + 4 = 36 rows
-- Total Expected Evidence after execution: 107 + 36 = 143 rows
--
-- Idempotency: ON CONFLICT (raw_event_id, mapping_id) DO NOTHING
-- Replay scenario (Run 2): All 8 records already processed → 0 new Evidence rows inserted
--
-- No schema changes required
-- No database writes (local specification only)
-- No downstream changes (Evidence → Assertion → Fold not executed)
--
-- =====================================================================
