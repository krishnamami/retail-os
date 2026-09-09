# Complete Evidence Mapping Matrix (Revised)
## Raw → Evidence Field-Level Transformation

**Status**: Ready for Approval  
**Last Revised**: 2026-09-06  
**Deployed Evidence Identity**: `(raw_event_id, mapping_id)` (LINEAGE-BASED)  
**Idempotency Constraint**: `UNIQUE (raw_event_id, mapping_id)` (UPDATED 2026-09-06)  
**Raw Records**: 169  
**Expected Evidence Rows**: 180-220 (estimated, subject to event-specific mapping rules)  
**Note**: Prior documentation referenced obsolete arrival_at-based idempotency. This has been CORRECTED.

---

## 1. Mapping Principles (Corrected)

### Principle 1: Evidence Identity & Idempotency (CORRECTED)
```sql
-- DEPLOYED CONSTRAINT (LINEAGE-BASED):
UNIQUE (raw_event_id, mapping_id)

-- IDEMPOTENCY STRATEGY:
INSERT INTO runtime.evidence (raw_event_id, mapping_id, ...)
VALUES (...)
ON CONFLICT (raw_event_id, mapping_id)
DO NOTHING
```

**Semantics**:
- Evidence identity is deterministic based on Raw lineage: `(raw_event_id, mapping_id)`
- `mapping_id`: Deterministic identifier for each observable property extraction rule (38 approved mappings)
- `raw_event_id`: Foreign key to originating raw.raw_event (immutable)
- `arrival_at`: Temporal provenance field (NOT part of identity)
- **Contradictions Preserved**: Different raw_event_ids for the same subject/property both survive as separate Evidence rows
- **Timestamp Independence**: arrival_at and occurred_at are preserved independently for historical Fold evaluation

**Prior Documentation Note**: Earlier versions referenced `UNIQUE (subject_type, subject_id, property_name, arrival_at)` as the idempotency key. This was INCORRECT. The corrected model uses raw_event_id + mapping_id as Evidence identity.

### Principle 2: Source Authority (Payload-Based)
- **NOT** raw.raw_event.source_system (which is "claris" for 168 events, inserted by loader)
- **EXTRACT** from payload fields:
  - approval_authority → Evidence.source_actor_id
  - loaded_by → Evidence.source_actor_id
  - status_changed_by → Evidence.source_actor_id
  - process_step → Evidence.source_actor_role
  - actor_id/actor_role (raw columns) → Evidence.source_actor_id/source_actor_role (for product_intent)

### Principle 3: Subject Identification
| Subject Type | Primary Source | Fallback | Example |
|---|---|---|---|
| launch | raw.launch_id | payload.launch_id | LAUNCH-001 |
| configuration | raw.con_id OR raw.prd_id | payload | CON-001, PRD-001 |
| sku | raw.sku_id | payload.sku_id | SKU-003 |
| material | raw.material_id | payload.material_id | MATERIAL-001 |

### Principle 4: Observable Property Selection
- Extract ONLY properties that represent meaningful business observations
- NOT every payload field → one Evidence property
- Multiple properties from one payload IF they represent distinct business facts

### Principle 5: Contradiction & Absence Handling (Lineage-Aware)
- **Contradiction Preserved**: When different raw_event_ids (from different source observations) assert different values for the same subject/property, both Evidence rows survive. They have the same (subject_type, subject_id, property_name) but different (raw_event_id, mapping_id) identities.
  - Example (SKU-003): Raw Event A asserts hierarchy_code=H100, Raw Event B asserts hierarchy_code=H200. Both exist. Identity prevents only duplicates where raw_event_id AND mapping_id are identical.
- **Absence NOT Generated**: If payload lacks a required extraction field, do NOT create Evidence with NULL/default value. No Evidence row is created.
  - Example (SKU-006): If technical_review source observation is absent in payload, no Evidence row is created (VALID ZERO).
- **Explicit Negatives Preserved**: Explicit negative/rejection observations (e.g., technical_approval_status = "REJECTED") create Evidence rows with the actual value.
  - Example (SKU-013): technical_approval_status = "REJECTED" is preserved as-is (not normalized).
- **Absence vs. Negative Are Semantically Distinct**: 
  - SKU-006: No technical review observation in source → no Evidence row
  - SKU-013: Explicit technical review rejection in source → Evidence row with value "REJECTED"

---

## 2. Event Type Mappings (Complete)

### Event: PRODUCT_INTENT_CREATED
**Count**: 13  
**Subject**: launch  
**Source System**: claris (raw col)  
**Authority**: process_step (payload)

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Product intent created | payload.product_intent_id | subject_id | string | launch_id |
| Intent classification | payload.intent_class OR "market_expansion" | property: intent_classification | string | Market intent type |

