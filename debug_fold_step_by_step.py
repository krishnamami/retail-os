#!/usr/bin/env python3
"""
STEP 5F.3 Debug Fold Logic Step-by-Step
Test each component individually with results and error logging
"""

import asyncio
import json
import sys
from typing import Dict, Any, List, Tuple

import asyncpg
import boto3


def get_postgres_credentials() -> Dict[str, Any]:
    secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
    response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
    return json.loads(response['SecretString'])


async def run_step(conn, step_num: int, step_name: str, sql: str) -> Tuple[bool, str, any]:
    """Run a single step and capture result or error"""
    try:
        result = await conn.fetch(sql) if 'SELECT' in sql else await conn.execute(sql)
        return (True, step_name, result)
    except Exception as e:
        return (False, step_name, f"{type(e).__name__}: {str(e)}")


async def debug_fold():
    """Debug Fold logic step by step"""
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
            print("STEP 5F.3 DEBUG FOLD LOGIC - STEP BY STEP")
            print("="*80)

            results = []
            step_counter = 1

            # Step 1: Drop previous debug tables if they exist
            print(f"\nStep {step_counter}: Cleanup previous debug tables")
            print("-" * 80)
            try:
                await conn.execute("DROP TABLE IF EXISTS debug_fold_results;")
                await conn.execute("DROP TABLE IF EXISTS temp_subject_snapshots;")
                await conn.execute("DROP TABLE IF EXISTS temp_applicable_properties;")
                print("✓ Cleanup successful")
                results.append((True, "Cleanup", "Tables dropped"))
            except Exception as e:
                print(f"✗ Cleanup error: {str(e)}")
                results.append((False, "Cleanup", str(e)))
            step_counter += 1

            # Step 2: Create debug results table
            print(f"\nStep {step_counter}: Create debug results table")
            print("-" * 80)
            try:
                await conn.execute("""
                    CREATE TEMP TABLE debug_fold_results (
                        step_num INT,
                        step_name TEXT,
                        status TEXT,
                        row_count INT,
                        error_msg TEXT,
                        details TEXT
                    );
                """)
                print("✓ Debug table created")
                results.append((True, "Create debug table", "Table created"))
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                results.append((False, "Create debug table", str(e)))
                return False
            step_counter += 1

            # Step 3: Test applicable_properties for each subject type
            print(f"\nStep {step_counter}: Test applicable_properties CTE")
            print("-" * 80)

            subject_types = [
                ('configuration', 'configuration'),
                ('launch', 'launch'),
                ('material', 'material'),
                ('sku', 'sku'),
                ('product', 'product'),
                ('configuration_request', 'configuration_request'),
            ]

            for subject_type, subject_prefix in subject_types:
                try:
                    count = await conn.fetchval(f"""
                        SELECT COUNT(DISTINCT subject_id) FROM runtime.assertion
                        WHERE subject_type = '{subject_type}';
                    """)
                    status = "✓ OK" if count > 0 else "⊘ No rows"
                    print(f"  {subject_type:30} {count} subjects {status}")
                    results.append((True, f"Subjects: {subject_type}", f"{count} subjects"))
                except Exception as e:
                    print(f"  {subject_type:30} ✗ ERROR")
                    print(f"    {str(e)}")
                    results.append((False, f"Subjects: {subject_type}", str(e)))
            step_counter += 1

            # Step 4: Create temp_applicable_properties
            print(f"\nStep {step_counter}: Build temp_applicable_properties")
            print("-" * 80)

            applicable_sql = """
            CREATE TEMP TABLE temp_applicable_properties AS
            SELECT 'configuration' AS subject_type, subject_id, 'sap_con_hierarchy_code' AS property_name
            FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a
            UNION ALL
            SELECT 'configuration', subject_id, 'sap_con_load_actor' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration') a
            UNION ALL
            SELECT 'launch', subject_id, 'change_requested_by' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'launch') a
            UNION ALL
            SELECT 'material', subject_id, 'material_status' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'material') a
            UNION ALL
            SELECT 'sku', subject_id, 'pricing_confirmed' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'sku') a
            UNION ALL
            SELECT 'product', subject_id, 'product_name' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'product') a
            UNION ALL
            SELECT 'product', subject_id, 'launch_reference' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'product') a
            UNION ALL
            SELECT 'configuration_request', subject_id, 'product_reference' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
            UNION ALL
            SELECT 'configuration_request', subject_id, 'launch_reference' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
            UNION ALL
            SELECT 'configuration_request', subject_id, 'geography' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
            UNION ALL
            SELECT 'configuration_request', subject_id, 'term_months' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a
            UNION ALL
            SELECT 'configuration_request', subject_id, 'customer_segment' FROM (SELECT DISTINCT subject_id FROM runtime.assertion WHERE subject_type = 'configuration_request') a;
            """

            try:
                await conn.execute(applicable_sql)
                count = await conn.fetchval("SELECT COUNT(*) FROM temp_applicable_properties;")
                print(f"✓ Applicable properties created: {count} rows")
                results.append((True, "Applicable properties", f"{count} rows"))
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                results.append((False, "Applicable properties", str(e)))
            step_counter += 1

            # Step 5: Verify fold_resolve_value function
            print(f"\nStep {step_counter}: Test fold_resolve_value function")
            print("-" * 80)

            try:
                sample = await conn.fetchrow("""
                    SELECT subject_type, subject_id, property_name
                    FROM temp_applicable_properties
                    LIMIT 1;
                """)

                if sample:
                    try:
                        result = await conn.fetchrow(f"""
                            SELECT runtime.fold_resolve_value(
                                '2026-06-20 10:45:00+00'::TIMESTAMPTZ,
                                '{sample['subject_type']}'::TEXT,
                                '{sample['subject_id']}'::TEXT,
                                '{sample['property_name']}'::TEXT
                            ) AS result;
                        """)
                        if result:
                            print(f"✓ fold_resolve_value works")
                            print(f"  Sample: {sample['subject_type']}.{sample['subject_id']}.{sample['property_name']}")
                            results.append((True, "fold_resolve_value", "Function works"))
                        else:
                            print(f"✗ fold_resolve_value returned NULL")
                            results.append((False, "fold_resolve_value", "Returned NULL"))
                    except Exception as e:
                        print(f"✗ fold_resolve_value error: {str(e)}")
                        results.append((False, "fold_resolve_value", str(e)))
                else:
                    print(f"⊘ No sample properties found")
                    results.append((False, "fold_resolve_value", "No sample data"))
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                results.append((False, "fold_resolve_value", str(e)))
            step_counter += 1

            # Step 6: Get KB and Policy versions
            print(f"\nStep {step_counter}: Verify KB and Policy versions")
            print("-" * 80)

            try:
                kb_version = await conn.fetchval("""
                    SELECT kb_version FROM runtime.governed_knowledge_base
                    WHERE is_active = true
                    ORDER BY created_at DESC LIMIT 1;
                """)
                if kb_version:
                    print(f"✓ KB version: {kb_version}")
                    results.append((True, "KB version", kb_version))
                else:
                    print(f"✗ No active KB version found")
                    results.append((False, "KB version", "No active KB version"))
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                results.append((False, "KB version", str(e)))

            try:
                policy_version = await conn.fetchval("""
                    SELECT policy_version FROM runtime.governed_policy
                    WHERE is_active = true
                    ORDER BY created_at DESC LIMIT 1;
                """)
                if policy_version:
                    print(f"✓ Policy version: {policy_version}")
                    results.append((True, "Policy version", policy_version))
                else:
                    print(f"✗ No active policy version found")
                    results.append((False, "Policy version", "No active policy version"))
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                results.append((False, "Policy version", str(e)))
            step_counter += 1

            # Step 7: Summary
            print("\n" + "="*80)
            print("DEBUG RESULTS SUMMARY")
            print("="*80)

            successes = sum(1 for s, _, _ in results if s)
            failures = sum(1 for s, _, _ in results if not s)

            print(f"\n✓ Successes: {successes}")
            print(f"✗ Failures: {failures}")

            print("\nDetailed Results:")
            print("-" * 80)
            for success, step_name, detail in results:
                status = "✓ OK" if success else "✗ FAIL"
                print(f"{status} {step_name:40} {str(detail)[:60]}")

            # Store results in database debug table
            print("\n" + "="*80)
            print("STORING RESULTS IN DATABASE")
            print("="*80)

            try:
                for success, step_name, detail in results:
                    await conn.execute("""
                        INSERT INTO debug_fold_results (step_name, status, details)
                        VALUES ($1, $2, $3);
                    """, step_name, "OK" if success else "FAIL", str(detail)[:1000])

                print("✓ Results stored in debug_fold_results table")
                print("\nQuery to view results:")
                print("  SELECT * FROM debug_fold_results;")
            except Exception as e:
                print(f"✗ Error storing results: {str(e)}")

            await pool.close()
            return successes == len(results)

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(debug_fold())
    sys.exit(0 if success else 1)
