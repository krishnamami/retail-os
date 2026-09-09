-- ============================================================================
-- D4I_003c step 1 -- what are the 36 PROTOTYPE_ASSUMPTION rows?
-- READ ONLY. ONE STATEMENT. ONE GRID. NO DESIGN.
-- ============================================================================
-- runtime.evidence.simulator_classification is populated on 36 of 143 rows
-- with a single value, PROTOTYPE_ASSUMPTION. That value is not in the
-- governed vocabulary: raw.raw_event's CHECK allows only OBSERVED and
-- PROPOSED_SIMULATOR_EXTENSION, and runtime.evidence carries no CHECK on this
-- column at all.
--
-- 36 is not 39. Close enough to look like an earlier partial attempt at the
-- distinction D4I_003c is about to design; different enough to prove it is
-- not the same set. Adding a value_provenance field on top of a half
-- populated column that may already mean something adjacent is how a schema
-- ends up with two fields that disagree, so this measures the relationship
-- before anything is proposed.
--
-- THREE DIMENSIONS THAT MUST NOT BE COLLAPSED
--   1  raw event classification -- is the corpus event real or a simulator
--      extension. Governed on raw.raw_event.
--   2  evidence simulator_classification -- meaning NOT ESTABLISHED. This
--      file measures it; it does not interpret it.
--   3  value provenance -- did the source assert this value or did the
--      projection supply it. Not represented anywhere yet.
--   A row may legitimately be a prototype event carrying an explicitly
--   asserted value: synthetic source, OBSERVED value. Those are different
--   questions and this file keeps them apart.
--
-- SECTIONS
--   1  provenance x marker overlap matrix, then the explicit totals
--   2  per mapping: rows, marked, unmarked, and the four-way cross
--   3  raw marker vs evidence marker -- inherited, renamed, or introduced
--   4  representative identifiers, only if a marker was introduced
--      downstream, sized for a targeted trace and nothing more
--
-- Provenance is computed exactly as in step 0: mapping kind is declared from
-- the verified function body, presence is measured against the live payload.
-- The declaration is an input; every count is a measurement.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH decl(mapping_id, kind, src_key) AS (
    VALUES
      ('CHANGE_REQUESTED_BY',    'EXTRACTION', NULL::text),
      ('CHANGE_REQUESTER_ROLE',  'EXTRACTION', NULL),
      ('SAP_CON_HIERARCHY',      'EXTRACTION', NULL),
      ('SAP_CON_LOAD_ACTOR',     'EXTRACTION', NULL),
      ('SAP_PRD_HIERARCHY',      'EXTRACTION', NULL),
      ('PRICING_VALUE',          'EXTRACTION', NULL),
      ('PRODUCT_DEF_LAUNCH',     'EXTRACTION', NULL),
      ('PRODUCT_DEF_NAME',       'EXTRACTION', NULL),
      ('CONF_REQ_PRODUCT',       'EXTRACTION', NULL),
      ('CONF_REQ_GEO',           'EXTRACTION', NULL),
      ('CONF_REQ_TERM',          'EXTRACTION', NULL),
      ('CONF_REQ_SEGMENT',       'EXTRACTION', NULL),
      ('CONF_REQ_LAUNCH',        'EXTRACTION', NULL),
      ('MATERIAL_CREATED',       'OCCURRENCE', NULL),
      ('SKU_MINTED',             'OCCURRENCE', NULL),
      ('SKU_ACTIVATED',          'OCCURRENCE', NULL),
      ('PRICING_STATUS',         'OCCURRENCE', NULL),
      ('PRICING_CONFIRMED',      'OCCURRENCE', NULL),
      ('PRODUCT_INTENT_CLASS',   'BRANCHING',  'intent_class'),
      ('SAP_CON_LOAD_STATUS',    'BRANCHING',  'con_status'),
      ('SAP_PRD_LOAD_STATUS',    'BRANCHING',  'prd_status'),
      ('TECHNICAL_REVIEW_RESULT','BRANCHING',  'technical_approval_status')
),
c AS (
    SELECT e.evidence_id,
           e.raw_event_id,
           e.mapping_id::text               AS mapping_id,
           e.property_name::text            AS property_name,
           r.event_type::text               AS event_type,
           e.simulator_classification::text AS ev_marker,
           r.simulator_classification::text AS raw_marker,
           CASE
             WHEN d.kind IN ('EXTRACTION','OCCURRENCE') THEN 'OBSERVED'
             WHEN r.payload ? d.src_key
                  AND r.payload ->> d.src_key IS NOT NULL THEN 'OBSERVED'
             ELSE 'DEFAULTED'
           END AS provenance
    FROM   runtime.evidence e
    JOIN   raw.raw_event r ON r.raw_event_id = e.raw_event_id
    JOIN   decl d ON d.mapping_id = e.mapping_id
),
t AS (
    SELECT count(*)                                            AS n_all,
           count(ev_marker)                                    AS n_marked,
           count(*) FILTER (WHERE provenance='OBSERVED')        AS n_obs,
           count(*) FILTER (WHERE provenance='DEFAULTED')       AS n_def,
           count(*) FILTER (WHERE provenance='DERIVED')         AS n_der,
           count(*) FILTER (WHERE ev_marker IS NOT NULL
                              AND provenance='OBSERVED')        AS m_obs,
           count(*) FILTER (WHERE ev_marker IS NOT NULL
                              AND provenance='DEFAULTED')       AS m_def,
           count(*) FILTER (WHERE ev_marker IS NULL
                              AND provenance='OBSERVED')        AS u_obs,
           count(*) FILTER (WHERE ev_marker IS NULL
                              AND provenance='DEFAULTED')       AS u_def
    FROM   c
),

