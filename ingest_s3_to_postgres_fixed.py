#!/usr/bin/env python3
"""
RAW Ingestion: S3 → PostgreSQL (ECS/Fargate One-Shot Task)
Async Python script using asyncpg + boto3

Key differences from Lambda:
- Uses asyncpg for async PostgreSQL connection pooling
- One-shot execution (no loop, no polling, no schedule)
- File-level checkpoint: audit.ingestion_file tracks S3 object/version
- Idempotency: INSERT ... ON CONFLICT DO NOTHING
- Three operational gates: pre-check, load, verify
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
import hashlib
import base64
from concurrent.futures import ThreadPoolExecutor

import asyncpg
import boto3
from botocore.exceptions import ClientError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RawIngestionTask:
    """Main ingestion orchestrator"""

    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.s3_bucket = os.getenv('AWS_S3_BUCKET')
        self.s3_prefix = os.getenv('AWS_S3_PREFIX')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME')
        self.postgres_db = os.getenv('POSTGRES_DB_NAME', 'accord')
        self.dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'

        if not all([self.s3_bucket, self.s3_prefix, self.postgres_secret_name]):
            logger.error(
                "Missing required environment variables: "
                "AWS_S3_BUCKET, AWS_S3_PREFIX, POSTGRES_SECRET_NAME"
            )
            sys.exit(1)

        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.postgres_pool = None
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def main(self):
        """Main orchestration"""
        try:
            logger.info("=" * 70)
            logger.info("GATE 1: PRE-FLIGHT CHECKS")
            logger.info("=" * 70)

            # Get PostgreSQL credentials
            credentials = self._get_postgres_credentials()

            # Create connection pool
            self.postgres_pool = await asyncpg.create_pool(
                host=credentials['host'],
                port=credentials['port'],
                user=credentials['username'],
                password=credentials['password'],
                database=credentials['dbname'],
                ssl=credentials.get('ssl', True),
                min_size=2,
                max_size=10,
            )

            # Test connection
            await self._test_postgres_connection()

            # Verify required tables exist
            await self._verify_required_tables()

            logger.info("\n" + "=" * 70)
            logger.info("SCANNING S3 FOR JSONL FILES")
            logger.info("=" * 70)

            # Scan S3
            jsonl_files = await self._scan_s3_prefix()
            logger.info(f"Found {len(jsonl_files)} JSONL files")

            if not jsonl_files:
                logger.warning("No JSONL files found in S3 prefix")
                return 0

            # Track totals
            total_discovered = 0
            total_inserted = 0

            logger.info("\n" + "=" * 70)
            logger.info("GATE 2: LOAD JSONL FILES")
            logger.info("=" * 70)

            # Process each file
            for idx, (bucket, key) in enumerate(jsonl_files, 1):
                logger.info(f"\n[{idx}/{len(jsonl_files)}] Processing: {key}")

                # Get object version for idempotency
                version_id = await self._get_object_version(bucket, key)

                # Check if already processed
                already_processed = await self._check_file_already_processed(
                    bucket, key, version_id
                )
                if already_processed:
                    logger.info(f"  → SKIP (already processed)")
                    continue

                # Load JSONL file
                discovered, inserted = await self._load_jsonl_file(
                    bucket, key, version_id
                )
                total_discovered += discovered
                total_inserted += inserted

                logger.info(
                    f"  → Discovered: {discovered}, Inserted: {inserted}"
                )

            logger.info(f"\nTotal: {total_discovered} discovered, {total_inserted} inserted")

            logger.info("\n" + "=" * 70)
            logger.info("GATE 3: VERIFY RESULTS")
            logger.info("=" * 70)

            await self._verify_results()

            logger.info("\n" + "=" * 70)
            logger.info("✓ INGESTION COMPLETE")
            logger.info("=" * 70)

            return 0

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1

        finally:
            if self.postgres_pool:
                await self.postgres_pool.close()
            self.executor.shutdown(wait=False)

    def _get_postgres_credentials(self) -> Dict[str, Any]:
        """Retrieve PostgreSQL credentials from Secrets Manager"""
        try:
            response = self.secrets_client.get_secret_value(
                SecretId=self.postgres_secret_name
            )
            secret = json.loads(response['SecretString'])
            return secret
        except ClientError as e:
            logger.error(f"Failed to retrieve secret {self.postgres_secret_name}: {e}")
            sys.exit(1)

    async def _test_postgres_connection(self):
        """Test PostgreSQL connectivity"""
        try:
            async with self.postgres_pool.acquire() as conn:
                result = await conn.fetchval('SELECT 1')
                logger.info(f"✓ PostgreSQL connectivity OK")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            sys.exit(1)

    async def _verify_required_tables(self):
        """Verify required tables exist"""
        required_tables = [
            ('raw', 'raw_event'),
            ('audit', 'ingestion_file'),
        ]

        async with self.postgres_pool.acquire() as conn:
            for schema, table in required_tables:
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = $1 AND table_name = $2
                    )
                    """,
                    schema, table
                )
                if not exists:
                    logger.error(f"Required table {schema}.{table} does not exist")
                    sys.exit(1)
                logger.info(f"✓ Table {schema}.{table} exists")

    async def _scan_s3_prefix(self) -> list:
        """Scan S3 prefix for JSONL files"""
        def _list_s3():
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.s3_bucket,
                Prefix=self.s3_prefix
            )

            files = []
            for page in pages:
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    if obj['Key'].endswith('.jsonl'):
                        files.append((self.s3_bucket, obj['Key']))
            return files

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _list_s3)

    async def _get_object_version(self, bucket: str, key: str) -> str:
        """Get S3 object version ID (or deterministic token if versioning not enabled)"""
        def _get_version():
            try:
                response = self.s3_client.head_object(Bucket=bucket, Key=key)
                version_id = response.get('VersionId', 'null')
                etag = response.get('ETag', '').strip('"')

                # If no VersionId, use ETag as deterministic token
                if version_id == 'null' or not version_id:
                    version_id = f"etag-{etag}"

                return version_id
            except Exception as e:
                logger.warning(f"Could not get version for {key}: {e}")
                return "unknown"

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _get_version)

    async def _check_file_already_processed(
        self, bucket: str, key: str, version_id: str
    ) -> bool:
        """Check if file was already processed using audit.ingestion_file"""
        async with self.postgres_pool.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT status
                FROM audit.ingestion_file
                WHERE bucket_name = $1
                  AND object_key = $2
                  AND object_version = $3
                  AND status IN ('SUCCESS', 'PROCESSING')
                LIMIT 1
                """,
                bucket, key, version_id
            )
            return result is not None

    def _compute_deterministic_record_id(
        self, bucket: str, key: str, version_id: str, position: int
    ) -> str:
        """Compute deterministic record ID from S3 object details + position"""
        combined = f"{bucket}||{key}||{version_id}||{position}"
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()
        return f"FROZEN_{hash_hex}"

    async def _load_jsonl_file(
        self, bucket: str, key: str, version_id: str
    ) -> tuple:
        """Load JSONL file from S3 into raw.raw_event"""

        def _download_and_parse():
            """Download file from S3 and parse JSON lines"""
            try:
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                content = response['Body'].read().decode('utf-8')

                records = []
                for position, line in enumerate(content.strip().split('\n')):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        records.append((position, record))
                    except json.JSONDecodeError as e:
                        logger.warning(f"  Skipping invalid JSON at {key}:{position}: {e}")

                return records
            except Exception as e:
                logger.error(f"Failed to download/parse {key}: {e}")
                return []

        # Download and parse in executor
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(self.executor, _download_and_parse)

        if not records:
            return 0, 0

        # Insert records
        async with self.postgres_pool.acquire() as conn:
            async with conn.transaction():
                # Mark file as PROCESSING
                await conn.execute(
                    """
                    INSERT INTO audit.ingestion_file
                    (bucket_name, object_key, object_version, status,
                     processing_started_at, records_discovered)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (bucket_name, object_key, object_version)
                    DO UPDATE SET
                        status = $4,
                        processing_started_at = $5,
                        records_discovered = $6
                    """,
                    bucket, key, version_id, 'PROCESSING',
                    datetime.utcnow(), len(records)
                )

                inserted_count = 0

                # Insert records
                for position, record in records:
                    source_record_id = record.get(
                        'source_record_id',
                        self._compute_deterministic_record_id(
                            bucket, key, version_id, position
                        )
                    )

                    source_system = record.get('source_system', 'claris')
                    source_version = record.get('source_version', '1.0')

                    try:
                        result = await conn.execute(
                            """
                            INSERT INTO raw.raw_event
                            (source_system, source_record_id, source_version,
                             event_type, occurred_at, recorded_at, arrival_at,
                             arrival_date, launch_id, sku_id, material_id, payload)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            ON CONFLICT (source_system, source_record_id, source_version)
                            DO NOTHING
                            """,
                            source_system,
                            source_record_id,
                            source_version,
                            record.get('event_type'),
                            record.get('occurred_at'),
                            record.get('recorded_at'),
                            record.get('arrival_at'),
                            record.get('arrival_date'),
                            record.get('launch_id'),
                            record.get('sku_id'),
                            record.get('material_id'),
                            json.dumps(record)
                        )

                        # Check if insert actually happened
                        if result == 'INSERT 0 1':
                            inserted_count += 1

                    except asyncpg.UniqueViolationError:
                        pass  # Duplicate, expected on re-run
                    except Exception as e:
                        logger.error(f"Failed to insert record: {e}")

                # Mark file as SUCCESS
                await conn.execute(
                    """
                    UPDATE audit.ingestion_file
                    SET status = $1,
                        records_inserted = $2,
                        processing_completed_at = $3
                    WHERE bucket_name = $4
                      AND object_key = $5
                      AND object_version = $6
                    """,
                    'SUCCESS', inserted_count, datetime.utcnow(),
                    bucket, key, version_id
                )

        return len(records), inserted_count

    async def _verify_results(self):
        """Verify results after loading"""
        async with self.postgres_pool.acquire() as conn:
            raw_count = await conn.fetchval(
                'SELECT COUNT(*) FROM raw.raw_event'
            )
            checkpoint_count = await conn.fetchval(
                "SELECT COUNT(*) FROM audit.ingestion_file WHERE status = 'SUCCESS'"
            )

            logger.info(f"✓ raw.raw_event: {raw_count} records")
            logger.info(f"✓ audit.ingestion_file (SUCCESS): {checkpoint_count} files")

            # Check protected tables
            for schema, table in [
                ('runtime', 'evidence'),
                ('runtime', 'assertion'),
                ('state', 'fold_state_snapshot')
            ]:
                count = await conn.fetchval(
                    f'SELECT COUNT(*) FROM {schema}.{table}'
                )
                logger.info(f"✓ {schema}.{table}: {count} records (protected)")


async def main():
    """Entry point"""
    task = RawIngestionTask()
    exit_code = await task.main()
    sys.exit(exit_code)


if __name__ == '__main__':
    asyncio.run(main())
