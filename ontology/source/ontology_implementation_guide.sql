-- Claris v0.5 Postgres Ontology - Implementation Guide
-- Row-level security, evidence capture, and use case execution patterns

-- ============================================================================
-- PART 1: ROW-LEVEL SECURITY (Department-based access control)
-- ============================================================================

-- Create a session variable for current actor
-- Usage: SELECT set_config('ontology.current_actor', 'Ops', false);

-- RLS Policy: Configuration versions visible based on department
CREATE POLICY config_version_access ON knowledge_base.configuration_versions
  USING (
    -- Can see all configurations
    -- TODO: Add department-based filtering when needed
    -- get_department_for_actor(current_setting('ontology.current_actor')) IN ('Ops', 'Product Management')
    true
  );

-- RLS Policy: Evidence visible based on captured department
CREATE POLICY evidence_access ON knowledge_base.evidence
  USING (
    -- Can see evidence from own department or governance evidence
    -- TODO: Add filtering based on asserting_party department
    true
  );

-- RLS Policy: Decisions visible to stakeholders
CREATE POLICY decision_access ON knowledge_base.decision_records
  USING (
    -- Can see decisions where involved as decided_by or in relevant department
    -- TODO: Filter by department jurisdiction
    true
  );

-- Helper function: Get department for an actor
CREATE OR REPLACE FUNCTION ontology.get_department_for_actor(actor_name VARCHAR)
RETURNS VARCHAR AS $$
  SELECT department
  FROM ontology.actors
  WHERE domain = 'retail' AND ontology_version = '2026.10'
    AND actor = actor_name
  LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- Helper function: Check if actor can make decision
CREATE OR REPLACE FUNCTION ontology.can_actor_decide(actor_name VARCHAR, decision_id VARCHAR)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1
    FROM ontology.decisions d
    WHERE d.domain = 'retail' AND d.ontology_version = '2026.10'
      AND d.decision_id = decision_id
      -- AND d.decided_by = actor_name  -- Extend with actual decided_by once stored
      AND EXISTS (
        SELECT 1 FROM ontology.actors a
        WHERE a.domain = d.domain AND a.ontology_version = d.ontology_version
          AND a.actor = actor_name
      )
  );
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- PART 2: EVIDENCE CAPTURE FUNCTIONS
-- ============================================================================

-- Capture evidence from source systems (automatic)
CREATE OR REPLACE FUNCTION knowledge_base.capture_source_event(
  p_source_system VARCHAR,
  p_event_type VARCHAR,
  p_subject_type VARCHAR,
  p_subject_id VARCHAR,
  p_assertion TEXT,
  p_asserting_party VARCHAR DEFAULT NULL
)
RETURNS VARCHAR AS $$
DECLARE
  v_evidence_id VARCHAR;
  v_asserting_party VARCHAR;
BEGIN
  v_evidence_id := 'EV-' || TO_CHAR(NOW(), 'YYYYMMDDHHmmss') || '-' || LPAD((RANDOM() * 9999)::INT::TEXT, 4, '0');
  v_asserting_party := COALESCE(p_asserting_party, p_source_system);

  INSERT INTO knowledge_base.evidence (
    domain, ontology_version, evidence_id, evidence_type,
    subject_type, subject_id, assertion,
    source_system, collection_method, asserting_party,
    captured_at, authority_score
  ) VALUES (
    'retail', '2026.10', v_evidence_id, p_event_type,
    p_subject_type, p_subject_id, p_assertion,
    p_source_system, 'automatic', v_asserting_party,
    NOW(), 0.9  -- Automatic captures are 90% confident
  );

  RETURN v_evidence_id;
END;
$$ LANGUAGE plpgsql;

