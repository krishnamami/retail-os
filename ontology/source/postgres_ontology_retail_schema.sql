-- Claris v0.5 Postgres Ontology - Retail Schema
-- Complete ontology structure for retail domain with knowledge base and evidence views
-- This is the foundational layer for all 22 use cases

-- ============================================================================
-- PART 1: CORE ONTOLOGY REFERENCE TABLES (21 tables)
-- ============================================================================

-- 1. Ontology Release Tracking
CREATE TABLE IF NOT EXISTS ontology.ontology_release (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  release_date              TIMESTAMP NOT NULL,
  description               TEXT,
  status                    VARCHAR(32) CHECK (status IN ('draft', 'active', 'deprecated')),
  PRIMARY KEY (domain, ontology_version)
) COMMENT 'Version control for ontology models';

-- 2. Object Types (what entities exist in the domain)
CREATE TABLE IF NOT EXISTS ontology.object_types (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  object_type               VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  is_governance_entity      BOOLEAN DEFAULT FALSE,
  is_evidence_entity        BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (domain, ontology_version, object_type)
) COMMENT 'Entities that exist in the ontology';

-- 3. Object Properties (attributes of entities)
CREATE TABLE IF NOT EXISTS ontology.object_properties (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  object_type               VARCHAR(128) NOT NULL,
  property_name             VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  data_type                 VARCHAR(64),
  is_identity_key           BOOLEAN DEFAULT FALSE,
  is_queryable              BOOLEAN DEFAULT TRUE,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, object_type, property_name),
  FOREIGN KEY (domain, ontology_version, object_type) REFERENCES ontology.object_types(domain, ontology_version, object_type)
) COMMENT 'Properties and attributes of objects';

-- 4. Links (relationships between entities)
CREATE TABLE IF NOT EXISTS ontology.links (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  link_name                 VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  from_type                 VARCHAR(128) NOT NULL,
  to_type                   VARCHAR(128) NOT NULL,
  cardinality               VARCHAR(16) CHECK (cardinality IN ('1:1', '1:N', 'N:M')),
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, link_name)
) COMMENT 'Relationships between objects';

-- 5. Departments (organizational units with governance responsibilities)
CREATE TABLE IF NOT EXISTS ontology.departments (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  department                VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, department)
) COMMENT 'Organizational departments (Ops, IS&T, Finance, etc.)';

-- 6. Actors (individuals or roles accountable for decisions)
CREATE TABLE IF NOT EXISTS ontology.actors (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  actor                     VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  role_type                 VARCHAR(64),
  department                VARCHAR(128),
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, actor),
  FOREIGN KEY (domain, ontology_version, department) REFERENCES ontology.departments(domain, ontology_version, department)
) COMMENT 'Decision makers and process owners';

-- 7. Evidence Types (what can be captured as evidence)
CREATE TABLE IF NOT EXISTS ontology.evidence_types (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  evidence_type             VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  captures_from             VARCHAR(256),
  is_automatic              BOOLEAN DEFAULT FALSE,
  is_manual                 BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (domain, ontology_version, evidence_type)
) COMMENT 'Types of evidence that support decisions';

-- 8. Inference Rules (how to derive conclusions from evidence)
CREATE TABLE IF NOT EXISTS ontology.inference_rules (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  rule_name                 VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  requires_evidence_types   TEXT,
  derives_conclusion        VARCHAR(256),
  PRIMARY KEY (domain, ontology_version, rule_name)
) COMMENT 'Logic for deriving conclusions from evidence';

-- 9. Contradiction Checks (what should never be true together)
CREATE TABLE IF NOT EXISTS ontology.contradiction_checks (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  check_name                VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  condition_1               TEXT NOT NULL,
  condition_2               TEXT NOT NULL,
  severity                  VARCHAR(32) CHECK (severity IN ('error', 'warning', 'info')),
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, check_name)
) COMMENT 'Detects impossible states';

