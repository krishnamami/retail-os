-- =====================================================================
-- STEP 5G.2 — IDENTITY_ASSESSMENT KB CONTRACT VERIFICATION
-- Query actual runtime KB schema (claris_kb, ontology schemas)
-- Write all findings to temp tables
-- =====================================================================

-- Master KB verification results
CREATE TEMP TABLE kb_verification_results (
    verification_section TEXT,
    verification_item TEXT,
    verification_value TEXT,
    verification_detail TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- 1. ACTIVE KB / ONTOLOGY / POLICY VERSIONS
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '1. KB/ONTOLOGY/POLICY VERSIONS',
    'KB versions (active)',
    kb_version,
    'Status: ' || status || ' | Effective: ' || effective_from::TEXT || ' to ' || COALESCE(effective_to::TEXT, 'present')
FROM ontology.kb_versions
WHERE status = 'active' OR effective_to IS NULL
ORDER BY activated_at DESC
LIMIT 1;

-- =====================================================================
-- 2. IDENTITY_ASSESSMENT DECISION DEFINITION
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '2. IDENTITY_ASSESSMENT DECISION',
    'Decision: ' || decision_type,
    decision_name,
    'Owner: ' || COALESCE(owner, 'N/A') || ' | Status: ' || status
FROM claris_kb.v_active_decisions
WHERE decision_type = 'IDENTITY_ASSESSMENT'
   OR decision_name LIKE '%IDENTITY%ASSESSMENT%';

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '2. IDENTITY_ASSESSMENT DECISION',
    'Description',
    description,
    'Governance: ' || COALESCE(governance_principle, 'N/A')
FROM claris_kb.v_active_decisions
WHERE decision_type = 'IDENTITY_ASSESSMENT'
   OR decision_name LIKE '%IDENTITY%ASSESSMENT%';

-- =====================================================================
-- 3. VERIFY IR-001 THROUGH IR-009 IDENTITY RULES
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '3. IDENTITY RULES (IR-001..IR-009)',
    'Rule: ' || rule_id,
    rule_name,
    'Status: ' || status || ' | Effective: ' || effective_from::TEXT || ' to ' || COALESCE(effective_to::TEXT, 'present')
FROM claris_kb.v_active_identity_rules
WHERE rule_id LIKE 'IR-%'
ORDER BY rule_id;

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value)
SELECT
    '3. IDENTITY RULES (IR-001..IR-009)',
    'Rule: ' || rule_id || ' | Rule Logic',
    COALESCE(description, rule_name)
FROM claris_kb.v_active_identity_rules
WHERE rule_id LIKE 'IR-%'
ORDER BY rule_id;

-- =====================================================================
-- 4. VERIFY EXACT ALLOWED OUTCOMES
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '4. ALLOWED DECISION OUTCOMES',
    'Outcome: ' || outcome_code,
    outcome_name,
    'Decision: ' || decision_type || ' | Status: ' || status
FROM claris_kb.v_active_decision_outputs
WHERE decision_type = 'IDENTITY_ASSESSMENT'
ORDER BY outcome_code;

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value)
SELECT
    '4. ALLOWED DECISION OUTCOMES',
    'Outcome: ' || outcome_code || ' | Actions',
    COALESCE(description, 'N/A')
FROM claris_kb.v_active_decision_outputs
WHERE decision_type = 'IDENTITY_ASSESSMENT'
ORDER BY outcome_code;

-- Search for reuse outcomes
INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '4. ALLOWED DECISION OUTCOMES',
    'REUSE outcome search',
    COALESCE(outcome_code, 'NOT FOUND'),
    'Checking for: REUSE_CONFIGURATION, USE_EXISTING, EXISTING_CONFIGURATION_MATCH'
FROM claris_kb.v_active_decision_outputs
WHERE decision_type = 'IDENTITY_ASSESSMENT'
  AND outcome_code IN ('REUSE_CONFIGURATION', 'USE_EXISTING_CONFIGURATION', 'EXISTING_CONFIGURATION_MATCH');

-- =====================================================================
-- 5. S6 GOVERNANCE: EXACT IDENTITY MATCH
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '5. S6 GOVERNANCE: EXACT MATCH',
    'Search outcome',
    CASE
        WHEN EXISTS (
            SELECT 1 FROM claris_kb.v_active_decision_outputs
            WHERE decision_type = 'IDENTITY_ASSESSMENT'
              AND outcome_code IN ('REUSE_CONFIGURATION', 'USE_EXISTING_CONFIGURATION', 'EXISTING_CONFIGURATION_MATCH')
        ) THEN 'EXACT MATCH/REUSE OUTCOME FOUND'
        ELSE 'NO GOVERNED MATCH/REUSE OUTCOME FOUND'
    END AS s6_finding,
    'Affects: CONFIG-REQ-2026-006 vs 006B (same logical identity)';

