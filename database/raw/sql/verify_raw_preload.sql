-- GATE 1: Pre-load verification
-- Run BEFORE executing the ECS raw ingestion task.
-- Confirms all required tables exist and protected tables are empty.

\set ECHO queries
\set ON_ERROR_STOP on

-- Connection
SELECT database() AS current_database;
SELECT version();

-- Table existence checks
DO $$
BEGIN
  PERFORM 1 FROM information_schema.tables
  WHERE table_schema = 'raw' AND table_name = 'raw_event';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Required table raw.raw_event does not exist';
  END IF;

  PERFORM 1 FROM information_schema.tables
  WHERE table_schema = 'runtime' AND table_name = 'evidence';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Required table runtime.evidence does not exist';
  END IF;

  PERFORM 1 FROM information_schema.tables
  WHERE table_schema = 'runtime' AND table_name = 'assertion';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Required table runtime.assertion does not exist';
  END IF;

  PERFORM 1 FROM information_schema.tables
  WHERE table_schema = 'state' AND table_name = 'fold_state_snapshot';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Required table state.fold_state_snapshot does not exist';
  END IF;

  PERFORM 1 FROM information_schema.tables
  WHERE table_schema = 'audit' AND table_name = 'ingestion_file';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Required table audit.ingestion_file does not exist';
  END IF;

  PERFORM 1 FROM information_schema.tables
  WHERE table_schema = 'audit' AND table_name = 'ingestion_log';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Required table audit.ingestion_log does not exist';
  END IF;

  PERFORM 1 FROM information_schema.tables
  WHERE table_schema = 'audit' AND table_name = 'schema_version';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Required table audit.schema_version does not exist';
  END IF;

  RAISE NOTICE 'All required tables exist.';
END $$;

-- Baseline record counts
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
UNION ALL
SELECT
  'audit.ingestion_log' AS table_name,
  COUNT(*) AS record_count
FROM audit.ingestion_log
ORDER BY table_name;

-- Verify protected tables are empty (gate requirement)
DO $$
DECLARE
  evidence_count INT;
  assertion_count INT;
  fold_count INT;
BEGIN
  SELECT COUNT(*) INTO evidence_count FROM runtime.evidence;
  SELECT COUNT(*) INTO assertion_count FROM runtime.assertion;
  SELECT COUNT(*) INTO fold_count FROM state.fold_state_snapshot;

  IF evidence_count > 0 OR assertion_count > 0 OR fold_count > 0 THEN
    RAISE EXCEPTION 'Protected tables are not empty: evidence=%, assertion=%, fold=%',
      evidence_count, assertion_count, fold_count;
  END IF;

  RAISE NOTICE 'Protected tables are empty. Pre-load verification PASSED.';
END $$;

-- Show raw.raw_event schema (column names and types)
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'raw' AND table_name = 'raw_event'
ORDER BY ordinal_position;

-- Verify primary/unique constraints on raw.raw_event
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'raw' AND table_name = 'raw_event';

-- Verify audit.ingestion_file schema
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'audit' AND table_name = 'ingestion_file'
ORDER BY ordinal_position;

-- Show existing ingestion file checkpoints (if any)
SELECT bucket, object_key, object_version, status, records_inserted, ingested_at
FROM audit.ingestion_file
ORDER BY ingested_at DESC
LIMIT 10;
