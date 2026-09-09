#!/usr/bin/env python3
"""
STEP 5F.1F FINAL ASSERTION GATE — READ-ONLY COMPREHENSIVE DIAGNOSTIC
Checks FK constraints, indexes, privileges, idempotency, and current state
"""

import asyncio
import json
import os
import re
import sys
from typing import Dict, Any

import asyncpg
import boto3


def get_postgres_credentials() -> Dict[str, Any]:
    secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
    response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
    return json.loads(response['SecretString'])


async def final_assertion_gate():
    """Comprehensive read-only diagnostic gate for Step 5F.1"""
    credentials = get_postgres_credentials()
    pool = None
    
    try:
        pool = await asyncpg.create_pool(
            host=credentials['host'],
            port=credentials['port'],
            user=credentials['username'],
            password=credentials['password'],
            database=credentials['dbname'],
            timeout=30.0,
        )

        async with pool.acquire() as conn:
            print("\n" + "="*80)
            print("STEP 5F.1F FINAL ASSERTION GATE — READ-ONLY DIAGNOSTIC")
            print("="*80)

            # 1. CURRENT DATABASE ROLE
            print("\n1. CURRENT DATABASE ROLE")
            print("-" * 80)

            role_info = await conn.fetchrow("""
                SELECT
                    current_database(),
                    current_user,
                    session_user;
            """)

            print(f"Current database: {role_info['current_database']}")
            print(f"Current user:     {role_info['current_user']}")
            print(f"Session user:     {role_info['session_user']}")

            # 2. FOREIGN KEYS ON runtime.assertion
            print("\n2. FOREIGN KEY CONSTRAINTS ON runtime.assertion")
            print("-" * 80)

            fks = await conn.fetch("""
                SELECT
                    con.conname AS constraint_name,
                    src_ns.nspname AS source_schema,
                    src.relname AS source_table,
                    src_att.attname AS source_column,
                    ref_ns.nspname AS referenced_schema,
                    ref.relname AS referenced_table,
                    ref_att.attname AS referenced_column
                FROM pg_constraint con
                JOIN pg_class src ON src.oid = con.conrelid
                JOIN pg_namespace src_ns ON src_ns.oid = src.relnamespace
                JOIN pg_class ref ON ref.oid = con.confrelid
                JOIN pg_namespace ref_ns ON ref_ns.oid = ref.relnamespace
                JOIN LATERAL unnest(con.conkey, con.confkey)
                  WITH ORDINALITY AS cols(src_attnum, ref_attnum, ord) ON TRUE
                JOIN pg_attribute src_att ON src_att.attrelid = con.conrelid AND src_att.attnum = cols.src_attnum
                JOIN pg_attribute ref_att ON ref_att.attrelid = con.confrelid AND ref_att.attnum = cols.ref_attnum
                WHERE con.contype = 'f'
                  AND src_ns.nspname = 'runtime'
                  AND src.relname = 'assertion'
                ORDER BY con.conname, cols.ord;
            """)

            if fks:
                for fk in fks:
                    print(f"\n  {fk['constraint_name']}")
                    print(f"    {fk['source_schema']}.{fk['source_table']}.{fk['source_column']}")
                    print(f"    →")
                    print(f"    {fk['referenced_schema']}.{fk['referenced_table']}.{fk['referenced_column']}")
                
                # Answer specific questions
                has_source_ev_fk = any(
                    fk['source_column'] == 'source_evidence_id' and
                    fk['referenced_table'] == 'evidence'
                    for fk in fks
                )
                has_supersedes_fk = any(
                    fk['source_column'] == 'supersedes_assertion_id' and
                    fk['referenced_table'] == 'assertion'
                    for fk in fks
                )
                
                print(f"\n✓ A. source_evidence_id → evidence.evidence_id FK: {has_source_ev_fk}")
                print(f"✓ B. supersedes_assertion_id → assertion.assertion_id FK: {has_supersedes_fk}")
            else:
                print("  No foreign keys found")
                print("\n✗ A. source_evidence_id → evidence.evidence_id FK: FALSE")
                print("✗ B. supersedes_assertion_id → assertion.assertion_id FK: FALSE")

            # 3. ALL INDEXES ON runtime.assertion
            print("\n3. ALL INDEXES ON runtime.assertion")
            print("-" * 80)

            indexes = await conn.fetch("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'runtime'
                  AND tablename = 'assertion'
                ORDER BY indexname;
            """)

            if indexes:
                for idx in indexes:
                    print(f"\n  {idx['indexname']}")
                    print(f"    {idx['indexdef']}")
            else:
                print("  No indexes found")

            # 4. INSERT PRIVILEGE
            print("\n4. INSERT AND SELECT PRIVILEGES")
            print("-" * 80)

            insert_priv = await conn.fetchval("""
                SELECT has_table_privilege(
                    current_user,
                    'runtime.assertion',
                    'INSERT'
                );
            """)

            select_priv = await conn.fetchval("""
                SELECT has_table_privilege(
                    current_user,
                    'runtime.assertion',
                    'SELECT'
                );
            """)

            print(f"INSERT privilege: {insert_priv}")
            print(f"SELECT privilege: {select_priv}")

            # 5. IDEMPOTENCY — DATABASE ENFORCEMENT
            print("\n5. DATABASE-LEVEL IDEMPOTENCY ENFORCEMENT")
            print("-" * 80)

            unique_constraints = await conn.fetch("""
                SELECT
                    tc.constraint_name,
                    string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                  AND tc.table_name = kcu.table_name
                WHERE tc.table_schema = 'runtime'
                  AND tc.table_name = 'assertion'
                  AND tc.constraint_type = 'UNIQUE'
                GROUP BY tc.constraint_name
                ORDER BY tc.constraint_name;
            """)

            print(f"UNIQUE constraints: {len(unique_constraints)}")
            if unique_constraints:
                for uc in unique_constraints:
                    print(f"  {uc['constraint_name']}: ({uc['columns']})")
                    # Check if any UNIQUE protects source_evidence_id
                    if 'source_evidence_id' in (uc['columns'] or ''):
                        print(f"    → Protects source_evidence_id idempotency")
            else:
                print("  No UNIQUE constraints")

            unique_indexes = await conn.fetch("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'runtime'
                  AND tablename = 'assertion'
                  AND indexdef LIKE '%UNIQUE%'
                ORDER BY indexname;
            """)

            print(f"\nUNIQUE indexes: {len(unique_indexes)}")
            if unique_indexes:
                for idx in unique_indexes:
                    print(f"  {idx['indexname']}")
                    print(f"    {idx['indexdef']}")

            # 6. IDEMPOTENCY — APPLICATION IMPLEMENTATION
            print("\n6. APPLICATION-LEVEL IDEMPOTENCY IMPLEMENTATION")
            print("-" * 80)
            print("Searching repository for Assertion creation/idempotency code...\n")

            search_patterns = [
                ('INSERT INTO runtime.assertion', 'INSERT statement'),
                ('ON CONFLICT', 'ON CONFLICT clause'),
                ('NOT EXISTS', 'NOT EXISTS predicate'),
                ('supersedes_assertion_id', 'supersedes_assertion_id'),
            ]

            found_implementations = {}
            exclude_dirs = {'.git', 'venv', 'venv_local', '__pycache__', '.pytest_cache', 'node_modules'}
            exclude_files = {'discovery_1_assertion_schema.py', 'discovery_2_prototype_evidence.py', 'discovery_3_assertion_semantics.py', 'final_assertion_gate.py'}

            for root, dirs, files in os.walk('.'):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if file.endswith(('.py', '.sql')) and file not in exclude_files:
                        filepath = os.path.join(root, file)
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                for i, line in enumerate(lines, 1):
                                    for pattern, desc in search_patterns:
                                        if pattern.lower() in line.lower():
                                            if desc not in found_implementations:
                                                found_implementations[desc] = []
                                            found_implementations[desc].append((filepath, i, line.strip()))
                        except:
                            pass

            if found_implementations:
                print("Found patterns in repository:")
                for desc, locations in sorted(found_implementations.items()):
                    print(f"\n  {desc}:")
                    for filepath, lineno, line in locations[:3]:
                        print(f"    {filepath}:{lineno}")
                        print(f"      {line[:100]}")
            else:
                print("✗ APPLICATION-LEVEL ASSERTION IDEMPOTENCY MECHANISM NOT FOUND")
                print("\n  No INSERT INTO runtime.assertion or idempotency guards found in repository")
                print("  (excluding discovery scripts)")

            # 7. CURRENT COUNTS — READ ONLY
            print("\n7. CURRENT TABLE COUNTS")
            print("-" * 80)

            raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event;")
            evidence_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
            assertion_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")
            fold_count = await conn.fetchval("SELECT COUNT(*) FROM state.fold_state_snapshot;")

            print(f"Raw events:        {raw_count} (expected: 177)")
            print(f"Evidence:          {evidence_count} (expected: 143)")
            print(f"Assertions:        {assertion_count} (expected: 107)")
            print(f"Fold snapshots:    {fold_count} (expected: 51)")

            counts_ok = (raw_count == 177 and evidence_count == 143 and
                        assertion_count == 107 and fold_count == 51)

            # 8. FINAL VERDICT
            print("\n" + "="*80)
            print("FINAL VERDICT")
            print("="*80)

            # Determine blockers
            blockers = []

            if not has_source_ev_fk:
                blockers.append("source_evidence_id FK to evidence.evidence_id NOT ENFORCED")
            
            if not insert_priv:
                blockers.append("No INSERT privilege on runtime.assertion")
            
            if not found_implementations and 'INSERT INTO runtime.assertion' not in str(found_implementations):
                blockers.append("No existing Assertion creation code found in repository")

            if blockers:
                print("\n✗ STEP 5F.1 BLOCKED")
                for blocker in blockers:
                    print(f"  — {blocker}")
            else:
                print("\n✓ STEP 5F.1 READY FOR IMPLEMENTATION")
                print("\nDecision basis:")
                print(f"  ✓ source_evidence_id FK enforced: {has_source_ev_fk}")
                print(f"  ✓ INSERT privilege available: {insert_priv}")
                print(f"  ✓ Current counts verified: {counts_ok}")

            print("\n" + "="*80)
            
            return True if not blockers else False

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if pool:
            await pool.close()


if __name__ == '__main__':
    success = asyncio.run(final_assertion_gate())
    sys.exit(0 if success else 1)
