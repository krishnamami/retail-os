-- ============================================================================
-- D4I_003c step 3C -- backfill value_provenance. ONE STATEMENT.
-- ============================================================================
-- Expected result line: UPDATE 143
--
-- WHAT THIS WRITES
--   One column, on rows that already exist. SET names value_provenance and
--   nothing else, so no value, subject, property, timestamp, mapping_id,
--   lineage or simulator_classification can move -- not by policy, but
--   because they are not in the statement.
--
-- WHERE THE CLASSIFICATION COMES FROM
--   runtime.evidence_projection_v2(), which step 3B proved reduces to the
--   frozen _v1 plus one column, reproduces all fifteen of v1's columns on all
--   143 rows, and classifies 104 / 39 / 0. The classification is therefore
--   derived from mapping identity, the raw event and source-path presence --
--   reproducible from first principles, and re-derivable at any time by
--   calling the function again.
--
-- WHAT IS NOT USED
--   No evidence_id is named. No row is classified by hand. Nothing is
--   inferred from simulator_classification -- step 1 measured the two
--   dimensions as independent, and a backfill that leaned on the marker would
--   have produced 36 / 107 instead of 104 / 39.
--
-- THE JOIN KEY
--   (raw_event_id, mapping_id) -- the identity runtime.evidence itself
--   declares through evidence_lineage_identity_unique. D4I_003c_03pre proves
--   the match is exactly one-to-one in both directions before this runs;
--   without that proof an UPDATE ... FROM with a duplicate match would pick a
--   row arbitrarily and report success.
--
-- IDEMPOTENT
--   Re-running writes the same values. The projection is STABLE and depends
--   only on raw.raw_event, which this statement does not touch.
--
-- Verify with D4I_003c_04_verify.sql. Do not set NOT NULL until it passes.
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

UPDATE runtime.evidence e
SET    value_provenance = p.value_provenance
FROM   runtime.evidence_projection_v2() p
WHERE  p.raw_event_id = e.raw_event_id
  AND  p.mapping_id   = e.mapping_id;
