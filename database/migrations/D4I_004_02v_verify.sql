-- ============================================================================
-- D4I_004 step 2 verification -- READ ONLY. ONE STATEMENT. ONE GRID.
-- ============================================================================
-- Section B is the one that matters. It re-runs the D4I_003b comparison of
-- runtime.evidence against the frozen _v1 over the 22 original mappings. That
-- comparison passed before D4I_004 existed. If it still passes, the 143
-- original facts were not touched -- measured, not inferred from the fact that
-- the apply used ON CONFLICT.
--
-- Section D proves the apply is replayable: every projected row is present
-- exactly once, so running it again inserts nothing.
--
-- Anything other than 'ok' or 'info' is a stop.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH ev AS MATERIALIZED (SELECT * FROM runtime.evidence),
     v1 AS MATERIALIZED (SELECT * FROM runtime.evidence_projection_v1()),
     ap AS MATERIALIZED (SELECT * FROM runtime.approval_projection_v1()),

secA AS (
    SELECT 'A'::text AS section, 1 AS ord, 'evidence rows'::text AS item,
           '143 original + 114 approval-chain'::text AS detail,
           (SELECT count(*) FROM ev)::text AS actual, '257'::text AS expected,
           CASE WHEN (SELECT count(*) FROM ev) = 257 THEN 'ok' ELSE 'FAIL' END
             AS verdict
    UNION ALL
    SELECT 'A', 2, 'mappings', '22 original + 28 new',
           (SELECT count(DISTINCT mapping_id) FROM ev)::text, '50',
           CASE WHEN (SELECT count(DISTINCT mapping_id) FROM ev) = 50
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 3, 'OBSERVED', '104 + 114',
           (SELECT count(*) FROM ev WHERE value_provenance='OBSERVED')::text,
           '218',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance='OBSERVED') = 218
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 4, 'DEFAULTED', 'unchanged -- D4I_004 added none',
           (SELECT count(*) FROM ev WHERE value_provenance='DEFAULTED')::text,
           '39',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance='DEFAULTED') = 39
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 5, 'DERIVED', '',
           (SELECT count(*) FROM ev WHERE value_provenance='DERIVED')::text,
           '0',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance='DERIVED') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 6, 'NULL provenance', 'NOT NULL should make this impossible',
           (SELECT count(*) FROM ev WHERE value_provenance IS NULL)::text, '0',
           CASE WHEN (SELECT count(*) FROM ev
                      WHERE value_provenance IS NULL) = 0
                THEN 'ok' ELSE 'FAIL' END
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
    SELECT 'B'::text, 1, 'original rows still present'::text,
           'every v1 row still in runtime.evidence'::text,
           (SELECT count(*) FROM v1 a WHERE EXISTS (
              SELECT 1 FROM ev e WHERE e.raw_event_id=a.raw_event_id
                                   AND e.mapping_id=a.mapping_id))::text,
           '143',
           CASE WHEN (SELECT count(*) FROM v1 a WHERE EXISTS (
                        SELECT 1 FROM ev e WHERE e.raw_event_id=a.raw_event_id
                                             AND e.mapping_id=a.mapping_id))
                     = 143 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'B', 2, 'original rows changed by D4I_004',
           'value, subject, property, timestamps, lineage',
           (SELECT count(*) FROM drift)::text, '0',
           CASE WHEN (SELECT count(*) FROM drift) = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'B', 2 + row_number() OVER (ORDER BY mapping_id, raw_event_id)::int,
           mapping_id, raw_event_id::text, 'changed', 'unchanged expected',
           'FAIL'
    FROM   drift
),

secC AS (
    SELECT 'C'::text,
           row_number() OVER (ORDER BY subject_type)::int,
           subject_type::text,
           ('mappings ' || count(DISTINCT mapping_id)::text)::text,
           count(*)::text,
           ('OBSERVED ' || count(*) FILTER (WHERE value_provenance='OBSERVED')::text
             || ' / DEFAULTED '
             || count(*) FILTER (WHERE value_provenance='DEFAULTED')::text)::text,
           'info'::text
    FROM   ev GROUP BY subject_type
),

