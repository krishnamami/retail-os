-- ============================================================================
-- D4I_003b -- verification only. READ ONLY. ONE STATEMENT. ONE GRID.
-- ============================================================================
-- This file contains no CREATE, no REPLACE, no INSERT, no UPDATE, no DELETE,
-- no TRUNCATE and no ALTER. It cannot change mapping behaviour. It can only
-- report what D4I_003a actually deployed.
--
-- WHY ONE STATEMENT AND ONE GRID
--   pgAdmin shows the result of the LAST statement in a file. A verification
--   file made of seven SELECTs therefore shows one seventh of its own answer,
--   and the six sections that mattered scroll past unseen -- which is how
--   "143 | 83" was read twice as though the function had been replaced.
--   So every section below is a labelled block of ONE union, ordered, with an
--   explicit verdict per row and an overall verdict at the end. There is
--   nothing to scroll past and nothing to select.
--
-- SECTIONS
--   A  the deployed function body -- correction markers and volatility
--   B  totals: deployed rows vs projected rows
--   C  semantic distribution by mapping, event type, subject type, property
--   D  rows present on one side only
--   E  matched rows that disagree on any semantic column
--   F  timestamps that disagree with raw.raw_event
--   G  approval-chain absence: D4I_003 adds no new event types
--   Z  overall verdict
--
-- HOW TO READ IT
--   Filter or sort by the verdict column. Anything other than "ok" or "info"
--   is a finding. Section Z states the single conclusion.
--
-- WHAT PASSING MEANS AND WHAT IT DOES NOT
--   Passing means the function reproduces the deployed evidence layer exactly:
--   same rows, same subjects, same values, same timestamps. It does NOT mean
--   the deployed contract is semantically correct. Four mappings default an
--   absent payload key to a constant, so roughly thirty rows record values no
--   source event asserted. Reproducing that faithfully is the point of D4I_003
--   and is recorded as EVIDENCE-SEMANTICS DEBT, not as endorsement.
-- ============================================================================

WITH fn AS (
    SELECT p.prosrc,
           p.provolatile,
           length(p.prosrc) AS body_length
    FROM   pg_proc p
    JOIN   pg_namespace n ON n.oid = p.pronamespace
    WHERE  n.nspname = 'runtime'
      AND  p.proname = 'evidence_projection_v1'
),

-- Materialised so the function is executed once and every section below
-- compares the same set of rows.
proj AS MATERIALIZED (
    SELECT * FROM runtime.evidence_projection_v1()
),
dep AS MATERIALIZED (
    SELECT * FROM runtime.evidence
),

-- ---------------------------------------------------------------------------
-- A. THE DEPLOYED FUNCTION BODY
-- ---------------------------------------------------------------------------
-- Five markers, one per correction made when the contract was reconstructed
-- from what runtime.evidence actually contains. If any is false, D4I_003a did
-- not take effect and every count below describes the OLD function.
marker AS (
    SELECT * FROM (VALUES
        (1, 'intent_class defaults to market_expansion',
            'market_expansion'),
        (2, 'con_status defaults to SUCCESS',
            'COALESCE(r.payload->>''con_status'''),
        (3, 'SAP_CON_* subject reads payload.con_id',
            '(r.payload->>''con_id'')::varchar'),
        (4, 'prd_status defaults to SUCCESS',
            'COALESCE(r.payload->>''prd_status'''),
        (5, 'technical_approval_status defaults to PASS',
            'COALESCE(r.payload->>''technical_approval_statu')
    ) AS v(seq, label, needle)
),
section_a AS (
    SELECT 'A'::text AS section,
           m.seq::int AS ord,
           m.label::text AS check_name,
           ''::text AS detail,
           CASE WHEN position(m.needle in f.prosrc) > 0
                THEN 'true' ELSE 'false' END::text AS actual,
           'true'::text AS expected,
           CASE WHEN position(m.needle in f.prosrc) > 0
                THEN 'ok' ELSE 'FAIL' END::text AS verdict
    FROM   marker m CROSS JOIN fn f
    UNION ALL
    SELECT 'A', 6, 'function is STABLE, so it cannot write', '',
           f.provolatile::text, 's',
           CASE WHEN f.provolatile = 's' THEN 'ok' ELSE 'FAIL' END
    FROM   fn f
    UNION ALL
    SELECT 'A', 7, 'body length', 'old body was 20527 characters',
           f.body_length::text, '<> 20527',
           CASE WHEN f.body_length = 20527 THEN 'FAIL' ELSE 'ok' END
    FROM   fn f
),

