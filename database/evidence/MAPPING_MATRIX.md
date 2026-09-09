# Evidence Mapping Matrix
## Raw → Evidence Transformation Design

**Status**: Design Phase (awaiting approval)  
**Raw Records**: 169  
**Evidence Records**: 0 (to be generated)  
**Timestamp**: 2026-09-06

---

## 1. Evidence Semantic Contract

**Raw** = "What record/event did the source emit?"  
**Evidence** = "What observable business fact(s) does that source record provide?"

**Cardinality**: 1 raw event → 0..N evidence observations

- A raw record can produce NO Evidence if it contains no relevant business observation
- A raw record can produce ONE Evidence row for a single observed property
- A raw record can produce MULTIPLE Evidence rows when it contains multiple observable properties

---

## 2. runtime.evidence Table Structure

```
evidence_id          uuid           PRIMARY KEY (auto-generated)
raw_event_id         uuid           NOT NULL, FK → raw.raw_event
evidence_type        varchar        NOT NULL (e.g., "hierarchy_approval", "pricing", "supply_chain")
subject_type         varchar        NOT NULL (e.g., "launch", "configuration", "sku", "material")
subject_id           varchar        NOT NULL (e.g., LAUNCH-001, SKU-003, MATERIAL-001)
property_name        varchar        NOT NULL (e.g., "hierarchy_code", "pricing_authority", "activation_status")
asserted_value       text           NULLABLE (e.g., "H100", "SIMULATED/product-council", "ACTIVE")
value_type           varchar        NOT NULL (e.g., "string", "boolean", "timestamp", "reference")
value_json           jsonb          NULLABLE (for complex/structured values)
source_system        varchar        NOT NULL (e.g., "claris", "product_intent")
source_actor_id      varchar        NULLABLE (e.g., user ID, system ID)
source_actor_role    varchar        NULLABLE (e.g., "product_manager", "automated")
occurred_at          timestamp      NOT NULL (when the business event occurred)
recorded_at          timestamp      NOT NULL (when the event was recorded in source)
arrival_at           timestamp      NOT NULL (when the event arrived at our system)
simulator_classification  varchar   NULLABLE (claris simulator classification)
evidence_reason      text           NULLABLE (why this observation matters, lineage notes)
evidence_lineage     jsonb          NULLABLE (detailed derivation path from raw payload)
created_at           timestamp      NOT NULL (DEFAULT CURRENT_TIMESTAMP)
```

---

## 3. Raw Event Types and Proposed Evidence Extraction

### Event Type Catalog (24 claris + 1 product_intent)

| Event Type | Count | Primary Subject | Observable Properties | Notes |
|---|---|---|---|---|
| **PRODUCT_INTENT_CREATED** | 13 | launch | product_intent_id, intent_classification | Market-facing intent, drive observable |
| **HIERARCHY_APPROVAL** | 13 | launch | hierarchy_code, approval_authority | CON/PRD hierarchy, approval source |
| **SAP_CON_LOADED** | 13 | configuration | con_id, sap_status, load_timestamp | CON-specific data load |
| **MATERIAL_ACTIVATED** | 11 | material | material_id, activation_status, activated_by | Material readiness |
| **OVERNIGHT_PUSH** | 11 | configuration | push_status, target_environment | Scheduled data push |
| **PRICING_DETERMINED** | 8 | launch | pricing_authority, pricing_status | Pricing decision authority |
| **PRICING_UPLOADED** | 8 | configuration | pricing_file_reference, upload_status | Pricing artifact tracking |
| **FINAL_PRICING_APPROVAL** | 9 | launch | approval_authority, final_pricing_status | Pricing gates |
| **SAP_PRD_LOADED** | 9 | configuration | prd_id, sap_status, load_timestamp | PRD-specific data load |
| **SKU_MINTED** | 9 | sku | sku_id, minting_authority | SKU creation event |
| **ZUPDM_APPROVED** | 9 | configuration | zupdm_approval_status, approval_timestamp | Supply chain approval |
| **TECHNICAL_REVIEW** | 9 | configuration | review_result (✓/✗/negative), reviewer_authority | Technical gate (can be negative) |
| **CON_VERIFIED** | 9 | configuration | con_verification_status, verified_by | CON content validation |
| **FULLY_APPROVED** | 9 | launch | approval_status, all_gates_cleared | Composite gate status |
| **MATERIAL_CREATED** | 3 | material | material_id, creation_timestamp | Material lineage |
| **PRICING_CONFIRMED** | 3 | configuration | pricing_confirmation_status | Pricing finalization |
| **PRICING_PUBLISHED** | 3 | configuration | publication_status, published_to_system | Pricing availability |
| **SKU_ACTIVATED** | 4 | sku | sku_activation_status, activated_by | SKU operational readiness |
| **SAP_CON_TESTED** | 4 | configuration | test_result (✓/✗), test_environment | CON testing |
| **SAP_PRD_PROMOTED** | 4 | configuration | promotion_status, target_environment | PRD promotion |
| **GO_LIVE_APPROVAL_REQUESTED** | 2 | launch | approval_requested_by, approval_timestamp | Gate initiation |
| **GO_LIVE_APPROVED** | 3 | launch | approval_authority, approval_status | Gate decision |
| **SUPPLY_CHAIN_NOTIFIED** | 2 | configuration | notification_status, notified_party | Downstream notification |
| **CHANGE_REQUESTED** | 1 | launch | change_type, change_reason, changed_by | Product intent: proposed modification |

