-- ============================================================================
-- D4I_003c step 0 -- LIVE EVIDENCE-PROVENANCE DISCOVERY
-- READ ONLY. ONE STATEMENT. ONE GRID. NO DESIGN.
-- ============================================================================
-- Nothing is designed until this has run. Five times in this project the
-- repository DDL has disagreed with the live database -- an enum, a column
-- name, a release status, two subject columns, a governance_basis column that
-- did not exist -- and once a varchar(32) that had to hold 74 characters. So
-- the provenance field is not proposed from what the repo says the schema is.
-- It is proposed from what the catalogue reports it is.
--
-- This file cannot fail on a missing column. Sections 6, 7 and 8 reach
-- evidence_lineage through to_jsonb(e)->'evidence_lineage', which yields NULL
-- if no such column exists rather than raising. Whether that column exists is
-- one of the things being measured.
--
-- SECTIONS
--   1  runtime.evidence: every column, udt, width, nullability, default,
--      identity and generation
--   2  related tables, their columns, and their foreign-key relationship to
--      runtime.evidence in both directions
--   3  constraints on runtime.evidence
--   4  every column anywhere already shaped like a provenance field
--   5  every enum label and every CHECK vocabulary already carrying
--      OBSERVED / DEFAULTED / DERIVED / ASSUMED
--   6  evidence_lineage: presence, physical type, key coverage, and one
--      representative object per distinct key signature -- not 143 dumps
--   7  source_path truth test: for every mapping, does the recorded
--      source_path actually resolve against its raw event
--   8  measured provenance totals, so section F of the report is a
--      measurement and not a prediction
--
-- SECTION 7 IS THE POINT
--   A source_path recorded in lineage does not prove the source field
--   existed. It records the intended lookup, which for a defaulted value is
--   a lookup that returned nothing. Section 7 measures the difference.
--
-- WHAT SECTION 8 ASSUMES AND WHAT IT MEASURES
--   The kind of each mapping -- EXTRACTION, OCCURRENCE, BRANCHING -- is
--   declared below from the verified body of runtime.evidence_projection_v1
--   (five markers present, length 20534). That declaration is an input.
--   Every count beside it is measured against the live payloads. Where the
--   two disagree the grid says DIFF and the measurement wins; expectations
--   are printed so they can be contradicted, not so they can be confirmed.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT anywhere in this file.
-- ============================================================================

WITH ev AS (
    SELECT e.*,
           to_jsonb(e) -> 'evidence_lineage' AS lin
    FROM   runtime.evidence e
),

-- The declared shape of each deployed mapping, read from the verified
-- function body. kind: EXTRACTION = value came from a payload path or raw
-- column; OCCURRENCE = the event happening is the fact and the constant
-- names it; BRANCHING = COALESCE, so provenance is per row. src_key is the
-- top-level payload key a BRANCHING mapping probes.
decl(mapping_id, kind, src_key, exp_observed, exp_defaulted) AS (
    VALUES
      ('CHANGE_REQUESTED_BY',    'EXTRACTION', NULL::text, NULL::int, NULL::int),
      ('CHANGE_REQUESTER_ROLE',  'EXTRACTION', NULL, NULL, NULL),
      ('SAP_CON_HIERARCHY',      'EXTRACTION', NULL, NULL, NULL),
      ('SAP_CON_LOAD_ACTOR',     'EXTRACTION', NULL, NULL, NULL),
      ('SAP_PRD_HIERARCHY',      'EXTRACTION', NULL, NULL, NULL),
      ('PRICING_VALUE',          'EXTRACTION', NULL, NULL, NULL),
      ('PRODUCT_DEF_LAUNCH',     'EXTRACTION', NULL, NULL, NULL),
      ('PRODUCT_DEF_NAME',       'EXTRACTION', NULL, NULL, NULL),
      ('CONF_REQ_PRODUCT',       'EXTRACTION', NULL, NULL, NULL),
      ('CONF_REQ_GEO',           'EXTRACTION', NULL, NULL, NULL),
      ('CONF_REQ_TERM',          'EXTRACTION', NULL, NULL, NULL),
      ('CONF_REQ_SEGMENT',       'EXTRACTION', NULL, NULL, NULL),
      ('CONF_REQ_LAUNCH',        'EXTRACTION', NULL, NULL, NULL),
      ('MATERIAL_CREATED',       'OCCURRENCE', NULL, NULL, NULL),
      ('SKU_MINTED',             'OCCURRENCE', NULL, NULL, NULL),
      ('SKU_ACTIVATED',          'OCCURRENCE', NULL, NULL, NULL),
      ('PRICING_STATUS',         'OCCURRENCE', NULL, NULL, NULL),
      ('PRICING_CONFIRMED',      'OCCURRENCE', NULL, NULL, NULL),
      ('PRODUCT_INTENT_CLASS',   'BRANCHING',  'intent_class',              0, 13),
      ('SAP_CON_LOAD_STATUS',    'BRANCHING',  'con_status',                4,  9),
      ('SAP_PRD_LOAD_STATUS',    'BRANCHING',  'prd_status',                0,  9),
      ('TECHNICAL_REVIEW_RESULT','BRANCHING',  'technical_approval_status', 1,  8)
),

