-- ============================================================================
-- VERTICAL SLICE -- widen claris.configuration.identity_digest to hold a
-- governed digest
-- ============================================================================
-- ONE COLUMN. ONE TYPE CHANGE. NOTHING ELSE.
--
-- THE DEFECT
--   claris.configuration.identity_digest is varchar(32). The governed digest
--   form locked at D.4G.2 is
--
--       v1:sha256:<64 hex>          74 characters
--
--   so the column cannot hold one. It was sized for a 32-character hash -- an
--   md5 hex, most likely -- before that contract existed.
--
-- WHY WIDEN RATHER THAN SHORTEN WHAT IS WRITTEN
--   Truncating a sha256 to fit 32 characters would put a digest in the
--   canonical layer that follows no governed contract, differs silently from
--   the v1:sha256: form every other digest in this database uses, and cannot be
--   verified against anything. claris.decision.input_digest is already
--   varchar(128) and holds exactly this form; this brings the sibling column to
--   the same width and the same contract.
--
-- WHY IT IS SAFE
--   claris.configuration holds ZERO rows, so there is nothing to rewrite and no
--   value can be lost. The column is nullable, carries no index, no unique
--   constraint and no check constraint (verified against pg_constraint before
--   this was written). Widening a varchar never rejects an existing value.
--
--   No other column is touched. canonical_identity is already varchar(256) and
--   holds the 39-character identity comfortably; configuration_id and
--   version_id are varchar(64) against 21 and 24 characters used.
--
-- WHAT identity_digest IS, AND IS NOT
--   It is a digest OF THE BUSINESS IDENTITY -- sha256 of the canonical_identity
--   string. It is NOT the decision's input_digest, which fingerprints one
--   evaluation's inputs so that decision can be replayed. Two configurations
--   carrying the same identity must produce the same identity_digest no matter
--   which decision created them, and that is only true if the digest is taken
--   over the identity rather than over the evaluation.
--
--   canonical_identity remains the authoritative key. The digest is a
--   fixed-width convenience beside it, never a substitute for it: no lookup in
--   this codebase resolves a configuration by digest.
--
-- STATUS: DEFERRED ON THIS DEPLOYMENT.
--   Nine claris.v_workbench_* views read this column and Postgres will not
--   retype a column a view depends on. None of those views has a repository
--   source, so recreating them is a job of its own, not a line in a slice
--   run. This migration detects them, reports them by name and stops. It is
--   SAFE to run: it changes nothing while they exist.
--
-- APPLY IN ONE TRANSACTION. Idempotent: re-running finds the column already
-- wide enough, or still blocked, and does nothing either way.
-- ============================================================================

DO $widen$
DECLARE
    current_width    integer;
    row_count        bigint;
    dependent_count  integer;
    dependent_views  text;
BEGIN
    SELECT character_maximum_length INTO current_width
    FROM   information_schema.columns
    WHERE  table_schema = 'claris'
      AND  table_name   = 'configuration'
      AND  column_name  = 'identity_digest';

    IF current_width IS NULL THEN
        RAISE EXCEPTION
            'claris.configuration.identity_digest does not exist as a bounded '
            'varchar; refusing to guess what to do';
    END IF;

    IF current_width >= 128 THEN
        RAISE NOTICE 'identity_digest is already varchar(%); nothing to do',
                     current_width;
        RETURN;
    END IF;

    -- Postgres will not retype a column that any view's rewrite rule reads,
    -- and nine claris.v_workbench_* views read this one. None of them has a
    -- repository source yet, so dropping and recreating them here would mean
    -- rebuilding nine definitions that exist only in the live catalogue --
    -- exactly the two-copies-drift-apart risk this engagement has been
    -- unwinding. This migration therefore REPORTS the blocker and stops,
    -- rather than aborting a transaction or guessing at a view.
    SELECT count(*), string_agg(DISTINCT v.relname, ', ' ORDER BY v.relname)
      INTO dependent_count, dependent_views
      FROM pg_depend d
      JOIN pg_rewrite r   ON r.oid = d.objid
      JOIN pg_class v     ON v.oid = r.ev_class
      JOIN pg_class c     ON c.oid = d.refobjid
      JOIN pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.refobjsubid
     WHERE n.nspname = 'claris' AND c.relname = 'configuration'
       AND a.attname = 'identity_digest'
       AND d.classid = 'pg_rewrite'::regclass
       AND v.relkind = 'v';

    IF dependent_count > 0 THEN
        RAISE NOTICE 'DEFERRED. identity_digest is varchar(%) and cannot hold '
                     'the governed v1:sha256:<64 hex> form (74 characters), but '
                     '% view(s) depend on it: %',
                     current_width, dependent_count, dependent_views;
        RAISE NOTICE 'Recover those view definitions into '
                     'database/views/claris/ first, then re-run this with the '
                     'drop/recreate around it. Until then the materializer '
                     'writes NULL rather than a truncated digest, and starts '
                     'writing digests automatically once this column is wide.';
        RETURN;
    END IF;

    SELECT count(*) INTO row_count FROM claris.configuration;
    RAISE NOTICE 'widening identity_digest from varchar(%) to varchar(128); '
                 '% existing row(s)', current_width, row_count;

    ALTER TABLE claris.configuration
        ALTER COLUMN identity_digest TYPE varchar(128);
END
$widen$;

COMMENT ON COLUMN claris.configuration.identity_digest IS
  'sha256 of canonical_identity, in the governed v1:sha256:<hex> form. A '
  'fixed-width convenience beside canonical_identity, which remains the '
  'authoritative key -- nothing resolves a configuration by digest. Distinct '
  'from claris.decision.input_digest, which fingerprints one evaluation''s '
  'inputs rather than a business identity.';

-- ---------------------------------------------------------------------------
-- proof
-- ---------------------------------------------------------------------------
SELECT table_name, column_name, data_type, character_maximum_length
FROM   information_schema.columns
WHERE  table_schema = 'claris'
  AND  table_name IN ('configuration', 'configuration_version', 'decision',
                      'product')
  AND  data_type = 'character varying'
ORDER  BY table_name, ordinal_position;

-- every canonical table is still empty; this migration wrote no data
SELECT (SELECT count(*) FROM claris.product)               AS products,
       (SELECT count(*) FROM claris.configuration)         AS configurations,
       (SELECT count(*) FROM claris.configuration_version) AS versions,
       (SELECT count(*) FROM claris.decision)              AS decisions;
