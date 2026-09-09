# Evidence Design - Final Summary Before SQL Implementation
## Corrected Architecture, Mapping Review Complete

**Date**: 2026-09-06  
**Status**: BLOCKING BLOCKER IDENTIFIED - UNIQUE CONSTRAINT RECONCILIATION REQUIRED

---

## A. CORRECTED EVIDENCE IDEMPOTENCY RULE

### Design Direction (Approved)
```
Primary Lineage: raw_event_id (FK to raw.raw_event)
Idempotency Model: raw_event_id + mapping_id
```

**Rationale**:
- One raw_event_id can produce multiple Evidence rows via different mapping_ids
- Different raw_event_ids produce different Evidence even if subject/property/value/arrival_at identical
- Contradictions preserved because they originate from different Raw records (different raw_event_id)

**Example**:
```
Raw Event A (raw_event_id = UUID-A, arrival_at = 2026-06-10 10:00):
  hierarchy_code = H100
  
Raw Event B (raw_event_id = UUID-B, arrival_at = 2026-06-10 10:00):
  hierarchy_code = H200

Both Evidence rows survive:
Evidence Row 1: raw_event_id=UUID-A, property=hierarchy_code, value=H100
Evidence Row 2: raw_event_id=UUID-B, property=hierarchy_code, value=H200
  
NOT because arrival_at differs (they're identical)
BUT because raw_event_id differs (different source lineage)
```

---

## B. EXACT DEPLOYED UNIQUE CONSTRAINT

**From schema audit**:
```sql
CONSTRAINT evidence_subject_property_arrival 
UNIQUE (subject_type, subject_id, property_name, arrival_at)
```

**This Constraint Enforces**:
- Only ONE Evidence row per (subject_type, subject_id, property_name, arrival_at) combination
- Prevents duplicate Evidence for identical subject/property/value at identical arrival_at
- DOES NOT enforce raw_event_id + mapping_id uniqueness

**Critical Misalignment**:
- Idempotency model requires: raw_event_id + mapping_id identity
- Constraint enforces: subject + property + arrival_at identity
- Different lineage (raw_event_id) at same arrival_at would violate the constraint

**BLOCKER**: These two idempotency models are **INCOMPATIBLE** as currently stated.

---

## C. BLOCKING ISSUE: CONSTRAINT RECONCILIATION REQUIRED

### The Problem

Raw Event A (UUID-A, arrival_at 10:00) and Raw Event B (UUID-B, arrival_at 10:00) both assert:
```
subject_type = launch
subject_id = LAUNCH-001
property_name = hierarchy_code
asserted_value = H100
arrival_at = 2026-06-10 10:00
```

**Deployed Constraint Behavior**:
- First Evidence row inserted successfully
- Second Evidence row INSERT would VIOLATE constraint (same subject/property/arrival_at)
- Conflict resolution: ON CONFLICT DO NOTHING → second row rejected

**Result**: Only ONE of the two contradictory raw events survives, the other is lost.

### The Solution Options

**Option 1**: Modify Constraint
```sql
ALTER TABLE runtime.evidence 
DROP CONSTRAINT evidence_subject_property_arrival
ADD CONSTRAINT evidence_raw_event_mapping UNIQUE (raw_event_id, mapping_id)
```
- Aligns with lineage-based idempotency
- Allows contradictions from different raw_event_ids at same arrival_at
- Requires schema change (blocker: "do not alter runtime.evidence without approval")

**Option 2**: Modify INSERT Logic
```sql
INSERT INTO runtime.evidence (...)
VALUES (...)
-- No ON CONFLICT clause
-- Accept constraint violation as error → human review required
```
- Preserves constraint as-is
- Loses idempotency: re-running loader creates duplicate Evidence rows
- Not acceptable for operational load

**Option 3**: Modify Mapping Logic
- Do NOT generate Evidence for contradictory raw events at same arrival_at
- Only preserve contradictions if arrival_at differs
- Violates SKU-003 use case (both hierarchies must survive regardless of arrival_at)
- Not acceptable

