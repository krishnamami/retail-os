r"""STEP 5G.6 PHASE D.4G.3 -- CONTROLLED DEPLOYMENT.

Applies, in order and only after its own preflight passes:

    1. ontology_authoring/ddl/001_ontology_authoring_schema.sql     (14 tables)
    2. database/migrations/D4G2_001_prototype_runtime_contract.sql  (runtime)
    3. ontology_authoring/restore/002_restore_2026_10.sql           (135 rows)
    4. ontology_authoring/restore/003_prototype_2026_10_P1.sql      ( 34 rows)

then runs the section 12 read-only verification.

    $env:RETAIL_OS_DEPLOY_CONFIRM = "D4G3"
    .\venv\Scripts\python.exe tests\decisions\integration\d4g3_deploy.py

WHAT THIS SCRIPT WILL NOT DO
    * proceed if ontology_authoring already exists          (rerun guard)
    * proceed if any canonical or upstream count is unknown (witness guard)
    * touch raw, evidence, assertions, fold state, claris.product,
      claris.configuration, claris.configuration_version, claris.action_record,
      claris.decision, or any legacy KB artifact
    * drop or replace the v1 execution path
    * compile, verify or activate a KB
    * execute IDENTITY_ASSESSMENT
    * materialize any canonical object
    * change any grant

Every file is applied inside a transaction and rolled back on the first error.

There are no enum additions. A live preflight established that the outcome
column is claris.decision.outcome_code character varying(64) and that no type
claris_decision_outcome exists; the migration no longer touches any type, and
this script refuses to run one if a future edit reintroduces it.

Exit codes
    0  deployed and verified
    2  refused before mutation (guard tripped)
    3  deployment failed and was rolled back
    4  deployed but verification failed
"""

from __future__ import annotations

import os
import re
import sys
import traceback

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

from decisions.adapters.connection import deploy_connection  # noqa: E402

DDL = os.path.join(_REPO_ROOT, "ontology_authoring", "ddl",
                   "001_ontology_authoring_schema.sql")
MIGRATION = os.path.join(_REPO_ROOT, "database", "migrations",
                         "D4G2_001_prototype_runtime_contract.sql")
AUTHORITATIVE = os.path.join(_REPO_ROOT, "ontology_authoring", "restore",
                             "002_restore_2026_10.sql")
PROTOTYPE = os.path.join(_REPO_ROOT, "ontology_authoring", "restore",
                         "003_prototype_2026_10_P1.sql")

EXPECTED_TABLES = {
    "ontology_release", "ontology_notes", "enums", "enum_values", "actors",
    "configuration_dimensions", "identity_rules", "decisions",
    "decision_outputs", "decision_dependencies", "projection_rules",
    "evidence_reference", "decision_reason_codes", "decision_rule_bindings",
}

AUTHORITATIVE_COUNTS = {
    "ontology_release": 1, "actors": 7, "ontology_notes": 7, "enums": 11,
    "enum_values": 46, "configuration_dimensions": 8, "identity_rules": 9,
    "decisions": 5, "decision_outputs": 27, "decision_reason_codes": 6,
    "decision_dependencies": 4, "projection_rules": 4,
}
PROTOTYPE_COUNTS = {
    "ontology_release": 1, "actors": 7, "decisions": 1, "decision_outputs": 6,
    "configuration_dimensions": 7, "identity_rules": 8,
    "decision_rule_bindings": 4,
}

WITNESS_TABLES = (
    "claris.product", "claris.configuration", "claris.configuration_version",
    "claris.decision", "claris.action_record",
    "claris_kb.decision_rules", "claris_kb.identity_rules",
    "ontology.decisions", "ontology.decision_outputs",
)
UPSTREAM_TABLES = ("raw.material", "raw.material_change", "claris.evidence",
                   "claris.assertion", "claris.configuration_state")

FAILURES: list = []


