#!/usr/bin/env python3
"""
STEP 5F.1 Discovery — Inspect Live runtime.assertion Schema
READ-ONLY: No database writes
"""

import asyncio
import json
import sys
from typing import Dict, Any

import asyncpg
import boto3


def get_postgres_credentials() -> Dict[str, Any]:
    secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
    response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
    return json.loads(response['SecretString'])


async def inspect_assertion_schema():
    """Inspect live runtime.assertion schema"""
    credentials = get_postgres_credentials()

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
            print("STEP 5F.1 DISCOVERY — LIVE ASSERTION SCHEMA")
            print("="*80)

            # Get table columns
            print("\n1. TABLE STRUCTURE (columns, types)")
            print("-" * 80)

            columns = await conn.fetch("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'runtime' AND table_name = 'assertion'
                ORDER BY ordinal_position;
            """)

            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"  {col['column_name']:25} {col['data_type']:20} {nullable}{default}")

            # Get primary key
            print("\n2. PRIMARY KEY")
            print("-" * 80)

            pk = await conn.fetchval("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_schema = 'runtime'
                  AND table_name = 'assertion'
                  AND constraint_type = 'PRIMARY KEY';
            """)

            if pk:
                pk_cols = await conn.fetch(f"""
                    SELECT column_name
                    FROM information_schema.key_column_usage
                    WHERE table_schema = 'runtime'
                      AND table_name = 'assertion'
                      AND constraint_name = '{pk}'
                    ORDER BY ordinal_position;
                """)
                print(f"  Constraint: {pk}")
                print(f"  Columns: {', '.join([c['column_name'] for c in pk_cols])}")
            else:
                print("  No primary key defined")

            # Get unique constraints
            print("\n3. UNIQUE CONSTRAINTS")
            print("-" * 80)

            uniques = await conn.fetch("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_schema = 'runtime'
                  AND table_name = 'assertion'
                  AND constraint_type = 'UNIQUE';
            """)

            if uniques:
                for u in uniques:
                    cols = await conn.fetch(f"""
                        SELECT column_name
                        FROM information_schema.key_column_usage
                        WHERE table_schema = 'runtime'
                          AND table_name = 'assertion'
                          AND constraint_name = '{u['constraint_name']}'
                        ORDER BY ordinal_position;
                    """)
                    col_names = ', '.join([c['column_name'] for c in cols])
                    print(f"  {u['constraint_name']}: ({col_names})")
            else:
                print("  No unique constraints")

            # Get foreign keys
            print("\n4. FOREIGN KEY CONSTRAINTS")
            print("-" * 80)

            fks = await conn.fetch("""
                SELECT
                    constraint_name,
                    column_name,
                    table_name as ref_table,
                    column_name as ref_column
                FROM information_schema.key_column_usage
                WHERE table_schema = 'runtime'
                  AND table_name = 'assertion'
                  AND referenced_table_name IS NOT NULL;
            """)

            if fks:
                for fk in fks:
                    print(f"  {fk['constraint_name']}: {fk['column_name']} → {fk['ref_schema']}.{fk['ref_table']}.{fk['ref_column']}")
            else:
                print("  No foreign keys")

            # Get check constraints
            print("\n5. CHECK CONSTRAINTS")
            print("-" * 80)

            checks = await conn.fetch("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_schema = 'runtime';
            """)

            if checks:
                for c in checks:
                    print(f"  {c['constraint_name']}: {c['check_clause']}")
            else:
                print("  No check constraints")

            # Get indexes
            print("\n6. INDEXES (RELEVANT TO IDEMPOTENCY)")
            print("-" * 80)

            indexes = await conn.fetch("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'runtime' AND tablename = 'assertion';
            """)

            for idx in indexes:
                print(f"  {idx['indexname']}")
                print(f"    {idx['indexdef']}")

            # Get row count
            print("\n7. CURRENT DATA")
            print("-" * 80)

            row_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")
            print(f"  Total rows: {row_count}")

            # Get authority values
            print("\n8. AUTHORITY VALUES (Sample from current data)")
            print("-" * 80)

            authorities = await conn.fetch("""
                SELECT DISTINCT authority, COUNT(*) as cnt
                FROM runtime.assertion
                GROUP BY authority
                ORDER BY cnt DESC;
            """)

            for auth in authorities:
                print(f"  {auth['authority']:30} ({auth['cnt']} rows)")

            # Get subject types
            print("\n9. SUBJECT TYPES (Sample from current data)")
            print("-" * 80)

            subject_types = await conn.fetch("""
                SELECT DISTINCT subject_type, COUNT(*) as cnt
                FROM runtime.assertion
                GROUP BY subject_type
                ORDER BY cnt DESC;
            """)

            for st in subject_types:
                print(f"  {st['subject_type']:30} ({st['cnt']} rows)")

            # Get property names
            print("\n10. PROPERTY NAMES (Sample from current data)")
            print("-" * 80)

            properties = await conn.fetch("""
                SELECT DISTINCT property_name, COUNT(*) as cnt
                FROM runtime.assertion
                GROUP BY property_name
                ORDER BY cnt DESC
                LIMIT 20;
            """)

            for prop in properties:
                print(f"  {prop['property_name']:40} ({prop['cnt']} rows)")

            # Sample row
            print("\n11. SAMPLE ROW (First Assertion)")
            print("-" * 80)

            sample = await conn.fetchrow("SELECT * FROM runtime.assertion LIMIT 1;")
            if sample:
                for key, val in dict(sample).items():
                    print(f"  {key:25} = {val}")

            await pool.close()
            return True

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(inspect_assertion_schema())
    sys.exit(0 if success else 1)
