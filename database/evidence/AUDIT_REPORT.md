# Evidence Layer - Pre-Implementation Audit Report
## Schema Inspection, Provenance Audit, Mapping Design

**Date**: 2026-09-06  
**Status**: READY FOR APPROVAL (blocking SQL implementation pending confirmation)

---

## EXECUTIVE SUMMARY

**Raw Layer Status**: ✓ Complete (169 records, verified)  
**Evidence Schema**: ✓ Ready (runtime.evidence deployed, no blockers)  
**Provenance Audit**: ✓ Complete (critical corrections identified)  
**Mapping Matrix**: ✓ Complete (528 lines, field-level detail)

**Critical Corrections Made**:
1. ✓ Idempotency key corrected: `(subject_type, subject_id, property_name, arrival_at)` NOT `(raw_event_id, ...)`
2. ✓ Source authority extraction: payload fields, NOT raw.raw_event.source_system
3. ✓ "claris" source_system identified as loader normalization, not authoritative

**Blockers**: NONE  
**Ready for SQL Implementation**: YES (pending approval)

---

## A. FILES CREATED IN retail_os/database/evidence/

| File | Lines | Purpose | Status |
|---|---|---|---|
| inspect_schema.py | ~180 | Schema inspection tool | ✓ Executed, output reviewed |
| audit_source_provenance.py | ~195 | Provenance audit tool | ✓ Executed, findings documented |
| MAPPING_MATRIX.md | ~350 | Initial mapping design | ✗ SUPERSEDED (idempotency key was incorrect) |
| PROVENANCE_AUDIT_FINDINGS.md | ~380 | Audit findings and corrections | ✓ Approved as reference |
| COMPLETE_MAPPING_MATRIX.md | ~528 | Final mapping design (corrected) | ✓ Ready for approval |
| AUDIT_REPORT.md | (this file) | Pre-implementation summary | ✓ Self-documenting |

**Total Documentation**: 1,633 lines (excluding superseded initial mapping matrix)

---

## B. SCHEMA INSPECTION FINDINGS

### raw.raw_event (169 rows)
- **Columns**: 24 (raw_event_id PK, event_type, timestamps, cross-refs, payload JSONB)
- **Source Systems**: claris (168), product_intent (1)
- **All source_record_id**: Non-NULL (complete provenance preservation)
- **Payload**: Full JSONB with event details

### runtime.evidence (0 rows - to be populated)
- **Columns**: 18 (evidence_id PK, raw_event_id FK, subject/property/value, actors, timestamps, lineage)
- **PK**: evidence_id (uuid, auto-generated)
- **FK**: raw_event_id → raw.raw_event
- **UNIQUE constraint**: `evidence_subject_property_arrival (subject_type, subject_id, property_name, arrival_at)`
- **NO BLOCKERS**: Schema supports all semantic requirements

---

## C. PROVENANCE AUDIT FINDINGS

### Finding 1: "claris" is Loader Normalization
- **Evidence**: Claris events (168 rows) have NO payload['source_system']
- **Conclusion**: Loader inserted "claris" as default, NOT from original JSONL
- **Exception**: product_intent event (1 row) DOES have payload.source_system = "product_intent"
- **Action**: Extract authority from payload fields, NOT raw.raw_event.source_system

### Finding 2: Authority Fields Identified
- HIERARCHY_APPROVAL: `approval_authority`
- SAP_*_LOADED: `loaded_by`
- MATERIAL_ACTIVATED: `status_changed_by`
- All events: `process_step`
- product_intent: `actor_id`, `actor_role`

### Finding 3: Idempotency Key Correction
- **Original Proposal** (INCORRECT): `(raw_event_id, subject_type, subject_id, property_name)`
- **Deployed Constraint** (ACTUAL): `(subject_type, subject_id, property_name, arrival_at)`
- **Impact**: Multiple Evidence rows per raw event allowed if arrival_at differs
- **Benefit**: Preserves timestamp deltas (SKU-010, SKU-011, SKU-012)