-- ---------------------------------------------------------------------------
-- 1. overlap
-- ---------------------------------------------------------------------------
-- If PROTOTYPE_ASSUMPTION already meant "this value was assumed", the marked
-- set would sit inside the DEFAULTED set. One marked-and-OBSERVED row proves
-- the column answers a different question.
sec1 AS (
    SELECT '1'::text AS section,
           row_number() OVER (ORDER BY provenance,
                              COALESCE(ev_marker,'~null'))::int AS ord,
           provenance::text AS item,
           COALESCE(ev_marker, '<unmarked>')::text AS detail,
           count(*)::text AS value_a,
           ''::text AS value_b,
           CASE
             WHEN provenance = 'DEFAULTED' AND ev_marker IS NOT NULL
                  THEN 'marked and defaulted'
             WHEN provenance = 'DEFAULTED'
                  THEN 'DEFAULTED BUT UNMARKED'
             WHEN ev_marker IS NOT NULL
                  THEN 'MARKED BUT OBSERVED -- column means something else'
             ELSE 'observed and unmarked'
           END::text AS note
    FROM   c
    GROUP  BY provenance, ev_marker
    UNION ALL
    SELECT '1', 100, 'total rows', 'runtime.evidence', t.n_all::text,
           'expected 143',
           CASE WHEN t.n_all = 143 THEN 'ok' ELSE 'DIFF' END FROM t
    UNION ALL
    SELECT '1', 101, 'total simulator-marked', 'ev_marker IS NOT NULL',
           t.n_marked::text, 'expected 36',
           CASE WHEN t.n_marked = 36 THEN 'ok' ELSE 'DIFF' END FROM t
    UNION ALL
    SELECT '1', 102, 'marked AND OBSERVED', 'the decisive cell',
           t.m_obs::text, '',
           CASE WHEN t.m_obs > 0
                THEN 'PROTOTYPE_ASSUMPTION IS NOT VALUE PROVENANCE'
                ELSE 'consistent with a value-provenance reading' END FROM t
    UNION ALL
    SELECT '1', 103, 'marked AND DEFAULTED', '', t.m_def::text, '', 'info' FROM t
    UNION ALL
    SELECT '1', 104, 'DEFAULTED but unmarked',
           'defaulted values the marker does not cover',
           t.u_def::text, '',
           CASE WHEN t.u_def > 0 THEN 'marker does not cover every default'
                ELSE 'marker covers every default' END FROM t
    UNION ALL
    SELECT '1', 105, 'OBSERVED and unmarked', '', t.u_obs::text, '', 'info'
    FROM   t
    UNION ALL
    SELECT '1', 106, 'OBSERVED + DEFAULTED + DERIVED',
           'must account for every row',
           (t.n_obs + t.n_def + t.n_der)::text, t.n_all::text,
           CASE WHEN t.n_obs + t.n_def + t.n_der = t.n_all
                THEN 'ok' ELSE 'DIFF -- rows unaccounted for' END FROM t
),

