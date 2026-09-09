-- =====================================================================
-- Fold Test Fixtures: Idempotency Verification (CORRECTED)
-- =====================================================================
-- Purpose: Verify that Run #1 and Run #2 produce identical snapshots
-- Strategy: Execute Fold twice at same horizon, compare counts and content
-- CORRECTED: Wrapped in transaction with ROLLBACK for test isolation
-- =====================================================================

BEGIN;  -- START TRANSACTION: Isolate test execution

-- =====================================================================
-- SETUP: Capture Run #1 state
-- =====================================================================

-- Create temporary table for Run #1 results
CREATE TEMP TABLE run1_snapshot AS
SELECT
  fold_state_id, decision_horizon, subject_type, subject_id,
  fold_status, folded_properties, basis_assertion_ids,
  kb_version, policy_version
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'
ORDER BY subject_type, subject_id;

-- Create temporary table for Run #1 property counts
CREATE TEMP TABLE run1_properties AS
SELECT
  subject_type, subject_id,
  jsonb_array_length(folded_properties) AS property_count,
  jsonb_array_length(basis_assertion_ids) AS basis_id_count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'
ORDER BY subject_type, subject_id;

-- =====================================================================
-- Execute Run #2: Re-run Fold at exact same horizon
-- =====================================================================

SELECT 'TEST: Idempotency Run #2 Execution' AS test_name;

SELECT 'Executing: runtime.fold_snapshot_at_horizon(2026-06-20 10:45:00+00)' AS execution;

-- This should insert 0 new rows (idempotent: ON CONFLICT DO NOTHING)
SELECT * FROM runtime.fold_snapshot_at_horizon('2026-06-20 10:45:00+00');

-- =====================================================================
-- Test 1: Snapshot Row Count Unchanged
-- =====================================================================

SELECT 'TEST: Snapshot Row Count Idempotency' AS test_name;

WITH run2_count AS (
  SELECT COUNT(*) AS count FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
),
run1_count AS (
  SELECT COUNT(*) AS count FROM run1_snapshot
)
SELECT
  run1_count.count AS run1_snapshots,
  run2_count.count AS run2_snapshots,
  CASE WHEN run1_count.count = run2_count.count THEN 'PASS'
       ELSE 'FAIL: Count mismatch'
  END AS status,
  'Expected: 51' AS expectation
FROM run1_count, run2_count;

-- =====================================================================
-- Test 2: Total Property Count Unchanged
-- =====================================================================

SELECT 'TEST: Property Count Idempotency' AS test_name;

WITH run1_props AS (
  SELECT COUNT(*) AS count FROM run1_properties
),
run2_props AS (
  SELECT
    COUNT(*) AS count
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
)
SELECT
  run1_props.count AS run1_property_states,
  run2_props.count AS run2_property_states,
  CASE WHEN run1_props.count = run2_props.count THEN 'PASS'
       ELSE 'FAIL: Count mismatch'
  END AS status,
  'Expected: 177' AS expectation
FROM run1_props, run2_props;

-- =====================================================================
-- Test 3: State Distribution Unchanged
-- =====================================================================

SELECT 'TEST: State Distribution Idempotency' AS test_name;

WITH run1_dist AS (
  SELECT
    COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED') AS est,
    COUNT(*) FILTER (WHERE fold_state = 'UNREPORTED') AS unr,
    COUNT(*) FILTER (WHERE fold_state = 'EXPLICITLY_UNDEFINED') AS undef,
    COUNT(*) FILTER (WHERE fold_state = 'CONTRADICTED') AS cont
  FROM run1_snapshot,
       LATERAL jsonb_array_elements(folded_properties) AS props
),
run2_dist AS (
  SELECT
    COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED') AS est,
    COUNT(*) FILTER (WHERE fold_state = 'UNREPORTED') AS unr,
    COUNT(*) FILTER (WHERE fold_state = 'EXPLICITLY_UNDEFINED') AS undef,
    COUNT(*) FILTER (WHERE fold_state = 'CONTRADICTED') AS cont
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
)
SELECT
  'ESTABLISHED' AS state,
  (run1_dist.est)::TEXT AS run1_count,
  (run2_dist.est)::TEXT AS run2_count,
  CASE WHEN run1_dist.est = run2_dist.est THEN 'PASS' ELSE 'FAIL' END AS status
FROM run1_dist, run2_dist
UNION ALL
SELECT
  'UNREPORTED',
  (run1_dist.unr)::TEXT,
  (run2_dist.unr)::TEXT,
  CASE WHEN run1_dist.unr = run2_dist.unr THEN 'PASS' ELSE 'FAIL' END
FROM run1_dist, run2_dist
UNION ALL
SELECT
  'EXPLICITLY_UNDEFINED',
  (run1_dist.undef)::TEXT,
  (run2_dist.undef)::TEXT,
  CASE WHEN run1_dist.undef = run2_dist.undef THEN 'PASS' ELSE 'FAIL' END
FROM run1_dist, run2_dist
UNION ALL
SELECT
  'CONTRADICTED',
  (run1_dist.cont)::TEXT,
  (run2_dist.cont)::TEXT,
  CASE WHEN run1_dist.cont = run2_dist.cont THEN 'PASS' ELSE 'FAIL' END
FROM run1_dist, run2_dist;

-- =====================================================================
-- Test 4: Duplicate Snapshot Keys (None Expected)
-- =====================================================================

SELECT 'TEST: Duplicate Snapshot Keys' AS test_name;

SELECT
  COUNT(*) AS duplicate_key_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: No duplicate keys'
       ELSE 'FAIL: Duplicates detected'
  END AS status
