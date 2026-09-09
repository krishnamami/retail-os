-- ============================================================================
-- D.4G.2 -- runtime / persistence contract corrections
-- ============================================================================
-- Phase   : STEP 5G.6 / D.4G.2
-- Scope   : claris.decision, claris.configuration_state,
--           claris.is_valid_outcome(), claris.execute_decision()
--
-- NOT EXECUTED. Generated as a repository artifact; live application is a
-- separate authorization (D.4G.2 section 17).
--
-- ADDITIVE ONLY. No DROP TABLE, no TRUNCATE, no DELETE, no UPDATE of business
-- data. Column widenings and additions only, plus two function replacements.
-- Nothing here touches the raw corpus, evidence, assertions, fold state,
-- canonical product/configuration/version data, or any legacy KB artifact.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. input_digest -- VARCHAR(32) cannot hold the digest the platform computes
-- ---------------------------------------------------------------------------
-- The deterministic digest contract is  v1:sha256:<64 hex>  = 74 characters.
-- The column is 32. Every governed decision write would have failed, and the
-- two available "fixes" -- truncating, or re-hashing to fit -- would each
-- destroy replay: a truncated digest is not the digest, and a digest of a
-- digest cannot be recomputed from the inputs it claims to fingerprint.
ALTER TABLE claris.decision
    ALTER COLUMN input_digest TYPE VARCHAR(128);

ALTER TABLE claris.configuration_state
    ALTER COLUMN input_digest TYPE VARCHAR(128);

ALTER TABLE claris.decision
    ADD CONSTRAINT ck_decision_input_digest_format
    CHECK (input_digest ~ '^v[0-9]+:[a-z0-9]+:[0-9a-f]{64}$');

-- ---------------------------------------------------------------------------
-- 2. version columns -- and the view dependencies that guard them
-- ---------------------------------------------------------------------------
-- VARCHAR(16) cannot hold '2026.10-prototype.1' (19 characters).
--
-- PostgreSQL refuses ALTER COLUMN ... TYPE while any view depends on the
-- column, and three do. They were discovered live at D.4G.3, not from
-- repository DDL -- none of them had a definition anywhere in this repository
-- before that point. Their recovered sources now live in
-- database/views/claris/ so this is never again a live-only artifact.
--
-- Dependency closure, established recursively over pg_depend:
--     v_workbench_full_workflow   -> v_workbench_stage6_decision
--     v_workbench_stage6_decision -> claris.decision (kb_version, policy_version)
--     v_workbench_stage5_policy   -> claris.decision (kb_version, policy_version)
-- Nothing depends on full_workflow. The other six views that read
-- claris.decision or claris.configuration_state do NOT reference these two
-- columns and are deliberately left alone.
--
-- DROP VIEW is used WITHOUT CASCADE on purpose: if an object nobody knew about
-- depends on one of these, the drop fails and the whole transaction rolls back,
-- rather than silently destroying it. That is the entire safety argument for
-- this section, so do not add CASCADE.
--
-- APPLY THIS FILE IN ONE TRANSACTION. Between the DROP and the CREATE the
-- three views do not exist; a failure outside a transaction would leave them
-- gone.

-- 2a. drop the dependents, deepest first
DROP VIEW claris.v_workbench_full_workflow;
DROP VIEW claris.v_workbench_stage6_decision;
DROP VIEW claris.v_workbench_stage5_policy;

-- 2b. the widenings the views were blocking
ALTER TABLE claris.decision
    ALTER COLUMN kb_version TYPE VARCHAR(64);

ALTER TABLE claris.decision
    ALTER COLUMN policy_version TYPE VARCHAR(64);

-- policy_version is derived-or-absent under the D.4G.1G.3 version contract:
-- the live registry holds zero rows while 13 records reference '1.0'. NOT NULL
-- forces a fabricated value where the honest answer is "none applies".
-- (A nullability change does not need the views dropped; it is here because it
-- belongs with the other policy_version work.)
ALTER TABLE claris.decision
    ALTER COLUMN policy_version DROP NOT NULL;

