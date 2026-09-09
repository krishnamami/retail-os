-- ============================================================================
-- claris.v_workbench_stage6_decision
-- ============================================================================
-- RECOVERED FROM THE LIVE DATABASE at D.4G.3, 2026-09-08.
--
-- This view had no definition anywhere in the repository. Its only copy was
-- the running catalogue, which meant one DROP ... CASCADE would have destroyed
-- it with nothing to rebuild from. Captured here via pg_get_viewdef(oid, true),
-- which returns the rewritten form -- the same text PostgreSQL will regenerate.
--
-- Owner: postgres
-- Grants observed live:
--     GRANT SELECT ON claris.v_workbench_stage6_decision TO claris_ingestion;
--     (postgres holds full privileges as owner)
-- ============================================================================

CREATE OR REPLACE VIEW claris.v_workbench_stage6_decision AS
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

GRANT SELECT ON claris.v_workbench_stage6_decision TO claris_ingestion;
