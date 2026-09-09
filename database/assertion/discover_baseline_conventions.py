#!/usr/bin/env python3
"""
STEP 5F.2 Discovery — Baseline Assertion Conventions
Discover exact baseline patterns for: assertion_type, authority_policy_id, validity_horizon, simulator_classification
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


async def discover_baseline_conventions():
    """Discover baseline Assertion conventions"""
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
            print("STEP 5F.2 DISCOVERY — BASELINE ASSERTION CONVENTIONS")
            print("="*80)

            # 1. ASSERTION_TYPE VALUES
            print("\n1. BASELINE assertion_type VALUES")
            print("-" * 80)

            assertion_types = await conn.fetch("""
                SELECT assertion_type, COUNT(*) as cnt
                FROM runtime.assertion
                GROUP BY assertion_type
                ORDER BY cnt DESC;
            """)

            if assertion_types:
                for at in assertion_types:
                    print(f"  {str(at['assertion_type']):40} ({at['cnt']} rows)")
            else:
                print("  No assertion_type found")

            # 2. AUTHORITY_POLICY_ID VALUES
            print("\n2. BASELINE authority_policy_id VALUES")
            print("-" * 80)

            authority_policy_ids = await conn.fetch("""
                SELECT authority_policy_id, COUNT(*) as cnt
                FROM runtime.assertion
                GROUP BY authority_policy_id
                ORDER BY cnt DESC;
            """)

            if authority_policy_ids:
                for api in authority_policy_ids:
                    val = api['authority_policy_id'] or 'NULL'
                    print(f"  {str(val):40} ({api['cnt']} rows)")
            else:
                print("  No authority_policy_id found")

            # 3. VALIDITY_HORIZON VALUES
            print("\n3. BASELINE validity_horizon VALUES")
            print("-" * 80)

            validity_horizons = await conn.fetch("""
                SELECT validity_horizon, COUNT(*) as cnt
                FROM runtime.assertion
                GROUP BY validity_horizon
                ORDER BY cnt DESC;
            """)

            if validity_horizons:
                for vh in validity_horizons:
                    val = vh['validity_horizon'] or 'NULL'
                    print(f"  {str(val):40} ({vh['cnt']} rows)")
            else:
                print("  No validity_horizon found")

            # 4. SIMULATOR_CLASSIFICATION COLUMN EXISTENCE
            print("\n4. SIMULATOR_CLASSIFICATION ON runtime.assertion")
            print("-" * 80)

            has_sim_class = await conn.fetchval("""
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'runtime' AND table_name = 'assertion'
                    AND column_name = 'simulator_classification'
                );
            """)

            print(f"Column exists: {has_sim_class}")

            if has_sim_class:
                sim_classes = await conn.fetch("""
                    SELECT simulator_classification, COUNT(*) as cnt
                    FROM runtime.assertion
                    GROUP BY simulator_classification
                    ORDER BY cnt DESC;
                """)

                if sim_classes:
                    for sc in sim_classes:
                        val = sc['simulator_classification'] or 'NULL'
                        print(f"  {str(val):40} ({sc['cnt']} rows)")

            # 5. SAMPLE BASELINE ASSERTION
            print("\n5. SAMPLE BASELINE ASSERTION ROW")
            print("-" * 80)

            sample = await conn.fetchrow("""
                SELECT
                    assertion_id,
                    subject_type,
                    subject_id,
                    property_name,
                    asserted_value,
                    property_value_type,
                    assertion_type,
                    authority,
                    authority_policy_id,
                    effective_at,
                    validity_horizon,
                    arrival_at,
                    source_evidence_id,
                    supersedes_assertion_id,
                    simulator_classification
                FROM runtime.assertion
                LIMIT 1;
            """)

            if sample:
                for key, val in dict(sample).items():
                    val_str = str(val)[:60] if val else "NULL"
                    print(f"  {key:30} = {val_str}")

            # 6. DIRECT EVIDENCE ASSERTIONS
            print("\n6. ASSERTIONS WITH source_evidence_id (direct Evidence mapping)")
            print("-" * 80)

            direct_count = await conn.fetchval("""
                SELECT COUNT(*) FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL;
            """)

            print(f"Assertions with source_evidence_id: {direct_count}")

            # Sample one
            direct_sample = await conn.fetchrow("""
                SELECT
                    assertion_id,
                    assertion_type,
                    authority_policy_id,
                    validity_horizon,
                    source_evidence_id
                FROM runtime.assertion
                WHERE source_evidence_id IS NOT NULL
                LIMIT 1;
            """)

            if direct_sample:
                print(f"\nSample direct assertion:")
                print(f"  assertion_type:        {direct_sample['assertion_type']}")
                print(f"  authority_policy_id:   {direct_sample['authority_policy_id']}")
                print(f"  validity_horizon:      {direct_sample['validity_horizon']}")
                print(f"  source_evidence_id:    {direct_sample['source_evidence_id']}")

            print("\n" + "="*80)
            print("BASELINE CONVENTIONS DISCOVERED")
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
    success = asyncio.run(discover_baseline_conventions())
    sys.exit(0 if success else 1)
