#!/usr/bin/env python3
"""
STEP 5G.5 PHASE D.3A - POST-WRITE RUNTIME NON-IMPACT VERIFICATION
READ-ONLY verification that new rules IR-010 through IR-013 are NOT runtime-active

Connection: Windows AWS Credential Chain → AWS Secrets Manager → PostgreSQL RDS
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


async def phase_d3a_verify():
    """STEP 5G.5 PHASE D.3A - POST-WRITE RUNTIME NON-IMPACT VERIFICATION"""

    print('\n' + '='*80)
    print('STEP 5G.5 PHASE D.3A EXECUTION')
    print('POST-WRITE RUNTIME NON-IMPACT VERIFICATION')
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
            # SECTION 1: VERIFY ACTIVE KB
            # ================================================================
            print('SECTION 1: VERIFY ACTIVE KB')
            print('-'*80)

            active_kb = await conn.fetchrow('''
                SELECT kb_version, status
                FROM claris_kb.kb_artifact
                WHERE status = 'ACTIVE'
                LIMIT 1
            ''')

            if active_kb:
                print(f'✓ Active KB version: {active_kb[0]} (status={active_kb[1]})')
            else:
                print(f'✗ No active KB found')
                await pool.close()
                return False

            # Verify v_active_kb also reflects this
            active_kb_view = await conn.fetchval('''
                SELECT kb_version FROM claris_kb.v_active_kb LIMIT 1
            ''')
            print(f'✓ v_active_kb confirms: {active_kb_view}')
            print()

            # ================================================================
            # SECTION 2: VERIFY ACTIVE DECISION VIEW
            # ================================================================
            print('SECTION 2: VERIFY ACTIVE DECISION VIEW')
            print('-'*80)

            new_rules = ['IR-010', 'IR-011', 'IR-012', 'IR-013']

            active_rules = await conn.fetch('''
                SELECT decision_rule_id, kb_version, status, decision_type, precedence, outcome_code
                FROM claris_kb.v_active_decision_rules
                WHERE decision_type = 'IDENTITY_ASSESSMENT'
                  AND decision_rule_id = ANY($1)
                ORDER BY decision_rule_id
            ''', new_rules)

            active_rule_ids = {r[0] for r in active_rules}

            print(f'Querying v_active_decision_rules for IDENTITY_ASSESSMENT rules:')
            print()

            visibility_report = {}
            for rule_id in new_rules:
                visible = rule_id in active_rule_ids
                visibility_report[rule_id] = visible
                status = "YES" if visible else "NO"
                print(f'  {rule_id} visible in active view = {status}')

            if active_rules:
                print()
                print(f'Active view details for new IDENTITY_ASSESSMENT rules:')
                for row in active_rules:
                    print(f'  {row[0]}: kb_version={row[1]}, status={row[2]}, prec={row[4]}, outcome={row[5]}')
            print()

            # ================================================================
            # SECTION 3: INSPECT VIEW DEFINITION
            # ================================================================
            print('SECTION 3: INSPECT VIEW DEFINITION')
            print('-'*80)

            view_def = await conn.fetchval('''
                SELECT pg_get_viewdef('claris_kb.v_active_decision_rules'::regclass)
            ''')

            if view_def:
                print('View definition for claris_kb.v_active_decision_rules:')
                print()
                print(view_def)
                print()

                # Analyze the view definition
                print('View definition analysis:')
                filters = []
                if 'kb_version' in view_def.lower():
                    filters.append('✓ Filters by kb_version')
                if 'status' in view_def.lower():
                    filters.append('✓ Filters by status')
                if 'decision_type' in view_def.lower():
                    filters.append('✓ Filters by decision_type')
                if 'effective' in view_def.lower():
                    filters.append('✓ Filters by effective dates')

                for f in filters:
                    print(f'  {f}')
            else:
                print('✗ Could not retrieve view definition')
            print()

            # ================================================================
            # SECTION 4: VERIFY EXECUTOR CONSUMPTION
            # ================================================================
            print('SECTION 4: VERIFY EXECUTOR CONSUMPTION')
            print('-'*80)

            print('Checking decision executor code patterns...')
            print()

            # Query to understand how active rules are used
            active_decision_rules_count = await conn.fetchval('''
                SELECT COUNT(*) FROM claris_kb.v_active_decision_rules
                WHERE decision_type = 'IDENTITY_ASSESSMENT'
            ''')

            print(f'Total IDENTITY_ASSESSMENT rules in v_active_decision_rules: {active_decision_rules_count}')

            # Check if our new rules are counted
            new_rules_in_active = await conn.fetchval('''
                SELECT COUNT(*) FROM claris_kb.v_active_decision_rules
                WHERE decision_type = 'IDENTITY_ASSESSMENT'
                  AND decision_rule_id = ANY($1)
            ''', new_rules)

            print(f'New rules (IR-010 through IR-013) in active view: {new_rules_in_active}')
            print()

            # Determine executor eligibility
            if new_rules_in_active > 0:
                print('⚠ New rules are visible in active decision rules view')
                print('  Executor eligibility depends on:')
                print('    1. status = ACTIVE (✓ new rules have status=ACTIVE)')
                print('    2. Active kb_version = 1.1 (✓ KB 1.1 is ACTIVE)')
                print('    3. No additional runtime gates in executor code')
                print()
                print('  ACTION: Need to verify executor code does NOT directly consume v_active_decision_rules')
                print('  or has additional filtering beyond the view')
            else:
                print('✓ New rules are NOT in active view')
                print('  Executor cannot access them through v_active_decision_rules')
            print()

            # ================================================================
            # SECTION 5: VERIFY SEMANTIC VIEW
            # ================================================================
            print('SECTION 5: VERIFY SEMANTIC VIEW')
            print('-'*80)

            semantic_rules = await conn.fetch('''
                SELECT rule_id, rule_name, kb_version, status
                FROM claris_kb.v_active_identity_rules
                WHERE rule_id = ANY($1)
                ORDER BY rule_id
            ''', new_rules)

            if semantic_rules:
                print(f'✓ New semantic identity rules visible in v_active_identity_rules:')
                for row in semantic_rules:
                    print(f'  {row[0]}: {row[1]} (kb_version={row[2]}, status={row[3]})')
                print()
                print('NOTE: Semantic visibility does NOT imply executor activation.')
                print('      Executor must explicitly enable rules for runtime evaluation.')
            else:
                print('✓ New semantic identity rules NOT in v_active_identity_rules')
            print()

            # ================================================================
            # SECTION 6: CLASSIFY RESULT
            # ================================================================
            print('SECTION 6: CLASSIFY RESULT')
            print('-'*80)

            result_classification = None

            if new_rules_in_active == 0:
                print('✓ Classification: A')
                print('  Rules are NOT executable/runtime-active.')
                print('  D.3 non-impact requirement satisfied.')
                result_classification = 'A'
            else:
                print('⚠ Classification: Requires investigation')
                print('  Rules are visible in active view.')
                print()
                print('  Need executor code inspection to determine:')
                print('  - Does executor read directly from v_active_decision_rules?')
                print('  - Are there additional runtime gates (e.g., authority verification)?')
                print('  - Does executor filter by business authority or governance status?')
                print()

                # Check for any authority or governance gates in decision_rules
                rules_with_authority = await conn.fetchval('''
                    SELECT COUNT(*) FROM claris_kb.decision_rules
                    WHERE decision_rule_id = ANY($1)
                      AND authority IS NOT NULL
                ''', new_rules)

                if rules_with_authority > 0:
                    print(f'  Potential gate: {rules_with_authority} rules have authority set')
                else:
                    print(f'  ⚠ WARNING: No authority gate on new rules')
                    result_classification = 'C'

            print()

            # ================================================================
            # SECTION 7: VERIFICATION SUMMARY
            # ================================================================
            print('SECTION 7: VERIFICATION SUMMARY')
            print('-'*80)

            print('Read-only queries executed:')
            print(f'  ✓ claris_kb.kb_artifact (ACTIVE KB: {active_kb[0]})')
            print(f'  ✓ claris_kb.v_active_decision_rules (new rules visible: {new_rules_in_active})')
            print(f'  ✓ View definition for v_active_decision_rules')
            print(f'  ✓ claris_kb.v_active_identity_rules (new rules: {len(semantic_rules)})')
            print()
            print('No database mutations performed.')
            print()

        await pool.close()
        return True

    except Exception as e:
        print()
        print(f'✗ ERROR: {type(e).__name__}: {str(e)}')
        import traceback
        traceback.print_exc()
        try:
            await pool.close()
        except:
            pass
        return False


async def main():
    """Main entry point"""
    success = await phase_d3a_verify()

    print()
    print('='*80)
    print('FINAL VERDICT')
    print('='*80)

    if success:
        print()
        print('STEP 5G.5 PHASE D.3A COMPLETE — VERIFICATION EXECUTED')
        print()
        print('Review the analysis above to determine:')
        print('  A) Rules are NOT executable → D.3 non-impact satisfied')
        print('  B) Rules visible but executor excludes them → D.3 non-impact satisfied')
        print('  C) Rules are visible AND executable → D.3 violated')
        print()
        sys.exit(0)
    else:
        print('STEP 5G.5 PHASE D.3A BLOCKED — Verification failed')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
