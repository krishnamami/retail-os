r"""STEP 5G.6 PHASE D.4G.4 -- PRE-IMPLEMENTATION GATE (READ ONLY).

Answers, from the live database rather than from repository DDL, the question
that decides whether D.4G.4 can finish:

    can this artifact model represent an ACTIVE prototype artifact WITHOUT
    displacing or breaking the production ACTIVE KB?

Also captures the compilation source witness and the protected-table BEFORE
counts. Writes nothing.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g4_gate.py
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

PROTOTYPE = "2026.10-prototype.1"
AUTHORITATIVE = "2026.10"

WITNESS_SCHEMAS = ("claris", "claris_kb", "ontology", "raw", "state",
                   "payments", "audit", "runtime", "public",
                   "ontology_authoring")


def head(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def show(db, label, sql, params=None, width=1200):
    print(f"\n-- {label} " + "-" * max(0, 56 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:220]}")
        return []
    if not rows:
        print("   (no rows)")
    for row in rows:
        text = " | ".join(
            f"{k}={'NULL' if v is None else str(v)[:width]}" for k, v in row.items())
        print("   " + text.encode("ascii", "replace").decode("ascii"))
    return rows


def main() -> int:
    with read_only_connection() as db:
        head("1. ARTIFACT MODEL -- can it hold a scoped prototype artifact?")
        show(db, "claris_kb relations", """
            SELECT c.relname AS name,
                   CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view'
                                  WHEN 'm' THEN 'matview' ELSE c.relkind::text END AS kind
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='claris_kb' AND c.relkind IN ('r','v','m')
            ORDER BY 2, 1
        """)
        show(db, "kb_artifact columns", """
            SELECT ordinal_position AS pos, column_name, data_type,
                   character_maximum_length AS width, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema='claris_kb' AND table_name='kb_artifact'
            ORDER BY 1
        """)
        show(db, "does ANY claris_kb column carry governance classification?", """
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema='claris_kb'
              AND column_name IN ('release_class','governance_basis',
                                  'validation_status','execution_mode')
            ORDER BY 1,2
        """)
        # column names read from the catalogue, never from repository DDL.
        # Assuming them is what broke this script's first run, and it is the
        # third time repository DDL has misdescribed this database.
        artifact_columns = [r["column_name"] for r in db.query("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='claris_kb' AND table_name='kb_artifact'
              AND data_type <> 'jsonb'
            ORDER BY ordinal_position""")]
        show(db, "kb_artifact rows (metadata only, no payload)",
             "SELECT %s FROM claris_kb.kb_artifact ORDER BY kb_version"
             % ", ".join(artifact_columns))
        show(db, "kb_artifact constraints", """
            SELECT conname, contype, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'claris_kb.kb_artifact'::regclass ORDER BY 1
        """)

        head("2. ACTIVATION MECHANISM -- the decisive question")
        show(db, "v_active_kb definition", """
            SELECT pg_get_viewdef('claris_kb.v_active_kb'::regclass, true) AS definition
        """)
        show(db, "v_active_kb currently returns", "SELECT * FROM claris_kb.v_active_kb")
        show(db, "v_active_decision_rules definition", """
            SELECT pg_get_viewdef('claris_kb.v_active_decision_rules'::regclass, true)
                   AS definition
        """)
        show(db, "how many artifacts are ACTIVE right now?", """
            SELECT status, count(*) AS n
            FROM claris_kb.kb_artifact GROUP BY 1 ORDER BY 1
        """)
        show(db, "every view in claris_kb that filters on ACTIVE", """
            SELECT c.relname AS view
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='claris_kb' AND c.relkind='v'
              AND pg_get_viewdef(c.oid, true) ILIKE '%ACTIVE%'
            ORDER BY 1
        """)

        head("3. COMPILATION SOURCE WITNESS -- 2026.10-prototype.1")
        show(db, "prototype release", """
            SELECT ontology_version, release_class, validation_status, status,
                   parent_ontology_version, parent_release_class,
                   source_namespace, left(content_digest,16)||'...' AS content_digest
            FROM ontology_authoring.ontology_release WHERE ontology_version=%s
        """, (PROTOTYPE,))
        print("\n-- row census per authoring table, per release "
              + "-" * 18)
        for table in ("ontology_release", "ontology_notes", "enums", "enum_values",
                      "actors", "configuration_dimensions", "identity_rules",
                      "decisions", "decision_outputs", "decision_dependencies",
                      "projection_rules", "evidence_reference",
                      "decision_reason_codes", "decision_rule_bindings"):
            has_version = db.scalar("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_schema='ontology_authoring' AND table_name=%s
                  AND column_name='ontology_version'""", (table,))
            if has_version:
                rows = db.query(
                    f"SELECT ontology_version, count(*) AS n "
                    f"FROM ontology_authoring.{table} GROUP BY 1 ORDER BY 1")
                summary = ", ".join(f"{r['ontology_version']}={r['n']}" for r in rows)
            else:
                summary = f"(no ontology_version column) total=" + str(
                    db.scalar(f"SELECT count(*) FROM ontology_authoring.{table}"))
            print(f"   {table:<28} {summary or '(empty)'}")

        head("4. PROTECTED TABLES -- BEFORE COUNTS")
        census = {}
        for row in db.query("""
                SELECT schemaname AS s, tablename AS t FROM pg_tables
                WHERE schemaname = ANY(%s) ORDER BY 1,2""", (list(WITNESS_SCHEMAS),)):
            q = f'{row["s"]}.{row["t"]}'
            census[q] = db.scalar(f'SELECT count(*) FROM "{row["s"]}"."{row["t"]}"')
        print(f"   {len(census)} table(s), {sum(census.values())} row(s)\n")
        for table, n in sorted(census.items()):
            if n:
                print(f"      {table:<48} {n}")
        print("\n   PROTECTED (must not change):")
        for table in ("claris.product", "claris.configuration",
                      "claris.configuration_version", "claris.decision",
                      "claris.action_record", "claris.configuration_state",
                      "claris.evidence", "claris.configuration_assertion",
                      "runtime.assertion", "runtime.evidence",
                      "state.fold_state_snapshot", "raw.raw_event"):
            print(f"      {table:<48} {census.get(table, '(absent)')}")

        head("5. GATE VERDICT")
        active = db.scalar(
            "SELECT count(*) FROM claris_kb.kb_artifact WHERE status='ACTIVE'")
        scoped = db.scalar("""
            SELECT count(*) FROM information_schema.columns
            WHERE table_schema='claris_kb' AND table_name='kb_artifact'
              AND column_name IN ('release_class','governance_basis')""")
        singleton = "count(*)" in (db.scalar(
            "SELECT pg_get_viewdef('claris_kb.v_active_kb'::regclass, true)") or "")
        print(f"   artifacts currently ACTIVE            : {active}")
        print(f"   v_active_kb is a fail-closed singleton: {singleton}")
        print(f"   kb_artifact classification columns    : {scoped}")
        if scoped == 0:
            print("\n   *** kb_artifact CANNOT DISTINGUISH a prototype artifact from a")
            print("       production one. Publishing an ACTIVE prototype row would make")
            print("       the ACTIVE set ambiguous and, if v_active_kb is a fail-closed")
            print("       singleton, would return NO active KB at all -- breaking")
            print("       production resolution. Read the v_active_kb definition above.")
            print("\n   D.4G.4 ACTIVATION IS MECHANICALLY BLOCKED unless the artifact")
            print("   model is extended. Report before changing anything.")
            return 2
        print("\n   kb_artifact can carry classification; scoped activation may be safe.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(1)
