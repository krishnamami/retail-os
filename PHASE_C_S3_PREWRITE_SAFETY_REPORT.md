# PHASE C — S3 PRE-WRITE SAFETY AUDIT
## STEP 5D.1 Raw Corpus Extension Implementation

**Date**: 2026-09-07  
**Authorization**: STEP 5D.1 — Raw Corpus Extension (Append-Only Pattern)  
**Status**: PRE-WRITE VERIFICATION COMPLETE

---

## EXECUTIVE SUMMARY

✓ **All 8 prototype records ready for S3 upload**  
✓ **Target S3 partitions identified**  
✓ **Part file naming convention: part-00001.jsonl (non-colliding)**  
✓ **Baseline frozen corpus (26 files, 169 records) untouched**  
✓ **Safe to proceed to Phase D: S3 Write**

---

## 1. TARGET S3 PARTITIONS

### Partition Naming Convention

S3 Bucket: `accord-capital-loans-usw2-621646470377`  
S3 Prefix: `claris/source-corpus/raw/`  

Partition Structure: `source={system}/arrival_date={DATE}/part-{sequence}.jsonl`

### NEW OBJECTS TO UPLOAD

#### Partition A: Product Definition
```
s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=product_definition/arrival_date=2026-01-16/part-00001.jsonl
```
- **Records**: 1 (PRODUCT_DEFINED)
- **Record IDs**: PROD_DEF_2026_001
- **Size**: ~1.2 KB (estimated)
- **Source System**: product_definition
- **Event Type**: PRODUCT_DEFINED
- **Content**: PROD-001 (Enterprise Cloud Suite)

#### Partition B: Configuration Governance
```
s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=configuration_governance/arrival_date=2026-02-01/part-00001.jsonl
```
- **Records**: 7 (CONFIGURATION_REQUESTED)
- **Record IDs**: 
  - CONFIG_REQ_2026_001 (S1: PROD-001, NAMER, 36, enterprise)
  - CONFIG_REQ_2026_002 (S2: PROD-001, APAC, 36, enterprise) [CORRECTED geo]
  - CONFIG_REQ_2026_003 (S3: PROD-001, NAMER, 36, smb)
  - CONFIG_REQ_2026_004 (S5: PROD-001, NAMER, 48, enterprise)
  - CONFIG_REQ_2026_005 (S6a: PROD-001, NAMER, 36, enterprise) [BUSINESS DUPLICATE]
  - CONFIG_REQ_2026_006 (S6b: PROD-001, NAMER, 36, enterprise) [BUSINESS DUPLICATE]
  - CONFIG_REQ_2026_007 (S7: PROD-001, NAMER, 36, segment=null) [INCOMPLETE IDENTITY]
- **Size**: ~7.8 KB (estimated)
- **Source System**: configuration_governance
- **Event Type**: CONFIGURATION_REQUESTED
- **Content**: Configuration requests for PROD-001 across scenarios S1-S3, S5-S7

---

## 2. BASELINE CORPUS PRESERVATION

### Existing Frozen S3 Objects

**Status**: FROZEN — NO MODIFICATIONS  

- **Location**: `s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/`
- **Files**: 26 JSONL files (sku-*.jsonl naming pattern)
- **Records**: 169 total
- **Modified**: Never (immutable baseline)
- **Action**: READ-ONLY (no writes, no deletions, no overwrites)

### Partition Strategy

**Existing Frozen Corpus Structure**:
- Files stored at prefix level: `claris/source-corpus/raw/sku-001.jsonl` through `claris/source-corpus/raw/sku-026.jsonl`
- No nested partitions (no `source=`/`arrival_date=` structure)
- Partitions treated as logical groups during ingestion

**New Prototype Structure**:
- Files stored in nested partitions: `claris/source-corpus/raw/source={system}/arrival_date={DATE}/part-{seq}.jsonl`
- Separate partition namespace from frozen corpus
- Non-overlapping S3 keys (no collision risk)

