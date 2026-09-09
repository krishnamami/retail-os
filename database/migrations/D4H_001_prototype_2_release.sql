-- ============================================================================
-- VERTICAL SLICE -- author release 2026.10-prototype.2
-- ============================================================================
-- ONE incremental prototype release. It exists because the prototype.1 rule set
-- cannot reach the outcomes prototype.1 itself declares: nothing bound
-- CREATE_PRODUCT, and nothing bound "a new identity under a product that
-- already has a configuration". Run the seven corpus requests against
-- prototype.1 and all seven conclude CANNOT_DECIDE.
--
-- WHAT CHANGES
--   + IA-PRED-005  MATCH  precedence 3  -> CREATE_PRODUCT
--                  renders IR-001, which the source calls tautological and
--                  which reads no dimension.
--   + IA-PRED-006  MATCH  precedence 7  -> CREATE_CONFIGURATION
--                  renders IR-002/IR-003/IR-004 jointly -- geography, term and
--                  segment additions, all three already proposing
--                  CREATE_CONFIGURATION, all three inside the locked tuple.
--   + PR-001..PR-004 projection rules, carried VERBATIM from the 2026.10
--                  authoring release. Not re-authored, not reinterpreted.
--
-- WHAT DOES NOT CHANGE
--   The locked identity tuple. The seven configuration dimensions. The eight
--   identity rules and their proposed effects. The six governed outcomes. The
--   two guards and their precedence. IR-006 stays unresolved and IR-007 stays
--   absent. No dimension leaves UNKNOWN. No assumption is added.
--
-- PARENT -- A DIVERGENCE FROM THE INSTRUCTION, AND WHY
--   The instruction named prototype.1 as the parent. Both
--   ck_ontology_release_parent_class and the compiler's own validation require
--   parent_release_class = 'AUTHORITATIVE': a prototype descends from the
--   authoritative release it derives meaning from, never from another
--   prototype, which is what stops assumption-on-assumption drift. So the
--   parent is 2026.10 / AUTHORITATIVE, exactly as prototype.1's is, and the
--   prototype.1 lineage is recorded in the description instead.
--
-- PROTOTYPE.1 IS NOT TOUCHED
--   Its authoring rows are read, never written, so recompiling prototype.1
--   still reproduces digest 888b202b... and the D.4G.4 verifier keeps passing.
--   Its authoring release also stays status 'published' -- marking it
--   'superseded' would make that same verifier's recompilation refuse, since
--   the compiler only compiles a published release. Only the ARTIFACT
--   lifecycle changes, and that happens in a later, separate migration.
--
-- COLUMN LISTS ARE READ FROM THE CATALOGUE, NEVER TYPED
--   The copy below builds its own column lists from information_schema.
--   Four defects in D.4G came from naming a live column out of a repository
--   file; this migration cannot repeat that, because it names no column it has
--   not just read.
--
-- APPLY IN ONE TRANSACTION. Idempotent: re-running inserts nothing twice.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. the release row -- the anchor every composite FK hangs on
-- ---------------------------------------------------------------------------
INSERT INTO ontology_authoring.ontology_release (
    domain, ontology_version, description, status, release_class,
    validation_status, parent_ontology_version, parent_release_class,
    source_namespace, source_sha256, created_by, published_at, published_by
)
SELECT
    'retail',
    '2026.10-prototype.2',
    'PROTOTYPE. NOT CLARIS APPROVED. FOR DEMONSTRATION ONLY. '
    'Successor to 2026.10-prototype.1, which it copies row for row and then '
    'extends with exactly two executable predicate bindings (IA-PRED-005 '
    'CREATE_PRODUCT, rendering IR-001; IA-PRED-006 CREATE_CONFIGURATION, '
    'rendering IR-002/IR-003/IR-004) and the four projection rules PR-001..'
    'PR-004 carried verbatim from 2026.10. No new business assumption, no '
    'change to the locked identity tuple, no dimension moved off UNKNOWN. '
    'The parent is 2026.10/AUTHORITATIVE because a prototype descends from an '
    'authoritative release, never from another prototype. Every governed value '
    'here remains an engineering assumption awaiting validation with Claris; '
    'Q-001 through Q-007 remain open.',
    'published',
    'PROTOTYPE',
    'TO_BE_VALIDATED_WITH_CLARIS',
    '2026.10',
    'AUTHORITATIVE',
    'repository:ontology/source/claris_ontology.sql',
    NULL,
    'engineering:vertical-slice',
    now(),
    'engineering:vertical-slice'
WHERE NOT EXISTS (
    SELECT 1 FROM ontology_authoring.ontology_release
    WHERE domain = 'retail' AND ontology_version = '2026.10-prototype.2'
);