-- ---------------------------------------------------------------------------
-- B. TOTALS
-- ---------------------------------------------------------------------------
totals AS (
    SELECT (SELECT count(*) FROM dep)  AS deployed_rows,
           (SELECT count(*) FROM proj) AS projected_rows,
           (SELECT count(DISTINCT mapping_id) FROM dep)  AS deployed_mappings,
           (SELECT count(DISTINCT mapping_id) FROM proj) AS projected_mappings
),
section_b AS (
    SELECT 'B'::text, 1,
           'row count'::text, 'runtime.evidence vs the projection'::text,
           t.projected_rows::text, t.deployed_rows::text,
           CASE WHEN t.projected_rows = t.deployed_rows THEN 'ok' ELSE 'FAIL' END
    FROM   totals t
    UNION ALL
    SELECT 'B', 2, 'mapping count', '',
           t.projected_mappings::text, t.deployed_mappings::text,
           CASE WHEN t.projected_mappings = t.deployed_mappings
                THEN 'ok' ELSE 'FAIL' END
    FROM   totals t
    UNION ALL
    SELECT 'B', 3, 'mapping count is the measured 22', '',
           t.deployed_mappings::text, '22',
           CASE WHEN t.deployed_mappings = 22 THEN 'ok' ELSE 'FAIL' END
    FROM   totals t
),

-- ---------------------------------------------------------------------------
-- C. SEMANTIC DISTRIBUTION
-- ---------------------------------------------------------------------------
-- Two different contracts can both produce 143 rows. This groups on the four
-- columns that carry the mapping's meaning -- which mapping, from which event
-- type, about which kind of subject, asserting which property -- and compares
-- row counts and distinct subject counts within each group. A contract that
-- moved rows between mappings, or attached them to the wrong subject, fails
-- here even when section B passes.
dist_d AS (
    SELECT e.mapping_id, r.event_type, e.subject_type, e.property_name,
           count(*) AS n, count(DISTINCT e.subject_id) AS s
    FROM   dep e
    JOIN   raw.raw_event r ON r.raw_event_id = e.raw_event_id
    GROUP  BY 1,2,3,4
),
dist_p AS (
    SELECT p.mapping_id, r.event_type, p.subject_type, p.property_name,
           count(*) AS n, count(DISTINCT p.subject_id) AS s
    FROM   proj p
    JOIN   raw.raw_event r ON r.raw_event_id = p.raw_event_id
    GROUP  BY 1,2,3,4
),
dist AS (
    SELECT COALESCE(d.mapping_id,   p.mapping_id)   AS mapping_id,
           COALESCE(d.event_type,   p.event_type)   AS event_type,
           COALESCE(d.subject_type, p.subject_type) AS subject_type,
           COALESCE(d.property_name,p.property_name) AS property_name,
           d.n AS dn, d.s AS ds, p.n AS pn, p.s AS ps,
           (d.n IS NOT DISTINCT FROM p.n
            AND d.s IS NOT DISTINCT FROM p.s) AS agrees
    FROM   dist_d d
    FULL OUTER JOIN dist_p p
      ON  p.mapping_id    = d.mapping_id
      AND p.event_type    = d.event_type
      AND p.subject_type  = d.subject_type
      AND p.property_name = d.property_name
),
section_c AS (
    SELECT 'C'::text, 0,
           'groups that disagree on rows or subjects'::text, ''::text,
           (SELECT count(*) FROM dist WHERE NOT agrees)::text, '0'::text,
           CASE WHEN (SELECT count(*) FROM dist WHERE NOT agrees) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'C',
           row_number() OVER (ORDER BY mapping_id, property_name)::int,
           mapping_id,
           event_type || ' -> ' || subject_type || '.' || property_name,
           'rows ' || COALESCE(pn::text,'-') || ' / subjects '
                   || COALESCE(ps::text,'-'),
           'rows ' || COALESCE(dn::text,'-') || ' / subjects '
                   || COALESCE(ds::text,'-'),
           CASE WHEN agrees THEN 'ok' ELSE 'DIFF' END
    FROM   dist
),

