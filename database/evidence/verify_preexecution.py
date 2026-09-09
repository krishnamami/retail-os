#!/usr/bin/env python3
"""
STEP 5E.3A Pre-Execution Verification (Corrected Nested Paths)
READ-ONLY: Verifies database state before Evidence insertion
No database writes
"""

import asyncio
import json
import sys
from typing import Dict, Any

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


async def verify_preexecution():
    """Verify pre-execution database state"""
    credentials = get_postgres_credentials()
    db_user = credentials.get('username')
    expected_user = "claris_ingestion"
    
    print("="*80)
    print("STEP 5E.3A — PRE-EXECUTION VERIFICATION")
    print("="*80)
    
    print(f"\nConnecting as: {db_user}")
    
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
        
        print("✓ Connected to accord database")
        
        # Verify connection state
        current_db = await conn.fetchval("SELECT current_database();")
        current_user = await conn.fetchval("SELECT current_user;")
        session_user = await conn.fetchval("SELECT session_user;")
        
        print(f"\nConnection State:")
        print(f"  current_database: {current_db}")
        print(f"  current_user: {current_user}")
        print(f"  session_user: {session_user}")
        
        # Verify database
        if current_db != 'accord':
            print(f"✗ ERROR: Expected database 'accord', got '{current_db}'")
            await conn.close()
            return False
        
        print(f"\n✓ Database correct: accord")
        
        # Verify role
        if current_user != expected_user:
            print(f"✗ ERROR: Expected user '{expected_user}', got '{current_user}'")
            await conn.close()
            return False
        
        print(f"✓ Connected user: {current_user}")
        
        # Verify baseline counts
        print("\nBaseline Counts:")
        raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event;")
        evidence_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
        assertion_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")
        fold_count = await conn.fetchval("SELECT COUNT(*) FROM state.fold_state_snapshot;")
        
        print(f"  raw.raw_event: {raw_count}")
        print(f"  runtime.evidence: {evidence_count}")
        print(f"  runtime.assertion: {assertion_count}")
        print(f"  state.fold_state_snapshot: {fold_count}")
        
        # Verify prototype records
        print("\nPrototype Record Verification:")
        
        # Count PRODUCT_DEFINED
        product_defined_count = await conn.fetchval(
            "SELECT COUNT(*) FROM raw.raw_event WHERE event_type = 'PRODUCT_DEFINED';"
        )
        print(f"  PRODUCT_DEFINED events: {product_defined_count}")
        
        # Count CONFIGURATION_REQUESTED
        config_requested_count = await conn.fetchval(
            "SELECT COUNT(*) FROM raw.raw_event WHERE event_type = 'CONFIGURATION_REQUESTED';"
        )
        print(f"  CONFIGURATION_REQUESTED events: {config_requested_count}")
        
        # Count prototype markers (in nested payload)
        prototype_count = await conn.fetchval(
            "SELECT COUNT(*) FROM raw.raw_event WHERE payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION';"
        )
        print(f"  PROTOTYPE_ASSUMPTION events (outer): {prototype_count}")
        
        # Count nested PROTOTYPE_ASSUMPTION in configuration payload
        nested_prototype = await conn.fetchval(
            "SELECT COUNT(*) FROM raw.raw_event WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION';"
        )
        print(f"  PROTOTYPE_ASSUMPTION in nested payload: {nested_prototype}")
        
        # Verify S7 null segment (in nested payload)
        s7_check = await conn.fetchval(
            "SELECT COUNT(*) FROM raw.raw_event WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'segment' IS NULL;"
        )
        print(f"  S7 events (nested segment IS NULL): {s7_check}")
        
        # Verify configuration_request_id is in nested payload
        config_req_check = await conn.fetchval(
            "SELECT COUNT(*) FROM raw.raw_event WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'configuration_request_id' IS NOT NULL;"
        )
        print(f"  CONFIGURATION_REQUESTED with nested configuration_request_id: {config_req_check}")
        
        await conn.close()
        
        print("\n" + "="*80)
        print("✓ PRE-EXECUTION VERIFICATION PASSED")
        print("="*80)
        print("\nDatabase is ready for Evidence insertion.")
        print("Run execute_evidence_sql.py to proceed.")
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        return False


if __name__ == '__main__':
    success = asyncio.run(verify_preexecution())
    sys.exit(0 if success else 1)
