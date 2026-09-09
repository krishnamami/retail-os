#!/usr/bin/env python3
"""
STEP 5E.3A Run 1 Post-Validation
READ-ONLY: Validates 36 Evidence rows after Run 1
No database writes
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


async def validate_run1():
    """Validate Run 1 results - READ ONLY"""
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
        
        conn = await pool.acquire()
        
        print("\n" + "="*80)
        print("STEP 5E.3A RUN 1 POST-VALIDATION (READ-ONLY)")
        print("="*80)
        
        # Overall counts
        print("\n1. OVERALL COUNTS")
        print("-" * 80)
        
        raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw.raw_event;")
        evidence_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
        assertion_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.assertion;")
        fold_count = await conn.fetchval("SELECT COUNT(*) FROM runtime.fold;")
        
        print(f"Raw: {raw_count} (expected: 177)")
        print(f"Evidence: {evidence_count} (expected: 143)")
        print(f"Assertions: {assertion_count} (expected: 107)")
        print(f"Fold: {fold_count} (expected: 51)")
        
        overall_ok = (raw_count == 177 and evidence_count == 143 and 
                     assertion_count == 107 and fold_count == 51)
        
        # Prototype Evidence breakdown
        print("\n2. PROTOTYPE EVIDENCE BREAKDOWN BY MAPPING")
        print("-" * 80)
        
        mappings = await conn.fetch("""
            SELECT mapping_id, COUNT(*) as count
            FROM runtime.evidence
            WHERE evidence_lineage->>'event_type' IN ('PRODUCT_DEFINED', 'CONFIGURATION_REQUESTED')
              AND simulator_classification = 'PROTOTYPE_ASSUMPTION'
            GROUP BY mapping_id
            ORDER BY mapping_id;
        """)
        
        mapping_counts = {}
        total_new = 0
        
        for row in mappings:
            mapping_id = row['mapping_id']
            count = row['count']
            mapping_counts[mapping_id] = count
            total_new += count
            print(f"{mapping_id}: {count}")
        
        print(f"\nTotal new Evidence: {total_new} (expected: 36)")
        
        mapping_ok = (
            mapping_counts.get('PRODUCT_DEF_NAME', 0) == 1 and
            mapping_counts.get('PRODUCT_DEF_LAUNCH', 0) == 1 and
            mapping_counts.get('CONF_REQ_PRODUCT', 0) == 7 and
            mapping_counts.get('CONF_REQ_LAUNCH', 0) == 7 and
            mapping_counts.get('CONF_REQ_GEO', 0) == 7 and
            mapping_counts.get('CONF_REQ_TERM', 0) == 7 and
            mapping_counts.get('CONF_REQ_SEGMENT', 0) == 6 and
            total_new == 36
        )
        
        if not mapping_ok:
            print("✗ ERROR: Mapping counts incorrect")
            await pool.close()
            return False
        
        # S7 validation
        print("\n3. S7 VALIDATION")
        print("-" * 80)
        
        s7_raw_id = await conn.fetchval("""
            SELECT raw_event_id FROM raw.raw_event
            WHERE event_type = 'CONFIGURATION_REQUESTED'
              AND payload->>'segment' IS NULL
              AND payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
            LIMIT 1;
        """)
        
        if s7_raw_id:
            s7_count = await conn.fetchval(
                "SELECT COUNT(*) FROM runtime.evidence WHERE raw_event_id = %s AND simulator_classification = 'PROTOTYPE_ASSUMPTION';",
                s7_raw_id
            )
            s7_segment_count = await conn.fetchval(
                "SELECT COUNT(*) FROM runtime.evidence WHERE raw_event_id = %s AND mapping_id = 'CONF_REQ_SEGMENT';",
                s7_raw_id
            )
            
            print(f"S7 total Evidence rows: {s7_count} (expected: 4)")
            print(f"S7 segment Evidence rows: {s7_segment_count} (expected: 0)")
            
            s7_ok = (s7_count == 4 and s7_segment_count == 0)
            if s7_ok:
                print("✓ S7 correctly has 4 Evidence and NO segment Evidence")
            else:
                print("✗ ERROR: S7 Evidence count incorrect")
                await pool.close()
                return False
        else:
            print("✗ ERROR: S7 record not found")
            await pool.close()
            return False
        
        # S6 validation
        print("\n4. S6 INDEPENDENCE VALIDATION")
        print("-" * 80)
        
        s6_records = await conn.fetch("""
            SELECT DISTINCT r.raw_event_id, r.payload->>'configuration_request_id' as config_id
            FROM raw.raw_event r
            WHERE r.event_type = 'CONFIGURATION_REQUESTED'
              AND r.payload->>'source_record_id' IN ('CONFIG_REQ_2026_005', 'CONFIG_REQ_2026_006')
              AND r.payload->>'simulator_classification' = 'PROTOTYPE_ASSUMPTION'
            ORDER BY r.payload->>'source_record_id';
        """)
        
        s6_ok = True
        for row in s6_records:
            raw_id = row['raw_event_id']
            config_id = row['config_id']
            
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM runtime.evidence WHERE raw_event_id = %s AND simulator_classification = 'PROTOTYPE_ASSUMPTION';",
                raw_id
            )
            
            print(f"S6 Config {config_id}: {count} Evidence rows")
            if count != 5:
                s6_ok = False
        
        if len(s6_records) != 2:
            print(f"✗ ERROR: Expected 2 S6 records, found {len(s6_records)}")
            await pool.close()
            return False
        
        if s6_ok:
            print("✓ S6a and S6b each have 5 Evidence rows")
        else:
            print("✗ ERROR: S6 Evidence counts incorrect")
            await pool.close()
            return False
        
        # Provenance validation
        print("\n5. PROVENANCE VALIDATION")
        print("-" * 80)
        
        sim_class_count = await conn.fetchval("""
            SELECT COUNT(*) FROM runtime.evidence
            WHERE simulator_classification = 'PROTOTYPE_ASSUMPTION'
              AND evidence_lineage->>'event_type' IN ('PRODUCT_DEFINED', 'CONFIGURATION_REQUESTED');
        """)
        
        print(f"Evidence with simulator_classification='PROTOTYPE_ASSUMPTION': {sim_class_count} (expected: 36)")
        
        prov_ok = (sim_class_count == 36)
        if prov_ok:
            print("✓ All new Evidence marked as PROTOTYPE_ASSUMPTION")
        else:
            print("✗ ERROR: Provenance marking incorrect")
            await pool.close()
            return False
        
        # Lineage validation
        print("\n6. LINEAGE VALIDATION")
        print("-" * 80)
        
        lineage_count = await conn.fetchval("""
            SELECT COUNT(*) FROM runtime.evidence
            WHERE evidence_lineage IS NOT NULL
              AND evidence_lineage->>'raw_event_id' IS NOT NULL
              AND evidence_lineage->>'mapping_id' IS NOT NULL
              AND evidence_lineage->>'event_type' IN ('PRODUCT_DEFINED', 'CONFIGURATION_REQUESTED')
              AND simulator_classification = 'PROTOTYPE_ASSUMPTION';
        """)
        
        print(f"Evidence rows with complete lineage: {lineage_count} (expected: 36)")
        
        lineage_ok = (lineage_count == 36)
        if lineage_ok:
            print("✓ All Evidence rows have complete lineage")
        else:
            print("✗ ERROR: Lineage validation failed")
            await pool.close()
            return False
        
        # Summary
        print("\n" + "="*80)
        print("RUN 1 VALIDATION SUMMARY")
        print("="*80)
        
        all_checks = overall_ok and mapping_ok and prov_ok and lineage_ok
        
        if all_checks:
            print("✓ ALL RUN 1 VALIDATIONS PASSED")
        else:
            print("✗ SOME RUN 1 VALIDATIONS FAILED")
        
        await pool.close()
        return all_checks
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        return False


if __name__ == '__main__':
    success = asyncio.run(validate_run1())
    sys.exit(0 if success else 1)
