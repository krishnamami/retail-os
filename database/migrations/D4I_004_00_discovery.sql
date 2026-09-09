-- ============================================================================
-- D4I_004 step 0 -- approval-chain payload discovery. READ ONLY. ONE STATEMENT.
-- ============================================================================
-- Your brief specifies most of the mappings, and specifies them from the
-- corpus rather than from the stale writer -- including the correction that
-- HIERARCHY_APPROVAL carries FLAT hierarchy_code and approval_authority, not
-- the payload.hierarchy_approvals array that raw_to_evidence_FINAL.sql guards
-- on. That single wrong guard is why 21 dormant INSERTs produce nothing.
--
-- Three mappings are specified only as "map source facts only":
--     CON_VERIFIED, SAP_CON_TESTED, SAP_PRD_PROMOTED
-- Their properties cannot be written without knowing which keys exist. And
-- every subject choice needs its column measured, not assumed: this project
-- has already found SAP_CON_* subjects living in payload.con_id while the
-- con_id COLUMN was null on every row.
--
-- So this measures, for all fourteen approval-chain event types:
--   1  how many raw events exist, how much evidence they currently produce,
--      and which subject columns are actually populated
--   2  every payload key, how often it is present and non-null, and a sample
--      value -- the raw material for each mapping's property list
--   3  nested payload shape, since CONF_REQ_* reads payload.payload.* and a
--      wrong nesting assumption silently yields zero rows
--   4  every event type in the corpus with its evidence coverage, so nothing
--      unmapped stays invisible
--
-- Nothing is designed from this file. It is the input to D4I_004.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH chain(event_type) AS (
    VALUES ('FINAL_PRICING_APPROVAL'), ('FULLY_APPROVED'), ('ZUPDM_APPROVED'),
           ('PRICING_UPLOADED'), ('PRICING_PUBLISHED'), ('OVERNIGHT_PUSH'),
           ('GO_LIVE_APPROVAL_REQUESTED'), ('GO_LIVE_APPROVED'),
           ('SUPPLY_CHAIN_NOTIFIED'), ('MATERIAL_ACTIVATED'),
           ('CON_VERIFIED'), ('SAP_CON_TESTED'), ('SAP_PRD_PROMOTED'),
           ('HIERARCHY_APPROVAL')
),
ev AS MATERIALIZED (
    SELECT r.*, c.event_type IS NOT NULL AS in_chain
    FROM   raw.raw_event r
    LEFT   JOIN chain c ON c.event_type = r.event_type
),

-- ---------------------------------------------------------------------------
-- 1. volume, current evidence, and which subject columns are populated
-- ---------------------------------------------------------------------------
sec1 AS (
    SELECT '1'::text AS section,
           row_number() OVER (ORDER BY r.event_type)::int AS ord,
           r.event_type::text AS item,
           ('raw ' || count(*)::text
             || ' / evidence ' || count(*) FILTER (
                    WHERE EXISTS (SELECT 1 FROM runtime.evidence e
                                  WHERE e.raw_event_id = r.raw_event_id))::text
           )::text AS detail,
           ('sku ' || count(r.sku_id)::text
             || ' | launch ' || count(r.launch_id)::text
             || ' | material ' || count(r.material_id)::text)::text AS value_a,
           ('payload.con_id ' || count(r.payload->>'con_id')::text
             || ' | payload.prd_id ' || count(r.payload->>'prd_id')::text
             || ' | payload.sku_id ' || count(r.payload->>'sku_id')::text
           )::text AS value_b,
           CASE WHEN count(*) = 0 THEN 'ABSENT FROM CORPUS'
                ELSE 'present' END::text AS note
    FROM   ev r
    WHERE  r.in_chain
    GROUP  BY r.event_type
),

