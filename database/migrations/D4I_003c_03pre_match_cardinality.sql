-- ============================================================================
-- D4I_003c step 3C pre-check -- match cardinality. READ ONLY. ONE STATEMENT.
-- ============================================================================
-- WHY THIS RUNS BEFORE THE UPDATE
--   The backfill is an UPDATE ... FROM. If one evidence row matched two
--   projection rows, PostgreSQL would pick one of them arbitrarily and report
--   success -- no error, no warning, a silently non-deterministic backfill of
--   a field whose whole purpose is to be trustworthy. The join key is
--   (raw_event_id, mapping_id), which runtime.evidence enforces as UNIQUE via
--   evidence_lineage_identity_unique, but the projection is a function and
--   carries no such constraint. So the cardinality is measured, not assumed.
--
--   Both directions are checked. A projection row matching no evidence row
--   would mean the backfill leaves rows unclassified; an evidence row
--   matching no projection row would mean the same thing from the other side.
--
-- Anything other than 'ok' is a stop. Do not run the backfill.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH p AS MATERIALIZED (SELECT * FROM runtime.evidence_projection_v2()),
e AS MATERIALIZED (
    SELECT raw_event_id, mapping_id, value_provenance FROM runtime.evidence
),
per_evidence AS (
    SELECT e.raw_event_id, e.mapping_id,
           (SELECT count(*) FROM p
            WHERE p.raw_event_id = e.raw_event_id
              AND p.mapping_id   = e.mapping_id) AS matches
    FROM   e
),
per_projection AS (
    SELECT p.raw_event_id, p.mapping_id,
           (SELECT count(*) FROM e
            WHERE e.raw_event_id = p.raw_event_id
              AND e.mapping_id   = p.mapping_id) AS matches
    FROM   p
),
report AS (
    SELECT 1 AS ord, 'evidence rows'::text AS check_name,
           (SELECT count(*) FROM e)::text AS actual, '143'::text AS expected,
           CASE WHEN (SELECT count(*) FROM e) = 143 THEN 'ok' ELSE 'FAIL' END
             AS verdict
    UNION ALL
    SELECT 2, 'projection v2 rows', (SELECT count(*) FROM p)::text, '143',
           CASE WHEN (SELECT count(*) FROM p) = 143 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 3, 'evidence rows matching EXACTLY ONE projection row',
           (SELECT count(*) FROM per_evidence WHERE matches = 1)::text, '143',
           CASE WHEN (SELECT count(*) FROM per_evidence WHERE matches = 1) = 143
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 4, 'evidence rows matching NO projection row',
           (SELECT count(*) FROM per_evidence WHERE matches = 0)::text, '0',
           CASE WHEN (SELECT count(*) FROM per_evidence WHERE matches = 0) = 0
                THEN 'ok' ELSE 'FAIL -- these would stay unclassified' END
    UNION ALL
    SELECT 5, 'evidence rows matching MORE THAN ONE projection row',
           (SELECT count(*) FROM per_evidence WHERE matches > 1)::text, '0',
           CASE WHEN (SELECT count(*) FROM per_evidence WHERE matches > 1) = 0
                THEN 'ok'
                ELSE 'FAIL -- UPDATE ... FROM would pick one arbitrarily' END
    UNION ALL
    SELECT 6, 'projection rows matching NO evidence row',
           (SELECT count(*) FROM per_projection WHERE matches = 0)::text, '0',
           CASE WHEN (SELECT count(*) FROM per_projection WHERE matches = 0) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 7, 'projection rows matching MORE THAN ONE evidence row',
           (SELECT count(*) FROM per_projection WHERE matches > 1)::text, '0',
           CASE WHEN (SELECT count(*) FROM per_projection WHERE matches > 1) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 8, 'duplicate (raw_event_id, mapping_id) within the projection',
           (SELECT count(*) FROM (SELECT raw_event_id, mapping_id FROM p
                                  GROUP BY 1,2 HAVING count(*) > 1) d)::text,
           '0',
           CASE WHEN (SELECT count(*) FROM (SELECT raw_event_id, mapping_id
                                            FROM p GROUP BY 1,2
                                            HAVING count(*) > 1) d) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 9, 'rows already classified (backfill should be the first write)',
           (SELECT count(value_provenance) FROM e)::text, '0',
           CASE WHEN (SELECT count(value_provenance) FROM e) = 0
                THEN 'ok' ELSE 'info -- backfill already ran; it is idempotent'
           END
)
SELECT ord AS seq, check_name, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM report
                  WHERE verdict NOT IN ('ok')
                    AND verdict NOT LIKE 'info%') = 0
            THEN 'CARDINALITY PROVEN -- backfill is deterministic'
            ELSE 'STOP -- do not run the backfill' END AS overall
FROM   report
ORDER  BY ord;