---

## D. MAPPING MATRIX DESIGN

### Principles
1. **1:N Cardinality**: One raw event → 0..N evidence observations
2. **Observable Property**: Only extract meaningful business facts, not every payload field
3. **Contradiction Preserved**: Different observations of same property allowed (different arrival_at)
4. **Absence NOT Generated**: No Evidence for missing observations (SKU-006)
5. **Negative Explicit**: Explicit negative observations create Evidence (SKU-013)

### Event Type Coverage (25 types)
- PRODUCT_INTENT_CREATED (13): 2 rows each
- HIERARCHY_APPROVAL (13): 2-4 rows each
- SAP_CON_LOADED (13): 3 rows each
- SAP_PRD_LOADED (9): 3 rows each
- MATERIAL_ACTIVATED (11): 2 rows each
- SKU_MINTED (9): 1 row each
- TECHNICAL_REVIEW (9): 1-2 rows each (no row if review absent)
- PRICING_* (19 total): 1-2 rows each
- FULLY_APPROVED (9): 1 row each
- GO_LIVE_* (5): 1-2 rows each
- SUPPLY_CHAIN_NOTIFIED (2): 1 row each
- OVERNIGHT_PUSH (11): 2 rows each
- CHANGE_REQUESTED (1): 4 rows
- Others: 1 row each

### Evidence Lineage Structure
```json
{
  "raw_event_id": "uuid",
  "event_type": "string",
  "source_path": "payload path extracted",
  "mapping_identity": "normalized property name",
  "extraction_rule": "how value was derived",
  "source_authority_field": "which payload field provided authority"
}
```

### Estimated Evidence Rows
- **Input**: 169 raw events
- **Output**: 180-230 evidence rows (estimated)
- **Actual**: TBD after SQL execution

---

## E. CRITICAL CORRECTIONS APPLIED

### Correction 1: Idempotency Key
```
BEFORE: (raw_event_id, subject_type, subject_id, property_name)
AFTER:  (subject_type, subject_id, property_name, arrival_at)

REASON: Deployed constraint is (subject_type, subject_id, property_name, arrival_at)
IMPACT: Allows multiple Evidence rows per raw event if arrival_at differs
ENABLES: Timestamp delta preservation, out-of-order arrival handling
```

### Correction 2: Source Authority
```
BEFORE: raw.raw_event.source_system = "claris" (assumed authoritative)
AFTER:  Extract from payload fields (approval_authority, loaded_by, etc.)

REASON: "claris" was loader default for 168 events, not original source
IMPACT: True source authority now captured in Evidence.source_actor_id
ENABLES: Proper attribution to actual decision-maker/process
```

### Correction 3: Event-Type-Specific Logic
```
BEFORE: Generic 1:1 mapping for all event types
AFTER:  Event-specific extraction rules (HIERARCHY_APPROVAL unnests, 
         TECHNICAL_REVIEW only if explicit result, etc.)

REASON: Different events require different property extraction
IMPACT: Proper handling of contradictions, absences, negatives
ENABLES: SKU-003, SKU-006, SKU-013 test cases to work correctly
```

---

## F. SCHEMA GAPS / BLOCKERS

**Status**: ✓ NONE IDENTIFIED

The deployed runtime.evidence schema SUPPORTS all requirements:
- ✓ 1:N cardinality (multiple rows per raw event via different subjects/properties/arrival_at)
- ✓ FK lineage (raw_event_id → raw.raw_event)
- ✓ Complex values (value_json JSONB, evidence_lineage JSONB)
- ✓ Actor attribution (source_actor_id, source_actor_role)
- ✓ Reasoning (evidence_reason, evidence_lineage)
- ✓ Timestamp preservation (arrival_at in unique constraint)
- ✓ Contradiction preservation (no constraint preventing different values for same property from different raw events)

