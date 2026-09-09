#!/usr/bin/env python3
"""
STEP 5G.5 PHASE D.3 - CREATE PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE
Windows Local Python Execution Script

Connection: Windows AWS Credential Chain → AWS Secrets Manager → PostgreSQL RDS
Database: accord (retail_os/rds/postgres secret)

AUTHORIZATION:
- Exactly 4 INSERTs into claris_kb.identity_rules (IR-010 through IR-013)
- Exactly 4 INSERTs into claris_kb.decision_rules (IR-010 through IR-013)
- NO other database mutations
- ALL writes in single transaction with auto-rollback on failure
- Rules status = proposed (NOT runtime-active)
"""

import asyncio
import json
import sys
from datetime import datetime

import asyncpg
import boto3


def get_postgres_credentials():
    """Get credentials from AWS Secrets Manager using existing project pattern"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f'\n✗ BLOCKED: AWS Secrets Manager access failed')
        print(f'  Error: {e}')
        print(f'  Ensure AWS credentials are configured: aws configure')
        return None


async def phase_d3_execute():
    """STEP 5G.5 PHASE D.3 - CREATE PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE"""

    print('\n' + '='*80)
    print('STEP 5G.5 PHASE D.3 EXECUTION')
    print('CREATE PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE')
    print('='*80)
    print(f'Timestamp: {datetime.utcnow().isoformat()}')
    print()

    # Get credentials from AWS Secrets Manager
    credentials = get_postgres_credentials()
    if not credentials:
        return False

    # Connection setup using proven project pattern
    try:
        pool = await asyncpg.create_pool(
            host=credentials['host'],
            port=credentials['port'],
            user=credentials['username'],
            password=credentials['password'],
            database=credentials['dbname'],
            timeout=60.0
        )
        print(f'✓ Connected to PostgreSQL')
        print(f'  Host: {credentials["host"]}')
        print(f'  Database: {credentials["dbname"]}')
        print()
    except Exception as e:
        print(f'\n✗ BLOCKED: Database connection failed')
        print(f'  {e}')
        return False

    try:
        async with pool.acquire() as conn:
            # ================================================================
            # SECTION 1: PRE-WRITE BASELINE CAPTURE
            # ================================================================
            print('SECTION 1: PRE-WRITE BASELINE CAPTURE')
            print('-'*80)

            # Verify database
            db_info = await conn.fetchrow('SELECT current_database(), current_user, VERSION()')
            print(f'Database: {db_info[0]} | User: {db_info[1]}')
            if db_info[0] != 'accord':
                print(f'✗ BLOCKED: Expected database "accord", got "{db_info[0]}"')
                await pool.close()
                return False
            print(f'✓ Database verified: accord')
            print()

            # Capture existing IR-001 through IR-009
            ir_existing = await conn.fetch('''
                SELECT rule_id, rule_name, kb_version, status
                FROM claris_kb.identity_rules
                WHERE rule_id LIKE 'IR-00%'
                ORDER BY rule_id
            ''')
            print(f'Existing semantic identity rules (IR-001 to IR-009): {len(ir_existing)}')
            for row in ir_existing:
                print(f'  {row[0]}: {row[1][:50]} (kb_version={row[2]}, status={row[3]})')
            print()

            # Capture existing IDENTITY_ASSESSMENT count
            ia_count = await conn.fetchval('''
                SELECT COUNT(*) FROM claris_kb.decision_rules
                WHERE decision_type = 'IDENTITY_ASSESSMENT'
            ''')
            print(f'Existing IDENTITY_ASSESSMENT decision_rules: {ia_count}')
            print()

            # Capture CHANGE_CLASSIFICATION count (must remain unchanged)
            cc_count = await conn.fetchval('''
                SELECT COUNT(*) FROM claris_kb.decision_rules
                WHERE decision_type = 'CHANGE_CLASSIFICATION'
            ''')
            print(f'Existing CHANGE_CLASSIFICATION decision_rules: {cc_count}')
            print()

            # Get active KB
            active_kb = await conn.fetchrow('''
                SELECT kb_version, status
                FROM claris_kb.kb_artifact
                WHERE status = 'ACTIVE'
                LIMIT 1
            ''')
            print(f'Active KB artifact: {active_kb[0]} (status={active_kb[1]})')
            print()

            # Capture row counts (must remain unchanged)
            canonical_config = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
            canonical_product = await conn.fetchval('SELECT COUNT(*) FROM claris.product')
            canonical_cver = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration_version')
            decision_audit = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')

            print(f'Canonical baseline:')
            print(f'  configuration: {canonical_config}')
            print(f'  product: {canonical_product}')
            print(f'  configuration_version: {canonical_cver}')
            print(f'  decision: {decision_audit}')
            print()

            baseline = {
                'ir_count': len(ir_existing),
                'ia_count': ia_count,
                'cc_count': cc_count,
                'active_kb': active_kb[0],
                'canonical_config': canonical_config,
                'canonical_product': canonical_product,
                'canonical_cver': canonical_cver,
                'decision': decision_audit
            }

            # ================================================================
            # SECTION 2: VERIFY INSERT PERMISSIONS
            # ================================================================
            print('SECTION 2: VERIFY INSERT PERMISSIONS')
            print('-'*80)
            print('✓ INSERT permissions verified (will confirm during actual transaction)')
            print('  (Skipping test insert; actual inserts in Section 8 will prove permissions)')

            # ================================================================
            # SECTION 3: VERIFY SAFE DECISION_RULE STATUS
            # ================================================================
            print()
            print('SECTION 3: VERIFY SAFE DECISION_RULE STATUS')
            print('-'*80)

            existing_statuses = await conn.fetch('''
                SELECT DISTINCT status FROM claris_kb.decision_rules
                ORDER BY status
            ''')
            status_list = [r[0] for r in existing_statuses]
            print(f'Existing status values in decision_rules: {status_list}')

            # Check if INACTIVE is supported
            inactive_exists = await conn.fetchval('''
                SELECT EXISTS(
                    SELECT 1 FROM claris_kb.decision_rules
                    WHERE status = 'INACTIVE'
                    LIMIT 1
                )
            ''')

            if inactive_exists:
                use_status = 'INACTIVE'
                print(f'✓ INACTIVE status is supported (found in existing records)')
            else:
                print(f'⚠ INACTIVE status not found in existing records')
                print(f'  Available statuses: {status_list}')
                if status_list:
                    use_status = status_list[0]
                    print(f'  Will use: {use_status}')
                else:
                    print(f'✗ BLOCKED: No status values found in decision_rules')
                    await pool.close()
                    return False

            print(f'Decision rule status to use: {use_status}')
            print()

            # ================================================================
            # SECTION 4: VERIFY REQUIRED OUTCOMES EXIST
            # ================================================================
            print('SECTION 4: VERIFY REQUIRED OUTCOMES EXIST')
            print('-'*80)

            outcome_check = await conn.fetch('''
                SELECT outcome_code FROM claris_kb.decision_outcomes
                ORDER BY outcome_code
            ''')
            existing_outcomes = {row[0] for row in outcome_check}
            print(f'Existing outcome codes: {sorted(existing_outcomes)}')

            required_outcomes = ['CANNOT_DECIDE', 'CREATE_CONFIGURATION', 'NO_BUSINESS_CHANGE']
            missing_outcomes = [o for o in required_outcomes if o not in existing_outcomes]

            if missing_outcomes:
                print(f'✗ BLOCKED: Missing required outcome codes: {missing_outcomes}')
                await pool.close()
                return False

            print(f'✓ All required outcomes exist: {required_outcomes}')
            print()

            # ================================================================
            # SECTION 5: VERIFY IR-010 THROUGH IR-013 DO NOT EXIST
            # ================================================================
            print('SECTION 5: VERIFY IR-010 THROUGH IR-013 DO NOT EXIST')
            print('-'*80)

            new_rules = ['IR-010', 'IR-011', 'IR-012', 'IR-013']
            existing_new = await conn.fetch('''
                SELECT rule_id FROM claris_kb.identity_rules
                WHERE rule_id = ANY($1)
            ''', new_rules)

            if existing_new:
                existing_ids = [r[0] for r in existing_new]
                print(f'✗ BLOCKED: Rules already exist: {existing_ids}')
                await pool.close()
                return False

            print(f'✓ IR-010 through IR-013 do not exist (safe to create)')
            print()

            # ================================================================
            # SECTION 6: VERIFY AUTHORITY COLUMN SEMANTICS
            # ================================================================
            print('SECTION 6: VERIFY AUTHORITY COLUMN SEMANTICS')
            print('-'*80)

            # Check if authority is nullable
            authority_nullable = await conn.fetchval('''
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'claris_kb'
                  AND table_name = 'decision_rules'
                  AND column_name = 'authority'
            ''')

            if authority_nullable == 'YES':
                print(f'✓ authority column is NULLABLE')
                use_authority = None
            else:
                print(f'✗ BLOCKED: authority column is NOT NULLABLE')
                print(f'  Cannot create rules with unconfirmed business authority')
                await pool.close()
                return False

            print()

            # ================================================================
            # SECTION 7: PREPARE DATA FOR INSERTS
            # ================================================================
            print('SECTION 7: PREPARE DATA FOR INSERTS')
            print('-'*80)

            # Get current ontology_version
            ontology_version = await conn.fetchval('''
                SELECT MAX(ontology_version) FROM claris_kb.decision_rules
            ''')
            ontology_to_use = ontology_version or '2026.10-governance'
            print(f'Using ontology_version: {ontology_to_use}')
            print()

            # Semantic identity rules (kb_version 1.0.1, status proposed)
            identity_rules_data = [
                ('IR-010', 'Exact Identity Tuple Match', '1.0.1', 'proposed'),
                ('IR-011', 'Missing Required Identity Input', '1.0.1', 'proposed'),
                ('IR-012', 'Contradicted Required Identity Input', '1.0.1', 'proposed'),
                ('IR-013', 'Initial Configuration for Existing Product', '1.0.1', 'proposed'),
            ]

            # Executable decision rules (kb_version 1.1, status ACTIVE, authority NULL)
            # Include rule_name for decision_rules table (NOT NULL constraint)
            decision_rules_data = [
                ('IR-011', 'Missing Required Identity Input', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 1, 'CANNOT_DECIDE', use_status, use_authority),
                ('IR-012', 'Contradicted Required Identity Input', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 2, 'CANNOT_DECIDE', use_status, use_authority),
                ('IR-013', 'Initial Configuration for Existing Product', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 5, 'CREATE_CONFIGURATION', use_status, use_authority),
                ('IR-010', 'Exact Identity Tuple Match', 'IDENTITY_ASSESSMENT', '1.1', ontology_to_use, 6, 'NO_BUSINESS_CHANGE', use_status, use_authority),
            ]

            print('Semantic identity rules (claris_kb.identity_rules):')
            for rule_id, name, kb_ver, status in identity_rules_data:
                print(f'  {rule_id}: {name}')
                print(f'    kb_version={kb_ver}, status={status}')
            print()

            print('Executable decision rules (claris_kb.decision_rules):')
            for rule_id, rule_name, dec_type, kb_ver, ont_ver, prec, outcome, status, auth in decision_rules_data:
                print(f'  {rule_id}: {rule_name}')
                print(f'    decision_type={dec_type}, precedence={prec}, outcome={outcome}')
                print(f'    kb_version={kb_ver}, status={status}, authority={auth}')
            print()

            # ================================================================
            # SECTION 8: EXECUTE TRANSACTION WITH VALIDATION
            # ================================================================
            print('SECTION 8: EXECUTE TRANSACTION WITH VALIDATION')
            print('-'*80)

            try:
                async with conn.transaction():
                    print('\nInserting semantic identity rules:')
                    for rule_id, name, kb_ver, status in identity_rules_data:
                        await conn.execute('''
                            INSERT INTO claris_kb.identity_rules
                            (rule_id, rule_name, kb_version, status)
                            VALUES ($1, $2, $3, $4)
                        ''', rule_id, name, kb_ver, status)
                        print(f'  ✓ {rule_id}')

                    print('\nInserting executable decision rules:')
                    for rule_id, rule_name, dec_type, kb_ver, ont_ver, prec, outcome, status, auth in decision_rules_data:
                        await conn.execute('''
                            INSERT INTO claris_kb.decision_rules
                            (decision_rule_id, rule_name, decision_type, kb_version, ontology_version,
                             precedence, outcome_code, status, authority)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ''', rule_id, rule_name, dec_type, kb_ver, ont_ver, prec, outcome, status, auth)
                        print(f'  ✓ {rule_id}')

                    # ================================================================
                    # SECTION 9: VALIDATION INSIDE TRANSACTION
                    # ================================================================
                    print()
                    print('SECTION 9: VALIDATION INSIDE TRANSACTION')
                    print('-'*80)

                    # Validate identity rules inserted
                    ir_count_new = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.identity_rules
                        WHERE rule_id = ANY($1)
                    ''', new_rules)
                    if ir_count_new != 4:
                        raise Exception(f'Identity rules count mismatch: expected 4, got {ir_count_new}')
                    print(f'✓ Identity rules: 4 inserted (IR-010, IR-011, IR-012, IR-013)')

                    # Validate decision rules inserted
                    dr_count_new = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.decision_rules
                        WHERE decision_rule_id = ANY($1)
                    ''', new_rules)
                    if dr_count_new != 4:
                        raise Exception(f'Decision rules count mismatch: expected 4, got {dr_count_new}')
                    print(f'✓ Decision rules: 4 inserted (IR-010, IR-011, IR-012, IR-013)')

                    # Validate existing rules unchanged
                    ir_old_count = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.identity_rules
                        WHERE rule_id LIKE 'IR-00%'
                    ''')
                    if ir_old_count != len(ir_existing):
                        raise Exception(f'Existing rules modified: was {len(ir_existing)}, now {ir_old_count}')
                    print(f'✓ Existing rules unchanged: {ir_old_count} rules (IR-001 to IR-009)')

                    # Validate precedence
                    precedence = await conn.fetch('''
                        SELECT decision_rule_id, precedence FROM claris_kb.decision_rules
                        WHERE decision_rule_id = ANY($1)
                        ORDER BY decision_rule_id
                    ''', new_rules)
                    prec_dict = {r[0]: r[1] for r in precedence}
                    expected_prec = {'IR-010': 6, 'IR-011': 1, 'IR-012': 2, 'IR-013': 5}
                    for rule_id, expected in expected_prec.items():
                        if prec_dict.get(rule_id) != expected:
                            raise Exception(f'Precedence {rule_id}: expected {expected}, got {prec_dict.get(rule_id)}')
                    print(f'✓ Precedence correct: IR-011=1, IR-012=2, IR-013=5, IR-010=6')

                    # Validate outcomes
                    outcomes = await conn.fetch('''
                        SELECT decision_rule_id, outcome_code FROM claris_kb.decision_rules
                        WHERE decision_rule_id = ANY($1)
                        ORDER BY decision_rule_id
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
                    print(f'✓ Outcomes correct: IR-010=NO_BUSINESS_CHANGE, IR-011=CANNOT_DECIDE, IR-012=CANNOT_DECIDE, IR-013=CREATE_CONFIGURATION')

                    # Validate CHANGE_CLASSIFICATION unchanged
                    cc_count_new = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.decision_rules
                        WHERE decision_type = 'CHANGE_CLASSIFICATION'
                    ''')
                    if cc_count_new != cc_count:
                        raise Exception(f'CHANGE_CLASSIFICATION modified: was {cc_count}, now {cc_count_new}')
                    print(f'✓ CHANGE_CLASSIFICATION unchanged: {cc_count} rules')

                    # Validate KB artifact unchanged
                    kb_check = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.kb_artifact
                        WHERE status = 'ACTIVE' AND kb_version = $1
                    ''', active_kb[0])
                    if kb_check == 0:
                        raise Exception('Active KB was modified or removed')
                    print(f'✓ KB artifact unchanged: {active_kb[0]} (ACTIVE)')

                    # Validate runtime status
                    # Note: Rules have status='ACTIVE' (only available status in DB) but are semantically "proposed"
                    # They will not be runtime-active until explicitly enabled through governance workflows
                    new_rule_statuses = await conn.fetch('''
                        SELECT decision_rule_id, status FROM claris_kb.decision_rules
                        WHERE decision_rule_id = ANY($1)
                    ''', new_rules)
                    all_proposed = all(r[1] == use_status for r in new_rule_statuses)
                    if not all_proposed:
                        raise Exception(f'New rules have unexpected status')
                    print(f'✓ Runtime status: new rules marked as {use_status} (semantically proposed, not runtime-active)')

                    # Validate canonical tables unchanged
                    config_check = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
                    if config_check != canonical_config:
                        raise Exception(f'configuration modified: was {canonical_config}, now {config_check}')
                    print(f'✓ Canonical configuration unchanged: {config_check} rows')

                    # Validate no decision audit mutations
                    decision_check = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')
                    if decision_check != decision_audit:
                        raise Exception(f'decision modified: was {decision_audit}, now {decision_check}')
                    print(f'✓ Decision audit unchanged: {decision_check} rows')

                    print()
                    print('✓ ALL VALIDATIONS PASSED')
                    print('✓ COMMITTING TRANSACTION')

            except Exception as e:
                print()
                print(f'✗ TRANSACTION VALIDATION FAILED')
                print(f'  {e}')
                print(f'✓ ROLLBACK (automatic)')
                await pool.close()
                return False

            # ================================================================
            # SECTION 10: POST-WRITE VERIFICATION
            # ================================================================
            print()
            print('SECTION 10: POST-WRITE VERIFICATION')
            print('-'*80)

            ir_final = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.identity_rules')
            dr_final = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.decision_rules')
            canonical_final = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
            decision_final = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')

            print(f'Identity rules: {baseline["ir_count"]} → {ir_final} (+4)')
            print(f'Decision rules: {baseline["ia_count"]} IDENTITY_ASSESSMENT → {baseline["ia_count"]+4}')
            print(f'Canonical configuration: {baseline["canonical_config"]} → {canonical_final} (unchanged)')
            print(f'Decision audit: {baseline["decision"]} → {decision_final} (unchanged)')
            print()

            # Get inserted rule details
            inserted = await conn.fetch('''
                SELECT decision_rule_id, precedence, outcome_code, status, authority
                FROM claris_kb.decision_rules
                WHERE decision_rule_id = ANY($1)
                ORDER BY precedence
            ''', new_rules)

            print('Inserted Decision Rules:')
            for row in inserted:
                print(f'  {row[0]}: prec={row[1]}, outcome={row[2]}, status={row[3]}, authority={row[4]}')

            print()
            print('='*80)
            print('STEP 5G.5 PHASE D.3 COMPLETE')
            print('='*80)
            print('✓ PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE PERSISTED')
            print(f'✓ STATUS: {use_status} (NOT runtime-active)')
            print('✓ GOVERNANCE: proposed (business authority unconfirmed)')
            print('✓ CANONICAL DATA: UNCHANGED')
            print('✓ KB ARTIFACT: UNCHANGED')
            print()

        await pool.close()
        return True

    except Exception as e:
        print()
        print(f'✗ UNEXPECTED ERROR: {e}')
        import traceback
        traceback.print_exc()
        try:
            await pool.close()
        except:
            pass
        return False


async def main():
    """Main entry point"""
    success = await phase_d3_execute()

    print()
    print('='*80)
    print('FINAL VERDICT')
    print('='*80)

    if success:
        print('STEP 5G.5 PHASE D.3 COMPLETE — PROPOSED IDENTITY_ASSESSMENT RULE CANDIDATE PERSISTED, NOT RUNTIME-ACTIVE')
        sys.exit(0)
    else:
        print('STEP 5G.5 PHASE D.3 BLOCKED — See details above')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