-- ---------------------------------------------------------------------------
-- D. ROWS ON ONE SIDE ONLY
-- ---------------------------------------------------------------------------
-- Keyed on (raw_event_id, mapping_id): the identity of an evidence row is the
-- event it came from and the mapping that read it.
only_dep AS (
    SELECT e.mapping_id, e.subject_id, e.property_name, e.asserted_value
    FROM   dep e
    WHERE  NOT EXISTS (SELECT 1 FROM proj p
                       WHERE p.raw_event_id = e.raw_event_id
                         AND p.mapping_id   = e.mapping_id)
),
only_proj AS (
    SELECT p.mapping_id, p.subject_id, p.property_name, p.asserted_value
    FROM   proj p
    WHERE  NOT EXISTS (SELECT 1 FROM dep e
                       WHERE e.raw_event_id = p.raw_event_id
                         AND e.mapping_id   = p.mapping_id)
),
one_sided AS (
    SELECT 'deployed but not projected'::text AS side, * FROM only_dep
    UNION ALL
    SELECT 'projected but not deployed'::text,        * FROM only_proj
),
section_d AS (
    SELECT 'D'::text, 0, 'rows present on one side only'::text, ''::text,
           (SELECT count(*) FROM one_sided)::text, '0'::text,
           CASE WHEN (SELECT count(*) FROM one_sided) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D',
           row_number() OVER (ORDER BY side, mapping_id, subject_id)::int,
           mapping_id,
           side || ': ' || subject_id || ' ' || property_name,
           COALESCE(asserted_value, '<null>'),
           '(no such row)',
           'FAIL'
    FROM   one_sided
),