-- 2c. put the views back, verbatim, in reverse dependency order.
-- These bodies are pg_get_viewdef(oid, true) output captured live on
-- 2026-09-08 -- the same text PostgreSQL regenerates -- and are byte-identical
-- to database/views/claris/*.sql.

CREATE VIEW claris.v_workbench_stage5_policy AS
 SELECT cv.version_id,
    cv.configuration_id,
    d.decision_type,
    d.kb_version,
    d.policy_version,
    d.horizon_as_of,
        CASE
            WHEN d.decision_id IS NULL THEN 'No decision yet; policy ready to apply'::text
            ELSE 'Policy applied to decision'::text
        END AS policy_status
   FROM claris.configuration_version cv
     LEFT JOIN claris.decision d ON d.subject_id::text = cv.version_id::text AND d.subject_type::text = 'configuration_version'::text AND d.state::text = 'current'::text
  ORDER BY cv.created_at DESC;

CREATE VIEW claris.v_workbench_stage6_decision AS
 SELECT d.decision_id,
    d.decision_type,
    d.subject_type,
    d.subject_id,
    d.outcome_code,
    d.reason_code,
    d.confidence_level,
    d.decided_by,
    d.decided_at,
    d.state AS decision_state,
    d.superseded_by,
    d.superseded_at,
    d.kb_version,
    d.policy_version,
    d.horizon_as_of,
    count(DISTINCT de.evidence_id) AS evidence_linked_count,
    d.missing_evidence,
    d.blocking_evidence,
        CASE
            WHEN d.state::text = 'current'::text THEN 'This is the active decision'::text
            WHEN d.state::text = 'superseded'::text THEN 'This decision was superseded'::text
            ELSE 'Unknown state'::text
        END AS decision_status_label
   FROM claris.decision d
     LEFT JOIN claris.decision_evidence de ON de.decision_id = d.decision_id AND de.role::text = 'INPUT'::text
  GROUP BY d.decision_id, d.decision_type, d.subject_type, d.subject_id, d.outcome_code, d.reason_code, d.confidence_level, d.decided_by, d.decided_at, d.state, d.superseded_by, d.superseded_at, d.kb_version, d.policy_version, d.horizon_as_of, d.missing_evidence, d.blocking_evidence
  ORDER BY d.decided_at DESC;

CREATE VIEW claris.v_workbench_full_workflow AS
 WITH config_stage AS (
         SELECT DISTINCT v_workbench_stage1_configuration.configuration_id,
            v_workbench_stage1_configuration.product_id,
            v_workbench_stage1_configuration.product_name,
            v_workbench_stage1_configuration.canonical_identity,
            v_workbench_stage1_configuration.status,
            v_workbench_stage1_configuration.created_at,
            v_workbench_stage1_configuration.version_id
           FROM claris.v_workbench_stage1_configuration
        ), evidence_summary AS (
         SELECT v_workbench_stage2_evidence.configuration_version_id,
            count(*) AS total_evidence,
            count(DISTINCT v_workbench_stage2_evidence.source_system) AS source_count,
            max(v_workbench_stage2_evidence.recorded_at) AS latest_evidence_at
           FROM claris.v_workbench_stage2_evidence
          GROUP BY v_workbench_stage2_evidence.configuration_version_id
        ), facts_summary AS (
         SELECT v_workbench_stage3_established_facts.configuration_version_id,
            count(*) AS total_dimensions,
            count(*) FILTER (WHERE v_workbench_stage3_established_facts.fact_status = 'ESTABLISHED'::claris_config_state_type) AS established_count,
            count(*) FILTER (WHERE v_workbench_stage3_established_facts.fact_status = 'UNREPORTED'::claris_config_state_type) AS unreported_count,
            count(*) FILTER (WHERE v_workbench_stage3_established_facts.fact_status = 'CONTRADICTED'::claris_config_state_type) AS contradicted_count
           FROM claris.v_workbench_stage3_established_facts
          GROUP BY v_workbench_stage3_established_facts.configuration_version_id
        ), decision_summary AS (
         SELECT v_workbench_stage6_decision.subject_id AS version_id,
            v_workbench_stage6_decision.decision_id,
            v_workbench_stage6_decision.decision_type,
            v_workbench_stage6_decision.outcome_code,
            v_workbench_stage6_decision.decided_at,
            v_workbench_stage6_decision.decision_state,
            row_number() OVER (PARTITION BY v_workbench_stage6_decision.subject_id ORDER BY v_workbench_stage6_decision.decided_at DESC) AS decision_rank
           FROM claris.v_workbench_stage6_decision
          WHERE v_workbench_stage6_decision.subject_type::text = 'configuration_version'::text
        ), action_summary AS (
         SELECT d.subject_id AS version_id,
            count(DISTINCT ar.action_id) AS total_actions,
            count(DISTINCT ar.action_id) FILTER (WHERE ar.action_status::text = 'proposed'::text) AS proposed_count,
            count(DISTINCT ar.action_id) FILTER (WHERE ar.action_status::text = 'approved'::text) AS approved_count,
            count(DISTINCT ar.action_id) FILTER (WHERE ar.action_status::text = 'executed'::text) AS executed_count,
            count(DISTINCT ar.action_id) FILTER (WHERE ar.action_status::text = 'rejected'::text) AS rejected_count
           FROM claris.decision d
             LEFT JOIN claris.action_record ar ON ar.decision_id = d.decision_id
          WHERE d.subject_type::text = 'configuration_version'::text
          GROUP BY d.subject_id
        )
 SELECT cs.configuration_id,
    cs.product_id,
    cs.product_name,
    cs.canonical_identity,
    cs.version_id,
    cs.status,
    cs.created_at,
    es.total_evidence,
    es.source_count,
    es.latest_evidence_at,
    fs.total_dimensions,
    fs.established_count,
    fs.unreported_count,
    fs.contradicted_count,
    ds.decision_id,
    ds.decision_type,
    ds.outcome_code,
    ds.decided_at,
    act.total_actions,
    act.proposed_count,
    act.approved_count,
    act.executed_count,
    act.rejected_count,
        CASE
            WHEN cs.status::text = 'pending'::text THEN 'Configuration created, awaiting evidence'::text
            WHEN es.total_evidence = 0 THEN 'No evidence collected yet'::text
            WHEN fs.contradicted_count > 0 THEN 'Contradictions found in evidence'::text
            WHEN fs.unreported_count > 0 THEN 'Missing evidence for some dimensions'::text
            WHEN ds.decision_id IS NULL THEN 'Evidence complete, awaiting decision'::text
            WHEN act.total_actions = 0 THEN 'Decision made, no actions proposed yet'::text
            WHEN act.proposed_count > 0 AND act.approved_count = 0 THEN 'Actions proposed, awaiting approval'::text
            WHEN act.executed_count > 0 THEN 'Actions executed'::text
            ELSE 'Workflow in progress'::text
        END AS overall_status
   FROM config_stage cs
     LEFT JOIN evidence_summary es ON es.configuration_version_id::text = cs.version_id::text
     LEFT JOIN facts_summary fs ON fs.configuration_version_id::text = cs.version_id::text
     LEFT JOIN decision_summary ds ON ds.version_id::text = cs.version_id::text AND ds.decision_rank = 1
     LEFT JOIN action_summary act ON act.version_id::text = cs.version_id::text
  ORDER BY cs.created_at DESC;

-- 2d. restore the grants observed live before the drop
GRANT SELECT ON claris.v_workbench_stage5_policy   TO claris_ingestion;
GRANT SELECT ON claris.v_workbench_stage6_decision TO claris_ingestion;
GRANT SELECT ON claris.v_workbench_full_workflow   TO claris_ingestion;

-- ---------------------------------------------------------------------------
-- 3. decision lineage -- what state was evaluated, and what matched
-- ---------------------------------------------------------------------------
-- Without these a decision record cannot answer "why", and cannot be replayed.
-- Each field carries exactly one meaning; none is overloaded.
ALTER TABLE claris.decision
    ADD COLUMN IF NOT EXISTS ontology_version        VARCHAR(64),
    ADD COLUMN IF NOT EXISTS governance_basis        VARCHAR(24)
        NOT NULL DEFAULT 'AUTHORITATIVE',
    ADD COLUMN IF NOT EXISTS execution_mode          VARCHAR(16)
        NOT NULL DEFAULT 'PRODUCTION',
    ADD COLUMN IF NOT EXISTS fold_state_id           VARCHAR(64),
    ADD COLUMN IF NOT EXISTS matched_rule_id         VARCHAR(32),
    ADD COLUMN IF NOT EXISTS matched_rule_class      VARCHAR(16),
    ADD COLUMN IF NOT EXISTS matched_rule_kb_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS executor_version        VARCHAR(32),
    ADD COLUMN IF NOT EXISTS digest_scheme_version   VARCHAR(16);

ALTER TABLE claris.decision
    ADD CONSTRAINT ck_decision_governance_basis
    CHECK (governance_basis IN ('AUTHORITATIVE', 'PROTOTYPE_ASSUMPTION'));

ALTER TABLE claris.decision
    ADD CONSTRAINT ck_decision_execution_mode
    CHECK (execution_mode IN ('PRODUCTION', 'PROTOTYPE'));

-- a prototype decision may only be recorded in prototype execution mode, and
-- an authoritative decision only in production mode. The persisted record can
-- therefore never misdescribe which governance produced it.
ALTER TABLE claris.decision
    ADD CONSTRAINT ck_decision_basis_matches_mode
    CHECK ( (governance_basis = 'AUTHORITATIVE'        AND execution_mode = 'PRODUCTION')
         OR (governance_basis = 'PROTOTYPE_ASSUMPTION' AND execution_mode = 'PROTOTYPE') );

ALTER TABLE claris.decision
    ADD CONSTRAINT ck_decision_matched_rule_class
    CHECK (matched_rule_class IS NULL
           OR matched_rule_class IN ('GUARD', 'MATCH', 'FALLBACK'));

-- executable technical predicates are IA-PRED-nnn. A governed business
-- identity rule id (IR-nnn) is never what "matched" at runtime.
ALTER TABLE claris.decision
    ADD CONSTRAINT ck_decision_matched_rule_not_ir
    CHECK (matched_rule_id IS NULL OR matched_rule_id !~ '^IR-[0-9]{3}$');

-- ---------------------------------------------------------------------------
-- 4. outcome vocabulary -- governed by version, not by a PostgreSQL type
-- ---------------------------------------------------------------------------
-- CORRECTED at the D.4G.3 pre-deployment correction, from a live preflight.
--
-- An earlier draft of this migration added three values to an enum type
-- claris_decision_outcome. That type DOES NOT EXIST in the live database, and
-- claris.decision does not have an enum-backed outcome column:
--
--     claris.decision.outcome_code   character varying(64) NOT NULL
--
-- The assumption came from database/ddl/001_core_schema.sql, which declares
-- such a type and a `recommendation` column. The deployed schema diverges from
-- that file. Repository DDL is not evidence of the live contract, and this
-- migration no longer treats it as such.
--
-- The only similarly named type in the database is payments.decision_outcome,
-- which is unrelated and is neither read nor altered here.
--
-- NOTHING IS DONE IN THIS SECTION, deliberately. The outcome column already
-- accepts every governed outcome string, so no widening, no type change and no
-- new type is required. Which strings are legitimate is a GOVERNANCE question,
-- not a storage question, and it is answered where governance lives:
--
--     claris.is_valid_outcome_v2(domain, ontology_version, decision_type,
--                                outcome_code, governance_basis)
--
-- scoped to the exact release that produced the decision. A PostgreSQL enum
-- could not express that: it is global, unversioned, and would have accepted a
-- prototype outcome for a production decision and vice versa.

-- ---------------------------------------------------------------------------
-- 5. is_valid_outcome() -- version scoped, no legacy fallback
-- ---------------------------------------------------------------------------
-- The previous body read ontology.decision_outputs with kb_version defaulting
-- to NULL, so an omitted argument validated against the frozen legacy KB 1.0
-- vocabulary. The replacement resolves against the authoring release that
-- actually governed the decision, and every scoping argument is mandatory.
CREATE OR REPLACE FUNCTION claris.is_valid_outcome_v2(
  p_domain           VARCHAR(64),
  p_ontology_version VARCHAR(64),
  p_decision_type    VARCHAR(64),
  p_outcome_code     VARCHAR(64),
  p_governance_basis VARCHAR(24)
)
RETURNS BOOLEAN AS $$
BEGIN
  IF p_domain IS NULL OR p_ontology_version IS NULL
     OR p_decision_type IS NULL OR p_outcome_code IS NULL
     OR p_governance_basis IS NULL THEN
    -- fail closed: an unscoped question has no safe answer
    RETURN false;
  END IF;

  RETURN EXISTS (
    SELECT 1
    FROM ontology_authoring.decision_outputs
    WHERE domain           = p_domain
      AND ontology_version = p_ontology_version
      AND decision         = p_decision_type
      AND outcome          = p_outcome_code
      AND governance_basis = p_governance_basis
  );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION claris.is_valid_outcome_v2 IS
  'Version-scoped outcome validation. Reads only the authoring release named by its arguments; never the legacy ontology schema, never a global ACTIVE lookup, and never with a default that means "any version".';

-- ---------------------------------------------------------------------------
-- 6. execute_decision() -- aligned with the runtime DecisionResult contract
-- ---------------------------------------------------------------------------
-- The v1 signature carried no ontology_version, no governance_basis, no
-- fold_state_id and no matched_rule_id, declared v_input_digest VARCHAR(32),
-- and validated through the unscoped is_valid_outcome(). v2 takes exactly what
-- DecisionResult carries and refuses anything it cannot validate.
CREATE OR REPLACE FUNCTION claris.execute_decision_v2(
  p_domain                  VARCHAR(64),
  p_ontology_version        VARCHAR(64),
  p_governance_basis        VARCHAR(24),
  p_execution_mode          VARCHAR(16),
  p_decision_type           VARCHAR(64),
  p_subject_type            VARCHAR(64),
  p_subject_id              VARCHAR(64),
  p_outcome_code            VARCHAR(64),
  p_reason_code             VARCHAR(256),
  p_kb_version              VARCHAR(64),
  p_policy_version          VARCHAR(64),
  p_horizon_as_of           TIMESTAMPTZ,
  p_input_digest            VARCHAR(128),
  p_fold_state_id           VARCHAR(64),
  p_matched_rule_id         VARCHAR(32),
  p_matched_rule_class      VARCHAR(16),
  p_matched_rule_kb_version VARCHAR(64),
  p_confidence_level        VARCHAR(32),
  p_missing_evidence        TEXT[],
  p_blocking_evidence       TEXT[],
  p_executor_version        VARCHAR(32),
  p_digest_scheme_version   VARCHAR(16),
  p_decided_by              VARCHAR(128) DEFAULT 'SYSTEM'
)
RETURNS TABLE (
  decision_id UUID,
  outcome_code VARCHAR(64),
  state VARCHAR(32),
  decided_at TIMESTAMPTZ
) AS $$
DECLARE
  v_decision_id UUID;
BEGIN
  IF NOT claris.is_valid_outcome_v2(
       p_domain, p_ontology_version, p_decision_type,
       p_outcome_code, p_governance_basis) THEN
    RAISE EXCEPTION
      'outcome % is not declared by % at % (%)',
      p_outcome_code, p_decision_type, p_ontology_version, p_governance_basis;
  END IF;

  INSERT INTO claris.decision (
    decision_type, subject_type, subject_id,
    outcome_code, reason_code,
    ontology_version, governance_basis, execution_mode,
    kb_version, policy_version, horizon_as_of,
    input_digest, fold_state_id,
    matched_rule_id, matched_rule_class, matched_rule_kb_version,
    confidence_level, missing_evidence, blocking_evidence,
    executor_version, digest_scheme_version, decided_by
  ) VALUES (
    p_decision_type, p_subject_type, p_subject_id,
    p_outcome_code, p_reason_code,
    p_ontology_version, p_governance_basis, p_execution_mode,
    p_kb_version, p_policy_version, p_horizon_as_of,
    p_input_digest, p_fold_state_id,
    p_matched_rule_id, p_matched_rule_class, p_matched_rule_kb_version,
    p_confidence_level, p_missing_evidence, p_blocking_evidence,
    p_executor_version, p_digest_scheme_version, p_decided_by
  )
  RETURNING claris.decision.decision_id INTO v_decision_id;

  -- the validated outcome string is persisted verbatim into the live
  -- character varying(64) column; there is no cast and no type coercion
  RETURN QUERY
  SELECT d.decision_id, d.outcome_code, d.state, d.decided_at
  FROM claris.decision d
  WHERE d.decision_id = v_decision_id;
END;
$$ LANGUAGE plpgsql VOLATILE;

-- ---------------------------------------------------------------------------
-- 7. lineage index
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_decision_governance
    ON claris.decision (ontology_version, governance_basis, decision_type);

-- ============================================================================
-- The v1 is_valid_outcome() and execute_decision() are deliberately LEFT IN
-- PLACE and not dropped. They are the legacy KB 1.0 execution path, which is
-- frozen rather than removed; cutting over is a later, separately approved
-- step. Nothing in this migration makes v1 unreachable, and nothing makes v2
-- the default.
-- ============================================================================
