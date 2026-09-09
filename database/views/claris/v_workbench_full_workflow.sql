-- ============================================================================
-- claris.v_workbench_full_workflow
-- ============================================================================
-- RECOVERED FROM THE LIVE DATABASE at D.4G.3, 2026-09-08.
--
-- Had no definition anywhere in the repository. Captured via
-- pg_get_viewdef(oid, true).
--
-- Depends on: v_workbench_stage1_configuration, v_workbench_stage2_evidence,
--             v_workbench_stage3_established_facts, v_workbench_stage6_decision,
--             claris.decision, claris.action_record
-- Nothing depends on it (verified by recursive closure over pg_depend).
--
-- Owner: postgres
-- Grants observed live:
--     GRANT SELECT ON claris.v_workbench_full_workflow TO claris_ingestion;
-- ============================================================================

CREATE OR REPLACE VIEW claris.v_workbench_full_workflow AS
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

GRANT SELECT ON claris.v_workbench_full_workflow TO claris_ingestion;