-- Manual evidence capture (governance, approvals)
CREATE OR REPLACE FUNCTION knowledge_base.capture_governance_evidence(
  p_evidence_type VARCHAR,
  p_subject_type VARCHAR,
  p_subject_id VARCHAR,
  p_assertion TEXT,
  p_asserting_party VARCHAR,
  p_authority_score DECIMAL DEFAULT 1.0
)
RETURNS VARCHAR AS $$
DECLARE
  v_evidence_id VARCHAR;
BEGIN
  v_evidence_id := 'EV-' || TO_CHAR(NOW(), 'YYYYMMDDHHmmss') || '-' || LPAD((RANDOM() * 9999)::INT::TEXT, 4, '0');

  INSERT INTO knowledge_base.evidence (
    domain, ontology_version, evidence_id, evidence_type,
    subject_type, subject_id, assertion,
    source_system, collection_method, asserting_party,
    captured_at, authority_score
  ) VALUES (
    'retail', '2026.10', v_evidence_id, p_evidence_type,
    p_subject_type, p_subject_id, p_assertion,
    'Claris Workbench', 'manual', p_asserting_party,
    NOW(), p_authority_score
  );

  RETURN v_evidence_id;
END;
$$ LANGUAGE plpgsql;

-- Record a decision with evidence basis
CREATE OR REPLACE FUNCTION knowledge_base.record_decision(
  p_decision_id VARCHAR,
  p_subject_type VARCHAR,
  p_subject_id VARCHAR,
  p_outcome TEXT,
  p_decided_by VARCHAR,
  p_basis_evidence_ids TEXT DEFAULT NULL,
  p_confidence_level VARCHAR DEFAULT 'high'
)
RETURNS VARCHAR AS $$
DECLARE
  v_record_id VARCHAR;
BEGIN
  v_record_id := 'DR-' || TO_CHAR(NOW(), 'YYYYMMDDHHmmss') || '-' || LPAD((RANDOM() * 9999)::INT::TEXT, 4, '0');

  INSERT INTO knowledge_base.decision_records (
    domain, ontology_version, record_id, decision_id,
    subject_type, subject_id, outcome,
    decided_by, decided_at, basis_evidence_ids, confidence_level
  ) VALUES (
    'retail', '2026.10', v_record_id, p_decision_id,
    p_subject_type, p_subject_id, p_outcome,
    p_decided_by, NOW(), p_basis_evidence_ids, p_confidence_level
  );

  RETURN v_record_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PART 3: USE CASE EXECUTION PATTERNS
-- ============================================================================

-- UC-01 Pattern: Get launch readiness for a configuration version
CREATE OR REPLACE FUNCTION ontology.get_launch_readiness(
  p_version_id VARCHAR
)
RETURNS TABLE (
  version_id VARCHAR,
  configuration_id VARCHAR,
  identity_effect VARCHAR,
  readiness_status VARCHAR,
  missing_items TEXT,
  evidence_count INT,
  decisions_made INT,
  action_items TEXT
) AS $$
  SELECT
    cv.version_id,
    cv.configuration_id,
    cv.identity_effect,
    CASE
      WHEN cv.identity_effect = 'CANNOT_DECIDE' THEN 'BLOCKED'
      WHEN COUNT(DISTINCT dr.record_id) < 3 THEN 'INCOMPLETE'
      WHEN COUNT(DISTINCT e.evidence_id) < 2 THEN 'MISSING_EVIDENCE'
      ELSE 'READY'
    END::VARCHAR as readiness_status,
    cv.missing_what,
    COUNT(DISTINCT e.evidence_id)::INT,
    COUNT(DISTINCT dr.record_id)::INT,
    CASE
      WHEN cv.identity_effect = 'CANNOT_DECIDE'
        THEN 'BLOCKED: ' || COALESCE(cv.reason_code, 'Unknown reason')
      WHEN COUNT(DISTINCT dr.record_id) < 3
        THEN 'Need ' || (3 - COUNT(DISTINCT dr.record_id)) || ' more decision records'
      WHEN COUNT(DISTINCT e.evidence_id) < 2
        THEN 'Need ' || (2 - COUNT(DISTINCT e.evidence_id)) || ' more evidence pieces'
      ELSE 'Ready for launch'
    END::TEXT
  FROM knowledge_base.configuration_versions cv
  LEFT JOIN knowledge_base.evidence e ON e.subject_id = cv.version_id
  LEFT JOIN knowledge_base.decision_records dr ON dr.subject_id = cv.version_id
  WHERE cv.domain = 'retail' AND cv.ontology_version = '2026.10'
    AND cv.version_id = p_version_id
  GROUP BY cv.version_id, cv.configuration_id, cv.identity_effect, cv.reason_code, cv.missing_what;
