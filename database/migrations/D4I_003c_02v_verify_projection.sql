-- ============================================================================
-- D4I_003c step 3B verification -- READ ONLY. ONE STATEMENT. ONE GRID.
-- ============================================================================
-- Proves three things before any row is written:
--
--   1  _v1 is still the frozen D4I_003 artifact -- same five correction
--      markers, same 20534-character body. If v2 had been created by
--      replacing v1, D4I_003's verdict would silently stop being about a
--      function that exists, and this is the check that would catch it.
--
--   2  v2 reproduces every one of v1's fifteen columns on every row, keyed
--      on (raw_event_id, mapping_id) -- the identity the database itself
--      declares via evidence_lineage_identity_unique. Not a row count: a
--      full-column diff, because two projections can both return 143 rows.
--
--   3  v2's provenance classification matches the measurement taken in step
--      0 -- 104 / 39 / 0 overall, and the per-mapping splits 0/13, 4/9, 0/9,
--      1/8 for the four branching mappings.
--
-- Anything other than 'ok' or 'info' is a stop. Do not backfill.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH v1 AS MATERIALIZED (SELECT * FROM runtime.evidence_projection_v1()),
     v2 AS MATERIALIZED (SELECT * FROM runtime.evidence_projection_v2()),

fn AS (
    SELECT p.proname::text AS name, p.provolatile, length(p.prosrc) AS len,
           p.prosrc
    FROM   pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE  n.nspname = 'runtime'
      AND  p.proname IN ('evidence_projection_v1','evidence_projection_v2')
),

-- ---------------------------------------------------------------------------
-- A. both functions, and v1 demonstrably untouched
-- ---------------------------------------------------------------------------
secA AS (
    SELECT 'A'::text AS section, 1 AS ord,
           'evidence_projection_v1 still deployed'::text AS item,
           COALESCE((SELECT 'yes' FROM fn WHERE name='evidence_projection_v1'),
                    'NO')::text AS actual,
           'yes'::text AS expected,
           CASE WHEN EXISTS (SELECT 1 FROM fn WHERE name='evidence_projection_v1')
                THEN 'ok' ELSE 'FAIL' END::text AS verdict
    UNION ALL
    SELECT 'A', 2, 'v1 body length unchanged',
           COALESCE((SELECT len::text FROM fn
                     WHERE name='evidence_projection_v1'), '<absent>'),
           '20534',
           CASE WHEN (SELECT len FROM fn WHERE name='evidence_projection_v1')
                     = 20534 THEN 'ok' ELSE 'FAIL -- v1 WAS MODIFIED' END
    UNION ALL
    SELECT 'A', 3, 'v1 still carries all five D4I_003 correction markers',
           (SELECT (position('market_expansion' in prosrc) > 0
                AND position('COALESCE(r.payload->>''con_status''' in prosrc) > 0
                AND position('(r.payload->>''con_id'')::varchar' in prosrc) > 0
                AND position('COALESCE(r.payload->>''prd_status''' in prosrc) > 0
                AND position('COALESCE(r.payload->>''technical_approval_statu'
                             in prosrc) > 0)::text
            FROM fn WHERE name='evidence_projection_v1'),
           'true',
           CASE WHEN (SELECT (position('market_expansion' in prosrc) > 0
                AND position('COALESCE(r.payload->>''con_status''' in prosrc) > 0
                AND position('(r.payload->>''con_id'')::varchar' in prosrc) > 0
                AND position('COALESCE(r.payload->>''prd_status''' in prosrc) > 0
                AND position('COALESCE(r.payload->>''technical_approval_statu'
                             in prosrc) > 0)
            FROM fn WHERE name='evidence_projection_v1')
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 4, 'evidence_projection_v2 deployed',
           COALESCE((SELECT 'yes' FROM fn WHERE name='evidence_projection_v2'),
                    'NO'), 'yes',
           CASE WHEN EXISTS (SELECT 1 FROM fn WHERE name='evidence_projection_v2')
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 5, 'v2 is STABLE, so it cannot write',
           COALESCE((SELECT provolatile::text FROM fn
                     WHERE name='evidence_projection_v2'), '<absent>'), 's',
           CASE WHEN (SELECT provolatile FROM fn
                      WHERE name='evidence_projection_v2') = 's'
                THEN 'ok' ELSE 'FAIL' END
),

