-- =====================================================================
-- Evidence Layer Validation Queries
-- =====================================================================
-- Purpose: Read-only verification suite for raw.raw_event → runtime.evidence transformation
-- Status: POST-EXECUTION VALIDATION (run after transformation completes)
-- Timestamp: 2026-09-06
-- =====================================================================

-- =====================================================================
-- 1. BASELINE RECORD COUNTS
-- =====================================================================

-- Record count in raw.raw_event (should be 169)
SELECT
  'RAW_EVENT_COUNT' AS validation_check,
  COUNT(*) AS record_count,
  COUNT(*) = 169 AS status_ok
FROM raw.raw_event;

-- Record count in runtime.evidence (should be > 0, typically 300-400 based on 1:N mapping)
SELECT
  'EVIDENCE_COUNT' AS validation_check,
  COUNT(*) AS record_count,
  COUNT(*) > 0 AS status_ok
FROM runtime.evidence;

-- Record count in runtime.assertion (should be 0 - Evidence only, no assertions yet)
SELECT
  'ASSERTION_COUNT_SHOULD_BE_ZERO' AS validation_check,
  COUNT(*) AS record_count,
  COUNT(*) = 0 AS status_ok
FROM runtime.assertion;

-- Record count in state.fold_state_snapshot (should be 0 - Fold layer not started)
SELECT
  'FOLD_COUNT_SHOULD_BE_ZERO' AS validation_check,
  COUNT(*) AS record_count,
  COUNT(*) = 0 AS status_ok
FROM state.fold_state_snapshot;

-- =====================================================================
-- 2. MAPPING_ID INVENTORY & COVERAGE
-- =====================================================================

-- All Evidence rows must have non-empty mapping_id
SELECT
  'MAPPING_ID_NOT_NULL_AND_NOT_EMPTY' AS validation_check,
  COUNT(*) AS record_count,
  COUNT(*) FILTER (WHERE mapping_id IS NULL OR mapping_id = '') AS null_or_empty_count,
  COUNT(*) FILTER (WHERE mapping_id IS NULL OR mapping_id = '') = 0 AS status_ok
FROM runtime.evidence;

-- Count Evidence rows per mapping_id (should show all 38 approved mappings used)
SELECT
  'MAPPING_ID_USAGE_SUMMARY' AS validation_check,
  mapping_id,
  COUNT(*) AS evidence_row_count
FROM runtime.evidence
GROUP BY mapping_id
ORDER BY evidence_row_count DESC;

-- Distinct mapping_ids in use (should be 38)
SELECT
  'DISTINCT_MAPPING_ID_COUNT' AS validation_check,
  COUNT(DISTINCT mapping_id) AS distinct_mapping_count,
  COUNT(DISTINCT mapping_id) = 38 AS status_ok
FROM runtime.evidence;