-- 10. Decisions (what must be decided in this ontology)
CREATE TABLE IF NOT EXISTS ontology.decisions (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  decision_id               VARCHAR(64) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  decision_type             VARCHAR(64),
  possible_outcomes         TEXT,
  PRIMARY KEY (domain, ontology_version, decision_id)
) COMMENT 'Decisions that must be made in the ontology';

-- 11. Decision Inputs (what data a decision reads)
CREATE TABLE IF NOT EXISTS ontology.decision_inputs (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  decision_id               VARCHAR(64) NOT NULL,
  input_ordinal             INT NOT NULL,
  input_source              VARCHAR(256),
  input_type                VARCHAR(128),
  is_required               BOOLEAN DEFAULT TRUE,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, decision_id, input_ordinal),
  FOREIGN KEY (domain, ontology_version, decision_id) REFERENCES ontology.decisions(domain, ontology_version, decision_id)
) COMMENT 'Inputs required to make a decision';

-- 12. Decision Outputs (what a decision produces)
CREATE TABLE IF NOT EXISTS ontology.decision_outputs (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  decision_id               VARCHAR(64) NOT NULL,
  output_ordinal            INT NOT NULL,
  output_type               VARCHAR(128),
  output_name               VARCHAR(256),
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, decision_id, output_ordinal),
  FOREIGN KEY (domain, ontology_version, decision_id) REFERENCES ontology.decisions(domain, ontology_version, decision_id)
) COMMENT 'Outputs produced by a decision';

-- 13. Decision Dependencies (ordering of decisions)
CREATE TABLE IF NOT EXISTS ontology.decision_dependencies (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  decision_id               VARCHAR(64) NOT NULL,
  depends_on_decision_id    VARCHAR(64) NOT NULL,
  dependency_type           VARCHAR(64) CHECK (dependency_type IN ('blocking', 'informing', 'sequential')),
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, decision_id, depends_on_decision_id),
  FOREIGN KEY (domain, ontology_version, decision_id) REFERENCES ontology.decisions(domain, ontology_version, decision_id),
  FOREIGN KEY (domain, ontology_version, depends_on_decision_id) REFERENCES ontology.decisions(domain, ontology_version, decision_id)
) COMMENT 'Which decisions must be made before others';

-- 14. Read Grants (who can read what)
CREATE TABLE IF NOT EXISTS ontology.read_grants (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  actor                     VARCHAR(128) NOT NULL,
  object_type               VARCHAR(128) NOT NULL,
  grant_type                VARCHAR(64) CHECK (grant_type IN ('all', 'own', 'department', 'filtered')),
  filter_condition          TEXT,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, actor, object_type),
  FOREIGN KEY (domain, ontology_version, actor) REFERENCES ontology.actors(domain, ontology_version, actor),
  FOREIGN KEY (domain, ontology_version, object_type) REFERENCES ontology.object_types(domain, ontology_version, object_type)
) COMMENT 'Read access control rules';

-- 15. Action Types (what actions are possible)
CREATE TABLE IF NOT EXISTS ontology.action_types (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  action_type               VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  is_reversible             BOOLEAN DEFAULT FALSE,
  requires_approval         BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (domain, ontology_version, action_type)
) COMMENT 'Types of actions that can be taken';

-- 16. Action Authorizations (who can take what actions)
CREATE TABLE IF NOT EXISTS ontology.action_authorizations (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  actor                     VARCHAR(128) NOT NULL,
  action_type               VARCHAR(128) NOT NULL,
  on_object_type            VARCHAR(128),
  condition                 TEXT,
  requires_evidence         BOOLEAN DEFAULT FALSE,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, actor, action_type),
  FOREIGN KEY (domain, ontology_version, actor) REFERENCES ontology.actors(domain, ontology_version, actor),
  FOREIGN KEY (domain, ontology_version, action_type) REFERENCES ontology.action_types(domain, ontology_version, action_type)
) COMMENT 'Authorization rules for actions';

-- 17. Enums (controlled vocabularies)
CREATE TABLE IF NOT EXISTS ontology.enums (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  enum_name                 VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, enum_name)
) COMMENT 'Enumerated value sets';

