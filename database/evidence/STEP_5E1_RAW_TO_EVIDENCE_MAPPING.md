================================================================================
STEP 5E.1 RAW → EVIDENCE MAPPING DESIGN
================================================================================
Analysis Date: 2026-09-07
Status: DESIGN ONLY (NO EXECUTION)
Raw Records: 8 prototype records (1 PRODUCT_DEFINED + 7 CONFIGURATION_REQUESTED)
Current Evidence Rows: 107
Expected New Evidence Rows: TBD (calculated below)

================================================================================
1. CURRENT EVIDENCE IMPLEMENTATION INSPECTED
================================================================================

**Repository Files:**
- None found in cloud workspace (files are on Windows machine)
- Evidence schema retrieved from live database: runtime.evidence

**Schema Location:** 
- Database: accord
- Schema: runtime
- Table: evidence

**Evidence Transformer Location:**
- Not directly inspected (requires Windows machine access)
- Assumed to be in: database/procedures/ or database/evidence/transformers/

================================================================================
2. CURRENT EVIDENCE TABLE/SCHEMA FIELDS
================================================================================

**Full Evidence Table Structure (20 fields):**

1. evidence_id (uuid, NOT NULL, PK) — Unique evidence identifier
2. raw_event_id (uuid, NOT NULL, FK) — Links to raw.raw_event for traceability
3. evidence_type (varchar, NOT NULL) — Type of evidence (e.g., "product_intent", "sap_load")
4. subject_type (varchar, NOT NULL) — Entity being described (e.g., "launch", "configuration")
5. subject_id (varchar, NOT NULL) — ID of the subject entity
6. property_name (varchar, NOT NULL) — Name of the business property being asserted
7. asserted_value (text, nullable) — Human-readable value representation
8. value_type (varchar, NOT NULL) — Value data type (e.g., "string", "integer", "jsonb")
9. value_json (jsonb, nullable) — JSON representation for complex values
10. source_system (varchar, NOT NULL) — Source system identifier (e.g., "product_intent", "sap_con")
11. source_actor_id (varchar, nullable) — Identity of the actor creating the event
12. source_actor_role (varchar, nullable) — Role of the actor (e.g., "process", "system", "S1")
13. occurred_at (timestamp with TZ, NOT NULL) — When event occurred in source
14. recorded_at (timestamp with TZ, NOT NULL) — When recorded in source system
15. arrival_at (timestamp with TZ, NOT NULL) — When data arrived in our ingestion system
16. simulator_classification (varchar, nullable) — Simulation marker (e.g., "SIMULATED/batch", "PROTOTYPE_ASSUMPTION")
17. evidence_reason (text, nullable) — Human-readable reason for this evidence
18. evidence_lineage (jsonb, nullable) — Lineage metadata: {event_type, mapping_id, source_path, raw_event_id}
19. created_at (timestamp with TZ, NOT NULL) — When evidence was generated
20. mapping_id (text, NOT NULL) — Identifier of the transformation rule applied (e.g., "PRODUCT_INTENT_CLASS", "SAP_CON_LOAD_STATUS")

================================================================================
3. ACTUAL EVIDENCE IDEMPOTENCY KEY/BEHAVIOR
================================================================================

**Observed from Sample Evidence:**
- No UNIQUE constraint on (raw_event_id, property_name) visible in schema
- Idempotency appears to rely on **raw_event_id + mapping_id** combination
- The transformer/application logic likely checks if Evidence already exists for a given raw_event_id + mapping_id before inserting

**Inferred Idempotency Contract:**
```
UNIQUE ON: (raw_event_id, property_name, subject_type, subject_id)
INSERT Behavior: 
  - First insert creates evidence row
  - Replay of same raw_event_id does not re-create Evidence (checked at application/transformer level)
  - Schema does not enforce this via database constraint (likely application-level check)
```

**Replay Scenario (Run 2 Idempotency):**
- When raw_event_id is replayed, transformer checks evidence_lineage.raw_event_id
- If Evidence with matching raw_event_id + mapping_id already exists, skip insert
- Result: No duplicate Evidence rows on replay

