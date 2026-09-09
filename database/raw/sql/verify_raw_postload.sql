-- GATE 2: Post-load verification
-- Run AFTER executing the ECS raw ingestion task.
-- Confirms 169 records were loaded and protected tables remain empty.

\set ECHO queries
\set ON_ERROR_STOP on

-- Connection
SELECT database() AS current_database, NOW() AT TIME ZONE 'UTC' AS query_time;

-- Record counts after load
SELECT
  'raw.raw_event' AS table_name,
  COUNT(*) AS record_count
FROM raw.raw_event
UNION ALL
SELECT
  'runtime.evidence' AS table_name,
  COUNT(*) AS record_count
FROM runtime.evidence
UNION ALL
SELECT
  'runtime.assertion' AS table_name,
  COUNT(*) AS record_count
FROM runtime.assertion
UNION ALL
SELECT
  'state.fold_state_snapshot' AS table_name,
  COUNT(*) AS record_count
FROM state.fold_state_snapshot
UNION ALL
SELECT
  'audit.ingestion_file' AS table_name,
  COUNT(*) AS record_count
FROM audit.ingestion_file
ORDER BY table_name;

-- Verify expected record count (169 from 26 JSONL files)
DO $$
DECLARE
  raw_count INT;
  evidence_count INT;
  assertion_count INT;
  fold_count INT;
BEGIN
  SELECT COUNT(*) INTO raw_count FROM raw.raw_event;
  SELECT COUNT(*) INTO evidence_count FROM runtime.evidence;
  SELECT COUNT(*) INTO assertion_count FROM runtime.assertion;
  SELECT COUNT(*) INTO fold_count FROM state.fold_state_snapshot;

  -- Expected: raw_event = 169, all others = 0
  IF raw_count <> 169 THEN
    RAISE EXCEPTION 'Expected 169 records in raw.raw_event, got %', raw_count;
  END IF;

  IF evidence_count > 0 OR assertion_count > 0 OR fold_count > 0 THEN
    RAISE EXCEPTION 'Protected tables are not empty: evidence=%, assertion=%, fold=%',
      evidence_count, assertion_count, fold_count;
  END IF;

  RAISE NOTICE 'Post-load verification PASSED: 169 records loaded, protected tables empty';
END $$;

-- Show ingestion file checkpoints
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

-- Expected: 26 files with SUCCESS status, total 169 records
DO $$
DECLARE
  file_count INT;
  total_records INT;
BEGIN
  SELECT COUNT(*) INTO file_count FROM audit.ingestion_file WHERE status = 'SUCCESS';
  SELECT COALESCE(SUM(records_inserted), 0) INTO total_records FROM audit.ingestion_file;

  RAISE NOTICE 'Files processed: %, Total records: %', file_count, total_records;

  IF file_count <> 26 THEN
    RAISE WARNING 'Expected 26 files, got %', file_count;
  END IF;

  IF total_records <> 169 THEN
    RAISE WARNING 'Expected 169 total records, got %', total_records;
  END IF;
END $$;

-- Show raw.raw_event sample records
SELECT
  id,
  source_system,
  source_record_id,
  source_version,
  event_type,
  sku_id,
  launch_id,
  ingested_at,
  (payload::text)[:100] || '...' AS payload_preview
FROM raw.raw_event
LIMIT 5;

-- Show source_system distribution
SELECT source_system, COUNT(*) as count
FROM raw.raw_event
GROUP BY source_system
ORDER BY count DESC;

-- Show event_type distribution
SELECT event_type, COUNT(*) as count
FROM raw.raw_event
GROUP BY event_type
ORDER BY count DESC;

-- Verify no missing values in critical fields
SELECT
  'source_system' AS field_name,
  COUNT(*) FILTER (WHERE source_system IS NULL) AS null_count
FROM raw.raw_event
UNION ALL
SELECT
  'source_record_id' AS field_name,
  COUNT(*) FILTER (WHERE source_record_id IS NULL) AS null_count
FROM raw.raw_event
UNION ALL
SELECT
  'payload' AS field_name,
  COUNT(*) FILTER (WHERE payload IS NULL) AS null_count
FROM raw.raw_event
UNION ALL
SELECT
  'ingested_at' AS field_name,
  COUNT(*) FILTER (WHERE ingested_at IS NULL) AS null_count
FROM raw.raw_event;
