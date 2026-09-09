# RAW Ingestion: S3 → PostgreSQL (ECS/Fargate One-Shot Prototype)

## Overview

This is a replacement for the blocked Lambda-based raw ingestion prototype. It uses **ECS/Fargate** to execute a one-shot containerized Python task that loads raw event data from S3 into PostgreSQL.

### Why ECS Instead of Lambda?

| Issue | Lambda | ECS/Fargate |
|-------|--------|-----------|
| **Binary compatibility** | psycopg2 rebuild required for Amazon Linux 2 | Standard Python 3.11 container; pip install |
| **Connection timeout** | 300s handler limit (you hit it) | No timeout; runs as long as needed |
| **VPC networking** | 30–60s cold start + ENI attachment delay | Container boots once; warm pool reused |
| **Incremental loading** | Stateless; re-ingest all data | Uses audit.ingestion_file checkpoint |
| **Execution model** | Event-driven (one invocation) | Manual one-shot task |

---

## Architecture

```
S3 Bucket
  ├─ accord-capital-loans-usw2-621646470377
  └─ claris/source-corpus/raw/
      ├─ sku-001.jsonl   (26 JSONL files, 169 records total)
      ├─ sku-002.jsonl
      └─ ...

          ↓ (boto3 S3 scan + download)

ECS Fargate Container
  ├─ asyncpg connection pool → PostgreSQL
  ├─ Audit checkpoint: audit.ingestion_file (S3 object/version)
  └─ On first run: load all files, set status=SUCCESS
     On second run: skip already-processed files, 0 inserts

          ↓ (asyncpg INSERT ... ON CONFLICT DO NOTHING)

PostgreSQL (claris database)
  ├─ raw.raw_event (169 records)
  ├─ runtime.evidence (0 records — protected, empty)
  ├─ runtime.assertion (0 records — protected, empty)
  ├─ state.fold_state_snapshot (0 records — protected, empty)
  └─ audit.ingestion_file (checkpoint; 26 files, status=SUCCESS)
```

---

## Files

### Application Code

| File | Purpose |
|------|---------|
| `ingest_s3_to_postgres.py` | Main ingestion script (asyncpg + boto3) |
| `Dockerfile` | Container definition (Python 3.11) |
| `requirements.txt` | Dependencies (asyncpg, boto3) |
| `README.md` | This file |

### SQL Verification

| File | Purpose | When to Run |
|------|---------|-----------|
| `verify_raw_preload.sql` | Pre-flight checks | Before Gate 1 |
| `verify_raw_postload.sql` | Post-load verification | After Gate 2 |
| `verify_idempotency.sql` | Second-run idempotency | After Gate 3 |

---

## Execution Model

### Manual Invocation (No Scheduler)

```bash
# One-time ECS task run
aws ecs run-task \
  --cluster retail-os-prototype \
  --task-definition raw-ingestion-ecs \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxxxx],
    securityGroups=[sg-xxxxx]
  }"
```

**Flow:**
1. Container starts
2. Retrieves PostgreSQL credentials from Secrets Manager
3. Connects to PostgreSQL
4. Runs Gate 1: pre-flight checks
5. Scans S3 prefix for JSONL files
6. Consults `audit.ingestion_file` for idempotency
7. Loads unprocessed files into `raw.raw_event`
8. Updates audit checkpoint
9. Exits

**No loop. No polling. No schedule.**

---

## Prerequisites

### AWS Resources Required

1. **ECS Cluster** — existing or create new
   ```bash
   aws ecs create-cluster --cluster-name retail-os-prototype
   ```

2. **IAM Task Execution Role** — permissions for ECS to pull logs, fetch secrets
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "logs:CreateLogGroup",
           "logs:CreateLogStream",
           "logs:PutLogEvents"
         ],
         "Resource": "arn:aws:logs:us-west-2:*:log-group:/ecs/raw-ingestion:*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "secretsmanager:GetSecretValue"
         ],
         "Resource": "arn:aws:secretsmanager:us-west-2:*:secret:retail_os/rds/postgres*"
       }
     ]
   }
   ```

3. **IAM Task Role** — permissions for container to access S3 + Secrets Manager
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::accord-capital-loans-usw2-621646470377",
           "arn:aws:s3:::accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/*"
         ]
       },
       {
         "Effect": "Allow",
         "Action": [
           "secretsmanager:GetSecretValue"
         ],
         "Resource": "arn:aws:secretsmanager:us-west-2:*:secret:retail_os/rds/postgres*"
       }
     ]
   }
   ```

