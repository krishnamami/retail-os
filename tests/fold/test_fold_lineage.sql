-- =====================================================================
-- Fold Test Fixtures: Lineage Validation
-- =====================================================================
-- Purpose: Verify complete lineage chain Fold → Assertion → Evidence → Raw
-- =====================================================================

-- =====================================================================
-- Test 1: Fold basis_assertion_ids Resolve to Assertion
-- =====================================================================

SELECT 'TEST: Fold → Assertion Lineage' AS test_name;

WITH fold_assertions AS (
  SELECT
    fss.subject_type, fss.subject_id,
    unnest(fss.basis_assertion_ids) AS assertion_id
  FROM state.fold_state_snapshot fss
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
),
missing_assertions AS (
  SELECT fa.assertion_id
  FROM fold_assertions fa
  WHERE NOT EXISTS (
    SELECT 1 FROM runtime.assertion a WHERE a.assertion_id = fa.assertion_id
  )
)
SELECT
  COUNT(*) AS orphan_assertion_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: All basis Assertions exist'
       ELSE 'FAIL: ' || COUNT(*) || ' orphan Assertion IDs'
  END AS status
FROM missing_assertions;

-- =====================================================================
-- Test 2: Assertion source_evidence_id Resolves to Evidence
-- =====================================================================

SELECT 'TEST: Assertion → Evidence Lineage' AS test_name;

WITH missing_evidence AS (
  SELECT a.assertion_id
  FROM runtime.assertion a
  WHERE NOT EXISTS (
    SELECT 1 FROM runtime.evidence e WHERE e.evidence_id = a.source_evidence_id
  )
)
SELECT
  COUNT(*) AS orphan_evidence_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: All source Evidence exists'
       ELSE 'FAIL: ' || COUNT(*) || ' Assertions reference missing Evidence'
  END AS status
FROM missing_evidence;

-- =====================================================================
-- Test 3: Evidence raw_event_id Resolves to Raw
-- =====================================================================

SELECT 'TEST: Evidence → Raw Lineage' AS test_name;

WITH missing_raw AS (
  SELECT e.evidence_id
  FROM runtime.evidence e
  WHERE NOT EXISTS (
    SELECT 1 FROM raw.raw_event r WHERE r.raw_event_id = e.raw_event_id
  )
)
SELECT
  COUNT(*) AS orphan_raw_count,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: All Raw events exist'
       ELSE 'FAIL: ' || COUNT(*) || ' Evidence references missing Raw events'
  END AS status
FROM missing_raw;

-- =====================================================================
-- Test 4: Complete Fold → Assertion → Evidence → Raw Chain
-- =====================================================================

SELECT 'TEST: Complete Lineage Chain' AS test_name;

WITH fold_chain AS (
  SELECT
    fss.subject_type, fss.subject_id,
    unnest(fss.basis_assertion_ids) AS assertion_id
  FROM state.fold_state_snapshot fss
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
),
with_evidence AS (
  SELECT
    fc.subject_type, fc.subject_id, fc.assertion_id,
    a.source_evidence_id
  FROM fold_chain fc
  INNER JOIN runtime.assertion a ON a.assertion_id = fc.assertion_id
),
with_raw AS (
  SELECT
    we.subject_type, we.subject_id, we.assertion_id,
    we.source_evidence_id, e.raw_event_id
  FROM with_evidence we
  INNER JOIN runtime.evidence e ON e.evidence_id = we.source_evidence_id
),
complete_chain AS (
  SELECT
    wr.subject_type, wr.subject_id, wr.assertion_id,
    wr.source_evidence_id, wr.raw_event_id,
    CASE WHEN EXISTS (SELECT 1 FROM raw.raw_event r WHERE r.raw_event_id = wr.raw_event_id)
      THEN 'COMPLETE'
      ELSE 'BROKEN'
    END AS chain_status
  FROM with_raw wr
)
SELECT
  COUNT(*) AS total_chain_links,
  COUNT(CASE WHEN chain_status = 'COMPLETE' THEN 1 END) AS complete_chains,
  CASE WHEN COUNT(*) = COUNT(CASE WHEN chain_status = 'COMPLETE' THEN 1 END)
    THEN 'PASS: All lineage chains complete'
    ELSE 'FAIL: Broken lineage detected'
  END AS status
