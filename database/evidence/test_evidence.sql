-- =====================================================================
-- Test Suite: Evidence Layer Basic Validation
-- =====================================================================
-- Purpose: Verify Evidence transformation completed successfully
-- Expected: 169 raw events, >0 evidence rows, 0 assertions, 0 fold entries
-- Status: Post-execution verification
-- =====================================================================

-- =====================================================================
-- TEST 1: Raw Event Count (should be 169)
-- =====================================================================
SELECT
  'TEST_RAW_EVENT_COUNT' AS test_name,
  COUNT(*) AS actual_count,
  169 AS expected_count,
  CASE WHEN COUNT(*) = 169 THEN 'PASS' ELSE 'FAIL' END AS status
FROM raw.raw_event;

-- =====================================================================
-- TEST 2: Evidence Row Count (should be >0)
-- =====================================================================
SELECT
  'TEST_EVIDENCE_COUNT' AS test_name,
  COUNT(*) AS actual_count,
  'EXPECTED: 300-400 (1:N cardinality)' AS expected_range,
  CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 3: Assertion Count (should be 0 - not started)
-- =====================================================================
SELECT
  'TEST_ASSERTION_COUNT_ZERO' AS test_name,
  COUNT(*) AS actual_count,
  0 AS expected_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.assertion;

-- =====================================================================
-- TEST 4: Fold State Count (should be 0 - not started)
-- =====================================================================
SELECT
  'TEST_FOLD_STATE_COUNT_ZERO' AS test_name,
  COUNT(*) AS actual_count,
  0 AS expected_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM state.fold_state_snapshot;

-- =====================================================================
-- TEST 5: Evidence Cardinality Ratio
-- =====================================================================
SELECT
  'TEST_CARDINALITY_RATIO' AS test_name,
  (SELECT COUNT(*) FROM raw.raw_event) AS raw_count,
  (SELECT COUNT(*) FROM runtime.evidence) AS evidence_count,
  ROUND(CAST((SELECT COUNT(*) FROM runtime.evidence) AS numeric) /
        CAST((SELECT COUNT(*) FROM raw.raw_event) AS numeric), 2) AS cardinality_ratio,
  'EXPECTED: 2.0-2.5 (1:N mapping)' AS expected_range,
  CASE WHEN ROUND(CAST((SELECT COUNT(*) FROM runtime.evidence) AS numeric) /
                  CAST((SELECT COUNT(*) FROM raw.raw_event) AS numeric), 2) >= 1.5
       THEN 'PASS' ELSE 'FAIL' END AS status;

-- =====================================================================
-- TEST 6: No NULL mapping_ids
-- =====================================================================
SELECT
  'TEST_NO_NULL_MAPPING_IDS' AS test_name,
  COUNT(*) FILTER (WHERE mapping_id IS NULL OR mapping_id = '') AS null_count,
  0 AS expected_null_count,
  CASE WHEN COUNT(*) FILTER (WHERE mapping_id IS NULL OR mapping_id = '') = 0
       THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 7: All Mapping IDs are Non-Empty Strings
-- =====================================================================
SELECT
  'TEST_MAPPING_ID_VALID_FORMAT' AS test_name,
  COUNT(*) AS evidence_rows,
  COUNT(*) FILTER (WHERE mapping_id ~ '^[A-Z_]+$') AS valid_format_count,
  CASE WHEN COUNT(*) = COUNT(*) FILTER (WHERE mapping_id ~ '^[A-Z_]+$')
       THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 8: Subject Type Distribution Check
-- =====================================================================
SELECT
  'TEST_SUBJECT_TYPE_DISTRIBUTION' AS test_name,
  COUNT(DISTINCT subject_type) AS distinct_subject_types,
  4 AS expected_types,
  STRING_AGG(DISTINCT subject_type, ', ' ORDER BY subject_type) AS subject_types_present,
  CASE WHEN COUNT(DISTINCT subject_type) = 4 THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 9: No NULL subject_ids
-- =====================================================================
SELECT
  'TEST_NO_NULL_SUBJECT_IDS' AS test_name,
  COUNT(*) FILTER (WHERE subject_id IS NULL OR subject_id = '') AS null_count,
  0 AS expected_null_count,
  CASE WHEN COUNT(*) FILTER (WHERE subject_id IS NULL OR subject_id = '') = 0
       THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 10: FK Integrity - all raw_event_ids reference valid raw events