-- ---------------------------------------------------------------------------
-- E. VALUE DISAGREEMENTS ON MATCHED ROWS
-- ---------------------------------------------------------------------------
-- evidence_id and created_at are excluded on purpose: one is a surrogate key
-- and the other records when a projection ran. Neither is part of what the
-- evidence asserts.
mismatch AS (
    SELECT e.mapping_id,
           e.raw_event_id,
           concat_ws(' | ',
             CASE WHEN e.evidence_type IS DISTINCT FROM p.evidence_type
                  THEN 'evidence_type ' || COALESCE(e.evidence_type,'<null>')
                       || ' -> ' || COALESCE(p.evidence_type,'<null>') END,
             CASE WHEN e.subject_type IS DISTINCT FROM p.subject_type
                  THEN 'subject_type ' || COALESCE(e.subject_type,'<null>')
                       || ' -> ' || COALESCE(p.subject_type,'<null>') END,
             CASE WHEN e.subject_id IS DISTINCT FROM p.subject_id
                  THEN 'subject_id ' || COALESCE(e.subject_id,'<null>')
                       || ' -> ' || COALESCE(p.subject_id,'<null>') END,
             CASE WHEN e.property_name IS DISTINCT FROM p.property_name
                  THEN 'property_name ' || COALESCE(e.property_name,'<null>')
                       || ' -> ' || COALESCE(p.property_name,'<null>') END,
             CASE WHEN e.asserted_value IS DISTINCT FROM p.asserted_value
                  THEN 'asserted_value ' || COALESCE(e.asserted_value,'<null>')
                       || ' -> ' || COALESCE(p.asserted_value,'<null>') END,
             CASE WHEN e.value_type IS DISTINCT FROM p.value_type
                  THEN 'value_type ' || COALESCE(e.value_type,'<null>')
                       || ' -> ' || COALESCE(p.value_type,'<null>') END,
             CASE WHEN e.source_system IS DISTINCT FROM p.source_system
                  THEN 'source_system ' || COALESCE(e.source_system,'<null>')
                       || ' -> ' || COALESCE(p.source_system,'<null>') END,
             CASE WHEN e.source_actor_id IS DISTINCT FROM p.source_actor_id
                  THEN 'source_actor_id ' || COALESCE(e.source_actor_id,'<null>')
                       || ' -> ' || COALESCE(p.source_actor_id,'<null>') END,
             CASE WHEN e.source_actor_role IS DISTINCT FROM p.source_actor_role
                  THEN 'source_actor_role '
                       || COALESCE(e.source_actor_role,'<null>')
                       || ' -> ' || COALESCE(p.source_actor_role,'<null>') END,
             CASE WHEN e.occurred_at IS DISTINCT FROM p.occurred_at
                  THEN 'occurred_at ' || COALESCE(e.occurred_at::text,'<null>')
                       || ' -> ' || COALESCE(p.occurred_at::text,'<null>') END,
             CASE WHEN e.recorded_at IS DISTINCT FROM p.recorded_at
                  THEN 'recorded_at ' || COALESCE(e.recorded_at::text,'<null>')
                       || ' -> ' || COALESCE(p.recorded_at::text,'<null>') END,
             CASE WHEN e.arrival_at IS DISTINCT FROM p.arrival_at
                  THEN 'arrival_at ' || COALESCE(e.arrival_at::text,'<null>')
                       || ' -> ' || COALESCE(p.arrival_at::text,'<null>') END
           ) AS differences
    FROM   dep e
    JOIN   proj p
      ON   p.raw_event_id = e.raw_event_id
     AND   p.mapping_id   = e.mapping_id
    WHERE  e.evidence_type     IS DISTINCT FROM p.evidence_type
       OR  e.subject_type      IS DISTINCT FROM p.subject_type
       OR  e.subject_id        IS DISTINCT FROM p.subject_id
       OR  e.property_name     IS DISTINCT FROM p.property_name
       OR  e.asserted_value    IS DISTINCT FROM p.asserted_value
       OR  e.value_type        IS DISTINCT FROM p.value_type
       OR  e.source_system     IS DISTINCT FROM p.source_system
       OR  e.source_actor_id   IS DISTINCT FROM p.source_actor_id
       OR  e.source_actor_role IS DISTINCT FROM p.source_actor_role
       OR  e.occurred_at       IS DISTINCT FROM p.occurred_at
       OR  e.recorded_at       IS DISTINCT FROM p.recorded_at
       OR  e.arrival_at        IS DISTINCT FROM p.arrival_at
),
section_e AS (
    SELECT 'E'::text, 0,
           'matched rows disagreeing on any semantic column'::text, ''::text,
           (SELECT count(*) FROM mismatch)::text, '0'::text,
           CASE WHEN (SELECT count(*) FROM mismatch) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'E',
           row_number() OVER (ORDER BY mapping_id, raw_event_id)::int,
           mapping_id,
           raw_event_id::text,
           differences,
           'identical',
           'FAIL'
    FROM   mismatch
),

-- ---------------------------------------------------------------------------
-- F. TIMESTAMPS PASS THROUGH UNMODIFIED
-- ---------------------------------------------------------------------------
-- occurred_at, recorded_at and arrival_at are three different facts: when it
-- happened, when the source recorded it, when it reached us. A projection that
-- collapsed them would destroy the late-arrival evidence the fold depends on.
ts_bad AS (
    SELECT p.mapping_id, p.subject_id, p.property_name
    FROM   proj p
    JOIN   raw.raw_event r ON r.raw_event_id = p.raw_event_id
    WHERE  p.occurred_at IS DISTINCT FROM r.occurred_at
       OR  p.recorded_at IS DISTINCT FROM r.recorded_at
       OR  p.arrival_at  IS DISTINCT FROM r.arrival_at
),
late AS (
    SELECT p.subject_id, p.property_name, p.occurred_at, p.arrival_at
    FROM   proj p
    WHERE  p.arrival_at::date <> p.occurred_at::date
),
section_f AS (
    SELECT 'F'::text, 0,
           'projected timestamps differing from raw.raw_event'::text, ''::text,
           (SELECT count(*) FROM ts_bad)::text, '0'::text,
           CASE WHEN (SELECT count(*) FROM ts_bad) = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'F', 1, 'late-arrival rows preserved',
           'occurred and arrival fall on different days', '',
           (SELECT count(*) FROM late)::text, 'info'
    UNION ALL
    SELECT 'F',
           1 + row_number() OVER (ORDER BY subject_id, property_name)::int,
           subject_id,
           property_name,
           'occurred ' || occurred_at::date::text,
           'arrived '  || arrival_at::date::text,
           'info'
    FROM   late
),