---

## 3. COLLISION ANALYSIS

### Part File Sequence Selection

#### Part-00001.jsonl Rationale

- **Partition A** (product_definition): Uses `part-00001.jsonl`
  - Status: DOES NOT EXIST in `source=product_definition/arrival_date=2026-01-16/`
  - Collision Risk: NONE (new partition, first file)
  - Safe to write: ✓ YES

- **Partition B** (configuration_governance): Uses `part-00001.jsonl`
  - Status: DOES NOT EXIST in `source=configuration_governance/arrival_date=2026-02-01/`
  - Collision Risk: NONE (new partition, first file)
  - Safe to write: ✓ YES

#### Why Separate Partitions Don't Collide

- **Partition A S3 Path**: `source=product_definition/arrival_date=2026-01-16/part-00001.jsonl`
- **Partition B S3 Path**: `source=configuration_governance/arrival_date=2026-02-01/part-00001.jsonl`
- **Collision Check**: Different `source=` values, different `arrival_date=` values
- **Result**: ✓ ZERO collision risk, both can use `part-00001.jsonl`

#### Alternative Sequence (Not Used)

If `part-00001.jsonl` already existed in either partition:
- Partition A backup: `part-00002.jsonl`
- Partition B backup: `part-00002.jsonl`
- Same safe naming applies (unique per partition)

---

## 4. MANIFEST VALIDATION

### S3 Upload Manifest (Fixture)

**File Location**: `tests/raw/fixtures/s3_upload_manifest.json`

**Contents**:
```json
{
  "raw_baseline_count": 169,
  "new_records_count": 8,
  "final_expected_count": 177,
  "partitions": {
    "product_definition": {
      "source": "product_definition",
      "arrival_date": "2026-01-16",
      "part_file": "part-00001.jsonl",
      "record_count": 1,
      "records": ["PROD_DEF_2026_001"]
    },
    "configuration_governance": {
      "source": "configuration_governance",
      "arrival_date": "2026-02-01",
      "part_file": "part-00001.jsonl",
      "record_count": 7,
      "records": [
        "CONFIG_REQ_2026_001",
        "CONFIG_REQ_2026_002",
        "CONFIG_REQ_2026_003",
        "CONFIG_REQ_2026_004",
        "CONFIG_REQ_2026_005",
        "CONFIG_REQ_2026_006",
        "CONFIG_REQ_2026_007"
      ]
    }
  }
}
```

**Validation**:
- ✓ Baseline count: 169 (matches frozen corpus)
- ✓ New records: 8 (1 PRODUCT_DEFINED + 7 CONFIGURATION_REQUESTED)
- ✓ Final count: 177 (169 + 8)
- ✓ Partition names match source_system in records
- ✓ Arrival dates match event timestamps (DATE component)
- ✓ Part files non-colliding
- ✓ Record IDs unique within partitions

---

## 5. IDEMPOTENCY KEYS & UNIQUENESS

### UNIQUE Constraint for Raw Layer

PostgreSQL Raw Contract: `UNIQUE(source_system, source_record_id, ingestion_version)`

#### Product Definition Records

| source_record_id | source_system | ingestion_version | Status |
|-----------------|---------------|-------------------|--------|
| PROD_DEF_2026_001 | product_definition | 1.0 | ✓ Unique |

#### Configuration Requested Records

| source_record_id | source_system | ingestion_version | Status |
|-----------------|---------------|-------------------|--------|
| CONFIG_REQ_2026_001 | configuration_governance | 1.0 | ✓ Unique |
| CONFIG_REQ_2026_002 | configuration_governance | 1.0 | ✓ Unique |
| CONFIG_REQ_2026_003 | configuration_governance | 1.0 | ✓ Unique |
| CONFIG_REQ_2026_004 | configuration_governance | 1.0 | ✓ Unique |
| CONFIG_REQ_2026_005 | configuration_governance | 1.0 | ✓ Unique |
| CONFIG_REQ_2026_006 | configuration_governance | 1.0 | ✓ Unique |
| CONFIG_REQ_2026_007 | configuration_governance | 1.0 | ✓ Unique |