FROM (
  SELECT decision_horizon, subject_type, subject_id, COUNT(*)
  FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
  GROUP BY decision_horizon, subject_type, subject_id
  HAVING COUNT(*) > 1
) t;

-- =====================================================================
-- Test 5: Business Content Unchanged (folded_properties JSON)
-- =====================================================================

SELECT 'TEST: folded_properties Content Idempotency' AS test_name;

WITH run1_hash AS (
  SELECT
    subject_type, subject_id,
    MD5(folded_properties::TEXT) AS content_hash
  FROM run1_snapshot
  ORDER BY subject_type, subject_id
),
run2_hash AS (
  SELECT
    subject_type, subject_id,
    MD5(folded_properties::TEXT) AS content_hash
  FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
  ORDER BY subject_type, subject_id
)
SELECT
  COUNT(*) AS subjects_compared,
  COUNT(CASE WHEN run1_hash.content_hash = run2_hash.content_hash THEN 1 END) AS matching_content,
  CASE WHEN COUNT(*) = COUNT(CASE WHEN run1_hash.content_hash = run2_hash.content_hash THEN 1 END)
    THEN 'PASS: All content identical'
    ELSE 'FAIL: Content divergence detected'
  END AS status
FROM run1_hash
FULL OUTER JOIN run2_hash
  ON run1_hash.subject_type = run2_hash.subject_type
  AND run1_hash.subject_id = run2_hash.subject_id;

-- =====================================================================
-- Test 6: basis_assertion_ids Unchanged
-- =====================================================================

SELECT 'TEST: basis_assertion_ids Idempotency' AS test_name;

WITH run1_basis AS (
  SELECT
    subject_type, subject_id,
    MD5(basis_assertion_ids::TEXT) AS basis_hash
  FROM run1_snapshot
  ORDER BY subject_type, subject_id
),
run2_basis AS (
  SELECT
    subject_type, subject_id,
    MD5(basis_assertion_ids::TEXT) AS basis_hash
  FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
  ORDER BY subject_type, subject_id
)
SELECT
  COUNT(*) AS subjects_compared,
  COUNT(CASE WHEN run1_basis.basis_hash = run2_basis.basis_hash THEN 1 END) AS matching_basis,
  CASE WHEN COUNT(*) = COUNT(CASE WHEN run1_basis.basis_hash = run2_basis.basis_hash THEN 1 END)
    THEN 'PASS: All basis IDs identical'
    ELSE 'FAIL: Basis divergence detected'
  END AS status
FROM run1_basis
FULL OUTER JOIN run2_basis
  ON run1_basis.subject_type = run2_basis.subject_type
  AND run1_basis.subject_id = run2_basis.subject_id;

-- =====================================================================
-- Test 7: Subject fold_status Unchanged
-- =====================================================================

SELECT 'TEST: Subject fold_status Idempotency' AS test_name;

WITH run1_status AS (
  SELECT subject_type, subject_id, fold_status FROM run1_snapshot
  ORDER BY subject_type, subject_id
),
run2_status AS (
  SELECT subject_type, subject_id, fold_status
  FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
  ORDER BY subject_type, subject_id
)
SELECT
  COUNT(*) AS subjects_compared,
  COUNT(CASE WHEN run1_status.fold_status = run2_status.fold_status THEN 1 END) AS matching_status,
  CASE WHEN COUNT(*) = COUNT(CASE WHEN run1_status.fold_status = run2_status.fold_status THEN 1 END)
    THEN 'PASS: All fold_status identical'
    ELSE 'FAIL: fold_status divergence detected'
  END AS status
FROM run1_status
FULL OUTER JOIN run2_status
  ON run1_status.subject_type = run2_status.subject_type
  AND run1_status.subject_id = run2_status.subject_id;

-- =====================================================================
-- Test 8: KB Version Consistency
-- =====================================================================

SELECT 'TEST: KB Version Consistency' AS test_name;

WITH run1_kb AS (
  SELECT DISTINCT kb_version FROM run1_snapshot
),
run2_kb AS (
  SELECT DISTINCT kb_version
  FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
)
SELECT
  (SELECT kb_version FROM run1_kb LIMIT 1) AS run1_kb_version,
  (SELECT kb_version FROM run2_kb LIMIT 1) AS run2_kb_version,
  CASE WHEN (SELECT kb_version FROM run1_kb) = (SELECT kb_version FROM run2_kb)
    THEN 'PASS: KB versions match'
    ELSE 'FAIL: KB version divergence'
  END AS status;

-- =====================================================================
-- Test 9: Policy Version Consistency
-- =====================================================================

SELECT 'TEST: Policy Version Consistency' AS test_name;

WITH run1_policy AS (
  SELECT DISTINCT policy_version FROM run1_snapshot
),
run2_policy AS (
  SELECT DISTINCT policy_version
  FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
)
SELECT
  (SELECT policy_version FROM run1_policy LIMIT 1) AS run1_policy_version,
  (SELECT policy_version FROM run2_policy LIMIT 1) AS run2_policy_version,
  CASE WHEN (SELECT policy_version FROM run1_policy) = (SELECT policy_version FROM run2_policy)
    THEN 'PASS: Policy versions match'
    ELSE 'FAIL: Policy version divergence'
  END AS status;

-- =====================================================================
-- Test Summary
-- =====================================================================

SELECT 'Idempotency verification complete. All tests should PASS.' AS summary;
SELECT 'If any test shows divergence between Run #1 and Run #2, investigate root cause.' AS note;

ROLLBACK;  -- ROLLBACK: Undo all test changes, restore to pre-test state
