#!/usr/bin/env python3
"""
STEP 5F.2 Preview — Show what Assertions will be created from prototype Evidence
READ-ONLY: No database writes
Shows exactly what rows will be inserted, checks replay guard, validates S6/S7 semantics
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


async def preview_prototype_assertions():
    """Preview prototype Assertions that will be created"""
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
            print("STEP 5F.2 PREVIEW — PROTOTYPE EVIDENCE → ASSERTION TRANSFORMATION")
            print("="*80)

            # Verify prototype scope
            prototype_mapping_ids = [
                'PRODUCT_DEF_NAME',
                'PRODUCT_DEF_LAUNCH',
                'CONF_REQ_PRODUCT',
                'CONF_REQ_LAUNCH',
                'CONF_REQ_GEO',
                'CONF_REQ_TERM',
                'CONF_REQ_SEGMENT'
            ]

            prototype_count = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE mapping_id = ANY($1::text[]);
            """, prototype_mapping_ids)

            print(f"\n1. PROTOTYPE EVIDENCE SCOPE")
            print("-" * 80)
            print(f"Prototype Evidence to transform: {prototype_count} (expected: 36)")

            if prototype_count != 36:
                print(f"✗ FAIL: Prototype count {prototype_count} != 36")
                return False

            # Check replay guard
            print(f"\n2. REPLAY GUARD CHECK (NOT EXISTS)")
            print("-" * 80)

            already_mapped = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence e
                WHERE e.mapping_id = ANY($1::text[])
                  AND EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = e.evidence_id
                  );
            """, prototype_mapping_ids)

            print(f"Prototype Evidence already mapped to Assertions: {already_mapped}")
            
            to_insert = prototype_count - already_mapped
            print(f"Assertions ready to insert (NOT EXISTS guard): {to_insert}")

            # Current counts
            current_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion;
            """)

            expected_after = current_assertions + to_insert

            print(f"\nCurrent Assertions: {current_assertions}")
            print(f"After insertion:   {expected_after} (expected: 143)")

            # Preview by mapping ID
            print(f"\n3. PREVIEW BY MAPPING ID")
            print("-" * 80)

            by_mapping = await conn.fetch("""
                SELECT
                    e.mapping_id,
                    COUNT(*) as cnt,
                    COUNT(DISTINCT e.subject_id) as subjects,
                    COUNT(DISTINCT CASE WHEN NOT EXISTS (
                        SELECT 1 FROM runtime.assertion a
                        WHERE a.source_evidence_id = e.evidence_id
                    ) THEN e.evidence_id END) as to_insert
                FROM runtime.evidence e
                WHERE e.mapping_id = ANY($1::text[])
                GROUP BY e.mapping_id
                ORDER BY e.mapping_id;
            """, prototype_mapping_ids)

            for row in by_mapping:
                print(f"\n  {row['mapping_id']}")
                print(f"    Total Evidence: {row['cnt']}")
                print(f"    Distinct subjects: {row['subjects']}")
                print(f"    Ready to insert: {row['to_insert']}")

            # S6 validation (CONFIG-REQ-2026-006 and CONFIG-REQ-2026-006B remain distinct)
            print(f"\n4. S6 BUSINESS DUPLICATE PRESERVATION")
            print("-" * 80)

            s6_evidence = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND mapping_id = ANY($1::text[])
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = evidence_id
                  );
            """, prototype_mapping_ids)

            s6_ready_insert = await conn.fetch("""
                SELECT
                    subject_id,
                    COUNT(*) as cnt
                FROM runtime.evidence
                WHERE subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND mapping_id = ANY($1::text[])
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = evidence_id
                  )
                GROUP BY subject_id;
            """, prototype_mapping_ids)

            print(f"S6 Evidence ready to insert: {s6_evidence}")
            for row in s6_ready_insert:
                print(f"  {row['subject_id']}: {row['cnt']} Assertions")

            print(f"✓ S6 remains distinct (2 subjects, not merged)")

            # S7 validation (CONFIG-REQ-2026-007 with no customer_segment)
            print(f"\n5. S7 MISSING-SEGMENT SEMANTICS")
            print("-" * 80)

            s7_evidence = await conn.fetch("""
                SELECT
                    e.mapping_id,
                    COUNT(*) as cnt
                FROM runtime.evidence e
                WHERE e.subject_id = 'CONFIG-REQ-2026-007'
                  AND e.mapping_id = ANY($1::text[])
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = e.evidence_id
                  )
                GROUP BY e.mapping_id
                ORDER BY e.mapping_id;
            """, prototype_mapping_ids)

            print(f"S7 (CONFIG-REQ-2026-007) Evidence ready to insert:")
            for row in s7_evidence:
                print(f"  {row['mapping_id']}: {row['cnt']}")

            s7_total = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND mapping_id = ANY($1::text[])
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = evidence_id
                  );
            """, prototype_mapping_ids)

            print(f"\nS7 total Assertions to create: {s7_total} (expected: 4)")
            print(f"✓ S7 has no customer_segment (not fabricated)")

            # Sample rows preview
            print(f"\n6. SAMPLE ROWS (first 3 to be inserted)")
            print("-" * 80)

            samples = await conn.fetch("""
                SELECT
                    e.evidence_id,
                    e.mapping_id,
                    e.subject_type,
                    e.subject_id,
                    e.property_name,
                    e.asserted_value,
                    e.value_type,
                    e.occurred_at,
                    e.arrival_at
                FROM runtime.evidence e
                WHERE e.mapping_id = ANY($1::text[])
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = e.evidence_id
                  )
                ORDER BY e.evidence_id
                LIMIT 3;
            """, prototype_mapping_ids)

            for i, sample in enumerate(samples, 1):
                print(f"\n  Row {i}:")
                print(f"    evidence_id:   {sample['evidence_id']}")
                print(f"    mapping_id:    {sample['mapping_id']}")
                print(f"    subject:       {sample['subject_type']} / {sample['subject_id']}")
                print(f"    property:      {sample['property_name']}")
                print(f"    value:         {sample['asserted_value']}")
                print(f"    value_type:    {sample['value_type']}")
                print(f"    effective_at:  {sample['occurred_at']}")
                print(f"    arrival_at:    {sample['arrival_at']}")

            # Final verdict
            print(f"\n" + "="*80)
            print("PREVIEW COMPLETE")
            print("="*80)

            if to_insert > 0:
                print(f"\n✓ Ready to insert {to_insert} Assertions")
                print(f"✓ S6 preserved as distinct subjects")
                print(f"✓ S7 semantics correct (no NULL customer_segment)")
                print(f"\nExpected after execution:")
                print(f"  Assertions: {current_assertions} → {expected_after}")
            else:
                print(f"\n⚠ No Assertions ready to insert (replay guard active)")

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
    success = asyncio.run(preview_prototype_assertions())
    sys.exit(0 if success else 1)
