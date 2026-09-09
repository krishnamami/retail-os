-- ============================================================================
-- D4I_003c step 3A verification -- READ ONLY. ONE STATEMENT. ONE GRID.
-- ============================================================================
-- Confirms the live column matches the approved design exactly, and that
-- nothing else about runtime.evidence moved. Anything other than 'ok' is a
-- stop: do not run the projection or the backfill.
--
-- The DEFAULT check is not a formality. A column that quietly acquired
-- DEFAULT 'OBSERVED' would satisfy every other check here and then
-- manufacture certainty on the first insert that forgot provenance.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH col AS (
    SELECT c.data_type, c.udt_name, c.character_maximum_length AS len,
           c.is_nullable, c.column_default, c.ordinal_position
    FROM   information_schema.columns c
    WHERE  c.table_schema = 'runtime' AND c.table_name = 'evidence'
      AND  c.column_name = 'value_provenance'
),
chk AS (
    SELECT con.conname::text AS name, pg_get_constraintdef(con.oid) AS def
    FROM   pg_constraint con
    JOIN   pg_class cl ON cl.oid = con.conrelid
    JOIN   pg_namespace ns ON ns.oid = cl.relnamespace
    WHERE  ns.nspname = 'runtime' AND cl.relname = 'evidence'
      AND  con.contype = 'c'
      AND  con.conname = 'evidence_value_provenance_valid'
),
report AS (
    SELECT 1 AS ord, 'column exists'::text AS check_name,
           (SELECT count(*) FROM col)::text AS actual, '1'::text AS expected,
           CASE WHEN (SELECT count(*) FROM col) = 1 THEN 'ok' ELSE 'FAIL' END
             AS verdict
    UNION ALL
    SELECT 2, 'underlying type',
           COALESCE((SELECT udt_name FROM col), '<absent>'), 'varchar',
           CASE WHEN (SELECT udt_name FROM col) = 'varchar'
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 3, 'character maximum length',
           COALESCE((SELECT len::text FROM col), '<absent>'), '32',
           CASE WHEN (SELECT len FROM col) = 32 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 4, 'nullable',
           COALESCE((SELECT is_nullable FROM col), '<absent>'), 'YES',
           CASE WHEN (SELECT is_nullable FROM col) = 'YES'
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 5, 'no DEFAULT -- a forgetful writer must fail, not assume',
           COALESCE((SELECT column_default FROM col), '<none>'), '<none>',
           CASE WHEN (SELECT column_default FROM col) IS NULL
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 6, 'CHECK constraint exists',
           (SELECT count(*) FROM chk)::text, '1',
           CASE WHEN (SELECT count(*) FROM chk) = 1 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 7, 'CHECK vocabulary',
           COALESCE((SELECT def FROM chk), '<absent>'),
           'OBSERVED / DEFAULTED / DERIVED',
           CASE WHEN (SELECT def FROM chk) LIKE '%OBSERVED%'
                 AND (SELECT def FROM chk) LIKE '%DEFAULTED%'
                 AND (SELECT def FROM chk) LIKE '%DERIVED%'
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 8, 'no row classified yet',
           (SELECT count(value_provenance) FROM runtime.evidence)::text, '0',
           CASE WHEN (SELECT count(value_provenance) FROM runtime.evidence) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 9, 'row count untouched',
           (SELECT count(*) FROM runtime.evidence)::text, '143',
           CASE WHEN (SELECT count(*) FROM runtime.evidence) = 143
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 10, 'simulator_classification untouched',
           (SELECT count(simulator_classification)
            FROM runtime.evidence)::text, '36',
           CASE WHEN (SELECT count(simulator_classification)
                      FROM runtime.evidence) = 36 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 11, 'total columns on runtime.evidence',
           (SELECT count(*)::text FROM information_schema.columns
            WHERE table_schema='runtime' AND table_name='evidence'), '21',
           CASE WHEN (SELECT count(*) FROM information_schema.columns
                      WHERE table_schema='runtime' AND table_name='evidence')
                     = 21 THEN 'ok' ELSE 'FAIL' END
)
SELECT ord AS seq, check_name, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM report WHERE verdict <> 'ok') = 0
            THEN 'STEP 3A OK -- proceed to 3B'
            ELSE 'STOP -- ' || (SELECT count(*) FROM report
                                WHERE verdict <> 'ok')::text
                 || ' failure(s), do not backfill' END AS overall
FROM   report
ORDER  BY ord;