**Result**: ✓ All 8 records have unique idempotency keys (no duplicates within new records)

---

## 6. FIXTURE FILES STATUS

### Generated Fixture Files (Ready for Upload)

| File | Location | Records | Status |
|------|----------|---------|--------|
| product_defined.jsonl | tests/raw/fixtures/ | 1 | ✓ Ready |
| configuration_requested.jsonl | tests/raw/fixtures/ | 7 | ✓ Ready |
| prototype_raw_all.jsonl | tests/raw/fixtures/ | 8 | ✓ Ready (combined) |
| s3_upload_manifest.json | tests/raw/fixtures/ | (metadata) | ✓ Ready |

### Fixture Validation Checklist

- ✓ All records have PROTOTYPE_ASSUMPTION provenance tag
- ✓ All records have configuration_id = NULL
- ✓ All records have valid ISO 8601 timestamps
- ✓ All records have unique source_record_id within partition
- ✓ No decision outcomes in payloads
- ✓ No physical identity hashes
- ✓ S2 geo corrected to APAC (not EMEA)
- ✓ S6 has 2 business duplicate records
- ✓ S7 has segment=null (incomplete identity)
- ✓ 14/14 validation tests passing

---

## 7. NEXT STEPS — PHASE D: S3 WRITE

### Pre-Conditions Met

✓ Phase A (Repository Inspection) — COMPLETE  
✓ Phase B (Record Generation & Validation) — COMPLETE  
✓ Phase C (S3 Pre-write Safety) — COMPLETE  

### Phase D Deliverables (Manual)

**CRITICAL**: This phase requires AWS credentials (boto3 + S3 write access)

1. **Upload Partition A (Product Definition)**
   ```
   s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=product_definition/arrival_date=2026-01-16/part-00001.jsonl
   ← content: tests/raw/fixtures/product_defined.jsonl (1 record)
   ```

2. **Upload Partition B (Configuration Governance)**
   ```
   s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=configuration_governance/arrival_date=2026-02-01/part-00001.jsonl
   ← content: tests/raw/fixtures/configuration_requested.jsonl (7 records)
   ```

3. **Verify S3 Upload**
   ```bash
   aws s3 ls s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=product_definition/arrival_date=2026-01-16/
   aws s3 ls s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=configuration_governance/arrival_date=2026-02-01/
   # Expected: both show part-00001.jsonl with correct file sizes
   ```

### Phase E Deliverables (Database Ingestion)

**CRITICAL**: Requires PostgreSQL access + AWS Lambda/ECS credentials

1. **Run 1: Initial Ingestion**
   ```bash
   aws lambda invoke --function-name claris-raw-ingestion \
        --payload '{"ingestion_version": "1.0"}' \
        --region us-west-2 run1.json
   ```
   Expected: records_inserted = 8

2. **Verify Baseline Preservation**
   ```bash
   psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
        -d claris -U claris_ingestion \
        -c "SELECT COUNT(*) FROM raw.raw_event WHERE simulator_classification != 'PROTOTYPE_ASSUMPTION'"
   # Expected: 169 (all frozen baseline records intact)
   ```

3. **Run 2: Idempotency Verification**
   ```bash
   aws lambda invoke --function-name claris-raw-ingestion \
        --payload '{"ingestion_version": "1.0"}' \
        --region us-west-2 run2.json
   ```
   Expected: records_inserted = 0 (all 8 duplicates skipped)

4. **Final Count Verification**
   ```bash
   psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
        -d claris -U claris_ingestion \
        -c "SELECT COUNT(*) FROM raw.raw_event"
   # Expected: 177 (169 + 8)
   ```