-- ---------------------------------------------------------------------------
-- 2. payload keys, presence, and a sample
-- ---------------------------------------------------------------------------
-- present  = key exists on the object
-- asserted = key exists AND is not JSON null (the test provenance uses)
keys AS (
    SELECT r.event_type::text AS event_type,
           k::text AS key,
           count(*) AS present,
           count(*) FILTER (WHERE r.payload -> k IS NOT NULL
                              AND r.payload -> k <> 'null'::jsonb) AS asserted,
           min(jsonb_typeof(r.payload -> k)) AS jtype,
           left(min(r.payload ->> k), 40) AS sample,
           (SELECT count(*) FROM ev x WHERE x.event_type = r.event_type) AS n_ev
    FROM   ev r, LATERAL jsonb_object_keys(r.payload) AS k
    WHERE  r.in_chain AND jsonb_typeof(r.payload) = 'object'
    GROUP  BY r.event_type, k
),
sec2 AS (
    SELECT '2'::text, row_number() OVER (ORDER BY event_type, key)::int,
           event_type, key,
           ('asserted ' || asserted::text || ' of ' || n_ev::text)::text,
           COALESCE(sample, '<null>'),
           CASE WHEN asserted = n_ev THEN 'on every event'
                WHEN asserted = 0    THEN 'NEVER ASSERTED'
                ELSE 'PARTIAL -- provenance would branch here' END
    FROM   keys
),

-- ---------------------------------------------------------------------------
-- 3. nested payload shape
-- ---------------------------------------------------------------------------
sec3 AS (
    SELECT '3'::text, row_number() OVER (ORDER BY r.event_type)::int,
           r.event_type::text,
           'payload.payload present on'::text,
           (count(*) FILTER (WHERE r.payload ? 'payload')::text
             || ' of ' || count(*)::text)::text,
           COALESCE(left((SELECT string_agg(kk, ', ' ORDER BY kk)
                          FROM jsonb_object_keys(
                                 (SELECT y.payload -> 'payload' FROM ev y
                                  WHERE y.event_type = r.event_type
                                    AND y.payload ? 'payload'
                                    AND jsonb_typeof(y.payload->'payload')
                                        = 'object'
                                  LIMIT 1)) AS kk), 120),
                    '<no nested object>'),
           CASE WHEN count(*) FILTER (WHERE r.payload ? 'payload') = 0
                THEN 'flat payload -- read keys directly'
                ELSE 'NESTED -- read payload.payload.*' END
    FROM   ev r
    WHERE  r.in_chain
    GROUP  BY r.event_type
),

-- ---------------------------------------------------------------------------
-- 4. corpus completeness -- what else is unmapped?
-- ---------------------------------------------------------------------------
sec4 AS (
    SELECT '4'::text, row_number() OVER (ORDER BY r.event_type)::int,
           r.event_type::text,
           CASE WHEN bool_or(r.in_chain) THEN 'in D4I_004 scope'
                ELSE 'outside D4I_004 scope' END::text,
           ('raw ' || count(*)::text)::text,
           ('evidence rows ' || (SELECT count(*) FROM runtime.evidence e
                                 WHERE e.raw_event_id IN (
                                   SELECT x.raw_event_id FROM ev x
                                   WHERE x.event_type = r.event_type))::text
           )::text,
           CASE WHEN (SELECT count(*) FROM runtime.evidence e
                      WHERE e.raw_event_id IN (SELECT x.raw_event_id FROM ev x
                                               WHERE x.event_type = r.event_type)
                     ) > 0 THEN 'mapped'
                WHEN bool_or(r.in_chain) THEN 'unmapped -- D4I_004 target'
                ELSE 'UNMAPPED AND OUT OF SCOPE -- decide explicitly' END
    FROM   ev r
    GROUP  BY r.event_type
)

SELECT section, ord AS seq, item, detail, value_a, value_b, note
FROM   (SELECT * FROM sec1
        UNION ALL SELECT * FROM sec2
        UNION ALL SELECT * FROM sec3
        UNION ALL SELECT * FROM sec4) AS discovery
ORDER  BY section, ord;
