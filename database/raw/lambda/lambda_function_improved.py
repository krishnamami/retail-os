"""
CLARIS Raw Ingestion Lambda Handler - IMPROVED VERSION
Purpose: Load frozen corpus (26 JSONL files, 169 records) into PostgreSQL raw.raw_event
Status: Fixed psycopg2 binary issue, improved error handling
"""
import json, boto3, psycopg2, hashlib, logging
from datetime import datetime
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "accord-capital-loans-usw2-621646470377")
S3_PREFIX = os.environ.get("S3_PREFIX", "claris/source-corpus/raw/")
PG_HOST = os.environ.get("PG_HOST", "database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DATABASE = os.environ.get("PG_DATABASE", "claris")
PG_USER = os.environ.get("PG_USER", "claris_ingestion")
DB_SECRET_NAME = os.environ.get("DB_SECRET_NAME", "claris/postgresql/production")

def get_secret(secret_name):
    sm_client = boto3.client("secretsmanager")
    response = sm_client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

def generate_source_record_id(bucket, key, version, position):
    hash_input = f"{bucket}|{key}|{version}|{position}"
    return f"FROZEN_{hashlib.sha256(hash_input.encode()).hexdigest()}"

def lambda_handler(event, context):
    test_mode = event.get("test_mode", False)
    if test_mode:
        return test_mode_handler(event)
    return ingestion_mode_handler(event)

def test_mode_handler(event):
    results = {"timestamp": datetime.utcnow().isoformat(), "status": "STARTED", "checks": {}, "errors": []}
    
    try:
        import psycopg2 as pg2
        results["checks"]["psycopg2_import"] = "SUCCESS"
        results["checks"]["psycopg2_version"] = psycopg2.__version__
    except Exception as e:
        results["checks"]["psycopg2_import"] = f"FAILED: {str(e)}"
        results["errors"].append(str(e))
        return {"statusCode": 500, "body": json.dumps(results)}
    
    try:
        secret = get_secret(DB_SECRET_NAME)
        pg_host, pg_port = secret.get("host", PG_HOST), int(secret.get("port", PG_PORT))
        pg_database, pg_user, pg_password = secret.get("database", PG_DATABASE), secret.get("username", PG_USER), secret.get("password")
        results["checks"]["secrets_manager"] = {"status": "VERIFIED"}
    except Exception as e:
        results["checks"]["secrets_manager"] = {"status": "FAILED", "error": str(e)}
        results["errors"].append(str(e))
        return {"statusCode": 500, "body": json.dumps(results)}
    
    conn = None
    try:
        conn = psycopg2.connect(host=pg_host, port=pg_port, database=pg_database, user=pg_user, password=pg_password)
        results["checks"]["postgresql_connection"] = {"status": "VERIFIED", "host": pg_host}
    except Exception as e:
        results["checks"]["postgresql_connection"] = {"status": "FAILED", "error": str(e)}
        results["errors"].append(str(e))
        return {"statusCode": 500, "body": json.dumps(results)}
    
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1")
        result = cur.fetchone()[0]
        results["checks"]["select_1_test"] = {"status": "SUCCESS", "result": result}
    except Exception as e:
        results["checks"]["select_1_test"] = {"status": "FAILED", "error": str(e)}
        results["errors"].append(str(e))
        cur.close()
        conn.close()
        return {"statusCode": 500, "body": json.dumps(results)}
    
    tables = {}
    try:
        for schema, table in [("raw", "raw_event"), ("runtime", "evidence"), ("runtime", "assertion"), ("state", "fold_state_snapshot"), ("audit", "ingestion_log"), ("audit", "ingestion_file")]:
            cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s)", (schema, table))
            tables[f"{schema}.{table}"] = "EXISTS" if cur.fetchone()[0] else "NOT_FOUND"
        results["checks"]["tables"] = tables
    except Exception as e:
        results["errors"].append(str(e))
    
    row_counts = {}
    try:
        for schema, table in [("raw", "raw_event"), ("runtime", "evidence"), ("runtime", "assertion"), ("state", "fold_state_snapshot"), ("audit", "ingestion_log"), ("audit", "ingestion_file")]:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            row_counts[f"{schema}.{table}"] = cur.fetchone()[0]
        results["checks"]["row_counts"] = row_counts
    except Exception as e:
        results["errors"].append(str(e))
    
    cur.close()
    conn.close()
    results["status"] = "FAILED" if results["errors"] else "SUCCESS"
    return {"statusCode": 200 if results["status"] == "SUCCESS" else 500, "body": json.dumps(results)}

def ingestion_mode_handler(event):
    ingestion_version = event.get("ingestion_version", "1.0")
    results = {"timestamp": datetime.utcnow().isoformat(), "status": "STARTED", "mode": "INGESTION", "ingestion_version": ingestion_version, "files_processed": 0, "records_inserted": 0, "records_skipped": 0, "errors": []}
    
    try:
        secret = get_secret(DB_SECRET_NAME)
        pg_host, pg_port = secret.get("host", PG_HOST), int(secret.get("port", PG_PORT))
        pg_database, pg_user, pg_password = secret.get("database", PG_DATABASE), secret.get("username", PG_USER), secret.get("password")
        
        conn = psycopg2.connect(host=pg_host, port=pg_port, database=pg_database, user=pg_user, password=pg_password)
        cur = conn.cursor()
        
        s3_client = boto3.client("s3")
        paginator = s3_client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                key = obj['Key']
                if key.endswith('/') or not key.endswith('.jsonl'):
                    continue
                
                try:
                    response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
                    content = response['Body'].read().decode('utf-8')
                    
                    for line_num, line in enumerate(content.strip().split('\n')):
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)
                            source_record_id = generate_source_record_id(S3_BUCKET, key, response.get('VersionId', '1'), line_num)
                            
                            cur.execute("INSERT INTO raw.raw_event (source_system, source_record_id, payload, occurred_at, recorded_at, ingestion_version) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING raw_event_id",
                                ("FROZEN", source_record_id, json.dumps(record), record.get("timestamp"), datetime.utcnow(), ingestion_version))
                            
                            if cur.fetchone():
                                results["records_inserted"] += 1
                            else:
                                results["records_skipped"] += 1
                        except json.JSONDecodeError as e:
                            results["errors"].append(f"Invalid JSON at line {line_num} in {key}: {str(e)}")
                    
                    results["files_processed"] += 1
                except Exception as e:
                    results["errors"].append(f"Failed to process {key}: {str(e)}")
        
        conn.commit()
        cur.close()
        conn.close()
        results["status"] = "SUCCESS" if not results["errors"] else "PARTIAL_SUCCESS"
    except Exception as e:
        results["errors"].append(f"Ingestion failed: {str(e)}")
        results["status"] = "FAILED"
    
    return {"statusCode": 200 if results["status"] in ["SUCCESS", "PARTIAL_SUCCESS"] else 500, "body": json.dumps(results)}