-- ---------------------------------------------------------------------------
-- 1. runtime.evidence -- exact live structure
-- ---------------------------------------------------------------------------
sec1 AS (
    SELECT '1'::text AS section,
           c.ordinal_position::int AS ord,
           c.column_name::text AS item,
           (c.data_type
            || COALESCE('(' || c.character_maximum_length::text || ')', '')
            || '  udt=' || c.udt_name)::text AS detail,
           (CASE WHEN c.is_nullable = 'YES' THEN 'nullable' ELSE 'NOT NULL' END
            || CASE WHEN c.is_identity = 'YES'
                    THEN '  identity ' || COALESCE(c.identity_generation,'')
                    ELSE '' END
            || CASE WHEN c.is_generated <> 'NEVER'
                    THEN '  generated ' || c.is_generated ELSE '' END)::text
             AS value_a,
           COALESCE(c.column_default, COALESCE(c.generation_expression, ''))::text
             AS value_b,
           'info'::text AS note
    FROM   information_schema.columns c
    WHERE  c.table_schema = 'runtime' AND c.table_name = 'evidence'
),

-- ---------------------------------------------------------------------------
-- 2. related tables, their columns, and their relationship to the evidence
-- ---------------------------------------------------------------------------
-- Anything that could already store provenance without a new column on
-- runtime.evidence: every table in the runtime schema, plus anything named
-- for evidence, lineage, provenance, assertion, mapping or projection.
rel_tables AS (
    SELECT t.table_schema::text AS sch, t.table_name::text AS tab,
           t.table_type::text AS typ
    FROM   information_schema.tables t
    WHERE  t.table_schema NOT IN ('pg_catalog','information_schema')
      AND  (t.table_schema = 'runtime'
            OR t.table_name ILIKE '%evidence%'
            OR t.table_name ILIKE '%lineage%'
            OR t.table_name ILIKE '%provenance%'
            OR t.table_name ILIKE '%assertion%'
            OR t.table_name ILIKE '%mapping%'
            OR t.table_name ILIKE '%projection%')
),
fk_edges AS (
    SELECT (chn.nspname || '.' || ch.relname)::text AS child,
           (pan.nspname || '.' || pa.relname)::text AS parent,
           pg_get_constraintdef(con.oid)::text AS def
    FROM   pg_constraint con
    JOIN   pg_class ch      ON ch.oid  = con.conrelid
    JOIN   pg_namespace chn ON chn.oid = ch.relnamespace
    JOIN   pg_class pa      ON pa.oid  = con.confrelid
    JOIN   pg_namespace pan ON pan.oid = pa.relnamespace
    WHERE  con.contype = 'f'
      AND  ((pan.nspname = 'runtime' AND pa.relname = 'evidence')
            OR (chn.nspname = 'runtime' AND ch.relname = 'evidence'))
),
sec2 AS (
    SELECT '2'::text, row_number() OVER (ORDER BY sch, tab)::int,
           (sch || '.' || tab)::text, typ,
           (SELECT string_agg(c.column_name || ' ' || c.udt_name, ', '
                              ORDER BY c.ordinal_position)
            FROM information_schema.columns c
            WHERE c.table_schema = sch AND c.table_name = tab)::text,
           ''::text, 'info'::text
    FROM   rel_tables
    UNION ALL
    SELECT '2', 100 + row_number() OVER (ORDER BY child, parent)::int,
           child, 'FOREIGN KEY -> ' || parent, def, ''::text,
           'relationship'::text
    FROM   fk_edges
),