**Option 4**: Modify Subject/Property Representation
- Add raw_event_id to subject or property_name to guarantee uniqueness
- Example: property_name = "hierarchy_code::UUID-A"
- Violates semantic meaning of property_name
- Not acceptable

---

## D. ACTION REQUIRED BEFORE SQL

**Choose One**:
1. **Approve schema change** to constraint `(raw_event_id, mapping_id)` UNIQUE
2. **Accept constraint as-is** and restrict contradictions to different arrival_at only
3. **Alternative idempotency model** that reconciles with deployed constraint

---

## E. SOURCE PROVENANCE vs ACTOR ATTRIBUTION (CORRECTED)

### Source Provenance
"Where/system/context did the observation originate?"

**Treatment**:
- Store in: Evidence.source_system OR evidence_lineage.logical_source_system
- Derive from: event_type mapping (NOT from raw.raw_event.source_system)
- Do NOT use: raw.raw_event.source_system = "claris" (loader default for 168 events)

**Mapping** (deterministic from event_type):
| Event Type | Logical Source |
|---|---|
| SAP_CON_* | sap_con |
| SAP_PRD_* | sap_prd |
| HIERARCHY_APPROVAL | approval_workflow |
| TECHNICAL_REVIEW | technical_gate |
| MATERIAL_ACTIVATED | material_lifecycle |
| ... | (see EVIDENCE_MAPPING_REVIEW_TABLE.md) |

### Actor Attribution
"Who/what asserted, approved, loaded, reviewed, or changed the observation?"

**Treatment**:
- Store in: Evidence.source_actor_id and Evidence.source_actor_role
- Extract from: Payload fields (approval_authority, loaded_by, status_changed_by, process_step)
- Separate concept from source_system

**Example**:
```
Raw Event: HIERARCHY_APPROVAL
  raw.raw_event.source_system = "claris" (loader default)
  payload.approval_authority = "SIMULATED/strategy-board" (actual authority)
  
Evidence:
  source_system = "approval_workflow" (logical source, derived from event type)
  source_actor_id = "SIMULATED/strategy-board" (from payload)
  source_actor_role = "approval_authority" (contextual role)
```

---

## F. EVIDENCE LINEAGE STRUCTURE (SIMPLIFIED)

```json
{
  "raw_event_id": "550e8400-e29b-41d4-a716-446655440000",
  "mapping_id": "SAP_CON_LOAD_STATUS",
  "source_path": "payload.con_status",
  "logical_source_system": "sap_con"
}
```

**NOT full payload copy** (retrievable via raw_event_id FK)

---

## G. COMPACT MAPPING REVIEW TABLE

**File**: `EVIDENCE_MAPPING_REVIEW_TABLE.md`

**Contains**: One row per distinct Evidence mapping

**Statistics**:
- **Total Mappings**: 38 (NOT 25 event types)
- **Largest Event Types**:
  - HIERARCHY_APPROVAL: 4 mappings
  - CHANGE_REQUESTED: 4 mappings
  - SAP_CON_LOADED: 3 mappings
  - SAP_PRD_LOADED: 3 mappings
  - Others: 1-2 mappings each

---

## H. MAPPING_ID ASSIGNMENT

**Every mapping has deterministic mapping_id**:

Examples:
- SAP_CON_LOAD_STATUS
- HIERARCHY_APPROVAL_CON_CODE
- HIERARCHY_APPROVAL_PRD_CODE
- MATERIAL_ACTIVATION_STATUS
- TECHNICAL_REVIEW_RESULT
- TECHNICAL_REVIEW_REASON

**Format**: `{LOGICAL_SOURCE}_{PROPERTY}` or `{EVENT_TYPE}_{PROPERTY}`

**Uniqueness**: Each mapping_id is globally unique and reproducible.

---

