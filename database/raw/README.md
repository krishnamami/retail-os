# Raw Ingestion Layer - Retail OS

**Status**: READY FOR INGESTION  
**Goal**: Load 169 records from S3 into PostgreSQL raw.raw_event with idempotency verification

---

## Architecture

```
S3 (26 JSONL files, 169 records)
  ↓
Lambda (Python 3.9 + psycopg2-binary==2.9.9)
  ↓ (deterministic ID: FROZEN_<SHA256>)
raw.raw_event (UNIQUE constraint prevents duplicates)
  ↓
audit.ingestion_file + audit.ingestion_log (checkpoint tracking)
  ↓
Idempotency verified: Run 2 = 0 new records
```

---

## Key Numbers

| Item | Value |
|------|-------|
| S3 Bucket | accord-capital-loans-usw2-621646470377 |
| S3 Prefix | claris/source-corpus/raw/ |
| JSONL Files | 26 |
| Expected Records | 169 |
| PostgreSQL Host | database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com |
| Target Table | raw.raw_event |
| Lambda Runtime | Python 3.9, Amazon Linux 2 |

---

## Files in This Directory

### SQL (Verification & DDL)
- `sql/create_raw_event_table.sql` - Creates table structure
- `sql/verify_raw_preload.sql` - Pre-load baseline (0 records)
- `sql/verify_raw_postload.sql` - Post-load check (169 records)
- `sql/verify_idempotency.sql` - Idempotency check (no duplicates)

### Lambda (Function & Build)
- `lambda/lambda_function_improved.py` - Fixed version (psycopg2 resolved)
- `lambda/lambda_function.py` - Original (reference)
- `lambda/Dockerfile` - Build psycopg2 in Lambda environment
- `lambda/build_deployment_package.sh` - Creates deployment ZIP
- `lambda/README.md` - Detailed setup and troubleshooting

---

## Quick Start

### Step 1: Create Tables
```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/create_raw_event_table.sql
```

### Step 2: Build psycopg2
```bash
cd database/raw/lambda
bash build_deployment_package.sh
# Output: ../../dist/lambda_deployment.zip
```

### Step 3: Deploy Lambda
```bash
aws lambda update-function-code --function-name claris-raw-ingestion \
     --zip-file fileb://dist/lambda_deployment.zip --region us-west-2
```

### Step 4: Run Ingestion
```bash
# Pre-check
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/verify_raw_preload.sql

# Run 1: Load 169 records
aws lambda invoke --function-name claris-raw-ingestion \
     --payload '{"ingestion_version": "1.0"}' --region us-west-2 run1.json

# Post-load check
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/verify_raw_postload.sql
# Expected: raw.raw_event = 169

# Run 2: Test idempotency
aws lambda invoke --function-name claris-raw-ingestion \
     --payload '{"ingestion_version": "1.0"}' --region us-west-2 run2.json
# Expected: records_inserted = 0

# Idempotency check
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/verify_idempotency.sql
# Expected: No duplicates, 169 records unchanged
```

---

## Idempotency Guarantee

**Mechanism**: UNIQUE constraint on (source_system, source_record_id, ingestion_version)

**Run 1**:
- 26 JSONL files → 169 records
- Each record gets deterministic ID: FROZEN_<SHA256>
- All inserted successfully

**Run 2** (same files):
- 26 JSONL files → 169 records (same as Run 1)
- Each record gets same ID: FROZEN_<SHA256> (deterministic!)
- INSERT...ON CONFLICT DO NOTHING → 0 new records
- **Result**: Total still 169, no duplicates

---

## What Was Fixed

**Blocker**: `No module named 'psycopg2._psycopg'`
- **Cause**: Binary incompatibility between build env and Lambda runtime
- **Solution**: Docker build using exact Lambda base image
- **Status**: FIXED ✓

---

## Expected Results After Completion

| Metric | Expected |
|--------|----------|
| raw.raw_event rows (Run 1) | 169 |
| raw.raw_event rows (Run 2) | 169 (unchanged) |
| New records on Run 2 | 0 |
| Duplicates found | 0 |
| Downstream tables (evidence, assertion, fold) | 0 each |

---

## Key Constraints

✓ No Lambda redesign (only psycopg2 fix)  
✓ No PostgreSQL DDL (schema already deployed)  
✓ No S3 modifications (corpus frozen)  
✓ No downstream implementation (placeholders only)  
✓ Deterministic IDs preserved  
✓ UNIQUE constraints enforced  

---

## References

- **Main Guide**: `INGESTION_EXECUTION_PLAN.md`
- **Lambda Setup**: `lambda/README.md`
- **SQL Scripts**: `sql/`
- **Docker Build**: `lambda/Dockerfile`
- **Build Script**: `lambda/build_deployment_package.sh`

---

**Status**: READY FOR EXECUTION  
**Timeline**: 15-30 minutes  
**Next Step**: Run build_deployment_package.sh
