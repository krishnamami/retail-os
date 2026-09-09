-- ============================================================================
-- D4I_003c step 3F -- prove writers MUST declare provenance. ONE STATEMENT.
-- ============================================================================
-- THIS FILE ENDS IN A DELIBERATE ERROR. That is the mechanism, not a fault.
--
-- The five cases below insert real rows into runtime.evidence to find out what
-- the database actually refuses. Asserting that from the catalogue would only
-- re-read the constraint definition; the question is whether the constraint
-- bites. So the rows are written, the outcomes are collected, and the block
-- ends with RAISE EXCEPTION carrying the results as its message. The
-- exception aborts the transaction, which rolls back every test insert.
--
-- Nothing can persist. Not by cleanup -- by the transaction never committing.
-- A DELETE-based tidy-up would leave residue if the block died early; an
-- abort cannot. Read the results in the error message, then run
-- D4I_003c_05v_verify_not_null.sql: rows must read 143 and the ZZ_3F check
-- must read 0.
--
-- WHAT EACH CASE ESTABLISHES
--   1  insert omitting value_provenance      must be REJECTED  (not_null)
--   2  insert with an invalid vocabulary     must be REJECTED  (check)
--   3  OBSERVED                              must SUCCEED
--   4  DEFAULTED                             must SUCCEED
--   5  DERIVED                               must SUCCEED at schema level,
--      even though no deployed mapping produces one yet -- D4I_004 or a
--      future derivation must not be blocked by a vocabulary that was
--      narrowed to whatever happened to exist in September.
--
-- Case 1 is the one that matters. Before step 3E it would have succeeded, and
-- the row would have been indistinguishable from a row whose provenance was
-- genuinely established. That is the failure this phase exists to remove.
--
-- Each case runs in its own subtransaction, so a rejection is caught and
-- reported rather than ending the run at the first expected failure.
-- ============================================================================

DO $test$
DECLARE
    v_raw    uuid;
    v_rows   integer;
    results  text := '';
BEGIN
    SELECT raw_event_id INTO v_raw FROM raw.raw_event ORDER BY raw_event_id
    LIMIT 1;
    IF v_raw IS NULL THEN
        RAISE EXCEPTION 'no raw event available to satisfy the foreign key';
    END IF;

    -- 1 --------------------------------------------------------------------
    BEGIN
        INSERT INTO runtime.evidence
            (raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
             property_name, asserted_value, value_type, source_system,
             occurred_at, recorded_at, arrival_at)
        VALUES (v_raw, 'ZZ_3F_1', 'test', 'test', 'T-1', 'p', 'v', 'string',
                'test', now(), now(), now());
        results := results || E'\n  1  omitted provenance       SUCCEEDED'
                 || '   <-- FAIL: a writer could still omit it';
    EXCEPTION
        WHEN not_null_violation THEN
            results := results || E'\n  1  omitted provenance       rejected'
                     || ' (not_null_violation)      ok';
        WHEN others THEN
            results := results || E'\n  1  omitted provenance       rejected ('
                     || SQLSTATE || ')  UNEXPECTED CODE';
    END;

    -- 2 --------------------------------------------------------------------
    BEGIN
        INSERT INTO runtime.evidence
            (raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
             property_name, asserted_value, value_type, source_system,
             occurred_at, recorded_at, arrival_at, value_provenance)
        VALUES (v_raw, 'ZZ_3F_2', 'test', 'test', 'T-2', 'p', 'v', 'string',
                'test', now(), now(), now(), 'PROBABLY_FINE');
        results := results || E'\n  2  invalid vocabulary       SUCCEEDED'
                 || '   <-- FAIL: the CHECK is not biting';
    EXCEPTION
        WHEN check_violation THEN
            results := results || E'\n  2  invalid vocabulary       rejected'
                     || ' (check_violation)         ok';
        WHEN others THEN
            results := results || E'\n  2  invalid vocabulary       rejected ('
                     || SQLSTATE || ')  UNEXPECTED CODE';
    END;

    -- 3, 4, 5 --------------------------------------------------------------
    BEGIN
        INSERT INTO runtime.evidence
            (raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
             property_name, asserted_value, value_type, source_system,
             occurred_at, recorded_at, arrival_at, value_provenance)
        VALUES (v_raw, 'ZZ_3F_3', 'test', 'test', 'T-3', 'p', 'v', 'string',
                'test', now(), now(), now(), 'OBSERVED');
        results := results || E'\n  3  OBSERVED                 accepted'
                 || '                            ok';
    EXCEPTION WHEN others THEN
        results := results || E'\n  3  OBSERVED                 REJECTED ('
                 || SQLSTATE || ')  FAIL';
    END;

    BEGIN
        INSERT INTO runtime.evidence
            (raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
             property_name, asserted_value, value_type, source_system,
             occurred_at, recorded_at, arrival_at, value_provenance)
        VALUES (v_raw, 'ZZ_3F_4', 'test', 'test', 'T-4', 'p', 'v', 'string',
                'test', now(), now(), now(), 'DEFAULTED');
        results := results || E'\n  4  DEFAULTED                accepted'
                 || '                            ok';
    EXCEPTION WHEN others THEN
        results := results || E'\n  4  DEFAULTED                REJECTED ('
                 || SQLSTATE || ')  FAIL';
    END;

    BEGIN
        INSERT INTO runtime.evidence
            (raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
             property_name, asserted_value, value_type, source_system,
             occurred_at, recorded_at, arrival_at, value_provenance)
        VALUES (v_raw, 'ZZ_3F_5', 'test', 'test', 'T-5', 'p', 'v', 'string',
                'test', now(), now(), now(), 'DERIVED');
        results := results || E'\n  5  DERIVED                  accepted'
                 || '                            ok';
    EXCEPTION WHEN others THEN
        results := results || E'\n  5  DERIVED                  REJECTED ('
                 || SQLSTATE || ')  FAIL';
    END;

    SELECT count(*) INTO v_rows FROM runtime.evidence;

    RAISE EXCEPTION '%',
        'D4I_003c STEP 3F RESULTS -- DELIBERATE ROLLBACK'
        || results
        || E'\n\n  rows visible inside the test: ' || v_rows::text
        || ' (143 plus the accepted inserts)'
        || E'\n  Those inserts are discarded when this exception aborts the'
        || E'\n  transaction. Re-run D4I_003c_05v_verify_not_null.sql: rows'
        || E'\n  must read 143 and the ZZ_3F check must read 0.';
END
$test$;
