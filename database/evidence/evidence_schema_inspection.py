#!/usr/bin/env python3
"""
Inspect runtime.evidence schema - FIXED version
"""

import asyncio
import json
import logging
import os
import sys

import asyncpg
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EvidenceSchemaInspector:
    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME', 'retail_os/rds/postgres')
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.postgres_pool = None

    async def main(self):
        try:
            logger.info("=" * 70)
            logger.info("EVIDENCE SCHEMA INSPECTION")
            logger.info("=" * 70)
            credentials = self._get_postgres_credentials()
            self.postgres_pool = await asyncpg.create_pool(
                host=credentials['host'], port=credentials['port'],
                user=credentials['username'], password=credentials['password'],
                database=credentials['dbname'], min_size=1, max_size=3,
            )
            await self._inspect_evidence_schema()
            logger.info("\n" + "=" * 70)
            logger.info("✓ INSPECTION COMPLETE")
            logger.info("=" * 70)
            return 0
        except Exception as e:
            logger.error(f"Inspection failed: {e}", exc_info=True)
            return 1
        finally:
            if self.postgres_pool:
                await self.postgres_pool.close()

    def _get_postgres_credentials(self):
        try:
            response = self.secrets_client.get_secret_value(SecretId=self.postgres_secret_name)
            return json.loads(response['SecretString'])
        except ClientError as e:
            logger.error(f"Failed to retrieve secret: {e}")
            sys.exit(1)

    async def _inspect_evidence_schema(self):
        async with self.postgres_pool.acquire() as conn:
            # Columns
            logger.info("\n📋 EVIDENCE COLUMNS:")
            columns = await conn.fetch(
                "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'runtime' AND table_name = 'evidence' ORDER BY ordinal_position"
            )
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default_str = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                logger.info(f"  {col['column_name']}: {col['data_type']} {nullable}{default_str}")

            mapping_id_exists = any(col['column_name'] == 'mapping_id' for col in columns)
            logger.info(f"\n🔍 mapping_id EXISTS: {mapping_id_exists}")
            logger.info(f"   Total columns: {len(columns)}")

            # Primary key
            logger.info("\n🔑 PRIMARY KEY:")
            pk = await conn.fetch(
                "SELECT constraint_name, column_name FROM information_schema.key_column_usage WHERE table_schema = 'runtime' AND table_name = 'evidence' AND constraint_name LIKE '%pkey'"
            )
            for row in pk:
                logger.info(f"  {row['constraint_name']}: {row['column_name']}")

            # UNIQUE constraints
            logger.info("\n🔐 UNIQUE CONSTRAINTS:")
            constraint_details = await conn.fetch(
                """SELECT c.conname as constraint_name, string_agg(a.attname, ', ' ORDER BY a.attnum) as columns
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON t.relnamespace = n.oid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
                WHERE n.nspname = 'runtime' AND t.relname = 'evidence' AND c.contype = 'u'
                GROUP BY c.conname ORDER BY c.conname"""
            )

            if constraint_details:
                for cd in constraint_details:
                    logger.info(f"  {cd['constraint_name']}: ({cd['columns']})")
                    if cd['columns'] and 'subject_type' in cd['columns'] and 'arrival_at' in cd['columns']:
                        logger.warning(f"\n  ⚠️  MUST DROP THIS ONE: {cd['constraint_name']}")
                        logger.warning(f"      Columns: ({cd['columns']})")
            else:
                logger.info("  (no unique constraints found)")

            # Foreign keys
            logger.info("\n🔗 FOREIGN KEYS:")
            fks = await conn.fetch(
                "SELECT constraint_name, column_name FROM information_schema.key_column_usage WHERE table_schema = 'runtime' AND table_name = 'evidence' AND referenced_table_name IS NOT NULL"
            )
            for fk in fks:
                logger.info(f"  {fk['constraint_name']}: {fk['column_name']}")

            # Row count
            logger.info("\n📊 ROW COUNT:")
            count = await conn.fetchval('SELECT COUNT(*) FROM runtime.evidence')
            logger.info(f"  runtime.evidence: {count} rows")

async def main():
    inspector = EvidenceSchemaInspector()
    exit_code = await inspector.main()
    sys.exit(exit_code)

if __name__ == '__main__':
    asyncio.run(main())