secD AS (
    SELECT 'D'::text, 1, 'approval rows present exactly once'::text,
           're-running the apply would insert nothing'::text,
           (SELECT count(*) FROM ap a WHERE EXISTS (
              SELECT 1 FROM ev e WHERE e.raw_event_id=a.raw_event_id
                                   AND e.mapping_id=a.mapping_id))::text,
           '114',
           CASE WHEN (SELECT count(*) FROM ap a WHERE EXISTS (
                        SELECT 1 FROM ev e WHERE e.raw_event_id=a.raw_event_id
                                             AND e.mapping_id=a.mapping_id))
                     = 114 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 2, 'stored approval rows differing from the projection', '',
           (SELECT count(*) FROM ev e JOIN ap a
              ON a.raw_event_id=e.raw_event_id AND a.mapping_id=e.mapping_id
            WHERE e.asserted_value   IS DISTINCT FROM a.asserted_value
               OR e.subject_id       IS DISTINCT FROM a.subject_id
               OR e.property_name    IS DISTINCT FROM a.property_name
               OR e.value_provenance IS DISTINCT FROM a.value_provenance
               OR e.evidence_lineage IS DISTINCT FROM a.evidence_lineage)::text,
           '0',
           CASE WHEN (SELECT count(*) FROM ev e JOIN ap a
                        ON a.raw_event_id=e.raw_event_id
                       AND a.mapping_id=e.mapping_id
                      WHERE e.asserted_value   IS DISTINCT FROM a.asserted_value
                         OR e.subject_id       IS DISTINCT FROM a.subject_id
                         OR e.property_name    IS DISTINCT FROM a.property_name
                         OR e.value_provenance IS DISTINCT FROM a.value_provenance
                         OR e.evidence_lineage IS DISTINCT FROM a.evidence_lineage)
                     = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 3, 'duplicate evidence identity', '',
           (SELECT count(*) FROM (SELECT raw_event_id, mapping_id FROM ev
                                  GROUP BY 1,2 HAVING count(*) > 1) d)::text,
           '0',
           CASE WHEN (SELECT count(*) FROM (SELECT raw_event_id, mapping_id
                                            FROM ev GROUP BY 1,2
                                            HAVING count(*) > 1) d) = 0
                THEN 'ok' ELSE 'FAIL' END
),

secE AS (
    SELECT 'E'::text, 1, 'simulator_classification marked'::text,
           'independent dimension, untouched'::text,
           (SELECT count(simulator_classification) FROM ev)::text, '36',
           CASE WHEN (SELECT count(simulator_classification) FROM ev) = 36
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 2, 'approval-chain event types now carrying evidence',
           'were 0 before D4I_004',
           (SELECT count(DISTINCT r.event_type) FROM ev e
            JOIN raw.raw_event r ON r.raw_event_id = e.raw_event_id
            WHERE r.event_type IN
              ('FINAL_PRICING_APPROVAL','FULLY_APPROVED','ZUPDM_APPROVED',
               'PRICING_UPLOADED','PRICING_PUBLISHED','OVERNIGHT_PUSH',
               'GO_LIVE_APPROVAL_REQUESTED','GO_LIVE_APPROVED',
               'SUPPLY_CHAIN_NOTIFIED','MATERIAL_ACTIVATED','CON_VERIFIED',
               'SAP_CON_TESTED','SAP_PRD_PROMOTED','HIERARCHY_APPROVAL'))::text,
           '14',
           CASE WHEN (SELECT count(DISTINCT r.event_type) FROM ev e
                      JOIN raw.raw_event r ON r.raw_event_id = e.raw_event_id
                      WHERE r.event_type IN
                        ('FINAL_PRICING_APPROVAL','FULLY_APPROVED',
                         'ZUPDM_APPROVED','PRICING_UPLOADED','PRICING_PUBLISHED',
                         'OVERNIGHT_PUSH','GO_LIVE_APPROVAL_REQUESTED',
                         'GO_LIVE_APPROVED','SUPPLY_CHAIN_NOTIFIED',
                         'MATERIAL_ACTIVATED','CON_VERIFIED','SAP_CON_TESTED',
                         'SAP_PRD_PROMOTED','HIERARCHY_APPROVAL')) = 14
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 3, 'FINAL_PRICING_APPROVAL still distinct from PRICING_CONFIRMED',
           'disjoint SKU populations, never merged',
           (SELECT count(*) FROM ev e
            JOIN raw.raw_event r ON r.raw_event_id = e.raw_event_id
            WHERE r.event_type='FINAL_PRICING_APPROVAL'
              AND e.property_name='pricing_confirmed')::text, '0',
           CASE WHEN (SELECT count(*) FROM ev e
                      JOIN raw.raw_event r ON r.raw_event_id = e.raw_event_id
                      WHERE r.event_type='FINAL_PRICING_APPROVAL'
                        AND e.property_name='pricing_confirmed') = 0
                THEN 'ok' ELSE 'FAIL' END
),

body AS (
    SELECT * FROM secA UNION ALL SELECT * FROM secB
    UNION ALL SELECT * FROM secC UNION ALL SELECT * FROM secD
    UNION ALL SELECT * FROM secE
)
SELECT section, ord AS seq, item, detail, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM body
                  WHERE verdict NOT IN ('ok','info')) = 0
            THEN 'D4I_004 APPLIED -- 257 rows, 50 mappings, 218/39/0, '
                 || 'originals untouched'
            ELSE 'STOP' END AS overall
FROM   body
ORDER  BY section, ord;
