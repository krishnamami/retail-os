#!/usr/bin/env python3
"""
STEP 5G.5 PHASE D.3C - REMOVE UNVERIFIED EXECUTABLE RULES
Preserve semantic candidate, restore runtime safety
"""

import asyncio
import json
import sys
from datetime import datetime

import asyncpg
import boto3


def get_postgres_credentials():
    """Get credentials from AWS Secrets Manager"""
    try:
        secrets_client = boto3.client('secretsmanager', region_name='us-west-2')
        response = secrets_client.get_secret_value(SecretId='retail_os/rds/postgres')
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f'✗ BLOCKED: AWS Secrets Manager access failed')
        print(f'  Error: {e}')
        return None


async def phase_d3c_execute():
    """STEP 5G.5 PHASE D.3C - REMOVE EXECUTABLE RULES"""

    print('\n' + '='*80)
    print('STEP 5G.5 PHASE D.3C EXECUTION')
    print('REMOVE UNVERIFIED EXECUTABLE IDENTITY_ASSESSMENT RULES')
    print('='*80)
    print(f'Timestamp: {datetime.utcnow().isoformat()}')
    print()

    credentials = get_postgres_credentials()
    if not credentials:
        return False

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
        print(f'✗ BLOCKED: Database connection failed')
        print(f'  {e}')
        return False

    try:
        async with pool.acquire() as conn:

            # ================================================================
            # SECTION 1: PRE-WRITE VALIDATION
            # ================================================================
            print('SECTION 1: PRE-WRITE VALIDATION')
            print('-'*80)

            new_rules = ['IR-010', 'IR-011', 'IR-012', 'IR-013']

            # Find the four rows to delete
            target_rows = await conn.fetch('''
                SELECT
                    decision_rule_id,
                    kb_version,
                    decision_type,
                    status,
                    outcome_code,
                    precedence,
                    authority
                FROM claris_kb.decision_rules
                WHERE decision_type = 'IDENTITY_ASSESSMENT'
                  AND decision_rule_id = ANY($1)
                  AND kb_version = '1.1'
                ORDER BY decision_rule_id
            ''', new_rules)

            print(f'Found {len(target_rows)} rows to delete:')
            if len(target_rows) != 4:
                print(f'✗ BLOCKED: Expected exactly 4 rows, found {len(target_rows)}')
                await pool.close()
                return False

            expected_rules = {
                'IR-010': (6, 'NO_BUSINESS_CHANGE'),
                'IR-011': (1, 'CANNOT_DECIDE'),
                'IR-012': (2, 'CANNOT_DECIDE'),
                'IR-013': (5, 'CREATE_CONFIGURATION')
            }

            for row in target_rows:
                rule_id = row[0]
                expected_prec, expected_outcome = expected_rules[rule_id]
                actual_prec = row[5]
                actual_outcome = row[4]
                actual_authority = row[6]

                if actual_prec != expected_prec or actual_outcome != expected_outcome:
                    print(f'✗ BLOCKED: {rule_id} has unexpected values')
                    print(f'  Expected: prec={expected_prec}, outcome={expected_outcome}')
                    print(f'  Found: prec={actual_prec}, outcome={actual_outcome}')
                    await pool.close()
                    return False

                if actual_authority is not None:
                    print(f'✗ BLOCKED: {rule_id} has authority={actual_authority}, expected NULL')
                    await pool.close()
                    return False

                print(f'  ✓ {rule_id}: prec={actual_prec}, outcome={actual_outcome}, authority={actual_authority}')

            print()

            # ================================================================
            # SECTION 2: CAPTURE BASELINE
            # ================================================================
            print('SECTION 2: CAPTURE BASELINE')
            print('-'*80)

            # Baseline counts before deletion
            active_dr_count = await conn.fetchval('''
                SELECT COUNT(*) FROM claris_kb.v_active_decision_rules
                WHERE decision_type = 'IDENTITY_ASSESSMENT'
            ''')

            cc_count = await conn.fetchval('''
                SELECT COUNT(*) FROM claris_kb.decision_rules
                WHERE decision_type = 'CHANGE_CLASSIFICATION'
            ''')

            active_kb = await conn.fetchval('''
                SELECT kb_version FROM claris_kb.kb_artifact
                WHERE status = 'ACTIVE' LIMIT 1
            ''')

            ir_semantic_count = await conn.fetchval('''
                SELECT COUNT(*) FROM claris_kb.identity_rules
                WHERE rule_id = ANY($1)
            ''', new_rules)

            canonical_config = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
            canonical_product = await conn.fetchval('SELECT COUNT(*) FROM claris.product')
            canonical_decision = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')

            print(f'Baseline state:')
            print(f'  v_active_decision_rules (IDENTITY_ASSESSMENT): {active_dr_count}')
            print(f'  decision_rules (CHANGE_CLASSIFICATION): {cc_count}')
            print(f'  Active KB: {active_kb}')
            print(f'  identity_rules (IR-010..013): {ir_semantic_count}')
            print(f'  canonical.configuration: {canonical_config}')
            print(f'  canonical.product: {canonical_product}')
            print(f'  canonical.decision: {canonical_decision}')
            print()

            baseline = {
                'active_dr_count': active_dr_count,
                'cc_count': cc_count,
                'active_kb': active_kb,
                'ir_semantic_count': ir_semantic_count,
                'canonical_config': canonical_config,
                'canonical_product': canonical_product,
                'canonical_decision': canonical_decision
            }

            # ================================================================
            # SECTION 3: TRANSACTION
            # ================================================================
            print('SECTION 3: EXECUTE TRANSACTION')
            print('-'*80)

            try:
                async with conn.transaction():
                    print('Deleting four executable decision_rules rows...')

                    deleted_count = await conn.execute('''
                        DELETE FROM claris_kb.decision_rules
                        WHERE decision_type = 'IDENTITY_ASSESSMENT'
                          AND decision_rule_id = ANY($1)
                          AND kb_version = '1.1'
                    ''', new_rules)

                    print(f'  ✓ Deleted {deleted_count} rows')
                    print()

                    # Validation inside transaction
                    print('VALIDATING INSIDE TRANSACTION')
                    print('-'*80)

                    # Verify executable rules deleted
                    remaining_dr = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.decision_rules
                        WHERE decision_type = 'IDENTITY_ASSESSMENT'
                          AND decision_rule_id = ANY($1)
                          AND kb_version = '1.1'
                    ''', new_rules)

                    if remaining_dr != 0:
                        raise Exception(f'Executable rules still exist: {remaining_dr}')
                    print(f'✓ IDENTITY_ASSESSMENT decision_rules (IR-010..013): 0 remaining')

                    # Verify semantic rules preserved
                    remaining_ir = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.identity_rules
                        WHERE rule_id = ANY($1)
                          AND kb_version = '1.0.1'
                    ''', new_rules)

                    if remaining_ir != 4:
                        raise Exception(f'Semantic rules lost: expected 4, found {remaining_ir}')
                    print(f'✓ Semantic identity_rules (IR-010..013, kb_version=1.0.1): 4 preserved')

                    # Verify CHANGE_CLASSIFICATION unchanged
                    cc_check = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.decision_rules
                        WHERE decision_type = 'CHANGE_CLASSIFICATION'
                    ''')

                    if cc_check != baseline['cc_count']:
                        raise Exception(f'CHANGE_CLASSIFICATION modified: was {baseline["cc_count"]}, now {cc_check}')
                    print(f'✓ CHANGE_CLASSIFICATION unchanged: {cc_check} rules')

                    # Verify KB artifact unchanged
                    kb_check = await conn.fetchval('''
                        SELECT COUNT(*) FROM claris_kb.kb_artifact
                        WHERE kb_version = $1 AND status = 'ACTIVE'
                    ''', baseline['active_kb'])

                    if kb_check == 0:
                        raise Exception('Active KB was modified or removed')
                    print(f'✓ KB artifact unchanged: {baseline["active_kb"]} (ACTIVE)')

                    # Verify canonical tables unchanged
                    config_check = await conn.fetchval('SELECT COUNT(*) FROM claris.configuration')
                    if config_check != baseline['canonical_config']:
                        raise Exception(f'configuration modified: was {baseline["canonical_config"]}, now {config_check}')
                    print(f'✓ Canonical configuration unchanged: {config_check} rows')

                    decision_check = await conn.fetchval('SELECT COUNT(*) FROM claris.decision')
                    if decision_check != baseline['canonical_decision']:
                        raise Exception(f'decision modified: was {baseline["canonical_decision"]}, now {decision_check}')
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
            # SECTION 4: ACTIVE VIEW VERIFICATION
            # ================================================================
            print()
            print('SECTION 4: ACTIVE VIEW VERIFICATION')
            print('-'*80)

            active_rules = await conn.fetch('''
                SELECT decision_rule_id
                FROM claris_kb.v_active_decision_rules
                WHERE decision_type = 'IDENTITY_ASSESSMENT'
                  AND decision_rule_id = ANY($1)
            ''', new_rules)

            if len(active_rules) > 0:
                print(f'✗ ERROR: Rules still in active view: {[r[0] for r in active_rules]}')
                await pool.close()
                return False

            print(f'✓ v_active_decision_rules contains ZERO rows for IR-010..013 IDENTITY_ASSESSMENT')
            print(f'✓ Known pre-D.3 executable state restored')
            print()

            # ================================================================
            # SECTION 5: PRESERVE SEMANTIC CANDIDATE
            # ================================================================
            print('SECTION 5: PRESERVE SEMANTIC CANDIDATE')
            print('-'*80)

            semantic_rules = await conn.fetch('''
                SELECT rule_id, kb_version, status
                FROM claris_kb.identity_rules
                WHERE rule_id = ANY($1)
                ORDER BY rule_id
            ''', new_rules)

            if len(semantic_rules) != 4:
                print(f'✗ ERROR: Semantic rules lost or corrupted: {len(semantic_rules)} found')
                await pool.close()
                return False

            print(f'Preserved semantic identity_rules (governance/design candidates):')
            for row in semantic_rules:
                print(f'  {row[0]}: kb_version={row[1]}, status={row[2]}')

            print()

            # ================================================================
            # SECTION 6: POST-DELETION VERIFICATION
            # ================================================================
            print('SECTION 6: POST-DELETION VERIFICATION')
            print('-'*80)

            # Check total decision rules count
            total_dr = await conn.fetchval('SELECT COUNT(*) FROM claris_kb.decision_rules')
            print(f'Total decision_rules remaining: {total_dr}')

            # Check active KB still active
            active_kb_final = await conn.fetchval('''
                SELECT kb_version FROM claris_kb.kb_artifact
                WHERE status = 'ACTIVE' LIMIT 1
            ''')
            print(f'Active KB: {active_kb_final}')

            print()
            print('='*80)
            print('STEP 5G.5 PHASE D.3C COMPLETE')
            print('='*80)
            print('✓ EXECUTABLE IDENTITY_ASSESSMENT RULES REMOVED')
            print('✓ SEMANTIC IDENTITY RULES PRESERVED (governance candidates)')
            print('✓ RUNTIME SAFETY RESTORED')
            print('✓ CANONICAL DATA UNCHANGED')
            print('✓ KB ARTIFACT UNCHANGED')
            print()

        await pool.close()
        return True

    except Exception as e:
        print()
        print(f'✗ UNEXPECTED ERROR: {type(e).__name__}: {str(e)}')
        import traceback
        traceback.print_exc()
        try:
            await pool.close()
        except:
            pass
        return False


async def main():
    """Main entry point"""
    success = await phase_d3c_execute()

    print()
    print('='*80)
    print('FINAL VERDICT')
    print('='*80)

    if success:
        print('STEP 5G.5 PHASE D.3C COMPLETE — EXECUTABLE RULES REMOVED, SEMANTIC CANDIDATE PRESERVED')
        sys.exit(0)
    else:
        print('STEP 5G.5 PHASE D.3C BLOCKED — See details above')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
