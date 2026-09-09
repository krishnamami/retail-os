#!/usr/bin/env python3
"""
STEP 5F.2 Execution — Evidence → Assertion Transformer
Executes transformation with pre-write and post-write validation gates
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


async def execute_prototype_assertions():
    """Transform prototype Evidence to Assertions"""
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
            print("STEP 5F.2 EXECUTION — EVIDENCE → ASSERTION TRANSFORMER")
            print("="*80)

            # PRE-WRITE GATE 1: Verify scope
            print("\nPRE-WRITE GATE 1: Verify prototype scope")
            print("-" * 80)

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

            print(f"Prototype Evidence found: {prototype_count}")
            
            if prototype_count != 36:
                print(f"✗ FAIL CLOSED: Prototype count {prototype_count} != 36")
                return False

            print("✓ Scope gate passed")

            # PRE-WRITE GATE 2: Verify current state
            print("\nPRE-WRITE GATE 2: Verify current database state")
            print("-" * 80)

            current_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion;
            """)

            print(f"Current Assertions: {current_assertions} (expected: 107)")
            
            if current_assertions != 107:
                print(f"✗ FAIL CLOSED: Current Assertions {current_assertions} != 107")
                return False

            print("✓ State gate passed")

            # PRE-WRITE GATE 3: Calculate insertion count
            print("\nPRE-WRITE GATE 3: Calculate ready-to-insert count")
            print("-" * 80)

            to_insert = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence e
                WHERE e.mapping_id = ANY($1::text[])
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = e.evidence_id
                  );
            """, prototype_mapping_ids)

            print(f"Ready to insert: {to_insert} (expected: 36)")
            
            if to_insert != 36:
                print(f"✗ FAIL CLOSED: Ready-to-insert {to_insert} != 36")
                return False

            print("✓ Calculation gate passed")

            # PRE-WRITE GATE 4: S6 and S7 preservation
            print("\nPRE-WRITE GATE 4: Business semantic preservation")
            print("-" * 80)

            s6_evidence = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND mapping_id = ANY($1::text[]);
            """, prototype_mapping_ids)

            s7_evidence = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND mapping_id = ANY($1::text[]);
            """, prototype_mapping_ids)

            s7_segment = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND mapping_id = 'CONF_REQ_SEGMENT';
            """)

            print(f"S6 distinct subjects (2 subjects × ~5 properties): {s6_evidence}")
            print(f"S7 Evidence ready to insert: {s7_evidence}")
            print(f"S7 CONF_REQ_SEGMENT Evidence: {s7_segment} (expected: 0)")
            
            if s7_segment > 0:
                print(f"✗ FAIL: S7 has customer_segment (unexpected)")
                return False

            print("✓ Semantic gates passed")

            # EXECUTION: INSERT PROTOTYPE ASSERTIONS
            print("\n" + "="*80)
            print("EXECUTION: INSERTING PROTOTYPE ASSERTIONS")
            print("="*80)

            result = await conn.execute("""
                INSERT INTO runtime.assertion
                (subject_type, subject_id, property_name, asserted_value, property_value_type, property_value_json, assertion_type, authority, authority_policy_id, effective_at, validity_horizon, arrival_at, source_evidence_id, supersedes_assertion_id, simulator_classification)
                SELECT
                    e.subject_type,
                    e.subject_id,
                    e.property_name,
                    e.asserted_value,
                    e.value_type AS property_value_type,
                    e.value_json AS property_value_json,
                    e.property_name || '_ASSERTION' AS assertion_type,
                    'evidence_direct' AS authority,
                    NULL AS authority_policy_id,
                    e.occurred_at AS effective_at,
                    NULL AS validity_horizon,
                    e.arrival_at,
                    e.evidence_id AS source_evidence_id,
                    NULL AS supersedes_assertion_id,
                    NULL AS simulator_classification
                FROM runtime.evidence e
                WHERE e.mapping_id = ANY($1::text[])
                  AND e.simulator_classification = 'PROTOTYPE_ASSUMPTION'
                  AND NOT EXISTS (SELECT 1 FROM runtime.assertion a WHERE a.source_evidence_id = e.evidence_id)
                ORDER BY e.evidence_id;
            """, prototype_mapping_ids)

            # Parse result string like "INSERT 0 36"
            inserted_count = int(result.split()[-1]) if result else 0
            print(f"✓ Inserted: {inserted_count} rows (expected: 36)")

            if inserted_count != 36:
                print(f"✗ EXECUTION FAILED: Inserted {inserted_count} rows instead of 36")
                return False

            # POST-WRITE VALIDATION
            print("\n" + "="*80)
            print("POST-WRITE VALIDATION")
            print("="*80)

            new_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")
            print(f"\nAssertion count: {new_count} (expected: 143)")
            
            if new_count != 143:
                print(f"✗ COUNT MISMATCH: {new_count} != 143")
                return False

            # Verify no duplicates via replay guard
            duplicates = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence e
                WHERE e.mapping_id = ANY($1::text[])
                  AND e.simulator_classification = 'PROTOTYPE_ASSUMPTION'
                  AND (
                    SELECT COUNT(*) FROM runtime.assertion a
                    WHERE a.source_evidence_id = e.evidence_id
                  ) > 1;
            """, prototype_mapping_ids)

            print(f"Duplicate assertions (should be 0): {duplicates}")
            
            if duplicates > 0:
                print(f"✗ DUPLICATES FOUND: {duplicates}")
                return False

            # Verify S6 preserved
            s6_assertions = await conn.fetchval("""
                SELECT COUNT(DISTINCT subject_id) FROM runtime.assertion
                WHERE subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND source_evidence_id IS NOT NULL;
            """)

            print(f"S6 distinct subjects in Assertions: {s6_assertions} (expected: 2)")
            
            if s6_assertions != 2:
                print(f"✗ S6 INTEGRITY LOST: {s6_assertions} != 2")
                return False

            # Verify S7 semantics
            s7_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND source_evidence_id IS NOT NULL;
            """)

            s7_segment_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND property_name = 'customer_segment'
                  AND source_evidence_id IS NOT NULL;
            """)

            print(f"S7 Assertions created: {s7_assertions} (expected: 4)")
            print(f"S7 customer_segment Assertions: {s7_segment_assertions} (expected: 0)")
            
            if s7_assertions != 4:
                print(f"✗ S7 COUNT WRONG: {s7_assertions} != 4")
                return False
            
            if s7_segment_assertions > 0:
                print(f"✗ S7 SEGMENT FABRICATED: {s7_segment_assertions} > 0")
                return False

            print("\n" + "="*80)
            print("✓ STEP 5F.2 EXECUTION COMPLETE")
            print("="*80)
            print(f"\nTransformation Summary:")
            print(f"  Assertions: 107 → 143 (+36)")
            print(f"  S6 preserved: 2 distinct subjects")
            print(f"  S7 correct: 4 Assertions, no customer_segment")
            print(f"  Idempotency: 0 duplicates (replay guard active)")
            
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
    success = asyncio.run(execute_prototype_assertions())
    sys.exit(0 if success else 1)