-- =====================================================================
SELECT
  'TEST_RAW_EVENT_ID_FK_INTEGRITY' AS test_name,
  COUNT(DISTINCT e.raw_event_id) AS evidence_raw_ids,
  COUNT(DISTINCT r.raw_event_id) AS actual_raw_ids,
  COUNT(DISTINCT e.raw_event_id) - COUNT(DISTINCT r.raw_event_id) AS orphaned_raw_ids,
  CASE WHEN COUNT(DISTINCT e.raw_event_id) - COUNT(DISTINCT r.raw_event_id) = 0
       THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence e
LEFT JOIN raw.raw_event r ON e.raw_event_id = r.raw_event_id;

-- =====================================================================
-- TEST 11: Timestamp Fields Not NULL
-- =====================================================================
SELECT
  'TEST_TIMESTAMP_NOT_NULL' AS test_name,
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE occurred_at IS NULL) AS null_occurred_at,
  COUNT(*) FILTER (WHERE recorded_at IS NULL) AS null_recorded_at,
  COUNT(*) FILTER (WHERE arrival_at IS NULL) AS null_arrival_at,
  COUNT(*) FILTER (WHERE occurred_at IS NOT NULL AND recorded_at IS NOT NULL AND arrival_at IS NOT NULL) AS all_valid,
  CASE WHEN COUNT(*) FILTER (WHERE occurred_at IS NULL) = 0
       AND COUNT(*) FILTER (WHERE recorded_at IS NULL) = 0
       AND COUNT(*) FILTER (WHERE arrival_at IS NULL) = 0
       THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 12: Evidence Reason and Lineage Capture
-- =====================================================================
SELECT
  'TEST_LINEAGE_METADATA_PRESENT' AS test_name,
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE evidence_lineage IS NOT NULL) AS rows_with_lineage,
  COUNT(*) FILTER (WHERE evidence_lineage::text LIKE '%extraction_path%') AS rows_with_extraction_path,
  ROUND(100.0 * COUNT(*) FILTER (WHERE evidence_lineage IS NOT NULL) / COUNT(*), 1) AS lineage_coverage_percent,
  CASE WHEN COUNT(*) FILTER (WHERE evidence_lineage IS NOT NULL) > 0
       THEN 'PASS' ELSE 'FAIL' END AS status
FROM runtime.evidence;

-- =====================================================================
-- TEST 13: Top Mapping IDs by Evidence Count
-- =====================================================================
SELECT
  'TEST_TOP_MAPPINGS' AS test_name,
  mapping_id,
  COUNT(*) AS evidence_count
FROM runtime.evidence
GROUP BY mapping_id
ORDER BY evidence_count DESC
LIMIT 10;

-- =====================================================================
-- TEST 14: Evidence Type Distribution
-- =====================================================================
SELECT
  'TEST_EVIDENCE_TYPE_DISTRIBUTION' AS test_name,
  evidence_type,
  COUNT(*) AS row_count
FROM runtime.evidence
WHERE evidence_type IS NOT NULL
GROUP BY evidence_type
ORDER BY row_count DESC;

-- =====================================================================
-- TEST 15: Transformation Quality Summary
-- =====================================================================
SELECT
  'TEST_QUALITY_SUMMARY' AS test_name,
  'Raw → Evidence Transformation Complete' AS status,
  (SELECT COUNT(*) FROM raw.raw_event) AS raw_event_count,
  (SELECT COUNT(*) FROM runtime.evidence) AS evidence_row_count,
  (SELECT COUNT(DISTINCT mapping_id) FROM runtime.evidence) AS mappings_used,
  (SELECT COUNT(DISTINCT subject_id) FROM runtime.evidence) AS distinct_subjects,
  (SELECT COUNT(DISTINCT property_name) FROM runtime.evidence) AS distinct_properties,
  (SELECT COUNT(*) FROM raw.raw_event) = 169
    AND (SELECT COUNT(*) FROM runtime.evidence) > 0
    AND (SELECT COUNT(*) FROM runtime.assertion) = 0
    AND (SELECT COUNT(*) FROM state.fold_state_snapshot) = 0
  AS transformation_successful;

-- =====================================================================
-- END OF TEST SUITE
-- =====================================================================
-- All tests above should show PASS status and valid counts.
-- If any test shows FAIL, review transformation logic in raw_to_evidence.sql
