-- ============================================================================
-- COMPLETE KB SETUP: ONE SCRIPT TO LOAD EVERYTHING (FIXED - no superuser needed)
-- ============================================================================

BEGIN;

-- Drop old functions (clean slate)
DROP FUNCTION IF EXISTS ontology.load_kb_dimensions(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_evidence_types(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_decisions(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_decision_inputs(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_decision_outputs(JSONB, VARCHAR, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_identity_rules(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_projection_rules(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_action_types(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_action_authorizations(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_roles(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_read_grants(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_kb_use_cases(JSONB, VARCHAR, TIMESTAMPTZ, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.load_knowledge_base(JSONB, VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS ontology.validate_kb_json(JSONB) CASCADE;

-- Create storage table for KB JSON
CREATE TABLE IF NOT EXISTS ontology.kb_store (
  kb_version VARCHAR(32) PRIMARY KEY,
  kb_data JSONB NOT NULL,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Load KB JSON into table (JSON embedded below using dollar-quoting)
INSERT INTO ontology.kb_store (kb_version, kb_data)
VALUES ('1.0', $KB_JSON$
{
  "kb_metadata": {
    "kb_version": "1.0",
    "kb_name": "Claris Core Knowledge Base v1.0",
    "policy_version": "1.0",
    "effective_from": "2026-09-03T00:00:00Z",
    "effective_to": null,
    "release_notes": "Initial Claris KB for product configuration governance. Covers 12 dimensions, 6 decision types, identity composition, projection rules, role-based access, 22 use cases across decision execution, query/read models, and simulations.",
    "author": "Claris Architecture"
  },

  "objects": {
    "product": {
      "object_id": "PRODUCT",
      "description": "Sellable offering (e.g., Pulse Max, Pulse Pro, Core). Represents a coherent product in the portfolio.",
      "identity_fields": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_TIER"],
      "lifecycle_states": ["launched", "planned", "retired"],
      "system_ids": []
    },
    "configuration": {
      "object_id": "CONFIGURATION",
      "description": "Product + commercial positioning for a market segment. The canonical identity: what we sell to whom at what terms.",
      "identity_fields": ["product_id", "D_SEGMENT", "D_GEOGRAPHY", "D_MARKET"],
      "commercial_fields": ["D_PRICE_USD", "D_PRICING_TYPE", "D_CURRENCY", "D_CONTRACT_LENGTH_MONTHS"],
      "system_ids": ["SAP_MATERIAL_ID", "ALL_SKUS_ID", "CATALOG_ID"],
      "lifecycle_states": ["planned", "active", "retired"]
    },
    "sku": {
      "object_id": "SKU",
      "description": "Physical manifestation in legacy/target systems. One canonical configuration may map to multiple physical SKUs due to system constraints.",
      "identity_fields": ["SAP_MATERIAL_ID", "ALL_SKUS_ID", "CATALOG_ID"],
      "system_of_origin": ["SAP", "all_skus", "ww_pricing", "Salesforce"],
      "lifecycle_states": ["planned", "active", "retired"]
    }
  },

  "dimensions": {
    "D_PRODUCT_FAMILY": {
      "dimension_id": "D_PRODUCT_FAMILY",
      "dimension_name": "Product Family",
      "category": "identity",
      "data_type": "VARCHAR(64)",
      "cardinality": "low",
      "examples": ["Pulse", "Core", "Enterprise"],
      "required_for_identity": true,
      "required_for_projection": ["SAP", "all_skus", "ww_pricing", "Salesforce"],
      "validation_rule": "IN (SELECT product_family FROM reference.product_families)",
      "validation_type": "reference_integrity"
    },
    "D_OFFERING": {
      "dimension_id": "D_OFFERING",
      "dimension_name": "Offering",
      "category": "identity",
      "data_type": "VARCHAR(64)",
      "cardinality": "medium",
      "examples": ["Max", "Pro", "Standard"],
      "required_for_identity": true,
      "required_for_projection": ["SAP", "all_skus", "ww_pricing"],
      "validation_rule": "LENGTH <= 32",
      "validation_type": "format"
    },
    "D_TIER": {
      "dimension_id": "D_TIER",
      "dimension_name": "Tier",
      "category": "commercial",
      "data_type": "VARCHAR(32)",
      "cardinality": "low",
      "examples": ["Premium", "Standard", "Basic"],
      "required_for_identity": true,
      "required_for_projection": ["SAP", "all_skus"],
      "validation_rule": "IN ('Premium', 'Standard', 'Basic')",
      "validation_type": "enumeration"
    },
    "D_SEGMENT": {
      "dimension_id": "D_SEGMENT",
      "dimension_name": "Segment",
      "category": "commercial",
      "data_type": "VARCHAR(32)",
      "cardinality": "low",
      "examples": ["Enterprise", "Mid-Market", "SMB"],
      "required_for_identity": true,
      "required_for_projection": ["all_skus", "Salesforce"],
      "validation_rule": "IN ('Enterprise', 'Mid-Market', 'SMB')",
      "validation_type": "enumeration"
    },
    "D_GEOGRAPHY": {
      "dimension_id": "D_GEOGRAPHY",
      "dimension_name": "Geography",
      "category": "commercial",
      "data_type": "VARCHAR(2)",
      "cardinality": "low",
      "examples": ["US", "EMEA", "APAC"],
      "required_for_identity": true,
      "required_for_projection": ["SAP", "all_skus", "ww_pricing", "Salesforce"],
      "validation_rule": "IN (SELECT region_code FROM reference.regions)",
      "validation_type": "reference_integrity"
    },
    "D_MARKET": {
      "dimension_id": "D_MARKET",
      "dimension_name": "Market",
      "category": "commercial",
      "data_type": "VARCHAR(64)",
      "cardinality": "medium",
      "examples": ["Retail", "CPG", "Healthcare"],
      "required_for_identity": true,
      "required_for_projection": ["Salesforce"],
      "validation_rule": "IN (SELECT market_name FROM reference.markets)",
      "validation_type": "reference_integrity"
    },
    "D_PRICE_USD": {
      "dimension_id": "D_PRICE_USD",
      "dimension_name": "Price (USD)",
      "category": "commercial",
      "data_type": "NUMERIC(10,2)",
      "cardinality": "high",
      "examples": [99.99, 499.99, 1999.99],
      "required_for_identity": false,
      "required_for_projection": ["ww_pricing", "Salesforce"],
      "validation_rule": "BETWEEN 0.01 AND 999999.99",
      "validation_type": "range"
    },
    "D_PRICING_TYPE": {
      "dimension_id": "D_PRICING_TYPE",
      "dimension_name": "Pricing Type",
      "category": "commercial",
      "data_type": "VARCHAR(32)",
      "cardinality": "low",
      "examples": ["Annual", "Monthly", "Perpetual"],
      "required_for_identity": false,
      "required_for_projection": ["ww_pricing", "Salesforce"],
      "validation_rule": "IN ('Annual', 'Monthly', 'Perpetual')",
      "validation_type": "enumeration"
    },
    "D_CURRENCY": {
      "dimension_id": "D_CURRENCY",
      "dimension_name": "Currency",
      "category": "commercial",
      "data_type": "VARCHAR(3)",
      "cardinality": "low",
      "examples": ["USD", "EUR", "GBP"],
      "required_for_identity": false,
      "required_for_projection": ["ww_pricing", "Salesforce"],
      "validation_rule": "LENGTH = 3 AND UPPER(value) = value",
      "validation_type": "format"
    },
    "D_CONTRACT_LENGTH_MONTHS": {
      "dimension_id": "D_CONTRACT_LENGTH_MONTHS",
      "dimension_name": "Contract Length (months)",
      "category": "commercial",
      "data_type": "INT",
      "cardinality": "low",
      "examples": [12, 24, 36, 60],
      "required_for_identity": false,
      "required_for_projection": ["Salesforce"],
      "validation_rule": "IN (12, 24, 36, 60)",
      "validation_type": "enumeration"
    },
    "SAP_MATERIAL_ID": {
      "dimension_id": "SAP_MATERIAL_ID",
      "dimension_name": "SAP Material ID",
      "category": "system_id",
      "data_type": "VARCHAR(64)",
      "cardinality": "high",
      "examples": ["MAT-123456", "MAT-789012"],
      "required_for_identity": false,
      "required_for_projection": ["SAP"],
      "validation_rule": "MATCHES '^MAT-[0-9]{6}$' OR NULL",
      "validation_type": "format",
      "source_systems": ["sap"],
      "mutable": false
    },
    "ALL_SKUS_ID": {
      "dimension_id": "ALL_SKUS_ID",
      "dimension_name": "All SKUs ID",
      "category": "system_id",
      "data_type": "VARCHAR(64)",
      "cardinality": "high",
      "examples": ["SKU-ABC-DEF-001"],
      "required_for_identity": false,
      "required_for_projection": ["all_skus"],
      "validation_rule": "MATCHES '^SKU-[A-Z0-9-]+$' OR NULL",
      "validation_type": "format",
      "source_systems": ["all_skus"],
      "mutable": false
    },
    "CATALOG_ID": {
      "dimension_id": "CATALOG_ID",
      "dimension_name": "Catalog ID",
      "category": "system_id",
      "data_type": "VARCHAR(64)",
      "cardinality": "high",
      "examples": ["CAT-2026-001"],
      "required_for_identity": false,
      "required_for_projection": ["catalog"],
      "validation_rule": "MATCHES '^CAT-[0-9]{4}-[0-9]+$' OR NULL",
      "validation_type": "format",
      "source_systems": ["catalog"],
      "mutable": false
    }
  },

  "evidence_types": {
    "SAP_MATERIAL_EXPORT": {
      "evidence_type_id": "SAP_MATERIAL_EXPORT",
      "evidence_name": "SAP Material Master",
      "source_system": "sap",
      "provides_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_TIER", "D_GEOGRAPHY", "SAP_MATERIAL_ID"],
      "frequency": "nightly",
      "authority_precedence_rank": 2,
      "description": "Authoritative source for SAP material master data. Contains hierarchical product structure."
    },
    "ALL_SKUS_CATALOG": {
      "evidence_type_id": "ALL_SKUS_CATALOG",
      "evidence_name": "All SKUs Product Catalog",
      "source_system": "all_skus",
      "provides_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_SEGMENT", "D_TIER", "D_GEOGRAPHY", "ALL_SKUS_ID"],
      "frequency": "hourly",
      "authority_precedence_rank": 2,
      "description": "All SKUs system: master SKU repository for internal sales systems."
    },
    "WW_PRICING_FEED": {
      "evidence_type_id": "WW_PRICING_FEED",
      "evidence_name": "Worldwide Pricing Feed",
      "source_system": "ww_pricing",
      "provides_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_GEOGRAPHY", "D_PRICE_USD", "D_PRICING_TYPE", "D_CURRENCY"],
      "frequency": "on_demand",
      "authority_precedence_rank": 1,
      "description": "Pricing team's authoritative pricing feed. May reflect proposed prices before SAP update."
    },
    "SALESFORCE_ACCOUNTS": {
      "evidence_type_id": "SALESFORCE_ACCOUNTS",
      "evidence_name": "Salesforce Account/Opportunity Data",
      "source_system": "salesforce",
      "provides_dimensions": ["D_MARKET", "D_SEGMENT", "D_GEOGRAPHY"],
      "frequency": "sync",
      "authority_precedence_rank": 3,
      "description": "Customer segment and market data from Salesforce CRM."
    },
    "HUMAN_INPUT": {
      "evidence_type_id": "HUMAN_INPUT",
      "evidence_name": "Manual Configuration Input",
      "source_system": "human",
      "provides_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_TIER", "D_SEGMENT", "D_GEOGRAPHY", "D_MARKET", "D_PRICE_USD"],
      "frequency": "on_demand",
      "authority_precedence_rank": 4,
      "description": "User-submitted configuration data via spreadsheets or UI. Lowest precedence."
    }
  },

  "identity_rules": {
    "CLARIS_CANONICAL_IDENTITY": {
      "identity_rule_id": "CLARIS_CANONICAL_IDENTITY",
      "object_type": "configuration",
      "identity_name": "Canonical Business Identity",
      "required_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_TIER", "D_SEGMENT", "D_GEOGRAPHY", "D_MARKET"],
      "description": "Minimum dimensions needed to identify a unique sellable configuration in Claris.",
      "identity_hash_algorithm": "SHA256(CONCAT(D_PRODUCT_FAMILY, '|', D_OFFERING, '|', D_TIER, '|', D_SEGMENT, '|', D_GEOGRAPHY, '|', D_MARKET))",
      "use_cases": ["UC-01", "UC-02", "UC-03", "UC-05", "UC-06", "UC-08", "UC-20"]
    }
  },

  "projection_rules": {
    "SAP_MATERIAL_PROJECTION": {
      "projection_rule_id": "SAP_MATERIAL_PROJECTION",
      "target_system": "SAP",
      "source_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_TIER", "D_GEOGRAPHY", "SAP_MATERIAL_ID"],
      "optional_dimensions": ["D_PRICE_USD", "D_PRICING_TYPE"],
      "system_payload_template": {
        "material_id": "SAP_MATERIAL_ID",
        "material_type": "PRODUCT",
        "product_hierarchy": "CONCAT(D_PRODUCT_FAMILY, '|', D_OFFERING)",
        "pricing_segment": "CONCAT(D_TIER, '|', D_GEOGRAPHY)"
      },
      "requires_decision_type": "IDENTITY_ASSESSMENT",
      "requires_decision_outcome": "READY_FOR_LAUNCH",
      "description": "Maps canonical configuration to SAP material master.",
      "proliferation_classification": "BUSINESS_REQUIRED"
    },
    "ALL_SKUS_PROJECTION": {
      "projection_rule_id": "ALL_SKUS_PROJECTION",
      "target_system": "all_skus",
      "source_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_SEGMENT", "D_TIER", "D_GEOGRAPHY", "ALL_SKUS_ID"],
      "optional_dimensions": [],
      "system_payload_template": {
        "sku_id": "ALL_SKUS_ID",
        "product_name": "CONCAT(D_PRODUCT_FAMILY, ' ', D_OFFERING)",
        "segment": "D_SEGMENT",
        "tier": "D_TIER",
        "geography": "D_GEOGRAPHY"
      },
      "requires_decision_type": "IDENTITY_ASSESSMENT",
      "requires_decision_outcome": "READY_FOR_LAUNCH",
      "description": "Maps canonical configuration to All SKUs master.",
      "proliferation_classification": "BUSINESS_REQUIRED"
    },
    "WW_PRICING_PROJECTION": {
      "projection_rule_id": "WW_PRICING_PROJECTION",
      "target_system": "ww_pricing",
      "source_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_GEOGRAPHY", "D_PRICE_USD", "D_PRICING_TYPE", "D_CURRENCY"],
      "optional_dimensions": ["D_SEGMENT"],
      "system_payload_template": {
        "product_id": "CONCAT(D_PRODUCT_FAMILY, '-', D_OFFERING)",
        "price_usd": "D_PRICE_USD",
        "pricing_type": "D_PRICING_TYPE",
        "currency": "D_CURRENCY",
        "geography": "D_GEOGRAPHY",
        "effective_date": "TODAY()"
      },
      "requires_decision_type": "PRICING_READINESS",
      "requires_decision_outcome": "PRICING_COMPLETE",
      "description": "Maps canonical configuration to worldwide pricing feed.",
      "proliferation_classification": "BUSINESS_REQUIRED"
    },
    "SALESFORCE_PROJECTION": {
      "projection_rule_id": "SALESFORCE_PROJECTION",
      "target_system": "Salesforce",
      "source_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_MARKET", "D_SEGMENT", "D_GEOGRAPHY"],
      "optional_dimensions": ["D_PRICE_USD"],
      "system_payload_template": {
        "product_name": "CONCAT(D_PRODUCT_FAMILY, ' ', D_OFFERING)",
        "market": "D_MARKET",
        "segment": "D_SEGMENT",
        "region": "D_GEOGRAPHY"
      },
      "requires_decision_type": "LAUNCH_READINESS",
      "requires_decision_outcome": "READY_TO_LAUNCH",
      "description": "Maps canonical configuration to Salesforce product record.",
      "proliferation_classification": "BUSINESS_REQUIRED"
    }
  },

  "decision_types": {
    "IDENTITY_ASSESSMENT": {
      "decision_type": "IDENTITY_ASSESSMENT",
      "decision_name": "Configuration Identity Assessment",
      "use_cases": ["UC-08"],
      "description": "Does this configuration have sufficient identity dimensions established to be treated as a canonical business entity?",
      "required_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_TIER", "D_SEGMENT", "D_GEOGRAPHY", "D_MARKET"],
      "risk_tier": "elevated",
      "decision_made_by": ["system_identity_engine", "human:reviewer"],
      "valid_inputs": ["IDENTITY_ASSESSMENT"],
      "valid_outcomes": [
        "READY_FOR_LAUNCH",
        "MISSING_REQUIRED_DIMENSIONS",
        "CONTRADICTED_IDENTITY_EVIDENCE",
        "CANNOT_DECIDE"
      ]
    },
    "PRICING_READINESS": {
      "decision_type": "PRICING_READINESS",
      "decision_name": "Pricing Configuration Readiness",
      "use_cases": [],
      "description": "Is pricing complete, consistent, and compliant for this configuration? (Query/read-model UCs inspect this state but do not execute this decision.)",
      "required_dimensions": ["D_PRICE_USD", "D_PRICING_TYPE", "D_CURRENCY"],
      "risk_tier": "elevated",
      "decision_made_by": ["system_pricing_engine", "human:pricing_reviewer"],
      "valid_inputs": ["PRICING_READINESS"],
      "valid_outcomes": [
        "PRICING_COMPLETE",
        "MISSING_PRICING",
        "PRICE_CONFLICT",
        "COMPLIANCE_ISSUE",
        "CANNOT_DECIDE"
      ]
    },
    "LAUNCH_READINESS": {
      "decision_type": "LAUNCH_READINESS",
      "decision_name": "Product Launch Readiness",
      "use_cases": ["UC-01", "UC-03", "UC-20"],
      "description": "Is this configuration ready to be projected into target systems and made available to customers?",
      "required_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_TIER", "D_SEGMENT", "D_GEOGRAPHY", "D_MARKET", "D_PRICE_USD"],
      "risk_tier": "elevated",
      "decision_made_by": ["human:approver_elevated"],
      "valid_inputs": ["IDENTITY_ASSESSMENT", "PRICING_READINESS"],
      "valid_outcomes": [
        "READY_TO_LAUNCH",
        "BLOCKED_MISSING_EVIDENCE",
        "BLOCKED_IDENTITY_CONFLICT",
        "BLOCKED_PRICING_ISSUE"
      ]
    },
    "LAUNCH_VIABILITY": {
      "decision_type": "LAUNCH_VIABILITY",
      "decision_name": "Launch Viability Assessment",
      "use_cases": ["UC-06"],
      "description": "Is this configuration viable to launch given current market conditions, competitive landscape, and internal constraints?",
      "required_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "D_SEGMENT", "D_GEOGRAPHY", "D_MARKET"],
      "risk_tier": "executive",
      "decision_made_by": ["human:approver_executive"],
      "valid_inputs": ["LAUNCH_READINESS"],
      "valid_outcomes": [
        "VIABLE_FOR_LAUNCH",
        "NOT_VIABLE_MARKET_CONDITIONS",
        "NOT_VIABLE_COMPETITIVE",
        "DEFER_PENDING_CONSTRAINT",
        "CANNOT_ASSESS"
      ]
    },
    "CHANGE_CLASSIFICATION": {
      "decision_type": "CHANGE_CLASSIFICATION",
      "decision_name": "Configuration Change Classification",
      "use_cases": ["UC-07"],
      "description": "What class of change is this configuration update? (Breaking, non-breaking, minor refinement?) What governance applies?",
      "required_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING"],
      "risk_tier": "elevated",
      "decision_made_by": ["system_change_engine", "human:approver_elevated"],
      "valid_inputs": ["IDENTITY_ASSESSMENT"],
      "valid_outcomes": [
        "BREAKING_CHANGE_REQUIRES_APPROVAL",
        "NON_BREAKING_CHANGE_AUTO_APPROVED",
        "MINOR_REFINEMENT_TRACKED",
        "CANNOT_CLASSIFY"
      ]
    },
    "LEGACY_PROJECTION_REQUIREMENT": {
      "decision_type": "LEGACY_PROJECTION_REQUIREMENT",
      "decision_name": "Legacy System Projection Requirement",
      "use_cases": ["UC-09"],
      "description": "Must this configuration be projected into legacy systems, or can it remain canonical-only? What legacy system constraints apply?",
      "required_dimensions": ["D_PRODUCT_FAMILY", "D_OFFERING", "SAP_MATERIAL_ID"],
      "risk_tier": "elevated",
      "decision_made_by": ["system_legacy_engine", "human:approver_elevated"],
      "valid_inputs": ["IDENTITY_ASSESSMENT"],
      "valid_outcomes": [
        "REQUIRES_LEGACY_PROJECTION",
        "CANONICAL_ONLY",
        "PHASED_LEGACY_SUNSET",
        "CANNOT_DETERMINE"
      ]
    }
  },

  "decision_inputs": {
    "IDENTITY_ASSESSMENT.input_evidence_type": {
      "decision_type": "IDENTITY_ASSESSMENT",
      "input_name": "Identity Evidence Type",
      "input_role": "evidence",
      "required_evidence_types": ["SAP_MATERIAL_EXPORT", "ALL_SKUS_CATALOG", "HUMAN_INPUT"],
      "description": "At least one of SAP, All_SKUs, or human input must report each required identity dimension."
    },
    "PRICING_READINESS.input_pricing_evidence": {
      "decision_type": "PRICING_READINESS",
      "input_name": "Pricing Evidence",
      "input_role": "evidence",
      "required_evidence_types": ["WW_PRICING_FEED"],
      "description": "Pricing dimensions must come from pricing feed or human input."
    },
    "LAUNCH_READINESS.input_prior_decisions": {
      "decision_type": "LAUNCH_READINESS",
      "input_name": "Prior Decisions",
      "input_role": "dependency",
      "required_prior_decisions": ["IDENTITY_ASSESSMENT", "PRICING_READINESS"],
      "required_prior_outcomes": ["READY_FOR_LAUNCH", "PRICING_COMPLETE"],
      "description": "Identity and pricing assessments must both be READY before launch readiness can be evaluated."
    },
    "LAUNCH_VIABILITY.input_launch_readiness": {
      "decision_type": "LAUNCH_VIABILITY",
      "input_name": "Launch Readiness Gate",
      "input_role": "dependency",
      "required_prior_decisions": ["LAUNCH_READINESS"],
      "required_prior_outcomes": ["READY_TO_LAUNCH"],
      "description": "Configuration must pass launch readiness before viability can be assessed."
    },
    "CHANGE_CLASSIFICATION.input_identity": {
      "decision_type": "CHANGE_CLASSIFICATION",
      "input_name": "Identity Assessment",
      "input_role": "dependency",
      "required_prior_decisions": ["IDENTITY_ASSESSMENT"],
      "required_prior_outcomes": ["READY_FOR_LAUNCH"],
      "description": "Current identity must be valid before change classification can occur."
    },
    "LEGACY_PROJECTION_REQUIREMENT.input_identity": {
      "decision_type": "LEGACY_PROJECTION_REQUIREMENT",
      "input_name": "Identity Assessment",
      "input_role": "dependency",
      "required_prior_decisions": ["IDENTITY_ASSESSMENT"],
      "required_prior_outcomes": ["READY_FOR_LAUNCH"],
      "description": "Configuration identity must be valid before legacy projection requirements can be determined."
    }
  },

  "decision_outputs": {
    "IDENTITY_ASSESSMENT.READY_FOR_LAUNCH": {
      "decision_type": "IDENTITY_ASSESSMENT",
      "outcome_code": "READY_FOR_LAUNCH",
      "outcome_name": "Configuration Ready for Identity",
      "actions_allowed": ["UPDATE_SAP_MATERIAL_PRICE", "PUBLISH_TO_CATALOG", "REQUEST_EVIDENCE"],
      "risk_tier_requires": "elevated",
      "description": "Configuration has all required identity dimensions established with no conflicts. Canonical identity is valid."
    },
    "IDENTITY_ASSESSMENT.MISSING_REQUIRED_DIMENSIONS": {
      "decision_type": "IDENTITY_ASSESSMENT",
      "outcome_code": "MISSING_REQUIRED_DIMENSIONS",
      "outcome_name": "Missing Required Identity Dimensions",
      "actions_allowed": ["REQUEST_EVIDENCE"],
      "risk_tier_requires": "routine",
      "description": "Configuration is missing one or more required identity dimensions. Cannot proceed until evidence is gathered."
    },
    "IDENTITY_ASSESSMENT.CONTRADICTED_IDENTITY_EVIDENCE": {
      "decision_type": "IDENTITY_ASSESSMENT",
      "outcome_code": "CONTRADICTED_IDENTITY_EVIDENCE",
      "outcome_name": "Contradicted Identity Evidence",
      "actions_allowed": ["INVESTIGATE_CONTRADICTION", "REQUEST_EVIDENCE"],
      "risk_tier_requires": "elevated",
      "description": "Multiple sources report different values for an identity dimension. Human judgment required."
    },
    "PRICING_READINESS.PRICING_COMPLETE": {
      "decision_type": "PRICING_READINESS",
      "outcome_code": "PRICING_COMPLETE",
      "outcome_name": "Pricing is Complete and Consistent",
      "actions_allowed": ["ACTIVATE_PRICING", "PUBLISH_TO_CATALOG"],
      "risk_tier_requires": "elevated",
      "description": "All pricing dimensions established. Price is consistent across sources or manually resolved."
    },
    "PRICING_READINESS.PRICE_CONFLICT": {
      "decision_type": "PRICING_READINESS",
      "outcome_code": "PRICE_CONFLICT",
      "outcome_name": "Price Conflict Detected",
      "actions_allowed": ["INVESTIGATE_CONTRADICTION"],
      "risk_tier_requires": "elevated",
      "description": "Multiple sources report different prices. Requires human judgment or KB governance rule to resolve."
    },
    "LAUNCH_READINESS.READY_TO_LAUNCH": {
      "decision_type": "LAUNCH_READINESS",
      "outcome_code": "READY_TO_LAUNCH",
      "outcome_name": "Configuration Ready for System Projection",
      "actions_allowed": ["CREATE_PRODUCT_IN_SAP", "PUBLISH_TO_CATALOG", "ACTIVATE_PRICING"],
      "risk_tier_requires": "elevated",
      "description": "Configuration has passed all readiness gates. Ready to project into target systems."
    },
    "LAUNCH_VIABILITY.VIABLE_FOR_LAUNCH": {
      "decision_type": "LAUNCH_VIABILITY",
      "outcome_code": "VIABLE_FOR_LAUNCH",
      "outcome_name": "Configuration is Viable for Launch",
      "actions_allowed": ["CREATE_PRODUCT_IN_SAP", "PUBLISH_TO_CATALOG", "ACTIVATE_PRICING"],
      "risk_tier_requires": "executive",
      "description": "Configuration is viable under current market, competitive, and internal conditions."
    },
    "LAUNCH_VIABILITY.NOT_VIABLE_MARKET_CONDITIONS": {
      "decision_type": "LAUNCH_VIABILITY",
      "outcome_code": "NOT_VIABLE_MARKET_CONDITIONS",
      "outcome_name": "Not Viable: Market Conditions",
      "actions_allowed": ["REQUEST_EVIDENCE"],
      "risk_tier_requires": "executive",
      "description": "Market conditions do not support launch at this time."
    },
    "CHANGE_CLASSIFICATION.BREAKING_CHANGE_REQUIRES_APPROVAL": {
      "decision_type": "CHANGE_CLASSIFICATION",
      "outcome_code": "BREAKING_CHANGE_REQUIRES_APPROVAL",
      "outcome_name": "Breaking Change: Requires Executive Approval",
      "actions_allowed": [],
      "risk_tier_requires": "executive",
      "description": "Change breaks backward compatibility or affects customer contracts. Executive approval required."
    },
    "CHANGE_CLASSIFICATION.NON_BREAKING_CHANGE_AUTO_APPROVED": {
      "decision_type": "CHANGE_CLASSIFICATION",
      "outcome_code": "NON_BREAKING_CHANGE_AUTO_APPROVED",
      "outcome_name": "Non-Breaking Change: Auto-Approved",
      "actions_allowed": ["PUBLISH_TO_CATALOG"],
      "risk_tier_requires": "routine",
      "description": "Change is backward compatible. Automatically approved."
    },
    "LEGACY_PROJECTION_REQUIREMENT.REQUIRES_LEGACY_PROJECTION": {
      "decision_type": "LEGACY_PROJECTION_REQUIREMENT",
      "outcome_code": "REQUIRES_LEGACY_PROJECTION",
      "outcome_name": "Configuration Requires Legacy System Projection",
      "actions_allowed": ["CREATE_PRODUCT_IN_SAP"],
      "risk_tier_requires": "elevated",
      "description": "Configuration must be projected into legacy systems due to business or data-retention requirements."
    },
    "LEGACY_PROJECTION_REQUIREMENT.CANONICAL_ONLY": {
      "decision_type": "LEGACY_PROJECTION_REQUIREMENT",
      "outcome_code": "CANONICAL_ONLY",
      "outcome_name": "Canonical-Only: No Legacy Projection Required",
      "actions_allowed": [],
      "risk_tier_requires": "routine",
      "description": "Configuration remains in canonical layer only. No legacy system synchronization needed."
    }
  },

  "action_types": {
    "CREATE_PRODUCT_IN_SAP": {
      "action_type_id": "CREATE_PRODUCT_IN_SAP",
      "action_name": "Create Product in SAP",
      "description": "Create a new material master record in SAP from the approved canonical configuration.",
      "system_target": "SAP",
      "risk_tier": "elevated",
      "requires_decision_type": "IDENTITY_ASSESSMENT",
      "requires_decision_outcome": "READY_FOR_LAUNCH",
      "payload_schema": {
        "sap_material_id": "VARCHAR(64)",
        "material_type": "VARCHAR(32)",
        "product_family": "VARCHAR(64)",
        "offering": "VARCHAR(64)",
        "tier": "VARCHAR(32)",
        "geography": "VARCHAR(2)"
      }
    },
    "PUBLISH_TO_CATALOG": {
      "action_type_id": "PUBLISH_TO_CATALOG",
      "action_name": "Publish to Catalog",
      "description": "Publish canonical configuration to product catalog systems (All_SKUs, internal catalog).",
      "system_target": "all_skus",
      "risk_tier": "elevated",
      "requires_decision_type": "IDENTITY_ASSESSMENT",
      "requires_decision_outcome": "READY_FOR_LAUNCH",
      "payload_schema": {
        "sku_id": "VARCHAR(64)",
        "product_name": "VARCHAR(256)",
        "segment": "VARCHAR(32)",
        "geography": "VARCHAR(2)"
      }
    },
    "ACTIVATE_PRICING": {
      "action_type_id": "ACTIVATE_PRICING",
      "action_name": "Activate Pricing",
      "description": "Publish approved pricing to external pricing systems and Salesforce.",
      "system_target": "ww_pricing, Salesforce",
      "risk_tier": "elevated",
      "requires_decision_type": "PRICING_READINESS",
      "requires_decision_outcome": "PRICING_COMPLETE",
      "payload_schema": {
        "product_id": "VARCHAR(128)",
        "price_usd": "NUMERIC(10,2)",
        "pricing_type": "VARCHAR(32)",
        "effective_date": "DATE"
      }
    },
    "REQUEST_EVIDENCE": {
      "action_type_id": "REQUEST_EVIDENCE",
      "action_name": "Request Missing Evidence",
      "description": "Notify evidence collectors to gather missing dimensions or resolve contradictions.",
      "system_target": "internal_workflow",
      "risk_tier": "routine",
      "requires_decision_type": null,
      "requires_decision_outcome": null,
      "payload_schema": {
        "missing_dimension": "VARCHAR(64)",
        "requested_from_systems": "VARCHAR[]",
        "deadline": "DATE"
      }
    },
    "INVESTIGATE_CONTRADICTION": {
      "action_type_id": "INVESTIGATE_CONTRADICTION",
      "action_name": "Investigate Contradiction",
      "description": "Human review task to investigate conflicting evidence and determine correct value.",
      "system_target": "internal_workflow",
      "risk_tier": "elevated",
      "requires_decision_type": null,
      "requires_decision_outcome": null,
      "payload_schema": {
        "dimension_id": "VARCHAR(64)",
        "conflicting_values": "VARCHAR[]",
        "conflicting_sources": "VARCHAR[]"
      }
    }
  },

  "action_authorizations": {
    "CREATE_PRODUCT_IN_SAP.routine": {
      "action_type": "CREATE_PRODUCT_IN_SAP",
      "authorization_level": "routine",
      "approval_required": false,
      "description": "Routine product creation (e.g., new region, existing tier). No approval required."
    },
    "CREATE_PRODUCT_IN_SAP.elevated": {
      "action_type": "CREATE_PRODUCT_IN_SAP",
      "authorization_level": "elevated",
      "approval_required": true,
      "description": "Elevated product creation (e.g., new tier, new product family). Requires elevated approval."
    },
    "ACTIVATE_PRICING.elevated": {
      "action_type": "ACTIVATE_PRICING",
      "authorization_level": "elevated",
      "approval_required": true,
      "description": "Price changes always require elevated approval."
    },
    "INVESTIGATE_CONTRADICTION.routine": {
      "action_type": "INVESTIGATE_CONTRADICTION",
      "authorization_level": "routine",
      "approval_required": false,
      "description": "Investigation requests require no approval; they route to relevant teams."
    }
  },

  "roles": {
    "reviewer": {
      "role_id": "reviewer",
      "role_name": "Configuration Reviewer",
      "description": "Reviews configurations and evidence. Can propose decisions. Cannot approve actions.",
      "permissions": ["read_assigned_configurations", "propose_decision", "comment_on_evidence"],
      "escalation_tier": "routine",
      "data_classification_read": ["public", "internal"]
    },
    "approver_routine": {
      "role_id": "approver_routine",
      "role_name": "Routine Approver",
      "description": "Approves routine-tier actions (new SKU regions, standard pricing).",
      "permissions": ["read_all_configurations", "approve_action_routine", "execute_action_routine"],
      "escalation_tier": "routine",
      "data_classification_read": ["public", "internal", "confidential"]
    },
    "approver_elevated": {
      "role_id": "approver_elevated",
      "role_name": "Elevated Approver",
      "description": "Approves elevated-tier actions (new tiers, price changes, launch decisions).",
      "permissions": ["read_all_configurations", "approve_action_elevated", "execute_action_elevated"],
      "escalation_tier": "elevated",
      "data_classification_read": ["public", "internal", "confidential", "restricted"]
    },
    "approver_executive": {
      "role_id": "approver_executive",
      "role_name": "Executive Approver",
      "description": "Approves executive-tier actions (portfolio decisions, strategic pricing, market entry).",
      "permissions": ["read_all_configurations", "approve_action_executive", "execute_action_executive"],
      "escalation_tier": "executive",
      "data_classification_read": ["public", "internal", "confidential", "restricted", "executive"]
    },
    "executor": {
      "role_id": "executor",
      "role_name": "System Executor",
      "description": "Executes approved actions. Can be a system service account or human operator.",
      "permissions": ["execute_approved_actions", "read_execution_logs"],
      "escalation_tier": null,
      "data_classification_read": ["public", "internal"]
    },
    "auditor": {
      "role_id": "auditor",
      "role_name": "Auditor",
      "description": "Read-only access to all decision and execution logs for compliance auditing.",
      "permissions": ["read_all_configurations_history", "read_all_decisions", "read_all_executions"],
      "escalation_tier": null,
      "data_classification_read": ["public", "internal", "confidential", "restricted", "executive"]
    }
  },

  "read_grants": {
    "reviewer_assigned_configurations": {
      "read_grant_id": "reviewer_assigned_configurations",
      "role": "reviewer",
      "resource_type": "configuration",
      "access_pattern": "ASSIGNED",
      "description": "Reviewers can read only configurations assigned to them."
    },
    "approver_all_configurations": {
      "read_grant_id": "approver_all_configurations",
      "role": "approver_routine",
      "resource_type": "configuration",
      "access_pattern": "ALL",
      "description": "Approvers can read all configurations in their tier."
    },
    "executor_approved_actions_only": {
      "read_grant_id": "executor_approved_actions_only",
      "role": "executor",
      "resource_type": "action_record",
      "access_pattern": "APPROVED",
      "description": "Executors can only read actions that have been approved."
    },
    "auditor_all_history": {
      "read_grant_id": "auditor_all_history",
      "role": "auditor",
      "resource_type": ["decision", "action_record", "approval_record", "execution_record"],
      "access_pattern": "ALL_HISTORY",
      "description": "Auditors have read-only access to all history."
    }
  },

  "use_cases": {
    "UC-01": {
      "use_case_id": "UC-01",
      "use_case_title": "Launch Status & Missing Evidence",
      "classification": "DECISION_EXECUTION",
      "description": "Assess whether a new configuration has sufficient evidence and readiness to launch into target systems.",
      "involved_decision_types": ["LAUNCH_READINESS"],
      "involved_action_types": ["CREATE_PRODUCT_IN_SAP", "PUBLISH_TO_CATALOG", "ACTIVATE_PRICING"],
      "required_roles": ["reviewer", "approver_elevated"],
      "typical_duration_days": 5
    },
    "UC-02": {
      "use_case_id": "UC-02",
      "use_case_title": "Ownership & Aging",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Which configurations are owned by which teams, and how old is the evidence supporting each dimension?",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["reviewer", "approver_routine"],
      "typical_duration_days": 1
    },
    "UC-03": {
      "use_case_id": "UC-03",
      "use_case_title": "Activation Authorization",
      "classification": "DECISION_EXECUTION",
      "description": "Approve and authorize activation of a configuration into production systems.",
      "involved_decision_types": ["LAUNCH_READINESS"],
      "involved_action_types": ["ACTIVATE_PRICING", "PUBLISH_TO_CATALOG"],
      "required_roles": ["approver_elevated"],
      "typical_duration_days": 2
    },
    "UC-04": {
      "use_case_id": "UC-04",
      "use_case_title": "Cross-System Contradiction",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Which configurations have contradictory evidence across different source systems?",
      "involved_decision_types": [],
      "involved_action_types": ["INVESTIGATE_CONTRADICTION"],
      "required_roles": ["reviewer", "auditor"],
      "typical_duration_days": 3
    },
    "UC-05": {
      "use_case_id": "UC-05",
      "use_case_title": "Rejected vs Never Answered",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Distinguish configurations with explicit rejections from those that were never submitted for decision.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["reviewer", "auditor"],
      "typical_duration_days": 2
    },
    "UC-06": {
      "use_case_id": "UC-06",
      "use_case_title": "Launch Viability",
      "classification": "DECISION_EXECUTION",
      "description": "Assess whether a configuration that passed launch readiness is viable given market conditions and competitive landscape.",
      "involved_decision_types": ["LAUNCH_VIABILITY"],
      "involved_action_types": [],
      "required_roles": ["approver_executive"],
      "typical_duration_days": 7
    },
    "UC-07": {
      "use_case_id": "UC-07",
      "use_case_title": "Change Classification",
      "classification": "DECISION_EXECUTION",
      "description": "Classify a configuration change as breaking, non-breaking, or minor refinement to determine governance pathway.",
      "involved_decision_types": ["CHANGE_CLASSIFICATION"],
      "involved_action_types": [],
      "required_roles": ["approver_elevated"],
      "typical_duration_days": 3
    },
    "UC-08": {
      "use_case_id": "UC-08",
      "use_case_title": "Identity Assessment",
      "classification": "DECISION_EXECUTION",
      "description": "Assess whether a configuration has sufficient identity dimensions to be treated as a canonical business object.",
      "involved_decision_types": ["IDENTITY_ASSESSMENT"],
      "involved_action_types": ["REQUEST_EVIDENCE"],
      "required_roles": ["reviewer"],
      "typical_duration_days": 3
    },
    "UC-09": {
      "use_case_id": "UC-09",
      "use_case_title": "Legacy Projection Requirement",
      "classification": "DECISION_EXECUTION",
      "description": "Determine whether a canonical configuration must be projected into legacy systems or can remain canonical-only.",
      "involved_decision_types": ["LEGACY_PROJECTION_REQUIREMENT"],
      "involved_action_types": [],
      "required_roles": ["approver_elevated"],
      "typical_duration_days": 4
    },
    "UC-10": {
      "use_case_id": "UC-10",
      "use_case_title": "Proliferation Measurement",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Analyze SKU proliferation; distinguish business-required multiplicity from legacy system constraints.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["reviewer", "auditor"],
      "typical_duration_days": 5
    },
    "UC-11": {
      "use_case_id": "UC-11",
      "use_case_title": "Identity-Rule Simulation",
      "classification": "SIMULATION",
      "description": "Simulation: What would happen if we changed identity composition rules? Show impact on current configurations.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["reviewer", "approver_elevated"],
      "typical_duration_days": 2
    },
    "UC-12": {
      "use_case_id": "UC-12",
      "use_case_title": "Governance Blocker",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Which configurations are blocked by governance rules or missing approvals?",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["approver_elevated", "auditor"],
      "typical_duration_days": 1
    },
    "UC-13": {
      "use_case_id": "UC-13",
      "use_case_title": "Decision Replay",
      "classification": "GOVERNANCE_AUDIT",
      "description": "Audit: Replay a past decision with historical KB version and evidence to verify reasoning and outcomes.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["auditor"],
      "typical_duration_days": 3
    },
    "UC-14": {
      "use_case_id": "UC-14",
      "use_case_title": "Separation of Duties",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Verify separation of duties across configuration authorship, approval, and execution.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["auditor"],
      "typical_duration_days": 2
    },
    "UC-15": {
      "use_case_id": "UC-15",
      "use_case_title": "Open Governance Decisions",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Which decisions are still open and awaiting evidence or approval?",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["reviewer", "approver_elevated"],
      "typical_duration_days": 1
    },
    "UC-16": {
      "use_case_id": "UC-16",
      "use_case_title": "Ontology/Policy Drift",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Detect configurations or decisions that violate current ontology or policy rules.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["auditor", "approver_elevated"],
      "typical_duration_days": 3
    },
    "UC-17": {
      "use_case_id": "UC-17",
      "use_case_title": "Change Impact Assessment",
      "classification": "SIMULATION",
      "description": "Simulation: What would be the impact on configurations and target systems if we changed pricing rules or identity rules?",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["approver_elevated"],
      "typical_duration_days": 4
    },
    "UC-18": {
      "use_case_id": "UC-18",
      "use_case_title": "Duplicate Configuration Prevention",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Detect configurations that have the same identity but exist as separate records.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["reviewer", "auditor"],
      "typical_duration_days": 2
    },
    "UC-19": {
      "use_case_id": "UC-19",
      "use_case_title": "Projection Preview",
      "classification": "SIMULATION",
      "description": "Simulation: Preview what a configuration would look like if projected into each target system.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["reviewer", "approver_elevated"],
      "typical_duration_days": 2
    },
    "UC-20": {
      "use_case_id": "UC-20",
      "use_case_title": "Overall Launch Readiness",
      "classification": "DECISION_EXECUTION",
      "description": "Aggregate launch readiness assessment across a portfolio of configurations.",
      "involved_decision_types": ["LAUNCH_READINESS"],
      "involved_action_types": [],
      "required_roles": ["approver_elevated"],
      "typical_duration_days": 5
    },
    "UC-21": {
      "use_case_id": "UC-21",
      "use_case_title": "Portfolio Bottleneck",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Identify bottlenecks preventing configurations from reaching target systems.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["approver_elevated", "auditor"],
      "typical_duration_days": 3
    },
    "UC-22": {
      "use_case_id": "UC-22",
      "use_case_title": "Legacy Dependency Analysis",
      "classification": "QUERY_READ_MODEL",
      "description": "Query: Analyze which configurations are locked into legacy systems and identify consolidation candidates.",
      "involved_decision_types": [],
      "involved_action_types": [],
      "required_roles": ["approver_elevated", "auditor"],
      "typical_duration_days": 7
    }
  }
}
$KB_JSON$::jsonb)
ON CONFLICT (kb_version) DO UPDATE SET
  kb_data = EXCLUDED.kb_data,
  loaded_at = NOW();

-- ============================================================================
-- VALIDATION FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION ontology.validate_kb_json(kb_json JSONB)
RETURNS TABLE (is_valid BOOLEAN, error_message TEXT) AS $$
DECLARE
  v_kb_version TEXT;
  v_missing_sections TEXT[] := ARRAY[]::TEXT[];
BEGIN
  FOREACH v_kb_version IN ARRAY ARRAY[
    'kb_metadata', 'objects', 'dimensions', 'evidence_types', 'decision_types',
    'decision_inputs', 'decision_outputs', 'identity_rules', 'projection_rules',
    'action_types', 'action_authorizations', 'roles', 'read_grants', 'use_cases'
  ] LOOP
    IF NOT (kb_json ? v_kb_version) THEN
      v_missing_sections := v_missing_sections || v_kb_version;
    END IF;
  END LOOP;
  IF array_length(v_missing_sections, 1) > 0 THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 'Missing required KB sections: ' || array_to_string(v_missing_sections, ', ');
    RETURN;
  END IF;
  IF NOT (kb_json->'kb_metadata' ? 'kb_version') THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 'kb_metadata.kb_version is required';
    RETURN;
  END IF;
  IF NOT (kb_json->'kb_metadata' ? 'policy_version') THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 'kb_metadata.policy_version is required';
    RETURN;
  END IF;
  IF NOT (kb_json->'kb_metadata' ? 'effective_from') THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 'kb_metadata.effective_from is required';
    RETURN;
  END IF;
  IF (kb_json->'dimensions')::jsonb = '{}'::jsonb THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 'dimensions section is empty';
    RETURN;
  END IF;
  IF (kb_json->'decision_types')::jsonb = '{}'::jsonb THEN
    RETURN QUERY SELECT FALSE::BOOLEAN, 'decision_types section is empty';
    RETURN;
  END IF;
  RETURN QUERY SELECT TRUE::BOOLEAN, NULL::TEXT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- ALL 12 LOADER FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION ontology.load_kb_dimensions(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_dim_id VARCHAR; v_dimension JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_dim_id, v_dimension IN SELECT key, value FROM jsonb_each(kb_json->'dimensions') LOOP
    INSERT INTO ontology.configuration_dimensions (dimension_id, dimension_name, category, data_type, cardinality, examples, required_for_identity, required_for_projection, validation_rule, validation_type, source_systems, mutable, kb_version, effective_from, created_by) VALUES (v_dimension->>'dimension_id', v_dimension->>'dimension_name', v_dimension->>'category', v_dimension->>'data_type', v_dimension->>'cardinality', v_dimension->'examples'::text, (v_dimension->>'required_for_identity')::BOOLEAN, v_dimension->'required_for_projection'::text, v_dimension->>'validation_rule', v_dimension->>'validation_type', v_dimension->'source_systems'::text, COALESCE((v_dimension->>'mutable')::BOOLEAN, TRUE), v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (dimension_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_evidence_types(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_et_id VARCHAR; v_evidence_type JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_et_id, v_evidence_type IN SELECT key, value FROM jsonb_each(kb_json->'evidence_types') LOOP
    INSERT INTO ontology.evidence_types (evidence_type_id, evidence_name, source_system, provides_dimensions, frequency, authority_precedence_rank, description, kb_version, effective_from, created_by) VALUES (v_evidence_type->>'evidence_type_id', v_evidence_type->>'evidence_name', v_evidence_type->>'source_system', v_evidence_type->'provides_dimensions'::text, v_evidence_type->>'frequency', (v_evidence_type->>'authority_precedence_rank')::INT, v_evidence_type->>'description', v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (evidence_type_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_decisions(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_decision_type VARCHAR; v_decision JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_decision_type, v_decision IN SELECT key, value FROM jsonb_each(kb_json->'decision_types') LOOP
    INSERT INTO ontology.decisions (decision_type, decision_name, use_cases, description, required_dimensions, risk_tier, decision_made_by, valid_inputs, valid_outcomes, kb_version, effective_from, created_by) VALUES (v_decision->>'decision_type', v_decision->>'decision_name', v_decision->'use_cases'::text, v_decision->>'description', v_decision->'required_dimensions'::text, v_decision->>'risk_tier', v_decision->'decision_made_by'::text, v_decision->'valid_inputs'::text, v_decision->'valid_outcomes'::text, v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (decision_type) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_decision_inputs(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_di_id VARCHAR; v_decision_input JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_di_id, v_decision_input IN SELECT key, value FROM jsonb_each(kb_json->'decision_inputs') LOOP
    INSERT INTO ontology.decision_inputs (decision_input_id, decision_type, input_name, input_role, required_evidence_types, required_prior_decisions, required_prior_outcomes, description, kb_version, effective_from, created_by) VALUES (v_di_id, v_decision_input->>'decision_type', v_decision_input->>'input_name', v_decision_input->>'input_role', v_decision_input->'required_evidence_types'::text, v_decision_input->'required_prior_decisions'::text, v_decision_input->'required_prior_outcomes'::text, v_decision_input->>'description', v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (decision_input_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_decision_outputs(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, policy_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_policy_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_do_id VARCHAR; v_decision_output JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_policy_version := COALESCE(policy_version, kb_json->'kb_metadata'->>'policy_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_do_id, v_decision_output IN SELECT key, value FROM jsonb_each(kb_json->'decision_outputs') LOOP
    INSERT INTO ontology.decision_outputs (decision_output_id, decision_type, outcome_code, outcome_name, actions_allowed, risk_tier_requires, description, kb_version, policy_version, effective_from, created_by) VALUES (v_do_id, v_decision_output->>'decision_type', v_decision_output->>'outcome_code', v_decision_output->>'outcome_name', v_decision_output->'actions_allowed'::text, v_decision_output->>'risk_tier_requires', v_decision_output->>'description', v_kb_version, v_policy_version, v_release_timestamp, p_created_by) ON CONFLICT (decision_output_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_identity_rules(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_ir_id VARCHAR; v_identity_rule JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_ir_id, v_identity_rule IN SELECT key, value FROM jsonb_each(kb_json->'identity_rules') LOOP
    INSERT INTO ontology.identity_rules (identity_rule_id, object_type, identity_name, required_dimensions, description, identity_hash_algorithm, use_cases, kb_version, effective_from, created_by) VALUES (v_ir_id, v_identity_rule->>'object_type', v_identity_rule->>'identity_name', v_identity_rule->'required_dimensions'::text, v_identity_rule->>'description', v_identity_rule->>'identity_hash_algorithm', v_identity_rule->'use_cases'::text, v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (identity_rule_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_projection_rules(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_pr_id VARCHAR; v_projection_rule JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_pr_id, v_projection_rule IN SELECT key, value FROM jsonb_each(kb_json->'projection_rules') LOOP
    INSERT INTO ontology.projection_rules (projection_rule_id, target_system, source_dimensions, optional_dimensions, system_payload_template, requires_decision_type, requires_decision_outcome, description, proliferation_classification, kb_version, effective_from, created_by) VALUES (v_pr_id, v_projection_rule->>'target_system', v_projection_rule->'source_dimensions'::text, v_projection_rule->'optional_dimensions'::text, v_projection_rule->'system_payload_template'::text, v_projection_rule->>'requires_decision_type', v_projection_rule->>'requires_decision_outcome', v_projection_rule->>'description', v_projection_rule->>'proliferation_classification', v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (projection_rule_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_action_types(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_at_id VARCHAR; v_action_type JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_at_id, v_action_type IN SELECT key, value FROM jsonb_each(kb_json->'action_types') LOOP
    INSERT INTO ontology.action_types (action_type_id, action_name, description, system_target, risk_tier, requires_decision_type, requires_decision_outcome, payload_schema, kb_version, effective_from, created_by) VALUES (v_at_id, v_action_type->>'action_name', v_action_type->>'description', v_action_type->>'system_target', v_action_type->>'risk_tier', v_action_type->>'requires_decision_type', v_action_type->>'requires_decision_outcome', v_action_type->'payload_schema'::text, v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (action_type_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_action_authorizations(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_aa_id VARCHAR; v_action_auth JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_aa_id, v_action_auth IN SELECT key, value FROM jsonb_each(kb_json->'action_authorizations') LOOP
    INSERT INTO ontology.action_authorizations (action_authorization_id, action_type, authorization_level, approval_required, description, kb_version, effective_from, created_by) VALUES (v_aa_id, v_action_auth->>'action_type', v_action_auth->>'authorization_level', (v_action_auth->>'approval_required')::BOOLEAN, v_action_auth->>'description', v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (action_authorization_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_roles(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_role_id VARCHAR; v_role JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_role_id, v_role IN SELECT key, value FROM jsonb_each(kb_json->'roles') LOOP
    INSERT INTO ontology.roles (role_id, role_name, description, permissions, escalation_tier, data_classification_read, kb_version, effective_from, created_by) VALUES (v_role->>'role_id', v_role->>'role_name', v_role->>'description', v_role->'permissions'::text, v_role->>'escalation_tier', v_role->'data_classification_read'::text, v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (role_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_read_grants(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_rg_id VARCHAR; v_read_grant JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_rg_id, v_read_grant IN SELECT key, value FROM jsonb_each(kb_json->'read_grants') LOOP
    INSERT INTO ontology.read_grants (read_grant_id, role_id, resource_type, access_pattern, description, kb_version, effective_from, created_by) VALUES (v_rg_id, v_read_grant->>'role_id', v_read_grant->'resource_type'::text, v_read_grant->>'access_pattern', v_read_grant->>'description', v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (read_grant_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ontology.load_kb_use_cases(kb_json JSONB, p_kb_version VARCHAR DEFAULT NULL, p_release_timestamp TIMESTAMPTZ DEFAULT NULL, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS INT AS $$
DECLARE v_kb_version VARCHAR; v_release_timestamp TIMESTAMPTZ; v_uc_id VARCHAR; v_use_case JSONB; v_inserted INT := 0;
BEGIN
  v_kb_version := COALESCE(p_kb_version, kb_json->'kb_metadata'->>'kb_version');
  v_release_timestamp := COALESCE(p_release_timestamp, NOW());
  FOR v_uc_id, v_use_case IN SELECT key, value FROM jsonb_each(kb_json->'use_cases') LOOP
    INSERT INTO ontology.use_cases (use_case_id, use_case_title, description, involved_decision_types, involved_action_types, required_roles, typical_duration_days, documents_created, output, kb_version, effective_from, created_by) VALUES (v_use_case->>'use_case_id', v_use_case->>'use_case_title', v_use_case->>'description', v_use_case->'involved_decision_types'::text, v_use_case->'involved_action_types'::text, v_use_case->'required_roles'::text, (v_use_case->>'typical_duration_days')::INT, v_use_case->'documents_created'::text, v_use_case->>'output', v_kb_version, v_release_timestamp, p_created_by) ON CONFLICT (use_case_id) DO NOTHING;
    v_inserted := v_inserted + 1;
  END LOOP;
  RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- MASTER LOADER FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION ontology.load_knowledge_base(kb_json JSONB, p_created_by VARCHAR DEFAULT 'system:kb_loader') RETURNS JSON AS $$
DECLARE
  v_result JSON;
  v_validation_result RECORD;
  v_kb_version VARCHAR;
  v_policy_version VARCHAR;
  v_release_timestamp TIMESTAMPTZ;
  v_content_digest VARCHAR;
  v_existing_digest VARCHAR;
  v_dim_count INT;
  v_et_count INT;
  v_decision_count INT;
  v_di_count INT;
  v_do_count INT;
  v_ir_count INT;
  v_pr_count INT;
  v_at_count INT;
  v_aa_count INT;
  v_role_count INT;
  v_rg_count INT;
  v_uc_count INT;
BEGIN
  SELECT * INTO v_validation_result FROM ontology.validate_kb_json(kb_json) LIMIT 1;
  IF NOT v_validation_result.is_valid THEN
    RETURN json_build_object('success', FALSE, 'error', v_validation_result.error_message);
  END IF;

  v_kb_version := kb_json->'kb_metadata'->>'kb_version';
  v_policy_version := kb_json->'kb_metadata'->>'policy_version';
  v_release_timestamp := NOW();
  v_content_digest := encode(digest(kb_json::text::bytea, 'sha256'), 'hex');

  SELECT content_digest INTO v_existing_digest FROM ontology.kb_versions WHERE kb_version = v_kb_version LIMIT 1;
  IF v_existing_digest IS NOT NULL THEN
    IF v_existing_digest != v_content_digest THEN
      RETURN json_build_object('success', FALSE, 'error', 'KB version ' || v_kb_version || ' already exists with different content digest');
    END IF;
  END IF;

  v_dim_count := ontology.load_kb_dimensions(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_et_count := ontology.load_kb_evidence_types(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_decision_count := ontology.load_kb_decisions(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_di_count := ontology.load_kb_decision_inputs(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_do_count := ontology.load_kb_decision_outputs(kb_json, v_kb_version, v_policy_version, v_release_timestamp, p_created_by);
  v_ir_count := ontology.load_kb_identity_rules(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_pr_count := ontology.load_kb_projection_rules(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_at_count := ontology.load_kb_action_types(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_aa_count := ontology.load_kb_action_authorizations(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_role_count := ontology.load_kb_roles(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_rg_count := ontology.load_kb_read_grants(kb_json, v_kb_version, v_release_timestamp, p_created_by);
  v_uc_count := ontology.load_kb_use_cases(kb_json, v_kb_version, v_release_timestamp, p_created_by);

  INSERT INTO ontology.kb_versions (kb_version, status, content_digest, effective_from, created_by) 
  VALUES (v_kb_version, 'DRAFT', v_content_digest, v_release_timestamp, p_created_by)
  ON CONFLICT (kb_version) DO NOTHING;

  RETURN json_build_object(
    'success', TRUE,
    'kb_version', v_kb_version,
    'policy_version', v_policy_version,
    'content_digest', v_content_digest,
    'release_timestamp', v_release_timestamp,
    'loaded_counts', json_build_object(
      'dimensions', v_dim_count,
      'evidence_types', v_et_count,
      'decisions', v_decision_count,
      'decision_inputs', v_di_count,
      'decision_outputs', v_do_count,
      'identity_rules', v_ir_count,
      'projection_rules', v_pr_count,
      'action_types', v_at_count,
      'action_authorizations', v_aa_count,
      'roles', v_role_count,
      'read_grants', v_rg_count,
      'use_cases', v_uc_count
    )
  );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- WRAPPER FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION ontology.load_kb_v1_0()
RETURNS JSON AS $$
DECLARE
  v_kb_json JSONB;
  v_result JSON;
BEGIN
  SELECT kb_data INTO v_kb_json FROM ontology.kb_store WHERE kb_version = '1.0';
  IF v_kb_json IS NULL THEN
    RAISE EXCEPTION 'KB v1.0 not found in ontology.kb_store';
  END IF;
  SELECT * INTO v_result FROM ontology.load_knowledge_base(v_kb_json, 'admin:deployment');
  RETURN v_result;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ============================================================================
-- EXECUTE THE KB LOAD
-- ============================================================================
SELECT * FROM ontology.load_kb_v1_0();

-- ============================================================================
-- ACTIVATE KB
-- ============================================================================
UPDATE ontology.kb_versions SET status = 'ACTIVE', activated_at = NOW() WHERE kb_version = '1.0';

-- ============================================================================
-- FINAL VERIFICATION
-- ============================================================================
SELECT kb_version, status, activated_at FROM ontology.kb_versions WHERE kb_version = '1.0';
