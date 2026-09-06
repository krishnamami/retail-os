# Lambda Ingestion Function

This directory contains the AWS Lambda function code for Retail OS data ingestion.

## Files

- **lambda_function.py**: Current deployed Lambda ingestion handler
  - Reads S3 events from ingestion bucket
  - Connects to PostgreSQL via psycopg2 (binary built for Python 3.9, Amazon Linux 2)
  - Inserts raw events into raw.raw_event table
  - Implements deterministic source_record_id (SHA256 hash)
  - Implements file-level idempotency via UNIQUE constraint
  - Retrieves PostgreSQL credentials from AWS Secrets Manager
  - Runs in VPC-isolated environment (no public internet access)

- **lambda_ingestion_implementation_reference.py**: Enhanced reference implementation
  - Includes test_mode for READ-ONLY connectivity verification
  - Useful for troubleshooting and validation
  - Not deployed to Lambda; for reference only

## Environment

- **Python**: 3.9
- **Runtime**: Amazon Linux 2 (x86_64)
- **Region**: us-west-2
- **VPC**: Private subnets with RDS access only
- **Binary Dependencies**: psycopg2 2.9.9 (built in Docker for exact Linux environment)

## Deployment Package Structure

The Lambda deployment ZIP must have this structure:
```
claris-ingestion-lambda.zip
├── lambda_function.py          (at root level)
├── psycopg2/                   (at root level)
├── boto3/                      (at root level)
└── ... (all packages at root, not in subdirectories)
```

**Important**: All Python packages must be at ZIP root level for sys.path discovery.

## Dependencies

- psycopg2-binary==2.9.9 (PostgreSQL driver)
- boto3 (AWS SDK)

## PostgreSQL Connection

- **Secrets Manager Key**: claris/postgres/credentials
- **Credentials Retrieved**:
  - host: RDS endpoint
  - port: 5432
  - database: accord
  - username: claris_ingestion
  - password: (from Secrets Manager)

## Data Model

Inserts into `raw.raw_event` table:
- **raw_event_id**: UUID (auto-generated primary key)
- **source_system**: Source S3 bucket/location
- **source_record_id**: SHA256 hash of (bucket|key|version|position) formatted as "FROZEN_<hex>"
- **source_version**: Version tracking
- **payload**: JSON data (JSONB column)
- **event_type**: Event classification
- **occurred_at**: When event occurred (timestamp)
- **recorded_at**: When event was recorded (timestamp)
- **arrival_at**: When Lambda received it (timestamp)
- **ingestion_version**: Ingestion run version

## File-Level Idempotency

- UNIQUE constraint on (source_system, source_record_id, source_version)
- Prevents duplicate ingestion if the same file is processed multiple times
- Enables safe retry without data duplication

## Troubleshooting

See `/tmp/diagnose_lambda.py` for diagnostic tool:
- Checks Lambda configuration
- Retrieves CloudWatch logs
- Tests connectivity with test payload

## Important Constraints

❌ **Do NOT**:
- Modify Lambda business logic without approval
- Change the deterministic ID calculation
- Remove idempotency checks
- Invoke ingestion without proper authorization
- Modify S3 corpus configuration
- Change PostgreSQL schema

✓ **READ-ONLY testing is safe**: The diagnostic test mode only verifies connectivity

---

*Imported from edms-simulator project. Current deployment version.*
