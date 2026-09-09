#!/usr/bin/env python3
"""
STEP 5E.3A Prototype Raw Input Validation (Corrected Nested Paths)
READ-ONLY: Verifies 8 prototype Raw records before Evidence insertion
No database writes
"""

import asyncio
import json
import sys
from typing import Dict, Any, List

import asyncpg
import boto3
from botocore.exceptions import ClientError


def get_postgres_credentials() -> Dict[str, Any]:
    """Retrieve PostgreSQL credentials from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
        return json.loads(response['SecretString'])
    except ClientError as e:
        print(f"✗ ERROR retrieving Secrets Manager: {str(e)}")
        sys.exit(1)


async def verify_prototype_input():
    """Verify 8 prototype Raw records"""
    credentials = get_postgres_credentials()
    
    print("="*80)
    print("STEP 5E.3A — PROTOTYPE RAW INPUT VALIDATION")
    print("="*80)
    
    try:
        conn = await asyncpg.connect(
            host=credentials['host'],
            port=credentials['port'],
            user=credentials['username'],
            password=credentials['password'],
            database=credentials['dbname'],
            timeout=30.0,
            command_timeout=30.0,
        )
        
        print("\nVerifying 8 Prototype Records:")
        print("-" * 80)
        
        # Query all prototype records
        prototype_query = """
            SELECT 
                raw_event_id,
                event_type,
                source_record_id,
                payload->'payload'->>'configuration_request_id' as config_req_id,
                payload->'payload'->>'product_id' as product_id,
                payload->'payload'->>'launch_id' as launch_id,
                payload->'payload'->>'geo' as geo,
                payload->'payload'->>'term' as term,
                payload->'payload'->>'segment' as segment
            FROM raw.raw_event
            WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
            ORDER BY event_type, source_record_id;
        """
        
        records = await conn.fetch(prototype_query)
        print(f"\nTotal prototype records found: {len(records)}")
        
        if len(records) != 8:
            print(f"✗ ERROR: Expected 8 records, got {len(records)}")
            await conn.close()
            return False
        
        # Group by event type
        product_defined = [r for r in records if r['event_type'] == 'PRODUCT_DEFINED']
        config_requested = [r for r in records if r['event_type'] == 'CONFIGURATION_REQUESTED']
        
        print(f"\n  PRODUCT_DEFINED: {len(product_defined)}")
        print(f"  CONFIGURATION_REQUESTED: {len(config_requested)}")
        
        if len(product_defined) != 1 or len(config_requested) != 7:
            print(f"✗ ERROR: Expected 1 PRODUCT_DEFINED and 7 CONFIGURATION_REQUESTED")
            await conn.close()
            return False
        
        # Validate CONFIGURATION_REQUESTED records
        print("\nCONFIGURATION_REQUESTED Records:")
        print("-" * 80)
        
        for rec in config_requested:
            print(f"\n  {rec['source_record_id']}")
            print(f"    config_request_id: {rec['config_req_id']}")
            print(f"    product_id: {rec['product_id']}")
            print(f"    geo: {rec['geo']}")
            print(f"    term: {rec['term']}")
            print(f"    segment: {rec['segment']}")
        
        # Validate S6 (CONFIG_REQ_2026_005 and 006)
        print("\nS6 Business Duplicate Validation:")
        print("-" * 80)
        
        s6_records = [r for r in config_requested if r['source_record_id'] in ('CONFIG_REQ_2026_005', 'CONFIG_REQ_2026_006')]
        
        if len(s6_records) != 2:
            print(f"✗ ERROR: Expected 2 S6 records, got {len(s6_records)}")
            await conn.close()
            return False
        
        s6a = s6_records[0]
        s6b = s6_records[1]
        
        # Verify distinct raw_event_id
        if s6a['raw_event_id'] == s6b['raw_event_id']:
            print(f"✗ ERROR: S6a and S6b have same raw_event_id")
            await conn.close()
            return False
        print(f"✓ S6a raw_event_id: {s6a['raw_event_id']}")
        print(f"✓ S6b raw_event_id: {s6b['raw_event_id']}")
        
        # Verify distinct configuration_request_id
        if s6a['config_req_id'] == s6b['config_req_id']:
            print(f"✗ ERROR: S6a and S6b have same configuration_request_id")
            await conn.close()
            return False
        print(f"✓ S6a config_request_id: {s6a['config_req_id']}")
        print(f"✓ S6b config_request_id: {s6b['config_req_id']}")
        
        # Verify same business dimensions
        if (s6a['product_id'] != s6b['product_id'] or
            s6a['geo'] != s6b['geo'] or
            s6a['term'] != s6b['term'] or
            s6a['segment'] != s6b['segment']):
            print(f"✗ ERROR: S6a and S6b have different business dimensions")
            await conn.close()
            return False
        
        print(f"✓ Same product_id: {s6a['product_id']}")
        print(f"✓ Same geo: {s6a['geo']}")
        print(f"✓ Same term: {s6a['term']}")
        print(f"✓ Same segment: {s6a['segment']}")
        
        # Validate S7 (CONFIG_REQ_2026_007)
        print("\nS7 Incomplete Identity Validation:")
        print("-" * 80)
        
        s7_records = [r for r in config_requested if r['source_record_id'] == 'CONFIG_REQ_2026_007']
        
        if len(s7_records) != 1:
            print(f"✗ ERROR: Expected 1 S7 record, got {len(s7_records)}")
            await conn.close()
            return False
        
        s7 = s7_records[0]
        
        if s7['segment'] is not None:
            print(f"✗ ERROR: S7 segment should be NULL, got {s7['segment']}")
            await conn.close()
            return False
        
        print(f"✓ S7 has NULL segment")
        print(f"  config_request_id: {s7['config_req_id']}")
        print(f"  product_id: {s7['product_id']}")
        print(f"  geo: {s7['geo']}")
        print(f"  term: {s7['term']}")
        
        await conn.close()
        
        print("\n" + "="*80)
        print("✓ PROTOTYPE RAW INPUT VALIDATION PASSED")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        return False


if __name__ == '__main__':
    success = asyncio.run(verify_prototype_input())
    sys.exit(0 if success else 1)
