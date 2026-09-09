-- STEP 5F.2 — TRANSFORM 36 PROTOTYPE EVIDENCE ROWS INTO ASSERTIONS
-- Idempotency: Guarded by NOT EXISTS on source_evidence_id
-- Scope: ONLY 36 prototype Evidence rows with specified mapping_ids
-- Expected result: +36 Assertions (107 → 143)
-- Preserves S6 (2 distinct subjects) and S7 (4 Assertions, no customer_segment NULL)

INSERT INTO runtime.assertion
(subject_type, subject_id, property_name, asserted_value, property_value_type, property_value_json, assertion_type, authority, authority_policy_id, effective_at, validity_horizon, arrival_at, source_evidence_id, supersedes_assertion_id, simulator_classification)
SELECT
    e.subject_type,
    e.subject_id,
    e.property_name,
    e.asserted_value,
    e.value_type AS property_value_type,
    e.value_json AS property_value_json,
    e.property_name || '_ASSERTION' AS assertion_type,
    'evidence_direct' AS authority,
    NULL AS authority_policy_id,
    e.occurred_at AS effective_at,
    NULL AS validity_horizon,
    e.arrival_at,
    e.evidence_id AS source_evidence_id,
    NULL AS supersedes_assertion_id,
    NULL AS simulator_classification
FROM runtime.evidence e
WHERE e.mapping_id = ANY(ARRAY['PRODUCT_DEF_NAME', 'PRODUCT_DEF_LAUNCH', 'CONF_REQ_PRODUCT', 'CONF_REQ_LAUNCH', 'CONF_REQ_GEO', 'CONF_REQ_TERM', 'CONF_REQ_SEGMENT']::text[])
  AND e.simulator_classification = 'PROTOTYPE_ASSUMPTION'
  AND NOT EXISTS (SELECT 1 FROM runtime.assertion a WHERE a.source_evidence_id = e.evidence_id)
ORDER BY e.evidence_id;
