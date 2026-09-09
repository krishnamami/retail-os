r"""STEP 5G.6 PHASE D.4F -- READ-ONLY governance discovery.

Not a pytest module (deliberately not named test_*): it is a one-shot
discovery report. It performs NO writes of any kind.

    cd C:\Users\bkgou\OneDrive\Documents\retail_os
    .\venv\Scripts\python.exe tests\decisions\integration\d4f_discovery.py

Safety: every statement goes through decisions.adapters.connection, whose gate
refuses anything that is not SELECT/WITH before it reaches the server, on a
session pinned READ ONLY. Before/after witnesses bracket the whole run.
"""

from __future__ import annotations

import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _path in (_REPO_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from decisions.adapters.connection import read_only_connection  # noqa: E402
from live_support import kb_status_fingerprint, row_counts  # noqa: E402

WITNESS_TABLES = (
    "claris.decision", "claris.action_record", "claris.product",
    "claris.configuration", "claris.configuration_version",
    "claris_kb.decision_rules", "claris_kb.identity_rules",
)


def head(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def sub(title: str) -> None:
    print(f"\n-- {title} " + "-" * max(0, 70 - len(title)))


def show(db, label, sql, params=None, limit=200):
    """Run one read and print it, or print why it could not run."""
    sub(label)
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001 - discovery: report, never abort
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:300]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for row in rows[:limit]:
        parts = []
        for k, v in row.items():
            text = "NULL" if v is None else str(v)
            if len(text) > 300:
                text = text[:300] + "...<truncated>"
            parts.append(f"{k}={text}")
        print("   " + " | ".join(parts))
    if len(rows) > limit:
        print(f"   ... {len(rows) - limit} more rows")
    return rows


def columns_of(db, schema, table):
    return show(
        db,
        f"columns of {schema}.{table}",
        """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )


def constraints_of(db, schema, table):
    return show(
        db,
        f"check constraints on {schema}.{table}",
        """
        SELECT c.conname, pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = %s AND t.relname = %s
        ORDER BY c.contype, c.conname
        """,
        (schema, table),
    )


def main() -> int:
    with read_only_connection() as db:
        head("0. CONNECTION AND READ-ONLY VERIFICATION")
        print(f"   context: {db.context()}")
        print(f"   session_is_read_only(): {db.session_is_read_only()}")

        before_counts = row_counts(db)
        before_kb = kb_status_fingerprint(db)
        print(f"   BEFORE row counts: {before_counts}")

        # ================================================================
        head("1. WHAT ACTUALLY EXISTS IN THIS POSTGRES DATABASE")
        show(db, "schemas", """
            SELECT nspname AS schema
            FROM pg_namespace
            WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
            ORDER BY 1
        """)
        show(db, "tables and views in claris / claris_kb / ontology / state", """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema IN ('claris','claris_kb','ontology','state','public')
            ORDER BY table_schema, table_type, table_name
        """)
        show(db, "any relation whose name mentions ontology / kb / policy / authority", """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_name ~* '(ontology|kb_|policy|authorit|actor|role|entitle|permission|auth)'
            ORDER BY table_schema, table_name
        """)

        # ================================================================
        head("2. SECTION 3 -- THE FIFTH PROPOSED 1.0.1 IDENTITY RULE")
        columns_of(db, "claris_kb", "identity_rules")
        constraints_of(db, "claris_kb", "identity_rules")
        show(db, "ALL claris_kb.identity_rules rows (every column)",
             "SELECT * FROM claris_kb.identity_rules ORDER BY kb_version, rule_id")
        show(db, "status x kb_version distribution", """
            SELECT kb_version, status, count(*) AS n
            FROM claris_kb.identity_rules GROUP BY 1,2 ORDER BY 1,2
        """)
        show(db, "proposed @ 1.0.1 ONLY", """
            SELECT * FROM claris_kb.identity_rules
            WHERE kb_version = '1.0.1' AND status = 'proposed'
            ORDER BY rule_id
        """)

        # ================================================================
        head("3. SECTION 4/7 -- EXECUTABLE RULE LAYER AND ACTIVE VIEW")
        columns_of(db, "claris_kb", "decision_rules")
        constraints_of(db, "claris_kb", "decision_rules")
        show(db, "distinct decision_rules status / decision_type / versions", """
            SELECT decision_type, kb_version, ontology_version,
                   coalesce(nullif(policy_version,''), '<EMPTY>') AS policy_version,
                   status, count(*) AS n
            FROM claris_kb.decision_rules
            GROUP BY 1,2,3,4,5 ORDER BY 1,2,5
        """)
        show(db, "ALL decision_rules rows (governance columns)", """
            SELECT decision_rule_id, decision_type, kb_version, ontology_version,
                   coalesce(nullif(policy_version,''),'<EMPTY>') AS policy_version,
                   precedence, outcome_code, status, authority
            FROM claris_kb.decision_rules
            ORDER BY decision_type, precedence, decision_rule_id
        """)
        show(db, "v_active_decision_rules DEFINITION",
             "SELECT pg_get_viewdef('claris_kb.v_active_decision_rules'::regclass, true) AS definition")
        show(db, "v_active_kb DEFINITION",
             "SELECT pg_get_viewdef('claris_kb.v_active_kb'::regclass, true) AS definition")
        show(db, "columns exposed by v_active_decision_rules", """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema='claris_kb' AND table_name='v_active_decision_rules'
            ORDER BY ordinal_position
        """)
        show(db, "every view in claris_kb (names)", """
            SELECT table_name FROM information_schema.views
            WHERE table_schema='claris_kb' ORDER BY 1
        """)

        # ================================================================
        head("4. SECTION 5 -- KB VERSION / ARTIFACT / PROMOTION MECHANISM")
        show(db, "v_active_kb rows", "SELECT * FROM claris_kb.v_active_kb")
        columns_of(db, "claris_kb", "kb_artifact")
        show(db, "kb_artifact rows", "SELECT * FROM claris_kb.kb_artifact ORDER BY 1")
        show(db, "ontology.kb_versions", "SELECT * FROM ontology.kb_versions ORDER BY 1")
        show(db, "any table with kb_version column", """
            SELECT table_schema, table_name FROM information_schema.columns
            WHERE column_name = 'kb_version'
            GROUP BY 1,2 ORDER BY 1,2
        """)
        show(db, "functions/procedures in claris_kb / ontology (possible compiler/publisher)", """
            SELECT n.nspname AS schema, p.proname AS name,
                   pg_get_function_identity_arguments(p.oid) AS args
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname IN ('claris_kb','ontology','claris')
            ORDER BY 1,2
        """)

        # ================================================================
        head("5. SECTION 4/11 -- ONTOLOGY LAYER AS IT EXISTS IN POSTGRES")
        show(db, "tables in schema 'ontology'", """
            SELECT table_name, table_type FROM information_schema.tables
            WHERE table_schema='ontology' ORDER BY 1
        """)
        for table in ("decisions", "decision_outputs", "enums", "enum_values",
                      "decision_inputs", "actors", "roles"):
            show(db, f"ontology.{table} (all rows)",
                 f"SELECT * FROM ontology.{table} ORDER BY 1")
        show(db, "anything anywhere mentioning IDENTITY_ASSESSMENT in a text column", """
            SELECT 'decision_rules' AS src, decision_rule_id AS id, decision_type AS detail
            FROM claris_kb.decision_rules WHERE decision_type ILIKE '%IDENTITY%'
        """)

        # ================================================================
        head("6. SECTION 11/12 -- OUTCOME AND REASON CODE VOCABULARY")
        show(db, "relations whose name suggests outcome/reason vocabulary", """
            SELECT table_schema, table_name FROM information_schema.tables
            WHERE table_name ~* '(outcome|reason|effect|enum|vocab|code)'
            ORDER BY 1,2
        """)
        show(db, "columns named like outcome/reason/effect anywhere", """
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE column_name ~* '(outcome|reason|effect)'
            ORDER BY 1,2,3
        """)
        show(db, "distinct outcome_code values in decision_rules", """
            SELECT outcome_code, count(*) AS n FROM claris_kb.decision_rules
            GROUP BY 1 ORDER BY 1
        """)
        show(db, "distinct outcome/effect values in identity_rules", """
            SELECT * FROM claris_kb.identity_rules LIMIT 0
        """)

        # ================================================================
        head("7. SECTION 14 -- BUSINESS AUTHORITY")
        show(db, "authority values on decision_rules", """
            SELECT decision_type, coalesce(authority,'<NULL>') AS authority, count(*) AS n
            FROM claris_kb.decision_rules GROUP BY 1,2 ORDER BY 1,2
        """)
        show(db, "columns named like authority/owner/approver anywhere", """
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE column_name ~* '(authority|owner|approver|approved|signed|steward)'
            ORDER BY 1,2,3
        """)

        # ================================================================
        head("8. SECTION 21 -- claris.decision PERSISTENCE SHAPE")
        columns_of(db, "claris", "decision")
        constraints_of(db, "claris", "decision")
        columns_of(db, "claris", "action_record")

        # ================================================================
        head("9. SECTION 22 -- AUTHORIZATION SUBSTRATE")
        show(db, "any relation that could be an authorization substrate", """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_name ~* '(auth|entitle|permission|grant|approval|policy)'
            ORDER BY 1,2
        """)

        # ================================================================
        head("10. SECTION 15/16 -- CANONICAL AND IDENTITY-EFFECT GOVERNANCE")
        columns_of(db, "claris", "configuration")
        constraints_of(db, "claris", "configuration")
        columns_of(db, "claris", "product")
        columns_of(db, "claris", "configuration_version")
        show(db, "columns mentioning identity anywhere", """
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE column_name ~* 'identity'
            ORDER BY 1,2,3
        """)

        # ================================================================
        head("11. AFTER WITNESS")
        after_counts = row_counts(db)
        after_kb = kb_status_fingerprint(db)
        print(f"   AFTER row counts : {after_counts}")
        print(f"   counts identical : {after_counts == before_counts}")
        print(f"   KB fingerprint identical: {after_kb == before_kb}")
        print(f"   session_is_read_only(): {db.session_is_read_only()}")
        if after_counts != before_counts or after_kb != before_kb:
            print("   *** D.4F DISCOVERY FAILED -- DATABASE STATE MUTATED ***")
            return 1
        print("\n   D.4F READ-ONLY DISCOVERY COMPLETE -- ZERO MUTATIONS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
