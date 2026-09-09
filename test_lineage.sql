-- =====================================================================
-- Test Suite: Lineage Integrity Verification
-- =====================================================================
-- Purpose: Verify Evidence lineage (raw_event_id → mapping_id relationships)
-- Focus: FK integrity, NULL checks, orphan detection, identity uniqueness
-- =====================================================================

-- =====================================================================
-- TEST 1: raw_event_id Foreign Key Integrity
-- =====================================================================
SELECT
  'TEST_RAW_EVENT_FK_INTEGRITY' AS test_name,
  COUNT(DISTINCT e.raw_event_id) AS evidence_raw_event_ids,
  COUNT(DISTINCT r.raw_event_id) AS actual_raw_event_ids,
  COUNT(DISTINCT e.raw_event_id) - COUNT(DISTINCT r.raw_event_id) AS orphaned_raw_events,
  CASE WHEN COUNT(DISTINCT e.raw_event_id) - COUNT(DISTINCT r.raw_event_id) = 0
       THEN 'PASS - No Orphaned raw_event_ids' ELSE 'FAIL' END AS status
FROM runtime.evidence e
LEFT JOIN raw.raw_event r ON e.raw_event_id = r.raw_event_id;

-- =====================================================================
-- TEST 2: Raw Event ID Not NULL
-- =====================================================================
SELECT
  'TEST_RAW_EVENT_ID_NOT_NULL' AS test_name,
  COUNT(*) AS total_evidence_rows,
  COUNT(*) FILTER (WHERE raw_event_id IS NULL) AS null_count,
  CASE WHEN COUNT(*) FILTER (WHERE raw_event_id IS NULL) = 0
       THEN 'PASS - All raw_event_ids non-NULL' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 3: Mapping ID Not NULL
-- =====================================================================
SELECT
  'TEST_MAPPING_ID_NOT_NULL' AS test_name,
  COUNT(*) AS total_evidence_rows,
  COUNT(*) FILTER (WHERE mapping_id IS NULL) AS null_count,
  COUNT(*) FILTER (WHERE mapping_id = '') AS empty_count,
  CASE WHEN COUNT(*) FILTER (WHERE mapping_id IS NULL OR mapping_id = '') = 0
       THEN 'PASS - All mapping_ids non-NULL and non-empty' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 4: Mapping ID Format Validation
-- =====================================================================
SELECT
  'TEST_MAPPING_ID_FORMAT' AS test_name,
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE mapping_id ~ '^[A-Z][A-Z0-9_]*$') AS valid_format_count,
  COUNT(*) FILTER (WHERE mapping_id !~ '^[A-Z][A-Z0-9_]*$') AS invalid_format_count,
  CASE WHEN COUNT(*) FILTER (WHERE mapping_id !~ '^[A-Z][A-Z0-9_]*$') = 0
       THEN 'PASS - All mapping_ids valid format' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 5: Duplicate Identity Detection (raw_event_id, mapping_id)
-- =====================================================================
SELECT
  'TEST_NO_DUPLICATE_IDENTITIES' AS test_name,
  COUNT(DISTINCT (raw_event_id, mapping_id)) AS unique_identities,
  COUNT(*) AS total_rows,
  COUNT(*) - COUNT(DISTINCT (raw_event_id, mapping_id)) AS duplicate_rows,
  CASE WHEN COUNT(*) = COUNT(DISTINCT (raw_event_id, mapping_id))
       THEN 'PASS - No duplicate identities' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 6: Duplicate Mapping Ids Per Raw Event (shows 1:N cardinality)
-- =====================================================================
-- One raw event should produce multiple Evidence rows (one per mapping)
SELECT
  'TEST_CARDINALITY_1_TO_N' AS test_name,
  raw_event_id,
  COUNT(DISTINCT mapping_id) AS distinct_mappings,
  COUNT(*) AS evidence_rows,
  CASE WHEN COUNT(DISTINCT mapping_id) = COUNT(*) THEN 'Multiple mappings' ELSE 'Same mapping multiple rows' END AS cardinality_type
