#!/usr/bin/env python3
"""
RAW Ingestion: S3 → PostgreSQL (Simplified Sync Version)
"""

import json
import logging
import os
import sys
from datetime import datetime
import hashlib

import psycopg2
import psycopg2.extras
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RawIngestionTask:
    def __init__(self):
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.s3_bucket = os.getenv('AWS_S3_BUCKET')
        self.s3_prefix = os.getenv('AWS_S3_PREFIX')
        self.postgres_secret_name = os.getenv('POSTGRES_SECRET_NAME')
        self.postgres_db = os.getenv('POSTGRES_DB_NAME', 'accord')

        if not all([self.s3_bucket, self.s3_prefix, self.postgres_secret_name]):
            logger.error("Missing required environment variables")
            sys.exit(1)

        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        self.secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        self.conn = None

    def main(self):
        try:
            logger.info("=" * 70)
            logger.info("GATE 1: PRE-FLIGHT CHECKS")
            logger.info("=" * 70)

            # Get credentials and connect
            credentials = self._get_postgres_credentials()
            self.conn = psycopg2.connect(
                host=credentials['host'],
                port=credentials['port'],
                user=credentials['username'],
                password=credentials['password'],
                database=credentials['dbname']
            )

            # Test connection
            with self.conn.cursor() as cur:
                cur.execute('SELECT 1')
                logger.info("✓ PostgreSQL connectivity OK")

                # Verify tables exist
                for schema, table in [('raw', 'raw_event'), ('audit', 'ingestion_file')]:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = %s AND table_name = %s
                        )
                    """, (schema, table))
                    if not cur.fetchone()[0]:
                        logger.error(f"Required table {schema}.{table} does not exist")
                        return 1
                    logger.info(f"✓ Table {schema}.{table} exists")

            logger.info("\n" + "=" * 70)
            logger.info("SCANNING S3 FOR JSONL FILES")
            logger.info("=" * 70)

            # Scan S3
            jsonl_files = self._scan_s3_prefix()
            logger.info(f"Found {len(jsonl_files)} JSONL files")

            if not jsonl_files:
                logger.warning("No JSONL files found")
                return 0

            total_discovered = 0
            total_inserted = 0

            logger.info("\n" + "=" * 70)
            logger.info("GATE 2: LOAD JSONL FILES")
            logger.info("=" * 70)

            # Process each file
            for idx, (bucket, key) in enumerate(jsonl_files, 1):
                logger.info(f"\n[{idx}/{len(jsonl_files)}] Processing: {key}")

                # Get version
                version_id = self._get_object_version(bucket, key)

                # Check if already processed
                if self._check_file_already_processed(bucket, key, version_id):
                    logger.info(f"  → SKIP (already processed)")
                    continue

                # Load file
                discovered, inserted = self._load_jsonl_file(bucket, key, version_id)
                total_discovered += discovered
                total_inserted += inserted

                logger.info(f"  → Discovered: {discovered}, Inserted: {inserted}")

            logger.info(f"\nTotal: {total_discovered} discovered, {total_inserted} inserted")

            logger.info("\n" + "=" * 70)
            logger.info("GATE 3: VERIFY RESULTS")
            logger.info("=" * 70)

            self._verify_results()

            logger.info("\n" + "=" * 70)
            logger.info("✓ INGESTION COMPLETE")
            logger.info("=" * 70)

            return 0

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1

        finally:
            if self.conn:
                self.conn.close()

    def _get_postgres_credentials(self):
        try:
            response = self.secrets_client.get_secret_value(SecretId=self.postgres_secret_name)
            return json.loads(response['SecretString'])
        except ClientError as e:
            logger.error(f"Failed to retrieve secret: {e}")
            sys.exit(1)

    def _scan_s3_prefix(self):
        files = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)

        for page in pages:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                if obj['Key'].endswith('.jsonl'):
                    files.append((self.s3_bucket, obj['Key']))
        return files

    def _get_object_version(self, bucket, key):
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            version_id = response.get('VersionId', 'null')
            etag = response.get('ETag', '').strip('"')
            if version_id == 'null' or not version_id:
                version_id = f"etag-{etag}"
            return version_id
        except Exception as e:
            logger.warning(f"Could not get version: {e}")
            return "unknown"

    def _check_file_already_processed(self, bucket, key, version_id):
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT status FROM audit.ingestion_file
                WHERE bucket_name = %s AND object_key = %s AND object_version = %s
                AND status IN ('SUCCESS', 'PROCESSING') LIMIT 1
            """, (bucket, key, version_id))
            return cur.fetchone() is not None

    def _compute_deterministic_record_id(self, bucket, key, version_id, position):
        combined = f"{bucket}||{key}||{version_id}||{position}"
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        return f"FROZEN_{hash_obj.hexdigest()}"

    def _load_jsonl_file(self, bucket, key, version_id):
        try:
            # Download file
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')

            # Parse records
            records = []
            for position, line in enumerate(content.strip().split('\n')):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    records.append((position, record))
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping invalid JSON: {e}")

            if not records:
                return 0, 0

            # Insert records
            inserted_count = 0
            with self.conn.cursor() as cur:
                # Mark as PROCESSING
                cur.execute("""
                    INSERT INTO audit.ingestion_file
                    (bucket_name, object_key, object_version, status, processing_started_at, records_discovered)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (bucket_name, object_key, object_version)
                    DO UPDATE SET status = %s, processing_started_at = %s, records_discovered = %s
                """, (bucket, key, version_id, 'PROCESSING', datetime.utcnow(), len(records),
                      'PROCESSING', datetime.utcnow(), len(records)))

                # Insert raw events
                for position, record in records:
                    source_record_id = record.get(
                        'source_record_id',
                        self._compute_deterministic_record_id(bucket, key, version_id, position)
                    )
                    source_system = record.get('source_system', 'claris')
                    source_version = record.get('source_version', '1.0')

                    try:
                        cur.execute("""
                            INSERT INTO raw.raw_event
                            (source_system, source_record_id, source_version,
                             event_type, occurred_at, recorded_at, arrival_at,
                             arrival_date, launch_id, sku_id, material_id, payload)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (source_system, source_record_id, source_version)
                            DO NOTHING
                        """, (
                            source_system, source_record_id, source_version,
                            record.get('event_type'), record.get('occurred_at'),
                            record.get('recorded_at'), record.get('arrival_at'),
                            record.get('arrival_date'), record.get('launch_id'),
                            record.get('sku_id'), record.get('material_id'),
                            json.dumps(record)
                        ))
                        if cur.rowcount > 0:
                            inserted_count += 1
                    except psycopg2.IntegrityError:
                        self.conn.rollback()

                # Mark as SUCCESS
                cur.execute("""
                    UPDATE audit.ingestion_file
                    SET status = %s, records_inserted = %s, processing_completed_at = %s
                    WHERE bucket_name = %s AND object_key = %s AND object_version = %s
                """, ('SUCCESS', inserted_count, datetime.utcnow(), bucket, key, version_id))

                self.conn.commit()

            return len(records), inserted_count

        except Exception as e:
            logger.error(f"Failed to load file: {e}", exc_info=True)
            if self.conn:
                self.conn.rollback()
            return 0, 0

    def _verify_results(self):
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM raw.raw_event')
            raw_count = cur.fetchone()[0]
            logger.info(f"✓ raw.raw_event: {raw_count} records")

            cur.execute("SELECT COUNT(*) FROM audit.ingestion_file WHERE status = 'SUCCESS'")
            checkpoint_count = cur.fetchone()[0]
            logger.info(f"✓ audit.ingestion_file (SUCCESS): {checkpoint_count} files")

            for schema, table in [('runtime', 'evidence'), ('runtime', 'assertion'), ('state', 'fold_state_snapshot')]:
                cur.execute(f'SELECT COUNT(*) FROM {schema}.{table}')
                count = cur.fetchone()[0]
                logger.info(f"✓ {schema}.{table}: {count} records (protected)")


async def main():
    task = RawIngestionTask()
    exit_code = task.main()
    sys.exit(exit_code)


if __name__ == '__main__':
    task = RawIngestionTask()
    sys.exit(task.main())
