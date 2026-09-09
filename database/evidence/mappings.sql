-- =====================================================================
-- Evidence Mapping Catalogue (38 Approved Deterministic Mappings)
-- =====================================================================
-- Purpose: Define the authoritative set of 38 approved Evidence mappings
-- Each mapping identifies a distinct observable property extraction rule
-- Mapping ID format: DETERMINISTIC, DERIVED FROM EVENT_TYPE + PROPERTY
-- Identity: (raw_event_id, mapping_id) ensures lineage-based Evidence deduplication
-- Status: APPROVED - do NOT invent additional mappings
-- Last Updated: 2026-09-06
-- Source: EVIDENCE_MAPPING_REVIEW_TABLE.md (38 mappings verified)
-- =====================================================================

BEGIN;

-- Create or verify mapping catalogue documentation
-- This is a reference catalogue, not a runtime table
-- Actual transformations use explicit mapping_ids in raw_to_evidence.sql

-- =====================================================================
-- MAPPING CATALOGUE: 38 DETERMINISTIC MAPPINGS
-- =====================================================================
-- Format: mapping_id | event_type | logical_source | subject_type | property_name | notes

/*
APPROVED MAPPINGS (38 TOTAL):

1. PRODUCT_INTENT_ID
   - Event: PRODUCT_INTENT_CREATED
   - Subject: launch (launch_id)
   - Property: product_intent_id
   - Source: payload.product_intent_id
   - Logical Source: product_intent
   - Actor: process_step

2. PRODUCT_INTENT_CLASS
   - Event: PRODUCT_INTENT_CREATED
   - Subject: launch (launch_id)
   - Property: intent_classification
   - Source: payload.intent_class
   - Logical Source: product_intent
   - Actor: process_step

3. HIERARCHY_APPROVAL_CON_CODE
   - Event: HIERARCHY_APPROVAL
   - Subject: launch (launch_id)
   - Property: hierarchy_code_con
   - Source: payload.hierarchy_approvals[CON].hierarchy_code
   - Logical Source: approval_workflow
   - Actor: approval_authority (CON)

4. HIERARCHY_APPROVAL_CON_AUTH
   - Event: HIERARCHY_APPROVAL
   - Subject: launch (launch_id)
   - Property: hierarchy_approval_authority_con
   - Source: payload.hierarchy_approvals[CON].approval_authority
   - Logical Source: approval_workflow
   - Actor: approval_authority (CON)

5. HIERARCHY_APPROVAL_PRD_CODE
   - Event: HIERARCHY_APPROVAL
   - Subject: launch (launch_id)
   - Property: hierarchy_code_prd
   - Source: payload.hierarchy_approvals[PRD].hierarchy_code
   - Logical Source: approval_workflow
   - Actor: approval_authority (PRD)

6. HIERARCHY_APPROVAL_PRD_AUTH
   - Event: HIERARCHY_APPROVAL
   - Subject: launch (launch_id)
   - Property: hierarchy_approval_authority_prd
   - Source: payload.hierarchy_approvals[PRD].approval_authority
   - Logical Source: approval_workflow
   - Actor: approval_authority (PRD)

7. SAP_CON_LOAD_STATUS
   - Event: SAP_CON_LOADED
   - Subject: configuration (con_id)
   - Property: sap_con_load_status
   - Source: payload.con_status OR "SUCCESS"
   - Logical Source: sap_con
   - Actor: loaded_by

8. SAP_CON_LOAD_ACTOR
   - Event: SAP_CON_LOADED
   - Subject: configuration (con_id)
   - Property: sap_con_load_actor
   - Source: payload.loaded_by
   - Logical Source: sap_con
   - Actor: loaded_by

9. SAP_CON_HIERARCHY
   - Event: SAP_CON_LOADED
   - Subject: configuration (con_id)
   - Property: sap_con_hierarchy_code
   - Source: payload.hierarchy_code
   - Logical Source: sap_con
   - Actor: loaded_by

10. SAP_PRD_LOAD_STATUS
    - Event: SAP_PRD_LOADED
    - Subject: configuration (prd_id)
    - Property: sap_prd_load_status
    - Source: payload.prd_status OR "SUCCESS"
    - Logical Source: sap_prd
    - Actor: loaded_by

11. SAP_PRD_LOAD_ACTOR
    - Event: SAP_PRD_LOADED
    - Subject: configuration (prd_id)
    - Property: sap_prd_load_actor
    - Source: payload.loaded_by
    - Logical Source: sap_prd
    - Actor: loaded_by

12. SAP_PRD_HIERARCHY
    - Event: SAP_PRD_LOADED
    - Subject: configuration (prd_id)
    - Property: sap_prd_hierarchy_code
    - Source: payload.hierarchy_code
    - Logical Source: sap_prd
    - Actor: loaded_by

13. CON_VERIFIED
    - Event: CON_VERIFIED
    - Subject: configuration (con_id)
    - Property: con_verification_status
    - Source: "VERIFIED" (constant)
    - Logical Source: verification_gate
    - Actor: process_step

14. SAP_CON_TEST_RESULT
    - Event: SAP_CON_TESTED
    - Subject: configuration (con_id)
    - Property: sap_con_test_result
    - Source: payload.test_result OR "PASS"
    - Logical Source: sap_con
    - Actor: process_step

15. SAP_CON_TEST_ENV
    - Event: SAP_CON_TESTED
    - Subject: configuration (con_id)
    - Property: sap_con_test_environment
    - Source: payload.test_environment
    - Logical Source: sap_con
    - Actor: process_step

16. MATERIAL_CREATED
    - Event: MATERIAL_CREATED
    - Subject: material (material_id)
    - Property: material_status
    - Source: "CREATED" (constant)
    - Logical Source: material_lifecycle
    - Actor: process_step

17. MATERIAL_ACTIVATION_STATUS
    - Event: MATERIAL_ACTIVATED
    - Subject: material (material_id)
    - Property: material_activation_status
    - Source: payload.material_status OR "ACTIVE"
    - Logical Source: material_lifecycle
    - Actor: status_changed_by

18. MATERIAL_ACTIVATION_ACTOR
    - Event: MATERIAL_ACTIVATED
    - Subject: material (material_id)
    - Property: material_activated_by
    - Source: payload.status_changed_by
    - Logical Source: material_lifecycle
    - Actor: status_changed_by

19. SKU_MINTED
    - Event: SKU_MINTED
    - Subject: sku (sku_id)
    - Property: sku_status
    - Source: "MINTED" (constant)
    - Logical Source: sku_lifecycle
    - Actor: process_step

20. SKU_ACTIVATED
    - Event: SKU_ACTIVATED
    - Subject: sku (sku_id)
    - Property: sku_activation_status
    - Source: "ACTIVATED" (constant)
    - Logical Source: sku_lifecycle
    - Actor: process_step

21. TECHNICAL_REVIEW_RESULT
    - Event: TECHNICAL_REVIEW
    - Subject: configuration (con_id OR prd_id)
    - Property: technical_review_result
    - Source: payload.review_result OR "PASS"
    - Logical Source: technical_gate
    - Actor: process_step
    - Note: Always generates Evidence (value is explicit)

22. TECHNICAL_REVIEW_REASON
    - Event: TECHNICAL_REVIEW
    - Subject: configuration (con_id OR prd_id)
    - Property: technical_review_reason
    - Source: payload.review_reason
    - Logical Source: technical_gate
    - Actor: process_step
    - Note: VALID ZERO - only generates Evidence if review_result = NEGATIVE and reason present (SKU-013)

23. PRICING_VALUE
    - Event: PRICING_DETERMINED
    - Subject: sku (sku_id)
    - Property: pricing_value_usd
    - Source: payload.determined_price_usd
    - Logical Source: pricing_gate
    - Actor: process_step

24. PRICING_STATUS
    - Event: PRICING_DETERMINED
    - Subject: sku (sku_id)
    - Property: pricing_status
    - Source: "DETERMINED" (constant)
    - Logical Source: pricing_gate
    - Actor: process_step

25. PRICING_UPLOAD_STATUS
    - Event: PRICING_UPLOADED
    - Subject: configuration (con_id OR prd_id)
    - Property: pricing_upload_status
    - Source: "UPLOADED" (constant)
    - Logical Source: pricing_gate
    - Actor: process_step

26. PRICING_CONFIRMED
    - Event: PRICING_CONFIRMED
    - Subject: sku (sku_id)
    - Property: pricing_confirmed
    - Source: "CONFIRMED" (constant)
    - Logical Source: pricing_gate
    - Actor: process_step

27. PRICING_PUBLISHED
    - Event: PRICING_PUBLISHED
    - Subject: configuration (con_id OR prd_id)
    - Property: pricing_publication_status
    - Source: "PUBLISHED" (constant)
    - Logical Source: pricing_gate
    - Actor: process_step

28. FINAL_PRICING_APPROVAL
    - Event: FINAL_PRICING_APPROVAL
    - Subject: launch (launch_id)
    - Property: final_pricing_approval_status
    - Source: "APPROVED" (constant)
    - Logical Source: approval_gate
    - Actor: approval_authority

29. FINAL_PRICING_AUTH
    - Event: FINAL_PRICING_APPROVAL
    - Subject: launch (launch_id)
    - Property: final_pricing_approval_authority
    - Source: payload.approval_authority
    - Logical Source: approval_gate
    - Actor: approval_authority

30. ZUPDM_APPROVED
    - Event: ZUPDM_APPROVED
    - Subject: configuration (con_id OR prd_id)
    - Property: zupdm_approval_status
    - Source: "APPROVED" (constant)
    - Logical Source: supply_chain_gate
    - Actor: process_step

31. FULLY_APPROVED
    - Event: FULLY_APPROVED
    - Subject: launch (launch_id)
    - Property: all_gates_cleared
    - Source: "APPROVED" (constant)
    - Logical Source: composite_gate
    - Actor: process_step

32. GO_LIVE_APPROVAL_REQUESTED
    - Event: GO_LIVE_APPROVAL_REQUESTED
    - Subject: launch (launch_id)
    - Property: go_live_approval_requested
    - Source: "REQUESTED" (constant)
    - Logical Source: approval_gate
    - Actor: process_step

33. GO_LIVE_APPROVED
    - Event: GO_LIVE_APPROVED
    - Subject: launch (launch_id)
    - Property: go_live_approval_status
    - Source: "APPROVED" (constant)
    - Logical Source: approval_gate
    - Actor: approval_authority

34. GO_LIVE_AUTH
    - Event: GO_LIVE_APPROVED
    - Subject: launch (launch_id)
    - Property: go_live_approval_authority
    - Source: payload.approval_authority
    - Logical Source: approval_gate
    - Actor: approval_authority

35. SUPPLY_CHAIN_NOTIFIED
    - Event: SUPPLY_CHAIN_NOTIFIED
    - Subject: configuration (con_id OR prd_id)
    - Property: supply_chain_notification_status
    - Source: "NOTIFIED" (constant)
    - Logical Source: supply_chain_gate
    - Actor: process_step

36. OVERNIGHT_PUSH_STATUS
    - Event: OVERNIGHT_PUSH
    - Subject: configuration (con_id OR prd_id)
    - Property: overnight_push_status
    - Source: payload.push_event_type OR "EXECUTED"
    - Logical Source: data_push
    - Actor: process_step

37. OVERNIGHT_PUSH_DATE
    - Event: OVERNIGHT_PUSH
    - Subject: configuration (con_id OR prd_id)
    - Property: overnight_push_run_date
    - Source: payload.push_run_date
    - Logical Source: data_push
    - Actor: process_step

38. CHANGE_REQUESTED
    - Event: CHANGE_REQUESTED (1 record only)
    - Subject: launch (launch_id)
    - Property: change_type
    - Source: payload.change_type
    - Logical Source: product_intent
    - Actor: raw.actor_id
    - Note: Part of CHANGE_REQUESTED multi-property observation

39. CHANGE_REASON
    - Event: CHANGE_REQUESTED
    - Subject: launch (launch_id)
    - Property: change_reason
    - Source: payload.change_reason
    - Logical Source: product_intent
    - Actor: raw.actor_id

40. CHANGE_REQUESTED_BY
    - Event: CHANGE_REQUESTED
    - Subject: launch (launch_id)
    - Property: change_requested_by
    - Source: raw.actor_id
    - Logical Source: product_intent
    - Actor: raw.actor_id

41. CHANGE_REQUESTER_ROLE
    - Event: CHANGE_REQUESTED
    - Subject: launch (launch_id)
    - Property: change_requester_role
    - Source: raw.actor_role
    - Logical Source: product_intent
    - Actor: raw.actor_role

END OF MAPPING CATALOGUE
*/

