#!/usr/bin/env python3
"""
STEP 5E.3B — Role / Privilege Diagnosis (READ-ONLY)
Must be run on Windows with configured AWS credentials
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


async def run_diagnosis():
    """Run READ-ONLY privilege diagnosis"""
    
    print("="*80)
    print("STEP 5E.3B — ROLE / PRIVILEGE VERIFICATION (READ-ONLY)")
    print("="*80)
    
    # Get credentials
    credentials = get_postgres_credentials()
    resolved_username = credentials.get('username')
    
    print(f"\n1. RESOLVED SECRETS MANAGER USERNAME: {resolved_username}")
    
    try:
        # Connect
        conn = await asyncpg.connect(
            host=credentials['host'],
            port=credentials['port'],
            user=credentials['username'],
            password=credentials['password'],
            database=credentials['dbname'],
            timeout=30.0,
            command_timeout=30.0,
        )
        
        # Query 1: Connection info
        print("\n2-4. CONNECTION STATE:")
        current_db = await conn.fetchval("SELECT current_database();")
        current_user_result = await conn.fetchval("SELECT current_user;")
        session_user_result = await conn.fetchval("SELECT session_user;")
        
        print(f"   current_database: {current_db}")
        print(f"   current_user: {current_user_result}")
        print(f"   session_user: {session_user_result}")
        
        # Query 2: Schema privileges
        print("\n5-7. SCHEMA PRIVILEGES:")
        raw_usage = await conn.fetchval(f"SELECT has_schema_privilege('{resolved_username}', 'raw', 'USAGE');")
        runtime_usage = await conn.fetchval(f"SELECT has_schema_privilege('{resolved_username}', 'runtime', 'USAGE');")
        state_usage = await conn.fetchval(f"SELECT has_schema_privilege('{resolved_username}', 'state', 'USAGE');")
        
        print(f"   raw schema USAGE: {'YES' if raw_usage else 'NO'}")
        print(f"   runtime schema USAGE: {'YES' if runtime_usage else 'NO'}")
        print(f"   state schema USAGE: {'YES' if state_usage else 'NO'}")
        
        # Query 3: Table privileges
        print("\n8-12. TABLE PRIVILEGES:")
        raw_event_select = await conn.fetchval(f"SELECT has_table_privilege('{resolved_username}', 'raw.raw_event', 'SELECT');")
        evidence_select = await conn.fetchval(f"SELECT has_table_privilege('{resolved_username}', 'runtime.evidence', 'SELECT');")
        evidence_insert = await conn.fetchval(f"SELECT has_table_privilege('{resolved_username}', 'runtime.evidence', 'INSERT');")
        assertion_select = await conn.fetchval(f"SELECT has_table_privilege('{resolved_username}', 'runtime.assertion', 'SELECT');")
        fold_select = await conn.fetchval(f"SELECT has_table_privilege('{resolved_username}', 'state.fold_state_snapshot', 'SELECT');")
        
        print(f"   raw.raw_event SELECT: {'YES' if raw_event_select else 'NO'}")
        print(f"   runtime.evidence SELECT: {'YES' if evidence_select else 'NO'}")
        print(f"   runtime.evidence INSERT: {'YES' if evidence_insert else 'NO'}")
        print(f"   runtime.assertion SELECT: {'YES' if assertion_select else 'NO'}")
        print(f"   state.fold_state_snapshot SELECT: {'YES' if fold_select else 'NO'}")
        
        # Query 4: Sequence privileges
        print("\n13. SEQUENCE PRIVILEGES:")
        try:
            seq_query = """
                SELECT EXISTS(
                    SELECT 1 FROM pg_class 
                    WHERE relname = 'evidence_id_seq' 
                    AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'runtime')
                );
            """
            seq_check = await conn.fetchval(seq_query)
            if seq_check:
                print(f"   Evidence ID sequence found")
                seq_usage = await conn.fetchval(f"SELECT has_sequence_privilege('{resolved_username}', 'runtime.evidence_id_seq', 'USAGE');")
                print(f"   Sequence USAGE privilege: {'YES' if seq_usage else 'NO'}")
            else:
                print(f"   No sequence found (identity column may be auto-managed)")
        except Exception as e:
            print(f"   Sequence check: {str(e)}")
        
        # Query 5: Live counts
        print("\n14-17. LIVE COUNTS:")
        raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event;")
        evidence_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
        assertion_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")
        fold_count = await conn.fetchval("SELECT COUNT(*) FROM state.fold_state_snapshot;")
        
        print(f"   raw.raw_event: {raw_count} (expected 177)")
        print(f"   runtime.evidence: {evidence_count} (expected 107)")
        print(f"   runtime.assertion: {assertion_count} (expected 107)")
        print(f"   state.fold_state_snapshot: {fold_count} (expected 51)")
        
        # Query 6: ON CONFLICT capability
        print("\n18. ON CONFLICT (raw_event_id, mapping_id) DO NOTHING:")
        print(f"   Requires: INSERT privilege = {evidence_insert}")
        print(f"   DO NOTHING variant requires: NO UPDATE privilege")
        print(f"   Foreign key checks: read-only, no privilege required")
        
        await conn.close()
        
        # Summary
        print("\n" + "="*80)
        print("PRIVILEGE SUMMARY:")
        print("="*80)
        
        all_required = (
            raw_usage and runtime_usage and state_usage and
            raw_event_select and evidence_select and evidence_insert and 
            assertion_select and fold_select
        )
        
        if all_required:
            print("\n✓ STEP 5E.3B ROLE VERIFIED — claris_ingestion HAS ALL REQUIRED PRIVILEGES")
            print("\nclaris_ingestion can safely execute STEP 5E.3 Evidence insertion:")
            print("  - SELECT from raw.raw_event ✓")
            print("  - SELECT from runtime.evidence ✓")
            print("  - INSERT into runtime.evidence ✓")
            print("  - SELECT from runtime.assertion ✓")
            print("  - SELECT from state.fold_state_snapshot ✓")
            print("  - ON CONFLICT DO NOTHING pattern supported ✓")
            
            print("\n19. NO DATABASE WRITES: ✓ Diagnosis is READ-ONLY")
            print("20. NO SECURITY CHANGES: ✓ No grants, revokes, or role changes")
            return True
        else:
            print("\n✗ STEP 5E.3B ROLE BLOCKED — MISSING PRIVILEGES:")
            if not evidence_insert:
                print("  - Missing: INSERT on runtime.evidence")
            if not raw_event_select:
                print("  - Missing: SELECT on raw.raw_event")
            if not assertion_select:
                print("  - Missing: SELECT on runtime.assertion")
            if not raw_usage or not runtime_usage or not state_usage:
                print("  - Missing: schema USAGE privilege")
            
            print("\nDO NOT EXECUTE EVIDENCE SQL")
            print("\n19. NO DATABASE WRITES: ✓ Diagnosis is READ-ONLY")
            print("20. NO SECURITY CHANGES: ✓ No grants, revokes, or role changes")
            return False
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        print("\n19. NO DATABASE WRITES: ✓ Diagnosis is READ-ONLY")
        print("20. NO SECURITY CHANGES: ✓ No grants, revokes, or role changes")
        return False


if __name__ == '__main__':
    success = asyncio.run(run_diagnosis())
    sys.exit(0 if success else 1)