-- Mapping_ids NOT present in Evidence (indicates event type not in corpus or mapping not used)
WITH approved_mappings AS (
  SELECT mapping_id FROM (VALUES
    ('PRODUCT_INTENT_ID'),
    ('PRODUCT_INTENT_CLASS'),
    ('HIERARCHY_APPROVAL_CON_CODE'),
    ('HIERARCHY_APPROVAL_CON_AUTH'),
    ('HIERARCHY_APPROVAL_PRD_CODE'),
    ('HIERARCHY_APPROVAL_PRD_AUTH'),
    ('SAP_CON_LOAD_STATUS'),
    ('SAP_CON_LOAD_ACTOR'),
    ('SAP_CON_HIERARCHY'),
    ('SAP_PRD_LOAD_STATUS'),
    ('SAP_PRD_LOAD_ACTOR'),
    ('SAP_PRD_HIERARCHY'),
    ('CON_VERIFIED'),
    ('SAP_CON_TEST_RESULT'),
    ('SAP_CON_TEST_ENV'),
    ('MATERIAL_CREATED'),
    ('MATERIAL_ACTIVATION_STATUS'),
    ('MATERIAL_ACTIVATION_ACTOR'),
    ('SKU_MINTED'),
    ('SKU_ACTIVATED'),
    ('TECHNICAL_REVIEW_RESULT'),
    ('TECHNICAL_REVIEW_REASON'),
    ('PRICING_VALUE'),
    ('PRICING_STATUS'),
    ('PRICING_UPLOAD_STATUS'),
    ('PRICING_CONFIRMED'),
    ('PRICING_PUBLISHED'),
    ('FINAL_PRICING_APPROVAL'),
    ('FINAL_PRICING_AUTH'),
    ('ZUPDM_APPROVED'),
    ('FULLY_APPROVED'),
    ('GO_LIVE_APPROVAL_REQUESTED'),
    ('GO_LIVE_APPROVED'),
    ('GO_LIVE_AUTH'),
    ('SUPPLY_CHAIN_NOTIFIED'),
    ('OVERNIGHT_PUSH_STATUS'),
    ('OVERNIGHT_PUSH_DATE'),
    ('CHANGE_TYPE'),
    ('CHANGE_REASON'),
    ('CHANGE_REQUESTED_BY'),
    ('CHANGE_REQUESTER_ROLE')
  ) AS t(mapping_id)
),
used_mappings AS (
  SELECT DISTINCT mapping_id FROM runtime.evidence
)
SELECT
  'APPROVED_MAPPINGS_NOT_USED' AS validation_check,
  am.mapping_id,
  COALESCE(um.mapping_id, 'NOT_USED') AS status
FROM approved_mappings am
LEFT JOIN used_mappings um ON am.mapping_id = um.mapping_id
WHERE um.mapping_id IS NULL
ORDER BY am.mapping_id;

-- =====================================================================
-- 3. SUBJECT IDENTITY VALIDATION
-- =====================================================================

-- Subject type distribution (should show launch, configuration, sku, material)
SELECT
  'SUBJECT_TYPE_DISTRIBUTION' AS validation_check,
  subject_type,
  COUNT(*) AS evidence_row_count
FROM runtime.evidence
GROUP BY subject_type
ORDER BY evidence_row_count DESC;

-- Subject_id null check (all should be non-empty)
SELECT
  'SUBJECT_ID_NOT_NULL_AND_NOT_EMPTY' AS validation_check,
  COUNT(*) AS record_count,
  COUNT(*) FILTER (WHERE subject_id IS NULL OR subject_id = '') AS null_or_empty_count,
  COUNT(*) FILTER (WHERE subject_id IS NULL OR subject_id = '') = 0 AS status_ok
FROM runtime.evidence;

-- =====================================================================
-- 4. LINEAGE INTEGRITY (raw_event_id FK)
-- =====================================================================

-- All Evidence rows must reference valid raw_event_id
SELECT
  'RAW_EVENT_ID_FK_INTEGRITY' AS validation_check,
  COUNT(e.raw_event_id) AS evidence_count,
  COUNT(r.raw_event_id) AS raw_event_count,
  COUNT(e.raw_event_id) - COUNT(r.raw_event_id) AS orphaned_count,
  COUNT(e.raw_event_id) - COUNT(r.raw_event_id) = 0 AS status_ok
FROM runtime.evidence e
LEFT JOIN raw.raw_event r ON e.raw_event_id = r.raw_event_id;

-- Detailed orphan detection (if any)
SELECT
  'ORPHANED_EVIDENCE_ROWS' AS validation_check,
  e.raw_event_id,
  e.mapping_id,
  e.subject_type,
  e.subject_id,
  COUNT(*) AS count
FROM runtime.evidence e
LEFT JOIN raw.raw_event r ON e.raw_event_id = r.raw_event_id
WHERE r.raw_event_id IS NULL
GROUP BY e.raw_event_id, e.mapping_id, e.subject_type, e.subject_id;

