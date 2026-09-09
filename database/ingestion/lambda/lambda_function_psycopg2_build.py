"""
CLARIS Lambda Handler - Test Mode with sys.path fix
"""
import sys
import os

# Add python packages to path for Lambda
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

import json
import boto3
import psycopg2
from datetime import datetime

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

def lambda_handler(event, context):
    test_mode = event.get("test_mode", False)
    
    if test_mode:
        return test_mode_handler(event)
    
    return {"statusCode": 200, "body": json.dumps({"status": "INGESTION_MODE"})}

def test_mode_handler(event):
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "STARTED",
        "checks": {},
        "errors": []
    }
    
    # Test psycopg2 import
    try:
        import psycopg2 as pg2
        results["checks"]["psycopg2_import"] = "SUCCESS"
        results["checks"]["psycopg2_version"] = psycopg2.__version__
        print(f"[OK] psycopg2 {psycopg2.__version__}")
    except Exception as e:
        results["checks"]["psycopg2_import"] = f"FAILED: {str(e)}"
        results["errors"].append(str(e))
        results["status"] = "FAILED"
        return {"statusCode": 500, "body": json.dumps(results)}
    
    # Get credentials
    try:
        secret = get_secret(DB_SECRET_NAME)
        pg_host = secret.get("host", PG_HOST)
        pg_port = int(secret.get("port", PG_PORT))
        pg_database = secret.get("database", PG_DATABASE)
        pg_user = secret.get("username") or secret.get("user", PG_USER)
        pg_password = secret.get("password")
        
        results["checks"]["secrets_manager"] = {"status": "VERIFIED"}
    except Exception as e:
        results["checks"]["secrets_manager"] = {"status": "FAILED", "error": str(e)}
        results["errors"].append(str(e))
        results["status"] = "FAILED"
        return {"statusCode": 500, "body": json.dumps(results)}
    
    # Connect to PostgreSQL
    conn = None
    try:
        conn = psycopg2.connect(
            host=pg_host, port=pg_port, database=pg_database,
            user=pg_user, password=pg_password
        )
        results["checks"]["postgresql_connection"] = {"status": "VERIFIED", "host": pg_host}
        print(f"[OK] PostgreSQL connected")
    except Exception as e:
        results["checks"]["postgresql_connection"] = {"status": "FAILED", "error": str(e)}
        results["errors"].append(str(e))
        results["status"] = "FAILED"
        return {"statusCode": 500, "body": json.dumps(results)}
    
    # Test SELECT 1
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1")
        result = cur.fetchone()[0]
        results["checks"]["select_1_test"] = {"status": "SUCCESS", "result": result}
        print(f"[OK] SELECT 1 = {result}")
    except Exception as e:
        results["checks"]["select_1_test"] = {"status": "FAILED", "error": str(e)}
        results["errors"].append(str(e))
        results["status"] = "FAILED"
        cur.close()
        conn.close()
        return {"statusCode": 500, "body": json.dumps(results)}
    
    # Check tables
    tables = {}
    try:
        for schema, table in [("raw", "raw_event"), ("runtime", "evidence"), ("runtime", "assertion"), 
                              ("state", "fold_state_snapshot"), ("audit", "ingestion_log"), 
                              ("audit", "ingestion_file"), ("audit", "schema_version")]:
            cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s)",
                       (schema, table))
            tables[f"{schema}.{table}"] = "EXISTS" if cur.fetchone()[0] else "NOT_FOUND"
        results["checks"]["tables"] = tables
        print(f"[OK] Tables verified")
    except Exception as e:
        results["errors"].append(str(e))
    
    # Get row counts
    row_counts = {}
    try:
        for schema, table in [("raw", "raw_event"), ("runtime", "evidence"), ("runtime", "assertion"), 
                              ("state", "fold_state_snapshot"), ("audit", "ingestion_log"), 
                              ("audit", "ingestion_file"), ("audit", "schema_version")]:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            row_counts[f"{schema}.{table}"] = cur.fetchone()[0]
        results["checks"]["row_counts"] = row_counts
        print(f"[OK] Row counts retrieved")
    except Exception as e:
        results["errors"].append(str(e))
    
    cur.close()
    conn.close()
    
    if results["errors"]:
        results["status"] = "FAILED"
    else:
        results["status"] = "SUCCESS"
    
    return {"statusCode": 200 if results["status"] == "SUCCESS" else 500, "body": json.dumps(results)}
