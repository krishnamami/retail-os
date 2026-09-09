# STEP 5D — Raw Corpus Extension Implementation (AUTHORIZED)

**Status**: ✅ STEP A Complete (8 records validated)  
**Next**: Execute STEPS 5D.2–5D.4 (S3 upload + database ingestion)

---

## Prerequisites

### AWS Credentials
AWS credentials must be configured before running. Options:
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- File: `~/.aws/credentials` (standard AWS CLI format)
- IAM role (if running on EC2)

**Example ~/.aws/credentials:**
```
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
```

### Python Packages
```bash
pip install boto3 asyncpg
```

### PostgreSQL Access
Database credentials are retrieved via AWS Secrets Manager by the ingestion loader.

---

## STEP 5D.2: Upload to S3

### Dry Run (Recommended First)
```bash
cd database/raw/local_loader
python upload_prototype_raw.py --dry-run
```

**Expected Output:**
```
[DRY RUN MODE]

Step 1: Validating fixture files...
✓ product_definition: 1 records
✓ configuration_governance: 7 records
✓ Total: 8 records

Step 2: Checking for S3 collisions...
✓ product_definition: No collision
✓ configuration_governance: No collision

Step 3: Uploading files...
Uploading: tests/raw/fixtures/product_defined.jsonl
  Target: s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=product_definition/arrival_date=2026-01-16/part-00001.jsonl
  [DRY RUN] Would upload

Uploading: tests/raw/fixtures/configuration_requested.jsonl
  Target: s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=configuration_governance/arrival_date=2026-02-01/part-00001.jsonl
  [DRY RUN] Would upload

================================================================================
STEP 5D.2 COMPLETE
================================================================================

Upload Summary:
  Records uploaded: 8
  Files uploaded: 2
```

### Actual Upload
```bash
python upload_prototype_raw.py
```

**Verify in S3:**
```bash
aws s3 ls s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/ --recursive
```

---

## STEP 5D.3: Database Ingestion (Run 1)

### Run 1 — Load 8 Records
```bash
cd ../../..  # Back to retail_os root
python database/raw/local_loader/ingest_s3_to_postgres.py --run-number 1
```

**Expected Output:**
```
Initial count:  169
Final count:    177
Net inserts:    8
Inserted:       8
Skipped:        0
Errors:         0
✓ PASS
```

**Database verification:**
```bash
psql -d claris_knowledge -U claris_user -c "SELECT COUNT(*) FROM raw.raw_event"
# Expected: 177
```

---

## STEP 5D.4: Idempotency Verification (Run 2)

### Run 2 — Verify No Duplicates
```bash
python database/raw/local_loader/ingest_s3_to_postgres.py --run-number 2
```

**Expected Output:**
```
Initial count:  177
Final count:    177
Net inserts:    0
Inserted:       0
Skipped:        8
Errors:         0
✓ PASS - Idempotency verified!
```

---

## Post-Ingestion Validation Queries

After Run 2, execute validation queries in `database/raw/sql/POST_INGESTION_VALIDATION_QUERIES.sql`:

```bash
psql -d claris_knowledge -U claris_user -f database/raw/sql/POST_INGESTION_VALIDATION_QUERIES.sql
```

**Expected Results:**
1. ✓ Total count = 177
2. ✓ PRODUCT_DEFINED = 1, CONFIGURATION_REQUESTED = 7
3. ✓ All 8 records: simulator_classification = PROTOTYPE_ASSUMPTION
4. ✓ All 8 records: configuration_id = NULL
5. ✓ Baseline preservation: 169 unchanged
6. ✓ No duplicate keys
7. ✓ S6 business duplicate pair present (2 distinct records, identical config)
8. ✓ S7 incomplete identity (segment = NULL)

---

## Troubleshooting

### S3 Upload Fails: "Unable to locate credentials"
- Configure AWS credentials (see Prerequisites)
- Or use: `export AWS_ACCESS_KEY_ID=...` and `export AWS_SECRET_ACCESS_KEY=...`

### S3 Collision: "S3 key already exists"
- Check if previous attempt left partial uploads
- Modify `upload_prototype_raw.py` to use next available part number
- Or contact admin to clean S3 prefix

### PostgreSQL Connection Refused
- Verify PostgreSQL running: `psql -U postgres -c "SELECT 1"`
- Check AWS Secrets Manager has valid credentials

### Run 1 Inserts = 0
- Verify S3 files were uploaded
- Check file contents: `aws s3 cp s3://...part-00001.jsonl - | head -1 | jq .`
- Check for existing records: `SELECT COUNT(*) FROM raw.raw_event WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'`

---

## Success Criteria

✅ **STEP 5D Complete When:**
- Run 1: 8 inserts, count becomes 177
- Run 2: 0 inserts, count stays 177
- All validation queries PASS
- No downstream layers modified
- Repository audit shows only STEP 5D changes

---

## Files Modified/Created

### Created:
- `database/raw/local_loader/upload_prototype_raw.py`

### Used (Not Modified):
- `tests/raw/fixtures/product_defined.jsonl`
- `tests/raw/fixtures/configuration_requested.jsonl`
- `database/raw/local_loader/ingest_s3_to_postgres.py`
- `database/raw/sql/POST_INGESTION_VALIDATION_QUERIES.sql` (or create if needed)

---

## Final Status

After all 4 steps complete successfully:

```
STEP 5D RAW CORPUS EXTENSION COMPLETE — IDEMPOTENCY VERIFIED
```

**Do NOT proceed to downstream layers** (Evidence, Fold, CHANGE_CLASSIFICATION, IDENTITY_ASSESSMENT, etc.)