---

## 4. Critical Mapping Rules

### 4.1 Subject Identification

Extract `subject_type` and `subject_id` from raw event according to primary entity:

| Subject Type | Source Fields (priority order) | Example |
|---|---|---|
| **launch** | `launch_id` → (payload might override) | LAUNCH-001 |
| **configuration** | `con_id` OR `prd_id` (check both) | CON-001, PRD-001 |
| **sku** | `sku_id` | SKU-003 |
| **material** | `material_id` | MATERIAL-001 |

### 4.2 Hierarchy Observation Preservation (SKU-003 Example)

**Rule**: When a raw event provides observations about BOTH CON and PRD hierarchies for the same launch, **create separate Evidence rows**.

```
Raw event: HIERARCHY_APPROVAL
  launch_id: LAUNCH-001
  payload:
    hierarchy_approvals:
      - environment: CON
        hierarchy_code: H100
        approved_by: SIMULATED/strategy-board
      - environment: PRD
        hierarchy_code: H200
        approved_by: SIMULATED/product-council

Evidence rows (2 rows from 1 raw event):
1. subject_id=LAUNCH-001, property_name=hierarchy_code_con, asserted_value=H100
2. subject_id=LAUNCH-001, property_name=hierarchy_code_prd, asserted_value=H200
```

### 4.3 Absence Preservation (SKU-006 Example)

**Rule**: Do NOT generate Evidence for missing observations.

```
Raw event: TECHNICAL_REVIEW
  payload:
    s12_review: <absent>
    other_review: PASS

Evidence generated:
1. property_name=other_review, asserted_value=PASS
   (NOT: property_name=s12_review, asserted_value=REJECTED)
```

### 4.4 Negative Observation Preservation (SKU-013 Example)

**Rule**: Preserve explicit negative/rejection observations as distinct Evidence.

```
Raw event: TECHNICAL_REVIEW (SKU-013)
  payload:
    result: NEGATIVE
    reason: "Configuration conflicts with supply chain constraints"

Evidence generated:
1. property_name=technical_review_result, asserted_value=NEGATIVE
2. property_name=technical_review_reason, asserted_value="Configuration conflicts..."
   
vs. SKU-006:
1. property_name=other_review, asserted_value=PASS
   (no negative review = absence, not negative result)
```

### 4.5 Timestamp Preservation

**Rule**: Preserve arrival_at deltas and out-of-order arrival patterns.

```
Raw records for LAUNCH-001 with different arrival_at values:
- occurred_at: 2026-06-10, arrival_at: 2026-06-10 (on-time)
- occurred_at: 2026-06-10, arrival_at: 2026-06-11 (delayed by 1 day)
- occurred_at: 2026-06-10, arrival_at: 2026-06-09 (out-of-order, pre-occurred)

Evidence lineage must preserve these distinct arrival_at values.
Idempotency key: (raw_event_id + subject + property)
NOT: (subject + property) alone (would collapse distinct arrival_at)
```

---

## 5. Event-Type-Specific Mapping Details