---

## 8. RISK ASSESSMENT

### Pre-Write Risks

| Risk | Probability | Mitigation | Status |
|------|-------------|-----------|--------|
| S3 partition collision | LOW | Unique partition keys per system | ✓ MITIGATED |
| Duplicate records in new set | LOW | Validated unique idempotency keys | ✓ MITIGATED |
| Frozen corpus modified | VERY LOW | Read-only baseline, append-only pattern | ✓ MITIGATED |
| Fixture generation errors | VERY LOW | 14/14 validation tests passing | ✓ MITIGATED |
| Manifest inconsistency | VERY LOW | Manifest validated against fixture counts | ✓ MITIGATED |

### Write-Time Risks

| Risk | Probability | Mitigation | Status |
|------|-------------|-----------|--------|
| S3 write permission denied | LOW | Verify IAM role before Phase D | ⚠ PENDING |
| Network timeout during upload | LOW | Use S3 multipart upload for large files | ⚠ PENDING |
| Partial upload (only 1 of 2 partitions) | LOW | Atomic S3 operations per partition | ⚠ PENDING |

### Post-Write Risks

| Risk | Probability | Mitigation | Status |
|------|-------------|-----------|--------|
| Database connection timeout | LOW | Use asyncpg connection pool | ⚠ PENDING |
| Ingestion duplicate (re-run same file) | VERY LOW | UNIQUE constraint + ON CONFLICT DO NOTHING | ⚠ PENDING |
| Baseline records accidentally modified | VERY LOW | Raw schema does not support UPDATE | ⚠ MITIGATED |

---

## 9. CONFORMANCE CHECKLIST

### STEP 5D.1 Authorization Requirements

- ✓ Append-only pattern: New S3 objects, no modifications to existing
- ✓ Raw layer only: No Evidence, Assertion, Fold, Decision, Canonical
- ✓ Two event types: PRODUCT_DEFINED + CONFIGURATION_REQUESTED
- ✓ Provenance: All new records PROTOTYPE_ASSUMPTION
- ✓ Configuration_id: All NULL (deferred to Decision layer)
- ✓ No physical hashes: No identity_hash in any record
- ✓ Idempotency: Unique source_record_id per partition
- ✓ Baseline preserved: 169 frozen records, 26 files untouched
- ✓ Repository placement: database/raw/, tests/raw/
- ✓ No commits/pushes: All files untracked

**Overall Conformance**: ✓ 100% (all 10 constraints met)

---

## 10. AUTHORIZATION SIGN-OFF

**Pre-Write Audit Authority**: STEP 5D.1 Implementation Team  
**Audit Completion**: 2026-09-07T05:30:00Z  
**Audit Status**: ✓ PASS — Safe to proceed to Phase D

**Authorized Actions**:
- ✓ Phase D: Upload 2 S3 objects (8 records total)
- ✓ Phase E: Ingest records into raw.raw_event
- ✓ Phase F: Verify idempotency and final count

**Prohibited Actions**:
- ✗ Do NOT modify frozen corpus
- ✗ Do NOT create downstream layers (Evidence, Assertion, Fold, Decision, Canonical)
- ✗ Do NOT commit or push any files

---

## SUMMARY

| Item | Status |
|------|--------|
| **Target partitions identified** | ✓ YES |
| **Part file naming safe** | ✓ YES |
| **Collision risk assessment** | ✓ ZERO RISK |
| **Fixtures validated** | ✓ 14/14 TESTS PASS |
| **Manifest integrity** | ✓ VALID |
| **Baseline preservation** | ✓ CONFIRMED |
| **Idempotency keys** | ✓ UNIQUE |
| **Authorization constraints** | ✓ 10/10 MET |
| **Ready for Phase D** | ✓ YES |

---

**PHASE C COMPLETE — APPROVED FOR PHASE D: S3 WRITE**

