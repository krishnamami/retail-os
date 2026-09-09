-- ============================================================================
-- claris.v_workbench_stage5_policy
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
--     GRANT SELECT ON claris.v_workbench_stage5_policy TO claris_ingestion;
--     (postgres holds full privileges as owner)
-- ============================================================================

CREATE OR REPLACE VIEW claris.v_workbench_stage5_policy AS
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

GRANT SELECT ON claris.v_workbench_stage5_policy TO claris_ingestion;