-- ---------------------------------------------------------------------------
-- 2. copy every governed section forward
-- ---------------------------------------------------------------------------
-- Column lists come from information_schema; ontology_version is replaced with
-- the new release and everything else travels through unaltered, so the
-- successor cannot silently differ from its predecessor in a column nobody
-- thought to list.
--
-- projection_rules is the one section drawn from 2026.10 rather than from
-- prototype.1: prototype.1 carried none, and these four are the authoritative
-- release's own rows. The table has no release_class or governance_basis
-- column, so nothing authoritative travels with them -- the release they now
-- belong to supplies the classification.
DO $copy$
DECLARE
    v_new  constant text := '2026.10-prototype.2';
    v_dom  constant text := 'retail';
    t      text;
    v_from text;
    cols   text;
    vals   text;
    n      integer;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'actors',
        'configuration_dimensions',
        'identity_rules',
        'decisions',
        'decision_outputs',
        'decision_rule_bindings',
        'projection_rules'
    ] LOOP
        v_from := CASE WHEN t = 'projection_rules'
                       THEN '2026.10' ELSE '2026.10-prototype.1' END;

        SELECT string_agg(quote_ident(column_name), ', '
                          ORDER BY ordinal_position),
               string_agg(CASE WHEN column_name = 'ontology_version'
                               THEN quote_literal(v_new)
                               ELSE quote_ident(column_name) END, ', '
                          ORDER BY ordinal_position)
          INTO cols, vals
          FROM information_schema.columns
         WHERE table_schema = 'ontology_authoring' AND table_name = t;

        IF cols IS NULL THEN
            RAISE EXCEPTION 'ontology_authoring.% has no columns; refusing', t;
        END IF;

        EXECUTE format(
            'INSERT INTO ontology_authoring.%I (%s) SELECT %s '
            'FROM ontology_authoring.%I WHERE domain = %L AND '
            'ontology_version = %L AND NOT EXISTS (SELECT 1 FROM '
            'ontology_authoring.%I x WHERE x.domain = %L AND '
            'x.ontology_version = %L)',
            t, cols, vals, t, v_dom, v_from, t, v_dom, v_new);
        GET DIAGNOSTICS n = ROW_COUNT;
        RAISE NOTICE 'ontology_authoring.% : % row(s) copied from %',
                     t, n, v_from;
    END LOOP;
END
$copy$;

-- ---------------------------------------------------------------------------
-- 3. the two new executable bindings
-- ---------------------------------------------------------------------------
-- Precedence is the whole contract here.
--
--   1  IA-PRED-001  GUARD  missing required input      -> CANNOT_DECIDE
--   2  IA-PRED-002  GUARD  contradicted required input -> CANNOT_DECIDE
--   3  IA-PRED-005  MATCH  no canonical product        -> CREATE_PRODUCT
--   5  IA-PRED-003  MATCH  initial configuration       -> CREATE_CONFIGURATION
--   6  IA-PRED-004  MATCH  exact identity match        -> NO_BUSINESS_CHANGE
--   7  IA-PRED-006  MATCH  additional configuration    -> CREATE_CONFIGURATION
--
-- Both guards keep running before any CREATE outcome, because the executor
-- evaluates every GUARD before any MATCH regardless of precedence number.
--
-- 6 BEFORE 7 IS LOAD-BEARING. Reversed, a request whose identity already
-- exists would create a second configuration carrying an identity that is by
-- construction unique -- the exact proliferation this platform exists to stop.
--
-- No FALLBACK is added. D.4B locked none for IDENTITY_ASSESSMENT, and
-- inventing one would give the decision a terminal outcome no authority
-- sanctioned. When nothing matches, the executor's no-resolution behaviour
-- applies and the answer is CANNOT_DECIDE / NO_RULE_MATCHED.
INSERT INTO ontology_authoring.decision_rule_bindings (
    domain, ontology_version, release_class, governance_basis, decision,
    rule_id, predicate_name, rule_class, precedence, expected_outcome,
    description, status
)
SELECT * FROM (VALUES
    ('retail', '2026.10-prototype.2', 'PROTOTYPE', 'PROTOTYPE_ASSUMPTION',
     'IDENTITY_ASSESSMENT', 'IA-PRED-005', 'ir_001_no_canonical_product',
     'MATCH', 3, 'CREATE_PRODUCT',
     'No canonical Product carries this product_reference. Renders IR-001 '
     '(new_product_family -> CREATE_PRODUCT), which the source describes as '
     'tautological and which reads no dimension. The full identity tuple must '
     'still be ESTABLISHED: CREATE_PRODUCT heads a bootstrap sequence whose '
     'next step is an initial Configuration keyed on that tuple.',
     'proposed'),
    ('retail', '2026.10-prototype.2', 'PROTOTYPE', 'PROTOTYPE_ASSUMPTION',
     'IDENTITY_ASSESSMENT', 'IA-PRED-006',
     'additional_configuration_for_existing_product',
     'MATCH', 7, 'CREATE_CONFIGURATION',
     'The product exists and already has a configuration, and no live '
     'configuration carries this canonical identity. Renders IR-002, IR-003 '
     'and IR-004 jointly: each proposes CREATE_CONFIGURATION for its own '
     'dimension, and geography, term_months and customer_segment are three of '
     'the four locked identity properties, so a tuple matching no live '
     'configuration differs in at least one of them. Splitting this into three '
     'bindings would require naming which dimension changed, and a Fold '
     'snapshot states what the identity IS, not what it previously was.',
     'proposed')
) AS v (domain, ontology_version, release_class, governance_basis, decision,
        rule_id, predicate_name, rule_class, precedence, expected_outcome,
        description, status)