FROM complete_chain;

-- =====================================================================
-- Test 5: Fold Basis IDs Match Property Basis IDs
-- =====================================================================

SELECT 'TEST: Fold Basis = Union of Property Bases' AS test_name;

WITH fold_level_basis AS (
  SELECT
    subject_type, subject_id,
    basis_assertion_ids AS fold_basis
  FROM state.fold_state_snapshot
  WHERE decision_horizon = '2026-06-20 10:45:00+00'
),
property_level_basis AS (
  SELECT
    subject_type, subject_id,
    array_agg(DISTINCT elem ORDER BY elem)
    FILTER (WHERE elem IS NOT NULL) AS property_basis
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props,
       LATERAL jsonb_array_elements(props->'basis_assertion_ids') AS elem
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
  GROUP BY subject_type, subject_id
),
basis_comparison AS (
  SELECT
    flb.subject_type, flb.subject_id,
    array_length(flb.fold_basis, 1) AS fold_basis_count,
    array_length(plb.property_basis, 1) AS property_basis_count,
    CASE WHEN flb.fold_basis = plb.property_basis
      THEN 'MATCH'
      ELSE 'MISMATCH'
    END AS basis_alignment
  FROM fold_level_basis flb
  LEFT JOIN property_level_basis plb
    ON flb.subject_type = plb.subject_type
    AND flb.subject_id = plb.subject_id
)
SELECT
  COUNT(*) AS subjects_checked,
  COUNT(CASE WHEN basis_alignment = 'MATCH' THEN 1 END) AS matching_subjects,
  CASE WHEN COUNT(*) = COUNT(CASE WHEN basis_alignment = 'MATCH' THEN 1 END)
    THEN 'PASS: All Fold basis equals property union'
    ELSE 'FAIL: Basis mismatch detected'
  END AS status
FROM basis_comparison;

-- =====================================================================
-- Test 6: Assertion IDs Match Evidence IDs in Basis
-- =====================================================================

SELECT 'TEST: Assertion → Evidence Mapping in Basis' AS test_name;

WITH fold_chain AS (
  SELECT
    fss.subject_type, fss.subject_id,
    unnest(fss.basis_assertion_ids) AS assertion_id
  FROM state.fold_state_snapshot fss
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
),
with_lineage AS (
  SELECT
    fc.subject_type, fc.subject_id, fc.assertion_id,
    a.source_evidence_id
  FROM fold_chain fc
  INNER JOIN runtime.assertion a ON a.assertion_id = fc.assertion_id
)
SELECT
  COUNT(DISTINCT assertion_id) AS assertions_in_fold_basis,
  COUNT(DISTINCT source_evidence_id) AS distinct_source_evidence,
  'Each Assertion in basis should trace to Evidence' AS note
FROM with_lineage;

-- =====================================================================
-- Test 7: No Duplicate IDs in basis_assertion_ids
-- =====================================================================

SELECT 'TEST: No Duplicate Assertion IDs in Basis' AS test_name;

WITH duplicates_check AS (
  SELECT
    subject_type, subject_id,
    COUNT(*) AS id_count,
    COUNT(DISTINCT unnest) AS distinct_id_count
  FROM state.fold_state_snapshot fss,
       LATERAL unnest(fss.basis_assertion_ids)
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
  GROUP BY subject_type, subject_id
  HAVING COUNT(*) != COUNT(DISTINCT unnest)
)
SELECT
  COUNT(*) AS subjects_with_duplicate_ids,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: No duplicate IDs'
       ELSE 'FAIL: Duplicates detected'
  END AS status
FROM duplicates_check;

-- =====================================================================
-- Test 8: Property Basis IDs Consistency
-- =====================================================================

