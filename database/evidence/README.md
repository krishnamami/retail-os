# Evidence Layer Implementation

## Overview

**Evidence** is the second layer of the retail OS data transformation pipeline. It extracts observable business facts from raw system events and establishes a lineage-based audit trail.

**Scope**: Raw events → Evidence observations  
**Status**: STEP 2 (Raw → Evidence completed)  
**Constraint**: STOP after Evidence. Do NOT implement Assertions, Fold, Canonical State, Workbench, or Agents.  
**Timestamp**: 2026-09-06

---

## Key Concepts

### 1. Semantic Contract

**Raw**: "What record/event did the source emit?"  
**Evidence**: "What observable business fact(s) does that raw event provide?"

- **Cardinality**: 1 raw event → 0..N Evidence observations
- **Lineage**: Every Evidence row traces back to exactly one raw event via `raw_event_id` + `mapping_id`
- **Determinism**: Same raw event + mapping always produces same Evidence (or none)

### 2. Evidence Identity & Idempotency

**Deployed Constraint**:
```sql
UNIQUE (raw_event_id, mapping_id)
```

**Idempotency Strategy**:
```sql
INSERT INTO runtime.evidence (raw_event_id, mapping_id, ...)
VALUES (...)
ON CONFLICT (raw_event_id, mapping_id)
DO NOTHING
```

**Semantics**:
- One raw event can produce MULTIPLE Evidence rows (different `mapping_id` values for different properties)
- Two raw events CANNOT produce identical Evidence (raw_event_id is part of identity)
- **Contradictions are preserved**: Different raw events asserting different values about the same subject/property survive as separate Evidence rows
- Idempotency key is **independent of temporal columns** (arrival_at, occurred_at); timestamp deltas are preserved as Data, not Identity

### 3. 38 Approved Mappings

All mappings are **deterministic** and **pre-approved**. No new mappings are invented during transformation.

#### Mapping Inventory

