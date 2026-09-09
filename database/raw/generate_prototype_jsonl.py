#!/usr/bin/env python3
"""Generate JSONL fixture files from prototype_generator"""

import json
import sys
from pathlib import Path
from prototype_generator import PrototypeRawGenerator

def main():
    generator = PrototypeRawGenerator()
    product_events, config_events = generator.generate_all()
    
    # Determine output directory
    fixtures_dir = Path(__file__).parent.parent.parent / "tests" / "raw" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    # Write product_defined.jsonl
    product_file = fixtures_dir / "product_defined.jsonl"
    with open(product_file, 'w') as f:
        for record in product_events:
            f.write(json.dumps(record) + '\n')
    print(f"✓ Wrote {len(product_events)} PRODUCT_DEFINED to {product_file}")
    
    # Write configuration_requested.jsonl
    config_file = fixtures_dir / "configuration_requested.jsonl"
    with open(config_file, 'w') as f:
        for record in config_events:
            f.write(json.dumps(record) + '\n')
    print(f"✓ Wrote {len(config_events)} CONFIGURATION_REQUESTED to {config_file}")
    
    # Write combined prototype_raw_all.jsonl
    all_records = product_events + config_events
    all_file = fixtures_dir / "prototype_raw_all.jsonl"
    with open(all_file, 'w') as f:
        for record in all_records:
            f.write(json.dumps(record) + '\n')
    print(f"✓ Wrote {len(all_records)} combined to {all_file}")
    
    # Write S3 manifest
    s3_manifest = {
        "raw_baseline_count": 169,
        "new_records_count": len(all_records),
        "final_expected_count": 169 + len(all_records),
        "partitions": {
            "product_definition": {
                "source": "product_definition",
                "arrival_date": "2026-01-16",
                "part_file": "part-00001.jsonl",
                "record_count": len(product_events),
                "records": [r["source_record_id"] for r in product_events]
            },
            "configuration_governance": {
                "source": "configuration_governance",
                "arrival_date": "2026-02-01",
                "part_file": "part-00001.jsonl",
                "record_count": len(config_events),
                "records": [r["source_record_id"] for r in config_events]
            }
        }
    }
    
    manifest_file = fixtures_dir / "s3_upload_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(s3_manifest, f, indent=2)
    print(f"✓ Wrote S3 manifest to {manifest_file}")
    
    print(f"\n{'='*70}")
    print("FIXTURE GENERATION SUMMARY")
    print(f"{'='*70}")
    print(f"PRODUCT_DEFINED: {len(product_events)}")
    print(f"CONFIGURATION_REQUESTED: {len(config_events)}")
    print(f"Total new records: {len(all_records)}")
    print(f"Expected final Raw count: 169 + {len(all_records)} = {169 + len(all_records)}")
    print()

if __name__ == '__main__':
    main()