4. **Security Group** — for ECS task to reach PostgreSQL
   ```bash
   aws ec2 authorize-security-group-ingress \
     --group-id sg-xxxxx \
     --protocol tcp \
     --port 5432 \
     --source-group sg-xxxxx  # self-reference for ECS task subnet
   ```

5. **CloudWatch Log Group**
   ```bash
   aws logs create-log-group --log-group-name /ecs/raw-ingestion
   ```

### PostgreSQL Secrets

Credentials must be stored at:
```
arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:retail_os/rds/postgres
```

Schema (JSON):
```json
{
  "username": "claris_ingest",
  "password": "***",
  "host": "database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com",
  "port": 5432,
  "dbname": "claris",
  "ssl": true
}
```

---

## Build & Deploy

### Step 1: Build Docker Image

```bash
cd database/raw/ecs/

# Build
docker build -t raw-ingestion:latest .

# Tag for ECR
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-west-2.amazonaws.com

docker tag raw-ingestion:latest \
  ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/raw-ingestion:latest

# Push
docker push ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/raw-ingestion:latest
```

### Step 2: Register ECS Task Definition

```bash
# Create task definition (save as task-definition.json)
cat > task-definition.json << 'EOF'
{
  "family": "raw-ingestion-ecs",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/raw-ingestion-task-role",
  "containerDefinitions": [
    {
      "name": "raw-ingestion",
      "image": "ACCOUNT.dkr.ecr.us-west-2.amazonaws.com/raw-ingestion:latest",
      "environment": [
        {
          "name": "AWS_REGION",
          "value": "us-west-2"
        },
        {
          "name": "AWS_S3_BUCKET",
          "value": "accord-capital-loans-usw2-621646470377"
        },
        {
          "name": "AWS_S3_PREFIX",
          "value": "claris/source-corpus/raw/"
        },
        {
          "name": "POSTGRES_SECRET_NAME",
          "value": "retail_os/rds/postgres"
        },
        {
          "name": "POSTGRES_DB_NAME",
          "value": "claris"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/raw-ingestion",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

# Register
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

---

## Execution: The Three Gates

### Gate 1: Read-Only Pre-Check

**Before running the ECS task**, verify PostgreSQL connectivity and table structure:

```bash
# Connect to PostgreSQL and run:
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -U claris_ingest -d claris \
     -f database/raw/sql/verify_raw_preload.sql
```

**Expected output:**
- ✓ All required tables exist
- ✓ raw.raw_event is empty (or has existing records)
- ✓ Protected tables (evidence, assertion, fold) are empty
- ✓ audit.ingestion_file checkpoint table exists

**Stop if precheck fails.**

### Gate 2: Manual Run 1

**Run the ECS task:**

```bash
aws ecs run-task \
  --cluster retail-os-prototype \
  --task-definition raw-ingestion-ecs:1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxxxx,subnet-yyyyy],
    securityGroups=[sg-xxxxx],
    assignPublicIp=DISABLED
  }"
```

**Monitor logs:**

```bash
aws logs tail /ecs/raw-ingestion --follow
```

**Expected output:**
- ✓ PostgreSQL connectivity test passed
- ✓ Found 26 JSONL files
- ✓ 169 records discovered, 169 records inserted
- ✓ Checkpoint written to audit.ingestion_file

**Verify after task completes:**

```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -U claris_ingest -d claris \
     -f database/raw/sql/verify_raw_postload.sql
```

**Expected:**
- ✓ raw.raw_event = 169 records
- ✓ runtime.evidence = 0
- ✓ runtime.assertion = 0
- ✓ state.fold_state_snapshot = 0
- ✓ audit.ingestion_file = 26 files with status=SUCCESS

### Gate 3: Idempotency Run

**Run the same ECS task again** (same S3, no changes):

```bash
aws ecs run-task \
  --cluster retail-os-prototype \
  --task-definition raw-ingestion-ecs:1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxxxx,subnet-yyyyy],
    securityGroups=[sg-xxxxx],
    assignPublicIp=DISABLED
  }"
```

**Expected log output:**
- ✓ Found 26 JSONL files
- ✓ All 26 files already processed (SKIP status)
- ✓ 0 records inserted (ON CONFLICT DO NOTHING)
- ✓ Checkpoint rows already exist; status remains SUCCESS

**Verify after second run:**

```bash
psql -h database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com \
     -U claris_ingest -d claris \
     -f database/raw/sql/verify_idempotency.sql
