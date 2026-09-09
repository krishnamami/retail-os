#!/usr/bin/env python3
"""
Diagnose claris-ingestion-lambda status and invoke test
"""
import json
import boto3
from datetime import datetime, timedelta

LAMBDA_FUNCTION = "claris-ingestion-lambda"
REGION = "us-west-2"
LOG_GROUP = "/aws/lambda/claris-ingestion-lambda"

def header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def step(num, text):
    print(f"\n[{num}] {text}")

def success(text):
    print(f"  ✓ {text}")

def error(text):
    print(f"  ✗ {text}")

def info(text):
    print(f"  → {text}")

# Initialize clients
lambda_client = boto3.client("lambda", region_name=REGION)
logs_client = boto3.client("logs", region_name=REGION)

header("LAMBDA DIAGNOSTICS")

# Step 1: Check function configuration
step(1, "Checking Lambda function configuration")
try:
    config = lambda_client.get_function_configuration(FunctionName=LAMBDA_FUNCTION)
    success(f"Function: {config['FunctionName']}")
    success(f"Runtime: {config['Runtime']}")
    success(f"State: {config['State']}")
    success(f"LastUpdateStatus: {config['LastUpdateStatus']}")
    success(f"CodeSize: {config['CodeSize'] / (1024*1024):.1f} MB")
    info(f"Last Modified: {config['LastModified']}")
except Exception as e:
    error(f"Failed to get config: {e}")
    exit(1)

# Step 2: Check recent logs
step(2, "Checking Lambda logs (last 10 minutes)")
try:
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(minutes=10)).timestamp() * 1000)

    response = logs_client.filter_log_events(
        logGroupName=LOG_GROUP,
        startTime=start_time,
        endTime=end_time,
        limit=100
    )

    events = response.get('events', [])
    if events:
        success(f"Found {len(events)} log entries:")
        for event in events[-20:]:  # Show last 20
            timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
            message = event['message'].strip()
            # Truncate long messages
            if len(message) > 120:
                message = message[:120] + "..."
            print(f"    [{timestamp.strftime('%H:%M:%S')}] {message}")
    else:
        info("No logs found in last 10 minutes")
except Exception as e:
    error(f"Failed to get logs: {e}")

# Step 3: Invoke Lambda with test payload
step(3, "Invoking Lambda with test payload")
test_payload = {
    "test_mode": True,
    "verify_s3": True
}

try:
    print(f"  Payload: {json.dumps(test_payload)}")
    response = lambda_client.invoke(
        FunctionName=LAMBDA_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(test_payload)
    )

    status_code = response["StatusCode"]
    print(f"  Response Status: {status_code}")

    # Read payload response
    payload_data = response["Payload"].read()

    try:
        payload = json.loads(payload_data)

        # Check for Lambda execution errors
        if "errorMessage" in payload:
            error(f"Lambda Error: {payload['errorMessage']}")
            if "errorType" in payload:
                print(f"  Type: {payload['errorType']}")
                print(f"  Traceback: {payload.get('errorTrace', 'N/A')}")
        else:
            # Parse body if present
            body = payload.get("body", payload)
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except:
                    pass

            if isinstance(body, dict):
                status = body.get("status", "UNKNOWN")
                if status == "SUCCESS":
                    success("Connectivity test PASSED!")
                    print("\n" + "=" * 70)
                    print("RESULTS:")
                    print("=" * 70)
                    # Print key results
                    if "checks" in body:
                        checks = body["checks"]
                        if "psycopg2_import" in checks:
                            result = checks["psycopg2_import"]
                            symbol = "✓" if result == "SUCCESS" else "✗"
                            print(f"  {symbol} psycopg2 import: {result}")
                            if "psycopg2_version" in checks:
                                print(f"     Version: {checks['psycopg2_version']}")

                        if "postgresql_connection" in checks:
                            pg = checks["postgresql_connection"]
                            symbol = "✓" if pg.get("status") == "VERIFIED" else "✗"
                            print(f"  {symbol} PostgreSQL connection: {pg.get('status')}")

                        if "select_1_test" in checks:
                            test = checks["select_1_test"]
                            symbol = "✓" if test.get("status") == "SUCCESS" else "✗"
                            print(f"  {symbol} SELECT 1 test: {test.get('status')}")

                        if "tables" in checks:
                            tables = checks["tables"]
                            exist = [t for t, s in tables.items() if s == "EXISTS"]
                            missing = [t for t, s in tables.items() if s != "EXISTS"]
                            print(f"  ✓ Tables found: {len(exist)}")
                            if missing:
                                print(f"  ✗ Tables missing: {missing}")

                        if "row_counts" in checks:
                            counts = checks["row_counts"]
                            print(f"  Row counts:")
                            for table, count in list(counts.items())[:3]:
                                if isinstance(count, int):
                                    print(f"    {table}: {count} rows")

                elif status == "FAILED":
                    error(f"Connectivity test FAILED")
                    if "errors" in body:
                        print("  Errors:")
                        for err in body["errors"]:
                            print(f"    - {err}")
                else:
                    info(f"Status: {status}")
                    print(f"  Response: {json.dumps(body, indent=2, default=str)[:500]}")
            else:
                info(f"Response: {str(body)[:200]}")
    except json.JSONDecodeError:
        print(f"  Raw response: {payload_data.decode()[:500]}")

except Exception as e:
    error(f"Failed to invoke Lambda: {e}")
    import traceback
    print(f"  Details: {traceback.format_exc()}")

print("\n")
