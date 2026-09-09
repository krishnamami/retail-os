#!/usr/bin/env python3
"""
STEP 5D Prototype Raw Record Generator
Generates exactly 8 approved records: 1 PRODUCT_DEFINED + 7 CONFIGURATION_REQUESTED
Scenarios: S1, S2, S3, S5, S6 (2 records with same logical identity), S7
Gaps: S4 (price-only), S8 (contradiction)
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any


class PrototypeRawGenerator:
    """Minimal Raw record generator for approved UC-18 scenarios"""
    
    def __init__(self):
        self.arrival_date = "2026-09-07"
        
    def generate_product_defined_events(self) -> List[Dict[str, Any]]:
        """Generate 1 PRODUCT_DEFINED event (PROD-001 only)"""
        product = {
            "product_id": "PROD-001",
            "product_name": "Enterprise Cloud Suite"
        }
        
        record = {
            "event_id": str(uuid.uuid4()),
            "event_type": "PRODUCT_DEFINED",
            "occurred_at": "2026-01-15T00:00:00Z",
            "recorded_at": "2026-01-15T10:00:00Z",
            "arrival_at": "2026-01-16T14:30:00Z",
            "actor_id": "product_mgmt_system",
            "actor_role": "product_steward",
            "source_system": "product_definition",
            "business_object_type": "Launch",
            "business_object_id": "LAUNCH-001",
            "launch_id": "LAUNCH-001",
            "product_id": product["product_id"],
            "configuration_id": None,
            "sku_id": None,
            "material_id": None,
            "payload": product,
            "source_record_id": "PROD_DEF_2026_001",
            "source_version": "1.0",
            "ingested_at": "2026-01-16T14:30:00Z",
            "simulator_classification": "PROTOTYPE_ASSUMPTION",
            "correlation_id": str(uuid.uuid4()),
            "causation_id": None
        }
        
        return [record]
    
    def generate_configuration_requested_events(self) -> List[Dict[str, Any]]:
        """Generate 7 CONFIGURATION_REQUESTED events for approved scenarios"""
        
        configs = [
            # S1: baseline (PROD-001, NAMER, 36, enterprise)
            {
                "configuration_request_id": "CONFIG-REQ-2026-001",
                "product_id": "PROD-001",
                "launch_id": "LAUNCH-001",
                "geo": "NAMER",
                "term": 36,
                "segment": "enterprise",
                "scenario": "S1: New Product + First Configuration"
            },
            # S2: geography (PROD-001, APAC, 36, enterprise)
            {
                "configuration_request_id": "CONFIG-REQ-2026-002",
                "product_id": "PROD-001",
                "launch_id": "LAUNCH-001",
                "geo": "APAC",
                "term": 36,
                "segment": "enterprise",
                "scenario": "S2: Same Product + New Geography (APAC)"
            },
            # S3: segment (PROD-001, NAMER, 36, smb)
            {
                "configuration_request_id": "CONFIG-REQ-2026-003",
                "product_id": "PROD-001",
                "launch_id": "LAUNCH-001",
                "geo": "NAMER",
                "term": 36,
                "segment": "smb",
                "scenario": "S3: Same Product + Different Segment"
            },
            # S5: term (PROD-001, NAMER, 48, enterprise)
            {
                "configuration_request_id": "CONFIG-REQ-2026-005",
                "product_id": "PROD-001",
                "launch_id": "LAUNCH-001",
                "geo": "NAMER",
                "term": 48,
                "segment": "enterprise",
                "scenario": "S5: Same Product + Different Term"
            },
            # S6a: Business Duplicate - FIRST instance (same logical identity as S1)
            {
                "configuration_request_id": "CONFIG-REQ-2026-006",
                "product_id": "PROD-001",
                "launch_id": "LAUNCH-001",
                "geo": "NAMER",
                "term": 36,
                "segment": "enterprise",
                "scenario": "S6a: Business Duplicate (first instance, same as S1 identity)"
            },
            # S6b: Business Duplicate - SECOND instance (same logical identity as S1)
            {
                "configuration_request_id": "CONFIG-REQ-2026-006B",
                "product_id": "PROD-001",
                "launch_id": "LAUNCH-001",
                "geo": "NAMER",
                "term": 36,
                "segment": "enterprise",
                "scenario": "S6b: Business Duplicate (second instance, same as S1 identity)"
            },
            # S7: Incomplete identity (segment missing)
            {
                "configuration_request_id": "CONFIG-REQ-2026-007",
                "product_id": "PROD-001",
                "launch_id": "LAUNCH-001",
                "geo": "NAMER",
                "term": 36,
                "segment": None,
                "scenario": "S7: Incomplete Identity (segment missing)"
            },
        ]
        
        records = []
        source_record_id_counter = 0
        
        for config in configs:
            scenario = config.pop("scenario")
            source_record_id_counter += 1
            
            # Build payload with only non-null values
            payload = {k: v for k, v in config.items() if v is not None}
            
            record = {
                "event_id": str(uuid.uuid4()),
                "event_type": "CONFIGURATION_REQUESTED",
                "occurred_at": "2026-02-01T00:00:00Z",
                "recorded_at": "2026-02-01T08:00:00Z",
                "arrival_at": "2026-02-01T10:00:00Z",
                "actor_id": "config_governance_system",
                "actor_role": "configuration_authority",
                "source_system": "configuration_governance",
                "business_object_type": "configuration_request",
                "business_object_id": config["configuration_request_id"],
                "launch_id": config["launch_id"],
                "product_id": config["product_id"],
                "configuration_id": None,
                "sku_id": None,
                "material_id": None,
                "payload": payload,
                "source_record_id": f"CONFIG_REQ_2026_{source_record_id_counter:03d}",
                "source_version": "1.0",
                "ingested_at": "2026-02-01T10:00:00Z",
                "simulator_classification": "PROTOTYPE_ASSUMPTION",
                "correlation_id": str(uuid.uuid4()),
                "causation_id": None
            }
            records.append(record)
            print(f"Generated: {scenario}")
        
        return records
    
    def generate_all(self) -> tuple:
        """Generate all approved prototype Raw records"""
        product_events = self.generate_product_defined_events()
        config_events = self.generate_configuration_requested_events()
        
        print(f"\nGenerated {len(product_events)} PRODUCT_DEFINED event")
        print(f"Generated {len(config_events)} CONFIGURATION_REQUESTED events")
        print(f"Total new records: {len(product_events) + len(config_events)}")
        
        return product_events, config_events
    
    def validate_records(self, records: List[Dict]):
        """Validate records against Raw contract"""
        required_fields = [
            'source_system', 'source_record_id', 'source_version',
            'event_type', 'occurred_at', 'recorded_at', 'arrival_at',
            'payload', 'simulator_classification'
        ]
        
        errors = []
        for i, record in enumerate(records):
            for field in required_fields:
                if field not in record:
                    errors.append(f"Record {i}: Missing field '{field}'")
            
            if record.get('simulator_classification') != 'PROTOTYPE_ASSUMPTION':
                errors.append(f"Record {i}: simulator_classification must be PROTOTYPE_ASSUMPTION")
            
            if record.get('configuration_id') is not None:
                errors.append(f"Record {i}: configuration_id must be NULL")
            
            if record.get('event_type') not in ['PRODUCT_DEFINED', 'CONFIGURATION_REQUESTED']:
                errors.append(f"Record {i}: Unauthorized event_type: {record.get('event_type')}")
            
            try:
                datetime.fromisoformat(record.get('arrival_at', '').replace('Z', '+00:00'))
            except:
                errors.append(f"Record {i}: Invalid arrival_at format")
        
        return errors


if __name__ == '__main__':
    generator = PrototypeRawGenerator()
    
    print("=" * 70)
    print("STEP 5D.1 PROTOTYPE RAW RECORD GENERATOR — CORRECTED")
    print("=" * 70)
    print()
    
    product_events, config_events = generator.generate_all()
    
    print("\nValidating records...")
    product_errors = generator.validate_records(product_events)
    config_errors = generator.validate_records(config_events)
    
    all_errors = product_errors + config_errors
    if all_errors:
        print(f"Found {len(all_errors)} validation errors:")
        for error in all_errors:
            print(f"  - {error}")
    else:
        print("✓ All records valid")
    
    print(f"\n{'='*70}")
    print("RECORD COUNTS")
    print(f"{'='*70}")
    print(f"PRODUCT_DEFINED events: {len(product_events)}")
    print(f"CONFIGURATION_REQUESTED events: {len(config_events)}")
    print(f"Total new Raw records: {len(product_events) + len(config_events)}")
    print(f"Expected final Raw count: 169 + {len(product_events) + len(config_events)} = {169 + len(product_events) + len(config_events)}")
    
    all_records = product_events + config_events
    unique_keys = set()
    duplicates = []
    for record in all_records:
        key = (record['source_system'], record['source_record_id'], record['source_version'])
        if key in unique_keys:
            duplicates.append(key)
        unique_keys.add(key)
    
    if duplicates:
        print(f"\n✗ Found {len(duplicates)} duplicate keys:")
        for dup in duplicates:
            print(f"  - {dup}")
    else:
        print("✓ All records have unique (source_system, source_record_id, source_version)")
    
    print()
