-- ============================================================================
-- D4I_003c step 3D -- post-backfill verification. READ ONLY. ONE STATEMENT.
-- ============================================================================
-- Two questions, and the second matters more than the first.
--
--   Did provenance land correctly?  Sections A and F.
--
--   Did anything else move?  Section B, which re-runs the D4I_003b comparison
--   against the frozen _v1: every semantic column of every row, keyed on
--   (raw_event_id, mapping_id). D4I_003b proved runtime.evidence matched _v1
--   exactly before provenance existed. If it still matches, the backfill
--   changed nothing but the column it named -- and that is a measurement, not
--   an appeal to the UPDATE's SET clause.
--
-- Section C holds simulator_classification to its measured population, 36 and
-- 107. It is a separate dimension and was not to be repaired, normalised or
-- aligned; if it moved, something reached further than it should have.
--
-- Section E lists exactly which facts a future readiness decision must treat
-- carefully: the DEFAULTED rows, by mapping, property and event type.
--
-- Anything other than 'ok' or 'info' is a stop. Do not set NOT NULL.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH v1 AS MATERIALIZED (SELECT * FROM runtime.evidence_projection_v1()),
     v2 AS MATERIALIZED (SELECT * FROM runtime.evidence_projection_v2()),
     ev AS MATERIALIZED (SELECT * FROM runtime.evidence),

-- ---------------------------------------------------------------------------
-- A. provenance population
-- ---------------------------------------------------------------------------
secA AS (
    SELECT 'A'::text AS section, 1 AS ord, 'rows'::text AS item,
           ''::text AS detail,
           (SELECT count(*) FROM ev)::text AS actual, '143'::text AS expected,
           CASE WHEN (SELECT count(*) FROM ev) = 143 THEN 'ok' ELSE 'FAIL' END
             AS verdict
    UNION ALL
    SELECT 'A', 2, 'OBSERVED', '',
           (SELECT count(*) FROM ev WHERE value_provenance='OBSERVED')::text,
           '104',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance='OBSERVED') = 104
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 3, 'DEFAULTED',
           'values no source event asserted',
           (SELECT count(*) FROM ev WHERE value_provenance='DEFAULTED')::text,
           '39',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance='DEFAULTED') = 39
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 4, 'DERIVED', 'no deployed mapping computes a value',
           (SELECT count(*) FROM ev WHERE value_provenance='DERIVED')::text,
           '0',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance='DERIVED') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 5, 'NULL', 'must be zero before NOT NULL can be set',
           (SELECT count(*) FROM ev WHERE value_provenance IS NULL)::text, '0',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance IS NULL) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 6, 'outside the approved vocabulary', '',
           (SELECT count(*) FROM ev WHERE value_provenance IS NOT NULL
              AND value_provenance NOT IN
                  ('OBSERVED','DEFAULTED','DERIVED'))::text, '0',
           CASE WHEN (SELECT count(*) FROM ev WHERE value_provenance IS NOT NULL
                        AND value_provenance NOT IN
                            ('OBSERVED','DEFAULTED','DERIVED')) = 0
                THEN 'ok' ELSE 'FAIL' END
),

-- ---------------------------------------------------------------------------
-- B. semantic immutability against the frozen D4I_003 contract
-- ---------------------------------------------------------------------------
one_sided AS (
    SELECT count(*) AS n FROM (
        SELECT e.raw_event_id FROM ev e
        WHERE NOT EXISTS (SELECT 1 FROM v1 a
                          WHERE a.raw_event_id = e.raw_event_id
                            AND a.mapping_id   = e.mapping_id)
        UNION ALL
        SELECT a.raw_event_id FROM v1 a
        WHERE NOT EXISTS (SELECT 1 FROM ev e
                          WHERE e.raw_event_id = a.raw_event_id
                            AND e.mapping_id   = a.mapping_id)) x
),
drift AS (
    SELECT e.mapping_id, e.raw_event_id
    FROM   ev e
    JOIN   v1 a ON a.raw_event_id = e.raw_event_id
               AND a.mapping_id   = e.mapping_id
    WHERE  e.evidence_type     IS DISTINCT FROM a.evidence_type
       OR  e.subject_type      IS DISTINCT FROM a.subject_type
       OR  e.subject_id        IS DISTINCT FROM a.subject_id
       OR  e.property_name     IS DISTINCT FROM a.property_name
       OR  e.asserted_value    IS DISTINCT FROM a.asserted_value
       OR  e.value_type        IS DISTINCT FROM a.value_type
       OR  e.source_system     IS DISTINCT FROM a.source_system
       OR  e.source_actor_id   IS DISTINCT FROM a.source_actor_id
       OR  e.source_actor_role IS DISTINCT FROM a.source_actor_role
       OR  e.occurred_at       IS DISTINCT FROM a.occurred_at
       OR  e.recorded_at       IS DISTINCT FROM a.recorded_at
       OR  e.arrival_at        IS DISTINCT FROM a.arrival_at
       OR  e.evidence_lineage  IS DISTINCT FROM a.evidence_lineage
),
secB AS (
    SELECT 'B'::text, 1, 'rows on one side only'::text,
           'runtime.evidence vs the frozen v1'::text,
           (SELECT n FROM one_sided)::text, '0'::text,
           CASE WHEN (SELECT n FROM one_sided) = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'B', 2, 'rows disagreeing on any semantic column',
           'value, subject, property, timestamps, lineage',
           (SELECT count(*) FROM drift)::text, '0',
           CASE WHEN (SELECT count(*) FROM drift) = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'B', 2 + row_number() OVER (ORDER BY mapping_id, raw_event_id)::int,
           mapping_id, raw_event_id::text, 'changed', 'unchanged expected',
           'FAIL'
    FROM   drift
),