-- =====================================================================
-- 6. S7 GOVERNANCE: MISSING REQUIRED INPUT
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '6. S7 GOVERNANCE: MISSING INPUT',
    'Missing-input rules (customer_segment)',
    rule_name,
    'Rule: ' || rule_id || ' | Status: ' || status
FROM claris_kb.v_active_identity_rules
WHERE description LIKE '%missing%'
   OR description LIKE '%CANNOT_DECIDE%'
   OR rule_name LIKE '%missing%';

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '6. S7 GOVERNANCE: MISSING INPUT',
    'Search result',
    CASE
        WHEN EXISTS (
            SELECT 1 FROM claris_kb.v_active_identity_rules
            WHERE description LIKE '%CANNOT_DECIDE%' OR rule_name LIKE '%cannot%decide%'
        ) THEN 'S7: CANNOT_DECIDE FOR MISSING INPUT SUPPORTED'
        ELSE 'S7 GOVERNANCE GAP — MISSING INPUT OUTCOME NOT DEFINED'
    END AS s7_finding,
    'Affects: CONFIG-REQ-2026-007 (customer_segment UNREPORTED)';

-- =====================================================================
-- 7. BOOTSTRAP: FIRST CREATION / EMPTY CANONICAL
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '7. BOOTSTRAP: EMPTY CANONICAL',
    'First-creation rule search',
    rule_name,
    'Rule: ' || rule_id || ' | Searches for CREATE_PRODUCT, CREATE_CONFIGURATION'
FROM claris_kb.v_active_identity_rules
WHERE rule_name LIKE '%CREATE%' OR description LIKE '%CREATE%'
ORDER BY rule_id;

-- =====================================================================
-- 8. DECISION INPUT GAP ANALYSIS
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '8. DECISION INPUT GAP MATRIX',
    'Input: ' || input_name,
    CASE WHEN required THEN 'REQUIRED' ELSE 'OPTIONAL' END,
    'Source: ' || source_type || ' | Condition: ' || COALESCE(condition, 'N/A')
FROM claris_kb.v_active_decision_inputs
WHERE decision_type = 'IDENTITY_ASSESSMENT'
ORDER BY input_name;

-- Explicit gap check
INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '8. DECISION INPUT GAP MATRIX',
    'customer_segment (S7)',
    CASE
        WHEN EXISTS (SELECT 1 FROM claris_kb.v_active_decision_inputs WHERE decision_type = 'IDENTITY_ASSESSMENT' AND input_name = 'customer_segment')
        THEN 'REQUIRED'
        ELSE 'NOT_REQUIRED or NOT_DEFINED'
    END,
    CASE
        WHEN EXISTS (SELECT 1 FROM claris_kb.v_active_decision_inputs WHERE decision_type = 'IDENTITY_ASSESSMENT' AND input_name = 'customer_segment')
        THEN 'MISSING_FROM_FOLD (only 6/7 requests have it)'
        ELSE 'Not part of decision inputs'
    END;

-- =====================================================================
-- 9. DECISION RULES FOR IDENTITY_ASSESSMENT
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '9. DECISION RULES',
    'Rule: ' || rule_name,
    'Outcome: ' || outcome_code,
    'Precedence: ' || COALESCE(precedence::TEXT, 'N/A') || ' | Missing-Evidence: ' || COALESCE(missing_evidence_action, 'N/A')
FROM claris_kb.v_active_decision_rules
WHERE decision_type = 'IDENTITY_ASSESSMENT'
ORDER BY COALESCE(precedence, 999), rule_name;

-- =====================================================================
-- 10. GOVERNANCE GAPS SUMMARY
-- =====================================================================

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '10. GOVERNANCE GAPS',
    'Gap: S6 Reuse Outcome',
    CASE
        WHEN EXISTS (SELECT 1 FROM claris_kb.v_active_decision_outputs WHERE decision_type = 'IDENTITY_ASSESSMENT' AND outcome_code IN ('REUSE_CONFIGURATION', 'USE_EXISTING_CONFIGURATION', 'EXISTING_CONFIGURATION_MATCH'))
        THEN 'NOT_A_GAP'
        ELSE 'CRITICAL_GAP'
    END,
    'S6: Exact identity match (006 vs 006B) outcome not explicitly defined'
