-- ============================================================================
-- D4I_005 step 1 verification -- READ ONLY. ONE STATEMENT. ONE GRID.
-- ============================================================================
-- Section D is the one that matters for the demo. technical_review_result is
-- ESTABLISHED on 9 SKUs and reads PASS on all of them -- but 8 of those rest
-- on a COALESCE fallback rather than an asserted value. A readiness rule that
-- treats a defaulted PASS as an observed one would declare eight SKUs
-- technically approved on the strength of a constant in the mapping code.
-- This is the number the whole provenance phase exists to surface.
--
-- READ ONLY.
-- ============================================================================

WITH H AS (SELECT '2026-07-31 00:00:00+00'::timestamptz AS h),
pp AS MATERIALIZED (
    SELECT * FROM runtime.property_provenance_at((SELECT h FROM H))
),
secA AS (
    SELECT 'A'::text AS section, 1 AS ord, 'property states'::text AS item,
           'must equal the fold'::text AS detail,
           (SELECT count(*) FROM pp)::text AS actual, '586'::text AS expected,
           CASE WHEN (SELECT count(*) FROM pp) = 586 THEN 'ok' ELSE 'FAIL' END
             AS verdict
    UNION ALL
    SELECT 'A', 2, 'ESTABLISHED', '',
           (SELECT count(*) FROM pp WHERE fold_state='ESTABLISHED')::text, '257',
           CASE WHEN (SELECT count(*) FROM pp
                      WHERE fold_state='ESTABLISHED') = 257
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 3, 'UNREPORTED -- no basis, so no provenance', '',
           (SELECT count(*) FROM pp WHERE fold_state='UNREPORTED')::text, '329',
           CASE WHEN (SELECT count(*) FROM pp
                      WHERE fold_state='UNREPORTED') = 329
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 4, 'ESTABLISHED but no provenance resolved',
           'every established property must trace to evidence',
           (SELECT count(*) FROM pp WHERE fold_state='ESTABLISHED'
              AND value_provenance IS NULL)::text, '0',
           CASE WHEN (SELECT count(*) FROM pp WHERE fold_state='ESTABLISHED'
                        AND value_provenance IS NULL) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 5, 'UNREPORTED but carrying provenance',
           'a contradiction if it happens',
           (SELECT count(*) FROM pp WHERE fold_state='UNREPORTED'
              AND value_provenance IS NOT NULL)::text, '0',
           CASE WHEN (SELECT count(*) FROM pp WHERE fold_state='UNREPORTED'
                        AND value_provenance IS NOT NULL) = 0
                THEN 'ok' ELSE 'FAIL' END
),
secB AS (
    SELECT 'B'::text, row_number() OVER (ORDER BY COALESCE(value_provenance,'~'))::int,
           COALESCE(value_provenance, '<no basis>')::text,
           'resolved property states'::text,
           count(*)::text,
           ('basis rows ' || sum(basis_count)::text)::text,
           'info'::text
    FROM   pp GROUP BY value_provenance
),
secC AS (
    SELECT 'C'::text, 1, 'established properties resting on any default'::text,
           'weakest link -- these are not fully observed'::text,
           (SELECT count(*) FROM pp
            WHERE fold_state='ESTABLISHED'
              AND value_provenance='DEFAULTED')::text, '39',
           CASE WHEN (SELECT count(*) FROM pp WHERE fold_state='ESTABLISHED'
                        AND value_provenance='DEFAULTED') = 39
                THEN 'ok -- matches the 39 defaulted evidence rows'
                ELSE 'info -- inspect' END
    UNION ALL
    SELECT 'C', 2, 'mixed-basis properties',
           'part observed, part defaulted',
           (SELECT count(*) FROM pp
            WHERE observed_count > 0 AND defaulted_count > 0)::text, '',
           'info'
),
secD AS (
    SELECT 'D'::text, row_number() OVER (ORDER BY pp.property_name,
                                                  pp.subject_id)::int,
           pp.subject_id::text,
           pp.property_name::text,
           (pp.resolved_value #>> '{}')::text,
           COALESCE(pp.value_provenance, '<none>')::text,
           CASE WHEN pp.value_provenance = 'DEFAULTED'
                THEN 'DEFAULTED -- no source asserted this'
                ELSE 'observed' END::text
    FROM   pp
    WHERE  pp.property_name IN ('technical_review_result',
                                'sap_con_load_status','sap_prd_load_status',
                                'intent_classification')
      AND  pp.fold_state = 'ESTABLISHED'
),
body AS (
    SELECT * FROM secA UNION ALL SELECT * FROM secB
    UNION ALL SELECT * FROM secC UNION ALL SELECT * FROM secD
)
SELECT section, ord AS seq, item, detail, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM body
                  WHERE verdict NOT IN ('ok','info','observed')
                    AND verdict NOT LIKE 'ok --%'
                    AND verdict NOT LIKE 'info --%'
                    AND verdict NOT LIKE 'DEFAULTED --%') = 0
            THEN 'PROVENANCE VIEW OK -- readiness can now see how each fact came to exist'
            ELSE 'STOP' END AS overall
FROM   body
ORDER  BY section, ord;