-- ---------------------------------------------------------------------------
-- B. totals
-- ---------------------------------------------------------------------------
secB AS (
    SELECT 'B'::text, 1, 'v1 rows'::text,
           (SELECT count(*) FROM v1)::text, '143'::text,
           CASE WHEN (SELECT count(*) FROM v1) = 143 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'B', 2, 'v2 rows', (SELECT count(*) FROM v2)::text, '143',
           CASE WHEN (SELECT count(*) FROM v2) = 143 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'B', 3, 'v2 mappings',
           (SELECT count(DISTINCT mapping_id) FROM v2)::text, '22',
           CASE WHEN (SELECT count(DISTINCT mapping_id) FROM v2) = 22
                THEN 'ok' ELSE 'FAIL' END
),

-- ---------------------------------------------------------------------------
-- C. v1 vs v2 across every column v1 has
-- ---------------------------------------------------------------------------
one_sided AS (
    SELECT count(*) AS n FROM (
        SELECT a.raw_event_id, a.mapping_id FROM v1 a
        WHERE NOT EXISTS (SELECT 1 FROM v2 b
                          WHERE b.raw_event_id = a.raw_event_id
                            AND b.mapping_id   = a.mapping_id)
        UNION ALL
        SELECT b.raw_event_id, b.mapping_id FROM v2 b
        WHERE NOT EXISTS (SELECT 1 FROM v1 a
                          WHERE a.raw_event_id = b.raw_event_id
                            AND a.mapping_id   = b.mapping_id)) x
),
diff AS (
    SELECT a.mapping_id, a.raw_event_id
    FROM   v1 a
    JOIN   v2 b ON b.raw_event_id = a.raw_event_id
               AND b.mapping_id   = a.mapping_id
    WHERE  a.evidence_type     IS DISTINCT FROM b.evidence_type
       OR  a.subject_type      IS DISTINCT FROM b.subject_type
       OR  a.subject_id        IS DISTINCT FROM b.subject_id
       OR  a.property_name     IS DISTINCT FROM b.property_name
       OR  a.asserted_value    IS DISTINCT FROM b.asserted_value
       OR  a.value_type        IS DISTINCT FROM b.value_type
       OR  a.source_system     IS DISTINCT FROM b.source_system
       OR  a.source_actor_id   IS DISTINCT FROM b.source_actor_id
       OR  a.source_actor_role IS DISTINCT FROM b.source_actor_role
       OR  a.occurred_at       IS DISTINCT FROM b.occurred_at
       OR  a.recorded_at       IS DISTINCT FROM b.recorded_at
       OR  a.arrival_at        IS DISTINCT FROM b.arrival_at
       OR  a.evidence_lineage  IS DISTINCT FROM b.evidence_lineage
),
secC AS (
    SELECT 'C'::text, 1, 'rows present in one projection only'::text,
           (SELECT n FROM one_sided)::text, '0'::text,
           CASE WHEN (SELECT n FROM one_sided) = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'C', 2,
           'matched rows disagreeing on any of v1''s fifteen columns',
           (SELECT count(*) FROM diff)::text, '0',
           CASE WHEN (SELECT count(*) FROM diff) = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'C', 2 + row_number() OVER (ORDER BY mapping_id, raw_event_id)::int,
           mapping_id, raw_event_id::text, 'identical expected', 'FAIL'
    FROM   diff
),

-- ---------------------------------------------------------------------------
-- D. provenance distribution
-- ---------------------------------------------------------------------------
secD AS (
    SELECT 'D'::text, 1, 'OBSERVED'::text,
           (SELECT count(*) FROM v2 WHERE value_provenance='OBSERVED')::text,
           '104'::text,
           CASE WHEN (SELECT count(*) FROM v2
                      WHERE value_provenance='OBSERVED') = 104
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 2, 'DEFAULTED',
           (SELECT count(*) FROM v2 WHERE value_provenance='DEFAULTED')::text,
           '39',
           CASE WHEN (SELECT count(*) FROM v2
                      WHERE value_provenance='DEFAULTED') = 39
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 3, 'DERIVED',
           (SELECT count(*) FROM v2 WHERE value_provenance='DERIVED')::text,
           '0',
           CASE WHEN (SELECT count(*) FROM v2
                      WHERE value_provenance='DERIVED') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 4, 'NULL -- every projected row must be classified',
           (SELECT count(*) FROM v2 WHERE value_provenance IS NULL)::text, '0',
           CASE WHEN (SELECT count(*) FROM v2
                      WHERE value_provenance IS NULL) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 5, 'outside the approved vocabulary',
           (SELECT count(*) FROM v2 WHERE value_provenance IS NOT NULL
              AND value_provenance NOT IN
                  ('OBSERVED','DEFAULTED','DERIVED'))::text, '0',
           CASE WHEN (SELECT count(*) FROM v2 WHERE value_provenance IS NOT NULL
                        AND value_provenance NOT IN
                            ('OBSERVED','DEFAULTED','DERIVED')) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 6, 'TOTAL', (SELECT count(*) FROM v2)::text, '143',
           CASE WHEN (SELECT count(*) FROM v2) = 143 THEN 'ok' ELSE 'FAIL' END
),

