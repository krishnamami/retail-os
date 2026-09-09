r"""STEP 5G.6 PHASE D.4G.1G.1 -- G.2 LIVE ONTOLOGY AUDIT (READ-ONLY).

Runs only after the governance READ grant. Verifies access first and refuses
to continue without it. SELECT/WITH only, READ ONLY session, before/after
witnesses. Writer functions (ontology.load_kb_*) are never called.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g1g_ontology_audit.py
"""

from __future__ import annotations

import os
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

from decisions.adapters.connection import read_only_connection  # noqa: E402
from live_support import kb_status_fingerprint, row_counts  # noqa: E402


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def show(db, label, sql, params=None, width=900, limit=60):
    print(f"\n-- {label} " + "-" * max(0, 60 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:250]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for row in rows[:limit]:
        if len(row) == 1:
            (v,) = row.values()
            t = "NULL" if v is None else str(v)[:width]
        else:
            t = " | ".join(f"{k}={'NULL' if v is None else str(v)[:width]}"
                           for k, v in row.items())
        print("   " + t.encode("ascii", "replace").decode("ascii"))
    if len(rows) > limit:
        print(f"   ... {len(rows)-limit} more")
    return rows


def main() -> int:
    with read_only_connection() as db:
        head("0. ACCESS VERIFICATION + BEFORE WITNESS")
        print(f"   session_is_read_only(): {db.session_is_read_only()}")
        acc = db.query("""
            SELECT current_user, session_user,
                   has_schema_privilege('ontology','USAGE')  AS usage_ok,
                   has_schema_privilege('ontology','CREATE') AS create_priv
        """)[0]
        print(f"   {acc}")
        if not acc["usage_ok"]:
            print("\n   *** ONTOLOGY READ ACCESS NOT PRESENT -- ABORTING AUDIT ***")
            return 2
        if acc["create_priv"]:
            print("\n   *** WARNING: CREATE privilege present -- exceeds intended READ. ***")
            print("   *** Reporting and continuing read-only; no writes attempted.  ***")
        show(db, "roles this login now holds", """
            SELECT r.rolname AS member_of FROM pg_auth_members m
            JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles me ON me.oid=m.member
            WHERE me.rolname = current_user ORDER BY 1
        """)
        before, before_kb = row_counts(db), kb_status_fingerprint(db)
        before_digest = db.query(
            "SELECT kb_version, content_digest FROM claris_kb.kb_artifact WHERE status='ACTIVE'")
        print(f"   BEFORE: {before}")

        # ==============================================================
        head("1. SECTION 6 -- OBJECT INVENTORY")
        show(db, "all relations in schema ontology", """
            SELECT c.relname, c.relkind,
                   CASE c.relkind WHEN 'r' THEN c.reltuples::bigint END AS approx_rows,
                   obj_description(c.oid) AS comment
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='ontology' AND c.relkind IN ('r','v','m','p')
            ORDER BY c.relkind, c.relname
        """, limit=100)
        show(db, "ALL columns of every ontology table", """
            SELECT table_name, ordinal_position AS pos, column_name, data_type,
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema='ontology'
            ORDER BY table_name, ordinal_position
        """, limit=400)
        show(db, "constraints on ontology tables", """
            SELECT t.relname AS table_name, c.conname, c.contype,
                   pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint c
            JOIN pg_class t ON t.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='ontology'
            ORDER BY 1, c.contype, 2
        """, limit=200)
        show(db, "row counts (exact) per ontology table", """
            SELECT 'action_authorizations' t, count(*) FROM ontology.action_authorizations
            UNION ALL SELECT 'action_types', count(*) FROM ontology.action_types
            UNION ALL SELECT 'configuration_dimensions', count(*) FROM ontology.configuration_dimensions
            UNION ALL SELECT 'decision_inputs', count(*) FROM ontology.decision_inputs
            UNION ALL SELECT 'decision_outputs', count(*) FROM ontology.decision_outputs
            UNION ALL SELECT 'decisions', count(*) FROM ontology.decisions
            UNION ALL SELECT 'evidence_types', count(*) FROM ontology.evidence_types
            UNION ALL SELECT 'identity_rules', count(*) FROM ontology.identity_rules
            UNION ALL SELECT 'kb_store', count(*) FROM ontology.kb_store
            UNION ALL SELECT 'kb_versions', count(*) FROM ontology.kb_versions
            UNION ALL SELECT 'policy_versions', count(*) FROM ontology.policy_versions
            UNION ALL SELECT 'projection_rules', count(*) FROM ontology.projection_rules
            UNION ALL SELECT 'read_grants', count(*) FROM ontology.read_grants
            UNION ALL SELECT 'roles', count(*) FROM ontology.roles
            UNION ALL SELECT 'use_cases', count(*) FROM ontology.use_cases
            ORDER BY 1
        """, limit=40)

        # ==============================================================
        head("2. SECTION 7 -- CONTENT AUDIT")
        for tbl in ("decisions", "decision_inputs", "decision_outputs",
                    "identity_rules", "configuration_dimensions",
                    "action_types", "action_authorizations", "read_grants",
                    "roles", "policy_versions", "kb_versions", "evidence_types"):
            show(db, f"ontology.{tbl} -- ALL ROWS", f"SELECT * FROM ontology.{tbl}",
                 width=700, limit=60)
        show(db, "ontology.projection_rules -- ALL ROWS",
             "SELECT * FROM ontology.projection_rules", width=600, limit=40)
        show(db, "ontology.use_cases -- ALL ROWS",
             "SELECT * FROM ontology.use_cases", width=600, limit=40)

        # ==============================================================
        head("3. SECTION 11/12 -- DECISION TYPES AND VOCABULARY")
        show(db, "decision types known to ontology", """
            SELECT DISTINCT decision_type, 'decisions' AS src FROM ontology.decisions
            UNION SELECT DISTINCT decision_type, 'decision_outputs' FROM ontology.decision_outputs
            UNION SELECT DISTINCT decision_type, 'decision_inputs' FROM ontology.decision_inputs
            ORDER BY 1,2
        """, limit=40)
        show(db, "IDENTITY_ASSESSMENT rows anywhere in ontology", """
            SELECT 'decisions' src, decision_type::text AS v FROM ontology.decisions WHERE decision_type ILIKE '%IDENTIT%'
            UNION ALL SELECT 'decision_outputs', decision_type||' / '||outcome_code FROM ontology.decision_outputs WHERE decision_type ILIKE '%IDENTIT%'
            UNION ALL SELECT 'decision_inputs', decision_type::text FROM ontology.decision_inputs WHERE decision_type ILIKE '%IDENTIT%'
            UNION ALL SELECT 'action_authorizations', action_type::text FROM ontology.action_authorizations WHERE required_decision ILIKE '%IDENTIT%'
            ORDER BY 1,2
        """, limit=60)
        show(db, "all distinct outcome_code values", """
            SELECT decision_type, outcome_code,
                   coalesce(kb_version,'<NULL>') AS kb_version,
                   coalesce(policy_version,'<NULL>') AS policy_version
            FROM ontology.decision_outputs ORDER BY 1,2
        """, limit=60)

        # ==============================================================
        head("4. SECTION 12 -- KB STORE")
        show(db, "ontology.kb_store (metadata only, no payload)", """
            SELECT kb_version,
                   pg_column_size(kb_data) AS payload_bytes,
                   jsonb_typeof(kb_data) AS payload_type
            FROM ontology.kb_store ORDER BY 1
        """, limit=20)
        show(db, "ontology.kb_store payload top-level keys", """
            SELECT kb_version, jsonb_object_keys(kb_data) AS key
            FROM ontology.kb_store ORDER BY 1,2
        """, limit=80)
        show(db, "ontology.kb_versions ALL ROWS",
             "SELECT * FROM ontology.kb_versions ORDER BY 1", limit=20)
        show(db, "compare with claris_kb.kb_artifact", """
            SELECT kb_version, status, source_catalog, source_schema, content_digest
            FROM claris_kb.kb_artifact ORDER BY kb_version
        """, limit=20)

        # ==============================================================
        head("5. SECTION 8 -- QUESTION GOVERNANCE SEARCH")
        show(db, "any ontology table/column suggesting question governance", """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='ontology'
              AND (table_name ~* '(note|question|open|issue|gap)'
                OR column_name ~* '(question|owner|blocks|status|resolution|confirm|authority)')
            ORDER BY 1,2
        """, limit=100)

        # ==============================================================
        head("5B. SECTION 3 -- INDEXES AND SEQUENCES (coverage gap closed)")
        show(db, "indexes on ontology tables", """
            SELECT tablename, indexname, indexdef
            FROM pg_indexes WHERE schemaname='ontology' ORDER BY 1,2
        """, limit=120)
        show(db, "sequences in ontology", """
            SELECT c.relname, c.relkind
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='ontology' AND c.relkind='S' ORDER BY 1
        """, limit=40)
        show(db, "functions/procedures in ontology (names + kind)", """
            SELECT p.proname, p.prokind,
                   pg_get_function_identity_arguments(p.oid) AS args
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='ontology' ORDER BY 1
        """, limit=60)

        # ==============================================================
        head("5C. SECTION 9 -- LITERAL SEARCH FOR QUESTION CONTENT")
        show(db, "rows in ANY ontology table mentioning Q-001/Q-002/SLP/identity-affecting", """
            SELECT 'decisions' t, r::text AS row FROM ontology.decisions r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'decision_inputs', r::text FROM ontology.decision_inputs r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'decision_outputs', r::text FROM ontology.decision_outputs r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'identity_rules', r::text FROM ontology.identity_rules r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'configuration_dimensions', r::text FROM ontology.configuration_dimensions r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'use_cases', r::text FROM ontology.use_cases r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'projection_rules', r::text FROM ontology.projection_rules r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'roles', r::text FROM ontology.roles r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'read_grants', r::text FROM ontology.read_grants r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'action_types', r::text FROM ontology.action_types r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'action_authorizations', r::text FROM ontology.action_authorizations r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            UNION ALL SELECT 'evidence_types', r::text FROM ontology.evidence_types r WHERE r::text ~* '(Q-00[12]|identity[ _-]?dimension|SLP|identity[ _-]affecting)'
            ORDER BY 1
        """, width=700, limit=60)
        show(db, "ontology function bodies mentioning question/identity governance", """
            SELECT p.proname
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='ontology'
              AND p.prokind IN ('f','p')
              AND pg_get_functiondef(p.oid) ~* '(Q-00[12]|identity_affecting|blocks_identity|ontology_notes|question)'
            ORDER BY 1
        """, limit=40)
        show(db, "column comments across ontology", """
            SELECT c.relname AS table_name, a.attname AS column_name,
                   col_description(c.oid, a.attnum) AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0
            WHERE n.nspname='ontology' AND col_description(c.oid,a.attnum) IS NOT NULL
            ORDER BY 1,2
        """, limit=120)

        # ==============================================================
        head("5D. SECTION 18 -- LIVE VOCABULARIES, AGGREGATED")
        show(db, "distinct identity_effect / action / reason in projection_rules", """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='ontology' AND table_name='projection_rules'
            ORDER BY ordinal_position
        """, limit=40)
        show(db, "distinct values per projection_rules column (text cast)", """
            SELECT DISTINCT r::text AS distinct_row
            FROM ontology.projection_rules r ORDER BY 1
        """, width=500, limit=40)

        # ==============================================================
        head("6. AFTER WITNESS")
        after, after_kb = row_counts(db), kb_status_fingerprint(db)
        after_digest = db.query(
            "SELECT kb_version, content_digest FROM claris_kb.kb_artifact WHERE status='ACTIVE'")
        print(f"   AFTER : {after}")
        ok = (after == before and after_kb == before_kb and after_digest == before_digest)
        print(f"   counts identical        : {after == before}")
        print(f"   KB fingerprint identical: {after_kb == before_kb}")
        print(f"   ACTIVE digest identical : {after_digest == before_digest}")
        print(f"   session_is_read_only()  : {db.session_is_read_only()}")
        if not ok:
            print("   *** STATE MUTATED -- STOP ***")
            return 1
        print("\n   G.2 ONTOLOGY AUDIT COMPLETE -- ZERO MUTATIONS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