WHERE NOT EXISTS (SELECT 1 FROM claris_kb.v_active_decision_outputs WHERE decision_type = 'IDENTITY_ASSESSMENT' AND outcome_code IN ('REUSE_CONFIGURATION', 'USE_EXISTING_CONFIGURATION', 'EXISTING_CONFIGURATION_MATCH'));

INSERT INTO kb_verification_results (verification_section, verification_item, verification_value, verification_detail)
SELECT
    '10. GOVERNANCE GAPS',
    'Gap: S7 Missing Input',
    CASE
        WHEN EXISTS (SELECT 1 FROM claris_kb.v_active_identity_rules WHERE description LIKE '%CANNOT_DECIDE%')
        THEN 'NOT_A_GAP'
        ELSE 'CRITICAL_GAP'
    END,
    'S7: Missing required input (customer_segment) outcome not explicitly defined'
WHERE NOT EXISTS (SELECT 1 FROM claris_kb.v_active_identity_rules WHERE description LIKE '%CANNOT_DECIDE%');

-- =====================================================================
-- COMPREHENSIVE DISPLAY FROM TEMP TABLE
-- =====================================================================

SELECT '=== STEP 5G.2 KB CONTRACT VERIFICATION - FINAL REPORT ===' AS heading;

-- 1. KB Versions
SELECT '--- 1. ACTIVE KB/ONTOLOGY/POLICY VERSIONS ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '1. KB/ONTOLOGY/POLICY VERSIONS'
ORDER BY verification_item;

-- 2. Decision Definition
SELECT '--- 2. IDENTITY_ASSESSMENT DECISION DEFINITION ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '2. IDENTITY_ASSESSMENT DECISION'
ORDER BY verification_item;

-- 3. Identity Rules
SELECT '--- 3. IDENTITY RULES (IR-001..IR-009) ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '3. IDENTITY RULES (IR-001..IR-009)'
ORDER BY verification_item;

-- 4. Allowed Outcomes
SELECT '--- 4. ALLOWED DECISION OUTCOMES ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '4. ALLOWED DECISION OUTCOMES'
ORDER BY verification_item;

-- 5. S6 Governance
SELECT '--- 5. S6 GOVERNANCE: EXACT IDENTITY MATCH ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '5. S6 GOVERNANCE: EXACT MATCH'
ORDER BY verification_item;

-- 6. S7 Governance
SELECT '--- 6. S7 GOVERNANCE: MISSING REQUIRED INPUT ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '6. S7 GOVERNANCE: MISSING INPUT'
ORDER BY verification_item;

-- 7. Bootstrap
SELECT '--- 7. BOOTSTRAP: FIRST CREATION / EMPTY CANONICAL ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '7. BOOTSTRAP: EMPTY CANONICAL'
ORDER BY verification_item;

-- 8. Decision Input Gap
SELECT '--- 8. DECISION INPUT GAP MATRIX ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '8. DECISION INPUT GAP MATRIX'
ORDER BY verification_item;

-- 9. Decision Rules
SELECT '--- 9. DECISION RULES FOR IDENTITY_ASSESSMENT ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '9. DECISION RULES'
ORDER BY verification_item;

-- 10. Governance Gaps
SELECT '--- 10. GOVERNANCE GAPS IDENTIFIED ---' AS section;
SELECT verification_item, verification_value, verification_detail
FROM kb_verification_results
WHERE verification_section = '10. GOVERNANCE GAPS'
ORDER BY verification_item;

-- =====================================================================
-- FINAL KB VERIFICATION VERDICT
-- =====================================================================

SELECT '=== KB VERIFICATION VERDICT ===' AS heading;

SELECT
  CASE
    WHEN (SELECT COUNT(*) FROM kb_verification_results WHERE verification_section = '10. GOVERNANCE GAPS' AND verification_value = 'CRITICAL_GAP') = 0
    THEN 'STEP 5G.2 IDENTITY_ASSESSMENT CONTRACT READY'
    ELSE 'STEP 5G.2 BLOCKED — ' || (SELECT COUNT(*) FROM kb_verification_results WHERE verification_section = '10. GOVERNANCE GAPS' AND verification_value = 'CRITICAL_GAP')::TEXT || ' critical gap(s) found'
  END AS final_verdict;

SELECT '=== STEP 5G.2 COMPLETE — All KB findings written to kb_verification_results temp table ===' AS note;
