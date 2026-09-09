# Retail OS

**Retail OS** is a data governance platform for product configuration management. It implements a deterministic, audited decision workflow: Raw Ingestion → Evidence Assembly → Assertion Generation → Fold State Compression → Canonical Configuration → Governed Decisions → Action Projection.

## Current Implementation Status (2026-09-06 - CORRECTED)

### ✓ Implemented Foundation

- **Repository Architecture**: Organized by layer (database, ontology, transforms, canonical, decisions, agents, audit)
- **PostgreSQL Schema**: Schemas (raw, runtime, state, audit), core tables, deterministic idempotency design
- **Ontology/KB Baseline**: Version 2026.10 (draft), Policy 1.1, KB 1.0.1
- **S3 Frozen Corpus**: 26 JSONL files, 169 raw records (ready for ingestion)
- **Lambda Prototype**: Deployed, S3/Secrets Manager working, but psycopg2 runtime incompatibility blocks execution
- **File-Level Idempotency**: Designed with deterministic SHA256 source_record_id, UNIQUE constraint (not yet tested)

### ⏸ Current Blocker

**Raw Ingestion NOT YET SUCCESSFULLY EXECUTED**

Lambda prototype deployed but blocked by:
- **Issue**: `No module named 'psycopg2._psycopg'` when Lambda tries to import psycopg2
- **Root Cause**: Binary incompatibility between build environment and Lambda runtime
- **Status**: UNRESOLVED - psycopg2 cannot be imported in Lambda environment
- **Impact**: All downstream steps (table verification, data load, idempotency test) cannot proceed

### ❌ Not Yet Verified

- ✗ psycopg2 import in Lambda runtime
- ✗ PostgreSQL SELECT 1 connection test
- ✗ PostgreSQL table structure access through Lambda
- ✗ Raw data ingestion (169 records)
- ✗ Second-run idempotency (duplicate prevention)

### ❌ Not Yet Implemented

- Raw → Evidence transformation
- Evidence → Assertions transformation
- Assertions → Fold state compression
- Canonical Configuration State
- Governed Decisions
- Actions / Projections
- Workbench
- AI Agents

---

## Project Structure

```
retail_os/
├── database/
│   ├── raw/                            # Raw ingestion layer
│   │   └── lambda/
│   │       ├── lambda_function.py      # PROTOTYPE - psycopg2 blocker
│   │       └── README.md               # Blocker documentation
│   ├── ddl/                            # PostgreSQL schema definitions
│   ├── ingestion/                      # Legacy ingestion directory
│   └── procedures/                     # Transformations (TODO)
├── ontology/
│   ├── source/                         # Ontology definitions
│   ├── compiled/                       # KB load scripts
│   ├── migrations/                     # TODO
│   └── validation/                     # TODO
├── transforms/, canonical/, decisions/, agents/  # TODO
└── audit/, docs/, tests/, ui/          # TODO
```

---

## Known Issues & Gaps

### ⚠ CRITICAL: psycopg2 Runtime Incompatibility

**Issue**: Lambda cannot import psycopg2  
**Error**: `No module named 'psycopg2._psycopg'`  
**Status**: BLOCKING ALL RAW INGESTION  
**Root Cause**: Binary driver built in Docker not compatible with Lambda runtime  
**Resolution Required**: Rebuild psycopg2 package with exact Lambda environment  

### ⚠ UC-18 Duplicate Configuration Prevention

**Issue**: Configuration request state (CONFIGURATION_REQUEST) has no source/data contract  
**Status**: Identified, not blocking ingestion (raw ingestion already blocked by psycopg2)  
**Action**: Do NOT fabricate configuration requests  

---

## What Actually Works

✓ Lambda deploys successfully  
✓ Lambda can access S3 (frozen corpus)  
✓ Lambda can retrieve Secrets Manager credentials  
✓ VPC configuration correct (subnets, security groups)  
✓ PostgreSQL schema deployed (raw, runtime, state, audit schemas)  
✓ Idempotency design correct (UNIQUE constraint in place)  

---

## What Doesn't Work Yet

✗ Lambda cannot import psycopg2 (BLOCKER)  
✗ PostgreSQL connectivity not verified from Lambda  
✗ Raw ingestion not executed  
✗ Data load (169 records) not attempted  
✗ Idempotency not tested  

---

## Next Steps (In Order)

1. **FIX BLOCKER**: Resolve psycopg2 binary incompatibility
   - Rebuild psycopg2 in exact Lambda environment
   - Fix Lambda deployment ZIP structure if needed
2. **VERIFY CONNECTIVITY**: Run connectivity test
   - `python test_psycopg2_connectivity.py`
   - Confirm SELECT 1 succeeds from Lambda
3. **VERIFY TABLE STRUCTURE**: Check table accessibility
   - Verify raw_event table is accessible from Lambda
   - Verify all columns present
4. **EXECUTE RAW LOAD**: Ingest 169 records
   - Load all S3 records into raw.raw_event
5. **VERIFY IDEMPOTENCY**: Test duplicate prevention
   - Re-run ingestion with same S3 files
   - Confirm no new records inserted (UNIQUE constraint prevents duplicates)
6. **AUTHORIZE**: Once verified, authorize Manual Run 1
7. **BEGIN TRANSFORMATIONS**: Implement raw→evidence→assertion→fold

---

## Technology Stack

- **Database**: PostgreSQL (us-west-2 RDS, VPC-isolated)
- **Ingestion**: AWS Lambda (Python 3.9, x86_64, Amazon Linux 2) - BLOCKED
- **Driver**: psycopg2 2.9.9 (binary built in Docker) - INCOMPATIBILITY ISSUE
- **Secrets**: AWS Secrets Manager (working)
- **Object Store**: S3 (frozen corpus, working)
- **Versioning**: Git (GitHub)

---

## Repository

- **Local**: `C:\Users\bkgou\OneDrive\Documents\retail_os`
- **Remote**: https://github.com/krishnamami/retail-os
- **Branch**: main

---

## Status Summary

| Component | Status | Blocker |
|-----------|--------|---------|
| S3 Corpus | ✓ Ready | None |
| Lambda Deployment | ✓ Ready | None |
| Secrets Manager | ✓ Working | None |
| VPC Configuration | ✓ Correct | None |
| PostgreSQL Schema | ✓ Deployed | None |
| **psycopg2 Import** | **✗ FAILED** | **YES - BLOCKS ALL** |
| PostgreSQL Connectivity | ✗ Not Verified | Blocked by psycopg2 |
| Raw Ingestion | ✗ Not Executed | Blocked by psycopg2 |
| Idempotency Test | ✗ Not Verified | Blocked by psycopg2 |

---

For detailed status, see:
- **database/raw/lambda/README.md** - Lambda prototype blocker details
- **CURRENT_STATUS.md** - Comprehensive implementation status
- **IMPORT_COMPLETE_AUDIT.md** - Detailed audit trail

*Last updated: 2026-09-06 (CORRECTED - Accurate blocker documentation)*