WHERE NOT EXISTS (
    SELECT 1 FROM ontology_authoring.decision_rule_bindings b
    WHERE b.domain = v.domain
      AND b.ontology_version = v.ontology_version
      AND b.decision = v.decision
      AND b.rule_id = v.rule_id
);

-- ---------------------------------------------------------------------------
-- 4. proof
-- ---------------------------------------------------------------------------
-- ontology_release has no governance_basis column, and deliberately so: the
-- basis is a property of the release CLASS, and row-level tables carry it only
-- because their rows have to be checkable against the release they claim.
SELECT ontology_version, release_class, validation_status,
       status, parent_ontology_version, parent_release_class
FROM   ontology_authoring.ontology_release
WHERE  domain = 'retail'
ORDER  BY ontology_version;

SELECT rule_id, rule_class, precedence, predicate_name, expected_outcome,
       governance_basis, status
FROM   ontology_authoring.decision_rule_bindings
WHERE  ontology_version = '2026.10-prototype.2'
ORDER  BY precedence;

SELECT rule, ordinal, source_object, target_system, proposed_action,
       requires_new_target_identity, projection_reason,
       proliferation_classification, status
FROM   ontology_authoring.projection_rules
WHERE  ontology_version = '2026.10-prototype.2'
ORDER  BY ordinal;

-- section census: prototype.2 must be prototype.1 plus exactly the additions
SELECT 'actors' AS section,
       (SELECT count(*) FROM ontology_authoring.actors
         WHERE ontology_version='2026.10-prototype.1') AS p1,
       (SELECT count(*) FROM ontology_authoring.actors
         WHERE ontology_version='2026.10-prototype.2') AS p2
UNION ALL SELECT 'configuration_dimensions',
       (SELECT count(*) FROM ontology_authoring.configuration_dimensions
         WHERE ontology_version='2026.10-prototype.1'),
       (SELECT count(*) FROM ontology_authoring.configuration_dimensions
         WHERE ontology_version='2026.10-prototype.2')
UNION ALL SELECT 'identity_rules',
       (SELECT count(*) FROM ontology_authoring.identity_rules
         WHERE ontology_version='2026.10-prototype.1'),
       (SELECT count(*) FROM ontology_authoring.identity_rules
         WHERE ontology_version='2026.10-prototype.2')
UNION ALL SELECT 'decisions',
       (SELECT count(*) FROM ontology_authoring.decisions
         WHERE ontology_version='2026.10-prototype.1'),
       (SELECT count(*) FROM ontology_authoring.decisions
         WHERE ontology_version='2026.10-prototype.2')
UNION ALL SELECT 'decision_outputs',
       (SELECT count(*) FROM ontology_authoring.decision_outputs
         WHERE ontology_version='2026.10-prototype.1'),
       (SELECT count(*) FROM ontology_authoring.decision_outputs
         WHERE ontology_version='2026.10-prototype.2')
UNION ALL SELECT 'decision_rule_bindings',
       (SELECT count(*) FROM ontology_authoring.decision_rule_bindings
         WHERE ontology_version='2026.10-prototype.1'),
       (SELECT count(*) FROM ontology_authoring.decision_rule_bindings
         WHERE ontology_version='2026.10-prototype.2')
UNION ALL SELECT 'projection_rules',
       (SELECT count(*) FROM ontology_authoring.projection_rules
         WHERE ontology_version='2026.10-prototype.1'),
       (SELECT count(*) FROM ontology_authoring.projection_rules
         WHERE ontology_version='2026.10-prototype.2')
ORDER BY 1;

-- prototype.1 must be untouched: still published, still 8 identity rules,
-- still 4 bindings, still no projection rules
SELECT status AS prototype_1_release_status
FROM   ontology_authoring.ontology_release
WHERE  ontology_version = '2026.10-prototype.1';
