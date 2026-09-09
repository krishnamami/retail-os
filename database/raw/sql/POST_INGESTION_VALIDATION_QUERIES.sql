-- =====================================================================
-- STEP 5D Post-Ingestion Validation Queries
-- Run after Phase E ingestion completes (both Run 1 and Run 2)
-- All queries are read-only; no data modifications
-- =====================================================================

-- Query 1: ROW COUNT VERIFICATION
-- Expected: 177 total (169 baseline + 8 prototype)
SELECT
  COUNT(*) as total_records,
  COUNT(*) FILTER (WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION') as prototype_records,
  COUNT(*) FILTER (WHERE payload->>'simulator_classification' IS NULL) as baseline_records
FROM raw.raw_event;

-- Query 2: EVENT TYPES IN PROTOTYPE RECORDS
-- Expected: 1 PRODUCT_DEFINED + 7 CONFIGURATION_REQUESTED = 8 total
SELECT
  event_type,
  COUNT(*) as count,
  STRING_AGG(DISTINCT source_record_id, ', ' ORDER BY source_record_id) as source_ids
FROM raw.raw_event
WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
GROUP BY event_type
ORDER BY event_type;

-- Query 3: PROVENANCE TAGGING VERIFICATION
-- Expected: 169 NULL (baseline), 8 PROTOTYPE_ASSUMPTION (new)
SELECT
  COALESCE(payload->>'simulator_classification', 'NULL') as provenance_tag,
  COUNT(*) as count
FROM raw.raw_event
GROUP BY COALESCE(payload->>'simulator_classification', 'NULL')
ORDER BY provenance_tag;

-- Query 4: CONFIGURATION_ID VALIDATION
-- Expected: All 8 prototype records have configuration_id = NULL
SELECT
  COUNT(*) FILTER (WHERE payload->>'configuration_id' IS NULL) as null_config_id,
  COUNT(*) FILTER (WHERE payload->>'configuration_id' IS NOT NULL) as non_null_config_id
FROM raw.raw_event
WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION';

-- Query 5: BASELINE PRESERVATION
-- Expected: 169 records unchanged
SELECT
  COUNT(*) as baseline_record_count
FROM raw.raw_event
WHERE payload->>'simulator_classification' IS NULL
   OR payload->>'simulator_classification' != 'PROTOTYPE_ASSUMPTION';

-- Query 6: IDEMPOTENCY KEY UNIQUENESS
-- Expected: 0 duplicate tuples (all unique)
-- If this returns any rows, idempotency has failed
SELECT
  source_system,
  source_record_id,
  source_version,
  COUNT(*) as duplicate_count
FROM raw.raw_event
WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
GROUP BY source_system, source_record_id, source_version
HAVING COUNT(*) > 1;

-- Query 7: S6 BUSINESS DUPLICATE PAIR
-- Expected: 2 distinct records with same configuration but different IDs
-- S6a: CONFIG_REQ_2026_005 (config_request_id=CONFIG-REQ-2026-006)
-- S6b: CONFIG_REQ_2026_006 (config_request_id=CONFIG-REQ-2026-006B)
SELECT
  source_record_id,
  source_system,
  payload->>'event_type' as event_type,
  payload->>'product_id' as product_id,
  (payload->'payload')->>'geo' as geo,
  (payload->'payload')->>'term' as term,
  (payload->'payload')->>'segment' as segment,
  (payload->'payload')->>'configuration_request_id' as config_request_id
FROM raw.raw_event
WHERE source_record_id IN ('CONFIG_REQ_2026_005', 'CONFIG_REQ_2026_006')
  AND payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
ORDER BY source_record_id;

-- Query 8: S7 INCOMPLETE IDENTITY
-- Expected: 1 record with segment = NULL
-- CONFIG_REQ_2026_007 with segment missing
SELECT
  source_record_id,
  payload->>'event_type' as event_type,
  payload->>'product_id' as product_id,
  (payload->'payload')->>'geo' as geo,
  (payload->'payload')->>'term' as term,
  (payload->'payload')->>'segment' as segment,
  (payload->'payload')->>'configuration_request_id' as config_request_id
FROM raw.raw_event
WHERE source_record_id = 'CONFIG_REQ_2026_007'
  AND payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION';

-- SUMMARY: All validations in one query
-- Run this at the end to confirm all checks pass
WITH validation_summary AS (
  SELECT
    'Total Records (expect 177)' as check_name,
    COUNT(*)::text as actual_value,
    CASE WHEN COUNT(*) = 177 THEN 'PASS' ELSE 'FAIL' END as status
  FROM raw.raw_event

  UNION ALL

  SELECT
    'Prototype Records (expect 8)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 8 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'

  UNION ALL

  SELECT
    'Baseline Records (expect 169)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 169 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE payload->>'simulator_classification' IS NULL

  UNION ALL

  SELECT
    'PRODUCT_DEFINED (expect 1)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 1 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE event_type = 'PRODUCT_DEFINED'
    AND payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'

  UNION ALL

  SELECT
    'CONFIGURATION_REQUESTED (expect 7)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 7 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE event_type = 'CONFIGURATION_REQUESTED'
    AND payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'

  UNION ALL

  SELECT
    'Configuration_ID NULL (expect 8)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 8 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
    AND payload->>'configuration_id' IS NULL

  UNION ALL

  SELECT
    'Source Version = 1 (expect 8)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 8 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
    AND (payload->>'source_version')::int = 1

  UNION ALL

  SELECT
    'S6 Business Duplicate (expect 2)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 2 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE source_record_id IN ('CONFIG_REQ_2026_005', 'CONFIG_REQ_2026_006')
    AND payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'

  UNION ALL

  SELECT
    'S7 Missing Segment (expect 1)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 1 THEN 'PASS' ELSE 'FAIL' END
  FROM raw.raw_event
  WHERE source_record_id = 'CONFIG_REQ_2026_007'
    AND payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
    AND (payload->'payload')->>'segment' IS NULL

  UNION ALL

  SELECT
    'Duplicate Keys (expect 0)',
    COUNT(*)::text,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END
  FROM (
    SELECT source_system, source_record_id, source_version
    FROM raw.raw_event
    WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
    GROUP BY source_system, source_record_id, source_version
    HAVING COUNT(*) > 1
  ) duplicates
)
SELECT
  check_name,
  actual_value,
  status
FROM validation_summary
ORDER BY
  CASE WHEN status = 'FAIL' THEN 0 ELSE 1 END DESC,
  check_name;