-- ---------------------------------------------------------------------------
-- 3. constraints on runtime.evidence
-- ---------------------------------------------------------------------------
sec3 AS (
    SELECT '3'::text, row_number() OVER (ORDER BY con.contype, con.conname)::int,
           con.conname::text,
           (CASE con.contype WHEN 'c' THEN 'CHECK' WHEN 'p' THEN 'PRIMARY KEY'
                             WHEN 'u' THEN 'UNIQUE' WHEN 'f' THEN 'FOREIGN KEY'
                             ELSE con.contype::text END)::text,
           pg_get_constraintdef(con.oid)::text,
           COALESCE((SELECT string_agg(a.attname, ', ' ORDER BY a.attnum)
                     FROM unnest(con.conkey) AS k(attnum)
                     JOIN pg_attribute a ON a.attrelid = con.conrelid
                                        AND a.attnum   = k.attnum), '')::text,
           'info'::text
    FROM   pg_constraint con
    JOIN   pg_class     cl ON cl.oid = con.conrelid
    JOIN   pg_namespace ns ON ns.oid = cl.relnamespace
    WHERE  ns.nspname = 'runtime' AND cl.relname = 'evidence'
),

-- ---------------------------------------------------------------------------
-- 4. every column anywhere already shaped like a provenance field
-- ---------------------------------------------------------------------------
-- Discovery only. If one of these exists and is governed, reusing it beats
-- adding another -- but nothing is selected here.
sec4 AS (
    SELECT '4'::text,
           row_number() OVER (ORDER BY c.table_schema, c.table_name,
                                       c.column_name)::int,
           (c.table_schema || '.' || c.table_name || '.' || c.column_name)::text,
           (c.data_type
            || COALESCE('(' || c.character_maximum_length::text || ')', '')
            || '  udt=' || c.udt_name)::text,
           (CASE WHEN c.is_nullable = 'YES' THEN 'nullable'
                 ELSE 'NOT NULL' END)::text,
           COALESCE(c.column_default, '')::text,
           'candidate'::text
    FROM   information_schema.columns c
    WHERE  c.table_schema NOT IN ('pg_catalog','information_schema')
      AND  c.column_name ~* ('(provenance|lineage|origin|source_kind'
                          || '|source_type|value_source|observation'
                          || '|derivation|defaulted|is_default|assumed'
                          || '|evidence_source|asserted_by)')
),

-- ---------------------------------------------------------------------------
-- 5. existing vocabulary: enums and CHECK constraints
-- ---------------------------------------------------------------------------
sec5 AS (
    SELECT '5'::text,
           row_number() OVER (ORDER BY n.nspname, t.typname, e.enumsortorder)::int,
           (n.nspname || '.' || t.typname)::text,
           'enum label'::text, e.enumlabel::text, ''::text,
           'candidate'::text
    FROM   pg_type t
    JOIN   pg_namespace n ON n.oid = t.typnamespace
    JOIN   pg_enum e ON e.enumtypid = t.oid
    WHERE  upper(e.enumlabel) IN ('OBSERVED','DEFAULTED','DERIVED','ASSUMED')
    UNION ALL
    SELECT '5', 100 + row_number() OVER (ORDER BY ns.nspname, cl.relname,
                                                  con.conname)::int,
           (ns.nspname || '.' || cl.relname || '.' || con.conname)::text,
           'CHECK vocabulary'::text,
           pg_get_constraintdef(con.oid)::text, ''::text,
           'candidate'::text
    FROM   pg_constraint con
    JOIN   pg_class cl ON cl.oid = con.conrelid
    JOIN   pg_namespace ns ON ns.oid = cl.relnamespace
    WHERE  con.contype = 'c'
      AND  pg_get_constraintdef(con.oid) ~* '(OBSERVED|DEFAULTED|DERIVED|ASSUMED)'
),