================================================================================
4. PRODUCT_DEFINED MAPPING TABLE
================================================================================

**Source:** 
- Raw event: PRODUCT_DEFINED
- source_system: product_definition
- source_record_id: PROD_DEF_2026_001
- event_type: PRODUCT_DEFINED

**Raw Payload Expected Structure:**
```json
{
  "product_id": "PROD-001",
  "product_name": "Standard Loan Product",
  "launch_id": "LAUNCH-001",
  "sku_id": null,
  "material_id": null,
  "simulator_classification": "PROTOTYPE_ASSUMPTION",
  "source_version": "1.0"
}
```

**Evidence Rows to Generate (1 Raw × 2 Properties = 2 Evidence rows):**

| Row | evidence_type | subject_type | subject_id | property_name | asserted_value | value_type | source_path | mapping_id | notes |
|-----|---|---|---|---|---|---|---|---|---|
| 1 | product_definition | product | PROD-001 | product_name | Standard Loan Product | string | payload.product_name | PRODUCT_DEF_NAME | Primary business fact |
| 2 | product_definition | product | PROD-001 | launch_reference | LAUNCH-001 | string | payload.launch_id | PRODUCT_DEF_LAUNCH | Relationship: Product→Launch |

**Decision Rationale:**

- **product_id**: Carried as subject_id, not replicated as property (metadata)
- **product_name**: Core business fact → Evidence property
- **launch_id**: Related entity → Evidence property (relationship fact)
- **sku_id, material_id**: NULL in payload → No Evidence rows (not reported)
- **simulator_classification**: Carried via evidence_lineage → Not replicated as property

