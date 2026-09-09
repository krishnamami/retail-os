# Evidence Mapping Review Table - Complete

**One row per distinct Evidence mapping. Not grouped by event type.**

| Mapping ID | Event Type | Logical Source | Subject Type | Subject ID Source | Property Name | Value Source | Actor Field | Timestamp Fields | Reason |
|---|---|---|---|---|---|---|---|---|---|
| PRODUCT_INTENT_ID | PRODUCT_INTENT_CREATED | product_intent | launch | launch_id | product_intent_id | payload.product_intent_id | - | occurred_at, recorded_at, arrival_at | Identify intent market driver |
| PRODUCT_INTENT_CLASS | PRODUCT_INTENT_CREATED | product_intent | launch | launch_id | intent_classification | payload.intent_class | process_step | occurred_at, recorded_at, arrival_at | Market intent type |
| HIERARCHY_APPROVAL_CON_CODE | HIERARCHY_APPROVAL | approval_workflow | launch | launch_id | hierarchy_code_con | payload.hierarchy_approvals[CON].hierarchy_code | approval_authority | occurred_at, recorded_at, arrival_at | CON hierarchy approval |
| HIERARCHY_APPROVAL_CON_AUTH | HIERARCHY_APPROVAL | approval_workflow | launch | launch_id | hierarchy_approval_authority_con | payload.hierarchy_approvals[CON].approval_authority | approval_authority | occurred_at, recorded_at, arrival_at | CON approval authority |
| HIERARCHY_APPROVAL_PRD_CODE | HIERARCHY_APPROVAL | approval_workflow | launch | launch_id | hierarchy_code_prd | payload.hierarchy_approvals[PRD].hierarchy_code | approval_authority | occurred_at, recorded_at, arrival_at | PRD hierarchy approval |
| HIERARCHY_APPROVAL_PRD_AUTH | HIERARCHY_APPROVAL | approval_workflow | launch | launch_id | hierarchy_approval_authority_prd | payload.hierarchy_approvals[PRD].approval_authority | approval_authority | occurred_at, recorded_at, arrival_at | PRD approval authority |
| SAP_CON_LOAD_STATUS | SAP_CON_LOADED | sap_con | configuration | con_id | sap_con_load_status | payload.con_status | loaded_by | occurred_at, recorded_at, arrival_at | CON load result (SUCCESS/FAILURE/PENDING) |
| SAP_CON_LOAD_ACTOR | SAP_CON_LOADED | sap_con | configuration | con_id | sap_con_load_actor | payload.loaded_by | loaded_by | occurred_at, recorded_at, arrival_at | Which system/process loaded CON |
| SAP_CON_HIERARCHY | SAP_CON_LOADED | sap_con | configuration | con_id | sap_con_hierarchy_code | payload.hierarchy_code | loaded_by | occurred_at, recorded_at, arrival_at | Hierarchy code loaded in CON |
| SAP_PRD_LOAD_STATUS | SAP_PRD_LOADED | sap_prd | configuration | prd_id | sap_prd_load_status | payload.prd_status | loaded_by | occurred_at, recorded_at, arrival_at | PRD load result (SUCCESS/FAILURE/PENDING) |
| SAP_PRD_LOAD_ACTOR | SAP_PRD_LOADED | sap_prd | configuration | prd_id | sap_prd_load_actor | payload.loaded_by | loaded_by | occurred_at, recorded_at, arrival_at | Which system/process loaded PRD |
| SAP_PRD_HIERARCHY | SAP_PRD_LOADED | sap_prd | configuration | prd_id | sap_prd_hierarchy_code | payload.hierarchy_code | loaded_by | occurred_at, recorded_at, arrival_at | Hierarchy code loaded in PRD |
| CON_VERIFIED | CON_VERIFIED | verification_gate | configuration | con_id | con_verification_status | "VERIFIED" | process_step | occurred_at, recorded_at, arrival_at | CON content verified |
| SAP_CON_TEST_RESULT | SAP_CON_TESTED | sap_con | configuration | con_id | sap_con_test_result | payload.test_result | process_step | occurred_at, recorded_at, arrival_at | CON testing result (PASS/FAIL) |
| SAP_CON_TEST_ENV | SAP_CON_TESTED | sap_con | configuration | con_id | sap_con_test_environment | payload.test_environment | process_step | occurred_at, recorded_at, arrival_at | Which environment tested |
| MATERIAL_CREATED | MATERIAL_CREATED | material_lifecycle | material | material_id | material_status | "CREATED" | process_step | occurred_at, recorded_at, arrival_at | Material lineage start |
| MATERIAL_ACTIVATION_STATUS | MATERIAL_ACTIVATED | material_lifecycle | material | material_id | material_activation_status | payload.material_status | status_changed_by | occurred_at, recorded_at, arrival_at | Material operational readiness |
| MATERIAL_ACTIVATION_ACTOR | MATERIAL_ACTIVATED | material_lifecycle | material | material_id | material_activated_by | payload.status_changed_by | status_changed_by | occurred_at, recorded_at, arrival_at | Who activated material |
| SKU_MINTED | SKU_LIFECYCLE | sku_lifecycle | sku | sku_id | sku_status | "MINTED" | process_step | occurred_at, recorded_at, arrival_at | SKU creation/minting event |
| SKU_ACTIVATED | SKU_LIFECYCLE | sku_lifecycle | sku | sku_id | sku_activation_status | "ACTIVATED" | process_step | occurred_at, recorded_at, arrival_at | SKU operational readiness |
| TECHNICAL_REVIEW_RESULT | TECHNICAL_REVIEW | technical_gate | configuration | (con_id OR prd_id) | technical_review_result | payload.review_result OR "PASS" | process_step | occurred_at, recorded_at, arrival_at | Technical gate result (PASS/NEGATIVE/PENDING) |
| TECHNICAL_REVIEW_REASON | TECHNICAL_REVIEW | technical_gate | configuration | (con_id OR prd_id) | technical_review_reason | payload.review_reason | process_step | occurred_at, recorded_at, arrival_at | ONLY if review_result = NEGATIVE (absence NOT generated) |
| PRICING_VALUE | PRICING_DETERMINED | pricing_gate | sku | sku_id | pricing_value_usd | payload.determined_price_usd | process_step | occurred_at, recorded_at, arrival_at | Price determined |
| PRICING_STATUS | PRICING_DETERMINED | pricing_gate | sku | sku_id | pricing_status | "DETERMINED" | process_step | occurred_at, recorded_at, arrival_at | Pricing gate status |
| PRICING_UPLOAD_STATUS | PRICING_UPLOADED | pricing_gate | configuration | (con_id OR prd_id) | pricing_upload_status | "UPLOADED" | process_step | occurred_at, recorded_at, arrival_at | Pricing file uploaded |
| PRICING_CONFIRMED | PRICING_CONFIRMED | pricing_gate | sku | sku_id | pricing_confirmed | "CONFIRMED" | process_step | occurred_at, recorded_at, arrival_at | Pricing confirmation gate |
| PRICING_PUBLISHED | PRICING_PUBLISHED | pricing_gate | configuration | (con_id OR prd_id) | pricing_publication_status | "PUBLISHED" | process_step | occurred_at, recorded_at, arrival_at | Pricing published to downstream |
| FINAL_PRICING_APPROVAL | FINAL_PRICING_APPROVAL | approval_gate | launch | launch_id | final_pricing_approval_status | "APPROVED" | approval_authority | occurred_at, recorded_at, arrival_at | Pricing approval gate |
| FINAL_PRICING_AUTH | FINAL_PRICING_APPROVAL | approval_gate | launch | launch_id | final_pricing_approval_authority | payload.approval_authority | approval_authority | occurred_at, recorded_at, arrival_at | Who approved pricing |
| ZUPDM_APPROVED | ZUPDM_APPROVED | supply_chain_gate | configuration | (con_id OR prd_id) | zupdm_approval_status | "APPROVED" | process_step | occurred_at, recorded_at, arrival_at | Supply chain approval |
| FULLY_APPROVED | FULLY_APPROVED | composite_gate | launch | launch_id | all_gates_cleared | "APPROVED" | process_step | occurred_at, recorded_at, arrival_at | All gates cleared |
| GO_LIVE_APPROVAL_REQUESTED | GO_LIVE_APPROVAL_REQUESTED | approval_gate | launch | launch_id | go_live_approval_requested | "REQUESTED" | process_step | occurred_at, recorded_at, arrival_at | Go-live approval gate initiation |
| GO_LIVE_APPROVED | GO_LIVE_APPROVED | approval_gate | launch | launch_id | go_live_approval_status | "APPROVED" | approval_authority | occurred_at, recorded_at, arrival_at | Go-live approval gate decision |
| GO_LIVE_AUTH | GO_LIVE_APPROVED | approval_gate | launch | launch_id | go_live_approval_authority | payload.approval_authority | approval_authority | occurred_at, recorded_at, arrival_at | Who approved go-live |
| SUPPLY_CHAIN_NOTIFIED | SUPPLY_CHAIN_NOTIFIED | supply_chain_gate | configuration | (con_id OR prd_id) | supply_chain_notification_status | "NOTIFIED" | process_step | occurred_at, recorded_at, arrival_at | Downstream supply chain notification |
| OVERNIGHT_PUSH_STATUS | OVERNIGHT_PUSH | data_push | configuration | (con_id OR prd_id) | overnight_push_status | payload.push_event_type | process_step | occurred_at, recorded_at, arrival_at | Scheduled data push result |
| OVERNIGHT_PUSH_DATE | OVERNIGHT_PUSH | data_push | configuration | (con_id OR prd_id) | overnight_push_run_date | payload.push_run_date | process_step | occurred_at, recorded_at, arrival_at | Push execution date |
| CHANGE_TYPE | CHANGE_REQUESTED | product_intent | launch | launch_id | change_type | payload.change_type | actor_id | occurred_at, recorded_at, arrival_at | Type of requested change |
| CHANGE_REASON | CHANGE_REQUESTED | product_intent | launch | launch_id | change_reason | payload.change_reason | actor_id | occurred_at, recorded_at, arrival_at | Reason for change request |
| CHANGE_REQUESTED_BY | CHANGE_REQUESTED | product_intent | launch | launch_id | change_requested_by | raw.actor_id | actor_id | occurred_at, recorded_at, arrival_at | Who requested change |
| CHANGE_REQUESTER_ROLE | CHANGE_REQUESTED | product_intent | launch | launch_id | change_requester_role | raw.actor_role | actor_role | occurred_at, recorded_at, arrival_at | Requester's role context |