$$ LANGUAGE SQL STABLE;

-- UC-03 Pattern: Assess configuration identity
CREATE OR REPLACE FUNCTION ontology.assess_configuration_identity(
  p_configuration_id VARCHAR
)
RETURNS TABLE (
  configuration_id VARCHAR,
  current_version_id VARCHAR,
  current_version_no INT,
  current_identity_effect VARCHAR,
  total_versions INT,
  identity_stable BOOLEAN,
  reason TEXT
) AS $$
  WITH versions AS (
    SELECT
      configuration_id,
      version_id,
      version_no,
      identity_effect,
      ROW_NUMBER() OVER (PARTITION BY configuration_id ORDER BY version_no DESC) as rn
    FROM knowledge_base.configuration_versions
    WHERE domain = 'retail' AND ontology_version = '2026.10'
      AND configuration_id = p_configuration_id
  )
  SELECT
    configuration_id::VARCHAR,
    version_id::VARCHAR,
    version_no::INT,
    identity_effect::VARCHAR,
    COUNT(*)::INT OVER (PARTITION BY configuration_id),
    (identity_effect IN ('USE_EXISTING', 'CREATE_CONFIGURATION', 'CREATE_PRODUCT'))::BOOLEAN,
    CASE
      WHEN identity_effect = 'CREATE_CONFIGURATION' THEN 'Identity was created and has not changed'
      WHEN identity_effect = 'NEW_VERSION' THEN 'Identity persists through version changes'
      WHEN identity_effect = 'USE_EXISTING' THEN 'No identity changes'
      WHEN identity_effect = 'CANNOT_DECIDE' THEN 'Identity undecidable - requires governance'
      ELSE 'Unknown state'
    END::TEXT
  FROM versions
  WHERE rn = 1;
$$ LANGUAGE SQL STABLE;

-- UC-10 Pattern: Count proliferation for a configuration version
CREATE OR REPLACE FUNCTION ontology.get_proliferation_cost(
  p_version_id VARCHAR
)
RETURNS TABLE (
  version_id VARCHAR,
  target_system VARCHAR,
  records_created INT,
  proliferation_records INT,
  business_growth_records INT,
  reason_codes TEXT,
  recommendation TEXT
) AS $$
  SELECT
    p.version_id::VARCHAR,
    p.target_system::VARCHAR,
    COUNT(*)::INT,
    SUM(CASE WHEN p.counts_as_proliferation THEN 1 ELSE 0 END)::INT,
    SUM(CASE WHEN NOT p.counts_as_proliferation THEN 1 ELSE 0 END)::INT,
    STRING_AGG(DISTINCT p.projection_reason, ', ' ORDER BY p.projection_reason)::TEXT,
    CASE
      WHEN SUM(CASE WHEN p.counts_as_proliferation THEN 1 ELSE 0 END)::INT > 0
        THEN 'Phase 2 candidate: ' || NULLIF(STRING_AGG(DISTINCT p.projection_reason, ', '), '')
      ELSE 'No proliferation cost'
    END::TEXT
  FROM knowledge_base.projections p
  WHERE p.domain = 'retail' AND p.ontology_version = '2026.10'
    AND p.version_id = p_version_id
    AND p.projection_status IN ('confirmed', 'required')
  GROUP BY p.version_id, p.target_system;
