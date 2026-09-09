-- GATE 3: Idempotency verification
-- Run AFTER executing the ECS raw ingestion task TWICE.
-- Confirms second run produces no duplicates and record count remains 169.

\set ECHO queries
\set ON_ERROR_STOP on

-- Connection
SELECT database() AS current_database, NOW() AT TIME ZONE 'UTC' AS query_time;

-- Record counts after second run
SELECT
  'raw.raw_event' AS table_name,
  COUNT(*) AS record_count
FROM raw.raw_event
UNION ALL
SELECT
  'audit.ingestion_file' AS table_name,
  COUNT(*) AS record_count
FROM audit.ingestion_file
ORDER BY table_name;

-- Verify record count remains 169 (no duplicates)
DO $$
DECLARE
  raw_count INT;
  expected_count INT := 169;
BEGIN
  SELECT COUNT(*) INTO raw_count FROM raw.raw_event;

  IF raw_count <> expected_count THEN
    RAISE EXCEPTION 'Idempotency violation: expected %, got %', expected_count, raw_count;
  END IF;

  RAISE NOTICE 'Idempotency verified: raw.raw_event count = %', raw_count;
END $$;

-- Show all ingestion file checkpoints (both runs)
SELECT
  bucket,
  object_key,
  object_version,
  status,
  records_discovered,
  records_inserted,
  ingested_at
FROM audit.ingestion_file
ORDER BY ingested_at DESC;

-- Verify second run: all files marked as SUCCESS with 0 new inserts
DO $$
DECLARE
  run_count INT;
  files_no_insert INT;
  files_already_processed INT;
BEGIN
  -- Count distinct ingestion timestamps (should be 2 for two runs)
  SELECT COUNT(DISTINCT DATE_TRUNC('minute', ingested_at))
  INTO run_count
  FROM audit.ingestion_file;

  -- Files with 0 records inserted on second run
  SELECT COUNT(*)
  INTO files_no_insert
  FROM audit.ingestion_file
  WHERE records_inserted = 0;

  -- Files marked as already processed (status = SUCCESS)
  SELECT COUNT(*)
  INTO files_already_processed
  FROM audit.ingestion_file
  WHERE status = 'SUCCESS';

  RAISE NOTICE 'Ingestion runs detected: %', run_count;
  RAISE NOTICE 'Files with 0 inserts (2nd run): %', files_no_insert;
  RAISE NOTICE 'Files successfully processed: %', files_already_processed;

  -- Expected: 2 runs, 26 files per run, 0 inserts on 2nd run
  IF run_count < 2 THEN
    RAISE WARNING 'Expected 2 ingestion runs, found only %', run_count;
  END IF;

  IF files_no_insert < 26 THEN
    RAISE WARNING 'Expected 26 files with 0 inserts on 2nd run, found %', files_no_insert;
  END IF;
END $$;

-- Check for duplicate source identities (should be 0)
DO $$
DECLARE
  duplicate_count INT;
BEGIN
  SELECT COUNT(*)
  INTO duplicate_count
  FROM (
    SELECT source_system, source_record_id, source_version, COUNT(*) as cnt
    FROM raw.raw_event
    GROUP BY source_system, source_record_id, source_version
    HAVING COUNT(*) > 1
  ) duplicates;

  IF duplicate_count > 0 THEN
    RAISE EXCEPTION 'Found % duplicate source identities (idempotency failed)', duplicate_count;
  END IF;

  RAISE NOTICE 'Duplicate source identity check PASSED (0 duplicates found)';
END $$;

-- Show sample of records to verify data integrity
SELECT
  source_system,
  source_record_id,
  event_type,
  sku_id,
  ingested_at
FROM raw.raw_event
LIMIT 10;

-- Final summary
DO $$
DECLARE
  raw_count INT;
  unique_source_ids INT;
  protected_tables_empty BOOLEAN;
BEGIN
  SELECT COUNT(*) INTO raw_count FROM raw.raw_event;

  SELECT COUNT(DISTINCT (source_system, source_record_id, source_version))
  INTO unique_source_ids
  FROM raw.raw_event;

  SELECT COUNT(*) = 0 AND COUNT(*) = 0 AND COUNT(*) = 0
  INTO protected_tables_empty
  FROM (
    SELECT COUNT(*) as evidence_count FROM runtime.evidence
    UNION ALL
    SELECT COUNT(*) as assertion_count FROM runtime.assertion
    UNION ALL
    SELECT COUNT(*) as fold_count FROM state.fold_state_snapshot
  ) t
  WHERE evidence_count = 0 AND assertion_count = 0 AND fold_count = 0;

  RAISE NOTICE '===========================================';
  RAISE NOTICE 'IDEMPOTENCY VERIFICATION SUMMARY';
  RAISE NOTICE '===========================================';
  RAISE NOTICE 'Total raw.raw_event records: %', raw_count;
  RAISE NOTICE 'Unique source identities: %', unique_source_ids;
  RAISE NOTICE 'Protected tables empty: %', protected_tables_empty;
  RAISE NOTICE 'Status: % (expected 169 / 169 / true)',
    CASE
      WHEN raw_count = 169 AND unique_source_ids = 169 AND protected_tables_empty
      THEN 'PASSED ✓'
      ELSE 'FAILED ✗'
    END;
  RAISE NOTICE '===========================================';
END $$;
