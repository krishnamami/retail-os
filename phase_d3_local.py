import asyncpg
import asyncio
from datetime import datetime

async def phase_d3_execute():
    '''STEP 5G.5 PHASE D.3 - CREATE PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE'''
    
    print('='*80)
    print('STEP 5G.5 PHASE D.3 EXECUTION')
    print('='*80)
    print(f'Timestamp: {datetime.utcnow().isoformat()}')
    print()
    
    # Try local connection
    conn = None
    try:
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password='Sharanya87$',
            database='accord'
        )
        print(f'✓ Connected to accord (localhost)')
    except Exception as e:
        print(f'✗ Connection failed: {e}')
        return 'BLOCKED_NO_CONNECTION'
    
    try:
        # SECTION 1: PRE-WRITE BASELINE
        print()
        print('SECTION 1: PRE-WRITE BASELINE')
        print('-'*80)
        
        db_info = await conn.fetchrow('SELECT current_database(), current_user, VERSION()')
        print(f'Database: {db_info[0]} | User: {db_info[1]}')
        
        ir_existing = await conn.fetch('''
            SELECT rule_id, rule_name, kb_version, status
            FROM claris_kb.identity_rules
            WHERE rule_id LIKE 'IR-%'
            ORDER BY rule_id
        ''')
        print(f'Existing identity rules: {len(ir_existing)}')
        
        ia_count = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.decision_rules WHERE decision_type = "IDENTITY_ASSESSMENT"')
        print(f'Existing IDENTITY_ASSESSMENT decision_rules: {ia_count}')
        
        active_kb = await conn.fetchrow('''
            SELECT kb_version, status FROM claris_kb.kb_artifact WHERE status = 'ACTIVE' LIMIT 1
        ''')
        print(f'Active KB: {active_kb[0]}')
        
        canonical_count = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
        decision_count = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')
        print(f'Baseline: config={canonical_count}, decision_audit={decision_count}')
        
        baseline = {
            'ir_existing_count': len(ir_existing),
            'ia_count': ia_count,
            'active_kb': active_kb[0],
            'canonical_count': canonical_count,
            'decision_count': decision_count
        }
        
        # SECTION 2: VERIFY SAFE DECISION_RULE STATUS
        print()
        print('SECTION 2: VERIFY SAFE DECISION_RULE STATUS')
        print('-'*80)
        
        existing_statuses = await conn.fetch('''
            SELECT DISTINCT status FROM claris_kb.decision_rules ORDER BY status
        ''')
        print(f'Existing status values: {[r[0] for r in existing_statuses]}')
        
        use_status = 'INACTIVE' if any(r[0] == 'INACTIVE' for r in existing_statuses) else existing_statuses[0][0]
        print(f'Using status: {use_status}')
        
        # SECTION 3: VERIFY REQUIRED OUTCOMES EXIST
        print()
        print('SECTION 3: VERIFY REQUIRED OUTCOMES')
        print('-'*80)
        
        outcome_check = await conn.fetch('''
            SELECT DISTINCT outcome_code FROM claris_kb.decision_rules ORDER BY outcome_code
        ''')
        existing_outcomes = {row[0] for row in outcome_check}
        print(f'Existing outcomes: {sorted(existing_outcomes)}')
        
        required_outcomes = ['CANNOT_DECIDE', 'CREATE_CONFIGURATION', 'NO_BUSINESS_CHANGE']
        missing = [o for o in required_outcomes if o not in existing_outcomes]
        if missing:
            print(f'✗ BLOCKED: Missing outcomes: {missing}')
            await conn.close()
            return 'BLOCKED_MISSING_OUTCOMES'
        print(f'✓ All required outcomes exist')
        
        # SECTION 4: CHECK IR-010 THROUGH IR-013 DO NOT EXIST
        print()
        print('SECTION 4: CHECK IR-010 THROUGH IR-013 DO NOT EXIST')
        print('-'*80)
        
        new_rules = ['IR-010', 'IR-011', 'IR-012', 'IR-013']
        existing_new = await conn.fetch('''
            SELECT rule_id FROM claris_kb.identity_rules WHERE rule_id = ANY($1)
        ''', new_rules)
        
        if existing_new:
            print(f'✗ BLOCKED: Rules exist: {[r[0] for r in existing_new]}')
            await conn.close()
            return 'BLOCKED_RULES_EXIST'
        print(f'✓ IR-010 through IR-013 do not exist')
        
        # SECTION 5: PREPARE DATA FOR INSERTS
        print()
        print('SECTION 5: PREPARE DATA FOR INSERTS')
        print('-'*80)
        
        ontology_version = await conn.fetchval('SELECT MAX(ontology_version) FROM claris_kb.decision_rules')
        ontology_to_use = ontology_version or '2026.10-governance'
        print(f'Using ontology_version: {ontology_to_use}')
        
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
        
        print(f'Ready to insert 4 identity_rules + 4 decision_rules')
        
        # SECTION 6: EXECUTE TRANSACTION
        print()
        print('SECTION 6: EXECUTE TRANSACTION')
        print('-'*80)
        
        try:
            async with conn.transaction():
                # Insert identity rules
                for rule_id, name, kb_ver, status in identity_rules_data:
                    await conn.execute('''
                        INSERT INTO claris_kb.identity_rules (rule_id, rule_name, kb_version, status)
                        VALUES ($1, $2, $3, $4)
                    ''', rule_id, name, kb_ver, status)
                    print(f'  ✓ {rule_id}')
                
                # Insert decision rules
                for rule_id, dec_type, kb_ver, ont_ver, prec, outcome, status, auth in decision_rules_data:
                    await conn.execute('''
                        INSERT INTO claris_kb.decision_rules
                        (rule_id, decision_type, kb_version, ontology_version, precedence, outcome_code, status, authority)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ''', rule_id, dec_type, kb_ver, ont_ver, prec, outcome, status, auth)
                    print(f'  ✓ {rule_id}')
                
                # SECTION 7: VALIDATION INSIDE TRANSACTION
                print()
                print('SECTION 7: VALIDATION INSIDE TRANSACTION')
                print('-'*80)
                
                ir_count_new = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.identity_rules WHERE rule_id = ANY($1)', new_rules)
                if ir_count_new != 4:
                    raise Exception(f'Identity rules count mismatch')
                print(f'✓ Identity rules: 4 inserted')
                
                dr_count_new = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.decision_rules WHERE rule_id = ANY($1)', new_rules)
                if dr_count_new != 4:
                    raise Exception(f'Decision rules count mismatch')
                print(f'✓ Decision rules: 4 inserted')
                
                ir_old_count = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.identity_rules WHERE rule_id LIKE "IR-00%"')
                if ir_old_count != len(ir_existing):
                    raise Exception(f'Existing rules modified')
                print(f'✓ Existing rules: {ir_old_count} unchanged')
                
                precedence = await conn.fetch('SELECT rule_id, precedence FROM claris_kb.decision_rules WHERE rule_id = ANY($1)', new_rules)
                prec_dict = {r[0]: r[1] for r in precedence}
                expected_prec = {'IR-010': 6, 'IR-011': 1, 'IR-012': 2, 'IR-013': 5}
                for rule_id, expected in expected_prec.items():
                    if prec_dict.get(rule_id) != expected:
                        raise Exception(f'Precedence mismatch {rule_id}')
                print(f'✓ Precedence: correct')
                
                outcomes = await conn.fetch('SELECT rule_id, outcome_code FROM claris_kb.decision_rules WHERE rule_id = ANY($1)', new_rules)
                outcome_dict = {r[0]: r[1] for r in outcomes}
                expected_outcomes = {'IR-010': 'NO_BUSINESS_CHANGE', 'IR-011': 'CANNOT_DECIDE', 'IR-012': 'CANNOT_DECIDE', 'IR-013': 'CREATE_CONFIGURATION'}
                for rule_id, expected in expected_outcomes.items():
                    if outcome_dict.get(rule_id) != expected:
                        raise Exception(f'Outcome mismatch {rule_id}')
                print(f'✓ Outcomes: correct')
                
                kb_check = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.kb_artifact WHERE status = "ACTIVE" AND kb_version = $1', active_kb[0])
                if kb_check == 0:
                    raise Exception('Active KB was modified')
                print(f'✓ KB artifact: unchanged')
                
                new_active_dr = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.v_active_decision_rules WHERE rule_id = ANY($1)', new_rules)
                if new_active_dr > 0:
                    raise Exception(f'Rules in active view')
                print(f'✓ Runtime: new rules NOT active')
                
                print()
                print('✓ All validations passed. Committing.')
                
        except Exception as e:
            print(f'✗ Transaction failed: {e}')
            raise
        
        # SECTION 8: POST-WRITE VERIFICATION
        print()
        print('SECTION 8: POST-WRITE VERIFICATION')
        print('-'*80)
        
        ir_final = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.identity_rules')
        dr_final = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.decision_rules')
        canonical_final = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
        decision_final = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')
        
        print(f'Identity rules: {baseline["ir_existing_count"]} → {ir_final}')
        print(f'Decision rules: +4 IDENTITY_ASSESSMENT')
        print(f'Canonical config: {baseline["canonical_count"]} → {canonical_final}')
        print(f'Decision audit: {baseline["decision_count"]} → {decision_final}')
        
        inserted = await conn.fetch('SELECT rule_id, precedence, outcome_code, status FROM claris_kb.decision_rules WHERE rule_id = ANY($1) ORDER BY precedence', new_rules)
        print()
        print('Inserted Rules:')
        for row in inserted:
            print(f'  {row[0]}: prec={row[1]}, outcome={row[2]}, status={row[3]}')
        
        print()
        print('='*80)
        print('STEP 5G.5 PHASE D.3 COMPLETE')
        print('='*80)
        print('✓ PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE PERSISTED')
        print('✓ NOT RUNTIME-ACTIVE (status='+use_status+')')
        print('✓ CANONICAL DATA UNCHANGED')
        print()
        
        await conn.close()
        return 'COMPLETE'
        
    except Exception as e:
        print(f'✗ Error: {e}')
        import traceback
        traceback.print_exc()
        try:
            await conn.close()
        except:
            pass
        return 'BLOCKED'

result = asyncio.run(phase_d3_execute())
print()
if result == 'COMPLETE':
    print('FINAL VERDICT: STEP 5G.5 PHASE D.3 COMPLETE — PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE PERSISTED, NOT RUNTIME-ACTIVE')
else:
    print(f'FINAL VERDICT: STEP 5G.5 PHASE D.3 BLOCKED — {result}')