$$ LANGUAGE SQL STABLE;

-- UC-09 Pattern: Map legacy system constraints
CREATE OR REPLACE FUNCTION ontology.map_legacy_constraints(
  p_configuration_id VARCHAR
)
RETURNS TABLE (
  configuration_id VARCHAR,
  target_system VARCHAR,
  constraint_type VARCHAR,
  counts_as_proliferation BOOLEAN,
  total_records INT,
  affected_versions TEXT
) AS $$
  SELECT
    cv.configuration_id::VARCHAR,
    p.target_system::VARCHAR,
    p.projection_reason::VARCHAR,
    p.counts_as_proliferation::BOOLEAN,
    COUNT(*)::INT,
    STRING_AGG(DISTINCT cv.version_id, ', ' ORDER BY cv.version_id)::TEXT
  FROM knowledge_base.configuration_versions cv
  JOIN knowledge_base.projections p ON cv.domain = p.domain
    AND cv.ontology_version = p.ontology_version
    AND cv.version_id = p.version_id
  WHERE cv.domain = 'retail' AND cv.ontology_version = '2026.10'
    AND cv.configuration_id = p_configuration_id
    AND p.projection_reason IN ('LEGACY_SYSTEM_CONSTRAINT', 'TARGET_SYSTEM_REQUIREMENT')
  GROUP BY cv.configuration_id, p.target_system, p.projection_reason, p.counts_as_proliferation;
$$ LANGUAGE SQL STABLE;

-- UC-06 Pattern: Trace evidence lineage
CREATE OR REPLACE FUNCTION ontology.get_evidence_lineage(
  p_evidence_id VARCHAR
)
RETURNS TABLE (
  evidence_id VARCHAR,
  evidence_type VARCHAR,
  assertion TEXT,
  source_system VARCHAR,
  collection_method VARCHAR,
  asserting_party VARCHAR,
  captured_at TIMESTAMP,
  authority_score DECIMAL,
  supports_configurations TEXT,
  supports_decisions TEXT,
  audit_trail TEXT
) AS $$
  SELECT
    e.evidence_id::VARCHAR,
    e.evidence_type::VARCHAR,
    e.assertion::TEXT,
    e.source_system::VARCHAR,
    e.collection_method::VARCHAR,
    e.asserting_party::VARCHAR,
    e.captured_at::TIMESTAMP,
    e.authority_score::DECIMAL,
    STRING_AGG(DISTINCT cv.configuration_id, ', ' ORDER BY cv.configuration_id)::TEXT,
    STRING_AGG(DISTINCT dr.decision_id, ', ' ORDER BY dr.decision_id)::TEXT,
    TO_CHAR(e.captured_at, 'YYYY-MM-DD HH24:MI:SS') || ' by ' || e.asserting_party || ' via ' || e.collection_method::TEXT
  FROM knowledge_base.evidence e
  LEFT JOIN knowledge_base.configuration_versions cv ON cv.subject_id = e.evidence_id
  LEFT JOIN knowledge_base.decision_records dr ON dr.basis_evidence_ids LIKE '%' || e.evidence_id || '%'
  WHERE e.domain = 'retail' AND e.ontology_version = '2026.10'
    AND e.evidence_id = p_evidence_id
  GROUP BY e.evidence_id, e.evidence_type, e.assertion, e.source_system, e.collection_method,
           e.asserting_party, e.captured_at, e.authority_score;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- PART 4: DASHBOARD VIEWS FOR EXECUTIVE REPORTING
-- ============================================================================