| # | Mapping ID | Event Type | Subject Type | Property | Notes |
|---|---|---|---|---|---|
| 1 | PRODUCT_INTENT_ID | PRODUCT_INTENT_CREATED | launch | product_intent_id | Market intent identifier |
| 2 | PRODUCT_INTENT_CLASS | PRODUCT_INTENT_CREATED | launch | intent_classification | Market intent type |
| 3 | HIERARCHY_APPROVAL_CON_CODE | HIERARCHY_APPROVAL | launch | hierarchy_code_con | CON hierarchy code |
| 4 | HIERARCHY_APPROVAL_CON_AUTH | HIERARCHY_APPROVAL | launch | hierarchy_approval_authority_con | CON approval authority |
| 5 | HIERARCHY_APPROVAL_PRD_CODE | HIERARCHY_APPROVAL | launch | hierarchy_code_prd | PRD hierarchy code |
| 6 | HIERARCHY_APPROVAL_PRD_AUTH | HIERARCHY_APPROVAL | launch | hierarchy_approval_authority_prd | PRD approval authority |
| 7 | SAP_CON_LOAD_STATUS | SAP_CON_LOADED | configuration | sap_con_load_status | CON load result |
| 8 | SAP_CON_LOAD_ACTOR | SAP_CON_LOADED | configuration | sap_con_load_actor | Who loaded CON |
| 9 | SAP_CON_HIERARCHY | SAP_CON_LOADED | configuration | sap_con_hierarchy_code | Hierarchy code in CON |
| 10 | SAP_PRD_LOAD_STATUS | SAP_PRD_LOADED | configuration | sap_prd_load_status | PRD load result |
| 11 | SAP_PRD_LOAD_ACTOR | SAP_PRD_LOADED | configuration | sap_prd_load_actor | Who loaded PRD |
| 12 | SAP_PRD_HIERARCHY | SAP_PRD_LOADED | configuration | sap_prd_hierarchy_code | Hierarchy code in PRD |
| 13 | CON_VERIFIED | CON_VERIFIED | configuration | con_verification_status | CON verified status |
| 14 | SAP_CON_TEST_RESULT | SAP_CON_TESTED | configuration | sap_con_test_result | CON test result |
| 15 | SAP_CON_TEST_ENV | SAP_CON_TESTED | configuration | sap_con_test_environment | Test environment |
| 16 | MATERIAL_CREATED | MATERIAL_CREATED | material | material_status | Material creation event |
| 17 | MATERIAL_ACTIVATION_STATUS | MATERIAL_ACTIVATED | material | material_activation_status | Material ready status |
| 18 | MATERIAL_ACTIVATION_ACTOR | MATERIAL_ACTIVATED | material | material_activated_by | Who activated material |
| 19 | SKU_MINTED | SKU_MINTED | sku | sku_status | SKU minting event |
| 20 | SKU_ACTIVATED | SKU_ACTIVATED | sku | sku_activation_status | SKU ready status |
| 21 | TECHNICAL_REVIEW_RESULT | TECHNICAL_REVIEW | configuration | technical_review_result | Review outcome (PASS/NEGATIVE) |
| 22 | TECHNICAL_REVIEW_REASON | TECHNICAL_REVIEW | configuration | technical_review_reason | Reason (VALID ZERO - only if NEGATIVE) |
| 23 | PRICING_VALUE | PRICING_DETERMINED | sku | pricing_value_usd | Price in USD |
| 24 | PRICING_STATUS | PRICING_DETERMINED | sku | pricing_status | Pricing gate status |
| 25 | PRICING_UPLOAD_STATUS | PRICING_UPLOADED | configuration | pricing_upload_status | Upload status |
| 26 | PRICING_CONFIRMED | PRICING_CONFIRMED | sku | pricing_confirmed | Confirmation status |
| 27 | PRICING_PUBLISHED | PRICING_PUBLISHED | configuration | pricing_publication_status | Publication status |
| 28 | FINAL_PRICING_APPROVAL | FINAL_PRICING_APPROVAL | launch | final_pricing_approval_status | Pricing approval |
| 29 | FINAL_PRICING_AUTH | FINAL_PRICING_APPROVAL | launch | final_pricing_approval_authority | Approval authority |
| 30 | ZUPDM_APPROVED | ZUPDM_APPROVED | configuration | zupdm_approval_status | Supply chain approval |
| 31 | FULLY_APPROVED | FULLY_APPROVED | launch | all_gates_cleared | All gates cleared |
| 32 | GO_LIVE_APPROVAL_REQUESTED | GO_LIVE_APPROVAL_REQUESTED | launch | go_live_approval_requested | Request initiated |
| 33 | GO_LIVE_APPROVED | GO_LIVE_APPROVED | launch | go_live_approval_status | Approval decision |
| 34 | GO_LIVE_AUTH | GO_LIVE_APPROVED | launch | go_live_approval_authority | Approval authority |
| 35 | SUPPLY_CHAIN_NOTIFIED | SUPPLY_CHAIN_NOTIFIED | configuration | supply_chain_notification_status | Notification status |
| 36 | OVERNIGHT_PUSH_STATUS | OVERNIGHT_PUSH | configuration | overnight_push_status | Push result |
| 37 | OVERNIGHT_PUSH_DATE | OVERNIGHT_PUSH | configuration | overnight_push_run_date | Push execution date |
| 38 | CHANGE_TYPE | CHANGE_REQUESTED | launch | change_type | Type of change request |
| 39 | CHANGE_REASON | CHANGE_REQUESTED | launch | change_reason | Reason for request |
| 40 | CHANGE_REQUESTED_BY | CHANGE_REQUESTED | launch | change_requested_by | Who requested change |
| 41 | CHANGE_REQUESTER_ROLE | CHANGE_REQUESTED | launch | change_requester_role | Requester role |

**Total Approved**: 38 core + 3 CHANGE_REQUESTED properties = 41 total

---

## Semantic Rules

### 1. Lineage Preservation

Every Evidence row captures:
- `raw_event_id`: FK to exact raw event (traceability)
- `mapping_id`: Deterministic transformation rule applied
- `evidence_lineage`: JSONB metadata with extraction path (reproducibility)