-- 18. Enum Values (individual enum entries)
CREATE TABLE IF NOT EXISTS ontology.enum_values (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  enum_name                 VARCHAR(128) NOT NULL,
  enum_value                VARCHAR(256) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, enum_name, enum_value),
  FOREIGN KEY (domain, ontology_version, enum_name) REFERENCES ontology.enums(domain, ontology_version, enum_name)
) COMMENT 'Values within controlled vocabularies';

-- 19. Configuration Dimensions (what dimensions define a configuration)
CREATE TABLE IF NOT EXISTS ontology.configuration_dimensions (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  dimension                 VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  label                     VARCHAR(256),
  authority                 VARCHAR(128),
  governance_state          VARCHAR(32) CHECK (governance_state IN ('unknown', 'governed', 'deprecated')),
  impact_if_wrong           TEXT,
  blocks_identity_assessment BOOLEAN DEFAULT FALSE,
  rationale                 TEXT,
  PRIMARY KEY (domain, ontology_version, dimension)
) COMMENT 'Dimensions that vary within a configuration';

-- 20. Configuration Dimension Values (allowed values for dimensions)
CREATE TABLE IF NOT EXISTS ontology.configuration_dimension_values (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  dimension                 VARCHAR(128) NOT NULL,
  value                     VARCHAR(256) NOT NULL,
  ordinal                   INT NOT NULL,
  label                     VARCHAR(256),
  active                    BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (domain, ontology_version, dimension, value),
  FOREIGN KEY (domain, ontology_version, dimension) REFERENCES ontology.configuration_dimensions(domain, ontology_version, dimension)
) COMMENT 'Valid values for each dimension';

-- 21. Identity Rules (what makes something the same identity across changes)
CREATE TABLE IF NOT EXISTS ontology.identity_rules (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  rule                      VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  change_type               VARCHAR(128),
  proposed_effect           VARCHAR(128) CHECK (proposed_effect IN ('CREATE_PRODUCT', 'CREATE_CONFIGURATION', 'NEW_VERSION', 'USE_EXISTING', 'NO_BUSINESS_CHANGE', 'CANNOT_DECIDE')),
  owner                     VARCHAR(128),
  status                    VARCHAR(32) CHECK (status IN ('proposed', 'confirm_with_claris', 'confirmed')),
  observed_materials        INT,
  rationale                 TEXT,
  PRIMARY KEY (domain, ontology_version, rule),
  FOREIGN KEY (domain, ontology_version, owner) REFERENCES ontology.actors(domain, ontology_version, actor)
) COMMENT 'Rules determining whether an identity is new or existing';

-- 22. Projection Rules (what target systems require for each identity outcome)
CREATE TABLE IF NOT EXISTS ontology.projection_rules (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  rule                      VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  identity_effect           VARCHAR(128),
  target_system             VARCHAR(128),
  target_object_type        VARCHAR(128),
  proposed_action           VARCHAR(32) CHECK (proposed_action IN ('CREATE', 'UPDATE', 'RETIRE', 'NO_ACTION')),
  requires_new_target_identity BOOLEAN DEFAULT FALSE,
  projection_reason         VARCHAR(256),
  owner                     VARCHAR(128),
  status                    VARCHAR(32) CHECK (status IN ('proposed', 'confirm_with_claris', 'confirmed')),
  rationale                 TEXT,
  PRIMARY KEY (domain, ontology_version, rule),
  FOREIGN KEY (domain, ontology_version, owner) REFERENCES ontology.actors(domain, ontology_version, actor)
) COMMENT 'Rules defining what target systems need from each identity decision';


-- ============================================================================
-- PART 2: USE CASES TABLE (All 22 use cases)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ontology.use_cases (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  use_case                  VARCHAR(16) NOT NULL,
  ordinal                   INT NOT NULL,
  name                      VARCHAR(256) NOT NULL,
  business_question         TEXT NOT NULL,
  capability_group          VARCHAR(256),
  client_outcome            VARCHAR(256),
  mechanism                 VARCHAR(256),
  decided_by                VARCHAR(128),
  reads_object_types        TEXT,
  result                    TEXT,
  phase                     INT CHECK (phase IN (1, 2)),
  status                    VARCHAR(32) CHECK (status IN ('buildable', 'needs_instances', 'blocked')),
  blocked_on                TEXT,
  journey_order             INT,
  in_demo                   BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (domain, ontology_version, use_case)
) COMMENT 'All 22 client-facing use cases with the mechanisms that answer them';