-- ---------------------------------------------------------------------------
-- 6. evidence_lineage: presence, type, keys, representative structure
-- ---------------------------------------------------------------------------
lin_keys AS (
    SELECT k::text AS k, count(*)::bigint AS n
    FROM   ev, LATERAL jsonb_object_keys(ev.lin) AS k
    WHERE  jsonb_typeof(ev.lin) = 'object'
    GROUP  BY 1
),
lin_sig AS (
    SELECT (SELECT array_agg(k ORDER BY k)
            FROM jsonb_object_keys(ev.lin) AS k) AS keys,
           ev.lin
    FROM   ev
    WHERE  jsonb_typeof(ev.lin) = 'object'
),
lin_rep AS (
    SELECT array_to_string(keys, ', ') AS sig,
           count(*)::bigint AS n,
           left((array_agg(lin::text ORDER BY lin::text))[1], 320) AS sample
    FROM   lin_sig GROUP BY 1
),
sec6 AS (
    SELECT '6'::text, 0,
           'evidence_lineage'::text,
           'probed via to_jsonb, so an absent column reports rather than raises'::text,
           ((SELECT count(*) FROM ev WHERE lin IS NOT NULL)::text || ' of '
             || (SELECT count(*) FROM ev)::text || ' rows populated')::text,
           COALESCE((SELECT c.udt_name FROM information_schema.columns c
                     WHERE c.table_schema='runtime' AND c.table_name='evidence'
                       AND c.column_name='evidence_lineage'),
                    '<not a physical column>')::text,
           COALESCE((SELECT jsonb_typeof(lin) FROM ev
                     WHERE lin IS NOT NULL LIMIT 1), '<absent>')::text
    UNION ALL
    SELECT '6', row_number() OVER (ORDER BY k)::int,
           k, 'lineage key', n::text,
           ((SELECT count(*) FROM ev)::text || ' rows total')::text,
           CASE WHEN n = (SELECT count(*) FROM ev)
                THEN 'on every row' ELSE 'PARTIAL' END
    FROM   lin_keys
    UNION ALL
    SELECT '6', 50 + row_number() OVER (ORDER BY sig)::int,
           'key signature', sig, n::text || ' rows', sample, 'representative'
    FROM   lin_rep
),

-- ---------------------------------------------------------------------------
-- 7. SOURCE_PATH TRUTH TEST
-- ---------------------------------------------------------------------------
-- 'payload.a.b' is read as raw_event.payload #> {a,b}. A path resolving to
-- SQL NULL was never there. A path resolving to JSON null was there and was
-- null -- a different fact, counted as absent for provenance purposes because
-- no value was asserted.
resolved AS (
    SELECT e.mapping_id::text AS mapping_id,
           (e.lin ->> 'source_path')::text AS source_path,
           ((e.lin ->> 'source_path') LIKE 'payload.%') AS is_payload_path,
           CASE WHEN (e.lin ->> 'source_path') LIKE 'payload.%'
                THEN r.payload #> string_to_array(
                         right(e.lin ->> 'source_path', -8), '.')
           END AS hit
    FROM   ev e
    JOIN   raw.raw_event r ON r.raw_event_id = e.raw_event_id
),
sec7_agg AS (
    SELECT r.mapping_id,
           COALESCE(r.source_path, '<no source_path>') AS source_path,
           count(*)::bigint AS rows_total,
           count(*) FILTER (WHERE r.hit IS NOT NULL
                              AND r.hit IS DISTINCT FROM 'null'::jsonb)::bigint
             AS present,
           bool_and(COALESCE(r.is_payload_path, false)) AS all_payload_paths,
           d.kind
    FROM   resolved r
    LEFT JOIN decl d ON d.mapping_id = r.mapping_id
    GROUP  BY r.mapping_id, COALESCE(r.source_path,'<no source_path>'), d.kind
),
sec7 AS (
    SELECT '7'::text,
           row_number() OVER (ORDER BY mapping_id, source_path)::int,
           mapping_id::text,
           (source_path || '   [' || COALESCE(kind,'UNDECLARED') || ']')::text,
           ('present ' || present::text || ' / absent '
             || (rows_total - present)::text
             || ' of ' || rows_total::text)::text,
           CASE
             WHEN NOT all_payload_paths       THEN 'no payload path to resolve'
             WHEN present = rows_total        THEN 'lineage honest on every row'
             WHEN present = 0                 THEN 'lineage names a source never read'
             ELSE 'lineage honest on some rows only'
           END::text,
           CASE
             WHEN kind = 'OCCURRENCE'         THEN 'occurrence -> OBSERVED'
             WHEN kind = 'EXTRACTION'
                  AND (NOT all_payload_paths OR present = rows_total)
                                              THEN 'extraction -> OBSERVED'
             WHEN kind = 'EXTRACTION'         THEN 'UNEXPECTED: extraction with absent source'
             WHEN kind = 'BRANCHING'          THEN 'per row -> ' || present::text
                                                    || ' OBSERVED / '
                                                    || (rows_total - present)::text
                                                    || ' DEFAULTED'
             ELSE 'UNDECLARED MAPPING'
           END::text
    FROM   sec7_agg
),

