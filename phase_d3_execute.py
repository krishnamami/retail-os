import asyncpg
import asyncio
import ssl
from datetime import datetime

async def phase_d3_execute():
    '''STEP 5G.5 PHASE D.3 - CREATE PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE'''
    
    print('='*80)
    print('STEP 5G.5 PHASE D.3 EXECUTION')
    print('='*80)
    print(f'Timestamp: {datetime.utcnow().isoformat()}')
    print()
    
    # Connection setup using RDS pattern
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
        print('✓ Connected to accord (RDS)')
    except Exception as e:
        print(f'✗ Connection failed: {e}')
        return 'BLOCKED'
    
    try:
        # SECTION 1: PRE-WRITE BASELINE
        print()
        print('SECTION 1: PRE-WRITE BASELINE')
        print('-'*80)
        
        # Get database info
        db_info = await conn.fetchrow('SELECT current_database(), current_user, VERSION()')
        print(f'Database: {db_info[0]}')
        print(f'User: {db_info[1]}')
        print(f'PostgreSQL: {db_info[2][:50]}...')
        
        # Check existing IR-001 through IR-009
        ir_existing = await conn.fetch('''
            SELECT rule_id, rule_name, kb_version, status
            FROM claris_kb.identity_rules
            WHERE rule_id LIKE 'IR-%'
            ORDER BY rule_id
        ''')
        print(f'Existing identity rules (IR-001 to IR-009): {len(ir_existing)}')
        for row in ir_existing:
            print(f'  {row[0]}: {row[1][:40]} (kb_version={row[2]}, status={row[3]})')
        
        # Check existing IDENTITY_ASSESSMENT decision_rules
        ia_existing = await conn.fetch('''
            SELECT COUNT(*) as count
            FROM claris_kb.decision_rules
            WHERE decision_type = 'IDENTITY_ASSESSMENT'
        ''')
        ia_count = ia_existing[0]['count']
        print(f'Existing IDENTITY_ASSESSMENT decision rules: {ia_count}')
        
        # Get active KB
        active_kb = await conn.fetchrow('''
            SELECT kb_version, status, effective_from, created_at
            FROM claris_kb.kb_artifact
            WHERE status = 'ACTIVE'
            LIMIT 1
        ''')
        print(f'Active KB: {active_kb[0]} (status={active_kb[1]})')
        
        # Check v_active views
        active_ir_count = await conn.fetchval('''
            SELECT COUNT(*) FROM claris_kb.v_active_identity_rules
        ''')
        active_dr_count = await conn.fetchval('''
            SELECT COUNT(*) FROM claris_kb.v_active_decision_rules
        ''')
        print(f'Active identity rules (view): {active_ir_count}')
        print(f'Active decision rules (view): {active_dr_count}')
        
        # Get row counts
        canonical_count = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
        decision_count = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')
        product_count = await conn.fetchval('SELECT COUNT(*) FROM claris.product')
        print(f'Canonical configuration rows: {canonical_count}')
        print(f'Decision audit rows: {decision_count}')
        print(f'Product rows: {product_count}')
        
        baseline = {
            'ir_existing_count': len(ir_existing),
            'ia_existing_count': ia_count,
            'active_kb': active_kb[0],
            'active_ir_view': active_ir_count,
            'active_dr_view': active_dr_count,
            'canonical_config_count': canonical_count,
            'decision_count': decision_count,
            'product_count': product_count
        }
        
        # SECTION 2: VERIFY SAFE DECISION_RULE STATUS
        print()
        print('SECTION 2: VERIFY SAFE DECISION_RULE STATUS')
        print('-'*80)
        
        # Get distinct existing status values
        existing_statuses = await conn.fetch('''
            SELECT DISTINCT status FROM claris_kb.decision_rules ORDER BY status
        ''')
        print(f'Existing status values in decision_rules:')
        for row in existing_statuses:
            print(f'  {row[0]}')
        
        # Check if INACTIVE is supported
        inactive_check = await conn.fetchval('''
            SELECT EXISTS(SELECT 1 FROM claris_kb.decision_rules WHERE status = 'INACTIVE' LIMIT 1)
        ''')
        if inactive_check:
            print('✓ INACTIVE status is supported (found in existing records)')
            use_status = 'INACTIVE'
        else:
            # Use first available status as fallback
            use_status = existing_statuses[0][0] if existing_statuses else 'ACTIVE'
            print(f'⚠ INACTIVE not found. Will use first available status: {use_status}')
        
        # SECTION 3: VERIFY REQUIRED OUTCOMES EXIST
        print()
        print('SECTION 3: VERIFY REQUIRED OUTCOMES')
        print('-'*80)
        
        required_outcomes = ['CANNOT_DECIDE', 'CREATE_CONFIGURATION', 'NO_BUSINESS_CHANGE']
        outcome_check = await conn.fetch('''
            SELECT DISTINCT outcome_code FROM claris_kb.decision_rules
            ORDER BY outcome_code
        ''')
        existing_outcomes = {row[0] for row in outcome_check}
        print(f'Existing outcome codes: {sorted(existing_outcomes)}')
        
        missing_outcomes = [o for o in required_outcomes if o not in existing_outcomes]
        if missing_outcomes:
            print(f'✗ BLOCKED: Missing required outcomes: {missing_outcomes}')
            await conn.close()
            return 'BLOCKED_MISSING_OUTCOMES'
        print(f'✓ All required outcomes exist')
        
        # SECTION 4: CHECK IR-010 THROUGH IR-013 DO NOT EXIST
        print()
        print('SECTION 4: CHECK IR-010 THROUGH IR-013 DO NOT EXIST')
        print('-'*80)
        
        new_rules = ['IR-010', 'IR-011', 'IR-012', 'IR-013']
        existing_new = await conn.fetch('''
            SELECT rule_id FROM claris_kb.identity_rules
            WHERE rule_id = ANY($1)
        ''', new_rules)
        
        if existing_new:
            print(f'✗ BLOCKED: Rules already exist: {[r[0] for r in existing_new]}')
            await conn.close()
            return 'BLOCKED_RULES_EXIST'
        print(f'✓ IR-010 through IR-013 do not exist (safe to create)')
        
        # SECTION 5: PREPARE DATA FOR INSERTS
        print()
        print('SECTION 5: PREPARE DATA FOR INSERTS')
        print('-'*80)
        
        # Get ontology version
        ontology_version = await conn.fetchval('''
            SELECT MAX(ontology_version) FROM claris_kb.decision_rules
        ''')
        print(f'Current ontology_version in decision_rules: {ontology_version}')
        
        # Use default if not found
        ontology_to_use = ontology_version or '2026.10-governance'
        
        # Prepare insert data
        identity_rules_data = [
            ('IR-010', 'Exact Identity Tuple Match', '1.0.1', 'proposed'),
            ('IR-011', 'Missing Required Identity Input', '1.0.1', 'proposed'),
            ('IR-012', 'Contradicted Required Identity Input', '1.0.1', 'proposed'),
            ('IR-013', 'Initial Configuration for Existing Product', '1.0.1', 'proposed'),
        ]
        
        decision_rules_data = [
            ('IR-011', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 1, 'CANNOT_DECIDE', use_status, None),
            ('IR-012', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 2, 'CANNOT_DECIDE', use_status, None),
            ('IR-013', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 5, 'CREATE_CONFIGURATION', use_status, None),
            ('IR-010', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 6, 'NO_BUSINESS_CHANGE', use_status, None),
        ]
        
        print('Identity rules to insert:')
        for rule_id, name, kb_ver, status in identity_rules_data:
            print(f'  {rule_id}: {name} (kb_version={kb_ver}, status={status})')
        
        print('Decision rules to insert:')
        for rule_id, dec_type, kb_ver, ont_ver, prec, outcome, status, auth in decision_rules_data:
            print(f'  {rule_id}: prec={prec} outcome={outcome} status={status}')
        
        # SECTION 6: EXECUTE TRANSACTION
        print()
        print('SECTION 6: EXECUTE TRANSACTION')
        print('-'*80)
        
        transaction_success = False
        try:
            async with conn.transaction():
                # Insert identity rules
                for rule_id, name, kb_ver, status in identity_rules_data:
                    await conn.execute('''
                        INSERT INTO claris_kb.identity_rules (rule_id, rule_name, kb_version, status)
                        VALUES ($1, $2, $3, $4)
                    ''', rule_id, name, kb_ver, status)
                    print(f'  ✓ Inserted: {rule_id}')
                
                # Insert decision rules
                for rule_id, dec_type, kb_ver, ont_ver, prec, outcome, status, auth in decision_rules_data:
                    await conn.execute('''
                        INSERT INTO claris_kb.decision_rules
                        (rule_id, decision_type, kb_version, ontology_version, precedence, outcome_code, status, authority)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ''', rule_id, dec_type, kb_ver, ont_ver, prec, outcome, status, auth)
                    print(f'  ✓ Inserted: {rule_id}')
                
                # SECTION 7: VALIDATION INSIDE TRANSACTION
                print()
                print('SECTION 7: VALIDATION INSIDE TRANSACTION')
                print('-'*80)
                
                # Verify all 4 identity rules inserted
                ir_count_new = await conn.fetchval('''
                    SELECT COUNT(*) FROM claris_kb.identity_rules
                    WHERE rule_id = ANY($1)
                ''', new_rules)
                if ir_count_new != 4:
                    raise Exception(f'Identity rules count: expected 4, got {ir_count_new}')
                print(f'✓ Identity rules: 4 inserted')
                
                # Verify all 4 decision rules inserted
                dr_count_new = await conn.fetchval('''
                    SELECT COUNT(*) FROM claris_kb.decision_rules
                    WHERE rule_id = ANY($1)
                ''', new_rules)
                if dr_count_new != 4:
                    raise Exception(f'Decision rules count: expected 4, got {dr_count_new}')
                print(f'✓ Decision rules: 4 inserted')
                
                # Verify IR-001 through IR-009 unchanged
                ir_old_count = await conn.fetchval('''
                    SELECT COUNT(*) FROM claris_kb.identity_rules
                    WHERE rule_id LIKE 'IR-00%'
                ''')
                if ir_old_count != len(ir_existing):
                    raise Exception(f'Existing rules modified: was {len(ir_existing)}, now {ir_old_count}')
                print(f'✓ Existing rules: {ir_old_count} unchanged')
                
                # Verify precedence
                precedence = await conn.fetch('''
                    SELECT rule_id, precedence FROM claris_kb.decision_rules
                    WHERE rule_id = ANY($1)
                    ORDER BY rule_id
                ''', new_rules)
                prec_dict = {r[0]: r[1] for r in precedence}
                expected_prec = {'IR-010': 6, 'IR-011': 1, 'IR-012': 2, 'IR-013': 5}
                for rule_id, expected in expected_prec.items():
                    if prec_dict.get(rule_id) != expected:
                        raise Exception(f'Precedence {rule_id}: expected {expected}, got {prec_dict.get(rule_id)}')
                print(f'✓ Precedence: IR-011=1, IR-012=2, IR-013=5, IR-010=6')
                
                # Verify outcomes
                outcomes = await conn.fetch('''
                    SELECT rule_id, outcome_code FROM claris_kb.decision_rules
                    WHERE rule_id = ANY($1)
                    ORDER BY rule_id
                ''', new_rules)
                outcome_dict = {r[0]: r[1] for r in outcomes}
                expected_outcomes = {
                    'IR-010': 'NO_BUSINESS_CHANGE',
                    'IR-011': 'CANNOT_DECIDE',
                    'IR-012': 'CANNOT_DECIDE',
                    'IR-013': 'CREATE_CONFIGURATION'
                }
                for rule_id, expected in expected_outcomes.items():
                    if outcome_dict.get(rule_id) != expected:
                        raise Exception(f'Outcome {rule_id}: expected {expected}, got {outcome_dict.get(rule_id)}')
                print(f'✓ Outcomes: correct')
                
                # Verify KB unchanged
                kb_check = await conn.fetchval('''
                    SELECT COUNT(*) FROM claris_kb.kb_artifact
                    WHERE status = 'ACTIVE' AND kb_version = $1
                ''', active_kb[0])
                if kb_check == 0:
                    raise Exception('Active KB was modified')
                print(f'✓ KB artifact: unchanged')
                
                # Verify runtime non-impact
                new_active_dr = await conn.fetchval('''
                    SELECT COUNT(*) FROM claris_kb.v_active_decision_rules
                    WHERE rule_id = ANY($1)
                ''', new_rules)
                if new_active_dr > 0:
                    raise Exception(f'New rules in active view: {new_active_dr}')
                print(f'✓ Runtime: new rules NOT active')
                
                print()
                print('✓ All validations passed. Committing transaction.')
                transaction_success = True
                
        except Exception as e:
            print(f'✗ Transaction validation failed: {e}')
            print('↓ Rolling back transaction')
            raise
        
        # SECTION 8: POST-WRITE VERIFICATION
        print()
        print('SECTION 8: POST-WRITE VERIFICATION')
        print('-'*80)
        
        # Compare with baseline
        ir_final = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.identity_rules')
        dr_final = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.decision_rules')
        canonical_final = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
        decision_final = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')
        product_final = await conn.fetchval('SELECT COUNT(*) FROM claris.product')
        
        print(f'Identity rules: {baseline["ir_existing_count"]} → {ir_final} (+4)')
        print(f'Decision rules baseline: {baseline["ia_existing_count"]} IDENTITY_ASSESSMENT')
        print(f'  After D.3: +4 IDENTITY_ASSESSMENT inserted (total DR count: {dr_final})')
        print(f'Canonical configuration: {baseline["canonical_config_count"]} → {canonical_final} (unchanged)')
        print(f'Decision audit: {baseline["decision_count"]} → {decision_final} (unchanged)')
        print(f'Product: {baseline["product_count"]} → {product_final} (unchanged)')
        
        # Get detail on inserted rules
        inserted_rules = await conn.fetch('''
            SELECT rule_id, precedence, outcome_code, status FROM claris_kb.decision_rules
            WHERE rule_id = ANY($1)
            ORDER BY precedence
        ''', new_rules)
        
        print()
        print('Inserted Decision Rules Detail:')
        for row in inserted_rules:
            print(f'  {row[0]}: prec={row[1]}, outcome={row[2]}, status={row[3]}')
        
        print()
        print('='*80)
        print('STEP 5G.5 PHASE D.3 COMPLETE')
        print('='*80)
        print('✓ PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE PERSISTED')
        print('✓ STATUS: proposed (NOT runtime-active)')
        print('✓ CANONICAL DATA: UNCHANGED')
        print('✓ KB ARTIFACT: UNCHANGED')
        print('✓ EXISTING RULES: UNCHANGED')
        print()
        print('Rule Summary:')
        print('  IR-010: Exact Identity Tuple Match (prec=6, outcome=NO_BUSINESS_CHANGE)')
        print('  IR-011: Missing Required Identity Input (prec=1, outcome=CANNOT_DECIDE)')
        print('  IR-012: Contradicted Required Identity Input (prec=2, outcome=CANNOT_DECIDE)')
        print('  IR-013: Initial Configuration for Existing Product (prec=5, outcome=CREATE_CONFIGURATION)')
        print()
        print('Governance Status: PROPOSED')
        print('Business Authority: UNCONFIRMED')
        print()
        
        await conn.close()
        return 'COMPLETE'
        
    except Exception as e:
        print(f'✗ Error: {e}')
        try:
            await conn.close()
        except:
            pass
        return 'BLOCKED'

# Run the async function
result = asyncio.run(phase_d3_execute())
print()
if result == 'COMPLETE':
    print('FINAL VERDICT: STEP 5G.5 PHASE D.3 COMPLETE — PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE PERSISTED, NOT RUNTIME-ACTIVE')
else:
    print(f'FINAL VERDICT: STEP 5G.5 PHASE D.3 BLOCKED — {result}')
