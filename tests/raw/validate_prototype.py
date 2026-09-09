#!/usr/bin/env python3
"""Manual validation of corrected prototype Raw records"""

import json
from pathlib import Path
from datetime import datetime

def load_fixture(filename):
    """Load JSONL fixture"""
    path = Path(__file__).parent / "fixtures" / filename
    records = []
    with open(path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def validate_all():
    """Run all validations"""
    print("=" * 70)
    print("STEP 5D.1 PROTOTYPE RAW VALIDATION — CORRECTED")
    print("=" * 70)
    
    product_records = load_fixture("product_defined.jsonl")
    config_records = load_fixture("configuration_requested.jsonl")
    all_records = product_records + config_records
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Record counts
    print("\n1. Record Counts:")
    if len(product_records) == 1:
        print(f"   ✓ PRODUCT_DEFINED: {len(product_records)}")
        tests_passed += 1
    else:
        print(f"   ✗ PRODUCT_DEFINED: Expected 1, got {len(product_records)}")
        tests_failed += 1
    
    if len(config_records) == 7:
        print(f"   ✓ CONFIGURATION_REQUESTED: {len(config_records)}")
        tests_passed += 1
    else:
        print(f"   ✗ CONFIGURATION_REQUESTED: Expected 7, got {len(config_records)}")
        tests_failed += 1
    
    if len(all_records) == 8:
        print(f"   ✓ Total new records: {len(all_records)}")
        print(f"   ✓ Expected final Raw count: 169 + 8 = 177")
        tests_passed += 1
    else:
        print(f"   ✗ Total: Expected 8, got {len(all_records)}")
        tests_failed += 1
    
    # Test 2: Provenance
    print("\n2. Provenance (all PROTOTYPE_ASSUMPTION):")
    prototype_count = sum(1 for r in all_records if r.get('simulator_classification') == 'PROTOTYPE_ASSUMPTION')
    if prototype_count == len(all_records):
        print(f"   ✓ All {prototype_count} records marked PROTOTYPE_ASSUMPTION")
        tests_passed += 1
    else:
        print(f"   ✗ Only {prototype_count}/{len(all_records)} marked PROTOTYPE_ASSUMPTION")
        tests_failed += 1
    
    # Test 3: Configuration ID NULL
    print("\n3. Configuration ID (must be NULL for all):")
    null_config_ids = sum(1 for r in all_records if r.get('configuration_id') is None)
    if null_config_ids == len(all_records):
        print(f"   ✓ All {null_config_ids} records have configuration_id = NULL")
        tests_passed += 1
    else:
        print(f"   ✗ Only {null_config_ids}/{len(all_records)} have configuration_id = NULL")
        tests_failed += 1
    
    # Test 4: Event type authorization
    print("\n4. Event Type Authorization:")
    authorized_types = sum(1 for r in all_records if r.get('event_type') in ['PRODUCT_DEFINED', 'CONFIGURATION_REQUESTED'])
    if authorized_types == len(all_records):
        print(f"   ✓ All {authorized_types} records use authorized event types")
        tests_passed += 1
    else:
        print(f"   ✗ Only {authorized_types}/{len(all_records)} use authorized event types")
        tests_failed += 1
    
    # Test 5: Required fields
    print("\n5. Required Fields:")
    required_fields = ['source_system', 'source_record_id', 'source_version', 'event_type', 
                      'occurred_at', 'recorded_at', 'arrival_at', 'payload', 'simulator_classification']
    missing_field_count = 0
    for record in all_records:
        for field in required_fields:
            if field not in record:
                missing_field_count += 1
    if missing_field_count == 0:
        print(f"   ✓ All {len(all_records)} records have required fields")
        tests_passed += 1
    else:
        print(f"   ✗ Found {missing_field_count} missing fields")
        tests_failed += 1
    
    # Test 6: Timestamp format
    print("\n6. Timestamp Format (ISO 8601):")
    invalid_timestamps = 0
    for record in all_records:
        for ts_field in ['occurred_at', 'recorded_at', 'arrival_at']:
            try:
                ts = record.get(ts_field, '').replace('Z', '+00:00')
                datetime.fromisoformat(ts)
            except:
                invalid_timestamps += 1
    if invalid_timestamps == 0:
        print(f"   ✓ All timestamps are valid ISO 8601")
        tests_passed += 1
    else:
        print(f"   ✗ Found {invalid_timestamps} invalid timestamps")
        tests_failed += 1
    
    # Test 7: Idempotency keys
    print("\n7. Idempotency Keys (unique on source_system, source_record_id, source_version):")
    unique_keys = set()
    duplicates = 0
    for record in all_records:
        key = (record['source_system'], record['source_record_id'], record['source_version'])
        if key in unique_keys:
            duplicates += 1
        unique_keys.add(key)
    if duplicates == 0:
        print(f"   ✓ All {len(unique_keys)} records have unique idempotency keys")
        tests_passed += 1
    else:
        print(f"   ✗ Found {duplicates} duplicate idempotency keys")
        tests_failed += 1
    
    # Test 8: Launch ID explicit
    print("\n8. Launch ID Explicit (required for CONFIGURATION_REQUESTED):")
    launch_id_count = sum(1 for r in config_records if r.get('launch_id') is not None)
    if launch_id_count == len(config_records):
        print(f"   ✓ All {launch_id_count} CONFIGURATION_REQUESTED have explicit launch_id")
        tests_passed += 1
    else:
        print(f"   ✗ Only {launch_id_count}/{len(config_records)} have launch_id")
        tests_failed += 1
    
    # Test 9: Product ID explicit
    print("\n9. Product ID Explicit (required for CONFIGURATION_REQUESTED):")
    product_id_count = sum(1 for r in config_records if r.get('product_id') is not None)
    if product_id_count == len(config_records):
        print(f"   ✓ All {product_id_count} CONFIGURATION_REQUESTED have explicit product_id")
        tests_passed += 1
    else:
        print(f"   ✗ Only {product_id_count}/{len(config_records)} have product_id")
        tests_failed += 1
    
    # Test 10: Scenario 7 segment missing
    print("\n10. Scenario 7 (segment missing):")
    s7_record = next((r for r in config_records if r.get('source_record_id') == 'CONFIG_REQ_2026_007'), None)
    if s7_record and 'segment' not in s7_record.get('payload', {}):
        print(f"   ✓ S7 record has segment=null in payload")
        tests_passed += 1
    else:
        print(f"   ✗ S7 record does not have segment missing")
        tests_failed += 1
    
    # Test 11: Scenario 6 business duplicates
    print("\n11. Scenario 6 (business duplicates - same identity, different IDs):")
    s6_records = [r for r in config_records if r.get('payload', {}).get('geo') == 'NAMER' and 
                  r.get('payload', {}).get('term') == 36 and 
                  r.get('payload', {}).get('segment') == 'enterprise']
    if len(s6_records) >= 2:
        # Check they have different source_record_id
        s6_ids = [r.get('source_record_id') for r in s6_records]
        if len(set(s6_ids)) == len(s6_ids):
            print(f"   ✓ Found {len(s6_records)} S6 duplicates with same logical identity, different source_record_id")
            tests_passed += 1
        else:
            print(f"   ✗ S6 duplicates don't have distinct source_record_id")
            tests_failed += 1
    else:
        print(f"   ✗ Expected 2+ S6 duplicates, found {len(s6_records)}")
        tests_failed += 1
    
    # Test 12: Scenario 2 geo correction
    print("\n12. Scenario 2 (geo = APAC, corrected from EMEA):")
    s2_record = next((r for r in config_records if r.get('source_record_id') == 'CONFIG_REQ_2026_002'), None)
    if s2_record and s2_record.get('payload', {}).get('geo') == 'APAC':
        print(f"   ✓ S2 record has geo = APAC")
        tests_passed += 1
    elif s2_record:
        print(f"   ✗ S2 record has geo = {s2_record.get('payload', {}).get('geo')}, expected APAC")
        tests_failed += 1
    else:
        print(f"   ✗ S2 record not found")
        tests_failed += 1
    
    # Test 13: No Decision outputs
    print("\n13. Decision Code Prohibition:")
    decision_fields = ['decision_output', 'change_classification', 'identity_assessment']
    decision_count = 0
    for record in all_records:
        payload = record.get('payload', {})
        for field in decision_fields:
            if field in payload:
                decision_count += 1
    if decision_count == 0:
        print(f"   ✓ No Decision outputs in records")
        tests_passed += 1
    else:
        print(f"   ✗ Found {decision_count} Decision fields in payloads")
        tests_failed += 1
    
    # Test 14: No identity hashes
    print("\n14. Physical Identity Hash Prohibition:")
    hash_fields = ['identity_hash', 'identity_digest', 'MD5', 'SHA', 'canonical_identity_hash']
    hash_count = 0
    for record in all_records:
        for field in hash_fields:
            if field in record:
                hash_count += 1
    if hash_count == 0:
        print(f"   ✓ No identity hashes in records")
        tests_passed += 1
    else:
        print(f"   ✗ Found {hash_count} identity hash fields")
        tests_failed += 1
    
    # Summary
    print(f"\n{'='*70}")
    print("VALIDATION SUMMARY")
    print(f"{'='*70}")
    print(f"Tests Passed: {tests_passed}/14")
    print(f"Tests Failed: {tests_failed}/14")
    
    if tests_failed == 0:
        print("\n✓ ALL VALIDATIONS PASSED")
        return 0
    else:
        print(f"\n✗ {tests_failed} VALIDATION(S) FAILED")
        return 1

if __name__ == '__main__':
    exit(validate_all())
