-- ============================================================================
-- D.4G.4 -- artifact governance classification
-- ============================================================================
-- Phase : STEP 5G.6 / D.4G.4
-- Scope : claris_kb.kb_artifact, claris_kb.v_active_kb (+ one new view)
--
-- WHY THIS EXISTS
-- claris_kb.kb_artifact cannot say what class of governance an artifact
-- carries. A row with kb_version '2026.10-prototype.1' and status 'VERIFIED'
-- is distinguishable from production governance only by a human reading the
-- version string. Every structural protection built in ontology_authoring --
-- the composite FK binding release_class to its release, the
-- ..._assumption_is_never_confirmed checks, the one-way parent lineage -- has
-- no counterpart here.
--
-- That is the mechanism that produced KB 1.1: an artifact whose classification
-- lived in a naming convention instead of a constraint.
--
-- AND v_active_kb is a GLOBAL fail-closed singleton:
--     WHERE status='ACTIVE' AND (SELECT count(*) WHERE status='ACTIVE') = 1
-- so publishing a second ACTIVE row makes the count 2, the guard matches zero,
-- the view returns nothing, and PostgresKBResolver raises NoActiveKB.
-- Production governance resolution would not degrade -- it would stop, along
-- with v_active_decision_rules and the five other ACTIVE-filtered views
-- beneath it.
--
-- WHAT THIS PRESERVES
-- The three existing artifacts default to AUTHORITATIVE, so v_active_kb keeps
-- returning KB 1.1: same row, same six columns in the same order, same
-- fail-closed behaviour -- now scoped to its own class. v_active_decision_rules
-- and the other ACTIVE views inherit the scoping unchanged and are not edited.
-- Production cannot fall back to prototype governance because it cannot see a
-- prototype row at all.
--
-- RERUN SAFE. Every statement is idempotent: ADD COLUMN IF NOT EXISTS,
-- ADD CONSTRAINT guarded by a pg_constraint existence check, CREATE UNIQUE
-- INDEX IF NOT EXISTS, CREATE OR REPLACE VIEW, COMMENT ON and GRANT (all
-- naturally idempotent). Applying this file twice changes nothing the second
-- time and errors on nothing.
--
-- ADDITIVE ONLY. No DROP, no TRUNCATE, no DELETE, no UPDATE of artifact
-- content. No kb_json is read, written or altered. KB 1.0, 1.0.1 and 1.1 keep
-- their payloads, digests and statuses byte for byte.
--
-- APPLY IN ONE TRANSACTION.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. classification columns
-- ---------------------------------------------------------------------------
-- The defaults are what keep this migration non-breaking: every artifact that
-- exists today is production governance, and saying so explicitly is exactly
-- right.
ALTER TABLE claris_kb.kb_artifact
    ADD COLUMN IF NOT EXISTS release_class     varchar(16) NOT NULL
        DEFAULT 'AUTHORITATIVE',
    ADD COLUMN IF NOT EXISTS governance_basis  varchar(24) NOT NULL
        DEFAULT 'AUTHORITATIVE',
    ADD COLUMN IF NOT EXISTS validation_status varchar(32);

-- Guarded: ADD CONSTRAINT is the one DDL here with no IF NOT EXISTS form.
--
-- The guard also accepts ck_kb_artifact_class, the name this same constraint
-- carried in a version of this SQL that was pasted into a chat message before
-- the file existed. Two spellings of one constraint is exactly the drift this
-- migration is meant to prevent elsewhere, so the guard tolerates either and
-- adds neither twice. See the reconciliation query in the phase report.
DO $guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'claris_kb.kb_artifact'::regclass
          AND conname IN ('ck_kb_artifact_release_class', 'ck_kb_artifact_class')
    ) THEN
        ALTER TABLE claris_kb.kb_artifact
            ADD CONSTRAINT ck_kb_artifact_release_class
            CHECK (release_class IN ('AUTHORITATIVE', 'PROTOTYPE'));
    END IF;
END
$guard$;

