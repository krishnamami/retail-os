-- Claris v0.5 Postgres Ontology - Retail Schema
-- Complete ontology structure for retail domain with knowledge base and evidence views

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
);

-- 2. Object Types
CREATE TABLE IF NOT EXISTS ontology.object_types (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  object_type               VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  is_governance_entity      BOOLEAN DEFAULT FALSE,
  is_evidence_entity        BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (domain, ontology_version, object_type)
);

-- 3. Object Properties
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
);

-- 4. Links
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
);

-- 5. Departments
CREATE TABLE IF NOT EXISTS ontology.departments (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  department                VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, department)
);

-- 6. Actors
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
);

-- 7. Evidence Types
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
);

-- 8. Inference Rules
CREATE TABLE IF NOT EXISTS ontology.inference_rules (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  rule_name                 VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  requires_evidence_types   TEXT,
  derives_conclusion        VARCHAR(256),
  PRIMARY KEY (domain, ontology_version, rule_name)
);

-- 9. Contradiction Checks
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
);

-- 10. Decisions
CREATE TABLE IF NOT EXISTS ontology.decisions (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  decision_id               VARCHAR(64) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  decision_type             VARCHAR(64),
  possible_outcomes         TEXT,
  PRIMARY KEY (domain, ontology_version, decision_id)
);

-- 11. Decision Inputs
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
);

-- 12. Decision Outputs
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
);

-- 13. Decision Dependencies
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
);

-- 14. Read Grants
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
);

-- 15. Action Types
CREATE TABLE IF NOT EXISTS ontology.action_types (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  action_type               VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  is_reversible             BOOLEAN DEFAULT FALSE,
  requires_approval         BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (domain, ontology_version, action_type)
);

-- 16. Action Authorizations
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
);

-- 17. Enums
CREATE TABLE IF NOT EXISTS ontology.enums (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  enum_name                 VARCHAR(128) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, enum_name)
);

-- 18. Enum Values
CREATE TABLE IF NOT EXISTS ontology.enum_values (
  domain                    VARCHAR(64) NOT NULL,
  ontology_version          VARCHAR(16) NOT NULL,
  enum_name                 VARCHAR(128) NOT NULL,
  enum_value                VARCHAR(256) NOT NULL,
  ordinal                   INT NOT NULL,
  description               TEXT,
  PRIMARY KEY (domain, ontology_version, enum_name, enum_value),
  FOREIGN KEY (domain, ontology_version, enum_name) REFERENCES ontology.enums(domain, ontology_version, enum_name)
);

-- 19. Configuration Dimensions
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
);

-- 20. Configuration Dimension Values
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
);

-- 21. Identity Rules
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
  PRIMARY KEY (domain, ontology_version, rule)
);

-- 22. Projection Rules
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
  PRIMARY KEY (domain, ontology_version, rule)
);

-- USE CASES TABLE
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
);

-- KNOWLEDGE BASE LAYER
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
);

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
);

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
);

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
);

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
);

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
);
