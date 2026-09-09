#!/usr/bin/env python3
import asyncio, json, sys, re
import asyncpg, boto3

async def run_migration():
    try:
        secrets = boto3.client('secretsmanager', region_name='us-west-2')
        response = secrets.get_secret_value(SecretId='retail_os/rds/postgres')
        creds = json.loads(response['SecretString'])
        
        conn = await asyncpg.connect(
            host=creds['host'], port=creds['port'],
            user=creds['username'], password=creds['password'],
            database=creds['dbname']
        )
        
        try:
            # Read SQL file (with BOM handling)
            with open('database/evidence/001_fix_evidence_identity.sql', 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            print("=" * 70)
            print("EXECUTING EVIDENCE SCHEMA MIGRATION")
            print("=" * 70)
            print("")
            
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in content.split(';') if s.strip()]
            
            for i, stmt in enumerate(statements, 1):
                # Skip comments
                stmt = re.sub(r'--.*$', '', stmt, flags=re.MULTILINE).strip()
                if not stmt:
                    continue
                
                print(f"[{i}] Executing statement...")
                try:
                    result = await conn.execute(stmt)
                    print(f"     ✓ Success")
                except Exception as e:
                    print(f"     ✗ Error: {e}")
                    raise
            
            print("")
            print("=" * 70)
            print("✓ MIGRATION SUCCESSFUL")
            print("=" * 70)
            print("")
            print("Migration applied:")
            print("  - mapping_id column added")
            print("  - evidence_subject_property_arrival constraint dropped")
            print("  - evidence_lineage_identity_unique constraint added")
            
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

asyncio.run(run_migration())
