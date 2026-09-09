#!/usr/bin/env python3
"""
STEP 5E.3B — Raw Contract Inspection (READ-ONLY)
Inspect raw.raw_event table structure and CONFIGURATION_REQUESTED records
Locate actual storage locations of configuration_request_id, product_id, launch_id, geo, term, segment
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


def get_sql_file_path() -> Path:
    """Get path to raw_to_evidence_prototype_mappings.sql"""
    return Path(__file__).parent / 'raw_to_evidence_prototype_mappings.sql'


def read_sql_file(sql_file: Path) -> str:
    """Read SQL mapping file"""
    try:
        with open(sql_file, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"✗ ERROR reading SQL file: {str(e)}")
        return ""


def extract_sql_expressions(sql_content: str) -> Dict[str, str]:
    """Extract the SQL expressions used for each field from mapping SQL"""
    expressions = {
        'configuration_request_id': None,
        'product_id': None,
        'launch_id': None,
        'geo': None,
        'term': None,
        'segment': None,
    }
    
    # Extract SELECT clause patterns for each field
    for field in expressions.keys():
        if field == 'configuration_request_id':
            if "r.payload->>'configuration_request_id'" in sql_content:
                expressions[field] = "r.payload->>'configuration_request_id'"
        elif field == 'product_id':
            if "r.payload->>'product_id'" in sql_content:
                expressions[field] = "r.payload->>'product_id'"
        elif field == 'launch_id':
            if "r.payload->>'launch_id'" in sql_content:
                expressions[field] = "r.payload->>'launch_id'"
        elif field == 'geo':
            if "r.payload->>'geo'" in sql_content:
                expressions[field] = "r.payload->>'geo'"
        elif field == 'term':
            if "r.payload->>'term'" in sql_content:
                expressions[field] = "r.payload->>'term'"
        elif field == 'segment':
            if "r.payload->>'segment'" in sql_content:
                expressions[field] = "r.payload->>'segment'"
    
    return expressions


async def inspect_raw_contract():
    """Inspect raw.raw_event table structure and records"""
    
    print("="*80)
    print("STEP 5E.3B — RAW CONTRACT INSPECTION (READ-ONLY)")
    print("="*80)
    
    credentials = get_postgres_credentials()
    sql_file = get_sql_file_path()
    sql_content = read_sql_file(sql_file)
    
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
        
        print("\n" + "="*80)
        print("1. RAW.RAW_EVENT TABLE SCHEMA")
        print("="*80)
        
        # Query information_schema for columns
        schema_query = """
            SELECT ordinal_position, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = 'raw_event'
            ORDER BY ordinal_position;
        """
        
        rows = await conn.fetch(schema_query)
        print(f"\nTotal columns: {len(rows)}\n")
        print(f"{'Pos':<4} {'Column Name':<30} {'Data Type':<20} {'Nullable':<8}")
        print("-" * 65)
        
        for row in rows:
            pos, col_name, data_type, nullable = row
            nullable_str = "YES" if nullable else "NO"
            print(f"{pos:<4} {col_name:<30} {data_type:<20} {nullable_str:<8}")
        
        print("\n" + "="*80)
        print("2. CONFIGURATION_REQUESTED RECORDS - COMPLETE DATA")
        print("="*80)
        
        # Query 4 CONFIGURATION_REQUESTED records
        config_records = [
            'CONFIG_REQ_2026_001',
            'CONFIG_REQ_2026_005',
            'CONFIG_REQ_2026_006',
            'CONFIG_REQ_2026_007',
        ]
        
        for config_id in config_records:
            print(f"\n{'─' * 80}")
            print(f"Record: {config_id}")
            print(f"{'─' * 80}")
            
            query = """
                SELECT * FROM raw.raw_event 
                WHERE source_record_id = $1 AND event_type = 'CONFIGURATION_REQUESTED'
                LIMIT 1;
            """
            
            record = await conn.fetchrow(query, config_id)
            
            if record is None:
                print(f"  ✗ Not found")
                continue
            
            # Print key physical columns
            print("\nKey Physical Columns:")
            print(f"  source_record_id: {record.get('source_record_id')}")
            print(f"  launch_id: {record.get('launch_id')}")
            print(f"  configuration_id: {record.get('configuration_id')}")
            print(f"  simulator_classification: {record.get('simulator_classification')}")
            
            # Print complete JSONB payload without truncation
            payload = record.get('payload')
            print("\nCOMPLETE PAYLOAD (no truncation):")
            if payload:
                print(json.dumps(payload, indent=2))
            else:
                print("  <NULL or empty payload>")
            
            # Test candidate extraction paths
            print("\nCandidate Extraction Paths (top-level from payload JSON):")
            if payload and isinstance(payload, dict):
                print(f"  payload['configuration_request_id']: {payload.get('configuration_request_id')}")
                print(f"  payload['product_id']: {payload.get('product_id')}")
                print(f"  payload['launch_id']: {payload.get('launch_id')}")
                print(f"  payload['geo']: {payload.get('geo')}")
                print(f"  payload['term']: {payload.get('term')}")
                print(f"  payload['segment']: {payload.get('segment')}")
            
            # Also query using SQL expressions to verify
            print("\nSQL Expression Results (via SELECT):")
            expr_query = """
                SELECT 
                    payload->>'configuration_request_id' as config_req_id_expr,
                    payload->>'product_id' as product_id_expr,
                    payload->>'launch_id' as launch_id_expr,
                    payload->>'geo' as geo_expr,
                    payload->>'term' as term_expr,
                    payload->>'segment' as segment_expr
                FROM raw.raw_event
                WHERE source_record_id = $1 AND event_type = 'CONFIGURATION_REQUESTED'
                LIMIT 1;
            """
            
            expr_result = await conn.fetchrow(expr_query, config_id)
            if expr_result:
                print(f"  payload->>'configuration_request_id': {expr_result['config_req_id_expr']}")
                print(f"  payload->>'product_id': {expr_result['product_id_expr']}")
                print(f"  payload->>'launch_id': {expr_result['launch_id_expr']}")
                print(f"  payload->>'geo': {expr_result['geo_expr']}")
                print(f"  payload->>'term': {expr_result['term_expr']}")
                print(f"  payload->>'segment': {expr_result['segment_expr']}")
            
            # Check for PROTOTYPE_ASSUMPTION in payload vs simulator_classification column
            print("\nPROTOTYPE Classification Check:")
            simulator_col = record.get('simulator_classification')
            if payload and isinstance(payload, dict):
                payload_classifier = payload.get('simulator_classification')
                print(f"  simulator_classification (column): {simulator_col}")
                print(f"  payload.simulator_classification: {payload_classifier}")
                if payload_classifier == 'PROTOTYPE_ASSUMPTION' and simulator_col is None:
                    print(f"  ✓ PROTOTYPE_ASSUMPTION found in payload JSON, column is NULL")
                elif payload_classifier == 'PROTOTYPE_ASSUMPTION':
                    print(f"  ✓ PROTOTYPE_ASSUMPTION in both payload and column")
        
        await conn.close()
        
        print("\n" + "="*80)
        print("3. MAPPING SQL EXPRESSIONS")
        print("="*80)
        print(f"\nSQL file: {sql_file}")
        print(f"File size: {sql_file.stat().st_size} bytes")
        
        if sql_content:
            expressions = extract_sql_expressions(sql_content)
            print("\nExtracted SQL expressions from raw_to_evidence_prototype_mappings.sql:")
            print("-" * 80)
            for field, expr in expressions.items():
                if expr:
                    print(f"  {field:<25} = {expr}")
                else:
                    print(f"  {field:<25} = <NOT FOUND IN SQL>")
        else:
            print("✗ Could not read SQL file")
        
        print("\n" + "="*80)
        print("✓ RAW CONTRACT INSPECTION COMPLETE")
        print("="*80)
        print("\nNo database writes performed.")
        print("All queries are READ-ONLY.")
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        return False


if __name__ == '__main__':
    success = asyncio.run(inspect_raw_contract())
    sys.exit(0 if success else 1)