-- =====================================================================
-- 5. IDEMPOTENCY KEY VALIDATION (raw_event_id, mapping_id)
-- =====================================================================

-- Check for duplicate (raw_event_id, mapping_id) combinations (should be 0)
SELECT
  'IDEMPOTENCY_KEY_DUPLICATES' AS validation_check,
  COUNT(*) AS duplicate_count,
  COUNT(*) = 0 AS status_ok
FROM (
  SELECT raw_event_id, mapping_id, COUNT(*) AS cnt
  FROM runtime.evidence
  GROUP BY raw_event_id, mapping_id
  HAVING COUNT(*) > 1
) AS duplicates;

-- Distribution of Evidence rows per raw_event_id (shows 1:N cardinality)
SELECT
  'EVIDENCE_CARDINALITY_DISTRIBUTION' AS validation_check,
  evidence_per_raw_count,
  COUNT(*) AS raw_event_count
FROM (
  SELECT raw_event_id, COUNT(*) AS evidence_per_raw_count
  FROM runtime.evidence
  GROUP BY raw_event_id
) AS cardinality
GROUP BY evidence_per_raw_count
ORDER BY evidence_per_raw_count;

-- =====================================================================
-- 6. TIMESTAMP PRESERVATION VALIDATION
-- =====================================================================

-- All Evidence rows must have occurred_at, recorded_at, arrival_at
SELECT
  'TIMESTAMP_NOT_NULL' AS validation_check,
  COUNT(*) AS record_count,
  COUNT(*) FILTER (WHERE occurred_at IS NULL) AS null_occurred_at,
  COUNT(*) FILTER (WHERE recorded_at IS NULL) AS null_recorded_at,
  COUNT(*) FILTER (WHERE arrival_at IS NULL) AS null_arrival_at,
  COUNT(*) FILTER (WHERE occurred_at IS NOT NULL AND recorded_at IS NOT NULL AND arrival_at IS NOT NULL) AS all_timestamps_present
FROM runtime.evidence;

-- Arrival_at delta analysis (shows delayed/out-of-order arrivals preserved)
SELECT
  'ARRIVAL_AT_DELTA_ANALYSIS' AS validation_check,
  CASE
    WHEN arrival_at = occurred_at THEN 'on_time'
    WHEN arrival_at > occurred_at THEN 'delayed'
    WHEN arrival_at < occurred_at THEN 'out_of_order'
    ELSE 'unknown'
  END AS arrival_pattern,
  COUNT(*) AS evidence_count
FROM runtime.evidence
GROUP BY arrival_pattern
ORDER BY arrival_pattern;

-- =====================================================================
-- 7. ACTOR ATTRIBUTION VALIDATION
-- =====================================================================

-- Actor field distribution (should show process_step, approval_authority, loaded_by, status_changed_by, etc.)
SELECT
  'ACTOR_FIELD_DISTRIBUTION' AS validation_check,
  mapping_id,
  COUNT(DISTINCT source_actor_id) AS distinct_actor_count,
  COUNT(*) FILTER (WHERE source_actor_id IS NULL) AS null_actor_count,
  COUNT(*) AS total_rows
FROM runtime.evidence
GROUP BY mapping_id
ORDER BY total_rows DESC;

-- =====================================================================
-- 8. VALUE FIDELITY VALIDATION
-- =====================================================================

-- Asserted value distribution (check for REJECTED, NEGATIVE, PENDING preservation)
SELECT
  'ASSERTED_VALUE_SAMPLE' AS validation_check,
  mapping_id,
  property_name,
  asserted_value,
  COUNT(*) AS value_count
FROM runtime.evidence
WHERE asserted_value IN ('REJECTED', 'NEGATIVE', 'PENDING', 'FAILURE')
GROUP BY mapping_id, property_name, asserted_value
ORDER BY value_count DESC;

