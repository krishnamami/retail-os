r"""STEP 5G.6 PHASE D.4G.3 -- DEPLOYMENT PREFLIGHT (READ ONLY).

Captures everything section 1 requires BEFORE any mutation, and decides whether
deployment may proceed. It writes nothing: SELECT only, session pinned READ
ONLY, and it never calls a function that could mutate.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g3_preflight.py

Exit codes
    0  preflight clean -- deployment may proceed
    2  deployment must NOT proceed (drift, or objects already present)
"""

from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _path in (_REPO_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from decisions.adapters.connection import read_only_connection  # noqa: E402

EXPECTED_AUTHORING_TABLES = {
    "ontology_release", "ontology_notes", "enums", "enum_values", "actors",
    "configuration_dimensions", "identity_rules", "decisions",
    "decision_outputs", "decision_dependencies", "projection_rules",
    "evidence_reference", "decision_reason_codes", "decision_rule_bindings",
}

WITNESS_TABLES = (
    "claris.product", "claris.configuration", "claris.configuration_version",
    "claris.decision", "claris.action_record", "claris.configuration_state",
    "claris_kb.decision_rules", "claris_kb.identity_rules",
    "ontology.decisions", "ontology.decision_outputs",
)

UPSTREAM_TABLES = (
    "raw.material", "raw.material_change", "claris.evidence",
    "claris.assertion", "claris.configuration_state",
)


def head(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def show(db, label, sql, params=None, width=400):
    print(f"\n-- {label} " + "-" * max(0, 58 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:220]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for row in rows:
        text = " | ".join(
            f"{k}={'NULL' if v is None else str(v)[:width]}" for k, v in row.items())
        print("   " + text.encode("ascii", "replace").decode("ascii"))
    return rows


#: Schemas whose contents must be byte-for-byte unchanged by this deployment.
#: ontology_authoring is deliberately excluded: it is what the deployment
#: creates.
WITNESS_SCHEMAS = ("claris", "claris_kb", "ontology", "raw", "state",
                   "payments", "audit", "runtime", "public")


def schema_census(db):
    """Exact row counts for EVERY table in the witness schemas.

    A hand-picked witness list is only as good as the guesses in it: the live
    preflight showed three of the names carried from repository DDL
    (raw.material, raw.material_change, claris.assertion) do not exist, so a
    list-based witness was quietly proving less than it claimed. Enumerating
    the catalogue cannot miss a table nobody thought to name.
    """
    tables = db.query("""
        SELECT schemaname AS schema, tablename AS table
        FROM pg_tables WHERE schemaname = ANY(%s)
        ORDER BY 1, 2
    """, (list(WITNESS_SCHEMAS),))
    census = {}
    for row in tables:
        qualified = f'{row["schema"]}.{row["table"]}'
        census[qualified] = db.scalar(
            f'SELECT count(*) FROM "{row["schema"]}"."{row["table"]}"')
    return census


def counts(db, tables):
    out = {}
    for table in tables:
        exists = db.scalar("SELECT to_regclass(%s)", (table,))
        out[table] = db.scalar(f"SELECT count(*) FROM {table}") if exists else None
    return out


def main() -> int:
    blockers = []
    with read_only_connection() as db:
        head("1. SESSION")
        show(db, "identity and version", """
            SELECT current_database() AS database, current_user, session_user,
                   version() AS server_version,
                   current_setting('server_version_num')::int AS version_num,
                   current_setting('transaction_read_only') AS read_only
        """)
        print(f"\n   session_is_read_only(): {db.session_is_read_only()}")

        print("   The D4G2 migration creates and alters no PostgreSQL type, so "
              "no ALTER TYPE\n   transaction handling applies.")

        head("2. SCHEMAS AND PRIVILEGES")
        show(db, "schemas present", """
            SELECT nspname AS schema FROM pg_namespace
            WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
            ORDER BY 1
        """)
        privileges = show(db, "privileges this login holds", """
            SELECT has_database_privilege(current_database(), 'CREATE') AS db_create,
                   has_schema_privilege('claris', 'USAGE')  AS claris_usage,
                   has_schema_privilege('claris', 'CREATE') AS claris_create,
                   to_regnamespace('ontology_authoring') IS NOT NULL AS authoring_exists
        """)
        privilege = privileges[0] if privileges else {}
        if not privilege.get("db_create"):
            blockers.append(
                "CREATE on database is absent: ontology_authoring cannot be created")
        if not privilege.get("claris_create"):
            blockers.append(
                "CREATE on schema claris is absent: the D4G2 migration cannot ALTER "
                "claris.decision / claris.configuration_state")

        head("3. EXISTING D.4G.3 OBJECTS -- DRIFT CHECK")
        authoring = show(db, "ontology_authoring tables", """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'ontology_authoring' ORDER BY 1
        """)
        present = {row["tablename"] for row in authoring}
        if present:
            print(f"\n   *** ontology_authoring ALREADY EXISTS with {len(present)} "
                  f"table(s) ***")
            missing = EXPECTED_AUTHORING_TABLES - present
            extra = present - EXPECTED_AUTHORING_TABLES
            print(f"   missing vs repository definition: {sorted(missing) or 'none'}")
            print(f"   extra   vs repository definition: {sorted(extra) or 'none'}")
            if missing or extra:
                blockers.append(
                    "ontology_authoring exists and does NOT match the repository "
                    "definition -- incompatible drift, deployment must not rerun")
            else:
                blockers.append(
                    "ontology_authoring already matches the repository definition; "
                    "deployment would be a rerun. Inspect row counts before "
                    "proceeding rather than reapplying blindly")
            show(db, "rows already present", """
                SELECT 'ontology_release' AS t, count(*) FROM ontology_authoring.ontology_release
                UNION ALL SELECT 'configuration_dimensions', count(*) FROM ontology_authoring.configuration_dimensions
                UNION ALL SELECT 'identity_rules', count(*) FROM ontology_authoring.identity_rules
                ORDER BY 1
            """)
        else:
            print("\n   ontology_authoring does not exist -- clean deployment")

        show(db, "D4G2 runtime objects already present?", """
            SELECT to_regprocedure('claris.is_valid_outcome_v2(varchar,varchar,varchar,varchar,varchar)')
                       IS NOT NULL AS is_valid_outcome_v2,
                   EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                           WHERE n.nspname='claris' AND p.proname='execute_decision_v2')
                       AS execute_decision_v2
        """)

        head("4. CURRENT PERSISTENCE CONTRACT (to be migrated)")
        show(db, "digest and version column widths", """
            SELECT table_schema||'.'||table_name AS relation, column_name,
                   data_type, character_maximum_length AS width, is_nullable
            FROM information_schema.columns
            WHERE table_schema='claris'
              AND table_name IN ('decision','configuration_state')
              AND column_name IN ('input_digest','kb_version','policy_version')
            ORDER BY 1, 2
        """)
        show(db, "lineage columns already present?", """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='claris' AND table_name='decision'
              AND column_name IN ('ontology_version','governance_basis',
                   'execution_mode','fold_state_id','matched_rule_id',
                   'matched_rule_class','matched_rule_kb_version',
                   'executor_version','digest_scheme_version')
            ORDER BY 1
        """)
        outcome_column = show(db, "outcome persistence column (live contract)", """
            SELECT column_name, data_type, character_maximum_length AS width,
                   is_nullable
            FROM information_schema.columns
            WHERE table_schema='claris' AND table_name='decision'
              AND column_name IN ('outcome_code', 'recommendation')
            ORDER BY 1
        """)
        names = {row["column_name"] for row in outcome_column}
        if "outcome_code" not in names:
            blockers.append(
                "claris.decision.outcome_code is absent; the migration persists "
                "the outcome into that column and cannot be applied as written")
        show(db, "outcome-ish types present (none should be used)", """
            SELECT n.nspname AS schema, t.typname AS type
            FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
            WHERE t.typname LIKE '%decision_outcome%' ORDER BY 1,2
        """)
        show(db, "object ownership (ALTER requires ownership)", """
            SELECT c.relname AS object, pg_get_userbyid(c.relowner) AS owner
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='claris' AND c.relname IN ('decision','configuration_state')
            ORDER BY 1
        """)
        ownership = db.query("""
            SELECT c.relname AS object, pg_get_userbyid(c.relowner) AS owner
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='claris' AND c.relname IN ('decision','configuration_state')""")
        me = db.scalar("SELECT current_user")
        for row in ownership:
            if row["owner"] != me and not db.scalar(
                    "SELECT pg_has_role(current_user, %s, 'USAGE')", (row["owner"],)):
                blockers.append(
                    f"claris.{row['object']} is owned by {row['owner']} and "
                    f"{me} is not a member of that role; ALTER TABLE will be "
                    f"denied. A DBA must run the migration or grant the role")

        head("5. BEFORE WITNESS -- EVERY TABLE THAT MUST NOT CHANGE")
        census = schema_census(db)
        print(f"   {len(census)} table(s) across {len(WITNESS_SCHEMAS)} schema(s)\n")
        for table, n in sorted(census.items()):
            print(f"   {table:<44} {n}")
        print(f"\n   total rows across all witness schemas: {sum(census.values())}")

        head("6. VERDICT")
        if blockers:
            print("   PREFLIGHT BLOCKED:")
            for item in blockers:
                print(f"     - {item}")
            print("\n   D.4G.3 DEPLOYMENT MUST NOT PROCEED")
            return 2
        print("   PREFLIGHT CLEAN -- deployment may proceed")
        print("   Next: d4g3_deploy.py (requires RETAIL_OS_DEPLOY_CONFIRM=D4G3)")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(1)