-- ============================================================================
-- PART 3: KNOWLEDGE BASE LAYER (Derived and instance data)
-- ============================================================================

-- Configuration versions (instances)
CREATE TABLE IF NOT EXISTS knowledge_base.configuration_versions (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  version_id                VARCHAR(64) NOT NULL,
  configuration_id          VARCHAR(64) NOT NULL,
  product_id                VARCHAR(64),
  version_no                INT NOT NULL,
  change_type               VARCHAR(128),
  identity_effect           VARCHAR(128),
  reason_code               VARCHAR(256),
  missing_what              TEXT,
  projection_count          INT DEFAULT 0,
  created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by                VARCHAR(128),
  PRIMARY KEY (domain, ontology_version, version_id)
) COMMENT 'Configuration versions in production';

-- Configuration values (dimension settings per version)
CREATE TABLE IF NOT EXISTS knowledge_base.configuration_values (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  version_id                VARCHAR(64) NOT NULL,
  dimension                 VARCHAR(128) NOT NULL,
  value                     VARCHAR(256) NOT NULL,
  effective_from            DATE NOT NULL,
  effective_to              DATE,
  evidence_id               VARCHAR(256),
  PRIMARY KEY (domain, ontology_version, version_id, dimension),
  FOREIGN KEY (domain, ontology_version, version_id) REFERENCES knowledge_base.configuration_versions(domain, ontology_version, version_id)
) COMMENT 'Dimension assignments to configuration versions';

-- Projections (physical rows in target systems)
CREATE TABLE IF NOT EXISTS knowledge_base.projections (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  projection_id             VARCHAR(64) NOT NULL,
  version_id                VARCHAR(64) NOT NULL,
  target_system             VARCHAR(128) NOT NULL,
  target_object_type        VARCHAR(128),
  target_key                VARCHAR(256),
  projection_action         VARCHAR(32),
  new_target_identity       BOOLEAN DEFAULT FALSE,
  projection_reason         VARCHAR(256),
  counts_as_proliferation   BOOLEAN DEFAULT FALSE,
  projection_status         VARCHAR(32) CHECK (projection_status IN ('required', 'pending', 'confirmed', 'failed', 'superseded')),
  created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (domain, ontology_version, projection_id),
  FOREIGN KEY (domain, ontology_version, version_id) REFERENCES knowledge_base.configuration_versions(domain, ontology_version, version_id)
) COMMENT 'Physical records in target systems derived from configurations';

-- Evidence (facts that support decisions)
CREATE TABLE IF NOT EXISTS knowledge_base.evidence (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  evidence_id               VARCHAR(256) NOT NULL,
  evidence_type             VARCHAR(128) NOT NULL,
  subject_type              VARCHAR(128),
  subject_id                VARCHAR(256),
  assertion                 TEXT NOT NULL,
  source_system             VARCHAR(128),
  collection_method         VARCHAR(256),
  asserting_party           VARCHAR(128),
  captured_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  authority_score           DECIMAL(3,2) DEFAULT 1.0,
  PRIMARY KEY (domain, ontology_version, evidence_id)
) COMMENT 'Evidence captured to support decisions';

-- Decision records (what decisions were made and their outcomes)
CREATE TABLE IF NOT EXISTS knowledge_base.decision_records (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  record_id                 VARCHAR(256) NOT NULL,
  decision_id               VARCHAR(64) NOT NULL,
  subject_type              VARCHAR(128),
  subject_id                VARCHAR(256),
  outcome                   TEXT,
  decided_by                VARCHAR(128),
  decided_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  basis_evidence_ids        TEXT,
  confidence_level          VARCHAR(32) CHECK (confidence_level IN ('certain', 'high', 'medium', 'low', 'unknown')),
  PRIMARY KEY (domain, ontology_version, record_id)
) COMMENT 'Records of decisions made in the system';

