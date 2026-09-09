-- ============================================================================
-- D4I_004 step 2 discovery -- assertions and fold. READ ONLY. ONE STATEMENT.
-- ============================================================================
-- The evidence layer now holds 257 rows, but assertions are built by a
-- transform scoped to seven mapping_ids AND simulator_classification =
-- 'PROTOTYPE_ASSUMPTION' -- the 36 prototype rows. The 114 new approval rows
-- carry no marker, so nothing currently promotes them, and readiness would be
-- deciding from a state that has never seen the approval chain.
--
-- Before extending that transform, four things must be measured rather than
-- assumed:
--   A  what runtime.assertion holds now, and how much of the evidence layer
--      it already covers
--   B  whether source_evidence_id is unique -- the idempotency guard depends
--      on it
--   C  what fold snapshots exist, at which horizons, over which subjects
--   D  what runtime.fold_snapshot_at_horizon actually does when called twice
--      at the same horizon: replace, upsert, or raise. Re-running a fold is
--      the whole point of replay, and guessing here risks either a unique
--      violation or a silently stale snapshot.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH secA AS (
    SELECT 'A'::text AS section, 1 AS ord, 'assertion rows'::text AS item,
           ''::text AS detail,
           (SELECT count(*) FROM runtime.assertion)::text AS value_a,
           ''::text AS value_b, 'info'::text AS note
    UNION ALL
    SELECT 'A', 2, 'with source_evidence_id', '',
           (SELECT count(source_evidence_id) FROM runtime.assertion)::text,
           (SELECT count(*) FROM runtime.assertion
            WHERE source_evidence_id IS NULL)::text || ' without', 'info'
    UNION ALL
    SELECT 'A', 3, 'evidence rows already promoted', '',
           (SELECT count(*) FROM runtime.evidence e
            WHERE EXISTS (SELECT 1 FROM runtime.assertion a
                          WHERE a.source_evidence_id = e.evidence_id))::text,
           'of 257', 'info'
    UNION ALL
    SELECT 'A', 4, 'evidence rows NOT yet promoted', 'the D4I_004 gap',
           (SELECT count(*) FROM runtime.evidence e
            WHERE NOT EXISTS (SELECT 1 FROM runtime.assertion a
                              WHERE a.source_evidence_id = e.evidence_id))::text,
           '', 'info'
    UNION ALL
    SELECT 'A', 10 + row_number() OVER (ORDER BY a.subject_type)::int,
           a.subject_type::text, 'assertions by subject',
           count(*)::text,
           ('authorities: ' || string_agg(DISTINCT a.authority, ', '))::text,
           'info'
    FROM   runtime.assertion a GROUP BY a.subject_type
    UNION ALL
    SELECT 'A', 40 + row_number() OVER (ORDER BY e.subject_type)::int,
           e.subject_type::text, 'UNPROMOTED evidence by subject',
           count(*)::text,
           ('mappings: ' || count(DISTINCT e.mapping_id)::text)::text,
           'D4I_004 target'
    FROM   runtime.evidence e
    WHERE  NOT EXISTS (SELECT 1 FROM runtime.assertion a
                       WHERE a.source_evidence_id = e.evidence_id)
    GROUP  BY e.subject_type
),
secB AS (
    SELECT 'B'::text, row_number() OVER (ORDER BY con.conname)::int,
           con.conname::text,
           (CASE con.contype WHEN 'c' THEN 'CHECK' WHEN 'p' THEN 'PRIMARY KEY'
                             WHEN 'u' THEN 'UNIQUE' WHEN 'f' THEN 'FOREIGN KEY'
                             WHEN 'n' THEN 'NOT NULL'
                             ELSE con.contype::text END)::text,
           pg_get_constraintdef(con.oid)::text, ''::text, 'info'::text
    FROM   pg_constraint con
    JOIN   pg_class cl ON cl.oid = con.conrelid
    JOIN   pg_namespace ns ON ns.oid = cl.relnamespace
    WHERE  ns.nspname = 'runtime' AND cl.relname = 'assertion'
      AND  con.contype IN ('p','u','f','c')
),
secC AS (
    SELECT 'C'::text, row_number() OVER (ORDER BY s.decision_horizon,
                                                  s.subject_type)::int,
           s.decision_horizon::text,
           s.subject_type::text,
           count(*)::text,
           ('folded properties ' ||
             COALESCE(sum(jsonb_array_length(s.folded_properties)),0)::text)::text,
           'info'::text
    FROM   state.fold_state_snapshot s
    GROUP  BY s.decision_horizon, s.subject_type
),
secD AS (
    SELECT 'D'::text, row_number() OVER (ORDER BY p.proname)::int,
           (n.nspname || '.' || p.proname)::text,
           pg_get_function_arguments(p.oid)::text,
           (length(p.prosrc)::text || ' chars, volatility '
             || p.provolatile::text)::text,
           (CASE WHEN p.prosrc ILIKE '%ON CONFLICT%' THEN 'ON CONFLICT '
                 ELSE '' END
            || CASE WHEN p.prosrc ILIKE '%DELETE%' THEN 'DELETE ' ELSE '' END
            || CASE WHEN p.prosrc ILIKE '%UPDATE%' THEN 'UPDATE ' ELSE '' END
            || CASE WHEN p.prosrc ILIKE '%INSERT%' THEN 'INSERT ' ELSE '' END
           )::text,
           CASE WHEN p.prosrc ILIKE '%ON CONFLICT%' THEN 'idempotent-capable'
                WHEN p.prosrc ILIKE '%DELETE%'     THEN 'replaces the horizon'
                ELSE 'CHECK BEFORE RE-RUNNING' END::text
    FROM   pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE  n.nspname IN ('runtime','state')
      AND  (p.proname ILIKE '%fold%' OR p.proname ILIKE '%snapshot%')
)
SELECT section, ord AS seq, item, detail, value_a, value_b, note
FROM   (SELECT * FROM secA UNION ALL SELECT * FROM secB
        UNION ALL SELECT * FROM secC UNION ALL SELECT * FROM secD) AS d
ORDER  BY section, ord;
