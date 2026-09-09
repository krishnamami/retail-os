#!/usr/bin/env python3
"""
Inspect Evidence and Raw schemas for Evidence mapping design
"""
import asyncio
import json
import logging
import os
import sys

import asyncpg
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SchemaInspector:
    """Inspect deployed schemas"""
    
    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME', 'retail_os/rds/postgres')
        self.postgres_db = os.getenv('POSTGRES_DB_NAME', 'accord')
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.pool = None
    
    def _get_postgres_credentials(self):
        try:
            response = self.secrets_client.get_secret_value(SecretId=self.postgres_secret_name)
            return json.loads(response['SecretString'])
        except ClientError as e:
            logger.error(f"Failed to retrieve secret: {e}")
            sys.exit(1)
    
    async def main(self):
        try:
            credentials = self._get_postgres_credentials()
            self.pool = await asyncpg.create_pool(
                host=credentials['host'],
                port=credentials['port'],
                user=credentials['username'],
                password=credentials['password'],
                database=credentials['dbname'],
                min_size=1,
                max_size=1,
            )
            
            async with self.pool.acquire() as conn:
                await self._inspect_evidence(conn)
                await self._inspect_raw_event(conn)
                await self._inspect_event_distribution(conn)
                await self._inspect_payloads(conn)
            
            return 0
        except Exception as e:
            logger.error(f"Inspection failed: {e}", exc_info=True)
            return 1
        finally:
            if self.pool:
                await self.pool.close()
    
    async def _inspect_evidence(self, conn):
        print("\n" + "=" * 90)
        print("1. RUNTIME.EVIDENCE SCHEMA")
        print("=" * 90)
        
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'runtime' AND table_name = 'evidence'
            ORDER BY ordinal_position
        """)
        
        print("\nCOLUMNS:")
        for col in cols:
            nullable = "✓" if col['is_nullable'] == 'YES' else "✗"
            default = col['column_default'] or ""
            print(f"  {col['column_name']:30} {col['data_type']:25} nullable={nullable}  default={default}")
        
        count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence")
        print(f"\nCurrent row count: {count}")
    
    async def _inspect_raw_event(self, conn):
        print("\n" + "=" * 90)
        print("2. RAW.RAW_EVENT SCHEMA")
        print("=" * 90)
        
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = 'raw_event'
            ORDER BY ordinal_position
        """)
        
        print("\nCOLUMNS:")
        for col in cols:
            nullable = "✓" if col['is_nullable'] == 'YES' else "✗"
            default = col['column_default'] or ""
            print(f"  {col['column_name']:30} {col['data_type']:25} nullable={nullable}  default={default}")
        
        count = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event")
        print(f"\nCurrent row count: {count}")
    
    async def _inspect_event_distribution(self, conn):
        print("\n" + "=" * 90)
        print("3. EVENT TYPE DISTRIBUTION")
        print("=" * 90)
        
        rows = await conn.fetch("""
            SELECT event_type, source_system, COUNT(*) as cnt
            FROM raw.raw_event
            GROUP BY event_type, source_system
            ORDER BY source_system, event_type
        """)
        
        for row in rows:
            print(f"  {row['event_type']:45} ({row['source_system']:20}): {row['cnt']:3} rows")
    
    async def _inspect_payloads(self, conn):
        print("\n" + "=" * 90)
        print("4. PAYLOAD STRUCTURE BY EVENT TYPE (sample record)")
        print("=" * 90)
        
        event_types = await conn.fetch("""
            SELECT DISTINCT event_type, source_system
            FROM raw.raw_event
            ORDER BY source_system, event_type
        """)
        
        for row in event_types:
            event_type = row['event_type']
            source_system = row['source_system']
            
            sample = await conn.fetchval("""
                SELECT payload::text FROM raw.raw_event 
                WHERE event_type = $1 AND source_system = $2
                LIMIT 1
            """, event_type, source_system)
            
            print(f"\n  [{source_system}] {event_type}:")
            if sample:
                try:
                    payload_dict = json.loads(sample)
                    for key in sorted(payload_dict.keys()):
                        val = payload_dict[key]
                        val_type = type(val).__name__
                        val_str = str(val)[:70]
                        print(f"    • {key:35} ({val_type:10}): {val_str}")
                except Exception as e:
                    print(f"    ERROR parsing payload: {e}")


async def main():
    inspector = SchemaInspector()
    exit_code = await inspector.main()
    sys.exit(exit_code)


if __name__ == '__main__':
    asyncio.run(main())
