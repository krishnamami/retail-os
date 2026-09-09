#!/usr/bin/env python3
"""
Discover Fold schema structure - simplified
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
            print("FOLD SCHEMA DISCOVERY - SIMPLIFIED")
            print("="*80)

            # fold_state_snapshot structure
            print("\n1. FOLD_STATE_SNAPSHOT COLUMNS")
            print("-" * 80)

            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'state' AND table_name = 'fold_state_snapshot'
                ORDER BY ordinal_position;
            """)

            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  {col['column_name']:30} {col['data_type']:20} {nullable}")

            # Current fold_state_snapshot
            print("\n2. CURRENT FOLD_STATE_SNAPSHOT DATA")
            print("-" * 80)

            total = await conn.fetchval("SELECT COUNT(*) FROM state.fold_state_snapshot;")
            print(f"Total rows: {total}")

            # Sample row
            print("\nSample row:")
            sample = await conn.fetchrow("SELECT * FROM state.fold_state_snapshot LIMIT 1;")
            if sample:
                for key, val in dict(sample).items():
                    val_str = str(val)[:80] if val else "NULL"
                    print(f"  {key:30} = {val_str}")

            # Group by decision_horizon
            print("\n3. DATA BY DECISION HORIZON")
            print("-" * 80)

            horizons = await conn.fetch("""
                SELECT
                    decision_horizon,
                    COUNT(*) as snapshot_count,
                    COUNT(DISTINCT subject_type) as subject_types,
                    COUNT(DISTINCT subject_id) as distinct_subjects
                FROM state.fold_state_snapshot
                GROUP BY decision_horizon
                ORDER BY decision_horizon DESC;
            """)

            for h in horizons:
                print(f"\n  {h['decision_horizon']}")
                print(f"    Snapshots: {h['snapshot_count']}")
                print(f"    Subject types: {h['subject_types']}")
                print(f"    Distinct subjects: {h['distinct_subjects']}")

            # Subject types
            print("\n4. SUBJECT TYPES IN CURRENT DATA")
            print("-" * 80)

            subject_types = await conn.fetch("""
                SELECT DISTINCT subject_type, COUNT(*) as cnt
                FROM state.fold_state_snapshot
                GROUP BY subject_type
                ORDER BY cnt DESC;
            """)

            for st in subject_types:
                print(f"  {st['subject_type']:30} {st['cnt']} rows")

            # Try to call fold_snapshot_at_horizon
            print("\n5. CALLING FOLD_SNAPSHOT_AT_HORIZON('2026-06-20 10:45:00+00')")
            print("-" * 80)

            try:
                result = await conn.fetchval("""
                    SELECT * FROM runtime.fold_snapshot_at_horizon('2026-06-20 10:45:00+00'::TIMESTAMPTZ);
                """)
                print(f"Return value: {result}")
                print(f"Return type: {type(result).__name__}")

                # Now check if new rows were added
                print("\n6. FOLD_STATE_SNAPSHOT AFTER FUNCTION CALL")
                print("-" * 80)

                new_total = await conn.fetchval("SELECT COUNT(*) FROM state.fold_state_snapshot;")
                print(f"Total rows after call: {new_total}")
                print(f"Difference: {new_total - total}")

                # New rows by horizon
                new_horizons = await conn.fetch("""
                    SELECT
                        decision_horizon,
                        COUNT(*) as snapshot_count,
                        COUNT(DISTINCT subject_type) as subject_types,
                        COUNT(DISTINCT subject_id) as distinct_subjects
                    FROM state.fold_state_snapshot
                    WHERE decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
                    GROUP BY decision_horizon;
                """)

                if new_horizons:
                    for h in new_horizons:
                        print(f"\n  {h['decision_horizon']}")
                        print(f"    Snapshots: {h['snapshot_count']}")
                        print(f"    Subject types: {h['subject_types']}")
                        print(f"    Distinct subjects: {h['distinct_subjects']}")

            except Exception as e:
                print(f"Error calling function: {type(e).__name__}: {str(e)}")

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