---

## G. REPOSITORY PLACEMENT AUDIT

**All Files Created Under retail_os/**:
```
retail_os/
└── database/
    └── evidence/
        ├── inspect_schema.py                    ✓ In retail_os
        ├── audit_source_provenance.py           ✓ In retail_os
        ├── MAPPING_MATRIX.md                    ✓ In retail_os (superseded)
        ├── PROVENANCE_AUDIT_FINDINGS.md         ✓ In retail_os
        ├── COMPLETE_MAPPING_MATRIX.md           ✓ In retail_os
        ├── AUDIT_REPORT.md                      ✓ In retail_os
        ├── raw_to_evidence.sql                  (To be created)
        ├── mappings.sql                         (To be created)
        ├── validation.sql                       (To be created)
        └── README.md                            (To be created)
```

**No Implementation Code Outside retail_os**: ✓ CONFIRMED

---

## H. BEFORE SQL IMPLEMENTATION

**Approval Required For**:
1. ✓ Idempotency key: `(subject_type, subject_id, property_name, arrival_at)` CORRECT?
2. ✓ Source authority extraction from payload fields (NOT raw.source_system) CORRECT?
3. ✓ Event-type-specific mappings (528-line matrix) ACCURATE?
4. ✓ Evidence lineage structure (JSON metadata + FK lineage) ACCEPTABLE?
5. ✓ Estimated row count (180-230 evidence rows from 169 raw) REASONABLE?

**Ready to Proceed With**:
- [ ] raw_to_evidence.sql (Event-type-specific extraction, payload parsing, JSONB operators)
- [ ] mappings.sql (Configuration tables if needed, mapping definitions)
- [ ] validation.sql (Row count verification, lineage checks, contradiction preservation tests)
- [ ] tests/evidence/ (Test cases for each event type, contradiction preservation, absence handling)
- [ ] database/evidence/README.md (Execution instructions, architecture documentation)

---

## I. NEXT STEPS

### IF APPROVED:
1. Create raw_to_evidence.sql
   - HIERARCHY_APPROVAL: UNNEST array, create row per environment
   - SAP_*_LOADED: Extract status, actor, hierarchy
   - TECHNICAL_REVIEW: Extract only if explicit result (handle absence)
   - CHANGE_REQUESTED: Use payload.source_system, actor fields
   - All others: Event-specific property extraction

2. Create mappings.sql (if needed)
   - May be inline in raw_to_evidence.sql if simple
   - Config tables if complex transformation needed

3. Create validation.sql
   - Verify Evidence row counts (estimate vs actual)
   - Check lineage integrity (raw_event_id FKs)
   - Verify contradiction preservation (SKU-003, SKU-013)
   - Verify absence handling (SKU-006)

4. Create tests/evidence/
   - Test each event type produces expected evidence
   - Test idempotency (run twice, get same results)
   - Test contradiction preservation
   - Test absence handling

5. Create database/evidence/README.md
   - Architecture overview
   - Mapping rules reference
   - Execution instructions
   - Validation procedures

### IF NOT APPROVED:
- Document specific corrections needed
- Update COMPLETE_MAPPING_MATRIX.md
- Return to provenance audit stage

---

## J. SIGN-OFF

**Status**: Ready for User Approval

**Pending Confirmation**:
1. Idempotency key: `(subject_type, subject_id, property_name, arrival_at)` ✓ DEPLOY AS-IS?
2. Source authority: Payload field extraction (approval_authority, loaded_by, etc.) ✓ DEPLOY AS-IS?
3. Event mappings: 25 event types, 528-line detail ✓ DEPLOY AS-IS?
4. Proceed to SQL implementation ✓ YES/NO?

---

**BLOCKING**: No SQL created until approval confirmed.  
**EVIDENCE LAYER STATUS**: DESIGN PHASE COMPLETE, AWAITING APPROVAL