```

**Expected:**
- ✓ raw.raw_event still = 169 records (NO DUPLICATES)
- ✓ Duplicate source identity count = 0
- ✓ Protected tables remain empty
- ✓ audit.ingestion_file shows 2 ingestion timestamps (2 runs)

---

## Raw Event Contract

Records inserted into `raw.raw_event` preserve the source structure:

```sql
SELECT
  id,
  source_system,          -- 'claris' (or derived from S3 metadata)
  source_record_id,       -- from source OR SHA256(bucket||key||version||position)
  source_version,         -- from source (default '1.0')
  event_type,             -- from source JSON
  occurred_at,            -- from source JSON
  recorded_at,            -- from source JSON
  arrival_at,             -- from source JSON
  arrival_date,           -- from source JSON
  launch_id,              -- from source JSON
  sku_id,                 -- from source JSON
  material_id,            -- from source JSON
  payload,                -- full original JSON record (JSONB)
  ingested_at             -- server timestamp when inserted
FROM raw.raw_event
LIMIT 1;
```

### Idempotency Contract

```sql
-- Unique constraint on source identity
UNIQUE (source_system, source_record_id, source_version)

-- On re-ingestion:
INSERT INTO raw.raw_event (...)
VALUES (...)
ON CONFLICT (source_system, source_record_id, source_version)
DO NOTHING;  -- No duplicates
```

### File-Level Checkpoint

```sql
-- audit.ingestion_file tracks S3 object/version
SELECT
  bucket,           -- 'accord-capital-loans-usw2-621646470377'
  object_key,       -- 's3://bucket/claris/source-corpus/raw/sku-001.jsonl'
  object_version,   -- S3 VersionId (or deterministic token)
  status,           -- 'SUCCESS' after first run
  records_discovered,  -- 169 total across all 26 files
  records_inserted,    -- 169 (only first run)
  ingested_at       -- timestamp of ingestion
FROM audit.ingestion_file;
```

---

## Troubleshooting

### Task fails to start

Check ECS task logs:
```bash
aws logs tail /ecs/raw-ingestion --follow --since 5m
```

Common issues:
- Task role missing S3 permissions
- VPC security group blocks PostgreSQL port 5432
- Secrets Manager secret name incorrect

### PostgreSQL connection fails

Verify from ECS task security group can reach PostgreSQL:
```bash
# From ECS task container
telnet database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com 5432

# From PostgreSQL
SELECT 1;
```

### 0 records inserted

Check if files are already processed in `audit.ingestion_file`:
```sql
SELECT COUNT(*) FROM audit.ingestion_file WHERE status = 'SUCCESS';
```

If > 0, run was idempotent (expected on 2nd run). Run Gate 3 to verify.

### Records show up twice

This indicates idempotency failed. Check:
1. Unique constraint exists: `UNIQUE(source_system, source_record_id, source_version)`
2. INSERT uses `ON CONFLICT DO NOTHING`
3. `source_record_id` is deterministic (not random UUID)

---

## Cleanup

To delete and start fresh:

```sql
-- DANGER: only if starting from scratch
TRUNCATE raw.raw_event CASCADE;
TRUNCATE audit.ingestion_file CASCADE;

-- Then re-run Gate 1 to verify empty state
```

---

## Success Criteria

Declare RAW ingestion complete when:

- [x] ECS container starts and connects to PostgreSQL
- [x] Gate 1: Pre-check passes (SELECT 1, tables exist, protected tables empty)
- [x] Gate 2: First run produces raw.raw_event = 169 records
- [x] Gate 2: Protected tables remain empty after first run
- [x] Gate 3: Second run leaves raw.raw_event = 169 (no duplicates)
- [x] Gate 3: Duplicate source identity count = 0
- [x] Repository contains ECS source + build assets (Dockerfile, requirements.txt, Python script)
- [x] No secrets committed to repository

**Final Status:**
```
✓ RAW INGESTION VERIFIED VIA ECS
✓ 26 JSONL FILES PROCESSED
✓ 169 RECORDS LOADED IDEMPOTENTLY
✓ PROTECTED TABLES REMAIN EMPTY
✓ READY FOR NEXT PHASE (Evidence/Assertion/Fold — NOT YET IMPLEMENTED)
```

---

## Next Steps (After Raw Verified)

- [ ] Implement Evidence → (Evidence schema design, not started)
- [ ] Implement Assertion → (Assertion logic, not started)
- [ ] Implement Fold → (State aggregation, not started)
- [ ] Implement Canonical → (Not started)
- [ ] Implement Decisions → (Not started)
- [ ] Implement Actions → (Not started)
- [ ] Implement Projection → (Not started)
- [ ] Implement Workbench → (Not started)

**For now: STOP after raw.raw_event = 169.**