-- basis, class and validation status move together or not at all. A prototype
-- artifact cannot exist without declaring it is awaiting Claris, and an
-- authoritative one cannot carry a prototype basis.
DO $guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'claris_kb.kb_artifact'::regclass
          AND conname = 'ck_kb_artifact_basis_matches_class'
    ) THEN
        ALTER TABLE claris_kb.kb_artifact
            ADD CONSTRAINT ck_kb_artifact_basis_matches_class
            CHECK ( (release_class = 'AUTHORITATIVE'
                     AND governance_basis = 'AUTHORITATIVE'
                     AND validation_status IS NULL)
                 OR (release_class = 'PROTOTYPE'
                     AND governance_basis = 'PROTOTYPE_ASSUMPTION'
                     AND validation_status = 'TO_BE_VALIDATED_WITH_CLARIS') );
    END IF;
END
$guard$;

-- ---------------------------------------------------------------------------
-- 2. exactly one ACTIVE artifact PER CLASS
-- ---------------------------------------------------------------------------
-- Enforced by the index rather than by a view's subquery: a view can only
-- report a violation after it happens, an index refuses the write.
CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_artifact_one_active_per_class
    ON claris_kb.kb_artifact (release_class)
    WHERE status = 'ACTIVE';

-- ---------------------------------------------------------------------------
-- 3. scope the production singleton to its own class
-- ---------------------------------------------------------------------------
-- CREATE OR REPLACE, not DROP: the column list, order and types are identical
-- to the live definition, so dependent views are untouched and nothing needs
-- recreating. Compare against the definition captured in the D.4G.4 gate --
-- the only change is the release_class predicate.
CREATE OR REPLACE VIEW claris_kb.v_active_kb AS
SELECT kb_version,
       ontology_version,
       content_digest,
       status,
       deployed_at,
       source_system
FROM   claris_kb.kb_artifact
WHERE  status::text = 'ACTIVE'::text
  AND  release_class::text = 'AUTHORITATIVE'::text
  AND  (( SELECT count(*) AS count
          FROM claris_kb.kb_artifact kb_artifact_1
         WHERE kb_artifact_1.status::text = 'ACTIVE'::text
           AND kb_artifact_1.release_class::text = 'AUTHORITATIVE'::text)) = 1;

COMMENT ON VIEW claris_kb.v_active_kb IS
  'The single ACTIVE production artifact. Fail-closed: returns nothing rather than guessing when zero or more than one is ACTIVE. Scoped to release_class AUTHORITATIVE at D.4G.4 so a prototype artifact can be active independently without ever appearing here.';

-- ---------------------------------------------------------------------------
-- 4. the prototype counterpart -- a separate door, not a fallback
-- ---------------------------------------------------------------------------
-- Nothing reads this by default. The prototype resolver must ask for it
-- explicitly, which is what makes prototype execution opt-in rather than
-- something a caller can arrive at by forgetting.
CREATE OR REPLACE VIEW claris_kb.v_active_prototype_kb AS
SELECT kb_version,
       ontology_version,
       content_digest,
       status,
       deployed_at,
       source_system,
       release_class,
       governance_basis,
       validation_status
FROM   claris_kb.kb_artifact
WHERE  status::text = 'ACTIVE'::text
  AND  release_class::text = 'PROTOTYPE'::text
  AND  (( SELECT count(*) AS count
          FROM claris_kb.kb_artifact kb_artifact_1
         WHERE kb_artifact_1.status::text = 'ACTIVE'::text
           AND kb_artifact_1.release_class::text = 'PROTOTYPE'::text)) = 1;

COMMENT ON VIEW claris_kb.v_active_prototype_kb IS
  'The single ACTIVE prototype artifact, if one exists. Disjoint from v_active_kb by construction: an artifact appears in exactly one of the two, never both and never neither by accident. Prototype governance is an engineering assumption awaiting validation with Claris and is never confirmed policy.';

GRANT SELECT ON claris_kb.v_active_prototype_kb TO claris_ingestion;

-- ============================================================================
-- The three existing artifacts (1.0 ARCHIVED, 1.0.1 VERIFIED, 1.1 ACTIVE) are
-- classified AUTHORITATIVE by the column default. Their kb_json, content_digest
-- and status are not read or written by this migration. v_active_kb returns
-- KB 1.1 before and after.
-- ============================================================================
