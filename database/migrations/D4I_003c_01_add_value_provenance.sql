-- ============================================================================
-- D4I_003c step 3A -- add runtime.evidence.value_provenance
-- ONE STATEMENT. Deliberately.
-- ============================================================================
-- WHAT THIS ADDS
--   value_provenance varchar(32) NULL, with a CHECK restricting it to
--   OBSERVED / DEFAULTED / DERIVED. Nothing is backfilled here, no value is
--   read or written, and no existing column is touched.
--
-- WHY THERE IS NO DEFAULT
--   A DEFAULT 'OBSERVED' would mean that any future writer which forgets
--   provenance silently manufactures certainty -- the exact failure this
--   field exists to prevent. Missing provenance must eventually be
--   impossible, not quietly assumed. So: no default now, and NOT NULL in
--   step 3E once the backfill has proven every row classified.
--
-- WHY NULLABLE FIRST
--   143 rows already exist. NOT NULL before the backfill would fail, and
--   NOT NULL with a default would fabricate the answer for all 143. Nullable
--   plus CHECK is the only ordering that lets the database refuse a wrong
--   value while still admitting "not yet classified".
--
-- WHY THE CHECK IS SAFE TO ADD NOW
--   A CHECK evaluates to NULL, not false, for a NULL column, so it admits
--   every existing row unchanged while rejecting any wrong vocabulary from
--   the first write onward. No table rewrite, no scan failure.
--
-- WHY varchar(32) AND NOT varchar(16)
--   The vocabulary is closed and the CHECK is what actually enforces it, so
--   width is only headroom. This project has already hit a widening
--   migration blocked by nine dependent views (D4H_004, identity_digest);
--   headroom now is cheaper than a blocked ALTER TYPE later.
--
-- WHAT IS DELIBERATELY NOT TOUCHED
--   simulator_classification. Step 1 measured the two dimensions as
--   independent -- all 36 marked rows are OBSERVED, all 39 DEFAULTED rows
--   are unmarked -- so it is not renamed, repurposed, constrained, aligned,
--   copied, or used to infer provenance.
--
-- Verify with D4I_003c_01v_verify_column.sql before going further.
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

ALTER TABLE runtime.evidence
    ADD COLUMN value_provenance varchar(32) NULL,
    ADD CONSTRAINT evidence_value_provenance_valid
        CHECK (value_provenance IN ('OBSERVED', 'DEFAULTED', 'DERIVED'));
