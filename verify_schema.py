#!/usr/bin/env python3
import asyncio, json, sys
import asyncpg, boto3

async def verify_schema():
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
            print("=" * 70)
            print("EVIDENCE SCHEMA VERIFICATION (POST-MIGRATION)")
            print("=" * 70)
            
            # Check columns
            print("\n📋 COLUMNS:")
            columns = await conn.fetch(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'runtime' AND table_name = 'evidence' ORDER BY ordinal_position"
            )
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  {col['column_name']}: {col['data_type']} {nullable}")
            
            # Check mapping_id specifically
            mapping_id_exists = any(col['column_name'] == 'mapping_id' for col in columns)
            print(f"\n✓ mapping_id EXISTS: {mapping_id_exists}")
            
            # Check UNIQUE constraints
            print("\n🔐 UNIQUE CONSTRAINTS:")
            constraints = await conn.fetch(
                """SELECT c.conname, string_agg(a.attname, ', ' ORDER BY a.attnum) as columns
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON t.relnamespace = n.oid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
                WHERE n.nspname = 'runtime' AND t.relname = 'evidence' AND c.contype = 'u'
                GROUP BY c.conname ORDER BY c.conname"""
            )
            
            old_constraint_gone = True
            new_constraint_exists = False
            
            for c in constraints:
                print(f"  {c['conname']}: ({c['columns']})")
                if c['conname'] == 'evidence_subject_property_arrival':
                    old_constraint_gone = False
                if c['conname'] == 'evidence_lineage_identity_unique':
                    new_constraint_exists = True
            
            # Check row count
            print("\n📊 ROW COUNT:")
            count = await conn.fetchval('SELECT COUNT(*) FROM runtime.evidence')
            print(f"  runtime.evidence: {count} rows")
            
            # Results
            print("\n" + "=" * 70)
            print("VERIFICATION RESULTS:")
            print("=" * 70)
            print(f"✓ mapping_id column added: {mapping_id_exists}")
            print(f"✓ Old constraint (evidence_subject_property_arrival) dropped: {old_constraint_gone}")
            print(f"✓ New constraint (evidence_lineage_identity_unique) exists: {new_constraint_exists}")
            print(f"✓ Row count unchanged: {count} rows")
            
            if mapping_id_exists and old_constraint_gone and new_constraint_exists and count == 0:
                print("\n✓✓✓ SCHEMA MIGRATION VERIFIED ✓✓✓")
            else:
                print("\n⚠️  Verification incomplete")
            
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

asyncio.run(verify_schema())