FROM runtime.evidence
GROUP BY raw_event_id
HAVING COUNT(DISTINCT mapping_id) > 1
LIMIT 10;

-- =====================================================================
-- TEST 7: Orphaned Evidence Rows (raw_event_id references non-existent raw event)
-- =====================================================================
SELECT
  'TEST_NO_ORPHANED_EVIDENCE' AS test_name,
  COUNT(*) AS orphaned_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS - No orphans' ELSE 'FAIL' END AS status
FROM runtime.evidence e
WHERE NOT EXISTS (
  SELECT 1 FROM raw.raw_event r
  WHERE r.raw_event_id = e.raw_event_id
);

-- Detail of orphaned rows (if any)
SELECT
  'ORPHANED_EVIDENCE_DETAIL' AS test_name,
  e.raw_event_id,
  e.mapping_id,
  e.subject_type,
  e.subject_id,
  e.property_name,
  'RAW EVENT NOT FOUND' AS issue
FROM runtime.evidence e
WHERE NOT EXISTS (
  SELECT 1 FROM raw.raw_event r
  WHERE r.raw_event_id = e.raw_event_id
);

-- =====================================================================
-- TEST 8: Approved Mapping IDs In Use
-- =====================================================================
-- Verify all mapping_ids in Evidence are from the approved list (38 total)
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
)
SELECT
  'TEST_ONLY_APPROVED_MAPPINGS_USED' AS test_name,
  COUNT(DISTINCT e.mapping_id) AS used_mappings,
  COUNT(*) AS approved_mappings,
  COUNT(DISTINCT CASE WHEN am.mapping_id IS NOT NULL THEN e.mapping_id END) AS approved_and_used,
  COUNT(DISTINCT CASE WHEN am.mapping_id IS NULL THEN e.mapping_id END) AS unapproved_mappings,
  CASE WHEN COUNT(DISTINCT CASE WHEN am.mapping_id IS NULL THEN e.mapping_id END) = 0
       THEN 'PASS - Only approved mappings used' ELSE 'FAIL' END AS status
FROM runtime.evidence e
LEFT JOIN approved_mappings am ON e.mapping_id = am.mapping_id
CROSS JOIN (SELECT COUNT(*) FROM (VALUES ('1')) AS t(x)) AS approved_count(value);

-- =====================================================================
-- TEST 9: Unapproved Mapping IDs (if any)
-- =====================================================================
-- Show any mapping_ids that are NOT in the approved list
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
)
SELECT
  'UNAPPROVED_MAPPING_IDS_FOUND' AS test_name,
  e.mapping_id,
  COUNT(*) AS usage_count
FROM runtime.evidence e
LEFT JOIN approved_mappings am ON e.mapping_id = am.mapping_id
WHERE am.mapping_id IS NULL
GROUP BY e.mapping_id
ORDER BY usage_count DESC;

-- =====================================================================
-- TEST 10: Lineage Metadata Completeness
-- =====================================================================
SELECT
  'TEST_LINEAGE_METADATA_COMPLETENESS' AS test_name,
  COUNT(*) AS total_evidence,
  COUNT(*) FILTER (WHERE evidence_lineage IS NOT NULL) AS has_lineage,
  COUNT(*) FILTER (WHERE evidence_lineage::text LIKE '%extraction_path%') AS has_extraction_path,
  COUNT(*) FILTER (WHERE evidence_lineage::text LIKE '%source_field%') AS has_source_field,
  COUNT(*) FILTER (WHERE evidence_lineage::text LIKE '%mapping_id%') AS has_mapping_id,
  ROUND(100.0 * COUNT(*) FILTER (WHERE evidence_lineage IS NOT NULL) / COUNT(*), 1) AS lineage_coverage_percent,
  CASE WHEN COUNT(*) FILTER (WHERE evidence_lineage IS NOT NULL) > 0
       THEN 'PASS - Lineage metadata captured' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 11: Raw Event → Evidence Coverage
