#!/usr/bin/env python3
"""
RAW Verification Script
Post-load verification and idempotency testing
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


class RawVerification:
    """Verification orchestrator"""

    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME', 'retail_os/rds/postgres')
        self.postgres_db = os.getenv('POSTGRES_DB_NAME', 'claris')
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.postgres_pool = None

    async def main(self):
        """Main verification"""
        try:
            logger.info("=" * 70)
            logger.info("RAW VERIFICATION")
            logger.info("=" * 70)

            # Get credentials and connect
            credentials = self._get_postgres_credentials()

            self.postgres_pool = await asyncpg.create_pool(
                host=credentials['host'],
                port=credentials['port'],
                user=credentials['username'],
                password=credentials['password'],
                database=credentials['dbname'],
                min_size=1,
                max_size=3,
            )

            # Run verification
            await self._verify_all()

            logger.info("\n" + "=" * 70)
            logger.info("✓ VERIFICATION COMPLETE")
            logger.info("=" * 70)

            return 0

        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)
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
            logger.error(f"Failed to retrieve secret: {e}")
            sys.exit(1)

    async def _verify_all(self):
        """Run all verification checks"""
        async with self.postgres_pool.acquire() as conn:
            # Row counts
            logger.info("\n📊 TABLE ROW COUNTS:")
            tables = [
                ('raw', 'raw_event'),
                ('runtime', 'evidence'),
                ('runtime', 'assertion'),
                ('state', 'fold_state_snapshot'),
                ('audit', 'ingestion_log'),
                ('audit', 'ingestion_file'),
            ]

            for schema, table in tables:
                count = await conn.fetchval(f'SELECT COUNT(*) FROM {schema}.{table}')
                logger.info(f"  {schema}.{table}: {count}")

            # Source system distribution
            logger.info("\n📈 SOURCE SYSTEM DISTRIBUTION:")
            distribution = await conn.fetch(
                'SELECT source_system, COUNT(*) as cnt FROM raw.raw_event GROUP BY source_system ORDER BY source_system'
            )
            for row in distribution:
                logger.info(f"  {row['source_system']}: {row['cnt']}")

            # NULL checks
            logger.info("\n❓ NULL VALUE CHECKS:")
            null_record_id = await conn.fetchval(
                'SELECT COUNT(*) FROM raw.raw_event WHERE source_record_id IS NULL'
            )
            null_system = await conn.fetchval(
                'SELECT COUNT(*) FROM raw.raw_event WHERE source_system IS NULL'
            )
            logger.info(f"  NULL source_record_id: {null_record_id}")
            logger.info(f"  NULL source_system: {null_system}")

            # Duplicate check
            logger.info("\n🔍 DUPLICATE IDENTITY CHECK:")
            duplicates = await conn.fetch(
                """
                SELECT source_system, source_record_id, source_version, COUNT(*) as cnt
                FROM raw.raw_event
                GROUP BY source_system, source_record_id, source_version
                HAVING COUNT(*) > 1
                """
            )
            if duplicates:
                logger.warning(f"  Found {len(duplicates)} duplicate identities:")
                for dup in duplicates:
                    logger.warning(f"    {dup['source_system']} / {dup['source_record_id']} / {dup['source_version']}: {dup['cnt']} rows")
            else:
                logger.info(f"  No duplicate identities found ✓")

            # Min/max arrival_at
            logger.info("\n📅 ARRIVAL TIME RANGE:")
            min_arrival = await conn.fetchval(
                'SELECT MIN(arrival_at) FROM raw.raw_event'
            )
            max_arrival = await conn.fetchval(
                'SELECT MAX(arrival_at) FROM raw.raw_event'
            )
            logger.info(f"  Min arrival_at: {min_arrival}")
            logger.info(f"  Max arrival_at: {max_arrival}")


async def main():
    task = RawVerification()
    exit_code = await task.main()
    sys.exit(exit_code)


if __name__ == '__main__':
    asyncio.run(main())
