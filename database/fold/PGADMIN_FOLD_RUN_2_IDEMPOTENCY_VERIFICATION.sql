-- =====================================================================
-- STEP 4J — FOLD RUN #2: IDEMPOTENCY VERIFICATION
-- =====================================================================
-- Authorization: STEP 4J Idempotency Verification
-- Objective: Execute exact same Fold horizon second time
--            Verify: new_snapshots_inserted = 0
--                    replay_mismatches = 0
--                    fold_computed_at timestamps unchanged
--                    property distributions identical
-- DO NOT delete existing 51 snapshots from Run #1
-- DO NOT modify Fold code or upstream layers
-- =====================================================================

-- =====================================================================
-- STEP 1: CAPTURE PRE-RUN STATE
-- =====================================================================

SELECT 'STEP 1: PRE-RUN STATE' AS step,
       COUNT(*) AS snapshot_count,
       MIN(fold_computed_at) AS min_computed_at,
       MAX(fold_computed_at) AS max_computed_at
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

-- Capture property distribution before Run #2
SELECT 'STEP 1B: PRE-RUN PROPERTY DISTRIBUTION' AS step,
       props->>'fold_state' AS fold_state,
       COUNT(*) AS property_count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY props->>'fold_state'
ORDER BY fold_state;

-- Capture upstream counts
SELECT 'STEP 1C: PRE-RUN UPSTREAM COUNTS' AS step,
       (SELECT COUNT(*) FROM raw.raw_event) AS raw_count,
       (SELECT COUNT(*) FROM runtime.evidence) AS evidence_count,
       (SELECT COUNT(*) FROM runtime.assertion) AS assertion_count;

-- =====================================================================
-- STEP 2: EXECUTE FOLD RUN #2 (Exact Same Call as Run #1)
-- =====================================================================

SELECT 'STEP 2: FOLD RUN #2 EXECUTION' AS step, *
FROM runtime.fold_snapshot_at_horizon('2026-06-20 10:45:00+00'::timestamptz);

-- =====================================================================
-- STEP 3: VERIFY SNAPSHOT COUNT UNCHANGED
-- =====================================================================

SELECT 'STEP 3: POST-RUN SNAPSHOT COUNT' AS step,
       COUNT(*) AS snapshot_count_after
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

-- =====================================================================
-- STEP 4: VERIFY fold_computed_at TIMESTAMPS UNCHANGED
-- =====================================================================

SELECT 'STEP 4: POST-RUN fold_computed_at TIMESTAMPS' AS step,
       MIN(fold_computed_at) AS min_computed_at,
       MAX(fold_computed_at) AS max_computed_at
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz;

-- =====================================================================
-- STEP 5: VERIFY PROPERTY DISTRIBUTION UNCHANGED
-- =====================================================================

SELECT 'STEP 5: POST-RUN PROPERTY DISTRIBUTION' AS step,
       props->>'fold_state' AS fold_state,
       COUNT(*) AS property_count
FROM state.fold_state_snapshot fss,
     LATERAL jsonb_array_elements(fss.folded_properties) AS props
WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY props->>'fold_state'
ORDER BY fold_state;

-- =====================================================================
-- STEP 6: VERIFY UPSTREAM COUNTS UNCHANGED
-- =====================================================================

SELECT 'STEP 6: POST-RUN UPSTREAM COUNTS' AS step,
       (SELECT COUNT(*) FROM raw.raw_event) AS raw_count,
       (SELECT COUNT(*) FROM runtime.evidence) AS evidence_count,
       (SELECT COUNT(*) FROM runtime.assertion) AS assertion_count;

-- =====================================================================
-- STEP 7: VERIFY SUBJECT FOLD STATUS DISTRIBUTION
-- =====================================================================

SELECT 'STEP 7: SUBJECT FOLD STATUS' AS step,
       fold_status AS subject_fold_status,
       COUNT(*) AS subject_count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY fold_status
ORDER BY fold_status;

-- =====================================================================
-- STEP 8: VERIFY SUBJECT DISTRIBUTION BY TYPE
-- =====================================================================

SELECT 'STEP 8: SUBJECT DISTRIBUTION BY TYPE' AS step,
       subject_type,
       COUNT(DISTINCT subject_id) AS subject_count
FROM state.fold_state_snapshot
WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz
GROUP BY subject_type
ORDER BY subject_type;

-- =====================================================================
-- STEP 9: IDEMPOTENCY VALIDATION SUMMARY
-- =====================================================================
-- Expected results for STEP 4J PASS:
--   Fold Run #2 returns:
--     fold_snapshot_count: 51
--     total_property_states: 177
--     established_count: 107
--     unreported_count: 70
--     new_snapshots_inserted: 0 ← KEY: No new inserts
--     deterministic_replays: 51
--     replay_mismatches: 0 ← KEY: No mismatches
--
--   STEP 3: snapshot_count_after = 51 (unchanged)
--   STEP 4: fold_computed_at timestamps identical (unchanged)
--   STEP 5: Property distribution identical (ESTABLISHED: 107, UNREPORTED: 70)
--   STEP 6: Upstream counts identical (raw: 169, evidence: 107, assertion: 107)
--   STEP 7: Subject fold status unchanged
--   STEP 8: Subject distribution unchanged

-- =====================================================================
-- SUMMARY FOR VALIDATION
-- =====================================================================

SELECT
  'IDEMPOTENCY_CHECK' AS validation_type,
  'PRE_RUN' AS phase,
  51 AS expected_snapshot_count,
  177 AS expected_total_properties,
  107 AS expected_established,
  70 AS expected_unreported,
  0 AS expected_new_inserts,
  51 AS expected_deterministic_replays,
  0 AS expected_replay_mismatches
UNION ALL
SELECT
  'IDEMPOTENCY_CHECK' AS validation_type,
  'POST_RUN' AS phase,
  (SELECT COUNT(*) FROM state.fold_state_snapshot WHERE decision_horizon = '2026-06-20 10:45:00+00'::timestamptz),
  (SELECT COUNT(*) FROM state.fold_state_snapshot fss, LATERAL jsonb_array_elements(fss.folded_properties) AS props WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz),
  (SELECT COUNT(*) FROM state.fold_state_snapshot fss, LATERAL jsonb_array_elements(fss.folded_properties) AS props WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND props->>'fold_state' = 'ESTABLISHED'),
  (SELECT COUNT(*) FROM state.fold_state_snapshot fss, LATERAL jsonb_array_elements(fss.folded_properties) AS props WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'::timestamptz AND props->>'fold_state' = 'UNREPORTED'),
  0 AS expected_new_inserts,
  51 AS expected_deterministic_replays,
  0 AS expected_replay_mismatches;