**Why Not Create All Fields as Properties:**
- Evidence preserves what the source explicitly asserted
- product_id is the subject identifier itself, not a property TO assert about the product
- sku_id and material_id are not present in PRODUCT_DEFINED source (they're infrastructure references)

================================================================================
5. CONFIGURATION_REQUESTED MAPPING TABLE
================================================================================

**Source:**
- Raw event type: CONFIGURATION_REQUESTED (7 records)
- source_system: configuration_governance
- business_object_type: configuration_request
- Configuration records: S1, S2, S3, S5, S6a, S6b, S7

**Raw Payload Expected Structure:**
```json
{
  "configuration_request_id": "CONFIG_REQ_2026_001",
  "product_id": "PROD-001",
  "launch_id": "LAUNCH-001",
  "geo": "NAMER",
  "term": 36,
  "segment": "enterprise",
  "configuration_id": null,
  "simulator_classification": "PROTOTYPE_ASSUMPTION",
  "source_version": "1.0"
}
```

**Evidence Rows to Generate (7 Raw × variable Properties = 28-33 Evidence rows total):**

**Standard Configuration Request (S1, S2, S3, S5, S6a, S6b — 6 complete records):**

| Row | evidence_type | subject_type | subject_id | property_name | asserted_value | value_type | source_path | mapping_id | count |
|-----|---|---|---|---|---|---|---|---|---|
| 1 | configuration_request | configuration_request | CONFIG_REQ_XXXX | product_reference | PROD-001 | string | payload.product_id | CONF_REQ_PRODUCT | 6 rows |
| 2 | configuration_request | configuration_request | CONFIG_REQ_XXXX | launch_reference | LAUNCH-001 | string | payload.launch_id | CONF_REQ_LAUNCH | 6 rows |
| 3 | configuration_request | configuration_request | CONFIG_REQ_XXXX | geography | NAMER/APAC/... | string | payload.geo | CONF_REQ_GEO | 6 rows |
| 4 | configuration_request | configuration_request | CONFIG_REQ_XXXX | term_months | 36/48/... | integer | payload.term | CONF_REQ_TERM | 6 rows |
| 5 | configuration_request | configuration_request | CONFIG_REQ_XXXX | customer_segment | enterprise/smb/... | string | payload.segment | CONF_REQ_SEGMENT | 6 rows |

**S7 (Incomplete Identity — segment = NULL):**

| Row | evidence_type | subject_type | subject_id | property_name | asserted_value | value_type | source_path | mapping_id | notes |
|-----|---|---|---|---|---|---|---|---|---|
| 1 | configuration_request | configuration_request | CONFIG_REQ_2026_007 | product_reference | PROD-001 | string | payload.product_id | CONF_REQ_PRODUCT | Normal |
| 2 | configuration_request | configuration_request | CONFIG_REQ_2026_007 | launch_reference | LAUNCH-001 | string | payload.launch_id | CONF_REQ_LAUNCH | Normal |
| 3 | configuration_request | configuration_request | CONFIG_REQ_2026_007 | geography | NAMER | string | payload.geo | CONF_REQ_GEO | Normal |
| 4 | configuration_request | configuration_request | CONFIG_REQ_2026_007 | term_months | 36 | integer | payload.term | CONF_REQ_TERM | Normal |
| (NO segment Evidence) | — | — | — | — | — | — | — | — | **S7 Intentionally Omits segment Evidence** |

**Why This Mapping:**

- **configuration_request_id**: Carried as subject_id, not replicated as property
- **product_id, launch_id**: Relationship facts → Evidence properties (enable entity linkage)
- **geo, term, segment**: Core business facts → Evidence properties (define configuration space)
- **configuration_id**: NULL in raw → No Evidence (pre-canonical data, not assigned yet)
- **S7 segment=NULL**: NO segment Evidence row created (allows Fold to derive UNREPORTED state)

**S6 Business Duplicate Handling:**
- S6a: source_record_id=CONFIG_REQ_2026_005, configuration_request_id=CONFIG-REQ-2026-006
- S6b: source_record_id=CONFIG_REQ_2026_006, configuration_request_id=CONFIG-REQ-2026-006B
- Evidence preserves BOTH records independently by raw_event_id lineage
- Idempotency key ensures no collapse on replay
- Business deduplication is a LATER concern (Fold/Decisions, not Evidence)

================================================================================
6. RELATIONSHIP REPRESENTATION DECISION
================================================================================

**Decision: Relationships as Evidence Properties**

Evidence does NOT introduce a separate relationship table.

Relationships (Product→Launch, ConfigRequest→Product, ConfigRequest→Launch) are represented as:
- **Evidence properties** with property_name = "{entity}_reference"
- **value_type** = "string"
- **asserted_value** = the ID of the related entity
- **evidence_lineage.source_path** = the Raw field that sourced this relationship

**Example:**
```
evidence_type: "configuration_request"
subject_type: "configuration_request"
subject_id: "CONFIG_REQ_2026_001"
property_name: "product_reference"
asserted_value: "PROD-001"
value_type: "string"
evidence_lineage: {
  "event_type": "CONFIGURATION_REQUESTED",
  "mapping_id": "CONF_REQ_PRODUCT",
  "source_path": "payload.product_id",
  "raw_event_id": "<raw_event_id>"
}
```

**Why This Approach:**
- Consistent with existing Evidence architecture (relationships are properties)
- Preserves source intent without invention
- Enables Fold to build entity graphs later via Evidence property values
- No schema changes required

================================================================================
7. LINEAGE MAPPING
================================================================================

**Evidence Lineage Structure (stored in evidence_lineage jsonb column):**

```json
{
  "event_type": "<Raw event_type>",
  "mapping_id": "<Transformation rule identifier>",
  "source_path": "<JSONPath to value in raw.payload>",
  "raw_event_id": "<UUID of source raw.raw_event>"
}
```

**For All 8 Prototype Records:**

| Evidence Property | event_type | mapping_id | source_path | raw_event_id |
|---|---|---|---|---|
| product_name (PRODUCT_DEFINED) | PRODUCT_DEFINED | PRODUCT_DEF_NAME | payload.product_name | <UUID> |
| launch_reference (PRODUCT_DEFINED) | PRODUCT_DEFINED | PRODUCT_DEF_LAUNCH | payload.launch_id | <UUID> |
| product_reference (CONF_REQ) | CONFIGURATION_REQUESTED | CONF_REQ_PRODUCT | payload.product_id | <UUID> |
| launch_reference (CONF_REQ) | CONFIGURATION_REQUESTED | CONF_REQ_LAUNCH | payload.launch_id | <UUID> |
| geography (CONF_REQ) | CONFIGURATION_REQUESTED | CONF_REQ_GEO | payload.geo | <UUID> |
| term_months (CONF_REQ) | CONFIGURATION_REQUESTED | CONF_REQ_TERM | payload.term | <UUID> |
| customer_segment (CONF_REQ) | CONFIGURATION_REQUESTED | CONF_REQ_SEGMENT | payload.segment | <UUID> (S1-S6 only) |

**Timestamp Mapping (for all Evidence):**
- occurred_at: Copy from raw.occurred_at
- recorded_at: Copy from raw.recorded_at
- arrival_at: Copy from raw.arrival_at
- created_at: Current timestamp when Evidence is generated
- simulator_classification: Copy from raw.payload.simulator_classification (if present) OR "PROTOTYPE_ASSUMPTION"

**Source System Mapping (for all Evidence):**
- source_system: Copy from raw.source_system (product_definition or configuration_governance)
- source_actor_role: "process" (inferred from prototype marker)

================================================================================
8. S6 BUSINESS DUPLICATE BEHAVIOR
================================================================================

**S6a and S6b are TWO DISTINCT SOURCE FACTS:**

Raw Records:
```
S6a: source_record_id=CONFIG_REQ_2026_005, configuration_request_id=CONFIG-REQ-2026-006
     product_id=PROD-001, geo=NAMER, term=36, segment=enterprise

S6b: source_record_id=CONFIG_REQ_2026_006, configuration_request_id=CONFIG-REQ-2026-006B
     product_id=PROD-001, geo=NAMER, term=36, segment=enterprise
```

**Evidence Generated:**

S6a produces 5 Evidence rows:
- subject_id: CONFIG-REQ-2026-006 (using configuration_request_id)
- property_name: product_reference, launch_reference, geography, term_months, customer_segment
- raw_event_id: <UUID of S6a raw event>

S6b produces 5 Evidence rows:
- subject_id: CONFIG-REQ-2026-006B (using configuration_request_id)
- property_name: product_reference, launch_reference, geography, term_months, customer_segment
- raw_event_id: <UUID of S6b raw event>

**Idempotency:**
- Each Evidence row is uniquely identified by: (raw_event_id, property_name, subject_type, subject_id)
- S6a and S6b have different raw_event_ids → Different Evidence rows despite identical business properties
- Replay of same Raw corpus: Transformer checks if raw_event_id already processed → No duplicate Evidence

**Why Preserve Both:**
- Raw facts are evidence layer input
- Business deduplication is a LATER concern (Fold derives: "two source facts represent same business configuration")
- Evidence is "what the source said", not "what the business means"

================================================================================
9. S7 MISSING SEGMENT BEHAVIOR
================================================================================

**S7 Raw Record:**
```
source_record_id: CONFIG_REQ_2026_007
product_id: PROD-001
launch_id: LAUNCH-001
geo: NAMER
term: 36
segment: null  ← INTENTIONALLY MISSING
```

**Evidence Generated (4 rows, NOT 5):**

| property_name | asserted_value | included | reason |
|---|---|---|---|
| product_reference | PROD-001 | YES | Explicitly stated |
| launch_reference | LAUNCH-001 | YES | Explicitly stated |
| geography | NAMER | YES | Explicitly stated |
| term_months | 36 | YES | Explicitly stated |
| customer_segment | ??? | NO | Not in source; DO NOT INVENT |

**Why No segment Evidence:**
- segment is NULL in raw payload
- Evidence preserves what the source asserted
- Source did not assert segment → No Evidence property for segment
- Fold can later infer: "segment = UNREPORTED" (from absence of segment Evidence)

**Critical:**
- Do NOT create Evidence rows with:
  - property_name = "customer_segment", asserted_value = "NULL"
  - property_name = "customer_segment", asserted_value = "UNKNOWN"
  - property_name = "customer_segment", asserted_value = "MISSING"
- This allows downstream Fold to distinguish:
  - "segment was reported as NULL" (would have Evidence) vs.
  - "segment was not reported at all" (no Evidence) ← S7

================================================================================
10. PROVENANCE HANDLING
================================================================================

**simulator_classification = PROTOTYPE_ASSUMPTION**

This field is present in Evidence schema: `simulator_classification (varchar, nullable)`

**Mapping Decision:**
- Copy `raw.payload.simulator_classification` to Evidence.simulator_classification
- All 8 prototype records have: `simulator_classification = "PROTOTYPE_ASSUMPTION"`
- This preserves provenance without invention

**Alternative:** Infer from evidence_lineage.mapping_id (all mappings starting with "PRODUCT_DEF_", "CONF_REQ_" are prototypes)

**Chosen Approach:** Direct copy for clarity

**Result:**
- All 8 evidence rows: simulator_classification = "PROTOTYPE_ASSUMPTION"
- Searchable in Evidence table for testing/prototype queries
- Traceable through raw_event_id lineage if needed

================================================================================
11. EXACT EXPECTED NUMBER OF NEW EVIDENCE ROWS
================================================================================

**Calculation:**

**PRODUCT_DEFINED (1 Raw Record):**
- S1: 1 Raw × 2 Properties = 2 Evidence rows
  - product_name
  - launch_reference
- Subtotal: **2 Evidence rows**

**CONFIGURATION_REQUESTED — Complete Records (6 Raw Records: S1, S2, S3, S5, S6a, S6b):**
- Each: 1 Raw × 5 Properties = 5 Evidence rows
  - product_reference
  - launch_reference
  - geography
  - term_months
  - customer_segment
- Subtotal: 6 Raw × 5 = **30 Evidence rows**

**CONFIGURATION_REQUESTED — Incomplete Record (1 Raw Record: S7):**
- S7: 1 Raw × 4 Properties = 4 Evidence rows
  - product_reference
  - launch_reference
  - geography
  - term_months
  - (NO customer_segment due to NULL in source)
- Subtotal: **4 Evidence rows**

**TOTAL NEW EVIDENCE: 2 + 30 + 4 = 36 Evidence rows**

**Expected Future Total:**
- Current Evidence: 107 rows
- New Evidence: 36 rows
- **Expected total: 107 + 36 = 143 Evidence rows**

================================================================================
12. EXPECTED FUTURE TOTAL EVIDENCE COUNT
================================================================================

**Before Step 5E.2:** 107 rows
**New from Step 5E.2:** 36 rows
**After Step 5E.2:** **143 rows**

This assumes:
- No filtering/conditional Evidence generation
- All 8 Raw records fully processed
- Idempotency prevents re-creation on replay

================================================================================
13. SCHEMA CHANGE REQUIREMENT
================================================================================

**Verdict: NO SCHEMA CHANGE REQUIRED** ✓

The current Evidence schema accommodates the new record types without modification:

| Feature Required | Schema Field | Status |
|---|---|---|
| Product entity tracking | subject_type = "product", subject_id = "PROD-001" | ✓ Exists |
| Configuration entity tracking | subject_type = "configuration_request", subject_id = "CONFIG_REQ_xxx" | ✓ Exists |
| Multiple properties per entity | Multiple rows per subject_id | ✓ Supported |
| Relationship facts | property_name = "{entity}_reference", asserted_value = "ID" | ✓ Pattern exists |
| Incomplete identity (S7) | Conditional Evidence generation per property | ✓ Application logic |
| Provenance tracking | simulator_classification, evidence_lineage | ✓ Exists |
| Raw lineage | raw_event_id, evidence_lineage.raw_event_id | ✓ Exists |
| Transformation tracking | mapping_id, evidence_lineage.mapping_id | ✓ Exists |

**Application-Level Changes Needed (not schema):**
- Transformer must implement PRODUCT_DEFINED → Evidence logic
- Transformer must implement CONFIGURATION_REQUESTED → Evidence logic
- Transformer must skip segment Evidence for S7 (conditional logic)
- Transformer must check (raw_event_id, mapping_id) for idempotency before insert

================================================================================
14. GAPS / UNRESOLVED ASSUMPTIONS
================================================================================

| Gap | Impact | Resolution |
|---|---|---|
| Exact Evidence Transformer location/language | Cannot audit full logic | Assumed: database/procedures/ or database/evidence/transformers/ |
| Whether Evidence idempotency is DB constraint or app logic | Affects replay behavior | Assumed: Application-level check (no UNIQUE constraint on (raw_event_id, property_name)) |
| Exact "launch_reference" property naming convention | Property name mapping | Assumed: Consistent with "{entity}_reference" pattern seen in samples |
| Whether all Evidence must have value_json populated | Data completeness | Assumed: asserted_value is sufficient; value_json optional for complex types |
| Exact source_actor_id for prototype events | Event attribution | Assumed: NULL (not attributed to specific actor) or generic "prototype" |
| Fold expectations for segment = UNREPORTED | Downstream behavior | Assumed: Fold will infer from absence of segment Evidence |
| Whether Evidence DELETE is ever used for replay | Idempotency model | Assumed: INSERT IF NOT EXISTS pattern, never DELETE |

================================================================================
15. EXACT FILES THAT WOULD NEED MODIFICATION IN STEP 5E.2
================================================================================

**Files to Create or Modify (estimated):**

1. **Evidence Transformer (likely one of):**
   - `database/procedures/transform_raw_to_evidence.sql` OR
   - `database/evidence/transformers/raw_event_transformer.py` OR
   - `database/evidence/transformers/product_definition_transformer.sql` OR
   - `database/evidence/transformers/configuration_request_transformer.sql`
   - **Change:** Add PRODUCT_DEFINED and CONFIGURATION_REQUESTED cases to transformer

2. **Evidence Mapping Configuration (if externalized):**
   - `database/evidence/mappings/product_definition_mappings.json` OR
   - `database/evidence/mappings/configuration_request_mappings.json`
   - **Change:** Define property extraction rules

3. **Evidence Tests (new):**
   - `tests/evidence/test_product_defined_evidence_generation.py` OR
   - `tests/evidence/test_configuration_request_evidence_generation.py`
   - **Change:** Add assertions for expected Evidence row counts and lineage

4. **Integration Tests:**
   - `tests/integration/test_raw_to_evidence_flow.py`
   - **Change:** Add PRODUCT_DEFINED and CONFIGURATION_REQUESTED scenarios

================================================================================
16. EXACT TESTS THAT SHOULD BE ADDED/UPDATED
================================================================================

**New Test Suite 1: PRODUCT_DEFINED Evidence Generation**

```python
def test_product_defined_generates_2_evidence_rows():
    # Given: 1 PRODUCT_DEFINED Raw record
    # When: Transformer processes it
    # Then: 2 Evidence rows created (product_name, launch_reference)
    assert evidence_count_for_raw(raw_event_id) == 2
    assert evidence_has_property(raw_event_id, "product_name")
    assert evidence_has_property(raw_event_id, "launch_reference")

def test_product_defined_preserves_lineage():
    # Given: PRODUCT_DEFINED Raw event
    # When: Evidence is generated
    # Then: evidence_lineage.raw_event_id matches Raw event UUID
    evidence = get_evidence_for_raw(raw_event_id)
    assert evidence.evidence_lineage["raw_event_id"] == raw_event_id
    assert evidence.evidence_lineage["mapping_id"] == "PRODUCT_DEF_NAME"

def test_product_defined_idempotency():
    # Given: PRODUCT_DEFINED Raw already processed
    # When: Transformer replays same Raw
    # Then: No duplicate Evidence rows created
    initial_count = count_evidence_for_raw(raw_event_id)
    replay_transformer(raw_event_id)
    assert count_evidence_for_raw(raw_event_id) == initial_count
```

**New Test Suite 2: CONFIGURATION_REQUESTED Evidence Generation (Complete)**

```python
def test_configuration_requested_complete_generates_5_evidence_rows():
    # Given: CONFIGURATION_REQUESTED Raw with all fields (S1-S6)
    # When: Transformer processes it
    # Then: 5 Evidence rows created
    assert evidence_count_for_raw(raw_event_id) == 5
    assert evidence_has_property(raw_event_id, "product_reference")
    assert evidence_has_property(raw_event_id, "launch_reference")
    assert evidence_has_property(raw_event_id, "geography")
    assert evidence_has_property(raw_event_id, "term_months")
    assert evidence_has_property(raw_event_id, "customer_segment")

def test_configuration_requested_preserves_relationships():
    # Given: CONFIGURATION_REQUESTED Raw
    # When: Evidence is generated
    # Then: Relationship properties have correct values
    evidence = get_evidence_by_property(raw_event_id, "product_reference")
    assert evidence.asserted_value == raw_payload["product_id"]
    assert evidence.evidence_lineage["source_path"] == "payload.product_id"
```

**New Test Suite 3: S7 Incomplete Identity (No segment)**

```python
def test_configuration_requested_s7_missing_segment_generates_4_not_5_evidence():
    # Given: CONFIGURATION_REQUESTED Raw with segment = NULL (S7)
    # When: Transformer processes it
    # Then: 4 Evidence rows (NO segment Evidence)
    assert evidence_count_for_raw(s7_raw_event_id) == 4
    assert NOT evidence_has_property(s7_raw_event_id, "customer_segment")
    assert evidence_has_property(s7_raw_event_id, "product_reference")

def test_configuration_requested_s7_allows_fold_to_derive_unreported():
    # Given: S7 Evidence without segment property
    # When: Fold processes Evidence
    # Then: Can infer segment = UNREPORTED (not UNKNOWN, not NULL)
    # Note: This is a Fold test, not Evidence test, but documents the contract
    pass
```

**New Test Suite 4: S6 Business Duplicate**

```python
def test_s6_business_duplicate_preserves_both_sources():
    # Given: S6a and S6b Raw (same business config, different source records)
    # When: Transformer processes both
    # Then: Both generate Evidence independently
    s6a_count = evidence_count_for_raw(s6a_raw_event_id)
    s6b_count = evidence_count_for_raw(s6b_raw_event_id)
    assert s6a_count == 5
    assert s6b_count == 5
    assert s6a_raw_event_id != s6b_raw_event_id
    assert Evidence_not_collapsed_by_business_identity()

def test_s6_idempotency_per_raw_not_per_business():
    # Given: S6 raw events already processed
    # When: Same raw_event_ids replayed
    # Then: Evidence not duplicated (idempotency on raw_event_id, not business_id)
    initial_count = count_all_evidence()
    replay_both_s6_raw_events()
    assert count_all_evidence() == initial_count
```

**Update Existing Tests:**

- `tests/evidence/test_evidence_idempotency.py` — Add PRODUCT_DEFINED and CONFIGURATION_REQUESTED cases
- `tests/integration/test_raw_to_evidence_flow.py` — Add prototype records to integration test suite
- `tests/raw/test_raw_event_structure.py` — Verify PRODUCT_DEFINED and CONFIGURATION_REQUESTED schema compatibility

================================================================================
17. CONFIRMATION: NO DB/S3 WRITES OCCURRED
================================================================================

✓ **Confirmed: No database writes**
- This step is DESIGN ONLY
- No Evidence rows inserted
- No raw.raw_event modifications
- No other table modifications
- Database remains at: Raw=177, Evidence=107, Assertion=107, Fold=51

✓ **Confirmed: No S3 operations**
- No new files uploaded
- No existing S3 objects modified
- S3 contains: 28 JSONL files (26 original + 2 from Step 5D.2)

✓ **Confirmed: No repository modifications**
- No files created
- No files edited
- No commits made
- Git status: clean (only untracked test/design artifacts in workspace)

================================================================================
18. CONFIRMATION: NO FILES WERE MODIFIED
================================================================================

✓ **All repository files remain unchanged:**
- database/evidence/ — not modified
- database/procedures/ — not modified
- database/raw/ — not modified
- tests/evidence/ — not modified
- tests/raw/ — not modified

✓ **This document is design output only:**
- No code implementation
- No SQL/Python execution
- No schema changes
- No data changes

================================================================================
FINAL STATUS: READY FOR IMPLEMENTATION
================================================================================

**✓ STEP 5E.1 RAW → EVIDENCE MAPPING DESIGN COMPLETE — READY FOR IMPLEMENTATION**

**Summary of Design Decisions:**

1. **PRODUCT_DEFINED → 2 Evidence rows:**
   - product_name (property_name: product_name)
   - launch_reference (property_name: launch_reference)

2. **CONFIGURATION_REQUESTED (S1-S6) → 5 Evidence rows each (30 total):**
   - product_reference
   - launch_reference
   - geography
   - term_months
   - customer_segment

3. **CONFIGURATION_REQUESTED (S7) → 4 Evidence rows (intentionally omits segment):**
   - product_reference
   - launch_reference
   - geography
   - term_months

4. **Total New Evidence: 36 rows** (2 + 30 + 4)
   - Expected future total: 143 rows (107 current + 36 new)

5. **Idempotency:** Transformer checks (raw_event_id, mapping_id) before insert
   - No schema changes required
   - Replay produces 0 new Evidence rows

6. **Relationships:** Represented as Evidence properties (product_reference, launch_reference)
   - No separate relationship table
   - Consistent with existing Evidence architecture

7. **S6 Business Duplicate:** Both sources preserved as independent Evidence
   - raw_event_id maintains uniqueness
   - Business deduplication deferred to Fold

8. **S7 Missing Segment:** No segment Evidence row created
   - Allows Fold to infer: segment = UNREPORTED

9. **Provenance:** simulator_classification = PROTOTYPE_ASSUMPTION copied from Raw
   - All 36 evidence rows marked as prototype

10. **No Schema Changes Required:** Existing Evidence table accommodates all 8 record types

================================================================================
NEXT STEP: STEP 5E.2 EVIDENCE GENERATION IMPLEMENTATION
================================================================================

Ready to implement Evidence generation when authorized.

Files to create/modify:
- Evidence transformer (location TBD from repository)
- New mapping configurations for PRODUCT_DEFINED and CONFIGURATION_REQUESTED
- New/updated test cases

Do NOT proceed to Step 5E.2 until this design is approved.

================================================================================

---

## STEP 5E.3C ADDENDUM — NESTED PAYLOAD DISCOVERY

### Live Raw Contract Verified

The `raw.raw_event` table physical structure:
- Stores the complete source event envelope in the `payload` JSONB column
- For `PRODUCT_DEFINED` events: business fields are at the top level of `payload`
- For `CONFIGURATION_REQUESTED` events: business fields are nested under `payload->'payload'`

### Nested Business Payload Structure

```
raw.raw_event.payload (envelope)
└── payload (business payload for CONFIGURATION_REQUESTED)
    ├── configuration_request_id
    ├── product_id
    ├── launch_id
    ├── geo
    ├── term
    ├── segment
    └── simulator_classification
```

### Authoritative Extraction Paths (Corrected)

**PRODUCT_DEFINED:**
- `r.payload->>'product_id'` (top-level)
- `r.payload->>'product_name'` (top-level)
- `r.payload->>'launch_id'` (top-level)

**CONFIGURATION_REQUESTED:**
- `r.payload->'payload'->>'configuration_request_id'` (nested)
- `r.payload->'payload'->>'product_id'` (nested)
- `r.payload->'payload'->>'launch_id'` (nested)
- `r.payload->'payload'->>'geo'` (nested)
- `r.payload->'payload'->>'term'` (nested)
- `r.payload->'payload'->>'segment'` (nested)

### Loader Normalization Discrepancy

The prototype Raw records exhibit the following:

**Physical column: `raw.raw_event.simulator_classification`**
- NULL for all CONFIGURATION_REQUESTED records
- Indicates incomplete normalization during load

**Nested in payload JSON: `payload.payload.simulator_classification`**
- `'PROTOTYPE_ASSUMPTION'` for all prototype events
- Preserved from original source event envelope

**Treatment:**
- This is a loader-level normalization gap, not a data quality issue
- The authoritative PROTOTYPE_ASSUMPTION classification is in the nested payload
- Evidence markers use `r.payload->>'simulator_classification'` for lineage
- No Raw table modifications are required as part of STEP 5E

### Evidence Mapping Update

All CONFIGURATION_REQUESTED Evidence extraction has been corrected to use the nested business payload paths, ensuring accurate subject_id and property_value assignment.

