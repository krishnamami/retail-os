-- ============================================================================
-- D4I_003c step 3E verification -- READ ONLY. ONE STATEMENT. ONE GRID.
-- ============================================================================
-- Confirms the final live contract, and that nothing shifted while it was
-- being applied. Also usable after D4I_003c_06 to prove the failure-behaviour
-- test left no residue: rows must read 143 again.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH col AS (
    SELECT c.udt_name, c.character_maximum_length AS len, c.is_nullable,
           c.column_default
    FROM   information_schema.columns c
    WHERE  c.table_schema='runtime' AND c.table_name='evidence'
      AND  c.column_name='value_provenance'
),
report AS (
    SELECT 1 AS ord, 'value_provenance is NOT NULL'::text AS check_name,
           COALESCE((SELECT is_nullable FROM col), '<absent>')::text AS actual,
           'NO'::text AS expected,
           CASE WHEN (SELECT is_nullable FROM col) = 'NO'
                THEN 'ok' ELSE 'FAIL' END::text AS verdict
    UNION ALL
    SELECT 2, 'still varchar(32)',
           COALESCE((SELECT udt_name || '(' || len::text || ')' FROM col),
                    '<absent>'), 'varchar(32)',
           CASE WHEN (SELECT udt_name FROM col) = 'varchar'
                 AND (SELECT len FROM col) = 32 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 3, 'still no DEFAULT -- NOT NULL must not be softened by one',
           COALESCE((SELECT column_default FROM col), '<none>'), '<none>',
           CASE WHEN (SELECT column_default FROM col) IS NULL
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 4, 'CHECK constraint still present',
           (SELECT count(*)::text FROM pg_constraint con
            JOIN pg_class cl ON cl.oid=con.conrelid
            JOIN pg_namespace ns ON ns.oid=cl.relnamespace
            WHERE ns.nspname='runtime' AND cl.relname='evidence'
              AND con.conname='evidence_value_provenance_valid'), '1',
           CASE WHEN (SELECT count(*) FROM pg_constraint con
                      JOIN pg_class cl ON cl.oid=con.conrelid
                      JOIN pg_namespace ns ON ns.oid=cl.relnamespace
                      WHERE ns.nspname='runtime' AND cl.relname='evidence'
                        AND con.conname='evidence_value_provenance_valid') = 1
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 5, 'rows -- 143 again after any test insert rolled back',
           (SELECT count(*) FROM runtime.evidence)::text, '143',
           CASE WHEN (SELECT count(*) FROM runtime.evidence) = 143
                THEN 'ok' ELSE 'FAIL -- test residue in runtime.evidence' END
    UNION ALL
    SELECT 6, 'OBSERVED',
           (SELECT count(*) FROM runtime.evidence
            WHERE value_provenance='OBSERVED')::text, '104',
           CASE WHEN (SELECT count(*) FROM runtime.evidence
                      WHERE value_provenance='OBSERVED') = 104
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 7, 'DEFAULTED',
           (SELECT count(*) FROM runtime.evidence
            WHERE value_provenance='DEFAULTED')::text, '39',
           CASE WHEN (SELECT count(*) FROM runtime.evidence
                      WHERE value_provenance='DEFAULTED') = 39
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 8, 'DERIVED',
           (SELECT count(*) FROM runtime.evidence
            WHERE value_provenance='DERIVED')::text, '0',
           CASE WHEN (SELECT count(*) FROM runtime.evidence
                      WHERE value_provenance='DERIVED') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 9, 'distinct mapping_id',
           (SELECT count(DISTINCT mapping_id) FROM runtime.evidence)::text,
           '22',
           CASE WHEN (SELECT count(DISTINCT mapping_id)
                      FROM runtime.evidence) = 22 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 10, 'simulator_classification still 36 / 107',
           (SELECT count(simulator_classification)::text || ' / '
                || count(*) FILTER (WHERE simulator_classification IS NULL)::text
            FROM runtime.evidence), '36 / 107',
           CASE WHEN (SELECT count(simulator_classification)
                      FROM runtime.evidence) = 36
                 AND (SELECT count(*) FROM runtime.evidence
                      WHERE simulator_classification IS NULL) = 107
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 11, 'no test mapping_id survived',
           (SELECT count(*) FROM runtime.evidence
            WHERE mapping_id LIKE 'ZZ_3F%')::text, '0',
           CASE WHEN (SELECT count(*) FROM runtime.evidence
                      WHERE mapping_id LIKE 'ZZ_3F%') = 0
                THEN 'ok' ELSE 'FAIL -- delete the residue' END
)
SELECT ord AS seq, check_name, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM report WHERE verdict <> 'ok') = 0
            THEN 'FINAL CONTRACT LIVE -- varchar(32) NOT NULL, no default, '
                 || 'vocabulary enforced'
            ELSE 'STOP -- ' || (SELECT count(*) FROM report
                                WHERE verdict <> 'ok')::text || ' failure(s)'
       END AS overall
FROM   report
ORDER  BY ord;
