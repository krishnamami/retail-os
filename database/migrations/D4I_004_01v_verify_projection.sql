-- ============================================================================
-- D4I_004 step 1 verification -- READ ONLY. ONE STATEMENT. ONE GRID.
-- ============================================================================
-- Runs BEFORE anything is written. Proves the new projection is what it claims
-- and, critically, that applying it can only add:
--
--   section C  no projected row collides with an existing evidence row on
--              (raw_event_id, mapping_id) -- the declared evidence identity.
--              If that is zero, the apply is provably additive and the 143
--              existing facts cannot move.
--   section D  no new mapping_id reuses one of the deployed 22.
--
-- Section E is the honesty check. D4I_004 must add no DEFAULTED evidence:
-- every mapping either asserts an event occurrence or is guarded on its source
-- key. Where a key is absent the mapping stays silent rather than inventing a
-- value, so the sparse events (HIERARCHY_APPROVAL 4 of 13, MATERIAL_ACTIVATED
-- and OVERNIGHT_PUSH 2 of 11) contribute nothing and the fold sees UNREPORTED.
--
-- Anything other than 'ok' or 'info' is a stop. Do not apply.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH p AS MATERIALIZED (SELECT * FROM runtime.approval_projection_v1()),
expect(mapping_id, n) AS (
    VALUES ('FINAL_PRICING_APPROVAL_STATUS', 9),
           ('PRICING_UPLOAD_STATUS', 8),
           ('PRICING_UPLOADED_PRICE', 8),
           ('PRICING_PUBLICATION_STATUS', 3),
           ('PRICING_LIST_PRICE', 3),
           ('PRICING_CURRENCY', 3),
           ('PRICING_PUBLISHED_BY', 3),
           ('OVERNIGHT_PUSH_STATUS', 2),
           ('OVERNIGHT_PUSH_RUN_DATE', 2),
           ('ZUPDM_APPROVAL_STATUS', 9),
           ('ALL_GATES_CLEARED', 9),
           ('GO_LIVE_APPROVAL_REQUESTED', 2),
           ('GO_LIVE_APPROVAL_LEVEL', 2),
           ('GO_LIVE_REQUESTED_BY', 2),
           ('GO_LIVE_APPROVAL_STATUS', 3),
           ('GO_LIVE_APPROVED_BY', 3),
           ('SUPPLY_CHAIN_NOTIFICATION_STATUS', 2),
           ('SUPPLY_CHAIN_NOTIFICATION_TYPE', 2),
           ('SUPPLY_CHAIN_NOTIFIED_BY', 2),
           ('MATERIAL_ACTIVATION_STATUS', 2),
           ('MATERIAL_ACTIVATED_BY', 2),
           ('CON_VERIFICATION_STATUS', 9),
           ('SAP_CON_TEST_STATUS', 4),
           ('SAP_CON_TEST_ACTOR', 4),
           ('SAP_PRD_PROMOTION_HIERARCHY', 4),
           ('SAP_PRD_PROMOTION_ACTOR', 4),
           ('HIERARCHY_APPROVAL_CODE', 4),
           ('HIERARCHY_APPROVAL_AUTHORITY', 4)
),

secA AS (
    SELECT 'A'::text AS section, 1 AS ord,
           'function is STABLE, so it cannot write'::text AS item,
           ''::text AS detail,
           COALESCE((SELECT pr.provolatile::text FROM pg_proc pr
                     JOIN pg_namespace n ON n.oid = pr.pronamespace
                     WHERE n.nspname='runtime'
                       AND pr.proname='approval_projection_v1'), '<absent>')
             AS actual,
           's'::text AS expected,
           CASE WHEN (SELECT pr.provolatile FROM pg_proc pr
                      JOIN pg_namespace n ON n.oid = pr.pronamespace
                      WHERE n.nspname='runtime'
                        AND pr.proname='approval_projection_v1') = 's'
                THEN 'ok' ELSE 'FAIL' END::text AS verdict
    UNION ALL
    SELECT 'A', 2, 'projected rows', '', (SELECT count(*) FROM p)::text, '114',
           CASE WHEN (SELECT count(*) FROM p) = 114 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 3, 'projected mappings', '',
           (SELECT count(DISTINCT mapping_id) FROM p)::text, '28',
           CASE WHEN (SELECT count(DISTINCT mapping_id) FROM p) = 28
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 4, 'every row has a subject', '',
           (SELECT count(*) FROM p WHERE subject_id IS NULL)::text, '0',
           CASE WHEN (SELECT count(*) FROM p WHERE subject_id IS NULL) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 5, 'timestamps pass through raw.raw_event unmodified', '',
           (SELECT count(*) FROM p JOIN raw.raw_event r
                 ON r.raw_event_id = p.raw_event_id
            WHERE p.occurred_at IS DISTINCT FROM r.occurred_at
               OR p.recorded_at IS DISTINCT FROM r.recorded_at
               OR p.arrival_at  IS DISTINCT FROM r.arrival_at)::text, '0',
           CASE WHEN (SELECT count(*) FROM p JOIN raw.raw_event r
                        ON r.raw_event_id = p.raw_event_id
                      WHERE p.occurred_at IS DISTINCT FROM r.occurred_at
                         OR p.recorded_at IS DISTINCT FROM r.recorded_at
                         OR p.arrival_at  IS DISTINCT FROM r.arrival_at) = 0
                THEN 'ok' ELSE 'FAIL' END
),

