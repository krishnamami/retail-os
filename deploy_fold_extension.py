#!/usr/bin/env python3
"""
STEP 5F.3 Deploy Extended Fold SQL and Execute
Deploy extended fold_snapshot.sql with product and configuration_request domains
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


async def deploy_fold_extension():
    """Deploy extended fold SQL and execute"""
    credentials = get_postgres_credentials()

    try:
        pool = await asyncpg.create_pool(
            host=credentials['host'],
            port=credentials['port'],
            user=credentials['username'],
            password=credentials['password'],
            database=credentials['dbname'],
            timeout=60.0,
        )

        async with pool.acquire() as conn:
            print("\n" + "="*80)
            print("STEP 5F.3 DEPLOY EXTENDED FOLD SQL")
            print("="*80)

            # Read extended fold_snapshot.sql
            print("\n1. READING EXTENDED FOLD SQL")
            print("-" * 80)

            try:
                with open('fold_snapshot.sql', 'r') as f:
                    fold_sql = f.read()
                print("✓ Extended fold_snapshot.sql loaded")
                print(f"  File size: {len(fold_sql)} bytes")
            except Exception as e:
                print(f"✗ Error reading fold_snapshot.sql: {str(e)}")
                await pool.close()
                return False

            # Deploy the function
            print("\n2. DEPLOYING EXTENDED FOLD FUNCTION")
            print("-" * 80)

            try:
                await conn.execute(fold_sql)
                print("✓ Extended fold_snapshot_at_horizon function deployed")
            except Exception as e:
                print(f"✗ Error deploying function: {str(e)}")
                await pool.close()
                return False

            # Pre-execution validation
            print("\n3. PRE-EXECUTION STATE")
            print("-" * 80)

            current_snapshots = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_state_snapshot;
            """)
            print(f"Current snapshots: {current_snapshots}")

            current_subjects = await conn.fetchval("""
                SELECT COUNT(DISTINCT (subject_type, subject_id))
                FROM state.fold_state_snapshot;
            """)
            print(f"Current subjects: {current_subjects}")

            subject_types = await conn.fetch("""
                SELECT subject_type, COUNT(DISTINCT subject_id) as cnt
                FROM state.fold_state_snapshot
                GROUP BY subject_type
                ORDER BY cnt DESC;
            """)

            print("Subject types:")
            for st in subject_types:
                print(f"  {st['subject_type']:30} {st['cnt']}")

            # Execute extended fold
            print("\n4. EXECUTING EXTENDED FOLD_SNAPSHOT_AT_HORIZON")
            print("-" * 80)

            try:
                result = await conn.fetchrow("""
                    SELECT * FROM runtime.fold_snapshot_at_horizon('2026-06-20 10:45:00+00'::TIMESTAMPTZ);
                """)

                if result:
                    print("✓ Fold execution completed")
                    print(f"  Snapshot count: {result['fold_snapshot_count']}")
                    print(f"  Total property states: {result['total_property_states']}")
                    print(f"  Established: {result['established_count']}")
                    print(f"  Unreported: {result['unreported_count']}")
                    print(f"  Explicitly undefined: {result['explicitly_undefined_count']}")
                    print(f"  Contradicted: {result['contradicted_count']}")
                    print(f"  New snapshots: {result['new_snapshots_inserted']}")
                    print(f"  Deterministic replays: {result['deterministic_replays']}")
                    print(f"  Mismatches: {result['replay_mismatches']}")
                    print(f"\n  Subjects by type: {result['subjects_by_type']}")
            except Exception as e:
                print(f"✗ Error executing fold: {str(e)}")
                await pool.close()
                return False

            # Post-execution validation
            print("\n5. POST-EXECUTION STATE")
            print("-" * 80)

            new_snapshots = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_state_snapshot;
            """)
            print(f"Snapshots after Fold: {new_snapshots}")
            print(f"Difference: +{new_snapshots - current_snapshots}")

            new_subjects = await conn.fetchval("""
                SELECT COUNT(DISTINCT (subject_type, subject_id))
                FROM state.fold_state_snapshot;
            """)
            print(f"Subjects after Fold: {new_subjects}")
            print(f"Difference: +{new_subjects - current_subjects}")

            subject_types_after = await conn.fetch("""
                SELECT subject_type, COUNT(DISTINCT subject_id) as cnt
                FROM state.fold_state_snapshot
                GROUP BY subject_type
                ORDER BY cnt DESC;
            """)

            print("\nSubject types (post-execution):")
            for st in subject_types_after:
                print(f"  {st['subject_type']:30} {st['cnt']}")

            # Verify new prototype subjects
            print("\n6. NEW PROTOTYPE SUBJECTS VERIFICATION")
            print("-" * 80)

            product_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT subject_id) FROM state.fold_state_snapshot
                WHERE subject_type = 'product';
            """)
            print(f"Product subjects: {product_count} (expected: 1)")

            config_req_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT subject_id) FROM state.fold_state_snapshot
                WHERE subject_type = 'configuration_request';
            """)
            print(f"Configuration request subjects: {config_req_count} (expected: 7)")

            # S6 verification
            print("\n7. S6 DUPLICATE BUSINESS SCENARIO VERIFICATION")
            print("-" * 80)

            s6_subjects = await conn.fetchval("""
                SELECT COUNT(DISTINCT subject_id) FROM state.fold_state_snapshot
                WHERE subject_type = 'configuration_request'
                  AND subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B');
            """)
            print(f"S6 distinct subjects: {s6_subjects} (expected: 2)")
            print(f"Status: {'✓ PASS' if s6_subjects == 2 else '✗ FAIL'}")

            s6_properties = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_state_snapshot
                WHERE subject_type = 'configuration_request'
                  AND subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B');
            """)
            print(f"S6 total snapshots: {s6_properties} (expected: 2)")

            # S7 verification
            print("\n8. S7 MISSING SEGMENT VERIFICATION")
            print("-" * 80)

            s7_count = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_state_snapshot
                WHERE subject_type = 'configuration_request'
                  AND subject_id = 'CONFIG-REQ-2026-007';
            """)
            print(f"S7 snapshots: {s7_count} (expected: 1)")

            # Summary
            print("\n" + "="*80)
            print("DEPLOYMENT AND EXECUTION SUMMARY")
            print("="*80)

            expected_snapshots = 59  # 51 + 8
            expected_subjects = 59   # 51 + 1 product + 7 config_request
            all_checks = (
                new_snapshots == expected_snapshots and
                product_count == 1 and
                config_req_count == 7 and
                s6_subjects == 2 and
                s7_count == 1
            )

            if all_checks:
                print("✓ FOLD EXTENSION DEPLOYMENT SUCCESSFUL")
                print(f"\nSnapshots: {current_snapshots} → {new_snapshots} (+{new_snapshots - current_snapshots})")
                print(f"Subjects: {current_subjects} → {new_subjects} (+{new_subjects - current_subjects})")
                print("✓ New domains extended (product + configuration_request)")
                print("✓ S6 and S7 semantics preserved")
            else:
                print("✗ FOLD EXTENSION DEPLOYMENT INCOMPLETE")
                if new_snapshots != expected_snapshots:
                    print(f"  - Snapshots: expected {expected_snapshots}, got {new_snapshots}")
                if product_count != 1:
                    print(f"  - Product subjects: expected 1, got {product_count}")
                if config_req_count != 7:
                    print(f"  - Config request subjects: expected 7, got {config_req_count}")

            await pool.close()
            return all_checks

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(deploy_fold_extension())
    sys.exit(0 if success else 1)
