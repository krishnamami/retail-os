#!/usr/bin/env python3
"""
STEP 5D: Live Raw Schema Inspection (READ-ONLY)
Queries information_schema to determine actual database structure
Does NOT modify database, run ingestion, or alter schema
"""

import asyncio
import json
import logging
import os
import sys

import asyncpg
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LiveSchemaInspector:
    """Read-only schema inspector for live PostgreSQL"""

    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME', 'retail_os/rds/postgres')
        self.postgres_db = os.getenv('POSTGRES_DB_NAME', 'claris')
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.postgres_pool = None

    async def main(self):
        """Main inspection"""
        try:
            logger.info("=" * 80)
            logger.info("STEP 5D: LIVE RAW SCHEMA VERIFICATION")
            logger.info("=" * 80)

            # Get credentials and connect
            credentials = self._get_postgres_credentials()

            self.postgres_pool = await asyncpg.create_pool(
                host=credentials['host'],
                port=credentials['port'],
                user=credentials['username'],
                password=credentials['password'],
                database=credentials['dbname'],
                min_size=1,
                max_size=1,
            )

            logger.info(f"✓ Connected to PostgreSQL: {credentials['host']}:{credentials['port']}/{credentials['dbname']}")
            logger.info("")

            # Run inspections
            await self._inspect_raw_event_columns()
            await self._inspect_unique_constraints()
            await self._inspect_indexes()
            await self._sample_baseline_rows()
            await self._count_baseline()

            logger.info("\n" + "=" * 80)
            logger.info("✓ SCHEMA INSPECTION COMPLETE - NO CHANGES MADE")
            logger.info("=" * 80)

            return 0

        except Exception as e:
            logger.error(f"Schema inspection failed: {e}", exc_info=True)
            return 1

        finally:
            if self.postgres_pool:
                await self.postgres_pool.close()

    def _get_postgres_credentials(self):
        try:
            response = self.secrets_client.get_secret_value(
                SecretId=self.postgres_secret_name
            )
            return json.loads(response['SecretString'])
        except ClientError as e:
            logger.error(f"Failed to retrieve secret {self.postgres_secret_name}: {e}")
            sys.exit(1)

    async def _inspect_raw_event_columns(self):
        """Query information_schema.columns for raw.raw_event"""
        logger.info("1. RAW.RAW_EVENT COLUMNS (from information_schema)")
        logger.info("-" * 80)

        async with self.postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                  column_name,
                  data_type,
                  is_nullable,
                  column_default,
                  ordinal_position
                FROM information_schema.columns
                WHERE table_schema = 'raw'
                  AND table_name = 'raw_event'
                ORDER BY ordinal_position
                """
            )

            if not rows:
                logger.error("  ✗ No columns found for raw.raw_event")
                return

            logger.info(f"  Found {len(rows)} columns:")
            logger.info("")

            source_version_exists = False
            ingestion_version_exists = False

            for row in rows:
                col_name = row['column_name']
                data_type = row['data_type']
                nullable = row['is_nullable']
                default = row['column_default'] or 'NULL'

                logger.info(f"  • {col_name:30s} | {data_type:20s} | nullable={nullable:5s} | default={default}")

                if col_name == 'source_version':
                    source_version_exists = True
                if col_name == 'ingestion_version':
                    ingestion_version_exists = True

            logger.info("")
            logger.info(f"  ✓ source_version exists: {source_version_exists}")
            logger.info(f"  ✓ ingestion_version exists: {ingestion_version_exists}")
            logger.info("")

    async def _inspect_unique_constraints(self):
        """Query information_schema for UNIQUE constraints on raw.raw_event"""
        logger.info("2. RAW.RAW_EVENT UNIQUE CONSTRAINTS")
        logger.info("-" * 80)

        async with self.postgres_pool.acquire() as conn:
            # Get UNIQUE constraints
            rows = await conn.fetch(
                """
                SELECT
                  tc.constraint_name,
                  string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns,
                  tc.constraint_type
                FROM information_schema.table_constraints tc
                LEFT JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'raw'
                  AND tc.table_name = 'raw_event'
                  AND tc.constraint_type = 'UNIQUE'
                GROUP BY tc.constraint_name, tc.constraint_type
                ORDER BY tc.constraint_name
                """
            )

            if not rows:
                logger.warning("  ⚠ No UNIQUE constraints found")
                logger.info("")
                return

            logger.info(f"  Found {len(rows)} UNIQUE constraint(s):")
            logger.info("")

            for row in rows:
                constraint_name = row['constraint_name']
                columns = row['columns']
                logger.info(f"  • {constraint_name}")
                logger.info(f"    Columns: ({columns})")
                logger.info("")

            # Try to identify the idempotency constraint
            logger.info("  📌 IDEMPOTENCY CONTRACT DETECTION:")
            for row in rows:
                columns = row['columns']
                if 'source_system' in columns and 'source_record_id' in columns:
                    if 'source_version' in columns:
                        logger.info(f"    ✓ LIVE IDEMPOTENCY KEY: (source_system, source_record_id, source_version)")
                    elif 'ingestion_version' in columns:
                        logger.info(f"    ✓ LIVE IDEMPOTENCY KEY: (source_system, source_record_id, ingestion_version)")
                    else:
                        logger.info(f"    ✓ LIVE IDEMPOTENCY KEY: ({columns})")
            logger.info("")

    async def _inspect_indexes(self):
        """Query indexes on raw.raw_event"""
        logger.info("3. RAW.RAW_EVENT INDEXES")
        logger.info("-" * 80)

        async with self.postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                  indexname,
                  indexdef
                FROM pg_indexes
                WHERE schemaname = 'raw'
                  AND tablename = 'raw_event'
                ORDER BY indexname
                """
            )

            if not rows:
                logger.info("  ℹ No indexes found (unlikely)")
                logger.info("")
                return

            logger.info(f"  Found {len(rows)} index(es):")
            logger.info("")

            for row in rows:
                index_name = row['indexname']
                index_def = row['indexdef']
                logger.info(f"  • {index_name}")
                logger.info(f"    {index_def}")
                logger.info("")

    async def _sample_baseline_rows(self):
        """Sample 5 baseline rows to see what columns are populated"""
        logger.info("4. BASELINE SAMPLE (5 rows)")
        logger.info("-" * 80)

        async with self.postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                  source_system,
                  source_record_id,
                  source_version,
                  ingestion_version,
                  event_type,
                  occurred_at,
                  arrival_at
                FROM raw.raw_event
                LIMIT 5
                """
            )

            if not rows:
                logger.warning("  ⚠ raw.raw_event is empty")
                logger.info("")
                return

            logger.info(f"  Sample of {len(rows)} row(s):")
            logger.info("")

            for idx, row in enumerate(rows, 1):
                logger.info(f"  Row {idx}:")
                for key, value in row.items():
                    logger.info(f"    {key:25s}: {value}")
                logger.info("")

    async def _count_baseline(self):
        """Count baseline records"""
        logger.info("5. BASELINE COUNT")
        logger.info("-" * 80)

        async with self.postgres_pool.acquire() as conn:
            count = await conn.fetchval(
                'SELECT COUNT(*) FROM raw.raw_event'
            )

            logger.info(f"  SELECT COUNT(*) FROM raw.raw_event: {count}")
            logger.info(f"  Expected baseline: 169")

            if count == 169:
                logger.info(f"  ✓ MATCH - Baseline count is correct")
            elif count < 169:
                logger.warning(f"  ⚠ LOW - Baseline count is less than expected")
            else:
                logger.warning(f"  ⚠ HIGH - Baseline count is more than expected")

            logger.info("")


async def main():
    task = LiveSchemaInspector()
    exit_code = await task.main()
    sys.exit(exit_code)


if __name__ == '__main__':
    asyncio.run(main())
