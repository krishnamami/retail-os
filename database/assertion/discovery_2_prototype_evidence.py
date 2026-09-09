#!/usr/bin/env python3
"""
STEP 5F.1 Discovery — Inspect 36 New Prototype Evidence Rows
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


async def inspect_prototype_evidence():
    """Inspect the 36 new prototype Evidence rows"""
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
            print("STEP 5F.1 DISCOVERY — 36 NEW PROTOTYPE EVIDENCE ROWS")
            print("="*80)

            # Get total prototype count
            total = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE simulator_classification = 'PROTOTYPE_ASSUMPTION';
            """)
            print(f"\nTotal prototype Evidence: {total}")

            # PRODUCT_DEFINED
            print("\n1. PRODUCT_DEFINED EVIDENCE (expected: 2 rows)")
            print("-" * 80)

            product_evidence = await conn.fetch("""
                SELECT
                    raw_event_id,
                    evidence_lineage->>'mapping_id' as mapping_id,
                    subject_type,
                    subject_id,
                    property_name,
                    asserted_value,
                    value_type
                FROM runtime.evidence
                WHERE evidence_lineage->>'event_type' = 'PRODUCT_DEFINED'
                  AND simulator_classification = 'PROTOTYPE_ASSUMPTION'
                ORDER BY evidence_lineage->>'mapping_id';
            """)

            print(f"\nFound {len(product_evidence)} rows:")
            for ev in product_evidence:
                print(f"\n  Mapping: {ev['mapping_id']}")
                print(f"    subject_type: {ev['subject_type']}")
                print(f"    subject_id: {ev['subject_id']}")
                print(f"    property_name: {ev['property_name']}")
                print(f"    asserted_value: {ev['asserted_value']}")
                print(f"    value_type: {ev['value_type']}")

            # CONFIGURATION_REQUESTED
            print("\n2. CONFIGURATION_REQUESTED EVIDENCE (expected: 34 rows)")
            print("-" * 80)

            config_evidence = await conn.fetch("""
                SELECT
                    raw_event_id,
                    subject_type,
                    subject_id,
                    evidence_lineage->>'mapping_id' as mapping_id,
                    property_name,
                    asserted_value
                FROM runtime.evidence
                WHERE evidence_lineage->>'event_type' = 'CONFIGURATION_REQUESTED'
                  AND simulator_classification = 'PROTOTYPE_ASSUMPTION'
                ORDER BY subject_id, evidence_lineage->>'mapping_id';
            """)

            print(f"\nFound {len(config_evidence)} rows")

            # Group by subject
            by_subject = {}
            for ev in config_evidence:
                subj = ev['subject_id']
                if subj not in by_subject:
                    by_subject[subj] = []
                by_subject[subj].append(ev)

            for subject_id in sorted(by_subject.keys()):
                rows = by_subject[subject_id]
                print(f"\n  Subject: {subject_id} ({len(rows)} properties)")
                for row in rows:
                    print(f"    {row['property_name']:25} = {row['asserted_value']}")

            # S6 Analysis
            print("\n3. S6 DUPLICATE BUSINESS SCENARIO (CONFIG-REQ-2026-006 variants)")
            print("-" * 80)

            s6_subjects = await conn.fetch("""
                SELECT DISTINCT subject_id FROM runtime.evidence
                WHERE subject_type = 'configuration_request'
                  AND subject_id LIKE 'CONFIG-REQ-2026-006%'
                  AND simulator_classification = 'PROTOTYPE_ASSUMPTION'
                ORDER BY subject_id;
            """)

            print(f"\nS6 subjects found: {len(s6_subjects)}")
            for s in s6_subjects:
                print(f"  {s['subject_id']}")

            # Get S6 logical identity
            s6_identity = await conn.fetch("""
                SELECT
                    subject_id,
                    property_name,
                    asserted_value
                FROM runtime.evidence
                WHERE subject_id IN ('CONFIG-REQ-2026-006', 'CONFIG-REQ-2026-006B')
                  AND simulator_classification = 'PROTOTYPE_ASSUMPTION'
                ORDER BY subject_id, property_name;
            """)

            print("\nS6 logical identity (both should match):")
            for ev in s6_identity:
                print(f"  {ev['subject_id']:25} {ev['property_name']:25} = {ev['asserted_value']}")

            # S7 Analysis
            print("\n4. S7 MISSING SEGMENT (CONFIG-REQ-2026-007)")
            print("-" * 80)

            s7_evidence = await conn.fetch("""
                SELECT
                    property_name,
                    asserted_value
                FROM runtime.evidence
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND simulator_classification = 'PROTOTYPE_ASSUMPTION'
                ORDER BY property_name;
            """)

            print(f"\nS7 Evidence rows: {len(s7_evidence)}")
            for ev in s7_evidence:
                print(f"  {ev['property_name']:25} = {ev['asserted_value']}")

            s7_segment_check = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.evidence
                WHERE subject_id = 'CONFIG-REQ-2026-007'
                  AND property_name = 'customer_segment'
                  AND simulator_classification = 'PROTOTYPE_ASSUMPTION';
            """)

            print(f"\nS7 has customer_segment Evidence: {s7_segment_check > 0} (expected: False)")

            # Authority and lineage
            print("\n5. AUTHORITY AND LINEAGE (Prototype Evidence)")
            print("-" * 80)

            authorities = await conn.fetch("""
                SELECT DISTINCT
                    authority,
                    COUNT(*) as cnt
                FROM runtime.evidence
                WHERE simulator_classification = 'PROTOTYPE_ASSUMPTION'
                GROUP BY authority;
            """)

            print("\nAuthority values:")
            for auth in authorities:
                print(f"  {auth['authority']:30} ({auth['cnt']} rows)")

            # Check lineage structure
            sample_lineage = await conn.fetchval("""
                SELECT evidence_lineage FROM runtime.evidence
                WHERE simulator_classification = 'PROTOTYPE_ASSUMPTION'
                LIMIT 1;
            """)

            if sample_lineage:
                print("\nSample evidence_lineage structure:")
                import json as json_lib
                lineage = json_lib.loads(sample_lineage) if isinstance(sample_lineage, str) else sample_lineage
                for key, val in lineage.items():
                    print(f"  {key}: {val}")

            await pool.close()
            return True

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(inspect_prototype_evidence())
    sys.exit(0 if success else 1)