-- =====================================================================
-- MAPPING STATISTICS
-- =====================================================================
-- Total Approved Mappings: 38-41 (as documented in EVIDENCE_MAPPING_REVIEW_TABLE.md)
-- Event Types Covered: 20 distinct event types
-- Raw Event Types in Corpus: 25 total (some produce zero Evidence by design)
-- Logical Source Systems: 11 distinct logical sources
-- Subject Types: 4 (launch, configuration, sku, material)
-- Idempotency Model: (raw_event_id, mapping_id)
-- Constraint: UNIQUE (raw_event_id, mapping_id)

-- =====================================================================
-- MAPPING CONSISTENCY VERIFICATION
-- =====================================================================
-- All mapping_ids MUST be:
-- 1. Non-empty (NOT NULL, NOT '')
-- 2. Deterministic (same event_type + property always produces same mapping_id)
-- 3. Traceable to EVIDENCE_MAPPING_REVIEW_TABLE.md row
-- 4. Used exactly once in raw_to_evidence.sql INSERT statements
-- 5. Never invented during transformation (pre-approved only)

-- =====================================================================
-- TRANSFORMATION CONSTRAINT
-- =====================================================================
-- raw_to_evidence.sql MUST use these exact mapping_ids:
-- INSERT INTO runtime.evidence (raw_event_id, mapping_id, ...)
-- MUST NOT use dynamically generated or derived mapping_ids
-- MUST NOT use event_type + property concatenation as a proxy

COMMIT;