**Evidence Rows Per Event**: 2  
**Idempotency**: (subject=launch, subject_id=LAUNCH-xxx, property=product_intent_id, arrival_at=...)  

**SQL Logic**:
```sql
INSERT INTO runtime.evidence (raw_event_id, evidence_type, subject_type, subject_id, 
  property_name, asserted_value, value_type, source_actor_role, occurred_at, 
  recorded_at, arrival_at, source_system)
SELECT 
  raw_event_id, 
  'product_intent', 
  'launch', 
  launch_id,
  'product_intent_id',
  payload->>'product_intent_id',
  'string',
  payload->>'process_step',
  occurred_at, recorded_at, arrival_at,
  source_system
FROM raw.raw_event
WHERE event_type = 'PRODUCT_INTENT_CREATED'
```

---

### Event: HIERARCHY_APPROVAL
**Count**: 13  
**Subject**: launch (may produce 2 rows if both CON and PRD hierarchies present)  
**Source System**: claris  
**Authority**: approval_authority (payload) → source_actor_id

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| CON hierarchy code | payload.hierarchy_approvals[CON].hierarchy_code | property: hierarchy_code_con | string | CON-specific |
| CON approval authority | payload.hierarchy_approvals[CON].approval_authority | source_actor_id | string | Who approved CON |
| PRD hierarchy code | payload.hierarchy_approvals[PRD].hierarchy_code | property: hierarchy_code_prd | string | PRD-specific |
| PRD approval authority | payload.hierarchy_approvals[PRD].approval_authority | source_actor_id | string | Who approved PRD |

**Evidence Rows Per Event**: 2-4 (one per hierarchy + authority)  
**Idempotency**: (subject=launch, property=hierarchy_code_con/prd, arrival_at=...)  
**Special Handling**: Extract each environment's hierarchy as separate property to preserve SKU-003 contradiction

**SQL Logic**: UNNEST payload.hierarchy_approvals array, create row per environment

---

### Event: SAP_CON_LOADED
**Count**: 13  
**Subject**: configuration (con_id)  
**Source System**: claris  
**Authority**: loaded_by (payload) → source_actor_id

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| CON load status | payload.con_status OR "SUCCESS" | property: sap_con_load_status | string | Load result |
| SAP loader actor | payload.loaded_by | source_actor_id | string | Which system/process |
| Hierarchy code loaded | payload.hierarchy_code | property: sap_con_hierarchy | string | Content loaded |

**Evidence Rows Per Event**: 3  
**Idempotency**: (subject=configuration, subject_id=CON-xxx, property=sap_con_load_status, arrival_at=...)

---

### Event: SAP_PRD_LOADED
**Count**: 9  
**Subject**: configuration (prd_id)  
**Source System**: claris  
**Authority**: loaded_by (payload) → source_actor_id

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| PRD load status | payload.prd_status OR "SUCCESS" | property: sap_prd_load_status | string | Load result |
| SAP loader actor | payload.loaded_by | source_actor_id | string | Which system/process |
| Hierarchy code loaded | payload.hierarchy_code | property: sap_prd_hierarchy | string | Content loaded |

**Evidence Rows Per Event**: 3

---