-- ---------------------------------------------------------------------------
-- 2. distribution by mapping
-- ---------------------------------------------------------------------------
-- A mapping carrying both marked and unmarked evidence proves the marker was
-- assigned per row or by some condition, not per mapping. Which condition is
-- not inferred here.
sec2 AS (
    SELECT '2'::text,
           row_number() OVER (ORDER BY mapping_id)::int,
           mapping_id,
           (event_type || ' -> ' || property_name)::text,
           ('rows ' || count(*)::text
             || ' / marked ' || count(ev_marker)::text
             || ' / unmarked ' || (count(*) - count(ev_marker))::text)::text,
           ('marked+OBS ' || count(*) FILTER (WHERE ev_marker IS NOT NULL
                                    AND provenance='OBSERVED')::text
             || ' / marked+DEF ' || count(*) FILTER (WHERE ev_marker IS NOT NULL
                                    AND provenance='DEFAULTED')::text
             || ' / unmarked+OBS ' || count(*) FILTER (WHERE ev_marker IS NULL
                                    AND provenance='OBSERVED')::text
             || ' / unmarked+DEF ' || count(*) FILTER (WHERE ev_marker IS NULL
                                    AND provenance='DEFAULTED')::text)::text,
           CASE
             WHEN count(ev_marker) = 0        THEN 'unmarked'
             WHEN count(ev_marker) = count(*) THEN 'every row marked'
             ELSE 'PARTIALLY MARKED -- assigned per row'
           END::text
    FROM   c
    GROUP  BY mapping_id, event_type, property_name
),

-- ---------------------------------------------------------------------------
-- 3. raw -> evidence inheritance
-- ---------------------------------------------------------------------------
-- raw.raw_event is governed to OBSERVED / PROPOSED_SIMULATOR_EXTENSION;
-- evidence holds PROTOTYPE_ASSUMPTION. If the two line up row for row the
-- evidence marker is a rename in transit. If evidence is marked where the raw
-- event is not, the marker was introduced somewhere between raw persistence
-- and this row -- which is all the data can prove. It does not name a writer,
-- and the current projection function cannot be that writer because it does
-- not return this column.
sec3 AS (
    SELECT '3'::text,
           row_number() OVER (ORDER BY COALESCE(raw_marker,'~null'),
                                       COALESCE(ev_marker,'~null'))::int,
           ('raw: ' || COALESCE(raw_marker, '<null>'))::text,
           ('evidence: ' || COALESCE(ev_marker, '<null>'))::text,
           count(*)::text,
           ''::text,
           CASE
             WHEN raw_marker IS NULL AND ev_marker IS NOT NULL
                  THEN 'INTRODUCED DOWNSTREAM -- trace required'
             WHEN raw_marker IS NOT NULL AND ev_marker IS NULL
                  THEN 'raw marker dropped'
             WHEN raw_marker = ev_marker THEN 'inherited unchanged'
             WHEN raw_marker IS NOT NULL AND ev_marker IS NOT NULL
                  THEN 'renamed in transit'
             ELSE 'neither marked'
           END::text
    FROM   c
    GROUP  BY raw_marker, ev_marker
),

-- ---------------------------------------------------------------------------
-- 4. representative identifiers for a targeted trace
-- ---------------------------------------------------------------------------
-- Only rows whose evidence marker was not inherited from the raw event, and
-- only twelve of them. Enough to trace a writer; not a dump.
sec4 AS (
    SELECT '4'::text,
           row_number() OVER (ORDER BY mapping_id, evidence_id)::int,
           mapping_id,
           ('evidence_id ' || evidence_id::text)::text,
           ('raw_event_id ' || raw_event_id::text)::text,
           ('raw ' || COALESCE(raw_marker,'<null>')
             || ' -> evidence ' || COALESCE(ev_marker,'<null>'))::text,
           provenance::text
    FROM   c
    WHERE  ev_marker IS NOT NULL
      AND  (raw_marker IS NULL OR raw_marker IS DISTINCT FROM ev_marker)
    ORDER  BY mapping_id, evidence_id
    LIMIT  12
)

SELECT section, ord AS seq, item, detail, value_a, value_b, note
FROM   (SELECT * FROM sec1
        UNION ALL SELECT * FROM sec2
        UNION ALL SELECT * FROM sec3
        UNION ALL SELECT * FROM sec4) AS probe
ORDER  BY section, ord;
