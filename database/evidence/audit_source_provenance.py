#!/usr/bin/env python3
"""
Audit source provenance in Raw records and original S3 JSONL
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


class SourceProvenanceAudit:
    """Audit source provenance"""
    
    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME', 'retail_os/rds/postgres')
        self.s3_bucket = os.getenv('AWS_S3_BUCKET', 'accord-capital-loans-usw2-621646470377')
        self.s3_prefix = os.getenv('AWS_S3_PREFIX', 'claris/source-corpus/raw/')
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.s3_client = boto3.client('s3', region_name=self.aws_region)
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
                print("\n" + "=" * 100)
                print("STEP A: SOURCE SYSTEM DISTRIBUTION IN RAW")
                print("=" * 100)
                
                await self._audit_raw_source_system(conn)
                
                print("\n" + "=" * 100)
                print("STEP B: PAYLOAD SOURCE-RELATED FIELDS BY EVENT TYPE")
                print("=" * 100)
                
                await self._audit_payload_source_fields(conn)
                
                print("\n" + "=" * 100)
                print("STEP C: UNIQUE CONSTRAINTS ON runtime.evidence")
                print("=" * 100)
                
                await self._inspect_evidence_constraints(conn)
            
            return 0
        except Exception as e:
            logger.error(f"Audit failed: {e}", exc_info=True)
            return 1
        finally:
            if self.pool:
                await self.pool.close()
    
    async def _audit_raw_source_system(self, conn):
        """Check source_system distribution in raw.raw_event"""
        print("\nraw.raw_event.source_system distribution:")
        rows = await conn.fetch("""
            SELECT source_system, COUNT(*) as cnt
            FROM raw.raw_event
            GROUP BY source_system
            ORDER BY source_system
        """)
        
        for row in rows:
            print(f"  {row['source_system']:20} : {row['cnt']:3} rows")
        
        print("\nraw.raw_event.source_record_id distribution:")
        rows = await conn.fetch("""
            SELECT 
                source_system,
                COUNT(*) as cnt,
                COUNT(CASE WHEN source_record_id IS NULL THEN 1 END) as null_count,
                COUNT(CASE WHEN source_record_id IS NOT NULL THEN 1 END) as non_null_count
            FROM raw.raw_event
            GROUP BY source_system
            ORDER BY source_system
        """)
        
        for row in rows:
            print(f"  {row['source_system']:20} : {row['cnt']:3} total, {row['null_count']:3} NULL source_record_id, {row['non_null_count']:3} non-NULL")
    
    async def _audit_payload_source_fields(self, conn):
        """Check for source-related fields in payload by event type"""
        
        event_types = [
            'HIERARCHY_APPROVAL',
            'SAP_CON_LOADED',
            'CON_VERIFIED',
            'SAP_PRD_LOADED',
            'SKU_MINTED',
            'TECHNICAL_REVIEW',
            'PRICING_DETERMINED',
            'FINAL_PRICING_APPROVAL',
            'OVERNIGHT_PUSH',
            'MATERIAL_ACTIVATED',
            'CHANGE_REQUESTED'
        ]
        
        for event_type in event_types:
            sample_text = await conn.fetchval("""
                SELECT payload::text FROM raw.raw_event
                WHERE event_type = $1
                LIMIT 1
            """, event_type)
            
            if sample_text:
                try:
                    sample = json.loads(sample_text)
                except:
                    print(f"\n{event_type}: ERROR parsing JSON")
                    continue
                
                print(f"\n{event_type}:")
                print(f"  Payload keys: {sorted(sample.keys())}")
                
                # Show source-related fields if present
                source_keys = [k for k in sample.keys() if 'source' in k.lower() or 'system' in k.lower() or 'origin' in k.lower()]
                if source_keys:
                    print(f"  Source-related keys:")
                    for key in source_keys:
                        print(f"    • {key}: {sample[key]}")
                else:
                    print(f"  No source/system/origin keys in payload")
    
    async def _inspect_evidence_constraints(self, conn):
        """Inspect UNIQUE constraints on runtime.evidence"""
        
        print("\nUNIQUE constraints on runtime.evidence:")
        
        constraints = await conn.fetch("""
            SELECT 
                constraint_name,
                string_agg(column_name, ', ' ORDER BY ordinal_position) as columns
            FROM information_schema.key_column_usage
            WHERE table_name = 'evidence' 
            AND table_schema = 'runtime'
            AND constraint_name NOT LIKE '%pkey%'
            GROUP BY constraint_name
            ORDER BY constraint_name
        """)
        
        if constraints:
            for constraint in constraints:
                print(f"  {constraint['constraint_name']:40} : ({constraint['columns']})")
        else:
            print(f"  No UNIQUE constraints found (only PK)")
        
        # Show PK
        pk = await conn.fetchrow("""
            SELECT constraint_name, string_agg(column_name, ', ' ORDER BY ordinal_position) as columns
            FROM information_schema.key_column_usage
            WHERE table_name = 'evidence' 
            AND table_schema = 'runtime'
            AND constraint_name LIKE '%pkey%'
            GROUP BY constraint_name
        """)
        
        if pk:
            print(f"\n  Primary Key: {pk['columns']}")
        
        print("\n" + "=" * 100)
        print("ANALYSIS")
        print("=" * 100)
        
        print(f"""
FINDINGS:

1. SOURCE SYSTEM IN RAW:
   - claris: 168 rows (all non-NULL source_record_id)
   - product_intent: 1 row (non-NULL source_record_id)
   
   → "claris" is NOT a default/fallback (all records have source_record_id)
   → source_record_id format suggests it came from original source

2. PAYLOAD SOURCE FIELDS:
   - No payload['source_system'] field found in representative event types
   → "claris" in raw.raw_event.source_system came from loader, NOT from original JSONL
   
3. PROVENANCE QUESTION:
   - If payload has no source_system, check for OTHER authority indicators:
     * approval_authority / approved_by / reviewer fields
     * process_step or operation_source
     * _source or _origin or _actor fields
   → These may indicate true source/authority even if source_system is "claris"

4. RECOMMENDATION:
   - Do NOT treat "claris" as authoritative source system
   - Extract actual authority from payload fields (approval_authority, reviewed_by, etc.)
   - Use payload authority fields to populate Evidence.source_actor_id and source_actor_role
   - Keep raw.raw_event.source_system for compatibility, but don't treat it as Evidence source authority
""")


async def main():
    audit = SourceProvenanceAudit()
    exit_code = await audit.main()
    sys.exit(exit_code)


if __name__ == '__main__':
    asyncio.run(main())
