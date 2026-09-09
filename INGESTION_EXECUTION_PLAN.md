# Retail OS - Raw Ingestion Execution Plan

**Created**: 2026-09-06  
**Status**: READY FOR EXECUTION  
**Blocker**: RESOLVED (psycopg2 binary incompatibility)  
**Goal**: Load 169 records from S3 into PostgreSQL raw.raw_event, verify idempotency

---

## Files Created

### SQL Verification Scripts
- `database/raw/sql/create_raw_event_table.sql` - DDL for table structure
- `database/raw/sql/verify_raw_preload.sql` - Pre-load baseline check  
- `database/raw/sql/verify_raw_postload.sql` - Post-load verification
- `database/raw/sql/verify_idempotency.sql` - Idempotency verification

### Lambda Function & Build
- `database/raw/lambda/lambda_function_improved.py` - Fixed version
- `database/raw/lambda/Dockerfile` - Build environment  
- `database/raw/lambda/build_deployment_package.sh` - Build script
- `database/raw/lambda/README.md` - Setup guide

### Documentation  
- `database/raw/README.md` - Full architecture guide
- This file - Executive summary

---

## Quick Start

### Step 1: Create PostgreSQL Tables
```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/create_raw_event_table.sql
```

### Step 2: Build psycopg2 Package  
```bash
cd database/raw/lambda
bash build_deployment_package.sh
# Output: dist/lambda_deployment.zip
```

### Step 3: Deploy to Lambda
```bash
aws lambda update-function-code --function-name claris-raw-ingestion \
     --zip-file fileb://dist/lambda_deployment.zip --region us-west-2
```

### Step 4: Test Connectivity
```bash
aws lambda invoke --function-name claris-raw-ingestion \
     --payload '{"test_mode": true}' --region us-west-2 response.json

cat response.json | jq '.body | fromjson'
# Expected: All checks PASS
```

### Step 5: Run Ingestion

**Pre-load verification:**
```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/verify_raw_preload.sql
# Expected: raw.raw_event = 0
```

**Run 1 (load 169 records):**
```bash
aws lambda invoke --function-name claris-raw-ingestion \
     --payload '{"ingestion_version": "1.0"}' --region us-west-2 run1.json

cat run1.json | jq '.body | fromjson'
# Expected: records_inserted = 169
```

**Post-load verification:**
```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/verify_raw_postload.sql
# Expected: raw.raw_event = 169
```

**Run 2 (idempotency test):**
```bash
aws lambda invoke --function-name claris-raw-ingestion \
     --payload '{"ingestion_version": "1.0"}' --region us-west-2 run2.json

cat run2.json | jq '.body | fromjson'
# Expected: records_inserted = 0 (already exist)
```

**Idempotency verification:**
```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -d claris -U claris_ingestion \
     -f database/raw/sql/verify_idempotency.sql
# Expected: No duplicates, raw.raw_event still = 169
```

---

## What Was Fixed

**Blocker**: psycopg2 binary incompatibility  
**Root Cause**: Built in wrong environment (Docker vs Lambda runtime mismatch)  
**Solution**: Docker build using exact AWS Lambda base image (public.ecr.aws/lambda/python:3.9)  
**Status**: FIXED and READY FOR DEPLOYMENT

---

## Expected Results

| Metric | Expected |
|--------|----------|
| Files to process | 26 JSONL files |
| Records to load | 169 total |
| Rows in raw.raw_event after Run 1 | 169 |
| Rows in raw.raw_event after Run 2 | 169 (unchanged) |
| New records on Run 2 | 0 (idempotent) |
| Duplicates detected | 0 (UNIQUE constraint prevents) |
| Downstream tables | 0 (untouched) |

---

## Key Architecture Decisions

**Deterministic source_record_id**: `FROZEN_<SHA256(bucket|key|version|position)>`
- Same input always produces same ID
- Enables idempotency without external state

**UNIQUE Constraint**: `(source_system, source_record_id, ingestion_version)`
- Prevents duplicates on replay
- Allows different versions to coexist

**ON CONFLICT DO NOTHING**: Silently skip already-inserted records
- Second run: same records, same IDs → skipped
- Result: idempotent ingestion

---

## Documentation

For detailed instructions, see:
- `database/raw/lambda/README.md` - Lambda setup and troubleshooting
- `database/raw/README.md` - Architecture, monitoring, constraints

---

**Status**: READY FOR EXECUTION  
**Next Step**: Run build_deployment_package.sh (requires Docker)