### PRODUCT_INTENT_CREATED
- **Subjects**: launch
- **Properties**: 
  - `product_intent_id` → asserted_value
  - `intent_classification` → asserted_value (e.g., "market_expansion", "cost_optimization")

### HIERARCHY_APPROVAL
- **Subjects**: launch (may have both CON and PRD)
- **Properties**:
  - For each hierarchy in payload:
    - `hierarchy_code_{env}` → asserted_value (H100, H200)
    - `hierarchy_approval_authority_{env}` → source_actor_id
- **Lineage**: Track approval source (SIMULATED/strategy-board vs SIMULATED/product-council)

### SAP_CON_LOADED / SAP_PRD_LOADED
- **Subjects**: configuration (con_id or prd_id)
- **Properties**:
  - `sap_load_status` → asserted_value (SUCCESS, FAILURE, PENDING)
  - `load_timestamp` → occurred_at
  - `target_sap_environment` → value_json (environment details)

### MATERIAL_ACTIVATED
- **Subjects**: material
- **Properties**:
  - `material_activation_status` → asserted_value (ACTIVE, INACTIVE)
  - `activated_by` → source_actor_id

### TECHNICAL_REVIEW
- **Subjects**: configuration
- **Properties**:
  - `technical_review_result` → asserted_value (PASS, NEGATIVE, PENDING)
  - If payload has `reason` or `note`: `technical_review_reason` → asserted_value
- **Special**: Negative results create Evidence, absence of a review does NOT create REJECTED Evidence

### PRICING_DETERMINED / FINAL_PRICING_APPROVAL
- **Subjects**: launch
- **Properties**:
  - `pricing_authority` → source_actor_id
  - `pricing_status` → asserted_value
  - `pricing_value` → asserted_value (if present in payload)

### CHANGE_REQUESTED (product_intent only)
- **Subjects**: launch
- **Properties**:
  - `change_type` → asserted_value
  - `change_reason` → evidence_reason
  - `changed_by` → source_actor_id
- **Note**: Single record, 1 evidence row expected

---

## 6. Idempotency Strategy

**Idempotency Key** (composite UNIQUE):
```sql
(raw_event_id, subject_type, subject_id, property_name)
```

**Rationale**:
- `raw_event_id`: Ensures traceability to exact raw record
- `subject_type + subject_id`: Identifies the business entity
- `property_name`: Distinguishes different observations from same raw event

**Result**: 
- One raw event can produce multiple Evidence rows (different properties)
- Two raw events cannot produce identical Evidence (raw_event_id is unique)
- Contradictory observations about the same subject/property are allowed IF they come from different raw events

**INSERT Strategy**:
```sql
INSERT INTO runtime.evidence (...)
VALUES (...)
ON CONFLICT (raw_event_id, subject_type, subject_id, property_name)
DO NOTHING
```

---

## 7. Schema Gaps / Blockers

✓ **No blockers identified**

The deployed `runtime.evidence` schema supports:
- Multiple rows per raw event (1:N cardinality)
- Lineage tracking via raw_event_id FK
- Complex values via value_json JSONB
- Actor attribution via source_actor_id + source_actor_role
- Detailed reasoning via evidence_reason and evidence_lineage
- Idempotency key support (composite unique on derived identity)

---

## 8. Next Steps

1. **Approve this mapping matrix** (or provide corrections)
2. **Implement raw_to_evidence.sql**
   - Event-type-specific transformation logic
   - Payload extraction and normalization
   - Subject identification rules
   - Idempotency application
3. **Implement mappings.sql**
   - Configuration lookup tables (if needed)
   - Mapping definitions per event type
4. **Implement validation.sql**
   - Verify Evidence row counts
   - Check for NULL violations
   - Verify lineage integrity
   - Check contradiction preservation
5. **Create tests/evidence/**
   - Test each event type produces expected evidence
   - Test idempotency (run twice, get same results)
   - Test contradiction preservation (SKU-003, SKU-013)
   - Test absence handling (SKU-006)

---

**Questions for Approval**:

1. Does this mapping correctly identify the business facts you want preserved as Evidence?
2. Should the idempotency key remain `(raw_event_id, subject_type, subject_id, property_name)` or change?
3. Are there additional event types or properties that should be mapped but are not listed?
4. Should evidence_lineage be a deep copy of the payload extraction path, or just a brief reference?