-- Executive dashboard: Configuration portfolio status
CREATE OR REPLACE VIEW ontology.v_portfolio_health AS
SELECT
  'retail'::VARCHAR as domain,
  COUNT(DISTINCT cv.configuration_id) as total_configurations,
  COUNT(DISTINCT cv.version_id) as total_versions,
  SUM(CASE WHEN cv.identity_effect = 'CREATE_CONFIGURATION' THEN 1 ELSE 0 END) as new_configurations,
  SUM(CASE WHEN cv.identity_effect = 'NEW_VERSION' THEN 1 ELSE 0 END) as versions_created,
  SUM(CASE WHEN cv.identity_effect = 'CANNOT_DECIDE' THEN 1 ELSE 0 END) as blocked_by_governance,
  SUM(p.projection_count) as total_physical_records,
  SUM(CASE WHEN p.counts_as_proliferation THEN p.projection_count ELSE 0 END) as legacy_driven_records,
  ROUND(100.0 * SUM(CASE WHEN p.counts_as_proliferation THEN p.projection_count ELSE 0 END) /
        NULLIF(SUM(p.projection_count), 0), 1) as pct_legacy_driven
FROM knowledge_base.configuration_versions cv
LEFT JOIN knowledge_base.projections p ON cv.domain = p.domain
  AND cv.ontology_version = p.ontology_version
  AND cv.version_id = p.version_id
WHERE cv.domain = 'retail' AND cv.ontology_version = '2026.10';

-- Phase readiness dashboard
CREATE OR REPLACE VIEW ontology.v_phase_readiness_dashboard AS
SELECT
  'Phase 1'::VARCHAR as phase,
  'Common Decision Workbench'::VARCHAR as capability,
  COUNT(DISTINCT CASE WHEN lr.readiness_status = 'READY' THEN lr.version_id END) as ready_count,
  COUNT(DISTINCT CASE WHEN lr.readiness_status = 'INCOMPLETE' THEN lr.version_id END) as incomplete_count,
  COUNT(DISTINCT CASE WHEN lr.readiness_status = 'BLOCKED' THEN lr.version_id END) as blocked_count,
  COUNT(DISTINCT lr.version_id) as total_versions
FROM ontology.v_launch_readiness lr;

-- Proliferation backlog (for phase 2 planning)
CREATE OR REPLACE VIEW ontology.v_phase2_backlog AS
SELECT
  p.target_system::VARCHAR as system_to_eliminate,
  p.projection_reason::VARCHAR as constraint_type,
  COUNT(DISTINCT p.projection_id) as record_count,
  COUNT(DISTINCT p.version_id) as configurations_affected,
  SUM(CASE WHEN p.counts_as_proliferation THEN 1 ELSE 0 END) as proliferation_cost,
  pr.status,
  pr.rationale
FROM knowledge_base.projections p
LEFT JOIN ontology.projection_rules pr ON p.domain = pr.domain
  AND p.ontology_version = pr.ontology_version
  AND p.target_system = pr.target_system
WHERE p.domain = 'retail' AND p.ontology_version = '2026.10'
  AND p.counts_as_proliferation = TRUE
  AND p.projection_status IN ('confirmed', 'required')
  AND p.projection_reason IN ('LEGACY_SYSTEM_CONSTRAINT', 'TARGET_SYSTEM_REQUIREMENT')
GROUP BY p.target_system, p.projection_reason, pr.status, pr.rationale
ORDER BY record_count DESC;

-- ============================================================================
-- PART 5: DEPLOYMENT INSTRUCTIONS
-- ============================================================================

