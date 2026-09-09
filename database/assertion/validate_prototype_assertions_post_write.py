#!/usr/bin/env python3
"""
STEP 5F.2 Post-Write Validation — Verify transformation completed correctly
READ-ONLY: No database writes
Validates row counts, field mappings, idempotency, semantics, and layer integrity
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


async def validate_prototype_assertions_post_write():
    """Validate prototype Assertion transformation (post-execution)"""
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
            print("STEP 5F.2 POST-WRITE VALIDATION — PROTOTYPE ASSERTIONS VERIFIED")
            print("="*80)

            prototype_mapping_ids = [
                'PRODUCT_DEF_NAME',
                'PRODUCT_DEF_LAUNCH',
                'CONF_REQ_PRODUCT',
                'CONF_REQ_LAUNCH',
                'CONF_REQ_GEO',
                'CONF_REQ_TERM',
                'CONF_REQ_SEGMENT'
            ]

            # VALIDATION 1: Row counts
            print("\n1. ROW COUNT VALIDATION")
            print("-" * 80)

            assertion_count = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion;
            """)

            expected_after = 143
            print(f"Total Assertions: {assertion_count} (expected: {expected_after})")
            
            if assertion_count != expected_after:
                print(f"✗ FAIL: Count mismatch")
                return False

            prototype_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                WHERE EXISTS (
                    SELECT 1 FROM runtime.evidence e
                    WHERE e.evidence_id = a.source_evidence_id
                      AND e.mapping_id = ANY($1::text[])
                );
            """, prototype_mapping_ids)

            print(f"Prototype Assertions: {prototype_assertions} (expected: 36)")
            
            if prototype_assertions != 36:
                print(f"✗ FAIL: Prototype count mismatch")
                return False

            # VALIDATION 2: Idempotency (replay guard)
            print("\n2. IDEMPOTENCY VERIFICATION")
            print("-" * 80)

            duplicate_check = await conn.fetchval("""
                SELECT COUNT(*) FROM (
                    SELECT source_evidence_id, COUNT(*) as cnt
                    FROM runtime.assertion
                    WHERE source_evidence_id IN (
                        SELECT evidence_id FROM runtime.evidence
                        WHERE mapping_id = ANY($1::text[])
                    )
                    GROUP BY source_evidence_id
                    HAVING COUNT(*) > 1
                ) dups;
            """, prototype_mapping_ids)

            print(f"Duplicate source_evidence_id mappings: {duplicate_check} (expected: 0)")
            
            if duplicate_check > 0:
                print(f"✗ FAIL: Duplicates found")
                return False

            print("✓ Replay guard verified: No duplicates created")

            # VALIDATION 3: S6 business duplicate preservation
            print("\n3. S6 BUSINESS DUPLICATE PRESERVATION")
            print("-" * 80)

            s6_assertions = await conn.fetch("""
                SELECT
                    a.subject_id,
                    COUNT(*) as cnt
                FROM runtime.assertion a
                WHERE a.subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND EXISTS (
                    SELECT 1 FROM runtime.evidence e
                    WHERE e.evidence_id = a.source_evidence_id
                      AND e.mapping_id = ANY($1::text[])
                  )
                GROUP BY a.subject_id;
            """, prototype_mapping_ids)

            print(f"S6 distinct subjects with Assertions: {len(s6_assertions)}")
            for row in s6_assertions:
                print(f"  {row['subject_id']}: {row['cnt']} Assertions")

            if len(s6_assertions) != 2:
                print(f"✗ FAIL: S6 not preserved as 2 distinct subjects")
                return False

            print("✓ S6 preserved: 2 distinct configuration_request subjects")

            # VALIDATION 4: S7 missing-segment semantics
            print("\n4. S7 MISSING-SEGMENT VALIDATION")
            print("-" * 80)

            s7_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                WHERE a.subject_id = 'CONFIG-REQ-2026-007'
                  AND EXISTS (
                    SELECT 1 FROM runtime.evidence e
                    WHERE e.evidence_id = a.source_evidence_id
                      AND e.mapping_id = ANY($1::text[])
                  );
            """, prototype_mapping_ids)

            print(f"S7 Assertions created: {s7_assertions} (expected: 4)")
            
            if s7_assertions != 4:
                print(f"✗ FAIL: S7 Assertion count {s7_assertions} != 4")
                return False

            s7_segment_check = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                WHERE a.subject_id = 'CONFIG-REQ-2026-007'
                  AND a.property_name = 'customer_segment'
                  AND EXISTS (
                    SELECT 1 FROM runtime.evidence e
                    WHERE e.evidence_id = a.source_evidence_id
                      AND e.mapping_id = ANY($1::text[])
                  );
            """, prototype_mapping_ids)

            print(f"S7 customer_segment Assertions: {s7_segment_check} (expected: 0)")
            
            if s7_segment_check > 0:
                print(f"✗ FAIL: S7 has customer_segment Assertion (unexpected)")
                return False

            print("✓ S7 semantics correct: 4 Assertions, no customer_segment")

            # VALIDATION 5: Field mapping correctness
            print("\n5. FIELD MAPPING VALIDATION")
            print("-" * 80)

            # Check a few samples
            mapping_mismatches = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
                WHERE e.mapping_id = ANY($1::text[])
                  AND (
                    a.subject_type IS DISTINCT FROM e.subject_type
                    OR a.subject_id IS DISTINCT FROM e.subject_id
                    OR a.property_name IS DISTINCT FROM e.property_name
                    OR a.asserted_value IS DISTINCT FROM e.asserted_value
                    OR a.property_value_type IS DISTINCT FROM e.value_type
                    OR a.effective_at IS DISTINCT FROM e.occurred_at
                    OR a.arrival_at IS DISTINCT FROM e.arrival_at
                  );
            """, prototype_mapping_ids)

            print(f"Field mapping mismatches: {mapping_mismatches} (expected: 0)")
            
            if mapping_mismatches > 0:
                print(f"✗ FAIL: Field mapping errors detected")
                return False

            print("✓ All field mappings correct")

            # VALIDATION 6: No orphans
            print("\n6. ORPHAN ASSERTION CHECK")
            print("-" * 80)

            orphans = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                WHERE a.source_evidence_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.evidence e
                    WHERE e.evidence_id = a.source_evidence_id
                  )
                  AND EXISTS (
                    SELECT 1 FROM runtime.evidence e2
                    WHERE e2.mapping_id = ANY($1::text[])
                  );
            """, prototype_mapping_ids)

            print(f"Orphaned Assertions: {orphans} (expected: 0)")
            
            if orphans > 0:
                print(f"✗ FAIL: Orphaned Assertions found")
                return False

            print("✓ No orphans: All Assertions have valid source_evidence_id")

            # VALIDATION 7: Layer integrity
            print("\n7. LAYER INTEGRITY CHECK")
            print("-" * 80)

            raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event;")
            evidence_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
            fold_count = await conn.fetchval("SELECT COUNT(*) FROM state.fold_state_snapshot;")

            print(f"Raw: {raw_count} (expected: 177)")
            print(f"Evidence: {evidence_count} (expected: 143)")
            print(f"Assertions: {assertion_count} (expected: 143)")
            print(f"Fold: {fold_count} (expected: 51)")

            if raw_count != 177 or evidence_count != 143 or fold_count != 51:
                print(f"✗ FAIL: Other layers were modified")
                return False

            print("✓ Layer integrity preserved: Only Assertions changed")

            # FINAL VERDICT
            print("\n" + "="*80)
            print("POST-WRITE VALIDATION COMPLETE")
            print("="*80)
            print("\n✓ STEP 5F.2 EXECUTION VERIFIED")
            print("  • Assertions: 107 → 143 (+36)")
            print("  • Prototype Evidence: 36 Assertions created")
            print("  • S6 preserved: 2 distinct subjects")
            print("  • S7 semantics: 4 Assertions, no customer_segment")
            print("  • Idempotency: 0 duplicates")
            print("  • Layer integrity: Only runtime.assertion changed")
            print("  • Ready for next step: STEP 5F.3 Fold re-execution")
            
            return True

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if pool:
            await pool.close()


if __name__ == '__main__':
    success = asyncio.run(validate_prototype_assertions_post_write())
    sys.exit(0 if success else 1)
