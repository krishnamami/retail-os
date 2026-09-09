# STEP 5A — CANONICAL STATE DESIGN & MODULAR PLACEMENT PREFLIGHT

**Date:** 2026-09-07  
**Status:** DESIGN ONLY — NO IMPLEMENTATION  
**Authorization:** STEP 5A Canonical State Design & Preflight

---

## EXECUTIVE SUMMARY

**CURRENT ARCHITECTURE STATE:**
- ✅ Raw Layer: 169 events (complete)
- ✅ Evidence Layer: 107 extracted (complete)
- ✅ Assertion Layer: 107 created (complete)
- ✅ Fold Layer: 51 snapshots, 177 properties (complete & idempotent)
- ⏸ Canonical Layer: Design phase (empty placeholder files exist)
- ⏸ Decisions Layer: Awaiting Canonical
- ⏸ Actions, Projection, Workbench, Agents: Downstream

**REPOSITORY AUDIT FINDINGS:**
| Finding | Status | Impact |
|---------|--------|--------|
| canonical/ folder exists | ✓ Present | 3 empty .py placeholder files (0 bytes each) |
| tests/canonical/ folder exists | ✗ Missing | No test coverage structure for Canonical |
| projection.py in canonical/ | ✗ Contamination | Should be in retail_os/projection/ (not yet created) |
| Configuration schema | ✗ Missing | No DDL/SQL design yet |
| Product schema | ✗ Missing | No DDL/SQL design yet |
| Configuration Version schema | ✗ Missing | No DDL/SQL design yet |

---

## 1. CANONICAL PURPOSE

**Canonical State answers:**
"What stable business objects and versions can be established from the governed Fold state?"