-- Change impact summary (cost per change type)
CREATE TABLE IF NOT EXISTS knowledge_base.change_impact (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  change_type               VARCHAR(128) NOT NULL,
  ordinal                   INT,
  identity_rule             VARCHAR(128),
  reads_dimension           VARCHAR(128),
  proposed_effect           VARCHAR(128),
  affects_product           BOOLEAN,
  affects_configuration     BOOLEAN,
  affects_version           BOOLEAN,
  affects_pricing           BOOLEAN,
  affects_entitlement       BOOLEAN,
  affects_hierarchy         BOOLEAN,
  systems_affected          VARCHAR(512),
  records_created           INT DEFAULT 0,
  proliferation_records     INT DEFAULT 0,
  observed_materials        INT DEFAULT 0,
  identity_decidable        BOOLEAN,
  blocked_by_dimension      VARCHAR(128),
  PRIMARY KEY (domain, ontology_version, change_type)
) COMMENT 'Derived: what each change type costs in physical records';


-- ============================================================================
-- PART 4: EVIDENCE CAPTURE VIEWS (For use case execution)
-- ============================================================================

-- UC-03: Configuration identity stability
CREATE OR REPLACE VIEW ontology.v_identity_assessment AS
SELECT
  cv.domain,
  cv.ontology_version,
  cv.version_id,
  cv.configuration_id,
  cv.identity_effect,
  COUNT(DISTINCT p.projection_id) as records_created,
  STRING_AGG(DISTINCT cv2.version_no::TEXT, ', ' ORDER BY cv2.version_no::TEXT) as versions_in_history,
  CASE
    WHEN cv.identity_effect = 'CREATE_CONFIGURATION' THEN 'New identity confirmed'
    WHEN cv.identity_effect = 'NEW_VERSION' THEN 'Identity persists, version changed'
    WHEN cv.identity_effect = 'USE_EXISTING' THEN 'No change to identity'
    WHEN cv.identity_effect = 'CANNOT_DECIDE' THEN 'Blocked: ' || cv.reason_code
    ELSE 'Unknown'
  END as identity_status
FROM knowledge_base.configuration_versions cv
LEFT JOIN knowledge_base.configuration_versions cv2 ON cv2.configuration_id = cv.configuration_id
LEFT JOIN knowledge_base.projections p ON p.version_id = cv.version_id
GROUP BY cv.domain, cv.ontology_version, cv.version_id, cv.configuration_id, cv.identity_effect, cv.reason_code
ORDER BY cv.configuration_id, cv.version_no DESC;

-- UC-09 & UC-10: Proliferation analysis
CREATE OR REPLACE VIEW ontology.v_proliferation_analysis AS
SELECT
  p.domain,
  p.ontology_version,
  p.target_system,
  COUNT(*) as total_records,
  SUM(CASE WHEN p.counts_as_proliferation THEN 1 ELSE 0 END) as proliferation_records,
  SUM(CASE WHEN NOT p.counts_as_proliferation THEN 1 ELSE 0 END) as business_growth_records,
  STRING_AGG(DISTINCT p.projection_reason, ', ' ORDER BY p.projection_reason) as reason_codes,
  ROUND(100.0 * SUM(CASE WHEN p.counts_as_proliferation THEN 1 ELSE 0 END) /
        NULLIF(COUNT(*), 0), 1) as pct_legacy_driven
FROM knowledge_base.projections p
WHERE p.projection_status IN ('confirmed', 'required')
GROUP BY p.domain, p.ontology_version, p.target_system
ORDER BY proliferation_records DESC;

