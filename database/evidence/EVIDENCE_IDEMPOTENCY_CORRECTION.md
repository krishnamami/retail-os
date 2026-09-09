# Evidence Idempotency and Source Model - Correction

**Date**: 2026-09-06  
**Status**: CRITICAL ARCHITECTURE CORRECTION

---

## A. IDEMPOTENCY MODEL - CORRECTED

### INCORRECT (Previously Proposed)
```sql
UNIQUE (subject_type, subject_id, property_name, arrival_at)
```
**Problem**: Two different Raw events could produce identical subject/property/value at identical arrival_at, and only one would survive.

### CORRECT (Approved Direction)
```sql
Primary Key: evidence_id
Lineage FK: raw_event_id (1:N allowed)
Idempotency: raw_event_id + mapping_id
```

**Rationale**: 
- Each raw_event_id + mapping_id combination produces at most ONE Evidence row
- Different raw_event_id always produce different Evidence (even if subject/property/value/arrival_at identical)
- Contradictions preserved because they originate from different Raw records

**Example**:
```
Raw Event A (raw_event_id = UUID-A):
  hierarchy_code = H100
  arrival_at = 2026-06-10 10:00

Raw Event B (raw_event_id = UUID-B):
  hierarchy_code = H200
  arrival_at = 2026-06-10 10:00  ← SAME arrival_at as Event A

Both Evidence rows survive because:
- Different raw_event_id lineage
- NOT because arrival_at differs
```

### INSERT Strategy
```sql
INSERT INTO runtime.evidence (raw_event_id, mapping_id, ...)
VALUES (...)
ON CONFLICT ???
```

**BLOCKER**: What is the actual UNIQUE constraint on runtime.evidence?

If deployed constraint is `(subject_type, subject_id, property_name, arrival_at)`:
- This does NOT enforce raw_event_id + mapping_id idempotency
- Multiple raw_event_ids for same subject/property/arrival_at would conflict
- May need to handle conflict strategy differently

**ACTION REQUIRED**: Verify actual runtime.evidence constraint and reconcile with lineage-based idempotency.

---

## B. SOURCE PROVENANCE vs ACTOR ATTRIBUTION - SEPARATED

### SOURCE PROVENANCE
"Where/system/context did the observation originate?"

Examples:
- SAP_CON_LOADED → logical_source = "sap_con"
- SAP_PRD_LOADED → logical_source = "sap_prd"
- HIERARCHY_APPROVAL → logical_source = "approval_workflow"
- TECHNICAL_REVIEW → logical_source = "technical_review_gate"

**Treatment**:
- Preserve in Evidence.source_system OR evidence_lineage.logical_source_system
- Do NOT claim "claris" for claris events (that was loader default)
- Derive from event_type mapping, not from raw.raw_event.source_system

### ACTOR ATTRIBUTION
"Who/what asserted, approved, loaded, reviewed, or changed the observation?"

Examples:
- approval_authority: "SIMULATED/strategy-board"
- loaded_by: "SAP_CONNECTOR_v2"
- status_changed_by: "supply_chain_manager"
- process_step: "technical_gate"

**Treatment**:
- Preserve in Evidence.source_actor_id and Evidence.source_actor_role
- Separate concept from source_system
- Indicates authority/actor, not originating system

### Corrected Fields
```
Evidence.source_system        ← logical_source derived from event mapping
Evidence.source_actor_id      ← approval_authority, loaded_by, status_changed_by
Evidence.source_actor_role    ← process_step, actor_role
Evidence.evidence_lineage     ← { raw_event_id, mapping_id, source_path, logical_source_system }
```

---

## C. EVIDENCE LINEAGE STRUCTURE - SIMPLIFIED

```json
{
  "raw_event_id": "550e8400-e29b-41d4-a716-446655440000",
  "mapping_id": "SAP_CON_LOAD_STATUS",
  "source_path": "payload.con_status",
  "logical_source_system": "sap_con"
}
```

**NOT**: Full copy of raw payload (retrievable via raw_event_id FK)

---

## D. UNIQUE CONSTRAINT AUDIT

**Deployed Constraint** (from earlier audit):
```
CONSTRAINT evidence_subject_property_arrival 
UNIQUE (subject_type, subject_id, property_name, arrival_at)
```

**Problem with Lineage-Based Idempotency**:
- Constraint is (subject, property, arrival_at)
- Idempotency requirement is (raw_event_id, mapping_id)
- These do NOT align

**Possible Resolutions**:
1. Schema allows multiple raw_event_ids for same subject/property/arrival_at (constraint doesn't prevent it)
   - Then ON CONFLICT may not trigger
   - Risk of duplicate Evidence rows
   
2. Constraint PREVENTS multiple raw_event_ids for same subject/property/arrival_at
   - Then 1:N cardinality from different raw events at same arrival_at breaks
   - Contradictions at same arrival_at cannot coexist

**ACTION REQUIRED**: Verify constraint semantics and reconcile with lineage requirement.

---

## E. MAPPING_ID ASSIGNMENT

Every distinct Evidence mapping must have a deterministic mapping_id.

**Format**: `{EVENT_TYPE}_{PROPERTY_NAME}` or `{SOURCE}_{PROPERTY}` or similar

Examples:
- SAP_CON_LOAD_STATUS
- SAP_CON_HIERARCHY_CODE
- HIERARCHY_APPROVAL_CON_CODE
- HIERARCHY_APPROVAL_CON_AUTHORITY
- HIERARCHY_APPROVAL_PRD_CODE
- HIERARCHY_APPROVAL_PRD_AUTHORITY
- TECHNICAL_REVIEW_RESULT
- TECHNICAL_REVIEW_REASON
- MATERIAL_ACTIVATION_STATUS
- MATERIAL_ACTIVATION_ACTOR

---

## F. NEXT STEPS BEFORE SQL

1. Verify actual runtime.evidence UNIQUE constraint
2. Reconcile constraint with lineage-based idempotency requirement
3. Assign mapping_id to every Evidence mapping
4. Create compact review table (one row per mapping, not per event type)
5. Clarify logical_source_system derivation for each event type
6. Document any event type producing zero Evidence
7. Document any field with ambiguous provenance

