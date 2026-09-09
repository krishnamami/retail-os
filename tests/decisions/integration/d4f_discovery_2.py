r"""STEP 5G.6 PHASE D.4F -- READ-ONLY discovery, round 2.

Round 1 established the schema map. This round closes the three gaps that
round 1 could not answer without guessing:

  * full view definitions (round 1 truncated the WHERE clauses -- and the
    WHERE clause IS the runtime eligibility contract, section 7)
  * the real ontology layer, which lives in claris_kb.decisions /
    decision_outputs / decision_outcomes, NOT in schema `ontology`
    (that schema holds only loader functions and is permission-denied)
  * the outcome-validation and persistence functions

No writes. Same SELECT/WITH gate, same READ ONLY pin, same witnesses.

    .\venv\Scripts\python.exe tests\decisions\integration\d4f_discovery_2.py
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


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def show(db, label, sql, params=None, limit=300, width=4000):
    print(f"\n-- {label} " + "-" * max(0, 68 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:300]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for row in rows[:limit]:
        if len(row) == 1:
            (value,) = row.values()
            print("   " + ("NULL" if value is None else str(value)[:width]))
        else:
            parts = []
            for k, v in row.items():
                s = "NULL" if v is None else str(v)
                parts.append(f"{k}={s[:width]}")
            print("   " + " | ".join(parts))
    if len(rows) > limit:
        print(f"   ... {len(rows) - limit} more")
    return rows


def cols(db, schema, table):
    return show(db, f"columns of {schema}.{table}", """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position
    """, (schema, table))


def checks(db, schema, table):
    return show(db, f"constraints on {schema}.{table}", """
        SELECT c.conname, pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class t ON t.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname=%s AND t.relname=%s ORDER BY c.contype, c.conname
    """, (schema, table))


def main() -> int:
    with read_only_connection() as db:
        head("0. READ-ONLY + BEFORE WITNESS")
        print(f"   session_is_read_only(): {db.session_is_read_only()}")
        before_counts, before_kb = row_counts(db), kb_status_fingerprint(db)
        print(f"   BEFORE: {before_counts}")

        # ==============================================================
        head("1. SECTION 6/7 -- FULL VIEW DEFINITIONS (untruncated)")
        for view in ("v_active_decision_rules", "v_active_kb", "v_active_decisions",
                     "v_active_decision_outputs", "v_active_identity_rules",
                     "v_active_decision_inputs", "v_active_actors"):
            show(db, f"DEFINITION claris_kb.{view}",
                 "SELECT pg_get_viewdef(%s::regclass, true) AS d", (f"claris_kb.{view}",))

        # ==============================================================
        head("2. SECTION 6 -- EXECUTABLE RULE STATUS MODEL")
        show(db, "decision_rules governance columns, ALL rows", """
            SELECT decision_rule_id, decision_type, kb_version, ontology_version,
                   parent_ontology_version, precedence, outcome_code, status,
                   authority, effective_from, effective_to, created_at,
                   left(coalesce(condition,''), 90) AS condition_head,
                   left(coalesce(required_evidence,''), 60) AS required_evidence_head,
                   left(coalesce(missing_evidence_action,''), 40) AS missing_action,
                   left(coalesce(contradiction_action,''), 40) AS contradiction_action,
                   left(coalesce(blocking_note,''), 60) AS blocking_note_head
            FROM claris_kb.decision_rules
            ORDER BY decision_type, precedence, decision_rule_id
        """)
        show(db, "distinct status values in decision_rules", """
            SELECT coalesce(status,'<NULL>') AS status, count(*) AS n
            FROM claris_kb.decision_rules GROUP BY 1 ORDER BY 1
        """)
        show(db, "distinct status values across every governed KB table", """
            SELECT 'decision_rules' AS t, coalesce(status,'<NULL>') AS status, count(*) FROM claris_kb.decision_rules GROUP BY 2
            UNION ALL SELECT 'identity_rules', coalesce(status,'<NULL>'), count(*) FROM claris_kb.identity_rules GROUP BY 2
            UNION ALL SELECT 'decisions', coalesce(status,'<NULL>'), count(*) FROM claris_kb.decisions GROUP BY 2
            UNION ALL SELECT 'decision_outputs', coalesce(status,'<NULL>'), count(*) FROM claris_kb.decision_outputs GROUP BY 2
            UNION ALL SELECT 'kb_artifact', coalesce(status,'<NULL>'), count(*) FROM claris_kb.kb_artifact GROUP BY 2
            ORDER BY 1,2
        """)

        # ==============================================================
        head("3. SECTION 4/11 -- THE REAL ONTOLOGY LAYER (claris_kb)")
        for table in ("decisions", "decision_outputs", "decision_outcomes",
                      "decision_inputs", "actors", "departments",
                      "projection_rules", "evidence_types"):
            cols(db, "claris_kb", table)
            checks(db, "claris_kb", table)
            show(db, f"claris_kb.{table} ALL ROWS", f"SELECT * FROM claris_kb.{table}")

        # ==============================================================
        head("4. SECTION 11 -- IDENTITY_ASSESSMENT OUTCOME CONTRACT")
        show(db, "decision types known to the KB", """
            SELECT DISTINCT decision_type FROM claris_kb.decisions
            UNION SELECT DISTINCT decision_type FROM claris_kb.decision_outputs
            UNION SELECT DISTINCT decision_type FROM claris_kb.decision_rules
            ORDER BY 1
        """)
        show(db, "ALL decision_outputs for IDENTITY_ASSESSMENT", """
            SELECT * FROM claris_kb.decision_outputs
            WHERE decision_type ILIKE '%IDENTITY%' ORDER BY 1
        """)
        show(db, "v_active_decision_outputs for IDENTITY_ASSESSMENT", """
            SELECT * FROM claris_kb.v_active_decision_outputs
            WHERE decision_type ILIKE '%IDENTITY%' ORDER BY 1
        """)
        show(db, "decision_inputs for IDENTITY_ASSESSMENT", """
            SELECT * FROM claris_kb.decision_inputs
            WHERE decision_type ILIKE '%IDENTITY%' ORDER BY 1
        """)
        show(db, "is_valid_outcome() SOURCE", """
            SELECT pg_get_functiondef(p.oid) AS d FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='claris' AND p.proname='is_valid_outcome'
        """)

        # ==============================================================
        head("5. SECTION 13 -- POLICY VERSION AUTHORITY")
        show(db, "kb_artifact policy/ontology/kb versions", """
            SELECT kb_version, ontology_version,
                   coalesce(policy_version,'<NULL>') AS policy_version,
                   status, source_system, source_catalog, source_schema, deployed_at
            FROM claris_kb.kb_artifact ORDER BY deployed_at
        """)
        cols(db, "runtime", "governed_policy")
        show(db, "runtime.governed_policy ALL ROWS", "SELECT * FROM runtime.governed_policy")
        cols(db, "runtime", "governed_knowledge_base")
        show(db, "runtime.governed_knowledge_base (versions only)", """
            SELECT * FROM runtime.governed_knowledge_base LIMIT 20
        """)
        show(db, "does the ACTIVE kb_json carry an IDENTITY_ASSESSMENT section?", """
            SELECT kb_version, jsonb_object_keys(kb_json->'sections') AS section
            FROM claris_kb.kb_artifact WHERE status='ACTIVE'
        """)
        show(db, "ACTIVE kb_json decision_rules section, decision types", """
            SELECT DISTINCT r->>'decision_type' AS decision_type, count(*) AS n
            FROM claris_kb.kb_artifact a,
                 jsonb_array_elements(a.kb_json->'sections'->'decision_rules') r
            WHERE a.status='ACTIVE' GROUP BY 1 ORDER BY 1
        """)
        show(db, "ACTIVE kb_json identity_rules section", """
            SELECT r AS identity_rule
            FROM claris_kb.kb_artifact a,
                 jsonb_array_elements(a.kb_json->'sections'->'identity_rules') r
            WHERE a.status='ACTIVE'
        """)

        # ==============================================================
        head("6. SECTION 14 -- BUSINESS AUTHORITY")
        show(db, "claris_kb.decisions authority/owner per decision type", """
            SELECT * FROM claris_kb.decisions ORDER BY 1
        """)
        show(db, "authority on decision_rules by type", """
            SELECT decision_type, coalesce(authority,'<NULL>') AS authority, count(*)
            FROM claris_kb.decision_rules GROUP BY 1,2 ORDER BY 1,2
        """)

        # ==============================================================
        head("7. SECTION 15/16 -- IDENTITY EFFECT AND CONFIGURATION VERSION")
        checks(db, "claris", "configuration_version")
        checks(db, "claris", "product")
        show(db, "any CHECK mentioning USE_EXISTING / NEW_VERSION / CREATE_CONFIGURATION", """
            SELECT n.nspname AS schema, t.relname AS table_name, c.conname,
                   pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint c
            JOIN pg_class t ON t.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE pg_get_constraintdef(c.oid) ~* '(USE_EXISTING|NEW_VERSION|CREATE_CONFIGURATION|CREATE_PRODUCT|NO_BUSINESS_CHANGE)'
            ORDER BY 1,2,3
        """)

        # ==============================================================
        head("8. SECTION 21/22 -- PERSISTENCE AND AUTHORIZATION SUBSTRATE")
        cols(db, "claris", "decision_evidence")
        checks(db, "claris", "action_record")
        cols(db, "claris", "approval_record")
        checks(db, "claris", "approval_record")
        cols(db, "claris", "execution_record")
        show(db, "execute_decision() SOURCE", """
            SELECT pg_get_functiondef(p.oid) AS d FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='claris' AND p.proname='execute_decision'
        """)
        show(db, "authorize_action_execution() SOURCE", """
            SELECT pg_get_functiondef(p.oid) AS d FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='claris' AND p.proname='authorize_action_execution'
        """)

        # ==============================================================
        head("9. AFTER WITNESS")
        after_counts, after_kb = row_counts(db), kb_status_fingerprint(db)
        print(f"   AFTER : {after_counts}")
        print(f"   counts identical        : {after_counts == before_counts}")
        print(f"   KB fingerprint identical: {after_kb == before_kb}")
        print(f"   session_is_read_only()  : {db.session_is_read_only()}")
        if after_counts != before_counts or after_kb != before_kb:
            print("   *** D.4F DISCOVERY FAILED -- DATABASE STATE MUTATED ***")
            return 1
        print("\n   D.4F ROUND 2 COMPLETE -- ZERO MUTATIONS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