/*
DEPLOYMENT STEPS:

1. Create schemas in Postgres retail database:
   CREATE SCHEMA ontology;
   CREATE SCHEMA knowledge_base;

2. Deploy the schema (postgres_ontology_retail_schema.sql):
   psql -U retailuser -d retail_db -f postgres_ontology_retail_schema.sql

3. Load seed data (postgres_ontology_retail_seed_data.sql):
   psql -U retailuser -d retail_db -f postgres_ontology_retail_seed_data.sql

4. Load implementation (this file):
   psql -U retailuser -d retail_db -f postgres_ontology_implementation_guide.sql

5. Create a user for each department:
   CREATE ROLE ops_user WITH LOGIN PASSWORD 'xxxxx';
   CREATE ROLE ist_user WITH LOGIN PASSWORD 'xxxxx';
   CREATE ROLE finance_user WITH LOGIN PASSWORD 'xxxxx';
   CREATE ROLE compliance_user WITH LOGIN PASSWORD 'xxxxx';

6. Grant permissions per department:
   -- Ops: Read all, write configurations and decisions
   GRANT SELECT ON ALL TABLES IN SCHEMA ontology TO ops_user;
   GRANT SELECT, INSERT, UPDATE ON knowledge_base.configuration_versions TO ops_user;
   GRANT SELECT, INSERT, UPDATE ON knowledge_base.configuration_values TO ops_user;
   GRANT SELECT, INSERT ON knowledge_base.decision_records TO ops_user;
   GRANT SELECT, INSERT ON knowledge_base.evidence TO ops_user;

   -- IS&T: Read all, write projections and technical evidence
   GRANT SELECT ON ALL TABLES IN SCHEMA ontology TO ist_user;
   GRANT SELECT ON knowledge_base.configuration_versions TO ist_user;
   GRANT SELECT, INSERT, UPDATE ON knowledge_base.projections TO ist_user;
   GRANT SELECT, INSERT ON knowledge_base.evidence TO ist_user;

   -- Finance: Read all, write pricing evidence and entitlement decisions
   GRANT SELECT ON ALL TABLES IN SCHEMA ontology TO finance_user;
   GRANT SELECT, INSERT ON knowledge_base.evidence TO finance_user;
   GRANT SELECT, INSERT ON knowledge_base.decision_records TO finance_user;

   -- Compliance: Read all, audit only
   GRANT SELECT ON ALL TABLES IN SCHEMA ontology TO compliance_user;
   GRANT SELECT ON ALL TABLES IN SCHEMA knowledge_base TO compliance_user;

7. Test the views:
   SELECT * FROM ontology.v_identity_assessment;
   SELECT * FROM ontology.v_launch_readiness;
   SELECT * FROM ontology.v_portfolio_health;

8. Enable row-level security (when ready):
   ALTER TABLE knowledge_base.configuration_versions ENABLE ROW LEVEL SECURITY;
   ALTER TABLE knowledge_base.evidence ENABLE ROW LEVEL SECURITY;
   ALTER TABLE knowledge_base.decision_records ENABLE ROW LEVEL SECURITY;

EVIDENCE CAPTURE WORKFLOW:

Step 1: Capture evidence from source systems
  SELECT knowledge_base.capture_source_event(
    'Salesforce',
    'salesforce_record',
    'configuration_version',
    'CFGV-0001-1',
    'Pricebook entry created for product variant',
    'Salesforce Admin'
  );

Step 2: Capture governance approvals manually
  SELECT knowledge_base.capture_governance_evidence(
    'governance_approval',
    'configuration_version',
    'CFGV-0001-1',
    'Approved for production launch in US region',
    'Product Management',
    1.0
  );

Step 3: Record decision with evidence basis
  SELECT knowledge_base.record_decision(
    'identity_assessment',
    'configuration_version',
    'CFGV-0001-1',
    'CREATE_CONFIGURATION',
    'Ops',
    'EV-20260903120000-1234,EV-20260903120100-5678',
    'high'
  );

Step 4: Query readiness for this configuration
  SELECT * FROM ontology.get_launch_readiness('CFGV-0001-1');

QUERYING USE CASES:

UC-01: SELECT * FROM ontology.v_launch_readiness;
UC-03: SELECT * FROM ontology.assess_configuration_identity('CFG-0001');
UC-06: SELECT * FROM ontology.get_evidence_lineage('EV-0001');
UC-09: SELECT * FROM ontology.map_legacy_constraints('CFG-0001');
UC-10: SELECT * FROM ontology.get_proliferation_cost('CFGV-0001-1');
UC-22: SELECT * FROM ontology.v_phase2_backlog;

*/