-- =====================================================================
-- Verify every raw event has produced at least one Evidence row
SELECT
  'TEST_RAW_EVENT_COVERAGE' AS test_name,
  (SELECT COUNT(*) FROM raw.raw_event) AS total_raw_events,
  COUNT(DISTINCT raw_event_id) AS raw_events_with_evidence,
  (SELECT COUNT(*) FROM raw.raw_event) - COUNT(DISTINCT raw_event_id) AS uncovered_raw_events,
  CASE WHEN (SELECT COUNT(*) FROM raw.raw_event) = COUNT(DISTINCT raw_event_id)
       THEN 'PASS - All raw events covered' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- Detail of uncovered raw events (if any)
SELECT
  'UNCOVERED_RAW_EVENTS_DETAIL' AS test_name,
  r.raw_event_id,
  r.event_type,
  r.actor_id,
  'NO EVIDENCE GENERATED' AS issue
FROM raw.raw_event r
LEFT JOIN runtime.evidence e ON r.raw_event_id = e.raw_event_id
WHERE e.raw_event_id IS NULL;

-- =====================================================================
-- TEST 12: Lineage Identity Uniqueness (Core Idempotency Key)
-- =====================================================================
SELECT
  'TEST_LINEAGE_IDENTITY_UNIQUE' AS test_name,
  COUNT(*) AS total_rows,
  COUNT(DISTINCT (raw_event_id, mapping_id)) AS unique_identities,
  COUNT(*) - COUNT(DISTINCT (raw_event_id, mapping_id)) AS duplicate_count,
  CASE WHEN COUNT(*) = COUNT(DISTINCT (raw_event_id, mapping_id))
       THEN 'PASS - Lineage identity unique' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 13: Raw Event Type Coverage by Mapping
-- =====================================================================
-- Show which raw event types have generated Evidence
SELECT
  'RAW_EVENT_TYPE_COVERAGE' AS test_name,
  r.event_type,
  COUNT(DISTINCT r.raw_event_id) AS raw_event_count,
  COUNT(DISTINCT e.raw_event_id) AS events_with_evidence,
  COUNT(DISTINCT e.mapping_id) AS distinct_mappings,
  COUNT(e.raw_event_id) AS total_evidence_rows
FROM raw.raw_event r
LEFT JOIN runtime.evidence e ON r.raw_event_id = e.raw_event_id
GROUP BY r.event_type
ORDER BY raw_event_count DESC;

-- =====================================================================
-- LINEAGE INTEGRITY SUMMARY
-- =====================================================================
SELECT
  'LINEAGE_INTEGRITY_SUMMARY' AS test_name,
  'Overall Status' AS metric,
  CASE
    WHEN COUNT(*) > 0
    AND COUNT(*) = COUNT(DISTINCT (raw_event_id, mapping_id))
    AND COUNT(DISTINCT raw_event_id) = (SELECT COUNT(*) FROM raw.raw_event)
    AND COUNT(*) FILTER (WHERE raw_event_id IS NULL) = 0
    AND COUNT(*) FILTER (WHERE mapping_id IS NULL OR mapping_id = '') = 0
    THEN 'PASS - Lineage Integrity Complete'
    ELSE 'FAIL - Lineage Issues Detected'
  END AS status,
  COUNT(*) AS total_evidence,
  COUNT(DISTINCT raw_event_id) AS raw_events_referenced,
  COUNT(DISTINCT mapping_id) AS mappings_used
FROM runtime.evidence;

-- =====================================================================
-- END OF LINEAGE INTEGRITY TEST SUITE
-- =====================================================================
-- All tests should show PASS status.
-- FK integrity and orphan detection are critical for lineage reliability.