**Idempotency guarantee**: Running transformation twice produces identical Evidence set.

### 2. 1:N Cardinality

One raw HIERARCHY_APPROVAL event produces FOUR Evidence rows:
```
Raw: HIERARCHY_APPROVAL with CON and PRD hierarchies
  ↓
Evidence: 
  1. HIERARCHY_APPROVAL_CON_CODE
  2. HIERARCHY_APPROVAL_CON_AUTH
  3. HIERARCHY_APPROVAL_PRD_CODE
  4. HIERARCHY_APPROVAL_PRD_AUTH
```

This preserves **SKU-003 contradiction**: Both H100 (CON) and H200 (PRD) coexist.

### 3. Absence Semantics (VALID ZERO)

**Rule**: Missing optional fields DO NOT generate Evidence.

Example (SKU-006):
```
Raw: TECHNICAL_REVIEW with review_result = undefined (absent)
  ↓
Evidence: NONE generated
(NOT: "TECHNICAL_REVIEW_RESULT" = "REJECTED")
```

This is NOT an error; it's **semantic absence preservation**.

### 4. Explicit Negatives (SKU-013)

**Rule**: Preserve explicit NEGATIVE/REJECTED values exactly.

Example:
```
Raw: TECHNICAL_REVIEW with review_result = "NEGATIVE" and reason present
  ↓
Evidence:
  1. TECHNICAL_REVIEW_RESULT = "NEGATIVE" (explicit)
  2. TECHNICAL_REVIEW_REASON = "Configuration conflicts..." (explanation)
```

**Value fidelity**: No normalization. "REJECTED" stays "REJECTED", not "NEGATIVE".

### 5. Contradiction Preservation

**Rule**: Different raw events asserting different values coexist as separate Evidence rows.

Example (SKU-003 extended):
```
Raw Event #1: HIERARCHY_APPROVAL → H100
Raw Event #2: HIERARCHY_APPROVAL → H200 (later)

Evidence:
  Row A: (raw_id=1, mapping=HIERARCHY_APPROVAL_CON_CODE, value=H100)
  Row B: (raw_id=2, mapping=HIERARCHY_APPROVAL_PRD_CODE, value=H200)
```

Both survive. Assertions layer (NOT implemented) will later resolve contradictions.

### 6. Timestamp Semantics

Preserved independently:
- `occurred_at`: Business event time (when market decision was made)
- `recorded_at`: Source system record time (when logged)
- `arrival_at`: Platform availability time (when we saw it)

**Arrival_at delta preservation**:
- On-time arrival: `arrival_at = occurred_at`
- Delayed arrival: `arrival_at > occurred_at` (preserved as Data)
- Out-of-order arrival: `arrival_at < occurred_at` (preserved as Data)

Idempotency key (raw_event_id, mapping_id) is **independent of temporal fields**.

### 7. Source Provenance (NOT raw.source_system)

Source system is **derived from mapping definition**, not copied from raw.source_system:

| Mapping Family | Logical Source | Examples |
|---|---|---|
| PRODUCT_INTENT_* | product_intent | Market intent signals |
| HIERARCHY_APPROVAL_* | approval_workflow | Approval authority decisions |
| SAP_CON_* | sap_con | CON system observations |
| SAP_PRD_* | sap_prd | PRD system observations |
| TECHNICAL_REVIEW_* | technical_gate | Technical verification gate |
| PRICING_* | pricing_gate | Pricing decision flow |
| MATERIAL_* | material_lifecycle | Material operational readiness |
| SKU_* | sku_lifecycle | SKU operational readiness |
| ZUPDM_* / SUPPLY_CHAIN_* | supply_chain_gate | Supply chain approval/notification |
| GO_LIVE_* | approval_gate | Go-live approval authority |
| FULLY_APPROVED | composite_gate | All gates composite |
| OVERNIGHT_PUSH_* | data_push | Scheduled data push |
| CHANGE_* | product_intent | Product intent change request |

---

## Implementation Details