-- NULL asserted_value check (some rows may have NULL if value is entirely in value_json)
SELECT
  'NULL_ASSERTED_VALUE_BY_MAPPING' AS validation_check,
  mapping_id,
  COUNT(*) AS null_value_count,
  COUNT(*) FILTER (WHERE value_json IS NOT NULL) AS has_value_json
FROM runtime.evidence
WHERE asserted_value IS NULL
GROUP BY mapping_id;

-- =====================================================================
-- 9. ABSENCE & VALID ZERO HANDLING
-- =====================================================================

-- TECHNICAL_REVIEW_REASON should only exist when review_result = NEGATIVE (VALID ZERO)
-- Check that no TECHNICAL_REVIEW_REASON exists without matching NEGATIVE result
SELECT
  'TECHNICAL_REVIEW_REASON_VALID_ZERO_CHECK' AS validation_check,
  COUNT(*) AS technical_review_reason_rows,
  COUNT(*) FILTER (
    WHERE EXISTS (
      SELECT 1 FROM runtime.evidence e2
      WHERE e2.raw_event_id = e.raw_event_id
      AND e2.mapping_id = 'TECHNICAL_REVIEW_RESULT'
      AND e2.asserted_value = 'NEGATIVE'
    )
  ) AS rows_with_negative_result,
  COUNT(*) = COUNT(*) FILTER (
    WHERE EXISTS (
      SELECT 1 FROM runtime.evidence e2
      WHERE e2.raw_event_id = e.raw_event_id
      AND e2.mapping_id = 'TECHNICAL_REVIEW_RESULT'
      AND e2.asserted_value = 'NEGATIVE'
    )
  ) AS status_ok
FROM runtime.evidence e
WHERE e.mapping_id = 'TECHNICAL_REVIEW_REASON';

-- =====================================================================
-- 10. CONTRADICTION PRESERVATION (SKU-003, SKU-013)
-- =====================================================================

-- SKU-003: Both CON and PRD hierarchies should coexist for LAUNCH-001
SELECT
  'SKU003_HIERARCHY_CONTRADICTION_CHECK' AS validation_check,
  COUNT(DISTINCT CASE WHEN mapping_id = 'HIERARCHY_APPROVAL_CON_CODE' THEN 1 END) AS con_code_present,
  COUNT(DISTINCT CASE WHEN mapping_id = 'HIERARCHY_APPROVAL_PRD_CODE' THEN 1 END) AS prd_code_present,
  (COUNT(DISTINCT CASE WHEN mapping_id = 'HIERARCHY_APPROVAL_CON_CODE' THEN 1 END) > 0
   AND COUNT(DISTINCT CASE WHEN mapping_id = 'HIERARCHY_APPROVAL_PRD_CODE' THEN 1 END) > 0) AS both_present
FROM runtime.evidence
WHERE subject_id = 'LAUNCH-001'
AND mapping_id IN ('HIERARCHY_APPROVAL_CON_CODE', 'HIERARCHY_APPROVAL_PRD_CODE');

-- SKU-013: Technical review NEGATIVE with reason should be preserved
SELECT
  'SKU013_NEGATIVE_REVIEW_CHECK' AS validation_check,
  raw_event_id,
  COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_RESULT' AND asserted_value = 'NEGATIVE') AS negative_result_count,
  COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_REASON') AS reason_count,
  COUNT(*) FILTER (WHERE mapping_id = 'TECHNICAL_REVIEW_REASON' AND asserted_value LIKE '%conflicts%') AS reason_detail_count
FROM runtime.evidence
WHERE mapping_id IN ('TECHNICAL_REVIEW_RESULT', 'TECHNICAL_REVIEW_REASON')
GROUP BY raw_event_id
ORDER BY negative_result_count DESC;

-- =====================================================================
-- 11. CHANGE_REQUESTED SPECIAL CASE (only 1 raw event)
-- =====================================================================