-- ---------------------------------------------------------------------------
-- G. THE APPROVAL CHAIN IS STILL ABSENT
-- ---------------------------------------------------------------------------
-- D4I_003 reproduces the deployed contract and extends nothing. If any of
-- these event types now projects evidence, the file did more than it claimed
-- and D4I_004's scope has been pre-empted. FINAL_PRICING_APPROVAL and
-- PRICING_CONFIRMED must also stay distinct: an approval is not a
-- confirmation, and merging them would fabricate a business fact.
chain AS (
    SELECT r.event_type, count(*) AS n
    FROM   proj p
    JOIN   raw.raw_event r ON r.raw_event_id = p.raw_event_id
    WHERE  r.event_type IN
           ('FINAL_PRICING_APPROVAL','FULLY_APPROVED','ZUPDM_APPROVED',
            'PRICING_UPLOADED','PRICING_PUBLISHED','OVERNIGHT_PUSH',
            'GO_LIVE_APPROVAL_REQUESTED','GO_LIVE_APPROVED',
            'SUPPLY_CHAIN_NOTIFIED','MATERIAL_ACTIVATED','CON_VERIFIED',
            'SAP_CON_TESTED','SAP_PRD_PROMOTED','HIERARCHY_APPROVAL')
    GROUP  BY 1
),
merged AS (
    SELECT count(*) AS n
    FROM   proj p
    JOIN   raw.raw_event r ON r.raw_event_id = p.raw_event_id
    WHERE  r.event_type = 'FINAL_PRICING_APPROVAL'
      AND  p.property_name = 'pricing_confirmed'
),
section_g AS (
    SELECT 'G'::text, 0,
           'approval-chain events projected'::text,
           'D4I_003 must add nothing'::text,
           COALESCE((SELECT sum(n) FROM chain), 0)::text, '0'::text,
           CASE WHEN COALESCE((SELECT sum(n) FROM chain), 0) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'G', 1,
           'FINAL_PRICING_APPROVAL folded into pricing_confirmed',
           'these are different business facts',
           (SELECT n FROM merged)::text, '0',
           CASE WHEN (SELECT n FROM merged) = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'G',
           1 + row_number() OVER (ORDER BY event_type)::int,
           event_type, 'unexpectedly projected', n::text, '0', 'FAIL'
    FROM   chain
),

-- ---------------------------------------------------------------------------
-- Z. OVERALL VERDICT
-- ---------------------------------------------------------------------------
body AS (
    SELECT section_a.* FROM section_a
    UNION ALL SELECT * FROM section_b
    UNION ALL SELECT * FROM section_c
    UNION ALL SELECT * FROM section_d
    UNION ALL SELECT * FROM section_e
    UNION ALL SELECT * FROM section_f
    UNION ALL SELECT * FROM section_g
),
failures AS (
    SELECT count(*) AS n FROM body WHERE verdict NOT IN ('ok','info')
),
section_z AS (
    SELECT 'Z'::text, 0,
           'D4I_003 VERDICT'::text,
           CASE WHEN (SELECT n FROM failures) = 0
                THEN 'deployed evidence contract reproduced, but '
                     || 'defaulted-evidence semantics still require review'
                ELSE 'do NOT proceed to D4I_004'
           END::text,
           CASE WHEN (SELECT n FROM failures) = 0
                THEN 'REPRODUCED' ELSE 'BLOCKED' END::text,
           (SELECT n FROM failures)::text || ' finding(s)',
           CASE WHEN (SELECT n FROM failures) = 0 THEN 'ok' ELSE 'FAIL' END
)

SELECT section,
       ord         AS seq,
       check_name  AS check,
       detail,
       actual      AS projected_or_actual,
       expected    AS deployed_or_expected,
       verdict
FROM   (SELECT * FROM body UNION ALL SELECT * FROM section_z) AS report
ORDER  BY section, ord;