### Files

- **mappings.sql** (~400 lines): Authoritative catalogue of 38-41 approved mapping_ids with deterministic definitions
- **raw_to_evidence.sql** (~1800 lines): PostgreSQL function `runtime.process_raw_to_evidence()` implementing transformation for 23+ event types
- **validation.sql** (~600 lines): 15 read-only verification queries for post-execution audit
- **test_evidence.sql**: Verifies raw count (169), Evidence count (>0), Assertions/Fold (0)
- **test_idempotency.sql**: Executes transformation twice, verifies count unchanged
- **test_lineage.sql**: Checks raw_event_id FK, mapping_id non-NULL, no orphans
- **test_scenarios.sql**: Validates SKU-003/006/010/011/012/013 and CHANGE_REQUESTED special cases

### Schema

**runtime.evidence** table structure:
```
evidence_id                uuid          PRIMARY KEY
raw_event_id               uuid          NOT NULL, FK → raw.raw_event
mapping_id                 varchar       NOT NULL (deterministic)
evidence_type              varchar       NOT NULL (category)
subject_type               varchar       NOT NULL (launch|configuration|sku|material)
subject_id                 varchar       NOT NULL (LAUNCH-001, CON-001, SKU-003, etc.)
property_name              varchar       NOT NULL (observable property)
asserted_value             text          NULLABLE (observed value or NULL if value_json used)
value_type                 varchar       NOT NULL (string|boolean|timestamp|reference)
value_json                 jsonb         NULLABLE (complex/structured values)
source_system              varchar       NOT NULL (derived from mapping: product_intent, approval_workflow, etc.)
source_actor_id            varchar       NULLABLE (who/what made observation)
source_actor_role          varchar       NULLABLE (actor role context)
occurred_at                timestamp     NOT NULL (business event time)
recorded_at                timestamp     NOT NULL (source record time)
arrival_at                 timestamp     NOT NULL (platform availability time)
simulator_classification   varchar       NULLABLE (claris simulator class)
evidence_reason            text          NULLABLE (why this observation matters)
evidence_lineage           jsonb         NULLABLE (extraction_path, source_field, derivation)
created_at                 timestamp     DEFAULT CURRENT_TIMESTAMP

UNIQUE (raw_event_id, mapping_id)  -- Idempotency key
```

---

## Execution

### 1. Load Mapping Catalogue
```sql
\i mappings.sql
```

### 2. Execute Raw → Evidence Transformation
```sql
SELECT * FROM runtime.process_raw_to_evidence();
```

Expected output:
```
| status_message | raw_count | evidence_count_before | evidence_count_after | evidence_inserted |
|---|---|---|---|---|
| Transformation completed | 169 | X | Y | Y-X |
```

### 3. Verify Raw Event Count
```sql
SELECT COUNT(*) FROM raw.raw_event;  -- Expected: 169
```

### 4. Verify Evidence Count
```sql
SELECT COUNT(*) FROM runtime.evidence;  -- Expected: 300-400 (1:N cardinality)
```

### 5. Run Validation Queries
```sql
\i validation.sql
```

All 15 validation sections should show `status_ok = true`.

### 6. Execute Transformation AGAIN (idempotency test)
```sql
SELECT * FROM runtime.process_raw_to_evidence();  -- Should insert 0 rows
```

Expected: `evidence_inserted = 0` (no duplicates)

### 7. Run Test Suite
```sql
\i test_evidence.sql
\i test_idempotency.sql
\i test_lineage.sql
\i test_scenarios.sql
```

All tests should pass without errors.

---

## Known Limitations & Gaps

### VALID ZERO (Expected Behavior)

**TECHNICAL_REVIEW_REASON** only generates Evidence if:
1. `review_result = 'NEGATIVE'` (or similar rejection)
2. AND `reason` field is present in payload

**Absence is not fabricated**:
- Raw event with no reason field → NO Evidence row generated
- Raw event with NEGATIVE result but no reason → NO Evidence row generated (reason omitted, not rejected)

This is by design. See **Explicit Negatives** section above.

