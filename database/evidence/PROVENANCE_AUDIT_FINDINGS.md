# Source Provenance Audit Findings
## Raw → Evidence Lineage Investigation

**Date**: 2026-09-06  
**Status**: CRITICAL FINDINGS - Idempotency Key CORRECTED

---

## Executive Summary

The deployed `runtime.evidence` table has a UNIQUE constraint that DIFFERS from the proposed mapping matrix idempotency key. This significantly affects Evidence transformation design.

**Critical Corrections Required**:
1. Idempotency key is NOT `(raw_event_id, subject_type, subject_id, property_name)`
2. Idempotency key IS `(subject_type, subject_id, property_name, arrival_at)`
3. Source authority for claris events is NOT the table column, but payload fields
4. "claris" source_system is a LOADER NORMALIZATION, not authoritative source

---

## A. Source System Provenance

### Finding 1: "claris" is Loader Default, Not Source Data

**Evidence**:
- raw.raw_event.source_system = "claris" (168 rows) or "product_intent" (1 row)
- For claris events: payload contains NO source_system field
- For product_intent event: payload CONTAINS source_system = "product_intent"

**Conclusion**:
- Loader inserted "claris" as default/normalization for events without explicit source_system
- Product_intent event preserved its authoritative source in payload
- **"claris" in raw.raw_event is NOT authoritative source provenance**

### Finding 2: True Authority Is Payload-Based

**Authority Fields Present in Payloads**:
- `approval_authority` (HIERARCHY_APPROVAL) → who/what approved
- `loaded_by` (SAP_CON_LOADED, SAP_PRD_LOADED) → which process/actor loaded
- `status_changed_by` (MATERIAL_ACTIVATED) → who changed status
- `process_step` (all events) → which process step generated the observation
- `actor_id`, `actor_role` (available in raw.raw_event columns) → actor context

**Conclusion**:
- Extract actual source authority from payload authority/actor fields
- Populate Evidence.source_actor_id from payload authority fields
- Populate Evidence.source_actor_role from payload role context
- Use raw.raw_event.source_system only for compatibility, not as Evidence authority

---

## B. runtime.evidence UNIQUE Constraint Discovery

### Critical Constraint Found

```sql
CONSTRAINT evidence_subject_property_arrival 
UNIQUE (subject_type, subject_id, property_name, arrival_at)
```

### Idempotency Key CORRECTED

**PREVIOUS (INCORRECT)**:
```sql
(raw_event_id, subject_type, subject_id, property_name)
```

**ACTUAL (DEPLOYED)**:
```sql
(subject_type, subject_id, property_name, arrival_at)
```

### Implications

1. **Multiple Raw Events Can Produce Same Subject/Property Evidence**
   ```
   Raw Event 1 (arrival_at: 2026-06-10 10:00):
     → Evidence: subject_id=LAUNCH-001, property=hierarchy_code, arrival_at=2026-06-10 10:00
   
   Raw Event 2 (arrival_at: 2026-06-10 11:00):
     → Evidence: subject_id=LAUNCH-001, property=hierarchy_code, arrival_at=2026-06-10 11:00
   
   Both Evidence rows coexist (different arrival_at)
   ```

2. **Arrival_At Is Part of Identity**
   - Preserves timestamp variations (delayed arrival, out-of-order arrival)
   - Allows multiple observations of same property at different arrival times
   - Naturally handles SKU-010 (delayed arrival), SKU-011 (out-of-order), SKU-012 (multiple horizons)

3. **INSERT Strategy Must Account for Composite Key**
   ```sql
   INSERT INTO runtime.evidence (...)
   VALUES (...)
   ON CONFLICT (subject_type, subject_id, property_name, arrival_at)
   DO NOTHING
   ```

---

## C. Payload Authority Field Mapping

### Event-Type Authority Fields

| Event Type | Authority Field | Type | Example | Maps To |
|---|---|---|---|---|
| **HIERARCHY_APPROVAL** | approval_authority | string | "SIMULATED/strategy-board" | Evidence.source_actor_id |
| **SAP_CON_LOADED** | loaded_by | string | "SAP_CONNECTOR_v2" | Evidence.source_actor_id |
| **SAP_PRD_LOADED** | loaded_by | string | "SAP_CONNECTOR_v2" | Evidence.source_actor_id |
| **MATERIAL_ACTIVATED** | status_changed_by | string | "supply_chain_manager" | Evidence.source_actor_id |
| **CON_VERIFIED** | process_step | string | "verification_gate" | Evidence.source_actor_role |
| **TECHNICAL_REVIEW** | process_step | string | "technical_gate" | Evidence.source_actor_role |
| **PRICING_DETERMINED** | process_step | string | "pricing_gate" | Evidence.source_actor_role |
| **CHANGE_REQUESTED** | actor_id (raw col) | string | "user_123" | Evidence.source_actor_id |
| **CHANGE_REQUESTED** | actor_role (raw col) | string | "product_manager" | Evidence.source_actor_role |

