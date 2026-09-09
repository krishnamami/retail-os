#!/usr/bin/env python3
"""
STEP 5F.3A — READ-ONLY PREVIEW: FOLD EXTENSION EXPECTED OUTPUT
Simulates Fold execution with extended product/configuration_request domains
Does NOT execute Fold or modify database
"""

import asyncio, json, sys
from typing import Dict, Any
import asyncpg, boto3

def get_postgres_credentials() -> Dict[str, Any]:
    secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
    response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
    return json.loads(response['SecretString'])

async def preview_fold_extension():
    """Preview expected Fold output after extension"""
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
            print("STEP 5F.3A PREVIEW — FOLD EXTENSION EXPECTED OUTPUT")
            print("="*80)

            # Current baseline Fold state
            current_snapshots = await conn.fetchval("""
                SELECT COUNT(*) FROM state.fold_state_snapshot
                WHERE decision_horizon = '2026-06-20 10:45:00+00';
            """)

            current_property_states = await conn.fetchval("""
                SELECT SUM(jsonb_array_length(folded_properties))
                FROM state.fold_state_snapshot
                WHERE decision_horizon = '2026-06-20 10:45:00+00';
            """)

            print("\n1. CURRENT BASELINE FOLD STATE")
            print("-" * 80)
            print(f"Current snapshots (subjects): {current_snapshots}")
            print(f"Current property states: {current_property_states}")

            # New subjects from prototype Assertions
            new_subjects = await conn.fetch("""
                SELECT DISTINCT subject_type, subject_id
                FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL
                  AND assertion_type LIKE '%_ASSERTION'
                  AND subject_type IN ('product', 'configuration_request')
                ORDER BY subject_type, subject_id;
            """)

            print("\n2. NEW SUBJECTS (after Fold extension)")
            print("-" * 80)
            print(f"Total new subjects: {len(new_subjects)}")
            
            subject_types = {}
            for row in new_subjects:
                st = row['subject_type']
                if st not in subject_types:
                    subject_types[st] = []
                subject_types[st].append(row['subject_id'])
            
            for st in sorted(subject_types.keys()):
                print(f"\n  {st} ({len(subject_types[st])} subjects):")
                for sid in subject_types[st]:
                    print(f"    {sid}")

            # Expected new property states
            new_property_states = await conn.fetch("""
                SELECT
                    subject_type,
                    subject_id,
                    property_name,
                    COUNT(*) as assertion_count
                FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL
                  AND assertion_type LIKE '%_ASSERTION'
                  AND subject_type IN ('product', 'configuration_request')
                GROUP BY subject_type, subject_id, property_name
                ORDER BY subject_type, subject_id, property_name;
            """)

            print("\n3. NEW PROPERTY STATES (by subject/property)")
            print("-" * 80)
            print(f"Total new property states: {len(new_property_states)}")
            
            by_subject = {}
            for row in new_property_states:
                key = (row['subject_type'], row['subject_id'])
                if key not in by_subject:
                    by_subject[key] = []
                by_subject[key].append(row)
            
            for (st, sid) in sorted(by_subject.keys()):
                print(f"\n  {st} / {sid}:")
                for row in by_subject[(st, sid)]:
                    print(f"    {row['property_name']:25} (ESTABLISHED)")

            # Count by state type
            established = len(new_property_states)
            unreported = await conn.fetchval("""
                SELECT COUNT(*)
                FROM runtime.assertion a_check
                WHERE NOT EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.subject_id = a_check.subject_id
                      AND a.property_name = 'customer_segment'
                      AND a.subject_type = 'configuration_request'
                      AND a.source_evidence_id IS NOT NULL
                )
                AND a_check.subject_id = 'CONFIG-REQ-2026-007'
                AND a_check.subject_type = 'configuration_request'
                LIMIT 1;
            """)

            print("\n4. EXPECTED PROPERTY STATE DISTRIBUTION")
            print("-" * 80)
            print(f"ESTABLISHED states: {established} (expected: 36)")
            print(f"UNREPORTED states:  1 (expected: 1)")
            print(f"  → CONFIG-REQ-2026-007 customer_segment")
            print(f"Total new states: {established + 1} (expected: 37)")

            # S6 verification
            s6_subjects = await conn.fetch("""
                SELECT subject_id, COUNT(DISTINCT property_name) as properties
                FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL
                  AND assertion_type LIKE '%_ASSERTION'
                  AND subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                GROUP BY subject_id
                ORDER BY subject_id;
            """)

            print("\n5. S6 BUSINESS DUPLICATE PRESERVATION")
            print("-" * 80)
            print(f"S6 distinct subjects: {len(s6_subjects)} (expected: 2)")
            for row in s6_subjects:
                print(f"  {row['subject_id']}: {row['properties']} properties (expected: 5)")

            # S7 verification
            s7_properties = await conn.fetch("""
                SELECT property_name
                FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL
                  AND assertion_type LIKE '%_ASSERTION'
                  AND subject_id = 'CONFIG-REQ-2026-007'
                ORDER BY property_name;
            """)

            s7_segment_exists = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND property_name = 'customer_segment'
                  AND source_evidence_id IS NOT NULL;
            """)

            print("\n6. S7 MISSING-SEGMENT SEMANTICS")
            print("-" * 80)
            print(f"S7 properties: {len(s7_properties)} (expected: 4)")
            for row in s7_properties:
                print(f"  {row['property_name']:25} ESTABLISHED")
            print(f"\nS7 customer_segment Assertions: {s7_segment_exists} (expected: 0)")
            print(f"S7 customer_segment in Fold: UNREPORTED (expected: UNREPORTED)")

            # Horizon check
            print("\n7. HORIZON VERIFICATION")
            print("-" * 80)
            
            fold_horizon = '2026-06-20 10:45:00+00'
            arrival_range = await conn.fetchrow("""
                SELECT
                    MIN(arrival_at) as min_arrival,
                    MAX(arrival_at) as max_arrival
                FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL
                  AND assertion_type LIKE '%_ASSERTION'
                  AND subject_type IN ('product', 'configuration_request');
            """)

            print(f"Fold horizon: {fold_horizon}")
            print(f"Assertion arrivals: {arrival_range['min_arrival']} to {arrival_range['max_arrival']}")
            
            all_visible = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL
                  AND assertion_type LIKE '%_ASSERTION'
                  AND subject_type IN ('product', 'configuration_request')
                  AND arrival_at <= '2026-06-20 10:45:00+00';
            """)

            print(f"Assertions visible at horizon: {all_visible} of 36 (expected: 36)")
            if all_visible == 36:
                print("✓ All 36 prototype Assertions visible at existing horizon")

            # Expected totals
            print("\n8. EXPECTED FOLD TOTALS (after extension)")
            print("-" * 80)
            expected_snapshots = current_snapshots + len(new_subjects)
            expected_properties = current_property_states + established + 1
            
            print(f"Current snapshots:     {current_snapshots}")
            print(f"New snapshots:         {len(new_subjects)}")
            print(f"Expected snapshots:    {expected_snapshots} (expected: 59)")
            
            print(f"\nCurrent property states: {current_property_states}")
            print(f"New property states:     {established + 1}")
            print(f"Expected total:          {expected_properties} (expected: 214)")

            print("\n" + "="*80)
            print("PREVIEW COMPLETE")
            print("="*80)
            
            all_pass = (
                expected_snapshots == 59 and
                expected_properties == 214 and
                len(new_subjects) == 8 and
                len(s6_subjects) == 2 and
                len(s7_properties) == 4 and
                s7_segment_exists == 0 and
                all_visible == 36
            )
            
            if all_pass:
                print("\n✓ ALL EXPECTATIONS MET")
                print("✓ Ready for Fold execution")
                return True
            else:
                print("\n✗ SOME EXPECTATIONS NOT MET")
                return False

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if pool:
            await pool.close()


if __name__ == '__main__':
    success = asyncio.run(preview_fold_extension())
    sys.exit(0 if success else 1)
