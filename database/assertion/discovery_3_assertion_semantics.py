#!/usr/bin/env python3
"""
STEP 5F.1 Discovery — Understand Evidence → Assertion Semantics (MECHANICALLY CORRECTED)
READ-ONLY: No database writes
Mechanical fixes:
1. Use real runtime.evidence.mapping_id column (not evidence_lineage->>'mapping_id')
2. Proper NULL-safe baseline predicate
3. Use pg_constraint catalog for FK (not invalid information_schema columns)
4. Safe asyncpg pool lifecycle
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


async def inspect_assertion_semantics():
    """Understand how Evidence maps to Assertions — MECHANICALLY CORRECTED"""
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
            print("STEP 5F.1 DISCOVERY — EVIDENCE → ASSERTION SEMANTICS")
            print("="*80)

            # Check actual Assertion columns
            print("\n1. ASSERTION TABLE COLUMNS (actual)")
            print("-" * 80)

            assertion_columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'runtime' AND table_name = 'assertion'
                ORDER BY ordinal_position;
            """)

            for col in assertion_columns:
                print(f"  {col['column_name']:30} {col['data_type']}")

            # MECHANICAL FIX 1: Use real mapping_id column
            print("\n2. EVIDENCE PARTITION (using real mapping_id column)")
            print("-" * 80)

            # First check for NULL mapping_id values
            null_mapping_count = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence WHERE mapping_id IS NULL;
            """)

            print(f"Evidence rows with NULL mapping_id: {null_mapping_count}")

            prototype_mapping_ids = [
                'PRODUCT_DEF_NAME',
                'PRODUCT_DEF_LAUNCH',
                'CONF_REQ_PRODUCT',
                'CONF_REQ_LAUNCH',
                'CONF_REQ_GEO',
                'CONF_REQ_TERM',
                'CONF_REQ_SEGMENT'
            ]

            # Count using real mapping_id column
            prototype_count = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE mapping_id = ANY($1::text[]);
            """, prototype_mapping_ids)

            total_evidence = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence;
            """)

            # MECHANICAL FIX 2: Proper NULL-safe baseline predicate
            baseline_count = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE NOT (mapping_id = ANY($1::text[]))
                  AND mapping_id IS NOT NULL;
            """, prototype_mapping_ids)

            # Partition verification
            partition_sum = prototype_count + baseline_count + null_mapping_count

            print(f"\nTotal Evidence:                  {total_evidence}")
            print(f"Prototype Evidence (mapping_id):  {prototype_count} (expected: 36)")
            print(f"Baseline Evidence:               {baseline_count} (expected: 107)")
            print(f"NULL mapping_id:                 {null_mapping_count} (expected: 0)")
            print(f"Partition sum:                   {partition_sum}")

            if partition_sum != total_evidence:
                print(f"\n✗ FAIL CLOSED: Partition sum {partition_sum} != Total {total_evidence}")
                return False

            if prototype_count != 36:
                print(f"\n✗ FAIL CLOSED: Prototype count {prototype_count} != 36")
                return False

            if baseline_count != 107:
                print(f"\n✗ FAIL CLOSED: Baseline count {baseline_count} != 107")
                return False

            print("✓ Evidence partition verified: 107 baseline + 36 prototype = 143 total")

            # Count Assertions
            assertion_count = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion;
            """)
            print(f"\nAssertions:                      {assertion_count} (expected: 107)")

            # CORRECTION 2: Baseline/Prototype unmapped Evidence separately
            print("\n3. UNMAPPED EVIDENCE (Pre-write state verification)")
            print("-" * 80)

            baseline_with_assertion = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence e
                WHERE NOT (mapping_id = ANY($1::text[]))
                  AND mapping_id IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = e.evidence_id
                  );
            """, prototype_mapping_ids)

            baseline_without_assertion = baseline_count - baseline_with_assertion

            prototype_with_assertion = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence e
                WHERE mapping_id = ANY($1::text[])
                  AND EXISTS (
                    SELECT 1 FROM runtime.assertion a
                    WHERE a.source_evidence_id = e.evidence_id
                  );
            """, prototype_mapping_ids)

            prototype_without_assertion = prototype_count - prototype_with_assertion

            print(f"Baseline Evidence with Assertion:    {baseline_with_assertion} (expected: 107)")
            print(f"Baseline Evidence without Assertion: {baseline_without_assertion} (expected: 0)")
            print(f"Prototype Evidence with Assertion:   {prototype_with_assertion} (expected: 0)")
            print(f"Prototype Evidence without Assertion: {prototype_without_assertion} (expected: 36)")

            # 1:1 baseline lineage check
            print("\n4. BASELINE LINEAGE 1:1 VERIFICATION")
            print("-" * 80)

            null_source = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion
                WHERE source_evidence_id IS NULL;
            """)

            orphan_assertions = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                WHERE a.source_evidence_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM runtime.evidence e
                    WHERE e.evidence_id = a.source_evidence_id
                  );
            """)

            # Multiple Assertions per baseline Evidence
            baseline_multi_assertion = await conn.fetchval("""
                SELECT COUNT(*) FROM (
                  SELECT source_evidence_id, COUNT(*) as cnt
                  FROM runtime.assertion a
                  WHERE source_evidence_id IS NOT NULL
                    AND EXISTS (
                      SELECT 1 FROM runtime.evidence e
                      WHERE e.evidence_id = a.source_evidence_id
                        AND NOT (e.mapping_id = ANY($1::text[]))
                        AND e.mapping_id IS NOT NULL
                    )
                  GROUP BY source_evidence_id
                  HAVING COUNT(*) > 1
                ) dups;
            """, prototype_mapping_ids)

            print(f"Assertions linked to baseline Evidence:      {baseline_with_assertion} (expected: 107)")
            print(f"Assertions with NULL source_evidence_id:     {null_source} (expected: 0)")
            print(f"Orphaned Assertions (missing Evidence):      {orphan_assertions} (expected: 0)")
            print(f"Baseline Evidence with >1 Assertion:         {baseline_multi_assertion} (expected: 0)")

            # VALUE FIELD MAPPING
            print("\n5. VALUE FIELD MAPPING (Evidence → Assertion)")
            print("-" * 80)

            has_property_value_type = await conn.fetchval("""
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'runtime' AND table_name = 'assertion'
                    AND column_name = 'property_value_type'
                );
            """)

            has_property_value_json = await conn.fetchval("""
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'runtime' AND table_name = 'assertion'
                    AND column_name = 'property_value_json'
                );
            """)

            print(f"Assertion.property_value_type exists:  {has_property_value_type}")
            print(f"Assertion.property_value_json exists:  {has_property_value_json}")

            # Verify asserted_value mapping across ALL baseline
            mismatched_asserted = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
                WHERE NOT (e.mapping_id = ANY($1::text[]))
                  AND e.mapping_id IS NOT NULL
                  AND (a.asserted_value IS DISTINCT FROM e.asserted_value);
            """, prototype_mapping_ids)

            print(f"Asserted value mismatches (baseline): {mismatched_asserted} (expected: 0)")

            # EFFECTIVE_AT TIMESTAMP MAPPING across ALL baseline
            print("\n6. EFFECTIVE_AT TIMESTAMP MAPPING (all baseline Evidence→Assertion)")
            print("-" * 80)

            eff_at_occurred = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
                WHERE NOT (e.mapping_id = ANY($1::text[]))
                  AND e.mapping_id IS NOT NULL
                  AND a.effective_at = e.occurred_at;
            """, prototype_mapping_ids)

            eff_at_recorded = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
                WHERE NOT (e.mapping_id = ANY($1::text[]))
                  AND e.mapping_id IS NOT NULL
                  AND a.effective_at = e.recorded_at;
            """, prototype_mapping_ids)

            eff_at_arrival = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
                WHERE NOT (e.mapping_id = ANY($1::text[]))
                  AND e.mapping_id IS NOT NULL
                  AND a.effective_at = e.arrival_at;
            """, prototype_mapping_ids)

            eff_at_other = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
                WHERE NOT (e.mapping_id = ANY($1::text[]))
                  AND e.mapping_id IS NOT NULL
                  AND a.effective_at NOT IN (e.occurred_at, e.recorded_at, e.arrival_at);
            """, prototype_mapping_ids)

            print(f"Assertion.effective_at = Evidence.occurred_at: {eff_at_occurred}")
            print(f"Assertion.effective_at = Evidence.recorded_at: {eff_at_recorded}")
            print(f"Assertion.effective_at = Evidence.arrival_at:  {eff_at_arrival}")
            print(f"Assertion.effective_at = other/null:           {eff_at_other} (expected: 0)")

            # Verify arrival_at mapping
            arrival_mismatch = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion a
                JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
                WHERE NOT (e.mapping_id = ANY($1::text[]))
                  AND e.mapping_id IS NOT NULL
                  AND (a.arrival_at IS DISTINCT FROM e.arrival_at);
            """, prototype_mapping_ids)

            print(f"Assertion.arrival_at mismatch: {arrival_mismatch} (expected: 0)")

            # IDEMPOTENCY AND FK
            print("\n7. ASSERTION IDEMPOTENCY AND FK ENFORCEMENT")
            print("-" * 80)

            # Check for UNIQUE constraints
            unique_constraints = await conn.fetch("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_schema = 'runtime' AND table_name = 'assertion'
                  AND constraint_type = 'UNIQUE';
            """)

            print(f"UNIQUE constraints on assertion: {len(unique_constraints)}")
            if unique_constraints:
                for uc in unique_constraints:
                    cols = await conn.fetch(f"""
                        SELECT column_name
                        FROM information_schema.key_column_usage
                        WHERE table_schema = 'runtime' AND table_name = 'assertion'
                          AND constraint_name = '{uc['constraint_name']}'
                        ORDER BY ordinal_position;
                    """)
                    col_names = ', '.join([c['column_name'] for c in cols])
                    print(f"  {uc['constraint_name']}: ({col_names})")

            # Check FK using pg_constraint catalog
            print("\nForeign Key Constraints (using pg_constraint):")
            
            fks = await conn.fetch("""
                SELECT
                    constraint_name,
                    a.attname as column_name,
                    referenced_table.relname as ref_table,
                    ref_schema.nspname as ref_schema,
                    a2.attname as ref_column
                FROM (
                    SELECT
                        constraint_oid,
                        conname as constraint_name,
                        conrelid,
                        confrelid,
                        conkey,
                        confkey
                    FROM pg_constraint
                    WHERE contype = 'f'
                ) fk
                JOIN pg_class referenced_table ON fk.confrelid = referenced_table.oid
                JOIN pg_namespace ref_schema ON referenced_table.relnamespace = ref_schema.oid
                JOIN pg_attribute a ON a.attrelid = fk.conrelid AND a.attnum = ANY(fk.conkey)
                JOIN pg_attribute a2 ON a2.attrelid = fk.confrelid AND a2.attnum = ANY(fk.confkey)
                WHERE pg_table_is_visible(fk.conrelid)
                  AND fk.conrelid IN (
                    SELECT oid FROM pg_class WHERE relname = 'assertion'
                      AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'runtime')
                  );
            """)

            if fks:
                for fk in fks:
                    print(f"  {fk['constraint_name']}: {fk['column_name']} → {fk['ref_schema']}.{fk['ref_table']}.{fk['ref_column']}")
            else:
                print("  No foreign keys found")

            print("\n" + "="*80)
            print("STEP 5F.1 DISCOVERY COMPLETE")
            print("="*80)
            
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
    success = asyncio.run(inspect_assertion_semantics())
    sys.exit(0 if success else 1)
