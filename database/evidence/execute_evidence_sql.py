#!/usr/bin/env python3
"""
STEP 5E.3A Execute Evidence SQL
AUTHORIZED TO WRITE: Executes database/evidence/raw_to_evidence_prototype_mappings.sql
Transactional execution with rollback on error
"""

import asyncio
import json
import os
import sys
from pathlib import Path
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
        print(f"✗ ERROR: Could not retrieve credentials: {str(e)}")
        sys.exit(1)


def get_sql_file_path() -> Path:
    """Resolve the authoritative SQL file path"""
    # Get the directory of this script
    script_dir = Path(__file__).parent
    sql_file = script_dir / 'raw_to_evidence_prototype_mappings.sql'
    
    if not sql_file.exists():
        print(f"✗ ERROR: SQL file not found: {sql_file}")
        sys.exit(1)
    
    return sql_file


def read_sql_file(sql_file: Path) -> str:
    """Read SQL from authoritative file"""
    try:
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        print(f"✓ SQL file loaded: {sql_file}")
        return sql_content
    except IOError as e:
        print(f"✗ ERROR: Could not read SQL file: {str(e)}")
        sys.exit(1)


async def execute_evidence_sql():
    """Execute Evidence SQL transactionally"""
    credentials = get_postgres_credentials()
    sql_file = get_sql_file_path()
    sql_content = read_sql_file(sql_file)

    pool = None
    try:
        pool = await asyncpg.create_pool(
            host=credentials['host'],
            port=credentials['port'],
            user=credentials['username'],
            password=credentials['password'],
            database=credentials['dbname'],
            timeout=30.0,
            command_timeout=30.0,
        )

        print("\n" + "="*80)
        print("STEP 5E.3 EVIDENCE INSERTION (IDEMPOTENT)")
        print("="*80)

        # Get pre-execution count
        async with pool.acquire() as conn:
            pre_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
            print(f"\nEvidence count before execution: {pre_count}")

        # Determine expected behavior based on pre_count
        if pre_count == 107:
            expected_inserts = 36
            expected_final = 143
            run_label = "RUN 1"
        elif pre_count == 143:
            expected_inserts = 0
            expected_final = 143
            run_label = "RUN 2 (Idempotent Replay)"
        else:
            print(f"✗ ERROR: Unexpected pre-execution count {pre_count}")
            print("Must be 107 (Run 1) or 143 (Run 2)")
            return False

        print(f"Execution mode: {run_label}")
        print(f"Expected new inserts: {expected_inserts}")

        # Execute SQL transactionally
        print(f"Executing SQL from {sql_file.name}...")

        try:
            async with pool.acquire() as conn:
                await conn.execute(sql_content)
                print("✓ SQL executed successfully")
        except Exception as sql_error:
            print(f"✗ SQL execution failed: {str(sql_error)}")
            print("Transaction rolled back - no data written")
            return False

        # Get post-execution count
        async with pool.acquire() as conn:
            post_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
            print(f"Evidence count after execution: {post_count}")

        new_inserts = post_count - pre_count
        print(f"New Evidence rows inserted: {new_inserts}")

        # Validate result
        print("\n" + "-"*80)
        if new_inserts == expected_inserts and post_count == expected_final:
            print(f"✓ CORRECT: {new_inserts} new rows inserted (expected: {expected_inserts})")
            print(f"✓ Final count: {post_count} (expected: {expected_final})")
            result = True
        else:
            print(f"✗ ERROR: Expected {expected_inserts} inserts, got {new_inserts}")
            print(f"✗ ERROR: Expected final {expected_final}, got {post_count}")
            result = False

        return result

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        return False
    finally:
        if pool:
            await pool.close()


if __name__ == '__main__':
    success = asyncio.run(execute_evidence_sql())
    sys.exit(0 if success else 1)
