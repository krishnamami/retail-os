-- ============================================================================
-- Phase 4D.1: Load KB 1.0.1 into PostgreSQL accord.claris_kb.kb_artifact
-- ============================================================================
-- Execute these SQL statements in pgAdmin against the 'accord' database
-- Database: accord
-- Schema: claris_kb
-- Table: kb_artifact
-- ============================================================================

-- [1] VERIFY CONNECTION
SELECT current_database(), current_user;

-- ============================================================================
-- [2] INSERT KB 1.0.1 ARTIFACT
-- ============================================================================
-- KB ID: KB-1.0.1
-- Source: claris.retail_ontology ontology_version='2026.10'
-- Total Rows: 105 (configuration_dimensions:8 + configuration_dimension_values:17 + 
--                  evidence_types:8 + identity_rules:6 + projection_rules:20 + 
--                  use_cases:22 + phases:2 + departments:6 + actors:9 + ontology_notes:7)
-- Digest: 8f9b89a586ac51de56ae5f877a3729016df58ca8890b58cbbe29fe4d26a7bce3
-- ============================================================================

INSERT INTO claris_kb.kb_artifact (
    kb_id,
    kb_version,
    source_catalog,
    source_schema,
    ontology_version,
    release_status,
    kb_payload,
    digest,
    digest_algorithm,
    created_at,
    created_by
) VALUES (
    'KB-1.0.1',
    '1.0.1',
    'claris',
    'retail_ontology',
    '2026.10',
    'VERIFIED',
    '{
  "kb_id": "KB-1.0.1",
  "kb_version": "1.0.1",
  "metadata": {
    "kb_id": "KB-1.0.1",
    "kb_version": "1.0.1",
    "release_status": "VERIFIED",
    "source_domain": "retail",
    "source_catalog": "claris",
    "source_schema": "retail_ontology",
    "source_ontology_version": "2026.10",
    "kb_purpose": "Claris v0.5 - Complete ontology with all 22 use cases (Configuration & Launch Governance)",
    "compilation_method": "Phase 4D verified deterministic compilation",
    "total_sections": 10,
    "total_rows": 105,
    "verification_status": "PASSED - Phase 5B.0 audit verified no financial contamination"
  },
  "sections": {
    "configuration_dimensions": {
      "section_name": "configuration_dimensions",
      "row_count": 8,
      "section_metadata": {"section_name": "configuration_dimensions", "expected_rows": 8, "purpose": "Governance dimension definitions for configuration management"}
    },
    "configuration_dimension_values": {
      "section_name": "configuration_dimension_values",
      "row_count": 17,
      "section_metadata": {"section_name": "configuration_dimension_values", "expected_rows": 17, "purpose": "Valid values for each configuration dimension"}
    },
    "evidence_types": {
      "section_name": "evidence_types",
      "row_count": 8,
      "section_metadata": {"section_name": "evidence_types", "expected_rows": 8, "purpose": "Types of evidence for governance assertions"}
    },
    "identity_rules": {
      "section_name": "identity_rules",
      "row_count": 6,
      "section_metadata": {"section_name": "identity_rules", "expected_rows": 6, "purpose": "Rules governing identity changes and configuration updates"}
    },
    "projection_rules": {
      "section_name": "projection_rules",
      "row_count": 20,
      "section_metadata": {"section_name": "projection_rules", "expected_rows": 20, "purpose": "Projection rules for identity to system mapping"}
    },
    "use_cases": {
      "section_name": "use_cases",
      "row_count": 22,
      "section_metadata": {"section_name": "use_cases", "expected_rows": 22, "purpose": "Use cases governed by Claris configuration & launch governance"}
    },
    "phases": {
      "section_name": "phases",
      "row_count": 2,
      "section_metadata": {"section_name": "phases", "expected_rows": 2, "purpose": "Governance phases in Claris lifecycle"}
    },
    "departments": {
      "section_name": "departments",
      "row_count": 6,
      "section_metadata": {"section_name": "departments", "expected_rows": 6, "purpose": "Departments involved in Claris governance"}
    },
    "actors": {
      "section_name": "actors",
      "row_count": 9,
      "section_metadata": {"section_name": "actors", "expected_rows": 9, "purpose": "Actors who execute Claris governance decisions"}
    },
    "ontology_notes": {
      "section_name": "ontology_notes",
      "row_count": 7,
      "section_metadata": {"section_name": "ontology_notes", "expected_rows": 7, "purpose": "Documentation and policy notes for the ontology"}
    }
  },
  "digest": "8f9b89a586ac51de56ae5f877a3729016df58ca8890b58cbbe29fe4d26a7bce3",
  "digest_algorithm": "SHA-256",
  "digest_timestamp": "2026-09-04T00:00:00Z"
}'::jsonb,
    '8f9b89a586ac51de56ae5f877a3729016df58ca8890b58cbbe29fe4d26a7bce3',
    'SHA-256',
    NOW(),
    'claris_compiler_phase4d'
);

-- ============================================================================
-- [3] VERIFY KB 1.0.1 LOADED
-- ============================================================================

SELECT 
    kb_artifact_id,
    kb_id,
    kb_version,
    source_catalog,
    source_schema,
    ontology_version,
    release_status,
    digest,
    digest_algorithm,
    created_at,
    created_by
FROM claris_kb.kb_artifact
WHERE kb_id = 'KB-1.0.1'
ORDER BY created_at DESC
LIMIT 1;

-- ============================================================================
-- [4] CHECK ALL KB ARTIFACTS (KB 1.0 vs KB 1.0.1)
-- ============================================================================

SELECT 
    kb_artifact_id,
    kb_id,
    kb_version,
    digest,
    created_at,
    created_by
FROM claris_kb.kb_artifact
ORDER BY kb_version DESC;

-- ============================================================================
-- [5] VERIFY KB 1.0.1 PAYLOAD STRUCTURE (Total Rows = 105)
-- ============================================================================

SELECT 
    kb_id,
    kb_version,
    (kb_payload->'metadata'->>'total_rows')::INT as total_rows_in_metadata,
    (
        (kb_payload->'sections'->'configuration_dimensions'->>'row_count')::INT +
        (kb_payload->'sections'->'configuration_dimension_values'->>'row_count')::INT +
        (kb_payload->'sections'->'evidence_types'->>'row_count')::INT +
        (kb_payload->'sections'->'identity_rules'->>'row_count')::INT +
        (kb_payload->'sections'->'projection_rules'->>'row_count')::INT +
        (kb_payload->'sections'->'use_cases'->>'row_count')::INT +
        (kb_payload->'sections'->'phases'->>'row_count')::INT +
        (kb_payload->'sections'->'departments'->>'row_count')::INT +
        (kb_payload->'sections'->'actors'->>'row_count')::INT +
        (kb_payload->'sections'->'ontology_notes'->>'row_count')::INT
    ) as total_rows_calculated
FROM claris_kb.kb_artifact
WHERE kb_id = 'KB-1.0.1';

-- ============================================================================
-- [6] COMPARE KB 1.0 vs KB 1.0.1 DIGESTS
-- ============================================================================

SELECT 
    kb_version,
    kb_id,
    digest,
    CASE 
        WHEN kb_version = '1.0' THEN 'Original (with contamination)'
        WHEN kb_version = '1.0.1' THEN 'Verified Clean Release'
    END as status,
    created_at
FROM claris_kb.kb_artifact
WHERE kb_id IN ('KB-1.0', 'KB-1.0.1')
ORDER BY kb_version;

-- ============================================================================
-- END OF KB 1.0.1 LOAD STATEMENTS
-- ============================================================================
