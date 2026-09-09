import asyncpg
import asyncio
import ssl

async def check():
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.load_verify_locations('global-bundle.pem')
        
        conn = await asyncpg.connect(
            host='database-1.c1qseu4kq079.us-west-2.rds.amazonaws.com',
            port=5432,
            user='claris_ingestion',
            password='postgres123',
            database='accord',
            ssl=ssl_context
        )
        
        print("✓ PostgreSQL RDS connected to 'accord'\n")
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
        
        await conn.close()
        
    except Exception as e:
        print(f"✗ Error: {e}")

asyncio.run(check())