### Source System Mapping

| Event Type | Source Mapping | Authority |
|---|---|---|
| **claris events (168)** | raw.raw_event.source_system = "claris" | Payload authority field (approval_authority, loaded_by, status_changed_by) |
| **product_intent (1)** | payload.source_system = "product_intent" | Payload field (authoritative) |

---

## D. Timestamp Preservation Across Arrival Deltas

### Unique Constraint Enables Proper Timestamp Tracking

```
Raw Event for LAUNCH-001:
  occurred_at: 2026-06-10 08:00
  recorded_at: 2026-06-10 08:15
  arrival_at:  2026-06-10 10:00  ← Delayed by 2 hours

Evidence Row 1:
  subject_id: LAUNCH-001
  property_name: hierarchy_code
  asserted_value: H100
  occurred_at: 2026-06-10 08:00
  recorded_at: 2026-06-10 08:15
  arrival_at:  2026-06-10 10:00  ← PRESERVED
  
If same property observed again at different arrival_at:

Raw Event 2 (delayed/out-of-order):
  arrival_at: 2026-06-10 09:30  ← Out-of-order (before Event 1)

Evidence Row 2:
  subject_id: LAUNCH-001
  property_name: hierarchy_code
  asserted_value: H100
  arrival_at:  2026-06-10 09:30  ← Different arrival, coexists with Row 1
  
Both rows coexist because (subject, property, arrival_at) is unique, not (subject, property).
```

---

## E. Contradiction Preservation (SKU-003, SKU-013)

### Hierarchy Contradiction (SKU-003)

**Design enables**:
```
Evidence Row 1:
  subject_id: LAUNCH-001
  property_name: hierarchy_code_con
  asserted_value: H100
  source_actor_id: SIMULATED/strategy-board
  arrival_at: 2026-06-10 10:00

Evidence Row 2:
  subject_id: LAUNCH-001
  property_name: hierarchy_code_prd
  asserted_value: H200
  source_actor_id: SIMULATED/product-council
  arrival_at: 2026-06-10 10:00

Both survive (different property names).
```

### Negative vs Absence (SKU-013 vs SKU-006)

**Design enables**:
```
SKU-013 (Explicit Negative):
  property_name: technical_review_result
  asserted_value: NEGATIVE
  → Evidence Row created

SKU-006 (Absence):
  property_name: s12_review
  asserted_value: (absent/NULL)
  → No Evidence Row created (absence ≠ negative observation)

Both patterns preserved correctly.
```

---

## F. Schema Gaps / Blockers

**✓ NO BLOCKERS IDENTIFIED**

The deployed constraint `evidence_subject_property_arrival` PROPERLY SUPPORTS:
- ✓ Multiple Evidence rows per raw event (different subjects/properties/arrival_at)
- ✓ Timestamp preservation (arrival_at in unique key)
- ✓ Contradiction preservation (different authorities/values for same property at different arrival times)
- ✓ Absence handling (no evidence generated for absent properties)
- ✓ Idempotency without blocking legitimate contradictions

---

## G. Corrected Mapping Principles

### Principle 1: Authority Extraction
- Source authority is NOT raw.raw_event.source_system for claris events
- Extract from payload: approval_authority, loaded_by, status_changed_by, process_step
- Map to Evidence.source_actor_id and Evidence.source_actor_role

### Principle 2: Idempotency
- Key: `(subject_type, subject_id, property_name, arrival_at)`
- Allows different raw events to create evidence for same property at different arrival times
- Prevents duplicating same observation at exact same arrival_at

### Principle 3: 1:N Cardinality
- One raw event → 0..N evidence rows
- Rows differ by: subject (launch/config/sku/material), property_name, or arrival_at
- Same raw event can generate multiple properties (HIERARCHY_APPROVAL → both CON and PRD hierarchies)

### Principle 4: Lineage
- Primary lineage: raw_event_id FK (preserved)
- Lineage metadata: raw_event_id + mapping_identity in evidence_lineage JSONB
- Source authority: payload authority fields (not raw.raw_event.source_system)

---

## H. Approved Correction Summary

**FOR MAPPING MATRIX REVISION**:
1. ✓ Update idempotency key to `(subject_type, subject_id, property_name, arrival_at)`
2. ✓ Source authority mapping: extract from payload, NOT from raw.raw_event.source_system
3. ✓ Document payload authority fields for each event type
4. ✓ Confirm 1:N cardinality is properly supported
5. ✓ Create complete field-level mapping matrix
6. ✓ Define evidence_lineage structure

**BEFORE SQL IMPLEMENTATION**:
- [ ] Approve revised mapping matrix with payload authority fields
- [ ] Confirm source_actor_id/source_actor_role extraction rules
- [ ] Confirm evidence_lineage structure
- [ ] Ready to create raw_to_evidence.sql

---

**Next**: Create COMPLETE MAPPING MATRIX with all field-level extraction rules, payload authority mapping, and idempotency key corrected.

