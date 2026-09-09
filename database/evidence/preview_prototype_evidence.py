#!/usr/bin/env python3
"""
STEP 5E.3C — Preview Prototype Evidence (READ-ONLY)
Shows what Evidence WOULD be generated without inserting
Validates corrected extraction paths and Evidence structure
No database writes
"""

import asyncio
import json
import sys
from typing import Dict, Any
from pathlib import Path

import asyncpg
import boto3
from botocore.exceptions import ClientError


def get_postgres_credentials() -> Dict[str, Any]:
    """Retrieve PostgreSQL credentials from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
        return json.loads(response['SecretString'])
    except ClientError as e:
        print(f"✗ ERROR retrieving Secrets Manager: {str(e)}")
        sys.exit(1)


async def preview_evidence():
    """Preview Evidence generation without inserting"""
    credentials = get_postgres_credentials()
    
    print("="*80)
    print("STEP 5E.3C — PREVIEW PROTOTYPE EVIDENCE (READ-ONLY)")
    print("="*80)
    
    try:
        conn = await asyncpg.connect(
            host=credentials['host'],
            port=credentials['port'],
            user=credentials['username'],
            password=credentials['password'],
            database=credentials['dbname'],
            timeout=30.0,
            command_timeout=30.0,
        )
        
        # Get current counts
        current_evidence = await conn.fetchval("SELECT COUNT(*) FROM runtime.evidence;")
        print(f"\nCurrent Evidence count: {current_evidence}")
        
        print("\n" + "="*80)
        print("EVIDENCE PREVIEW (NO INSERTS)")
        print("="*80)
        
        # PRODUCT_DEFINED: 2 Evidence rows expected
        print("\n1. PRODUCT_DEFINED (1 Raw → 2 Evidence)")
        print("-" * 80)
        
        product_query = """
            SELECT
                raw_event_id,
                'PRODUCT_DEF_NAME' as mapping_id,
                'product_definition' as evidence_type,
                'product' as subject_type,
                payload->>'product_id' as subject_id,
                'product_name' as property_name,
                payload->'payload'->>'product_name' as asserted_value
            FROM raw.raw_event
            WHERE event_type = 'PRODUCT_DEFINED'
              AND payload->'payload'->>'product_name' IS NOT NULL
            UNION ALL
            SELECT
                raw_event_id,
                'PRODUCT_DEF_LAUNCH' as mapping_id,
                'product_definition' as evidence_type,
                'product' as subject_type,
                payload->>'product_id' as subject_id,
                'launch_reference' as property_name,
                payload->>'launch_id' as asserted_value
            FROM raw.raw_event
            WHERE event_type = 'PRODUCT_DEFINED'
        """
        
        product_evidence = await conn.fetch(product_query)
        print(f"\nExpected Product Evidence rows: {len(product_evidence)}")
        
        for ev in product_evidence:
            print(f"\n  mapping_id: {ev['mapping_id']}")
            print(f"    evidence_type: {ev['evidence_type']}")
            print(f"    subject_type: {ev['subject_type']}")
            print(f"    subject_id: {ev['subject_id']}")
            print(f"    property_name: {ev['property_name']}")
            print(f"    asserted_value: {ev['asserted_value']}")
        
        if len(product_evidence) != 2:
            print(f"\n✗ ERROR: Expected 2 PRODUCT_DEFINED Evidence, got {len(product_evidence)}")
            await conn.close()
            return False
        
        # CONFIGURATION_REQUESTED: 34 Evidence rows expected (30 complete + 4 S7)
        print("\n2. CONFIGURATION_REQUESTED (7 Raw → 34 Evidence)")
        print("-" * 80)
        
        config_query = """
            SELECT
                raw_event_id,
                source_record_id,
                'CONF_REQ_PRODUCT' as mapping_id,
                payload->'payload'->>'configuration_request_id' as subject_id,
                payload->'payload'->>'product_id' as asserted_value
            FROM raw.raw_event
            WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'product_id' IS NOT NULL
            UNION ALL
            SELECT
                raw_event_id,
                source_record_id,
                'CONF_REQ_LAUNCH' as mapping_id,
                payload->'payload'->>'configuration_request_id' as subject_id,
                payload->'payload'->>'launch_id' as asserted_value
            FROM raw.raw_event
            WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'launch_id' IS NOT NULL
            UNION ALL
            SELECT
                raw_event_id,
                source_record_id,
                'CONF_REQ_GEO' as mapping_id,
                payload->'payload'->>'configuration_request_id' as subject_id,
                payload->'payload'->>'geo' as asserted_value
            FROM raw.raw_event
            WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'geo' IS NOT NULL
            UNION ALL
            SELECT
                raw_event_id,
                source_record_id,
                'CONF_REQ_TERM' as mapping_id,
                payload->'payload'->>'configuration_request_id' as subject_id,
                payload->'payload'->>'term' as asserted_value
            FROM raw.raw_event
            WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'term' IS NOT NULL
            UNION ALL
            SELECT
                raw_event_id,
                source_record_id,
                'CONF_REQ_SEGMENT' as mapping_id,
                payload->'payload'->>'configuration_request_id' as subject_id,
                payload->'payload'->>'segment' as asserted_value
            FROM raw.raw_event
            WHERE event_type = 'CONFIGURATION_REQUESTED' AND payload->'payload'->>'segment' IS NOT NULL
            ORDER BY source_record_id, mapping_id
        """
        
        config_evidence = await conn.fetch(config_query)
        print(f"\nExpected Configuration Evidence rows: {len(config_evidence)}")
        
        # Group by source record
        evidence_by_source = {}
        for ev in config_evidence:
            source = ev['source_record_id']
            if source not in evidence_by_source:
                evidence_by_source[source] = []
            evidence_by_source[source].append(ev)
        
        for source in sorted(evidence_by_source.keys()):
            rows = evidence_by_source[source]
            print(f"\n  {source}: {len(rows)} rows")
            for row in rows:
                print(f"    - {row['mapping_id']}: {row['asserted_value']}")
        
        if len(config_evidence) != 34:
            print(f"\n✗ ERROR: Expected 34 CONFIGURATION_REQUESTED Evidence, got {len(config_evidence)}")
            await conn.close()
            return False
        
        # Validate S7 has exactly 4 Evidence (no segment)
        s7_evidence = [e for e in config_evidence if e['source_record_id'] == 'CONFIG_REQ_2026_007']
        if len(s7_evidence) != 4:
            print(f"\n✗ ERROR: Expected 4 S7 Evidence, got {len(s7_evidence)}")
            await conn.close()
            return False
        
        s7_has_segment = any(e['mapping_id'] == 'CONF_REQ_SEGMENT' for e in s7_evidence)
        if s7_has_segment:
            print(f"\n✗ ERROR: S7 should not have CONF_REQ_SEGMENT Evidence")
            await conn.close()
            return False
        
        print(f"\n  ✓ S7 has exactly 4 Evidence rows (no segment)")
        
        # Validate S6 (CONFIG_REQ_2026_005 and 006)
        s6a_evidence = [e for e in config_evidence if e['source_record_id'] == 'CONFIG_REQ_2026_005']
        s6b_evidence = [e for e in config_evidence if e['source_record_id'] == 'CONFIG_REQ_2026_006']
        
        if len(s6a_evidence) != 5 or len(s6b_evidence) != 5:
            print(f"\n✗ ERROR: S6a/S6b should each have 5 Evidence")
            await conn.close()
            return False
        
        # Verify different subject_ids (configuration_request_id)
        s6a_subject = s6a_evidence[0]['subject_id']
        s6b_subject = s6b_evidence[0]['subject_id']
        
        if s6a_subject == s6b_subject:
            print(f"\n✗ ERROR: S6a and S6b have same configuration_request_id")
            await conn.close()
            return False
        
        print(f"\n  ✓ S6a configuration_request_id: {s6a_subject}")
        print(f"  ✓ S6b configuration_request_id: {s6b_subject}")
        print(f"  ✓ S6 preserved as 2 distinct configuration requests")
        
        # Validate no NULL subject_ids
        null_subjects = [e for e in config_evidence if e['subject_id'] is None]
        if null_subjects:
            print(f"\n✗ ERROR: Found {len(null_subjects)} Evidence with NULL subject_id")
            await conn.close()
            return False
        
        print(f"\n  ✓ No NULL configuration_request_id values")
        
        # Final summary
        print("\n" + "="*80)
        print("EVIDENCE GENERATION SUMMARY (NO INSERTS)")
        print("="*80)
        
        total_new_evidence = len(product_evidence) + len(config_evidence)
        expected_final = current_evidence + total_new_evidence
        
        print(f"\nCurrent Evidence:        {current_evidence}")
        print(f"PRODUCT_DEFINED new:     {len(product_evidence)}")
        print(f"CONFIGURATION_REQUESTED: {len(config_evidence)}")
        print(f"  - 6 complete (S1,S2,S3,S5,S6a,S6b): 30 rows")
        print(f"  - 1 incomplete (S7):                  4 rows")
        print(f"\nTotal new Evidence:      {total_new_evidence}")
        print(f"Expected final count:    {expected_final}")
        
        if total_new_evidence != 36:
            print(f"\n✗ ERROR: Expected 36 new Evidence, would generate {total_new_evidence}")
            await conn.close()
            return False
        
        if expected_final != 143:
            print(f"\n✗ ERROR: Expected 143 final Evidence, would have {expected_final}")
            await conn.close()
            return False
        
        print(f"\n✓ All validations passed")
        print(f"✓ Ready for database execution")
        
        await conn.close()
        
        print("\n" + "="*80)
        print("✓ PREVIEW COMPLETE — NO DATABASE WRITES")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        return False


if __name__ == '__main__':
    success = asyncio.run(preview_evidence())
    sys.exit(0 if success else 1)