-- ---------------------------------------------------------------------------
-- E. the four branching mappings, per row
-- ---------------------------------------------------------------------------
expect(mapping_id, e_obs, e_def) AS (
    VALUES ('PRODUCT_INTENT_CLASS',   0, 13),
           ('SAP_CON_LOAD_STATUS',    4,  9),
           ('SAP_PRD_LOAD_STATUS',    0,  9),
           ('TECHNICAL_REVIEW_RESULT',1,  8)
),
secE AS (
    SELECT 'E'::text, row_number() OVER (ORDER BY e.mapping_id)::int,
           e.mapping_id::text,
           ('OBSERVED ' || count(*) FILTER (WHERE v.value_provenance='OBSERVED')::text
             || ' / DEFAULTED '
             || count(*) FILTER (WHERE v.value_provenance='DEFAULTED')::text)::text,
           ('expected OBSERVED ' || max(e.e_obs)::text
             || ' / DEFAULTED ' || max(e.e_def)::text)::text,
           CASE WHEN count(*) FILTER (WHERE v.value_provenance='OBSERVED')
                     = max(e.e_obs)
                 AND count(*) FILTER (WHERE v.value_provenance='DEFAULTED')
                     = max(e.e_def)
                THEN 'ok' ELSE 'FAIL' END
    FROM   expect e JOIN v2 v ON v.mapping_id = e.mapping_id
    GROUP  BY e.mapping_id
    UNION ALL
    SELECT 'E', 90, 'every other mapping is wholly OBSERVED',
           (SELECT count(*) FROM v2 v
            WHERE v.mapping_id NOT IN (SELECT mapping_id FROM expect)
              AND v.value_provenance <> 'OBSERVED')::text,
           '0',
           CASE WHEN (SELECT count(*) FROM v2 v
                      WHERE v.mapping_id NOT IN (SELECT mapping_id FROM expect)
                        AND v.value_provenance <> 'OBSERVED') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 91,
           'event-occurrence mappings are OBSERVED, not DEFAULTED',
           (SELECT count(*) FROM v2 v
            WHERE v.mapping_id IN ('MATERIAL_CREATED','SKU_MINTED',
                                   'SKU_ACTIVATED','PRICING_STATUS',
                                   'PRICING_CONFIRMED')
              AND v.value_provenance = 'OBSERVED')::text,
           '27',
           CASE WHEN (SELECT count(*) FROM v2 v
                      WHERE v.mapping_id IN ('MATERIAL_CREATED','SKU_MINTED',
                                             'SKU_ACTIVATED','PRICING_STATUS',
                                             'PRICING_CONFIRMED')
                        AND v.value_provenance = 'OBSERVED') = 27
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 92,
           'provenance is not inferred from simulator_classification',
           (SELECT count(*) FROM v2 v
            JOIN runtime.evidence e2 ON e2.raw_event_id = v.raw_event_id
                                    AND e2.mapping_id   = v.mapping_id
            WHERE e2.simulator_classification IS NOT NULL
              AND v.value_provenance = 'OBSERVED')::text,
           '36',
           CASE WHEN (SELECT count(*) FROM v2 v
                      JOIN runtime.evidence e2
                        ON e2.raw_event_id = v.raw_event_id
                       AND e2.mapping_id   = v.mapping_id
                      WHERE e2.simulator_classification IS NOT NULL
                        AND v.value_provenance = 'OBSERVED') = 36
                THEN 'ok -- marked rows are OBSERVED, as measured'
                ELSE 'FAIL' END
),

body AS (
    SELECT * FROM secA
    UNION ALL SELECT * FROM secB
    UNION ALL SELECT * FROM secC
    UNION ALL SELECT * FROM secD
    UNION ALL SELECT * FROM secE
)
SELECT section, ord AS seq, item, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM body WHERE verdict NOT IN ('ok','info')
                    AND verdict NOT LIKE 'ok --%') = 0
            THEN 'STEP 3B OK -- proceed to 3C backfill'
            ELSE 'BLOCKED -- PROJECTION V2 PROVENANCE RECONCILIATION FAILED'
       END AS overall
FROM   body
ORDER  BY section, ord;
