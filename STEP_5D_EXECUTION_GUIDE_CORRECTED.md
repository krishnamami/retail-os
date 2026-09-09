# STEP 5D — Raw Corpus Extension Implementation (CORRECTED)

**Status**: ✅ STEP A Complete (8 records validated)  
**Database**: accord (verified live environment)  
**Credentials**: AWS Secrets Manager (retail_os/rds/postgres)  

---

## Prerequisites

### AWS Credentials
AWS credentials must be configured before running:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-west-2
```

### Environment Variables for Loader
The existing loader uses:
```bash
export POSTGRES_SECRET_NAME=retail_os/rds/postgres    # AWS Secrets Manager secret name
export POSTGRES_DB_NAME=accord                        # Verified live database
```

### Python Packages
```bash
pip install boto3 asyncpg
```

---

## STEP 5D.2: Upload to S3

### Dry Run (Recommended First)
```bash
cd database/raw/local_loader
python upload_prototype_raw.py --dry-run
```

**Expected Output**: Validation pass, collision check pass, no actual uploads

### Actual Upload
```bash
python upload_prototype_raw.py
```

**Expected Results**:
- 2 new S3 objects created
- 8 records total uploaded (1 PRODUCT_DEFINED + 7 CONFIGURATION_REQUESTED)
- Target keys:
  - `s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=product_definition/arrival_date=2026-01-16/part-00001.jsonl`
  - `s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/source=configuration_governance/arrival_date=2026-02-01/part-00001.jsonl`

---

## STEP 5D.3: Database Ingestion (Run 1)

```bash
cd ../../..  # Back to retail_os root
python database/raw/local_loader/ingest_s3_to_postgres.py --run-number 1
```

**Expected Output**:
```
Initial count:  169
Final count:    177
Net inserts:    8
Inserted:       8
Skipped:        0
Errors:         0
✓ PASS
```

**Database**: Uses AWS Secrets Manager to retrieve `accord` database credentials

---

## STEP 5D.4: Idempotency Verification (Run 2)

```bash
python database/raw/local_loader/ingest_s3_to_postgres.py --run-number 2
```

**Expected Output**:
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

## Post-Ingestion Validation

### Option 1: Use Existing Verify Script (Recommended)
```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d accord \
     -f database/raw/sql/verify_raw_postload.sql
```

Or with AWS Secrets Manager:
```bash
# Retrieve credentials from Secrets Manager
CREDS=$(aws secretsmanager get-secret-value --secret-id retail_os/rds/postgres --query SecretString --output text)
export PGUSER=$(echo $CREDS | jq -r '.username')
export PGPASSWORD=$(echo $CREDS | jq -r '.password')
export PGHOST=$(echo $CREDS | jq -r '.host')
export PGPORT=$(echo $CREDS | jq -r '.port')
export PGDATABASE=accord

psql -f database/raw/sql/verify_raw_postload.sql
```

### Option 2: Use Python Validation
Create a small Python script that uses the same AWS Secrets Manager pattern as the loader to verify record counts and idempotency.

---

## Success Criteria

✅ **STEP 5D Complete When**:
- Run 1: 8 inserts, count = 177
- Run 2: 0 inserts, count = 177
- Database: accord
- Baseline: 169 records unchanged
- No downstream layers touched

---

## Files in This Implementation

### Created:
- `database/raw/local_loader/upload_prototype_raw.py` — S3 upload script

### Used (Not Modified):
- `tests/raw/fixtures/product_defined.jsonl` — PRODUCT_DEFINED fixture
- `tests/raw/fixtures/configuration_requested.jsonl` — CONFIGURATION_REQUESTED fixtures
- `database/raw/local_loader/ingest_s3_to_postgres.py` — Ingestion with AWS Secrets Manager
- `database/raw/sql/verify_raw_postload.sql` — Existing post-ingestion verification

### NOT Used:
- No cloud workspace files
- No new validation SQL files (use existing verify_*.sql)
- No hardcoded database names or credentials

---

## Troubleshooting

**S3 Upload Fails: "Unable to locate credentials"**
- Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are exported
- Check AWS region is us-west-2

**Ingestion Fails: "Unable to locate credentials"**
- Verify AWS Secrets Manager secret exists: `aws secretsmanager describe-secret --secret-id retail_os/rds/postgres`
- Check secret contains: host, port, username, password, dbname

**Database Connection Refused**
- Verify RDS endpoint: database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com
- Verify database name is `accord` (not claris_knowledge)
- Verify security group allows connection on port 5432

---

## Final Status After Completion

```
STEP 5D RAW CORPUS EXTENSION COMPLETE — IDEMPOTENCY VERIFIED

Results:
  Baseline count before: 169
  Records added: 8
  Count after Run 1: 177
  Count after Run 2: 177
  Idempotency: VERIFIED
  Database: accord
  Downstream: NOT TOUCHED
```