def head(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(f"{label}: got {actual!r}, expected {expected!r}")
    return ok


def show(db, label, sql, params=None, width=300):
    print(f"\n-- {label} " + "-" * max(0, 56 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:200]}")
        return []
    if not rows:
        print("   (no rows)")
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


# ----------------------------------------------------------------------
# statement splitting -- dollar-quoting aware, because function bodies
# contain semicolons and a naive split on ';' would shred them
# ----------------------------------------------------------------------

def split_statements(sql: str) -> list:
    statements, buffer, index, tag = [], [], 0, None
    while index < len(sql):
        if tag is None:
            match = re.match(r"\$[A-Za-z_]*\$", sql[index:])
            if match:
                tag = match.group(0)
                buffer.append(tag)
                index += len(tag)
                continue
            character = sql[index]
            if character == "-" and sql[index:index + 2] == "--":
                end = sql.find("\n", index)
                index = len(sql) if end < 0 else end + 1
                continue
            if character == "'":
                end = index + 1
                while end < len(sql):
                    if sql[end] == "'":
                        if sql[end:end + 2] == "''":
                            end += 2
                            continue
                        break
                    end += 1
                buffer.append(sql[index:end + 1])
                index = end + 1
                continue
            if character == ";":
                statement = "".join(buffer).strip()
                if statement:
                    statements.append(statement)
                buffer = []
                index += 1
                continue
            buffer.append(character)
            index += 1
        else:
            if sql[index:index + len(tag)] == tag:
                buffer.append(tag)
                index += len(tag)
                tag = None
                continue
            buffer.append(sql[index])
            index += 1
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def apply_file(db, label, path):
    """Apply one file in a single transaction, rolling back on any error."""
    body = [s for s in split_statements(read(path))
            if s.upper() not in ("BEGIN", "COMMIT")
            and not s.upper().startswith("SET SEARCH_PATH")]

    # No migration in this deployment creates or alters a PostgreSQL type.
    # Outcome legitimacy is governed by version through is_valid_outcome_v2,
    # not by an enum, and an enum could not express a version scope anyway.
    offending = [s for s in body if s.upper().startswith(("ALTER TYPE", "CREATE TYPE"))]
    if offending:
        raise RuntimeError(
            f"{label} contains {len(offending)} type statement(s); the live "
            f"outcome contract is character varying and this deployment must "
            f"not create or alter a type: {offending[0][:120]}")

    print(f"\n-- applying {label} ({len(body)} statement(s))")
    try:
        for statement in body:
            db.execute(statement)
        db.commit()
        print(f"   committed: {label}")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"   *** ROLLED BACK: {type(exc).__name__}: "
              f"{str(exc).strip()[:400]}")
        raise


def main() -> int:
    for path in (DDL, MIGRATION, AUTHORITATIVE, PROTOTYPE):
        if not os.path.exists(path):
            print(f"missing artifact: {path}")
            return 2

    with deploy_connection() as db:
        head("0. PREFLIGHT GUARDS")
        context = db.query("""
            SELECT current_database() AS database, current_user,
                   current_setting('server_version_num')::int AS version_num,
                   has_database_privilege(current_database(),'CREATE') AS db_create,
                   has_schema_privilege('claris','CREATE') AS claris_create,
                   to_regnamespace('ontology_authoring') IS NOT NULL AS authoring_exists
        """)[0]
        print(f"   {context}")

        if context["authoring_exists"]:
            print("\n   *** ontology_authoring ALREADY EXISTS -- REFUSING TO RERUN ***")
            print("   Run d4g3_preflight.py and inspect for drift before proceeding.")
            return 2
        if not context["db_create"] or not context["claris_create"]:
            print("\n   *** INSUFFICIENT PRIVILEGE -- REFUSING ***")
            print("   Required: CREATE on the database, CREATE on schema claris.")
            return 2

        payments_enum_before = db.scalar("""
            SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
            WHERE n.nspname='payments' AND t.typname='decision_outcome'""")
        before_census = schema_census(db)
        print(f"\n   BEFORE census: {len(before_census)} table(s), "
              f"{sum(before_census.values())} row(s) across "
              f"{len(WITNESS_SCHEMAS)} schema(s)")
        for table, n in sorted(before_census.items()):
            if n:
                print(f"      {table:<44} {n}")

        head("1. DEPLOY ontology_authoring (14 tables)")
        apply_file(db, "001_ontology_authoring_schema.sql", DDL)

        head("2. APPLY D4G2 RUNTIME MIGRATION")
        apply_file(db, "D4G2_001_prototype_runtime_contract.sql", MIGRATION)

        head("3. LOAD AUTHORITATIVE RESTORATION (135 rows)")
        apply_file(db, "002_restore_2026_10.sql", AUTHORITATIVE)

        head("4. LOAD PROTOTYPE RELEASE (34 rows)")
        apply_file(db, "003_prototype_2026_10_P1.sql", PROTOTYPE)

        # ------------------------------------------------------------------
        from d4g3_verify import run_verification

        FAILURES.extend(run_verification(db))

        head("12B. DEPLOYMENT DELTA -- NOTHING OUTSIDE THE NEW SCHEMA MOVED")
        after_census = schema_census(db)
        moved = {t: (before_census.get(t), n) for t, n in after_census.items()
                 if before_census.get(t) != n}
        if moved:
            print("   *** ROWS MOVED ***")
            for table, (before, after) in sorted(moved.items()):
                print(f"      {table:<44} {before} -> {after}")
        check("no table in any witness schema changed", moved, {})
        check("no table appeared outside ontology_authoring",
              sorted(set(after_census) - set(before_census)), [])
        check("no table vanished",
              sorted(set(before_census) - set(after_census)), [])

        head("13. RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} VERIFICATION FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        print("   D.4G.3 DEPLOYMENT VERIFIED -- all checks passed")
        print("   Nothing compiled. Nothing activated. No decision executed.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(3)
