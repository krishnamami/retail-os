#!/usr/bin/env python3
"""
STEP 5F.3 Fold Re-execution with Extended Property Domains
Execute Fold snapshot computation with product and configuration_request domains
Validates pre/post execution state
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


async def execute_fold_extension():
    """Execute Fold re-execution with extended property domains"""
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
            print("STEP 5F.3 FOLD RE-EXECUTION WITH EXTENDED PROPERTY DOMAINS")
            print("="*80)

            # Pre-execution validation
            print("\n1. PRE-EXECUTION STATE VALIDATION")
            print("-" * 80)

            current_snapshots = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_state_snapshot;
            """)
            print(f"Current snapshots: {current_snapshots} (expected: 51)")

            current_property_states = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_property_state;
            """)
            print(f"Current property states: {current_property_states} (expected: 177)")

            # Verify layer integrity before execution
            raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event;")
            evidence_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
            assertion_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")

            print(f"\nLayer state before Fold execution:")
            print(f"  Raw events: {raw_count} (expected: 177)")
            print(f"  Evidence: {evidence_count} (expected: 143)")
            print(f"  Assertions: {assertion_count} (expected: 143)")

            # Verify new Assertions are visible
            new_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion
                WHERE subject_type IN ('product', 'configuration_request')
                  AND simulator_classification = 'PROTOTYPE_ASSUMPTION';
            """)
            print(f"  New prototype Assertions: {new_assertions} (expected: 36)")

            # Execute Fold snapshot computation at horizon
            print("\n2. EXECUTING FOLD SNAPSHOT AT HORIZON")
            print("-" * 80)

            try:
                result = await conn.fetchval("""
                    SELECT * FROM runtime.fold_snapshot_at_horizon('2026-06-20 10:45:00+00'::TIMESTAMPTZ);
                """)
                print(f"✓ Fold snapshot computation completed")
            except Exception as e:
                print(f"✗ Fold execution error: {str(e)}")
                await pool.close()
                return False

            # Post-execution validation
            print("\n3. POST-EXECUTION STATE VALIDATION")
            print("-" * 80)

            new_snapshots = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_state_snapshot;
            """)
            print(f"Snapshots after Fold: {new_snapshots}")
            print(f"  Expected: 59 (51 + 8 new subjects)")
            print(f"  Status: {'✓ PASS' if new_snapshots == 59 else '✗ FAIL'}")

            new_property_states = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_property_state;
            """)
            print(f"\nProperty states after Fold: {new_property_states}")
            print(f"  Expected: 214 (177 + 37 new)")
            print(f"  Status: {'✓ PASS' if new_property_states == 214 else '✗ FAIL'}")

            # Verify new subjects
            new_subjects = await conn.fetchval("""
                SELECT COUNT(DISTINCT (decision_horizon, subject_type, subject_id))
                FROM state.fold_state_snapshot
                WHERE (subject_type, subject_id) NOT IN (
                    SELECT DISTINCT subject_type, subject_id FROM state.fold_state_snapshot
                    WHERE decision_horizon < '2026-06-20 10:45:00+00'
                );
            """)
            print(f"\nNew Fold subjects: {new_subjects} (expected: 8)")
            print(f"  Status: {'✓ PASS' if new_subjects == 8 else '✗ FAIL'}")

            # S6 Semantics: 2 distinct configuration_request subjects
            print("\n4. S6 DUPLICATE BUSINESS SCENARIO VERIFICATION")
            print("-" * 80)

            s6_subjects = await conn.fetchval("""
                SELECT COUNT(DISTINCT subject_id) FROM state.fold_state_snapshot
                WHERE subject_type = 'configuration_request'
                  AND subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;
            """)
            print(f"S6 distinct subjects: {s6_subjects} (expected: 2)")
            print(f"Status: {'✓ PASS' if s6_subjects == 2 else '✗ FAIL'}")

            s6_total_states = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_property_state
                WHERE subject_type = 'configuration_request'
                  AND subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;
            """)
            print(f"S6 total property states: {s6_total_states} (expected: 10 = 2 subjects × 5 properties)")
            print(f"Status: {'✓ PASS' if s6_total_states == 10 else '✗ FAIL'}")

            # S6 logical identity verification
            s6_product_refs = await conn.fetch("""
                SELECT DISTINCT subject_id, property_name, property_value
                FROM state.fold_property_state
                WHERE subject_type = 'configuration_request'
                  AND subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND property_name = 'product_reference'
                  AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ
                ORDER BY subject_id;
            """)

            print("\nS6 Logical Identity (should be identical):")
            s6_product_value = None
            for row in s6_product_refs:
                print(f"  {row['subject_id']:25} product_reference = {row['property_value']}")
                s6_product_value = row['property_value']

            if len(s6_product_refs) == 2 and all(r['property_value'] == s6_product_refs[0]['property_value'] for r in s6_product_refs):
                print(f"  Status: ✓ PASS (both subjects have identical product_reference)")
            else:
                print(f"  Status: ✗ FAIL (logical identity mismatch)")

            # S7 Missing-value Semantics
            print("\n5. S7 MISSING SEGMENT VERIFICATION")
            print("-" * 80)

            s7_established = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_property_state
                WHERE subject_type = 'configuration_request'
                  AND subject_id = 'CONFIG-REQ-2026-007'
                  AND property_state = 'ESTABLISHED'
                  AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;
            """)
            print(f"S7 ESTABLISHED properties: {s7_established} (expected: 4)")
            print(f"Status: {'✓ PASS' if s7_established == 4 else '✗ FAIL'}")

            s7_unreported = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_property_state
                WHERE subject_type = 'configuration_request'
                  AND subject_id = 'CONFIG-REQ-2026-007'
                  AND property_name = 'customer_segment'
                  AND property_state = 'UNREPORTED'
                  AND decision_horizon = '2026-06-20 10:45:00+00'::TIMESTAMPTZ;
            """)
            print(f"S7 UNREPORTED customer_segment: {s7_unreported} (expected: 1)")
            print(f"Status: {'✓ PASS' if s7_unreported == 1 else '✗ FAIL'}")

            # Layer integrity post-execution
            print("\n6. LAYER INTEGRITY VERIFICATION")
            print("-" * 80)

            raw_after = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event;")
            evidence_after = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
            assertion_after = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")

            raw_ok = raw_after == 177
            evidence_ok = evidence_after == 143
            assertion_ok = assertion_after == 143

            print(f"Raw events: {raw_after} (expected: 177) {'✓' if raw_ok else '✗'}")
            print(f"Evidence: {evidence_after} (expected: 143) {'✓' if evidence_ok else '✗'}")
            print(f"Assertions: {assertion_after} (expected: 143) {'✓' if assertion_ok else '✗'}")

            # Summary
            print("\n" + "="*80)
            print("STEP 5F.3 FOLD EXECUTION SUMMARY")
            print("="*80)

            all_checks = (
                new_snapshots == 59 and
                new_property_states == 214 and
                new_subjects == 8 and
                s6_subjects == 2 and
                s6_total_states == 10 and
                s7_established == 4 and
                s7_unreported == 1 and
                raw_ok and evidence_ok and assertion_ok
            )

            if all_checks:
                print("✓ STEP 5F.3 FOLD RE-EXECUTION SUCCESSFUL")
                print("\nFinal State:")
                print(f"  Snapshots: {current_snapshots} → {new_snapshots} (+8)")
                print(f"  Property states: {current_property_states} → {new_property_states} (+37)")
                print(f"  Subjects extended: product (1) + configuration_request (7)")
                print("\n✓ S6 Duplicate Business Scenario Preserved (2 distinct subjects)")
                print("✓ S7 Missing-value Semantics Preserved (1 UNREPORTED property)")
                print("✓ All other layers unchanged (Raw/Evidence/Assertions)")
            else:
                print("✗ STEP 5F.3 FOLD RE-EXECUTION FAILED — Some checks did not pass")
                print("\nFailed checks:")
                if new_snapshots != 59:
                    print(f"  - Snapshots: expected 59, got {new_snapshots}")
                if new_property_states != 214:
                    print(f"  - Property states: expected 214, got {new_property_states}")
                if s6_subjects != 2:
                    print(f"  - S6 subjects: expected 2, got {s6_subjects}")
                if s7_established != 4:
                    print(f"  - S7 ESTABLISHED: expected 4, got {s7_established}")
                if s7_unreported != 1:
                    print(f"  - S7 UNREPORTED: expected 1, got {s7_unreported}")

            await pool.close()
            return all_checks

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(execute_fold_extension())
    sys.exit(0 if success else 1)
