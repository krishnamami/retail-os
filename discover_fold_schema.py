#!/usr/bin/env python3
"""
Discover actual Fold schema structure
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


async def discover_fold_schema():
    """Discover actual Fold schema"""
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
            print("FOLD SCHEMA DISCOVERY")
            print("="*80)

            # List all tables in state schema
            print("\n1. TABLES IN STATE SCHEMA")
            print("-" * 80)

            tables = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'state'
                ORDER BY table_name;
            """)

            if tables:
                for table in tables:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM state.{table['table_name']};")
                    print(f"  {table['table_name']}: {count} rows")
            else:
                print("  No tables found in state schema")

            # List all schemas
            print("\n2. ALL SCHEMAS IN DATABASE")
            print("-" * 80)

            schemas = await conn.fetch("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT LIKE 'pg_%'
                ORDER BY schema_name;
            """)

            for schema in schemas:
                print(f"  {schema['schema_name']}")

            # List functions in runtime schema
            print("\n3. FUNCTIONS IN RUNTIME SCHEMA")
            print("-" * 80)

            funcs = await conn.fetch("""
                SELECT routine_name, routine_type
                FROM information_schema.routines
                WHERE routine_schema = 'runtime'
                ORDER BY routine_name;
            """)

            if funcs:
                for func in funcs:
                    print(f"  {func['routine_name']} ({func['routine_type']})")
            else:
                print("  No functions found")

            # Check fold_snapshot_at_horizon signature
            print("\n4. FOLD_SNAPSHOT_AT_HORIZON FUNCTION")
            print("-" * 80)

            fold_func = await conn.fetchrow("""
                SELECT routine_definition
                FROM information_schema.routines
                WHERE routine_schema = 'runtime'
                  AND routine_name = 'fold_snapshot_at_horizon';
            """)

            if fold_func:
                print("Function found - first 500 chars of definition:")
                print(fold_func['routine_definition'][:500])
            else:
                print("Function fold_snapshot_at_horizon NOT FOUND")

            # Try to call fold_snapshot_at_horizon and see what it returns
            print("\n5. CALLING FOLD_SNAPSHOT_AT_HORIZON")
            print("-" * 80)

            try:
                result = await conn.fetchval("""
                    SELECT * FROM runtime.fold_snapshot_at_horizon('2026-06-20 10:45:00+00'::TIMESTAMPTZ);
                """)
                print(f"Function returned: {result}")
                print(f"Return type: {type(result)}")
            except Exception as e:
                print(f"Error calling function: {str(e)}")

            # Check fold_state_snapshot structure
            print("\n6. FOLD_STATE_SNAPSHOT TABLE STRUCTURE")
            print("-" * 80)

            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'state' AND table_name = 'fold_state_snapshot'
                ORDER BY ordinal_position;
            """)

            if columns:
                for col in columns:
                    print(f"  {col['column_name']:30} {col['data_type']}")
            else:
                print("  Table fold_state_snapshot does not exist")

            # Count current fold_state_snapshot rows
            print("\n7. CURRENT FOLD STATE")
            print("-" * 80)

            try:
                snap_count = await conn.fetchval("SELECT COUNT(*) FROM state.fold_state_snapshot;")
                print(f"fold_state_snapshot rows: {snap_count}")

                # Get distinct decision horizons
                horizons = await conn.fetch("""
                    SELECT DISTINCT decision_horizon
                    FROM state.fold_state_snapshot
                    ORDER BY decision_horizon DESC;
                """)

                print(f"\nDecision horizons ({len(horizons)}):")
                for h in horizons[:5]:
                    print(f"  {h['decision_horizon']}")
                if len(horizons) > 5:
                    print(f"  ... and {len(horizons) - 5} more")

                # Get distinct subject types
                subject_types = await conn.fetch("""
                    SELECT DISTINCT subject_type, COUNT(*) as cnt
                    FROM state.fold_state_snapshot
                    GROUP BY subject_type
                    ORDER BY cnt DESC;
                """)

                print(f"\nSubject types:")
                for st in subject_types:
                    print(f"  {st['subject_type']:30} {st['cnt']} subjects")

            except Exception as e:
                print(f"Error querying fold_state_snapshot: {str(e)}")

            await pool.close()
            return True

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(discover_fold_schema())
    sys.exit(0 if success else 1)