-- UC-01: Launch readiness status
CREATE OR REPLACE VIEW ontology.v_launch_readiness AS
SELECT
  cv.domain,
  cv.ontology_version,
  cv.version_id,
  cv.configuration_id,
  cv.change_type,
  cv.identity_effect,
  COUNT(DISTINCT k.evidence_id) as evidence_count,
  COUNT(DISTINCT dr.record_id) as decisions_made,
  CASE
    WHEN cv.identity_effect = 'CANNOT_DECIDE' THEN 'BLOCKED'
    WHEN COUNT(DISTINCT dr.record_id) < 3 THEN 'INCOMPLETE'
    WHEN COUNT(DISTINCT k.evidence_id) < 2 THEN 'MISSING_EVIDENCE'
    ELSE 'READY'
  END as readiness_status,
  cv.missing_what as missing_items
FROM knowledge_base.configuration_versions cv
LEFT JOIN knowledge_base.evidence k ON k.subject_id = cv.version_id
LEFT JOIN knowledge_base.decision_records dr ON dr.subject_id = cv.version_id
GROUP BY cv.domain, cv.ontology_version, cv.version_id, cv.configuration_id,
         cv.change_type, cv.identity_effect, cv.missing_what
ORDER BY cv.configuration_id, cv.version_no DESC;

-- UC-02: Decision delegation matrix
CREATE OR REPLACE VIEW ontology.v_decision_delegation AS
SELECT
  d.domain,
  d.ontology_version,
  d.decision_id,
  d.description,
  a.actor,
  a.role_type,
  a.department,
  STRING_AGG(DISTINCT di.input_source, ', ' ORDER BY di.input_source) as required_inputs,
  STRING_AGG(DISTINCT do.output_type, ', ' ORDER BY do.output_type) as produces_outputs,
  STRING_AGG(DISTINCT dd.depends_on_decision_id, ', ' ORDER BY dd.depends_on_decision_id) as must_happen_after
FROM ontology.decisions d
LEFT JOIN ontology.decision_inputs di ON d.domain = di.domain AND d.ontology_version = di.ontology_version AND d.decision_id = di.decision_id
LEFT JOIN ontology.decision_outputs do ON d.domain = do.domain AND d.ontology_version = do.ontology_version AND d.decision_id = do.decision_id
LEFT JOIN ontology.decision_dependencies dd ON d.domain = dd.domain AND d.ontology_version = dd.ontology_version AND d.decision_id = dd.decision_id
LEFT JOIN ontology.actors a ON d.domain = a.domain AND d.ontology_version = a.ontology_version
GROUP BY d.domain, d.ontology_version, d.decision_id, d.description, a.actor, a.role_type, a.department
ORDER BY d.ordinal;

-- UC-06: Evidence lineage
CREATE OR REPLACE VIEW ontology.v_evidence_lineage AS
SELECT
  e.domain,
  e.ontology_version,
  e.evidence_id,
  e.evidence_type,
  e.subject_type,
  e.subject_id,
  e.assertion,
  e.source_system,
  e.collection_method,
  e.asserting_party,
  e.captured_at,
  e.authority_score,
  STRING_AGG(DISTINCT dr.decision_id, ', ' ORDER BY dr.decision_id) as supports_decisions
FROM knowledge_base.evidence e
LEFT JOIN knowledge_base.decision_records dr ON dr.domain = e.domain
    AND dr.ontology_version = e.ontology_version
    AND dr.basis_evidence_ids LIKE '%' || e.evidence_id || '%'
GROUP BY e.domain, e.ontology_version, e.evidence_id, e.evidence_type, e.subject_type,
         e.subject_id, e.assertion, e.source_system, e.collection_method, e.asserting_party,
         e.captured_at, e.authority_score
ORDER BY e.captured_at DESC;

-- UC-15: Identity rule audit
CREATE OR REPLACE VIEW ontology.v_identity_rule_audit AS
SELECT
  ir.domain,
  ir.ontology_version,
  ir.rule,
  ir.change_type,
  ir.proposed_effect,
  ir.status,
  COUNT(DISTINCT cv.version_id) as configurations_using_rule,
  SUM(CASE WHEN cv.identity_effect = ir.proposed_effect THEN 1 ELSE 0 END) as rule_confirmed_count,
  SUM(CASE WHEN cv.identity_effect <> ir.proposed_effect AND cv.identity_effect IS NOT NULL THEN 1 ELSE 0 END) as rule_violated_count