### Event Type Reconciliation

25 event types in corpus → 20 event types with mapping definitions (in COMPLETE_MAPPING_MATRIX.md)

**Reconciliation Status**:
- PRODUCT_INTENT_CREATED: ✓ Mapped (2 mappings)
- HIERARCHY_APPROVAL: ✓ Mapped (4 mappings)
- SAP_CON_LOADED: ✓ Mapped (3 mappings)
- SAP_PRD_LOADED: ✓ Mapped (3 mappings)
- CON_VERIFIED: ✓ Mapped (1 mapping)
- SAP_CON_TESTED: ✓ Mapped (2 mappings)
- MATERIAL_CREATED: ✓ Mapped (1 mapping)
- MATERIAL_ACTIVATED: ✓ Mapped (2 mappings)
- SKU_MINTED: ✓ Mapped (1 mapping)
- SKU_ACTIVATED: ✓ Mapped (1 mapping)
- TECHNICAL_REVIEW: ✓ Mapped (1-2 mappings, conditional)
- PRICING_DETERMINED: ✓ Mapped (2 mappings)
- PRICING_UPLOADED: ✓ Mapped (1 mapping)
- PRICING_CONFIRMED: ✓ Mapped (1 mapping)
- PRICING_PUBLISHED: ✓ Mapped (1 mapping)
- FINAL_PRICING_APPROVAL: ✓ Mapped (2 mappings)
- ZUPDM_APPROVED: ✓ Mapped (1 mapping)
- FULLY_APPROVED: ✓ Mapped (1 mapping)
- GO_LIVE_APPROVAL_REQUESTED: ✓ Mapped (1 mapping)
- GO_LIVE_APPROVED: ✓ Mapped (2 mappings)
- SUPPLY_CHAIN_NOTIFIED: ✓ Mapped (1 mapping)
- OVERNIGHT_PUSH: ✓ Mapped (2 mappings)
- CHANGE_REQUESTED: ✓ Mapped (4 mappings)

**5 event types not yet mapped** (do they exist in corpus?):
- SKU_LIFECYCLE (conflated with SKU_MINTED/SKU_ACTIVATED?)
- SAP_CON_PROMOTED / SAP_PRD_PROMOTED (similar to _LOADED events?)
- (Others TBD pending event type corpus inspection)

---

## Execution Results

**Transformation Execution**: Not yet run in this session  
**Expected Evidence Count**: ~300-400 rows (169 raw events → multiple observations via 38-41 mappings)  
**Expected Assertions Count**: 0 (NOT STARTED)  
**Expected Fold Count**: 0 (NOT STARTED)  

---

## Next Steps (NOT Implemented)

After Evidence layer is complete and validated:

1. **Assertions Layer**: Define business rules to resolve contradictions and assign canonical values
2. **Fold Layer**: Snapshot canonical state at meaningful time horizons
3. **Projection Layer**: Forecast future states based on patterns
4. **Workbench**: Interactive exploration interface
5. **Agents**: Automated monitoring and alerting

**Current Scope**: STOP after Evidence. Do NOT implement Assertions or downstream layers.

---

## Debugging

### If Evidence count is 0
- Check raw_to_evidence.sql for syntax errors
- Verify raw.raw_event table is populated (SELECT COUNT(*) FROM raw.raw_event should be 169)
- Check PostgreSQL logs for constraint violations or FK issues
- Run validation.sql to identify NULL/empty mapping_ids

### If Evidence count is much lower than expected
- Check for events without matching mappings
- Review test_scenarios.sql output to identify missing event types
- Verify JSONB unnesting in HIERARCHY_APPROVAL / CHANGE_REQUESTED logic

### If Idempotency test fails
- Check for ON CONFLICT clause in INSERT statements
- Verify (raw_event_id, mapping_id) UNIQUE constraint exists
- Look for duplicate mapping_ids being generated dynamically (should not happen - all 38 pre-approved)

---

**Author**: Claude Haiku 4.5  
**Date**: 2026-09-06  
**Status**: Ready for Execution