**Canonical State is NOT:**
- Raw source data (that's Raw Layer)
- Evidence extraction (that's Evidence Layer)
- Assertion creation (that's Assertion Layer)
- Fold computation (that's Fold Layer)
- Governed decisions (that's Decisions Layer)
- Action authorization (that's Actions Layer)
- Downstream system projection (that's Projection Layer)
- UI model (that's Workbench Layer)
- Agent orchestration (that's Agents Layer)

**Canonical State IS:**
A stable, traceable, business-object repository that materializes only when:
1. Fold state is ESTABLISHED (not UNREPORTED/CONTRADICTED)
2. Governance rules are satisfied
3. Upstream immutability is preserved
4. Identity semantics are explicitly authorized

---

## 2. PROPOSED MODULAR CANONICAL FOLDER STRUCTURE

**Recommended Structure (Do NOT create yet):**

```
retail_os/
├── canonical/
│   ├── README.md                          [Canonical module purpose & governance]
│   ├── schema/
│   │   ├── 001_product.sql               [Product entity definition]
│   │   ├── 002_configuration.sql         [Configuration entity definition]
│   │   ├── 003_configuration_version.sql [Configuration versioning]
│   │   └── 004_canonical_meta.sql        [Canonical system metadata]
│   │
│   ├── transforms/
│   │   ├── 001_product_derivation.sql    [Product identity derivation logic]
│   │   ├── 002_configuration_derivation.sql [Configuration identity derivation]
│   │   ├── 003_version_state_derivation.sql [Version state derivation]
│   │   └── 999_canonical_materialization.sql [Main materialization entry point]
│   │
│   ├── lineage/
│   │   ├── 001_canonical_lineage_schema.sql  [Lineage table definitions]
│   │   └── 002_lineage_population.sql        [How to trace Canonical → Decision → Fold → Assert → Evid → Raw]
│   │
│   ├── validation/
│   │   ├── 001_canonical_constraints.sql    [CHECK/UNIQUE/FK validation]
│   │   ├── 002_temporal_validation.sql      [valid_from/valid_to semantics]
│   │   └── 003_immutability_validation.sql  [Verify Fold immutability post-insert]
│   │
│   └── models/
│       └── canonical_data_model.md          [Conceptual model documentation]
│
├── tests/
│   ├── canonical/                           [NEW: Create this folder]
│   │   ├── test_schema.sql                  [DDL validity & constraints]
│   │   ├── test_product_identity.sql        [Product derivation correctness]
│   │   ├── test_configuration_identity.sql  [Configuration derivation correctness]
│   │   ├── test_version_materialization.sql [Version state correctness]
│   │   ├── test_lineage.sql                 [Lineage traceability]
│   │   ├── test_temporal_semantics.sql      [Temporal field correctness]
│   │   ├── test_idempotency.sql             [Materialization idempotency]
│   │   ├── test_immutability.sql            [Upstream immutability verification]
│   │   └── test_cannot_decide_behavior.sql  [Missing data behavior]
│   │
│   └── [fold/, raw/, evidence/, assertion/] [Existing test layers]
```

**Rationale:**
- Canonical implementation files live ONLY under retail_os/canonical/
- Tests live ONLY under tests/canonical/
- Clear separation: schema/ | transforms/ | lineage/ | validation/ | models/
- Flat file naming: 001, 002, 003... (sequential deployment order)
- No .py files in canonical/ at this phase (SQL-first for data layer)
- projection/ will be SEPARATE folder (not shown; created in later phase)

---

## 3. PROPOSED TEST FOLDER STRUCTURE

**Create NEW:** `retail_os/tests/canonical/`

```
tests/canonical/
├── test_schema.sql                    [DDL syntax, constraints, types]
├── test_product_identity.sql          [Product derivation rules]
├── test_configuration_identity.sql    [Configuration derivation rules]
├── test_version_materialization.sql   [Version state from Fold + Decision]
├── test_lineage.sql                   [Lineage traceability to Raw]
├── test_temporal_semantics.sql        [valid_from, valid_to, created_at distinctions]
├── test_idempotency.sql               [Canonical materialization is idempotent]
├── test_immutability.sql              [Fold/Assertion/Evidence unchanged post-insert]
├── test_cannot_decide_behavior.sql    [Behavior when UNREPORTED/CONTRADICTED]
└── test_materialization_order.sql     [Deployment sequence validation]
```

Each test file will:
1. Set up known Fold state
2. Execute Canonical materialization
3. Verify expected output
4. Confirm no upstream mutation
5. Teardown

---

## 4. FILE-TO-MODULE OWNERSHIP MAP

| File | Purpose | Module | Owning Phase | Test File |
|------|---------|--------|--------------|-----------|
| schema/001_product.sql | Product entity DDL | Canonical | 5B | test_schema.sql |
| schema/002_configuration.sql | Configuration entity DDL | Canonical | 5B | test_schema.sql |
| schema/003_configuration_version.sql | Version entity DDL | Canonical | 5B | test_schema.sql |
| schema/004_canonical_meta.sql | System metadata tables | Canonical | 5B | test_schema.sql |
| transforms/001_product_derivation.sql | Product identity logic | Canonical | 5C | test_product_identity.sql |
| transforms/002_configuration_derivation.sql | Configuration identity logic | Canonical | 5C | test_configuration_identity.sql |
| transforms/003_version_state_derivation.sql | Version state logic | Canonical | 5D | test_version_materialization.sql |
| transforms/999_canonical_materialization.sql | Main entry point | Canonical | 5E | test_materialization_order.sql |
| lineage/001_canonical_lineage_schema.sql | Lineage table DDL | Canonical | 5C | test_lineage.sql |
| lineage/002_lineage_population.sql | Lineage logic | Canonical | 5D | test_lineage.sql |
| validation/001_canonical_constraints.sql | CHECK/UNIQUE/FK constraints | Canonical | 5B | test_schema.sql |
| validation/002_temporal_validation.sql | Temporal correctness | Canonical | 5D | test_temporal_semantics.sql |
| validation/003_immutability_validation.sql | Immutability assurance | Canonical | 5E | test_immutability.sql |
| models/canonical_data_model.md | Conceptual documentation | Canonical | 5A | (reference) |

**Ownership Rule:** Every file created in retail_os/canonical/ or tests/canonical/ is the responsibility of the CANONICAL module. No file outside these folders may contain Canonical implementation logic.

---

## 5. EXISTING REPOSITORY PLACEMENT AUDIT

**AUDIT RESULTS:**

| Location | Finding | Status | Action Required |
|----------|---------|--------|-----------------|
| canonical/configuration.py | Empty placeholder (0 bytes) | ⚠️ Exists but no content | Keep or remove per preference; do NOT implement in |
| canonical/configuration_version.py | Empty placeholder (0 bytes) | ⚠️ Exists but no content | Keep or remove per preference; do NOT implement in |
| canonical/projection.py | Empty placeholder (0 bytes) | ❌ MISPLACED | Should NOT be in canonical/; belongs in retail_os/projection/ (future) |
| tests/canonical/ | Does NOT exist | ❌ MISSING | CREATE this folder; add .gitkeep; create test files as designed |
| database/ddl/ | Contains fold, raw schemas | ✅ Correct | Separate from canonical/; do not modify |
| database/fold/ | Contains fold procedures | ✅ Correct | Separate from canonical/; do not modify |

**CRITICAL PLACEMENT VIOLATIONS:**
1. ❌ projection.py should NOT be in canonical/ folder
2. ❌ tests/canonical/ does not exist (test isolation broken)
3. ⚠️ Empty .py files are placeholders (phase is SQL/DDL-first, not Python-first)

**Recommended Remediation (Do NOT execute in STEP 5A):**
1. Leave canonical/configuration.py, configuration_version.py as-is (placeholder)
2. Move canonical/projection.py → retail_os/projection/projection.py (when projection phase starts)
3. Create tests/canonical/ folder with test files designed in Section 3
4. Do NOT add Python implementation to canonical/ at this phase

---

## 6. PRODUCT IDENTITY ASSESSMENT

**Question:** Can the current Fold + KB establish a stable Product identity?

**Analysis:**

From Fold subjects:
- 13 SKUs exist (sku-001 ... sku-013, plus SKU-006 tested)
- 13 Launches exist
- 3 Materials exist
- 22 Configurations exist

**Assumption Validation (DISPROVE if incorrect):**
- ❌ SKU ≠ Product (SKUs are catalog entities, Products are business entities)
- ❌ Material ≠ Product (Materials are components, Products are aggregates)
- ❌ Launch ≠ Product (Launches are temporal events, Products are stable)
- ❌ Configuration ≠ Product (Configurations are sellable variants)
- ❓ Product identity source is UNKNOWN

**Known Data Gap:**
- UC-18 status: "CONFIGURATION IDENTITY CONTRACT NEEDED"
- Pre-mint product dimensions missing from Raw source
- No explicit Product entities in Fold state
- No product_id or product_identity properties observed (requires preflight query execution)

**Current Product Identity Evidence:**
| Evidence Type | Exists? | Confidence | Notes |
|---|---|---|---|
| Explicit product_id in Fold | ? | N/A | Must verify via preflight query |
| Product hierarchy/family concept | ? | N/A | Must verify via preflight query |
| Product classification/type | ? | N/A | Must verify via preflight query |
| Product lifecycle rules in KB | ? | N/A | Must inspect knowledge_base.policies |
| Product versioning semantics | ? | N/A | Must inspect knowledge_base.policies |

**VERDICT (Provisional):**
```
CANNOT SAFELY ESTABLISH PRODUCT IDENTITY YET

Reason: No explicit Product entity observed in Fold.
        Must execute preflight query to confirm.
        If missing, Product identity requires GOVERNANCE DECISION input
        (e.g., "Is a Product derived from Configuration?" or other rule).
        
Dependency: Preflight query results required.
```

---

## 7. CONFIGURATION IDENTITY ASSESSMENT

**Question:** Can current Fold state establish stable Configuration identity?

**Known Configuration Properties (ASSUMED):**
From Fold: 22 configurations exist in snapshot

**Configuration Identity Inputs Required:**
From authorization: "Do NOT use hierarchy_code alone as configuration identity"

**KB Identity Rules:**
- IR-001 through IR-009 exist (must inspect read-only)
- Cannot proceed without reviewing actual KB rules

**Configuration Identity Derivation:**
```
Configuration Identity must answer:
  "Which Fold configuration subject can be promoted to canonical.configuration?"
  
Candidates:
  - All 22 that are ESTABLISHED?
  - Only those where all identity inputs are ESTABLISHED?
  - Only those authorized by a governed IDENTITY_ASSESSMENT decision?
```

**Configuration Identity Preflight Checklist:**

| Input | Status | Where From | Required? |
|-------|--------|-----------|-----------|
| configuration_id | ? | Fold subject_id | ✅ Yes |
| product_id | ? | (TBD) | ? Depends on Product rule |
| identity_key | ? | Fold + KB rules | ✅ Yes |
| sellable_status | ? | Fold properties | ? Depends on rules |
| market_availability | ? | Fold properties (UNREPORTED?) | ? May be missing |
| channel | ? | Fold properties (missing?) | ? May be missing |
| pricing_model | ? | Fold properties (UNREPORTED?) | ? May be missing |
| intended_segment | ? | Fold properties (missing?) | ✅ No - do NOT fabricate |

**VERDICT (Provisional):**
```
CANNOT SAFELY ESTABLISH CONFIGURATION IDENTITY YET

Reason: Identity rules IR-001..IR-009 must be read.
        Required identity inputs must be verified as ESTABLISHED in Fold.
        UC-18 gap (duplicate prevention dimensions missing).
        
Dependency: Must inspect KB rules + preflight Fold properties + IDENTITY_ASSESSMENT decision.
```

---

## 8. CONFIGURATION VERSION ASSESSMENT

**Question:** Can current Fold establish Configuration Versions?

**Configuration Version Semantics:**
```
One stable Configuration → Multiple Versions
  - Version 1 (valid_from: T0, valid_to: T1)
  - Version 2 (valid_from: T1, valid_to: T2)
  - Version 3 (valid_from: T2, valid_to: ∞)
```

**Required Fields for configuration_version:**

| Field | Source | Available? | Notes |
|-------|--------|-----------|-------|
| version_id | System-generated | ✅ Yes | UUID in Canonical |
| configuration_id | Fold subject_id | ✅ Yes | From Fold |
| version_no | System-generated | ✅ Yes | Increment counter |
| valid_from | Fold decision_horizon or Decision | ⚠️ Partial | Fold provides timestamp; unclear if this = valid_from |
| valid_to | Future horizon or Decision | ❌ No | Not available until next version; requires Decisions |
| change_type | Governed Decision | ❌ No | CHANGE_CLASSIFICATION must execute first |
| identity_effect | Governed Decision | ❌ No | IDENTITY_ASSESSMENT must execute first |
| created_by_decision | Governed Decision ID | ❌ No | Decisions not yet executed |

**Temporal Semantics Problem:**
```
Fold decision_horizon = "2026-06-20 10:45:00+00" (current cut)
Canonical valid_from = ? (should equal decision_horizon? or something else?)
Canonical valid_to = ? (unknown until next cut; requires future Decision execution)

RISK: If we set valid_to = ∞ for first version, it implies this version is current forever.
      But next Canonical materialization might need to set valid_to = current and create v2.
      This requires Decisions to already have executed CHANGE_CLASSIFICATION.
```

**VERDICT:**
```
CANNOT SAFELY ESTABLISH CONFIGURATION VERSIONS YET

Reason: Version lifecycle (change_type, identity_effect, created_by_decision) 
        depends on Governed Decisions that haven't executed yet.
        
Dependency: Must complete CHANGE_CLASSIFICATION and IDENTITY_ASSESSMENT before version materialization.
            Bootstrap approach: Create first version with change_type = "BOOTSTRAP" as special case?
            (This requires explicit architecture decision.)
```

---

## 9. FOLD PROPERTIES RELEVANT TO CANONICAL

**To Be Verified:** Execute preflight queries to confirm which 177 properties exist.

**Anticipated Canonical-Relevant Properties:**

| Property Name | Subject Type | Fold State | Relevance | Notes |
|---|---|---|---|---|
| (product_id) | configuration, sku | ? | A (Product Identity) | May not exist in Fold |
| (hierarchy_code) | configuration, sku | ? | E (Projection only) | DO NOT use for identity |
| (pricing_status) | configuration | ? | C (Version state) | Mutable attribute |
| (sku_activation_status) | sku | ? | C (Version state) | Mutable attribute |
| (market_status) | configuration | UNREPORTED? | F (Unknown) | May be missing |
| (intended_segment) | configuration | UNREPORTED? | F (Unknown) | Do NOT fabricate |
| (channel) | configuration | UNREPORTED? | F (Unknown) | Do NOT fabricate |

**Status:** Preflight queries needed to inventory all 177 properties and classify each.

---

## 10. MISSING REQUIRED PROPERTIES

**Known Gaps (from UC-18 analysis):**

| Property | Why Missing | Impact | Workaround |
|---|---|---|---|
| intended_segment | Raw source doesn't capture pre-mint business context | Cannot prevent duplicates | None (do NOT fabricate) |
| intended_tier | Raw source doesn't capture pre-mint business context | Cannot prevent duplicates | None (do NOT fabricate) |
| intended_term | Raw source doesn't capture pre-mint business context | Cannot prevent duplicates | None (do NOT fabricate) |
| intended_pricing_model | Raw source doesn't capture pre-mint business context | Cannot prevent duplicates | None (do NOT fabricate) |
| channel | Raw source unclear | Configuration identity incomplete | Governed Decision required |
| market/geography | Raw source unclear | Configuration identity incomplete | Governed Decision required |
| product_id | Product identity not established | Cannot derive Configuration → Product link | Depends on Product identity solution |

**Consequence:** Configuration identity cannot be fully determined without Governed Decisions and/or Raw source enhancement.

---

## 11. KB IDENTITY RULE ASSESSMENT

**Rules to Inspect (Read-Only):**
- IR-001 through IR-009 (Identity Rules in knowledge_base.rules)
- VERSIONING policies in knowledge_base.policies

**What to Determine:**
1. Do IR-001..IR-009 define product identity semantics?
2. Do they define configuration identity semantics?
3. Which Fold properties do they reference?
4. Are those properties ESTABLISHED or UNREPORTED in current Fold?
5. Do they require inputs missing from Fold?

**Status:** Cannot complete without executing preflight KB inspection queries.

---

## 12. UC-18 IMPACT (DUPLICATE PREVENTION)

**UC-18 Status:** Configuration Identity Contract Needed

**Current Impact on Canonical:**
1. Cannot establish configuration.identity_key without pre-mint business dimensions
2. Cannot guarantee duplicate prevention at configuration level
3. Canonical materialization should flag this gap explicitly

**Recommended Handling:**
```sql
-- In canonical.configuration:
ALTER TABLE canonical.configuration ADD COLUMN
  identity_completeness VARCHAR(20) DEFAULT 'INCOMPLETE'
  CHECK (identity_completeness IN ('COMPLETE', 'INCOMPLETE', 'CANNOT_DECIDE'));

-- When materializing:
INSERT INTO canonical.configuration (
  configuration_id, product_id, identity_key, identity_completeness, ...
)
SELECT
  fss.subject_id,
  (derived product_id),
  (derived identity_key),
  CASE
    WHEN (market = NULL OR channel = NULL) THEN 'INCOMPLETE'
    ELSE 'COMPLETE'
  END,
  ...
FROM Fold
LEFT JOIN ... (identity rules)
WHERE (identity inputs are ESTABLISHED)
   OR (identity inputs missing; flag INCOMPLETE instead of fabricating);
```

**Decision Required:** Should Canonical skip a configuration if identity is INCOMPLETE, or should it materialize with a flag?

---

## 13. PROPOSED PRODUCT SCHEMA

**⚠️ PROVISIONAL (Cannot finalize without Product identity decision)**

```sql
-- canonical/schema/001_product.sql
CREATE TABLE canonical.product (
  product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_name TEXT NOT NULL,
  product_code TEXT NOT NULL UNIQUE,
  product_status VARCHAR(20) NOT NULL
    CHECK (product_status IN ('ACTIVE', 'INACTIVE', 'DISCONTINUED', 'CANNOT_DECIDE')),
  
  -- Product family / hierarchy
  product_family_id UUID REFERENCES canonical.product(product_id) ON DELETE RESTRICT,
  
  -- Temporal tracking
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by_decision UUID REFERENCES canonical.decision(decision_id),
  
  -- Lineage
  fold_source_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],  -- Which Fold subjects contributed
  
  -- Audit
  decision_horizon TIMESTAMPTZ NOT NULL,  -- When this Product was materialized
  kb_version TEXT NOT NULL,               -- KB version used
  
  -- Status
  materialization_status VARCHAR(20) NOT NULL
    CHECK (materialization_status IN ('MATERIALIZED', 'CANNOT_DECIDE', 'PENDING')),
  
  CONSTRAINT product_must_have_source_or_cannot_decide
    CHECK (array_length(fold_source_ids, 1) > 0 OR materialization_status = 'CANNOT_DECIDE')
);

CREATE INDEX idx_product_family ON canonical.product(product_family_id);
CREATE INDEX idx_product_status ON canonical.product(product_status);
CREATE INDEX idx_product_decision_horizon ON canonical.product(decision_horizon);
```

**Rationale:**
- `product_id`: Canonical identity (UUID, not derived from Fold)
- `product_code`: Business-visible identifier (from Fold or Decision)
- `product_status`: CANNOT_DECIDE option for incomplete identity cases
- `fold_source_ids`: Array of Fold subject_ids that contributed (lineage)
- `created_by_decision`: Links to Governed Decision (lineage)
- `materialization_status`: Explicit flag for incomplete identity cases

---

## 14. PROPOSED CONFIGURATION SCHEMA

**⚠️ PROVISIONAL (Depends on Product & identity rules)**

```sql
-- canonical/schema/002_configuration.sql
CREATE TABLE canonical.configuration (
  configuration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES canonical.product(product_id) ON DELETE CASCADE,
  
  -- Stable identity
  identity_key TEXT NOT NULL,  -- From KB IR-001..IR-009 + Fold properties
  fold_subject_id TEXT NOT NULL UNIQUE,  -- Link to Fold (CON-001, etc.)
  
  -- Sellable status
  configuration_status VARCHAR(20) NOT NULL
    CHECK (configuration_status IN ('SELLABLE', 'NONSELLABLE', 'CANNOT_DECIDE')),
  
  -- Identity completeness flag (UC-18)
  identity_completeness VARCHAR(20) NOT NULL DEFAULT 'INCOMPLETE'
    CHECK (identity_completeness IN ('COMPLETE', 'INCOMPLETE', 'CANNOT_DECIDE')),
  
  -- Temporal tracking
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by_decision UUID REFERENCES canonical.decision(decision_id),
  
  -- Lineage
  decision_horizon TIMESTAMPTZ NOT NULL,  -- When this Configuration was materialized
  fold_snapshot_id UUID NOT NULL,  -- Link to state.fold_state_snapshot
  kb_version TEXT NOT NULL,
  
  -- Audit
  materialization_status VARCHAR(20) NOT NULL
    CHECK (materialization_status IN ('MATERIALIZED', 'CANNOT_DECIDE', 'PENDING')),
  
  CONSTRAINT config_identity_must_be_complete_or_cannot_decide
    CHECK (identity_completeness IN ('COMPLETE', 'CANNOT_DECIDE'))
);

CREATE UNIQUE INDEX idx_config_identity ON canonical.configuration(product_id, identity_key);
CREATE INDEX idx_config_status ON canonical.configuration(configuration_status);
CREATE INDEX idx_config_fold_link ON canonical.configuration(fold_subject_id, fold_snapshot_id);
CREATE INDEX idx_config_decision_horizon ON canonical.configuration(decision_horizon);
```

**Rationale:**
- Deliberately THIN: configuration_id, product_id, identity_key, status only
- Mutable attributes belong in configuration_version (NOT here)
- identity_completeness flags UC-18 gaps
- fold_subject_id, fold_snapshot_id provide lineage
- created_by_decision links to governance

---

## 15. PROPOSED CONFIGURATION_VERSION SCHEMA

**⚠️ PROVISIONAL (Depends on Decisions layer)**

```sql
-- canonical/schema/003_configuration_version.sql
CREATE TABLE canonical.configuration_version (
  version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  configuration_id UUID NOT NULL REFERENCES canonical.configuration(configuration_id) ON DELETE CASCADE,
  
  -- Version numbering
  version_no INT NOT NULL,
  
  -- Temporal validity
  valid_from TIMESTAMPTZ NOT NULL,  -- When this version became effective
  valid_to TIMESTAMPTZ,              -- When this version was superseded (NULL = current)
  
  -- Mutable business state (examples only; expand per actual requirements)
  pricing_status TEXT,               -- ESTABLISHED, UNREPORTED, CONTRADICTED
  sku_activation_status TEXT,        -- ESTABLISHED, UNREPORTED, CONTRADICTED
  (other mutable attributes),
  
  -- Change metadata
  change_type VARCHAR(30) NOT NULL   -- From CHANGE_CLASSIFICATION decision
    CHECK (change_type IN ('BOOTSTRAP', 'MINOR_CHANGE', 'MAJOR_CHANGE', 'CANNOT_DECIDE')),
  
  identity_effect VARCHAR(20) NOT NULL  -- From IDENTITY_ASSESSMENT decision
    CHECK (identity_effect IN ('SAME_IDENTITY', 'NEW_IDENTITY', 'CANNOT_DECIDE')),
  
  -- Lineage
  created_by_decision UUID NOT NULL REFERENCES canonical.decision(decision_id),
  decision_horizon TIMESTAMPTZ NOT NULL,
  fold_snapshot_id UUID NOT NULL,
  
  -- Audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  kb_version TEXT NOT NULL,
  
  CONSTRAINT version_must_have_start_date
    CHECK (valid_from IS NOT NULL),
  
  CONSTRAINT version_temporal_consistency
    CHECK (valid_to IS NULL OR valid_to > valid_from),
  
  CONSTRAINT change_type_and_identity_must_be_known
    CHECK (change_type != 'CANNOT_DECIDE' AND identity_effect != 'CANNOT_DECIDE')
);

CREATE INDEX idx_version_config ON canonical.configuration_version(configuration_id);
CREATE INDEX idx_version_temporal ON canonical.configuration_version(configuration_id, valid_from, valid_to);
CREATE INDEX idx_version_decision_horizon ON canonical.configuration_version(decision_horizon);
```

**Rationale:**
- `version_no`: Sequential version counter
- `valid_from`: When this version became effective (= decision_horizon initially)
- `valid_to`: NULL until next version created
- `change_type`, `identity_effect`: Must come from Decisions (not CANNOT_DECIDE in production)
- `created_by_decision`: Every version traces to a Governance Decision
- Mutable attributes stored here, NOT on configuration
- BOOTSTRAP change_type for initial version materialization

---

## 16. PROPOSED LINEAGE MODEL

**Canonical Lineage Design:**

```
canonical.configuration_version
    ↓ created_by_decision
canonical.decision (table in decisions/ layer)
    ↓ based_on_fold_snapshots
state.fold_state_snapshot
    ↓ contains_assertions
runtime.assertion
    ↓ drawn_from_evidence
runtime.evidence
    ↓ extracted_from_raw
raw.raw_event
```

**Implementation Approach (Option A: Explicit Lineage Table):**

```sql
-- canonical/lineage/001_canonical_lineage_schema.sql
CREATE TABLE canonical.lineage (
  lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Canonical object being traced
  canonical_table_name VARCHAR(50) NOT NULL  -- 'product', 'configuration', 'configuration_version'
    CHECK (canonical_table_name IN ('product', 'configuration', 'configuration_version')),
  canonical_object_id UUID NOT NULL,
  
  -- Upstream ancestry (each row shows one hop)
  upstream_layer VARCHAR(30) NOT NULL  -- 'decision', 'fold', 'assertion', 'evidence', 'raw'
    CHECK (upstream_layer IN ('decision', 'fold', 'assertion', 'evidence', 'raw')),
  upstream_object_id UUID NOT NULL,
  upstream_table_name TEXT NOT NULL,  -- 'decision', 'fold_state_snapshot', 'assertion', 'evidence', 'raw_event'
  
  -- Lineage relationship
  relationship_type VARCHAR(30) NOT NULL  -- 'created_by', 'based_on', 'derived_from', 'contains', 'extracted_from'
    CHECK (relationship_type IN ('created_by', 'based_on', 'derived_from', 'contains', 'extracted_from')),
  
  -- Temporal
  traced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT lineage_must_have_objects
    CHECK (canonical_object_id IS NOT NULL AND upstream_object_id IS NOT NULL)
);

CREATE INDEX idx_lineage_canonical ON canonical.lineage(canonical_table_name, canonical_object_id);
CREATE INDEX idx_lineage_upstream ON canonical.lineage(upstream_layer, upstream_object_id);
CREATE INDEX idx_lineage_relationship ON canonical.lineage(relationship_type);
```

**Implementation Approach (Option B: Foreign Key Lineage):**

Keep lineage implicit via foreign keys in the schemas themselves:
- configuration_version.created_by_decision → decision
- decision.fold_snapshot_ids → fold_state_snapshot
- (Fold already links to Assertions)
- (Assertions already link to Evidence)
- (Evidence already links to Raw)

**Recommendation:** Use Option A (explicit lineage table) for:
- Auditability
- Query simplicity
- Historical tracking of lineage changes
- Compliance reporting

---

## 17. TEMPORAL SEMANTICS

**Define Clearly:**

| Term | Source | Meaning | Example |
|------|--------|---------|---------|
| **decision_horizon** | Fold/Decision | The timestamp at which this state was materialized | 2026-06-20 10:45:00+00 |
| **valid_from** | Configuration Version | When this version became effective | 2026-06-20 10:45:00+00 (initially = decision_horizon) |
| **valid_to** | Configuration Version | When this version was superseded | NULL (current), or timestamp of next version |
| **Assertion effective_at** | Assertion | When the asserted fact became effective | 2026-06-15 12:00:00+00 (might be in past) |
| **Assertion arrival_at** | Assertion | When the assertion was received by the system | 2026-06-20 09:30:00+00 (actual ingestion time) |
| **Canonical created_at** | System | When the Canonical object was materialized | CURRENT_TIMESTAMP |

**Temporal Consistency Rules:**

```
1. valid_from ≤ decision_horizon (version can't be valid from future)
2. decision_horizon ≤ CURRENT_TIMESTAMP (cut is never in future)
3. valid_to > valid_from (if valid_to is set)
4. Assertion effective_at ≤ decision_horizon (only past/present assertions in Fold)
5. Assertion arrival_at ≤ decision_horizon (only past/present arrivals in Fold)
6. Fold decision_horizon is FIXED for a materialization run (idempotent)
```

**Version Chronology Example:**

```
Configuration CON-001 created 2026-06-20 10:45:00+00

v1 (BOOTSTRAP):
  valid_from: 2026-06-20 10:45:00+00
  valid_to:   NULL (current)
  change_type: BOOTSTRAP
  created_by_decision: (BOOTSTRAP_CANONICAL decision)
  
(Time passes; data changes; Canonical re-runs at 2026-06-25 14:00:00+00)

v2 (MINOR_CHANGE):
  valid_from: 2026-06-25 14:00:00+00
  valid_to:   NULL (current)
  change_type: MINOR_CHANGE
  created_by_decision: (CHANGE_CLASSIFICATION decision #2)
  
(v1.valid_to is updated to 2026-06-25 14:00:00+00 retroactively)
```

---

## 18. MISSING / CONTRADICTED / CANNOT_DECIDE BEHAVIOR

**Design Decision Required:**

When materializing Canonical, what should happen if:
1. Identity inputs are UNREPORTED (fold_state = 'UNREPORTED')?
2. Identity inputs are CONTRADICTED (fold_state = 'CONTRADICTED')?
3. Governed identity decision = CANNOT_DECIDE?
4. Required properties for configuration identity are absent?

**Option A: Skip (Conservative)**
```
DO NOT materialize configuration/product.
Log diagnostic: "Cannot materialize CON-001: identity_status = CANNOT_DECIDE"
Canonical table remains empty for that object.
Decisions layer can later decide "CREATE_CONFIGURATION" with complete data.
```

**Option B: Materialize with Flag (Pragmatic)**
```
DO materialize but set materialization_status = 'CANNOT_DECIDE'
Set identity_completeness = 'INCOMPLETE'
Flag the configuration as "awaiting governance decision"
Can be queried but marked as provisional.
```

**Option C: Materialize as Reference (Optimistic)**
```
Materialize with identity_key = (best-effort derived key)
Set materialization_status = 'PENDING'
Await IDENTITY_ASSESSMENT decision to confirm/update identity_key.
Risky for duplicate prevention (UC-18).
```

**RECOMMENDATION: Option A + Option B Hybrid**

```sql
-- Option A (Skip) for Product and Configuration identity
IF product identity is CANNOT_DECIDE:
  DO NOT insert canonical.product
ELSE:
  Insert canonical.product with materialization_status = 'MATERIALIZED'

IF configuration identity is CANNOT_DECIDE:
  DO NOT insert canonical.configuration
ELSE IF identity_completeness = 'INCOMPLETE':
  Insert canonical.configuration with materialization_status = 'PENDING'
                                        identity_completeness = 'INCOMPLETE'
ELSE:
  Insert canonical.configuration with materialization_status = 'MATERIALIZED'
                                      identity_completeness = 'COMPLETE'

-- Option B (Flag) for Configuration Versions
IF change_type is CANNOT_DECIDE OR identity_effect is CANNOT_DECIDE:
  DO NOT insert canonical.configuration_version
  (Requires Governed Decisions to execute first)
ELSE:
  Insert canonical.configuration_version with change_type and identity_effect set
```

---

## 19. DEPENDENCY ON CHANGE_CLASSIFICATION

**Question:** Is Canonical blocked by CHANGE_CLASSIFICATION decision?

**Answer:** PARTIALLY YES

**Explanation:**

For Canonical to materialize configuration_version with proper change_type:
- change_type = BOOTSTRAP for initial version ✅ (no decision needed)
- change_type = MINOR_CHANGE, MAJOR_CHANGE, ... for subsequent versions ❌ (requires CHANGE_CLASSIFICATION)

**Can Canonical START without CHANGE_CLASSIFICATION?** YES
- Materialize Product
- Materialize Configuration
- Materialize initial configuration_version with change_type = 'BOOTSTRAP'

**Will Canonical COMPLETE without CHANGE_CLASSIFICATION?** NO
- Subsequent versions cannot be materialized
- Canonical layer will be in "awaiting decisions" state
- Decision layer must execute CHANGE_CLASSIFICATION before Canonical can evolve

**Recommended Dependency Model:**

```
Phase 5A-5E (Canonical Bootstrap):
  - Schema DDL
  - Product identity derivation
  - Configuration identity derivation
  - Initial version materialization (BOOTSTRAP only)
  - Lineage & temporal semantics
  
  Materialize to Canonical:
    ✅ Product (if identity derivable)
    ✅ Configuration (if identity derivable)
    ✅ Configuration Version v1 with change_type = 'BOOTSTRAP'
    
Phase 6+ (Decisions):
  - CHANGE_CLASSIFICATION decides next change type
  - IDENTITY_ASSESSMENT confirms identity effects
  - Downstream Canonical evolves versions

Blocker: CHANGE_CLASSIFICATION prevents version evolution past bootstrap.
         But does NOT prevent CANONICAL PHASE 5 completion.
```

---

## 20. DEPENDENCY ON IDENTITY_ASSESSMENT

**Question:** Is Canonical blocked by IDENTITY_ASSESSMENT decision?

**Answer:** PARTIALLY YES

**Explanation:**

For Canonical to establish stable Product and Configuration identity:
- If KB rules + Fold state contain sufficient identity information ✅ (derive directly)
- If identity is ambiguous or missing ❌ (requires IDENTITY_ASSESSMENT)

**Can Canonical START without IDENTITY_ASSESSMENT?** DEPENDS
- If KB rules IR-001..IR-009 fully specify identity derivation from Fold: YES
- If KB rules require inputs from Governed Decisions: NO

**Will Canonical COMPLETE without IDENTITY_ASSESSMENT?** MAYBE
- Product identity may be impossible without IDENTITY_ASSESSMENT
- Configuration identity may have gaps (UC-18) requiring IDENTITY_ASSESSMENT
- Canonical may materialize as INCOMPLETE/PENDING awaiting decision

**Recommended Dependency Model:**

```
Before Phase 5A execution:
  ✅ Read KB rules IR-001..IR-009 (read-only)
  ✅ Execute preflight Fold query to inventory all properties
  ✅ Cross-reference which properties are ESTABLISHED vs UNREPORTED
  ✅ Determine which identity inputs are available
  
If sufficient identity inputs in Fold:
  Canonical can materialize Product & Configuration with COMPLETE status
  
If identity inputs missing:
  Canonical can materialize with INCOMPLETE status, awaiting IDENTITY_ASSESSMENT
  
Blocker: IDENTITY_ASSESSMENT prevents final identity confirmation if needed.
         But does NOT prevent CANONICAL PHASE 5 design/partial materialization.
```

---

## 21. WHETHER CANONICAL CAN SAFELY MATERIALIZE NOW

**Question:** Can Product, Configuration, and Configuration Version be safely materialized from current Fold + KB BEFORE Governed CHANGE_CLASSIFICATION and IDENTITY_ASSESSMENT execute?

**Answer: CONDITIONAL YES**

### YES for:
1. ✅ **Configuration Versions (Bootstrap Only)**
   - Initial version with change_type = 'BOOTSTRAP' can materialize now
   - Does not require CHANGE_CLASSIFICATION decision
   - Establishes first version; subsequent versions wait for decisions

2. ✅ **Configuration Entity (Thin Definition)**
   - configuration_id, product_id, identity_key, status only
   - If KB rules IR-001..IR-009 + Fold provide identity: materialize
   - If identity incomplete: materialize with identity_completeness = 'INCOMPLETE'
   - Mutable attributes stay in version, not configuration

3. ✅ **Product Entity (Conditional)**
   - If Fold + KB define product identity rules: materialize
   - If product identity cannot be derived: set materialization_status = 'CANNOT_DECIDE'
   - Do NOT fabricate product identity

### NO for:
1. ❌ **Configuration Versions (Beyond Bootstrap)**
   - Subsequent versions require CHANGE_CLASSIFICATION (change_type)
   - Subsequent versions require IDENTITY_ASSESSMENT (identity_effect)
   - These must wait for Decisions layer

### REQUIREMENTS (Check Before Proceeding):

| Requirement | Status | Must Verify | Blocker If Missing |
|---|---|---|---|
| KB rules IR-001..IR-009 define sufficient identity derivation | ? | Inspect knowledge_base.rules | YES |
| Fold properties include all identity inputs (ESTABLISHED state) | ? | Execute preflight property query | PARTIAL |
| UC-18 gap documented and mitigated via identity_completeness flag | ⚠️ Acknowledged | Design includes flag | NO |
| UNREPORTED/CONTRADICTED behavior defined | ✅ Designed | Option A+B hybrid | NO |
| Lineage schema designed | ✅ Designed | Explicit lineage table | NO |
| Temporal semantics documented | ✅ Designed | Valid_from/to/created_at rules | NO |

### FINAL VERDICT:

```
✅ CANONICAL CAN SAFELY MATERIALIZE NOW (Partial)

Safe to materialize:
  - Configuration entity (with identity_completeness flag)
  - Product entity (with materialization_status flag)
  - Configuration Version v1 (with change_type = 'BOOTSTRAP')
  - Lineage tracking (upstream → Fold → Assertions → Evidence → Raw)

NOT safe to materialize:
  - Configuration Versions beyond v1 (requires CHANGE_CLASSIFICATION)
  - Final product/configuration identity (if KB rules incomplete)
  
Recommended approach:
  1. Implement Canonical schema & transforms
  2. Materialize v1 with change_type = 'BOOTSTRAP'
  3. Create explicit flag columns (identity_completeness, materialization_status)
  4. Leave v2+ ready but not populated until Decisions execute
  5. Parallel-track: Decisions layer executes CHANGE_CLASSIFICATION & IDENTITY_ASSESSMENT
  6. Once Decisions complete: Decisions → Canonical integration enables v2+ materialization
```

---

## 22. PROPOSED SEQUENTIAL CANONICAL IMPLEMENTATION PLAN

**If design is viable, here is the smallest sequential implementation:**

### **STEP 5B: CANONICAL SCHEMA & INFRASTRUCTURE**
**Owning Folder:** retail_os/canonical/schema/

| File | Outputs | Inputs | Tests |
|------|---------|--------|-------|
| 001_product.sql | canonical.product table | Canonical business model | test_schema.sql |
| 002_configuration.sql | canonical.configuration table | Canonical business model | test_schema.sql |
| 003_configuration_version.sql | canonical.configuration_version table | Canonical business model | test_schema.sql |
| 004_canonical_meta.sql | Metadata tables (KB version, decision lineage, etc.) | Canonical model | test_schema.sql |

**Deliverable:** DDL only. No data inserted. All tables empty but ready.

**Stop Condition:** All STEP 5B tables deployed and constraints pass syntax validation.

---

### **STEP 5C: CANONICAL LINEAGE INFRASTRUCTURE**
**Owning Folder:** retail_os/canonical/lineage/

| File | Outputs | Inputs | Tests |
|------|---------|--------|-------|
| 001_canonical_lineage_schema.sql | canonical.lineage table | Canonical schema | test_lineage.sql |
| 002_lineage_reference_views.sql | SQL views for lineage queries | Canonical schema + Raw/Fold/Assertion schema | (integrated into test_lineage.sql) |

**Deliverable:** Lineage infrastructure ready; no population yet.

**Stop Condition:** Lineage queries can trace canonical.configuration → Fold → Assertion → Evidence → Raw.

---

### **STEP 5D: PRODUCT & CONFIGURATION IDENTITY DERIVATION (Read-Only)**
**Owning Folder:** retail_os/canonical/transforms/

| File | Outputs | Inputs | Tests |
|------|---------|--------|-------|
| 001_product_derivation.sql | SQL function: derive_product_identity(...) | Fold, KB rules, Decision (optional) | test_product_identity.sql |
| 002_configuration_derivation.sql | SQL function: derive_configuration_identity(...) | Fold, KB rules, Decision (optional) | test_configuration_identity.sql |
| 003_version_state_derivation.sql | SQL function: derive_version_state(...) | Fold, previous version | test_version_materialization.sql |

**Deliverable:** Read-only derived views, not materialized yet.

**Stop Condition:** Derivation functions produce correct identity_key values and identity_completeness flags.

---

### **STEP 5E: CANONICAL MATERIALIZATION (BOOTSTRAP)**
**Owning Folder:** retail_os/canonical/transforms/

| File | Outputs | Inputs | Tests |
|------|---------|--------|-------|
| 999_canonical_materialization.sql | Main entry point: materialize_canonical_v1(...) | Derivation functions, Fold | test_materialization_order.sql, test_idempotency.sql |

**Deliverable:** Insert Product, Configuration, Version v1 with change_type = 'BOOTSTRAP'.

**Stop Condition:** 
- All 22 configurations materialized with identity_completeness flag
- All configurations have corresponding versions v1
- Lineage populated
- No upstream mutation (Fold/Assertion/Evidence/Raw unchanged)

---

### **STEP 5F: CANONICAL VALIDATION & AUDIT**
**Owning Folder:** retail_os/canonical/validation/

| File | Outputs | Inputs | Tests |
|------|---------|--------|-------|
| 001_canonical_constraints.sql | CHECK/UNIQUE/FK constraint verification | Canonical tables | test_schema.sql |
| 002_temporal_validation.sql | valid_from/valid_to/created_at correctness | Configuration Version | test_temporal_semantics.sql |
| 003_immutability_validation.sql | Verify Fold/Assertion/Evidence/Raw untouched | Canonical + Upstream | test_immutability.sql |

**Deliverable:** Validation queries prove Canonical is sound and upstream is untouched.

**Stop Condition:** All 3 validation queries return PASS.

---

### **STEP 5G: CANONICAL DOCUMENTATION**
**Owning Folder:** retail_os/canonical/

| File | Purpose |
|------|---------|
| README.md | Canonical module purpose, design decisions, temporal semantics, deployment sequence |
| models/canonical_data_model.md | Entity relationship diagram, semantics, constraints |

---

## 23. PLACEMENT RULES FOR EVERY PROPOSED FILE

**RULE: Every file created in Phase 5 must be traceable.**

| File Path | Purpose | Type | Phase | Module | Test File | Go/No-Go |
|---|---|---|---|---|---|---|
| canonical/README.md | Module documentation | .md | 5A | Canonical | (reference) | DESIGN |
| canonical/schema/001_product.sql | Product table DDL | .sql | 5B | Canonical | test_schema.sql | READY |
| canonical/schema/002_configuration.sql | Configuration table DDL | .sql | 5B | Canonical | test_schema.sql | READY |
| canonical/schema/003_configuration_version.sql | Version table DDL | .sql | 5B | Canonical | test_schema.sql | READY |
| canonical/schema/004_canonical_meta.sql | Metadata tables | .sql | 5B | Canonical | test_schema.sql | READY |
| canonical/transforms/001_product_derivation.sql | Product identity logic | .sql | 5D | Canonical | test_product_identity.sql | READY |
| canonical/transforms/002_configuration_derivation.sql | Config identity logic | .sql | 5D | Canonical | test_configuration_identity.sql | READY |
| canonical/transforms/003_version_state_derivation.sql | Version state logic | .sql | 5D | Canonical | test_version_materialization.sql | READY |
| canonical/transforms/999_canonical_materialization.sql | Main entry point | .sql | 5E | Canonical | test_materialization_order.sql | READY |
| canonical/lineage/001_canonical_lineage_schema.sql | Lineage table DDL | .sql | 5C | Canonical | test_lineage.sql | READY |
| canonical/lineage/002_lineage_population.sql | Lineage logic | .sql | 5D | Canonical | test_lineage.sql | READY |
| canonical/validation/001_canonical_constraints.sql | Constraint checks | .sql | 5F | Canonical | test_schema.sql | READY |
| canonical/validation/002_temporal_validation.sql | Temporal checks | .sql | 5F | Canonical | test_temporal_semantics.sql | READY |
| canonical/validation/003_immutability_validation.sql | Immutability checks | .sql | 5F | Canonical | test_immutability.sql | READY |
| canonical/models/canonical_data_model.md | Data model docs | .md | 5A | Canonical | (reference) | DESIGN |
| tests/canonical/test_schema.sql | DDL validation | .sql | 5B | Canonical | (paired) | READY |
| tests/canonical/test_product_identity.sql | Product derivation tests | .sql | 5D | Canonical | (paired) | READY |
| tests/canonical/test_configuration_identity.sql | Config derivation tests | .sql | 5D | Canonical | (paired) | READY |
| tests/canonical/test_version_materialization.sql | Version logic tests | .sql | 5E | Canonical | (paired) | READY |
| tests/canonical/test_lineage.sql | Lineage traceability tests | .sql | 5C | Canonical | (paired) | READY |
| tests/canonical/test_temporal_semantics.sql | Temporal correctness tests | .sql | 5F | Canonical | (paired) | READY |
| tests/canonical/test_idempotency.sql | Materialization idempotency | .sql | 5E | Canonical | (paired) | READY |
| tests/canonical/test_immutability.sql | Upstream immutability tests | .sql | 5F | Canonical | (paired) | READY |

**Enforcement Rules:**
1. ✅ Every .sql file must be in retail_os/canonical/ OR tests/canonical/
2. ✅ Every file must have matching test (where applicable)
3. ✅ No file may live in database/fold/, database/raw/, or other layers
4. ✅ No file may be named "FINAL", "CORRECTED", "NEW", "_v2" (use version control instead)
5. ✅ No .py implementation files until AFTER SQL DDL/logic complete
6. ✅ projection.py must move to retail_os/projection/ (when that phase starts)

---

## 24. BLOCKERS

**Design-Phase Blockers (Must Resolve Before STEP 5B):**

| Blocker | Impact | Resolution | Timeline |
|---------|--------|-----------|----------|
| KB rules IR-001..IR-009 not yet inspected | Cannot confirm identity derivation is possible | Execute preflight KB inspection query | Before 5B |
| Fold property inventory not completed | Cannot confirm identity inputs are ESTABLISHED | Execute preflight Fold property query | Before 5B |
| Product identity source unknown | Cannot derive product_id | Governed Decision required (or: Product = Configuration?) | Before 5D |
| UC-18 duplicate prevention gap acknowledged | Configuration identity incomplete | Design includes identity_completeness flag (workaround) | Before 5D |
| CHANGE_CLASSIFICATION not executed | Cannot materialize v2+ versions | Design accommodates: v1 = BOOTSTRAP only; v2+ await Decisions | Before 5E |
| IDENTITY_ASSESSMENT not executed | Cannot confirm configuration identity | Design accommodates: materialize with INCOMPLETE flag | Before 5E |

**Implementation-Phase Blockers (Will Arise in 5B-5G):**

| Phase | Blocker | Mitigation |
|-------|---------|-----------|
| 5B | PostgreSQL constraint conflicts | Review existing database schema; may require migration |
| 5B | Foreign key to decision table (doesn't exist yet) | Use deferrable constraints; Decisions layer creates table |
| 5D | Fold schema changes | Assume Fold is now frozen; if changes, requires re-run |
| 5E | Identity derivation returns CANNOT_DECIDE for >X% configs | Escalate to governance; adjust INCOMPLETE tolerance |
| 5F | Upstream tables modified during materialization | Implement transactional integrity checks |

**No Blocker Prevents STEP 5A Design Completion.**

---

## 25. RECOMMENDED NEXT SMALLEST STEP

**Immediate Next Action (After STEP 5A Approval):**

### **Execute Preflight Queries to Unblock Design Decisions**

Before STEP 5B, run these read-only queries:

1. **Fold Property Inventory**
   - Retrieve all 177 properties
   - Classify each as: A (Product identity), B (Config identity), C (Version state), D (Launch context), E (Projection-only), F (Unknown)
   - Check fold_state for each (ESTABLISHED vs UNREPORTED)

2. **KB Identity Rules Inspection**
   - Read IR-001..IR-009 definitions
   - List which Fold properties each rule requires
   - Identify which required properties are missing (UNREPORTED)

3. **Configuration Subjects Detailed View**
   - For each of 22 configurations, show:
     - All properties and their fold_state
     - Which satisfy KB identity requirements
     - Which have UNREPORTED/CONTRADICTED state

4. **Product Identity Assessment**
   - Determine whether Product identity exists in Fold
   - Or whether Product = Configuration (1:1 relationship)
   - Or whether Product identity requires Governance Decision

**After Preflight Completion:**
- Update STEP 5A design with actual Fold data
- Confirm whether design assumptions hold
- Clear remaining blockers
- Get approval to proceed to STEP 5B

---

## FINAL STATUS

### **CANONICAL DESIGN READY — GOVERNED DECISION DEPENDENCY IDENTIFIED**

**Reasoning:**

1. ✅ **Design is complete and safe** for Phase 5A
   - Modular structure defined
   - Schema proposals ready
   - Lineage model designed
   - Temporal semantics clarified
   - CANNOT_DECIDE behavior designed

2. ✅ **Bootstrap materialization possible now**
   - Product (if identity derivable from Fold + KB)
   - Configuration (with identity_completeness flag for incomplete cases)
   - Configuration Version v1 (with change_type = 'BOOTSTRAP')

3. ❌ **Subsequent evolution blocked by Decisions**
   - Configuration Version v2+ requires CHANGE_CLASSIFICATION
   - Final identity confirmation requires IDENTITY_ASSESSMENT
   - But STEP 5B-5E can materialize and prepare for these inputs

4. ⚠️ **Critical Preflight Data Needed**
   - Must inspect KB identity rules (IR-001..IR-009)
   - Must inventory actual Fold properties
   - Must confirm identity inputs are ESTABLISHED (not UNREPORTED)

---

## RECOMMENDATIONS

**DO (Before STEP 5B):**
- Execute preflight Fold property & KB rules inspection
- Confirm identity derivation rules from KB
- Audit existing canonical/configuration.py, etc. files (decide: keep as placeholder or remove)
- Create tests/canonical/ folder structure

**DO NOT (In STEP 5A):**
- Create any implementation files (wait for STEP 5B approval)
- Modify Fold, Raw, Evidence, Assertion, KB, or Policy layers
- Start Decisions, Actions, Projection, Workbench, or Agents layers
- Commit or push any changes

**DO NEXT (When Approved):**
- Proceed to STEP 5B: Canonical Schema & Infrastructure DDL
- Implement files per design in Section 23
- Deploy to database as-is (tables ready, data empty)

---

**STOP.**  
**DO NOT IMPLEMENT CANONICAL.**  
**DO NOT CREATE FILES.**  
**DO NOT CREATE TABLES.**  
**DO NOT START DECISIONS.**  

**Await approval and preflight data before STEP 5B execution.**

---

*STEP 5A Design Complete*  
*Date: 2026-09-07*  
*Authorization: STEP 5A Canonical State Design & Preflight*