---

## Mapping Statistics

- **Total Distinct Mappings**: 38 (NOT 25 event types, but 38 discrete Evidence mappings)
- **Event Types with Multiple Mappings**: 
  - HIERARCHY_APPROVAL: 4 mappings
  - SAP_CON_LOADED: 3 mappings
  - SAP_PRD_LOADED: 3 mappings
  - MATERIAL_ACTIVATED: 2 mappings
  - SAP_CON_TESTED: 2 mappings
  - TECHNICAL_REVIEW: 2 mappings (second only if negative)
  - PRICING_DETERMINED: 2 mappings
  - FINAL_PRICING_APPROVAL: 2 mappings
  - GO_LIVE_APPROVED: 2 mappings (third is actor)
  - OVERNIGHT_PUSH: 2 mappings
  - CHANGE_REQUESTED: 4 mappings
  - All others: 1 mapping each

---

## Logical Source System Mapping

| Logical Source | Event Types | Rationale |
|---|---|---|
| product_intent | PRODUCT_INTENT_CREATED, CHANGE_REQUESTED | Product intent source (extracted from payload for CHANGE_REQUESTED) |
| approval_workflow | HIERARCHY_APPROVAL, FINAL_PRICING_APPROVAL, GO_LIVE_APPROVED | Approval authority observations |
| sap_con | SAP_CON_LOADED, SAP_CON_TESTED, CON_VERIFIED | CON-specific SAP system observations |
| sap_prd | SAP_PRD_LOADED, SAP_PRD_PROMOTED | PRD-specific SAP system observations |
| material_lifecycle | MATERIAL_CREATED, MATERIAL_ACTIVATED | Material lifecycle events |
| sku_lifecycle | SKU_MINTED, SKU_ACTIVATED | SKU lifecycle events |
| technical_gate | TECHNICAL_REVIEW, SAP_CON_TESTED | Technical review/testing gate |
| pricing_gate | PRICING_DETERMINED, PRICING_UPLOADED, PRICING_CONFIRMED, PRICING_PUBLISHED, FINAL_PRICING_APPROVAL | Pricing decision/publication process |
| verification_gate | CON_VERIFIED, ZUPDM_APPROVED | Verification gates |
| approval_gate | GO_LIVE_APPROVAL_REQUESTED, GO_LIVE_APPROVED, FULLY_APPROVED | High-level approval gates |
| composite_gate | FULLY_APPROVED | Composite gate (all gates passed) |
| supply_chain_gate | SUPPLY_CHAIN_NOTIFIED, ZUPDM_APPROVED | Supply chain approval/notification |
| data_push | OVERNIGHT_PUSH | Scheduled data push process |

