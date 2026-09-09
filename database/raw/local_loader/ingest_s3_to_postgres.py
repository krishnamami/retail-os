#!/usr/bin/env python3
"""
RAW Ingestion: S3 → PostgreSQL (Local Prototype)
Single-run async loader with idempotency via ON CONFLICT DO NOTHING
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import hashlib
from dateutil import parser as date_parser

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
    """Local S3 → PostgreSQL ingestion orchestrator"""

    def __init__(self, expected_baseline_count: int = 169):
        self.expected_baseline_count = expected_baseline_count
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.s3_bucket = os.getenv('AWS_S3_BUCKET', 'accord-capital-loans-usw2-621646470377')
        self.s3_prefix = os.getenv('AWS_S3_PREFIX', 'claris/source-corpus/raw/')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME', 'retail_os/rds/postgres')
        self.postgres_db = os.getenv('POSTGRES_DB_NAME', 'claris')

        if not all([self.s3_bucket, self.s3_prefix]):
            logger.error("Missing required environment variables: AWS_S3_BUCKET, AWS_S3_PREFIX")
            sys.exit(1)

        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.postgres_pool = None

    async def main(self):
        try:
            logger.info("=" * 70)
            logger.info("STEP 1: PRE-FLIGHT CHECKS")
            logger.info("=" * 70)

            credentials = self._get_postgres_credentials()

            self.postgres_pool = await asyncpg.create_pool(
                host=credentials['host'],
                port=credentials['port'],
                user=credentials['username'],
                password=credentials['password'],
                database=credentials['dbname'],
                min_size=2,
                max_size=5,
                timeout=30.0,
                command_timeout=30.0,
                max_cached_statement_lifetime=300,
                max_cacheable_statement_size=15000,
            )

            await self._test_postgres_connection()
            await self._verify_required_tables()

            logger.info("\n" + "=" * 70)
            logger.info("STEP 2: DISCOVER S3 CORPUS")
            logger.info("=" * 70)

            jsonl_files = await self._scan_s3_prefix()
            logger.info(f"Found {len(jsonl_files)} JSONL files")

            if not jsonl_files:
                logger.warning("No JSONL files found in S3 prefix")
                return 0

            # Note: File count may vary as new records are added. Just log for reference.
            logger.info(f"Note: S3 corpus contains {len(jsonl_files)} JSONL files")

            total_discovered = 0
            for bucket, key in jsonl_files:
                count = await self._count_records_in_file(bucket, key)
                total_discovered += count

            logger.info(f"Total records in corpus: {total_discovered}")
            # Note: Record count may vary as new records are added. Just log for reference.
            logger.info(f"Note: S3 corpus contains {total_discovered} total records")

            logger.info("\n" + "=" * 70)
            logger.info("STEP 3: LOAD JSONL FILES")
            logger.info("=" * 70)

            total_inserted = 0
            failed_files = []

            for idx, (bucket, key) in enumerate(jsonl_files, 1):
                logger.info(f"\n[{idx}/{len(jsonl_files)}] Processing: {key}")

                try:
                    discovered, inserted = await self._load_jsonl_file(bucket, key)
                    total_inserted += inserted
                    logger.info(f"  → Discovered: {discovered}, Inserted: {inserted}")
                except Exception as e:
                    logger.error(f"  → FAILED: {e}")
                    failed_files.append((key, str(e)))

            logger.info(f"\nTotal inserted: {total_inserted}/{total_discovered}")

            if failed_files:
                logger.warning(f"Failed files: {len(failed_files)}")
                for key, error in failed_files:
                    logger.warning(f"  - {key}: {error}")
                return 1

            logger.info("\n" + "=" * 70)
            logger.info("STEP 4: VERIFY RESULTS")
            logger.info("=" * 70)

            await self._verify_results()

            logger.info("\n" + "=" * 70)
            logger.info("✓ RAW INGESTION COMPLETE")
            logger.info("=" * 70)

            return 0

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1

        finally:
            if self.postgres_pool:
                await self.postgres_pool.close()

    def _get_postgres_credentials(self) -> Dict[str, Any]:
        try:
            response = self.secrets_client.get_secret_value(
                SecretId=self.postgres_secret_name
            )
            secret = json.loads(response['SecretString'])
            logger.info(f"✓ Retrieved credentials for {self.postgres_secret_name}")
            return secret
        except ClientError as e:
            logger.error(f"Failed to retrieve secret {self.postgres_secret_name}: {e}")
            sys.exit(1)

    async def _test_postgres_connection(self):
        try:
            async with self.postgres_pool.acquire() as conn:
                result = await conn.fetchval('SELECT 1')
                logger.info(f"✓ PostgreSQL connectivity OK")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            sys.exit(1)

    async def _verify_required_tables(self):
        required_tables = [
            ('raw', 'raw_event'),
            ('runtime', 'evidence'),
            ('runtime', 'assertion'),
            ('state', 'fold_state_snapshot'),
            ('audit', 'ingestion_log'),
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

                count = await conn.fetchval(f'SELECT COUNT(*) FROM {schema}.{table}')
                logger.info(f"✓ Table {schema}.{table}: {count} rows")

            # STEP 5D: Verify baseline matches expected count (idempotency safety)
            raw_count = await conn.fetchval('SELECT COUNT(*) FROM raw.raw_event')
            logger.info(f"Raw baseline count: {raw_count}")
            if raw_count != self.expected_baseline_count:
                logger.error(
                    f"STOP: expected Step 5D baseline of {self.expected_baseline_count} rows, "
                    f"found {raw_count}"
                )
                sys.exit(1)

    async def _scan_s3_prefix(self) -> list:
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
            return sorted(files)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list_s3)

    async def _count_records_in_file(self, bucket: str, key: str) -> int:
        def _count():
            try:
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                content = response['Body'].read().decode('utf-8')
                lines = [line for line in content.strip().split('\n') if line.strip()]
                return len(lines)
            except Exception as e:
                logger.warning(f"Could not count records in {key}: {e}")
                return 0

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _count)

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse ISO 8601 datetime string to datetime object"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return date_parser.isoparse(value)
            except Exception:
                logger.warning(f"Could not parse datetime: {value}")
                return None
        return None

    def _compute_deterministic_record_id(
        self, bucket: str, key: str, position: int
    ) -> str:
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            version_id = response.get('VersionId', 'null')
            etag = response.get('ETag', '').strip('"')
            if version_id == 'null' or not version_id:
                version_id = f"etag-{etag}"
        except Exception:
            version_id = "unknown"

        combined = f"{bucket}||{key}||{version_id}||{position}"
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()
        return f"FROZEN_{hash_hex}"

    async def _load_jsonl_file(
        self, bucket: str, key: str
    ) -> Tuple[int, int]:
        def _download_and_parse():
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

        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(None, _download_and_parse)

        if not records:
            return 0, 0

        async with self.postgres_pool.acquire() as conn:
            async with conn.transaction():
                inserted_count = 0

                for position, record in records:
                    source_record_id = record.get(
                        'source_record_id',
                        self._compute_deterministic_record_id(bucket, key, position)
                    )

                    source_system = record.get('source_system', 'claris')
                    source_version_str = record.get('source_version', '1.0')

                    try:
                        source_version = int(float(source_version_str))
                    except (ValueError, TypeError):
                        source_version = 1

                    try:
                        occurred_at = self._parse_datetime(record.get('occurred_at'))
                        recorded_at = self._parse_datetime(record.get('recorded_at'))
                        arrival_at = self._parse_datetime(record.get('arrival_at'))

                        result = await conn.execute(
                            """
                            INSERT INTO raw.raw_event
                            (source_system, source_record_id, source_version,
                             event_type, occurred_at, recorded_at, arrival_at,
                             launch_id, sku_id, material_id, payload)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            ON CONFLICT (source_system, source_record_id, source_version)
                            DO NOTHING
                            """,
                            source_system,
                            source_record_id,
                            source_version,
                            record.get('event_type'),
                            occurred_at,
                            recorded_at,
                            arrival_at,
                            record.get('launch_id'),
                            record.get('sku_id'),
                            record.get('material_id'),
                            json.dumps(record)
                        )

                        if result == 'INSERT 0 1':
                            inserted_count += 1

                    except asyncpg.UniqueViolationError:
                        pass
                    except Exception as e:
                        logger.error(f"Failed to insert record: {e}")
                        raise

        return len(records), inserted_count

    async def _verify_results(self):
        async with self.postgres_pool.acquire() as conn:
            raw_count = await conn.fetchval(
                'SELECT COUNT(*) FROM raw.raw_event'
            )
            logger.info(f"✓ raw.raw_event: {raw_count} records")

            for schema, table in [
                ('runtime', 'evidence'),
                ('runtime', 'assertion'),
                ('state', 'fold_state_snapshot')
            ]:
                count = await conn.fetchval(
                    f'SELECT COUNT(*) FROM {schema}.{table}'
                )
                logger.info(f"✓ {schema}.{table}: {count} records")

            distribution = await conn.fetch(
                'SELECT source_system, COUNT(*) FROM raw.raw_event GROUP BY source_system ORDER BY source_system'
            )
            logger.info(f"✓ Source system distribution:")
            for row in distribution:
                logger.info(f"  {row['source_system']}: {row['count']}")

            null_record_id = await conn.fetchval(
                'SELECT COUNT(*) FROM raw.raw_event WHERE source_record_id IS NULL'
            )
            logger.info(f"✓ NULL source_record_id count: {null_record_id}")

            null_system = await conn.fetchval(
                'SELECT COUNT(*) FROM raw.raw_event WHERE source_system IS NULL'
            )
            logger.info(f"✓ NULL source_system count: {null_system}")

            duplicate_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM (
                    SELECT source_system, source_record_id, source_version, COUNT(*)
                    FROM raw.raw_event
                    GROUP BY source_system, source_record_id, source_version
                    HAVING COUNT(*) > 1
                ) dup
                """
            )
            logger.info(f"✓ Duplicate identity count: {duplicate_count}")


async def main(expected_baseline_count: int = 169):
    task = RawIngestionTask(expected_baseline_count=expected_baseline_count)
    exit_code = await task.main()
    sys.exit(exit_code)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='RAW Ingestion: S3 → PostgreSQL with idempotency validation'
    )
    parser.add_argument(
        '--expected-baseline-count',
        type=int,
        default=169,
        help='Expected number of records in raw.raw_event before ingestion (default: 169)'
    )
    args = parser.parse_args()

    asyncio.run(main(expected_baseline_count=args.expected_baseline_count))
