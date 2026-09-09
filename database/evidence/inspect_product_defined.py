#!/usr/bin/env python3
"""
BLOCKER 1 — PRODUCT_DEFINED Raw Event Inspection (READ-ONLY)
Must run on Windows with AWS credentials configured
"""
import asyncio
import json
import sys
import boto3

async def inspect():
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
        creds = json.loads(response['SecretString'])
    except Exception as e:
        print(f"✗ AWS error: {e}")
        return False
    
    try:
        import asyncpg
        conn = await asyncpg.connect(
            host=creds['host'], port=creds['port'],
            user=creds['username'], password=creds['password'],
            database=creds['dbname'], timeout=30.0, command_timeout=30.0
        )
    except Exception as e:
        print(f"✗ DB error: {e}")
        return False
    
    print("="*80)
    print("BLOCKER 1 — PRODUCT_DEFINED Raw Event Inspection (READ-ONLY)")
    print("="*80)
    
    # Get the PRODUCT_DEFINED event with all details
    query = """
        SELECT 
            raw_event_id,
            source_record_id,
            launch_id,
            simulator_classification,
            payload
        FROM raw.raw_event
        WHERE event_type = 'PRODUCT_DEFINED'
        LIMIT 1;
    """
    
    record = await conn.fetchrow(query)
    
    if not record:
        print("✗ No PRODUCT_DEFINED event found")
        await conn.close()
        return False
    
    print(f"\nPhysical Columns:")
    print(f"  source_record_id: {record['source_record_id']}")
    print(f"  launch_id (column): {record['launch_id']}")
    print(f"  simulator_classification (column): {record['simulator_classification']}")
    
    # Get specific field locations
    specific_query = """
        SELECT 
            payload->>'product_id' as top_product_id,
            payload->>'product_name' as top_product_name,
            payload->>'launch_id' as top_launch_id,
            payload->'payload'->>'product_id' as nested_product_id,
            payload->'payload'->>'product_name' as nested_product_name,
            payload->'payload'->>'launch_id' as nested_launch_id
        FROM raw.raw_event
        WHERE event_type = 'PRODUCT_DEFINED'
        LIMIT 1;
    """
    
    specific = await conn.fetchrow(specific_query)
    
    print(f"\nField Location Analysis:")
    print(f"{'─'*80}")
    print(f"\nTop-level (r.payload->>...):")
    print(f"  product_id: {specific['top_product_id']}")
    print(f"  product_name: {specific['top_product_name']}")
    print(f"  launch_id: {specific['top_launch_id']}")
    
    print(f"\nNested (r.payload->'payload'->>...):")
    print(f"  product_id: {specific['nested_product_id']}")
    print(f"  product_name: {specific['nested_product_name']}")
    print(f"  launch_id: {specific['nested_launch_id']}")
    
    print(f"\n{'─'*80}")
    print(f"\nCOMPLETE payload JSON (raw.raw_event.payload):")
    print(f"{'─'*80}")
    payload = record['payload']
    print(json.dumps(payload, indent=2))
    
    # Determine location
    print(f"\n{'='*80}")
    print("RESOLUTION:")
    print(f"{'='*80}")
    
    if specific['top_product_name']:
        print(f"\n✓ product_name LOCATION: TOP-LEVEL")
        print(f"  Extraction path: r.payload->>'product_name'")
        print(f"  Value: {specific['top_product_name']}")
        location = "TOP"
    elif specific['nested_product_name']:
        print(f"\n✓ product_name LOCATION: NESTED")
        print(f"  Extraction path: r.payload->'payload'->>'product_name'")
        print(f"  Value: {specific['nested_product_name']}")
        location = "NESTED"
    else:
        print(f"\n✗ product_name NOT FOUND in either location")
        location = "NOT_FOUND"
    
    print(f"\nCORRECTION REQUIRED:")
    if location == "TOP":
        print(f"  SQL: r.payload->>'product_name'")
    elif location == "NESTED":
        print(f"  SQL: r.payload->'payload'->>'product_name'")
    
    await conn.close()
    return location != "NOT_FOUND"

if __name__ == '__main__':
    try:
        success = asyncio.run(inspect())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ ERROR: {e}")
        sys.exit(1)