FROM ontology.identity_rules ir
LEFT JOIN knowledge_base.configuration_versions cv ON cv.domain = ir.domain
    AND cv.ontology_version = ir.ontology_version
    AND cv.change_type = ir.change_type
GROUP BY ir.domain, ir.ontology_version, ir.rule, ir.change_type, ir.proposed_effect, ir.status
ORDER BY rule_violated_count DESC, ir.ordinal;

-- UC-19: Missing dimensions
CREATE OR REPLACE VIEW ontology.v_dimension_completeness AS
SELECT
  cv.domain,
  cv.ontology_version,
  cv.version_id,
  cv.configuration_id,
  cd.dimension,
  CASE WHEN k.value IS NOT NULL THEN 'assigned' ELSE 'missing' END as assignment_status,
  cd.governance_state,
  cd.blocks_identity_assessment
FROM knowledge_base.configuration_versions cv
CROSS JOIN ontology.configuration_dimensions cd
LEFT JOIN knowledge_base.configuration_values k ON cv.domain = k.domain
    AND cv.ontology_version = k.ontology_version
    AND cv.version_id = k.version_id
    AND cd.dimension = k.dimension
WHERE cv.domain = cd.domain AND cv.ontology_version = cd.ontology_version
ORDER BY cv.configuration_id, cv.version_no DESC, cd.dimension;

-- UC-22: Phase 2 elimination backlog
CREATE OR REPLACE VIEW ontology.v_elimination_backlog AS
SELECT
  p.domain,
  p.ontology_version,
  p.target_system,
  p.projection_reason,
  COUNT(DISTINCT p.projection_id) as record_count,
  COUNT(DISTINCT p.version_id) as configurations_affected,
  STRING_AGG(DISTINCT p.target_object_type, ', ' ORDER BY p.target_object_type) as object_types_created,
  pr.status as projection_rule_status,
  pr.rationale
FROM knowledge_base.projections p
LEFT JOIN ontology.projection_rules pr ON p.domain = pr.domain
    AND p.ontology_version = pr.ontology_version
    AND p.target_system = pr.target_system
WHERE p.counts_as_proliferation = TRUE
  AND p.projection_status IN ('confirmed', 'required')
GROUP BY p.domain, p.ontology_version, p.target_system, p.projection_reason, pr.status, pr.rationale
ORDER BY record_count DESC;

-- Master decision workbench (for UC-04 and others)
CREATE OR REPLACE VIEW ontology.v_open_decisions AS
SELECT
  'dimension'::VARCHAR as item_type,
  cd.dimension as item,
  cd.label as subject,
  cd.authority as owed_by,
  cd.governance_state as state,
  COALESCE(cd.impact_if_wrong, '-') as at_stake,
  CASE WHEN cd.blocks_identity_assessment
       THEN 'Blocks IDENTITY_ASSESSMENT for any change touching this dimension'
       ELSE '-' END as consequence,
  cd.rationale
FROM ontology.configuration_dimensions cd
WHERE cd.blocks_identity_assessment
  AND cd.governance_state = 'unknown'

UNION ALL

SELECT
  'identity_rule'::VARCHAR,
  ir.rule,
  ir.change_type,
  ir.owner,
  ir.status,
  CONCAT(CAST(ir.observed_materials AS VARCHAR), ' materials observed'),
  CONCAT('Proposes ', ir.proposed_effect),
  ir.rationale
FROM ontology.identity_rules ir
WHERE ir.status <> 'confirmed'

UNION ALL

SELECT
  'projection_rule'::VARCHAR,
  pr.rule,
  CONCAT(pr.identity_effect, ' → ', pr.target_system),
  pr.owner,
  pr.status,
  CONCAT(CAST(CASE WHEN pr.requires_new_target_identity THEN 1 ELSE 0 END AS VARCHAR), ' new identities'),
  CONCAT('Proposes ', pr.proposed_action),
  pr.rationale
FROM ontology.projection_rules pr
WHERE pr.status <> 'confirmed'

ORDER BY at_stake DESC, item;