## I. EVENT TYPES PRODUCING ZERO EVIDENCE

**Explicit Zero Evidence**:
- None. All 25 event types produce at least one mapping.

**Conditional Zero Evidence**:
- **TECHNICAL_REVIEW**: Produces zero Evidence rows IF review_result field absent in payload (SKU-006 case)
  - Mapping exists: `TECHNICAL_REVIEW_RESULT`
  - Execution: IF payload.review_result is NULL → no row created
  - Correct handling: Absence ≠ NEGATIVE observation

---

## J. AMBIGUOUS PROVENANCE

**Status**: NONE IDENTIFIED

All mappings have:
- ✓ Deterministic source_path in payload
- ✓ Deterministic logical_source_system
- ✓ Clear actor field (if applicable)

**Edge Case Reviewed**:
- TECHNICAL_REVIEW reason field (only if negative) → Correctly documented as conditional

---

## K. FILES MODIFIED/CREATED

```
retail_os/database/evidence/
├── inspect_schema.py                           (created, executed)
├── audit_source_provenance.py                  (created, executed)
├── MAPPING_MATRIX.md                           (created, superseded)
├── PROVENANCE_AUDIT_FINDINGS.md                (created, reference)
├── COMPLETE_MAPPING_MATRIX.md                  (created, superseded)
├── EVIDENCE_IDEMPOTENCY_CORRECTION.md          (created, current)
├── EVIDENCE_MAPPING_REVIEW_TABLE.md            (created, current - 38 mappings)
├── AUDIT_REPORT.md                             (created, reference)
└── PRE_SQL_FINAL_SUMMARY.md                    (this file)

retail_os/tests/evidence/
(To be created post-approval)

retail_os/database/evidence/ (To be created post-approval):
├── raw_to_evidence.sql
├── mappings.sql
├── validation.sql
└── README.md
```

---

## L. APPROVAL GATE - FINAL CHECKLIST

**Ready for Approval**:
- ✓ Evidence idempotency corrected (raw_event_id + mapping_id lineage-based)
- ✓ Source provenance vs actor attribution separated and documented
- ✓ Compact mapping review table complete (38 mappings, one per row)
- ✓ Logical source system assigned deterministically for each mapping
- ✓ Mapping_id assigned to every distinct mapping
- ✓ Event types with zero Evidence identified (none explicitly, TECHNICAL_REVIEW conditionally)
- ✓ Ambiguous provenance audit complete (none found)
- ✓ Evidence lineage structure simplified and documented
- ✓ Repository placement verified (all files in retail_os)

**BLOCKING ISSUE - REQUIRES RESOLUTION**:
1. **UNIQUE Constraint Mismatch**
   - Deployed: `(subject_type, subject_id, property_name, arrival_at)`
   - Required: `(raw_event_id, mapping_id)` for lineage-based idempotency
   - **Decision Required**: Alter constraint, accept constraint-based idempotency, or alternative model?

**BEFORE SQL IMPLEMENTATION**:
- [ ] Resolve UNIQUE constraint mismatch (choose option 1, 2, or 3)
- [ ] Confirm 38-mapping matrix and mapping_ids
- [ ] Confirm logical_source_system derivation
- [ ] Confirm source_actor_id/source_actor_role extraction rules

---

## M. NEXT STEPS

### IF Constraint Reconciliation Approved:
1. Create raw_to_evidence.sql
2. Create mappings.sql (if needed)
3. Create validation.sql
4. Create tests/evidence/
5. Create database/evidence/README.md

### IF Blocked:
- Clarify UNIQUE constraint strategy
- Iterate on constraint resolution
- Return to this pre-SQL phase

---

**CURRENT STATUS**: DESIGN COMPLETE, BLOCKING ON CONSTRAINT RECONCILIATION

**AWAITING**: 
1. Constraint resolution decision
2. Final approval on 38-mapping matrix
3. Confirmation to proceed with SQL implementation