-- ---------------------------------------------------------------------------
-- C. simulator_classification untouched
-- ---------------------------------------------------------------------------
secC AS (
    SELECT 'C'::text, 1, 'PROTOTYPE_ASSUMPTION rows'::text,
           'an independent dimension, deliberately not repaired'::text,
           (SELECT count(*) FROM ev
            WHERE simulator_classification = 'PROTOTYPE_ASSUMPTION')::text,
           '36',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE simulator_classification='PROTOTYPE_ASSUMPTION')=36
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'C', 2, 'unmarked rows', '',
           (SELECT count(*) FROM ev
            WHERE simulator_classification IS NULL)::text, '107',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE simulator_classification IS NULL) = 107
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'C', 3, 'distinct values', '',
           (SELECT count(DISTINCT simulator_classification) FROM ev)::text, '1',
           CASE WHEN (SELECT count(DISTINCT simulator_classification)
                      FROM ev) = 1 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'C', 4, 'marked rows that are DEFAULTED',
           'the two dimensions must stay independent',
           (SELECT count(*) FROM ev
            WHERE simulator_classification IS NOT NULL
              AND value_provenance = 'DEFAULTED')::text, '0',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE simulator_classification IS NOT NULL
                        AND value_provenance = 'DEFAULTED') = 0
                THEN 'ok -- provenance was not inferred from the marker'
                ELSE 'FAIL' END
),

-- ---------------------------------------------------------------------------
-- D. structural integrity
-- ---------------------------------------------------------------------------
secD AS (
    SELECT 'D'::text, 1, 'distinct evidence_id'::text,
           'no row added or removed'::text,
           (SELECT count(DISTINCT evidence_id) FROM ev)::text, '143',
           CASE WHEN (SELECT count(DISTINCT evidence_id) FROM ev) = 143
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 2, 'distinct mapping_id', '',
           (SELECT count(DISTINCT mapping_id) FROM ev)::text, '22',
           CASE WHEN (SELECT count(DISTINCT mapping_id) FROM ev) = 22
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 3, 'duplicate (raw_event_id, mapping_id)',
           'the declared evidence identity',
           (SELECT count(*) FROM (SELECT raw_event_id, mapping_id FROM ev
                                  GROUP BY 1,2 HAVING count(*) > 1) d)::text,
           '0',
           CASE WHEN (SELECT count(*) FROM (SELECT raw_event_id, mapping_id
                                            FROM ev GROUP BY 1,2
                                            HAVING count(*) > 1) d) = 0
                THEN 'ok' ELSE 'FAIL' END
),

-- ---------------------------------------------------------------------------
-- E. the DEFAULTED rows, named
-- ---------------------------------------------------------------------------
-- These are the facts a governed readiness decision must not read as though
-- a source had asserted them.
secE AS (
    SELECT 'E'::text, row_number() OVER (ORDER BY e.mapping_id)::int,
           e.mapping_id::text,
           (r.event_type || ' -> ' || e.property_name)::text,
           ('DEFAULTED ' || count(*) FILTER
                (WHERE e.value_provenance='DEFAULTED')::text)::text,
           ('of ' || count(*)::text || ' rows')::text,
           ('asserted value: ' || min(e.asserted_value))::text
    FROM   ev e
    JOIN   raw.raw_event r ON r.raw_event_id = e.raw_event_id
    WHERE  e.value_provenance = 'DEFAULTED'
    GROUP  BY e.mapping_id, r.event_type, e.property_name
),

-- ---------------------------------------------------------------------------
-- F. what landed equals what the projection says
-- ---------------------------------------------------------------------------
secF AS (
    SELECT 'F'::text, 1,
           'rows whose stored provenance differs from v2'::text,
           're-derivable, not hand-classified'::text,
           (SELECT count(*) FROM ev e
            JOIN v2 p ON p.raw_event_id = e.raw_event_id
                     AND p.mapping_id   = e.mapping_id
            WHERE e.value_provenance IS DISTINCT FROM p.value_provenance)::text,
           '0',
           CASE WHEN (SELECT count(*) FROM ev e
                      JOIN v2 p ON p.raw_event_id = e.raw_event_id
                               AND p.mapping_id   = e.mapping_id
                      WHERE e.value_provenance
                            IS DISTINCT FROM p.value_provenance) = 0
                THEN 'ok' ELSE 'FAIL' END
),

body AS (
    SELECT * FROM secA
    UNION ALL SELECT * FROM secB
    UNION ALL SELECT * FROM secC
    UNION ALL SELECT * FROM secD
    UNION ALL SELECT * FROM secE
    UNION ALL SELECT * FROM secF
)
SELECT section, ord AS seq, item, detail, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM body
                  WHERE verdict NOT IN ('ok','info')
                    AND verdict NOT LIKE 'ok --%'
                    AND verdict NOT LIKE 'asserted value:%') = 0
            THEN 'STEP 3D OK -- 143 rows, 104/39/0, nothing else moved'
            ELSE 'STOP -- do not set NOT NULL' END AS overall
FROM   body
ORDER  BY section, ord;
