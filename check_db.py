import asyncpg
import asyncio
import sys

async def check():
    password = 'Sharanya87$'  # Set password here
    
    try:
        conn = await asyncpg.connect(
            host='localhost', 
            port=5432, 
            user='postgres',
            password=password,
            database='accord'
        )
        
        print("✓ PostgreSQL connected\n")
        
        version = await conn.fetchval('SELECT VERSION()')
        print(f"Version: {version}\n")
        
        print("=== TABLE COUNTS ===")
        raw = await conn.fetchval('SELECT COUNT(*) FROM raw.raw_event')
        evidence = await conn.fetchval('SELECT COUNT(*) FROM runtime.evidence')
        assertion = await conn.fetchval('SELECT COUNT(*) FROM runtime.assertion')
        fold = await conn.fetchval('SELECT COUNT(*) FROM state.fold_state_snapshot')
        
        print(f"raw.raw_event: {raw}")
        print(f"runtime.evidence: {evidence}")
        print(f"runtime.assertion: {assertion}")
        print(f"state.fold_state_snapshot: {fold}")
        
        print("\n=== EVENT TYPES ===")
        rows = await conn.fetch('SELECT event_type, COUNT(*) as count FROM raw.raw_event GROUP BY event_type ORDER BY count DESC')
        for row in rows:
            print(f"{row['event_type']}: {row['count']}")
        
        distinct = await conn.fetchval('SELECT COUNT(DISTINCT event_type) FROM raw.raw_event')
        print(f"\nDistinct event_type count: {distinct}")
        
        print("\n=== EVIDENCE CONSTRAINTS ===")
        constraints = await conn.fetch("SELECT constraint_name, constraint_type FROM information_schema.table_constraints WHERE table_name='evidence' AND table_schema='runtime'")
        for c in constraints:
            print(f"{c['constraint_name']}: {c['constraint_type']}")
        
        await conn.close()
        
    except Exception as e:
        print(f"✗ Error: {e}")

asyncio.run(check())
