-- ============================================================================
-- D4I_004 step 2 diagnosis, take 2 -- READ ONLY. ONE STATEMENT.
-- ============================================================================
-- Established already: 257 assertions, zero unpromoted evidence, one-to-one
-- with evidence. So the promotion landed. The fold still aborted on
-- configuration / PRD-001 with a NULL basis_assertion_ids, which is uuid[]
-- NOT NULL.
--
-- Question: does PRD-001 actually have assertions, and if so why did the fold
-- find none? Section A answers it directly by listing every configuration
-- subject with its assertion count. Section C prints how the function
-- enumerates subjects and how it resolves the basis, so the fix is written
-- against the function's own logic rather than my inference from a keyword.
--
-- READ ONLY.
-- ============================================================================

WITH assertions_by_subject AS (
    SELECT a.subject_type, a.subject_id,
           count(*) AS n,
           count(*) FILTER (
             WHERE a.arrival_at <= '2026-06-20 10:45:00+00'::timestamptz)
             AS in_horizon,
           min(a.arrival_at) AS first_arrival,
           max(a.arrival_at) AS last_arrival
    FROM   runtime.assertion a
    GROUP  BY a.subject_type, a.subject_id
),
evidence_by_subject AS (
    SELECT e.subject_type, e.subject_id, count(*) AS n
    FROM   runtime.evidence e GROUP BY e.subject_type, e.subject_id
),
gap AS (
    SELECT COALESCE(ev.subject_type, a.subject_type) AS subject_type,
           COALESCE(ev.subject_id,   a.subject_id)   AS subject_id,
           COALESCE(ev.n, 0) AS evidence_rows,
           COALESCE(a.n, 0)  AS assertion_rows,
           COALESCE(a.in_horizon, 0) AS in_horizon,
           a.last_arrival
    FROM   evidence_by_subject ev
    FULL OUTER JOIN assertions_by_subject a
      ON  a.subject_type = ev.subject_type
     AND  a.subject_id   = ev.subject_id
),
secA AS (
    SELECT 'A'::text AS section,
           row_number() OVER (ORDER BY subject_type, subject_id)::int AS ord,
           (subject_type || ' / ' || subject_id)::text AS item,
           ('evidence ' || evidence_rows::text
             || ' | assertions ' || assertion_rows::text)::text AS detail,
           in_horizon::text AS actual,
           COALESCE(last_arrival::text, '<none>')::text AS expected,
           CASE WHEN in_horizon = 0
                THEN 'NO ASSERTION IN HORIZON -- fold cannot write this subject'
                ELSE 'ok' END::text AS verdict
    FROM   gap
    WHERE  subject_type = 'configuration'
),
secB AS (
    SELECT 'B'::text, 1,
           'subjects with zero assertions inside the horizon'::text,
           'any one of these aborts the fold'::text,
           (SELECT count(*) FROM gap WHERE in_horizon = 0)::text, '0'::text,
           CASE WHEN (SELECT count(*) FROM gap WHERE in_horizon = 0) = 0
                THEN 'ok' ELSE 'FAIL' END::text
    UNION ALL
    SELECT 'B', 2 + row_number() OVER (ORDER BY subject_type, subject_id)::int,
           (subject_type || ' / ' || subject_id),
           ('evidence ' || evidence_rows::text
             || ' | assertions ' || assertion_rows::text),
           in_horizon::text, COALESCE(last_arrival::text, '<none>'),
           'ZERO IN HORIZON'
    FROM   gap WHERE in_horizon = 0
    UNION ALL
    SELECT 'B', 90, 'assertions arriving after the horizon',
           'invisible to a fold at 2026-06-20 10:45',
           (SELECT count(*) FROM runtime.assertion
            WHERE arrival_at > '2026-06-20 10:45:00+00'::timestamptz)::text,
           '0',
           CASE WHEN (SELECT count(*) FROM runtime.assertion
                      WHERE arrival_at
                            > '2026-06-20 10:45:00+00'::timestamptz) = 0
                THEN 'ok' ELSE 'info' END
    UNION ALL
    SELECT 'B', 91, 'latest assertion arrival overall', '',
           (SELECT max(arrival_at)::text FROM runtime.assertion),
           '2026-06-20 10:45:00+00', 'info'
),
secC AS (
    SELECT 'C'::text, row_number() OVER ()::int,
           'fold_snapshot_at_horizon'::text,
           'source line'::text,
           line::text, ''::text, 'info'::text
    FROM (
      SELECT unnest(string_to_array(p.prosrc, E'\n')) AS line
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
      WHERE n.nspname = 'runtime' AND p.proname = 'fold_snapshot_at_horizon'
    ) x
    WHERE line ILIKE '%ON CONFLICT%'   OR line ILIKE '%DO NOTHING%'
       OR line ILIKE '%DO UPDATE%'     OR line ILIKE '%all_basis_ids%'
       OR line ILIKE '%FROM runtime.assertion%'
       OR line ILIKE '%FROM runtime.evidence%'
       OR line ILIKE '%subject_type, subject_id%'
       OR line ILIKE '%array_agg%'     OR line ILIKE '%DISTINCT%'
)
SELECT section, ord AS seq, item, detail, actual, expected, verdict
FROM   (SELECT * FROM secA UNION ALL SELECT * FROM secB
        UNION ALL SELECT * FROM secC) AS d
ORDER  BY section, ord;
