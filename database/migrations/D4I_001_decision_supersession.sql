-- ============================================================================
-- AGENT SUPPORT -- one current decision per subject, decision type and
-- governance scope
-- ============================================================================
-- THE DEFECT
--   claris.execute_decision_v2 never writes `state`. It relies on the column
--   default 'current' and knows nothing about a prior decision, so a second
--   evaluation of the same subject leaves two rows at state='current' with
--   different outcomes. The vertical-slice replay produced exactly that:
--   CONFIG-REQ-2026-002 carries both CREATE_CONFIGURATION and
--   NO_BUSINESS_CHANGE, both current. An Agent asking "what is the current
--   decision" gets two contradictory answers and no way to choose.
--
--   The model already expects supersession: claris.decision has state,
--   superseded_by and superseded_at, and check_decision_state permits
--   'superseded'. Nothing was writing them.
--
-- WHAT CHANGES, AND ONLY THIS
--   One UPDATE is added after the INSERT. Everything else in the function --
--   the is_valid_outcome_v2 guard, the column list, the verbatim outcome
--   persistence, the RETURN QUERY -- is byte-for-byte what was deployed.
--
-- THE SUPERSESSION KEY, AND WHY EACH PART OF IT IS THERE
--       decision_type      a LAUNCH_READINESS decision does not retire an
--                          IDENTITY_ASSESSMENT one; they answer different
--                          questions about the same subject
--       subject_type       + subject_id: the thing being decided about
--       governance_basis   PROTOTYPE_ASSUMPTION never retires AUTHORITATIVE
--       execution_mode     and PROTOTYPE never retires PRODUCTION
--
--   The last two are the isolation guarantee. A prototype run must not be able
--   to mark a production decision superseded -- that would let an engineering
--   assumption silently retire confirmed governance, which is the single worst
--   thing this codebase could permit. The database already refuses to let basis
--   and mode disagree (ck_decision_basis_matches_mode), so matching on both is
--   belt and braces rather than redundancy: a future basis/mode pair still
--   scopes correctly.
--
-- HISTORY IS PRESERVED
--   No row is deleted and no outcome is rewritten. A superseded decision keeps
--   its outcome, reason, digest, evidence arrays and lineage; it gains a
--   pointer to what replaced it and when. "What did we conclude in September
--   and why" stays answerable forever.
--
--   superseded_at is the NEW decision's decided_at, not now(). The moment one
--   decision replaced another is a property of that replacement, and reading
--   the clock a second time would put a value in the audit trail that
--   corresponds to nothing.
--
-- WHAT THIS DOES NOT DECIDE
--   Whether a decision SHOULD be re-evaluated, on what horizon, or by whom.
--   That is policy. This only ensures that when a second decision is recorded,
--   exactly one of them claims to be current.
--
-- APPLY IN ONE TRANSACTION. Idempotent: CREATE OR REPLACE, and re-running
-- changes nothing. Existing rows are NOT retro-superseded -- see the optional
-- backfill at the end, which is deliberately separate and commented out.
-- ============================================================================

CREATE OR REPLACE FUNCTION claris.execute_decision_v2(
    p_domain                  character varying,
    p_ontology_version        character varying,
    p_governance_basis        character varying,
    p_execution_mode          character varying,
    p_decision_type           character varying,
    p_subject_type            character varying,
    p_subject_id              character varying,
    p_outcome_code            character varying,
    p_reason_code             character varying,
    p_kb_version              character varying,
    p_policy_version          character varying,
    p_horizon_as_of           timestamp with time zone,
    p_input_digest            character varying,
    p_fold_state_id           character varying,
    p_matched_rule_id         character varying,
    p_matched_rule_class      character varying,
    p_matched_rule_kb_version character varying,
    p_confidence_level        character varying,
    p_missing_evidence        text[],
    p_blocking_evidence       text[],
    p_executor_version        character varying,
    p_digest_scheme_version   character varying,
    p_decided_by              character varying DEFAULT 'SYSTEM'::character varying
)
RETURNS TABLE(decision_id uuid, outcome_code character varying,
              state character varying, decided_at timestamp with time zone)
LANGUAGE plpgsql
AS $function$
DECLARE
  v_decision_id UUID;
  v_decided_at  TIMESTAMPTZ;
  v_superseded  INTEGER;
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
  RETURNING claris.decision.decision_id, claris.decision.decided_at
       INTO v_decision_id, v_decided_at;

  -- ------------------------------------------------------------------
  -- retire the decision this one replaces, within its own scope only
  -- ------------------------------------------------------------------
  -- Scoped by governance_basis AND execution_mode so a prototype run can never
  -- mark a production decision superseded. decision_id <> v_decision_id keeps
  -- the row just inserted out of its own UPDATE.
  UPDATE claris.decision d
     SET state         = 'superseded',
         superseded_by = v_decision_id,
         superseded_at = v_decided_at
   WHERE d.decision_type    = p_decision_type
     AND d.subject_type     = p_subject_type
     AND d.subject_id       = p_subject_id
     AND d.governance_basis = p_governance_basis
     AND d.execution_mode   = p_execution_mode
     AND d.state            = 'current'
     AND d.decision_id     <> v_decision_id;

  GET DIAGNOSTICS v_superseded = ROW_COUNT;
  IF v_superseded > 1 THEN
    -- Not an error to swallow: more than one current decision existed before
    -- this call, which means rows predate this function version. They are all
    -- now superseded by the new one, which is the correct repair, but it is
    -- worth saying out loud.
    RAISE NOTICE '% decisions were current for %/% before this one; all '
                 'superseded', v_superseded, p_subject_id, p_decision_type;
  END IF;

  -- the validated outcome string is persisted verbatim into the live
  -- character varying(64) column; there is no cast and no type coercion
  RETURN QUERY
  SELECT d.decision_id, d.outcome_code, d.state, d.decided_at
  FROM claris.decision d
  WHERE d.decision_id = v_decision_id;
END;
$function$;

COMMENT ON FUNCTION claris.execute_decision_v2 IS
  'Persists one governed decision and retires the decision it replaces within '
  'the same (decision_type, subject_type, subject_id, governance_basis, '
  'execution_mode) scope. Exactly one decision per scope is state=''current''. '
  'History is preserved: superseded rows keep their outcome, reason, digest and '
  'lineage, and gain superseded_by / superseded_at. Prototype governance can '
  'never supersede production governance -- the scope includes basis and mode.';

-- ---------------------------------------------------------------------------
-- proof
-- ---------------------------------------------------------------------------
-- Existing rows are NOT retro-superseded by this migration: it changes the
-- function, not the data. The 14 decisions already recorded still carry two
-- current rows per subject, and the FIRST re-evaluation of each subject will
-- supersede them (the RAISE NOTICE above fires when it does). That is the
-- honest repair path -- rewriting history to match a rule that did not exist
-- when it was written would be inventing a supersession event that never
-- happened.
SELECT subject_id, decision_type,
       count(*)                                        AS decisions,
       count(*) FILTER (WHERE state = 'current')       AS current,
       count(*) FILTER (WHERE state = 'superseded')    AS superseded
FROM   claris.decision
GROUP  BY subject_id, decision_type
ORDER  BY subject_id;

SELECT proname,
       pg_get_function_result(oid) AS returns,
       obj_description(oid, 'pg_proc') IS NOT NULL AS documented
FROM   pg_proc
WHERE  proname = 'execute_decision_v2';