secB AS (
    SELECT 'B'::text,
           row_number() OVER (ORDER BY e.mapping_id)::int,
           e.mapping_id::text,
           (SELECT DISTINCT x.evidence_lineage->>'event_type' FROM p x
            WHERE x.mapping_id = e.mapping_id)::text,
           COALESCE((SELECT count(*) FROM p WHERE p.mapping_id=e.mapping_id),0)::text,
           e.n::text,
           CASE WHEN COALESCE((SELECT count(*) FROM p
                               WHERE p.mapping_id=e.mapping_id),0) = e.n
                THEN 'ok' ELSE 'DIFF' END
    FROM   expect e
),

secC AS (
    SELECT 'C'::text, 1,
           'projected rows colliding with existing evidence'::text,
           'on (raw_event_id, mapping_id) -- must be zero for an additive apply'::text,
           (SELECT count(*) FROM p JOIN runtime.evidence ev
              ON ev.raw_event_id = p.raw_event_id
             AND ev.mapping_id   = p.mapping_id)::text, '0',
           CASE WHEN (SELECT count(*) FROM p JOIN runtime.evidence ev
                        ON ev.raw_event_id = p.raw_event_id
                       AND ev.mapping_id   = p.mapping_id) = 0
                THEN 'ok' ELSE 'FAIL -- apply would not be additive' END
    UNION ALL
    SELECT 'C', 2, 'duplicate identity within the projection', '',
           (SELECT count(*) FROM (SELECT raw_event_id, mapping_id FROM p
                                  GROUP BY 1,2 HAVING count(*) > 1) d)::text, '0',
           CASE WHEN (SELECT count(*) FROM (SELECT raw_event_id, mapping_id
                                            FROM p GROUP BY 1,2
                                            HAVING count(*) > 1) d) = 0
                THEN 'ok' ELSE 'FAIL' END
),

secD AS (
    SELECT 'D'::text, 1,
           'new mapping_id reusing a deployed one'::text, ''::text,
           (SELECT count(DISTINCT p.mapping_id) FROM p
            WHERE p.mapping_id IN (SELECT DISTINCT mapping_id
                                   FROM runtime.evidence))::text, '0',
           CASE WHEN (SELECT count(DISTINCT p.mapping_id) FROM p
                      WHERE p.mapping_id IN (SELECT DISTINCT mapping_id
                                             FROM runtime.evidence)) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 2,
           'FINAL_PRICING_APPROVAL folded into pricing_confirmed',
           'different events, disjoint SKU populations',
           (SELECT count(*) FROM p
            WHERE p.property_name = 'pricing_confirmed')::text, '0',
           CASE WHEN (SELECT count(*) FROM p
                      WHERE p.property_name='pricing_confirmed') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 3, 'any mapping reading approval_authority on a pricing event',
           'that key does not exist there',
           (SELECT count(*) FROM p
            WHERE p.evidence_lineage->>'event_type'='FINAL_PRICING_APPROVAL'
              AND p.evidence_lineage->>'source_path' LIKE '%approval_authority%'
           )::text, '0',
           CASE WHEN (SELECT count(*) FROM p
                      WHERE p.evidence_lineage->>'event_type'
                            ='FINAL_PRICING_APPROVAL'
                        AND p.evidence_lineage->>'source_path'
                            LIKE '%approval_authority%') = 0
                THEN 'ok' ELSE 'FAIL' END
),

secE AS (
    SELECT 'E'::text, 1, 'OBSERVED'::text,
           'occurrence constants plus guarded extractions'::text,
           (SELECT count(*) FROM p WHERE value_provenance='OBSERVED')::text,
           '114',
           CASE WHEN (SELECT count(*) FROM p
                      WHERE value_provenance='OBSERVED') = 114
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 2, 'DEFAULTED',
           'D4I_004 invents no value -- absent key means no row',
           (SELECT count(*) FROM p WHERE value_provenance='DEFAULTED')::text,
           '0',
           CASE WHEN (SELECT count(*) FROM p
                      WHERE value_provenance='DEFAULTED') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 3, 'DERIVED', '',
           (SELECT count(*) FROM p WHERE value_provenance='DERIVED')::text, '0',
           CASE WHEN (SELECT count(*) FROM p
                      WHERE value_provenance='DERIVED') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 4, 'NULL or outside the vocabulary', '',
           (SELECT count(*) FROM p WHERE value_provenance IS NULL
              OR value_provenance NOT IN
                 ('OBSERVED','DEFAULTED','DERIVED'))::text, '0',
           CASE WHEN (SELECT count(*) FROM p WHERE value_provenance IS NULL
                        OR value_provenance NOT IN
                           ('OBSERVED','DEFAULTED','DERIVED')) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E', 5, 'events that stay silent because their key is absent',
           'HIERARCHY_APPROVAL 9, MATERIAL_ACTIVATED 9, OVERNIGHT_PUSH 9',
           (SELECT count(*) FROM raw.raw_event r
            WHERE r.event_type IN ('HIERARCHY_APPROVAL','MATERIAL_ACTIVATED',
                                   'OVERNIGHT_PUSH')
              AND NOT EXISTS (SELECT 1 FROM p
                              WHERE p.raw_event_id = r.raw_event_id))::text,
           '27', 'info'
),

body AS (
    SELECT * FROM secA UNION ALL SELECT * FROM secB
    UNION ALL SELECT * FROM secC UNION ALL SELECT * FROM secD
    UNION ALL SELECT * FROM secE
)
SELECT section, ord AS seq, item, detail, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM body
                  WHERE verdict NOT IN ('ok','info')) = 0
            THEN 'STEP 1 OK -- 114 rows, 28 mappings, additive, all OBSERVED'
            ELSE 'STOP -- do not apply' END AS overall
FROM   body
ORDER  BY section, ord;