SELECT 'TEST: Property-Level Basis IDs Validity' AS test_name;

WITH property_bases AS (
  SELECT
    fss.subject_type, fss.subject_id,
    (props->>'property_name') AS property_name,
    (props->'basis_assertion_ids')::uuid[] AS property_basis_ids
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
),
invalid_basis_ids AS (
  SELECT pb.subject_type, pb.subject_id, pb.property_name, pb.property_basis_ids
  FROM property_bases pb
  WHERE EXISTS (
    SELECT 1 FROM UNNEST(pb.property_basis_ids) AS id
    WHERE NOT EXISTS (SELECT 1 FROM runtime.assertion a WHERE a.assertion_id = id)
  )
)
SELECT
  COUNT(*) AS properties_with_invalid_basis,
  CASE WHEN COUNT(*) = 0 THEN 'PASS: All property basis IDs resolve'
       ELSE 'FAIL: Invalid basis IDs detected'
  END AS status
FROM invalid_basis_ids;

-- =====================================================================
-- Test 9: Raw Event Coverage
-- =====================================================================

SELECT 'TEST: Raw Event Coverage in Lineage' AS test_name;

WITH fold_raw_events AS (
  SELECT DISTINCT
    e.raw_event_id
  FROM state.fold_state_snapshot fss,
       LATERAL unnest(fss.basis_assertion_ids) AS assertion_id
  INNER JOIN runtime.assertion a ON a.assertion_id = assertion_id
  INNER JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
)
SELECT
  (SELECT COUNT(*) FROM raw.raw_event) AS total_raw_events,
  COUNT(*) AS raw_events_in_fold,
  CASE WHEN COUNT(*) > 0 THEN 'INFO: Raw events referenced in Fold'
       ELSE 'INFO: No Raw events in corpus'
  END AS status
FROM fold_raw_events;

-- =====================================================================
-- Test 10: Lineage Chain Depth Verification
-- =====================================================================

SELECT 'TEST: Lineage Chain Depth' AS test_name;

WITH chain_depth AS (
  SELECT
    fss.subject_type, fss.subject_id,
    unnest(fss.basis_assertion_ids) AS assertion_id
  FROM state.fold_state_snapshot fss
  WHERE fss.decision_horizon = '2026-06-20 10:45:00+00'
),
full_chain AS (
  SELECT
    cd.subject_type, cd.subject_id, cd.assertion_id,
    a.assertion_id AS assertion_exists,
    e.evidence_id AS evidence_exists,
    r.raw_event_id AS raw_exists
  FROM chain_depth cd
  LEFT JOIN runtime.assertion a ON a.assertion_id = cd.assertion_id
  LEFT JOIN runtime.evidence e ON e.evidence_id = (SELECT source_evidence_id FROM runtime.assertion WHERE assertion_id = cd.assertion_id)
  LEFT JOIN raw.raw_event r ON r.raw_event_id = (SELECT raw_event_id FROM runtime.evidence WHERE evidence_id = (SELECT source_evidence_id FROM runtime.assertion WHERE assertion_id = cd.assertion_id))
)
SELECT
  COUNT(*) AS links_checked,
  COUNT(CASE WHEN assertion_exists IS NOT NULL THEN 1 END) AS assertions_resolved,
  COUNT(CASE WHEN evidence_exists IS NOT NULL THEN 1 END) AS evidence_resolved,
  COUNT(CASE WHEN raw_exists IS NOT NULL THEN 1 END) AS raw_resolved,
  CASE WHEN COUNT(*) = COUNT(CASE WHEN raw_exists IS NOT NULL THEN 1 END)
    THEN 'PASS: Complete Fold→Assertion→Evidence→Raw chains'
    ELSE 'FAIL: Incomplete lineage detected'
  END AS status
FROM full_chain;

-- =====================================================================
-- Test Summary
-- =====================================================================

SELECT 'Lineage validation tests completed. All chains must resolve completely.' AS summary;
