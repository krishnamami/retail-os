#!/usr/bin/env python3
"""
STEP 5D.2: Upload Prototype Raw JSONL Files to S3

Uploads 2 JSONL partition files (1 PRODUCT_DEFINED + 7 CONFIGURATION_REQUESTED)
from local fixtures to S3 using the standard append-only partition structure.

Targets:
  - s3://accord-capital-loans-usw2-621646470377/claris/source-corpus/raw/
    source=product_definition/arrival_date=2026-01-16/part-00001.jsonl (1 record)
    source=configuration_governance/arrival_date=2026-02-01/part-00001.jsonl (7 records)

Prerequisites:
  - AWS credentials configured (environment or ~/.aws/credentials)
  - boto3 installed
  - Local fixture files: tests/raw/fixtures/product_defined.jsonl, configuration_requested.jsonl

Usage:
  python upload_prototype_raw.py --dry-run
  python upload_prototype_raw.py              # Actual upload
"""

import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Dict, Tuple
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

S3_BUCKET = "accord-capital-loans-usw2-621646470377"
S3_PREFIX = "claris/source-corpus/raw"

UPLOAD_MANIFEST = {
    "product_definition": {
        "fixture_file": "tests/raw/fixtures/product_defined.jsonl",
        "s3_partition": "source=product_definition/arrival_date=2026-01-16/part-00001.jsonl",
        "expected_count": 1,
    },
    "configuration_governance": {
        "fixture_file": "tests/raw/fixtures/configuration_requested.jsonl",
        "s3_partition": "source=configuration_governance/arrival_date=2026-02-01/part-00001.jsonl",
        "expected_count": 7,
    }
}


class PrototypeS3Uploader:
    """Upload prototype JSONL files to S3."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.s3_client = boto3.client('s3', region_name='us-west-2')
        self.uploaded_keys = []

    def validate_fixture_file(self, fixture_path: str) -> Tuple[int, bool]:
        """Validate local fixture file and count records."""
        try:
            if not Path(fixture_path).exists():
                logger.error(f"Fixture file not found: {fixture_path}")
                return 0, False

            count = 0
            with open(fixture_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            json.loads(line)
                            count += 1
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON in {fixture_path}: {e}")
                            return 0, False

            return count, True
        except Exception as e:
            logger.error(f"Error validating {fixture_path}: {e}")
            return 0, False

    def check_s3_collision(self, s3_key: str) -> bool:
        """Check if S3 key already exists."""
        try:
            self.s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
            return True  # Object exists
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False  # Object doesn't exist
            else:
                raise

    def upload_file(self, fixture_path: str, s3_key: str) -> bool:
        """Upload fixture file to S3."""
        try:
            logger.info(f"Uploading: {fixture_path}")
            logger.info(f"  Target: s3://{S3_BUCKET}/{s3_key}")

            if self.dry_run:
                logger.info("  [DRY RUN] Would upload")
                return True

            with open(fixture_path, 'rb') as f:
                self.s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=f.read(),
                    ContentType='application/json',
                    Metadata={'source': 'prototype-raw-corpus-extension', 'version': '1.0'}
                )

            self.uploaded_keys.append(s3_key)
            logger.info("  ✓ Upload successful")
            return True

        except ClientError as e:
            logger.error(f"✗ S3 upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return False

    def run(self) -> bool:
        """Execute full upload pipeline."""
        logger.info("=" * 80)
        logger.info("STEP 5D.2: Upload Prototype Raw to S3")
        logger.info("=" * 80)
        logger.info("")

        if self.dry_run:
            logger.info("[DRY RUN MODE]")
            logger.info("")

        # Step 1: Validate fixture files
        logger.info("Step 1: Validating fixture files...")
        all_valid = True
        total_records = 0

        for source_name, manifest in UPLOAD_MANIFEST.items():
            fixture_file = manifest['fixture_file']
            expected_count = manifest['expected_count']

            count, valid = self.validate_fixture_file(fixture_file)
            total_records += count

            if not valid or count != expected_count:
                logger.error(f"✗ {source_name}: Invalid or wrong count (expected {expected_count}, got {count})")
                all_valid = False
            else:
                logger.info(f"✓ {source_name}: {count} records")

        if not all_valid or total_records != 8:
            logger.error("✗ Validation failed")
            return False

        logger.info(f"✓ Total: {total_records} records")
        logger.info("")

        # Step 2: Check S3 collisions
        logger.info("Step 2: Checking for S3 collisions...")
        collision_found = False

        for source_name, manifest in UPLOAD_MANIFEST.items():
            s3_key = f"{S3_PREFIX}/{manifest['s3_partition']}"

            if self.check_s3_collision(s3_key):
                logger.error(f"✗ {source_name}: S3 key already exists: {s3_key}")
                collision_found = True
            else:
                logger.info(f"✓ {source_name}: No collision")

        if collision_found:
            logger.error("✗ Collision check failed")
            return False

        logger.info("")

        # Step 3: Upload files
        logger.info("Step 3: Uploading files...")
        upload_success = True

        for source_name, manifest in UPLOAD_MANIFEST.items():
            fixture_file = manifest['fixture_file']
            s3_key = f"{S3_PREFIX}/{manifest['s3_partition']}"

            if not self.upload_file(fixture_file, s3_key):
                upload_success = False

        if not upload_success:
            logger.error("✗ Upload failed")
            return False

        logger.info("")

        # Summary
        logger.info("=" * 80)
        logger.info("STEP 5D.2 COMPLETE")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Upload Summary:")
        logger.info(f"  Records uploaded: {total_records}")
        logger.info(f"  Files uploaded: {len(self.uploaded_keys)}")
        logger.info("")
        logger.info("Uploaded S3 keys:")
        for key in self.uploaded_keys:
            logger.info(f"  s3://{S3_BUCKET}/{key}")
        logger.info("")

        return True


def main():
    parser = argparse.ArgumentParser(description='Upload prototype raw JSONL files to S3')
    parser.add_argument('--dry-run', action='store_true', help='Validate without uploading')
    args = parser.parse_args()

    try:
        uploader = PrototypeS3Uploader(dry_run=args.dry_run)
        success = uploader.run()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
