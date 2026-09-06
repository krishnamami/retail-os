# Raw Ingestion Lambda Function (Prototype)

**Status**: PROTOTYPE / TEST LOADER - NOT PRODUCTION READY  
**Current Blocker**: psycopg2 runtime binary incompatibility  
**Raw Ingestion Status**: NOT YET SUCCESSFULLY EXECUTED

---

## Purpose

This is a prototype/test ingestion function designed to:
- Read S3 frozen corpus (26 JSONL files, 169 records)
- Connect to PostgreSQL via psycopg2
- Insert records into raw.raw_event table
- Implement deterministic ID and idempotency

**Important**: This is NOT a verified working implementation. Execution has failed due to runtime compatibility issues.

---

## Verification Status

### ✓ Verified (Working)
- Lambda deployment to AWS
- S3 bucket access from Lambda
- AWS Secrets Manager credential retrieval
- VPC configuration (subnets, security groups)
- Lambda environment setup (Python 3.9, Amazon Linux 2)

### ✗ NOT Verified (Blocking)
- psycopg2 import in Lambda runtime
- PostgreSQL SELECT 1 connection test
- Table structure validation through Lambda
- Raw data load (169 records)
- Second-run idempotency verification

### Current Blocker

**Error**: `No module named 'psycopg2._psycopg'`

**Cause**: psycopg2 binary incompatibility between:
- Build environment (Docker Amazon Linux 2)
- Lambda runtime (Amazon Linux 2)
- Possible sys.path discovery issue

**Status**: ROOT CAUSE NOT YET RESOLVED

---

## What Needs to Happen

1. Diagnose psycopg2 binary compatibility issue
2. Rebuild psycopg2 package if needed
3. Fix Lambda deployment package structure
4. Run connectivity test (`SELECT 1`)
5. Verify table structure from Lambda
6. Execute raw load with all 169 records
7. Verify second-run idempotency (same file twice = no duplicates)

---

## Code Overview

**Input**: S3 frozen corpus
- Location: S3 ingestion bucket
- Format: 26 JSONL files
- Records: 169 total

**Processing**:
1. Retrieve PostgreSQL credentials from Secrets Manager
2. Connect to accord database
3. For each record:
   - Generate deterministic source_record_id: SHA256(bucket|key|version|position)
   - Format as "FROZEN_<32-char-hex>"
   - Insert into raw.raw_event
   - Unique constraint prevents duplicates on second run

**Output**: raw.raw_event table
- raw_event_id: UUID
- source_system: Source identifier
- source_record_id: Deterministic SHA256 hash
- payload: JSON data
- timestamps: occurred_at, recorded_at, arrival_at
- ingestion_version: Run version

---

## Dependencies

- psycopg2-binary==2.9.9 (BLOCKING - binary incompatibility)
- boto3 (AWS SDK)
- Python 3.9 standard library

---

## Important Notes

❌ **DO NOT**:
- Deploy this Lambda expecting it to work (will fail with psycopg2 error)
- Claim raw ingestion is complete (it is NOT)
- Claim PostgreSQL connectivity is verified (it is NOT)
- Invoke this Lambda for production data load

⚠️ **KNOWN ISSUES**:
- psycopg2 binary not importable in Lambda runtime
- SELECT 1 test has never succeeded from Lambda
- Real data load (169 records) has never been executed
- Idempotency has never been verified

✓ **WHAT WORKS**:
- Lambda deploys successfully
- Lambda can read S3
- Lambda can retrieve Secrets Manager credentials
- VPC configuration is correct

---

## Next Steps

1. Resolve psycopg2 runtime binary issue
2. Rebuild psycopg2 package using exact Lambda base image
3. Fix Lambda deployment ZIP structure if needed
4. Re-test with diagnostic: `python test_psycopg2_connectivity.py`
5. Only after SELECT 1 succeeds: verify table structure
6. Only after table verification: attempt 169-record load
7. Only after load: verify idempotency with second run

---

## Files

- **lambda_function.py**: Prototype ingestion handler (psycopg2 blocker)
- **test_psycopg2_connectivity.py**: (in edms-simulator) Diagnostic test

---

**Status**: Prototype with known blocker - NOT READY FOR RAW INGESTION  
**Blocker**: psycopg2 binary incompatibility - UNRESOLVED  
**Action Required**: Fix psycopg2 runtime compatibility before proceeding