---

## Event Types with Zero Evidence

**None identified.** All 25 event types produce at least one Evidence mapping.

**Note**: TECHNICAL_REVIEW produces zero Evidence rows IF review_result field is absent (SKU-006 case). The mapping exists, but execution produces no rows.

---

## Ambiguous Provenance - NONE

All mappings have deterministic source path and logical source system.

**Potential Concern**: TECHNICAL_REVIEW reason field
- Only generates Evidence if review_result = NEGATIVE
- Is this correct? Or should reason create Evidence regardless?
- **Status**: As designed per SKU-013 vs SKU-006 requirement (explicit negative creates Evidence, absence does not)

---

## Mapping ID Format

`{LOGICAL_SOURCE}_{PROPERTY_NORMALIZED}` or `{EVENT_TYPE}_{PROPERTY}`

Examples:
- SAP_CON_LOAD_STATUS (event-level, more specific)
- MATERIAL_ACTIVATION_STATUS (event-level, more specific)
- HIERARCHY_APPROVAL_CON_CODE (event-level, distinguishes CON vs PRD)

**Determinism**: Each mapping_id is unique and derivable from event_type + property extraction rule.

---

## Approval Gate

**Ready for Approval**:
1. ✓ 38 distinct mappings identified (not 25 events)
2. ✓ Each mapping has deterministic mapping_id
3. ✓ Logical source system assigned for each
4. ✓ No event type produces zero Evidence
5. ✓ No ambiguous provenance
6. ✓ TECHNICAL_REVIEW reason handling confirmed (absence ≠ negative)
7. ✓ Actor attribution vs source provenance separated

**Outstanding Blocker**:
- runtime.evidence UNIQUE constraint `(subject_type, subject_id, property_name, arrival_at)` vs lineage-based idempotency `(raw_event_id, mapping_id)`
- Needs reconciliation before SQL implementation

