#!/usr/bin/env python3
"""
STEP 5D Raw Prototype Validation Tests
Tests record structure, idempotency, and S3 compatibility
"""

import json
import pytest
import os
from pathlib import Path
from datetime import datetime


class TestPrototypeRawRecords:
    """Test suite for prototype Raw records"""
    
    @pytest.fixture
    def product_records(self):
        """Load product_defined fixture"""
        fixture_file = Path(__file__).parent / "fixtures" / "product_defined.jsonl"
        records = []
        with open(fixture_file) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records
    
    @pytest.fixture
    def config_records(self):
        """Load configuration_requested fixture"""
        fixture_file = Path(__file__).parent / "fixtures" / "configuration_requested.jsonl"
        records = []
        with open(fixture_file) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records
    
    @pytest.fixture
    def all_records(self, product_records, config_records):
        """Combined records"""
        return product_records + config_records
    
    def test_fixture_files_exist(self):
        """Verify fixture files were created"""
        fixtures = [
            "fixtures/product_defined.jsonl",
            "fixtures/configuration_requested.jsonl",
            "fixtures/prototype_raw_all.jsonl",
            "fixtures/s3_upload_manifest.json"
        ]
        for fixture in fixtures:
            path = Path(__file__).parent / fixture
            assert path.exists(), f"Missing fixture: {fixture}"
    
    def test_product_defined_count(self, product_records):
        """Verify PRODUCT_DEFINED record count"""
        assert len(product_records) == 2, f"Expected 2 PRODUCT_DEFINED, got {len(product_records)}"
    
    def test_configuration_requested_count(self, config_records):
        """Verify CONFIGURATION_REQUESTED record count"""
        assert len(config_records) == 7, f"Expected 7 CONFIGURATION_REQUESTED, got {len(config_records)}"
    
    def test_total_new_records(self, all_records):
        """Verify total record count"""
        assert len(all_records) == 9, f"Expected 9 total, got {len(all_records)}"
    
    def test_all_records_have_simulator_classification(self, all_records):
        """Verify all records are marked PROTOTYPE_ASSUMPTION"""
        for i, record in enumerate(all_records):
            assert 'simulator_classification' in record, f"Record {i} missing simulator_classification"
            assert record['simulator_classification'] == 'PROTOTYPE_ASSUMPTION', \
                f"Record {i} simulator_classification should be PROTOTYPE_ASSUMPTION"
    
    def test_configuration_id_is_null(self, all_records):
        """Verify configuration_id is NULL for all records"""
        for i, record in enumerate(all_records):
            assert record.get('configuration_id') is None, \
                f"Record {i}: configuration_id must be NULL, got {record.get('configuration_id')}"
    
    def test_authorized_event_types(self, all_records):
        """Verify only authorized event types exist"""
        authorized = ['PRODUCT_DEFINED', 'CONFIGURATION_REQUESTED']
        for i, record in enumerate(all_records):
            assert record['event_type'] in authorized, \
                f"Record {i}: Unauthorized event_type {record['event_type']}"
    
    def test_required_fields_present(self, all_records):
        """Verify required Raw envelope fields"""
        required = [
            'event_id', 'event_type', 'occurred_at', 'recorded_at', 'arrival_at',
            'source_system', 'source_record_id', 'source_version',
            'payload', 'simulator_classification'
        ]
        for i, record in enumerate(all_records):
            for field in required:
                assert field in record, f"Record {i} missing required field: {field}"
    
    def test_product_defined_payload_minimal(self, product_records):
        """Verify PRODUCT_DEFINED payload contains only minimal fields"""
        required_payload_fields = ['product_id', 'product_name']
        for i, record in enumerate(product_records):
            payload = record['payload']
            for field in required_payload_fields:
                assert field in payload, f"PRODUCT_DEFINED {i} payload missing {field}"
    
    def test_configuration_requested_payload_fields(self, config_records):
        """Verify CONFIGURATION_REQUESTED payload contains identity dimensions"""
        for i, record in enumerate(config_records):
            payload = record['payload']
            assert 'configuration_request_id' in payload, f"CONFIG {i} missing configuration_request_id"
            assert 'product_id' in payload, f"CONFIG {i} missing product_id"
            assert 'launch_id' in payload, f"CONFIG {i} missing launch_id"
            # geo, term, segment may be null (Scenario 7)
    
    def test_timestamp_formats(self, all_records):
        """Verify timestamp fields are ISO 8601"""
        for i, record in enumerate(all_records):
            for ts_field in ['occurred_at', 'recorded_at', 'arrival_at']:
                ts = record.get(ts_field)
                try:
                    datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    pytest.fail(f"Record {i} {ts_field} not ISO 8601: {ts}")
    
    def test_idempotency_uniqueness(self, all_records):
        """Verify uniqueness on (source_system, source_record_id, source_version)"""
        seen = set()
        duplicates = []
        for record in all_records:
            key = (record['source_system'], record['source_record_id'], record['source_version'])
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        
        assert len(duplicates) == 0, f"Found {len(duplicates)} duplicate idempotency keys"
    
    def test_product_explicitly_carries_launch_id(self, product_records):
        """Verify PRODUCT_DEFINED carries launch_id"""
        for i, record in enumerate(product_records):
            assert 'launch_id' in record, f"PRODUCT_DEFINED {i} missing launch_id"
            assert record['launch_id'] is not None, f"PRODUCT_DEFINED {i} launch_id is NULL"
    
    def test_configuration_explicitly_carries_launch_id(self, config_records):
        """Verify CONFIGURATION_REQUESTED carries launch_id"""
        for i, record in enumerate(config_records):
            assert 'launch_id' in record, f"CONFIG {i} missing launch_id"
            assert record['launch_id'] is not None, f"CONFIG {i} launch_id is NULL"
    
    def test_incomplete_identity_has_null_segment(self, config_records):
        """Verify Scenario 7 (incomplete identity) has segment=null"""
        scenario_7 = [r for r in config_records if r['source_record_id'] == 'CONFIG_REQ_2026_006']
        assert len(scenario_7) == 1, "Scenario 7 record not found"
        record = scenario_7[0]
        assert record['payload'].get('segment') is None, "Scenario 7 segment should be NULL"
    
    def test_duplicate_configuration_identical_payload(self, config_records):
        """Verify Scenario 6 (duplicate) has identical identity to Scenario 1"""
        scenario_1 = [r for r in config_records if r['source_record_id'] == 'CONFIG_REQ_2026_001']
        scenario_6 = [r for r in config_records if r['source_record_id'] == 'CONFIG_REQ_2026_005']
        
        assert len(scenario_1) == 1, "Scenario 1 not found"
        assert len(scenario_6) == 1, "Scenario 6 not found"
        
        # Compare identity dimensions (product_id, geo, term, segment)
        for dim in ['product_id', 'geo', 'term', 'segment']:
            assert scenario_1[0]['payload'].get(dim) == scenario_6[0]['payload'].get(dim), \
                f"Scenario 1 and 6 differ in {dim}"
    
    def test_s3_partition_naming_convention(self, all_records):
        """Verify records are compatible with S3 partition convention"""
        # source={system}/arrival_date={DATE}/part-{seq}.jsonl
        for record in all_records:
            assert record['source_system'] in ['product_definition', 'configuration_governance'], \
                f"Source system '{record['source_system']}' not in partition naming"
            # arrival_at should be 2026-09-07
            arrival_date = record['arrival_at'].split('T')[0]
            assert arrival_date == '2026-02-01', f"arrival_at date {arrival_date} unexpected"
    
    def test_no_invented_decision_codes(self, all_records):
        """Verify no Decision outcomes in Raw"""
        forbidden_keys = ['decision_output', 'decision_result', 'change_classification', 'identity_assessment']
        for i, record in enumerate(all_records):
            for key in forbidden_keys:
                assert key not in record.get('payload', {}), \
                    f"Record {i} payload contains forbidden key: {key}"
    
    def test_no_identity_hash_in_records(self, all_records):
        """Verify no physical identity hash exists"""
        forbidden_keys = ['identity_hash', 'canonical_identity_hash', 'identity_digest', 'hash_value']
        for i, record in enumerate(all_records):
            payload = record.get('payload', {})
            for key in forbidden_keys:
                assert key not in payload, f"Record {i} contains forbidden hash key: {key}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