-- CHANGE_REQUESTED should produce 4 Evidence rows (type, reason, by, role)
SELECT
  'CHANGE_REQUESTED_MAPPING_COUNT' AS validation_check,
  raw_event_id,
  COUNT(*) AS evidence_row_count,
  COUNT(DISTINCT mapping_id) AS distinct_mapping_count,
  STRING_AGG(DISTINCT mapping_id, ', ' ORDER BY mapping_id) AS mapping_ids_present
FROM runtime.evidence
WHERE mapping_id IN ('CHANGE_TYPE', 'CHANGE_REASON', 'CHANGE_REQUESTED_BY', 'CHANGE_REQUESTER_ROLE')
GROUP BY raw_event_id;

-- =====================================================================
-- 12. LINEAGE METADATA VALIDATION
-- =====================================================================

-- Evidence lineage structure (should have extraction_path at minimum)
SELECT
  'EVIDENCE_LINEAGE_STRUCTURE' AS validation_check,
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE evidence_lineage IS NOT NULL) AS rows_with_lineage,
  COUNT(*) FILTER (WHERE evidence_lineage::text LIKE '%extraction_path%') AS rows_with_extraction_path,
  COUNT(*) FILTER (WHERE evidence_lineage::text LIKE '%source_field%') AS rows_with_source_field
FROM runtime.evidence;

-- =====================================================================
-- 13. SOURCE PROVENANCE VALIDATION
-- =====================================================================

-- Source system distribution (should show product_intent, approval_workflow, sap_con, sap_prd, etc.)
SELECT
  'SOURCE_PROVENANCE_DISTRIBUTION' AS validation_check,
  source_system,
  COUNT(*) AS evidence_count
FROM runtime.evidence
GROUP BY source_system
ORDER BY evidence_count DESC;

-- Mapping_id to source_system consistency check
SELECT
  'MAPPING_ID_SOURCE_SYSTEM_CONSISTENCY' AS validation_check,
  mapping_id,
  source_system,
  COUNT(*) AS evidence_count
FROM runtime.evidence
GROUP BY mapping_id, source_system
ORDER BY mapping_id, source_system;

-- =====================================================================
-- 14. PROPERTY_NAME COVERAGE
-- =====================================================================

-- Distinct property_names generated (should match mapping definitions)
SELECT
  'PROPERTY_NAME_DISTRIBUTION' AS validation_check,
  property_name,
  COUNT(*) AS evidence_count
FROM runtime.evidence
GROUP BY property_name
ORDER BY evidence_count DESC;

-- =====================================================================
-- 15. SUMMARY STATISTICS
-- =====================================================================

SELECT
  'TRANSFORMATION_SUMMARY' AS validation_check,
  'Raw Events' AS metric,
  COUNT(*) AS value
FROM raw.raw_event
UNION ALL
SELECT
  'TRANSFORMATION_SUMMARY',
  'Evidence Rows',
  COUNT(*)
FROM runtime.evidence
UNION ALL
SELECT
  'TRANSFORMATION_SUMMARY',
  'Distinct Subjects',
  COUNT(DISTINCT (subject_type, subject_id))
FROM runtime.evidence
UNION ALL
SELECT
  'TRANSFORMATION_SUMMARY',
  'Distinct Mappings Used',
  COUNT(DISTINCT mapping_id)
FROM runtime.evidence
UNION ALL
SELECT
  'TRANSFORMATION_SUMMARY',
  'Raw Events → Evidence (avg ratio)',
  ROUND(CAST(COUNT(*) AS numeric) / (SELECT COUNT(*) FROM raw.raw_event), 2)
FROM runtime.evidence
ORDER BY metric;

-- =====================================================================
-- END OF VALIDATION QUERIES
-- =====================================================================
-- Run sequentially; each section stands alone and can be used independently
-- for troubleshooting specific aspects of the Evidence transformation.