-- ---------------------------------------------------------------------------
-- 8. MEASURED PROVENANCE TOTALS
-- ---------------------------------------------------------------------------
-- Classification kind is declared; every count is measured. A BRANCHING row
-- is OBSERVED only when its declared source key is present AND non-null in
-- the raw payload; otherwise the projection's fallback supplied the value.
classified AS (
    SELECT e.mapping_id::text AS mapping_id,
           e.property_name::text AS property_name,
           r.event_type::text AS event_type,
           d.kind,
           CASE
             WHEN d.kind IS NULL THEN 'UNCLASSIFIED'
             WHEN d.kind IN ('EXTRACTION','OCCURRENCE') THEN 'OBSERVED'
             WHEN r.payload ? d.src_key
                  AND r.payload ->> d.src_key IS NOT NULL THEN 'OBSERVED'
             ELSE 'DEFAULTED'
           END AS provenance
    FROM   ev e
    JOIN   raw.raw_event r ON r.raw_event_id = e.raw_event_id
    LEFT JOIN decl d ON d.mapping_id = e.mapping_id
),
sec8 AS (
    SELECT '8'::text, 0, 'OBSERVED'::text, 'measured'::text,
           (SELECT count(*) FROM classified WHERE provenance='OBSERVED')::text,
           'expected 104'::text,
           CASE WHEN (SELECT count(*) FROM classified
                      WHERE provenance='OBSERVED') = 104
                THEN 'match' ELSE 'DIFF -- measurement wins' END::text
    UNION ALL
    SELECT '8', 1, 'DEFAULTED', 'measured',
           (SELECT count(*) FROM classified WHERE provenance='DEFAULTED')::text,
           'expected 39',
           CASE WHEN (SELECT count(*) FROM classified
                      WHERE provenance='DEFAULTED') = 39
                THEN 'match' ELSE 'DIFF -- measurement wins' END
    UNION ALL
    SELECT '8', 2, 'DERIVED', 'no deployed mapping computes a value',
           (SELECT count(*) FROM classified WHERE provenance='DERIVED')::text,
           'expected 0',
           CASE WHEN (SELECT count(*) FROM classified
                      WHERE provenance='DERIVED') = 0
                THEN 'match' ELSE 'DIFF -- measurement wins' END
    UNION ALL
    SELECT '8', 3, 'UNCLASSIFIED',
           'a mapping the declaration does not cover',
           (SELECT count(*) FROM classified
            WHERE provenance='UNCLASSIFIED')::text,
           'expected 0',
           CASE WHEN (SELECT count(*) FROM classified
                      WHERE provenance='UNCLASSIFIED') = 0
                THEN 'match' ELSE 'DIFF -- declaration incomplete' END
    UNION ALL
    SELECT '8', 4, 'TOTAL', 'every evidence row is classified exactly once',
           (SELECT count(*) FROM classified)::text, 'expected 143',
           CASE WHEN (SELECT count(*) FROM classified) = 143
                THEN 'match' ELSE 'DIFF -- measurement wins' END
    UNION ALL
    SELECT '8', 10 + row_number() OVER (ORDER BY c.mapping_id)::int,
           c.mapping_id,
           (c.event_type || ' -> ' || c.property_name)::text,
           ('DEFAULTED ' || count(*) FILTER (WHERE c.provenance='DEFAULTED')::text
             || ' / OBSERVED '
             || count(*) FILTER (WHERE c.provenance='OBSERVED')::text)::text,
           ('expected DEFAULTED ' || COALESCE(max(d.exp_defaulted)::text,'-')
             || ' / OBSERVED ' || COALESCE(max(d.exp_observed)::text,'-'))::text,
           CASE WHEN count(*) FILTER (WHERE c.provenance='DEFAULTED')
                     = max(d.exp_defaulted)
                 AND count(*) FILTER (WHERE c.provenance='OBSERVED')
                     = max(d.exp_observed)
                THEN 'match' ELSE 'DIFF -- measurement wins' END
    FROM   classified c
    JOIN   decl d ON d.mapping_id = c.mapping_id
    WHERE  d.kind = 'BRANCHING'
    GROUP  BY c.mapping_id, c.event_type, c.property_name
)

SELECT section, ord AS seq, item, detail, value_a, value_b, note
FROM   (SELECT * FROM sec1
        UNION ALL SELECT * FROM sec2
        UNION ALL SELECT * FROM sec3
        UNION ALL SELECT * FROM sec4
        UNION ALL SELECT * FROM sec5
        UNION ALL SELECT * FROM sec6
        UNION ALL SELECT * FROM sec7
        UNION ALL SELECT * FROM sec8) AS discovery
ORDER  BY section, ord;