### Event: CON_VERIFIED
**Count**: 9  
**Subject**: configuration (con_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| CON verification status | "VERIFIED" | property: con_verification_status | string | Gate pass |

**Evidence Rows Per Event**: 1

---

### Event: SAP_CON_TESTED
**Count**: 4  
**Subject**: configuration (con_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Test result | payload.test_result OR "PASS" | property: sap_con_test_result | string | PASS or FAIL |
| Test environment | payload.test_environment | property: sap_con_test_env | string | Which env tested |

**Evidence Rows Per Event**: 2

---

### Event: MATERIAL_CREATED
**Count**: 3  
**Subject**: material (material_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Material created | "CREATED" | property: material_status | string | Creation event |

**Evidence Rows Per Event**: 1

---

### Event: MATERIAL_ACTIVATED
**Count**: 11  
**Subject**: material (material_id)  
**Source System**: claris  
**Authority**: status_changed_by (payload) → source_actor_id

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Activation status | payload.material_status OR "ACTIVE" | property: material_activation_status | string | ACTIVE/INACTIVE |
| Who activated | payload.status_changed_by | source_actor_id | string | Actor ID |

**Evidence Rows Per Event**: 2

---

### Event: SKU_MINTED
**Count**: 9  
**Subject**: sku (sku_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| SKU minted | "MINTED" | property: sku_status | string | Creation/minting |

**Evidence Rows Per Event**: 1

---

### Event: SKU_ACTIVATED
**Count**: 4  
**Subject**: sku (sku_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| SKU activation status | "ACTIVATED" | property: sku_activation_status | string | Operational readiness |

**Evidence Rows Per Event**: 1

---

### Event: TECHNICAL_REVIEW
**Count**: 9  
**Subject**: configuration (con_id OR prd_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Review result | payload.review_result OR "PASS" | property: technical_review_result | string | PASS/NEGATIVE/PENDING |
| Review reason (if negative) | payload.review_reason | property: technical_review_reason | text | Only if NEGATIVE |

**Evidence Rows Per Event**: 1-2 (reason only if NEGATIVE)  
**Special**: If review_result absent → 0 rows (SKU-006). If NEGATIVE → include reason (SKU-013)

---

### Event: PRICING_DETERMINED
**Count**: 8  
**Subject**: sku (sku_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Pricing determined | payload.determined_price_usd | property: pricing_value | string | Price in USD |
| Pricing status | "DETERMINED" | property: pricing_status | string | Status |

**Evidence Rows Per Event**: 2

---

### Event: PRICING_UPLOADED
**Count**: 8  
**Subject**: configuration (con_id OR prd_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Pricing upload status | "UPLOADED" | property: pricing_upload_status | string | Upload state |

**Evidence Rows Per Event**: 1

---

### Event: PRICING_CONFIRMED
**Count**: 3  
**Subject**: sku (sku_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Pricing confirmation | "CONFIRMED" | property: pricing_confirmed | string | Confirmation gate |

**Evidence Rows Per Event**: 1

---

### Event: PRICING_PUBLISHED
**Count**: 3  
**Subject**: configuration (con_id OR prd_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Publishing status | "PUBLISHED" | property: pricing_publication_status | string | Publication state |

**Evidence Rows Per Event**: 1

---

### Event: FINAL_PRICING_APPROVAL
**Count**: 9  
**Subject**: launch (launch_id)  
**Source System**: claris  
**Authority**: approval_authority (payload) → source_actor_id

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Approval status | "APPROVED" | property: final_pricing_approval | string | Gate decision |
| Approval authority | payload.approval_authority | source_actor_id | string | Who approved |

**Evidence Rows Per Event**: 2

---

### Event: ZUPDM_APPROVED
**Count**: 9  
**Subject**: configuration (con_id OR prd_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| ZUPDM approval | "APPROVED" | property: zupdm_approval_status | string | Gate decision |

**Evidence Rows Per Event**: 1

---

### Event: FULLY_APPROVED
**Count**: 9  
**Subject**: launch (launch_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| All gates cleared | "APPROVED" | property: all_gates_cleared | string | Composite gate |

**Evidence Rows Per Event**: 1

---

### Event: GO_LIVE_APPROVAL_REQUESTED
**Count**: 2  
**Subject**: launch (launch_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Go-live requested | "REQUESTED" | property: go_live_approval_requested | string | Gate initiation |

**Evidence Rows Per Event**: 1

---

### Event: GO_LIVE_APPROVED
**Count**: 3  
**Subject**: launch (launch_id)  
**Source System**: claris  
**Authority**: approval_authority (payload) → source_actor_id

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Go-live approval | "APPROVED" | property: go_live_approved | string | Gate decision |
| Approval authority | payload.approval_authority | source_actor_id | string | Who approved |

**Evidence Rows Per Event**: 2

---

### Event: SUPPLY_CHAIN_NOTIFIED
**Count**: 2  
**Subject**: configuration (con_id OR prd_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Notification status | "NOTIFIED" | property: supply_chain_notification_status | string | Downstream notice |

**Evidence Rows Per Event**: 1

---

### Event: OVERNIGHT_PUSH
**Count**: 11  
**Subject**: configuration (con_id OR prd_id)  
**Source System**: claris  
**Authority**: process_step → source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Push status | payload.push_event_type OR "EXECUTED" | property: overnight_push_status | string | Push result |
| Push run date | payload.push_run_date | property: overnight_push_date | string | Execution date |

**Evidence Rows Per Event**: 2

---

### Event: CHANGE_REQUESTED
**Count**: 1  
**Subject**: launch (launch_id)  
**Source System**: product_intent (payload field, authoritative)  
**Authority**: actor_id, actor_role (raw columns) → source_actor_id, source_actor_role

| Observable | Source Path | Evidence Column | Type | Notes |
|---|---|---|---|---|
| Change type | payload.change_type | property: change_type | string | Type of change |
| Change reason | payload.change_reason | evidence_reason | text | Why change requested |
| Changed by | raw.actor_id OR payload.actor_id | source_actor_id | string | Who requested |
| Actor role | raw.actor_role OR payload.actor_role | source_actor_role | string | Actor context |

**Evidence Rows Per Event**: 4 (or 3 if no reason)  
**Special**: source_system = payload.source_system (product_intent), NOT raw.source_system

---

## 3. Evidence Lineage Structure

```json
{
  "raw_event_id": "uuid",
  "event_type": "HIERARCHY_APPROVAL",
  "source_path": "payload.hierarchy_approvals[0].hierarchy_code",
  "mapping_identity": "hierarchy_code_con",
  "extraction_rule": "unnest hierarchy_approvals, extract [CON].hierarchy_code",
  "source_authority_field": "approval_authority"
}
```

- NOT a full copy of raw payload (preserved via raw_event_id FK)
- Structured lineage metadata for debugging/tracing
- Identifies exact extraction path for reproducibility

---

## 4. Evidence Type Classification

```
evidence_type = extracted from event_type + property_name:
  - product_intent
  - hierarchy
  - sap_load
  - verification
  - testing
  - material
  - pricing
  - activation
  - gates (approval, go_live)
  - supply_chain
  - change_management
```

---

## 5. INSERT Idempotency Strategy (LINEAGE-BASED)

```sql
-- DEPLOYED CONSTRAINT:
INSERT INTO runtime.evidence (raw_event_id, mapping_id, ...)
VALUES (...)
ON CONFLICT (raw_event_id, mapping_id)
DO NOTHING
```

**Evidence Identity**: (raw_event_id, mapping_id)  
**NOT**: (subject_type, subject_id, property_name, arrival_at) ← This was incorrect and has been replaced.

**Why This Works**:
- `raw_event_id`: Uniquely identifies the source observation (immutable)
- `mapping_id`: Uniquely identifies the extraction rule (38 deterministic approved mappings)
- Together they prevent true duplicates while preserving contradictions
- Same subject/property CAN have multiple Evidence rows if from different raw_event_ids
- `arrival_at` is preserved as temporal provenance, not as identity

**Example (SKU-003 Contradiction Preservation)**:
- Raw Event A (raw_event_id=UUID-1) asserts: hierarchy_code = H100 (mapping_id=HIERARCHY_APPROVAL_CON_CODE)
- Raw Event B (raw_event_id=UUID-2) asserts: hierarchy_code = H200 (mapping_id=HIERARCHY_APPROVAL_PRD_CODE)
- Both rows exist because (UUID-1, HIERARCHY_APPROVAL_CON_CODE) ≠ (UUID-2, HIERARCHY_APPROVAL_PRD_CODE)
- ON CONFLICT only prevents inserting the exact same (raw_event_id, mapping_id) tuple twice

**Enables**:
- SKU-010 (delayed arrival): Same raw_event + mapping can arrive late; second insert is idempotent (DO NOTHING)
- SKU-011 (out-of-order): Different raw_events preserve their temporal relationships independently
- SKU-012 (multiple horizons): Different arrival_at times preserved for historical Fold evaluation

---

## 6. Estimated Evidence Row Count

**Per Event Type** (based on properties per event):
- HIERARCHY_APPROVAL: 13 events × 2-4 rows = 26-52 rows
- SAP_CON_LOADED: 13 × 3 = 39 rows
- SAP_PRD_LOADED: 9 × 3 = 27 rows
- CON_VERIFIED: 9 × 1 = 9 rows
- SKU_MINTED: 9 × 1 = 9 rows
- MATERIAL_ACTIVATED: 11 × 2 = 22 rows
- TECHNICAL_REVIEW: 9 × 1-2 = 9-18 rows
- PRICING events: ~20 rows
- FINAL_PRICING_APPROVAL: 9 × 2 = 18 rows
- FULLY_APPROVED: 9 × 1 = 9 rows
- GO_LIVE: 5 × 1-2 = 5-10 rows
- PRODUCT_INTENT_CREATED: 13 × 2 = 26 rows
- CHANGE_REQUESTED: 1 × 4 = 4 rows
- Other events: ~30 rows

**Total Estimate**: 180-230 Evidence rows from 169 Raw events

---

## 7. Approval Checklist

- [ ] Idempotency key corrected to `(subject_type, subject_id, property_name, arrival_at)`
- [ ] Source authority extraction from payload confirmed (NOT raw.source_system for claris)
- [ ] Event-type mappings reviewed for accuracy
- [ ] Subject identification rules clear (launch/config/sku/material)
- [ ] Contradiction/absence/negative preservation rules confirmed
- [ ] Evidence lineage structure accepted
- [ ] Ready to proceed with raw_to_evidence.sql implementation

---

## 8. Files in repository/evidence/

```
database/evidence/
├── inspect_schema.py                    (Schema inspection script - executed)
├── audit_source_provenance.py           (Provenance audit script - executed)
├── MAPPING_MATRIX.md                    (Initial mapping matrix - SUPERSEDED)
├── PROVENANCE_AUDIT_FINDINGS.md         (Audit results and corrections)
├── COMPLETE_MAPPING_MATRIX.md           (This file - ready for approval)
├── raw_to_evidence.sql                  (To be created after approval)
├── mappings.sql                         (To be created after approval)
├── validation.sql                       (To be created after approval)
└── README.md                            (To be created after approval)
```

