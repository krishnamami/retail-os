r"""STEP 5G.6 PHASE D.4G.1F -- F.1 AUTHORIZED ACCESS GATE (READ-ONLY).

Determines whether an ALREADY-AUTHORIZED path to schema `ontology` exists for
the connection this repository is configured to use. Performs no GRANT, no
SET ROLE, no ALTER, no impersonation, and requests no credentials.

If no authorized path exists the phase stops here: ONTOLOGY AUTHORING ACCESS
-- BLOCKED. Nothing is implemented.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g1f_access_gate.py
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

ONTOLOGY_TABLES = [
    "decisions", "decision_inputs", "decision_outputs", "identity_rules",
    "configuration_dimensions", "action_types", "action_authorizations",
    "read_grants", "roles", "projection_rules", "evidence_types",
    "use_cases", "kb_store", "kb_versions", "policy_versions",
]


def show(db, label, sql, params=None, width=700):
    print(f"\n-- {label} " + "-" * max(0, 60 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:250]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for row in rows:
        if len(row) == 1:
            (v,) = row.values()
            t = "NULL" if v is None else str(v)[:width]
        else:
            t = " | ".join(f"{k}={'NULL' if v is None else str(v)[:width]}"
                           for k, v in row.items())
        print("   " + t.encode("ascii", "replace").decode("ascii"))
    return rows


def main() -> int:
    with read_only_connection() as db:
        print("=" * 78 + "\nD.4G.1F -- F.1 AUTHORIZED ACCESS GATE\n" + "=" * 78)
        print(f"   session_is_read_only(): {db.session_is_read_only()}")

        # -- preflight DB witness (section 1) ---------------------------
        before = row_counts(db)
        before_kb = kb_status_fingerprint(db)
        print(f"   BEFORE witness: {before}")
        show(db, "ACTIVE artifact", """
            SELECT count(*) OVER () AS active_count, kb_version, status, content_digest
            FROM claris_kb.kb_artifact WHERE status='ACTIVE'
        """)

        # -- identity ---------------------------------------------------
        show(db, "connection identity", """
            SELECT current_user, session_user, current_database(),
                   current_setting('transaction_read_only') AS read_only
        """)

        # -- schema-level privilege ------------------------------------
        show(db, "schema privileges for the CURRENT user", """
            SELECT nspname AS schema,
                   has_schema_privilege(nspname,'USAGE')  AS usage,
                   has_schema_privilege(nspname,'CREATE') AS create_priv,
                   pg_get_userbyid(nspowner)              AS schema_owner
            FROM pg_namespace
            WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
            ORDER BY 1
        """)

        # -- table-level privilege on ontology --------------------------
        show(db, "table privileges on ontology.* for CURRENT user", """
            SELECT t AS table_name,
                   to_regclass('ontology.'||t) IS NOT NULL AS exists,
                   has_table_privilege('ontology.'||t,'SELECT') AS can_select,
                   has_table_privilege('ontology.'||t,'INSERT') AS can_insert
            FROM unnest(%s::text[]) t ORDER BY 1
        """, (ONTOLOGY_TABLES,))

        # -- role membership: is there a role we hold that CAN read? -----
        show(db, "roles this login is a member of", """
            SELECT r.rolname AS member_of, r.rolsuper, r.rolcreaterole, r.rolcreatedb
            FROM pg_auth_members m
            JOIN pg_roles r ON r.oid = m.roleid
            JOIN pg_roles me ON me.oid = m.member
            WHERE me.rolname = current_user
            ORDER BY 1
        """)
        show(db, "ALL roles in the cluster (names/attributes only, no secrets)", """
            SELECT rolname, rolcanlogin, rolsuper, rolcreaterole,
                   has_schema_privilege(rolname,'ontology','USAGE') AS ontology_usage
            FROM pg_roles
            WHERE rolname NOT LIKE 'pg_%'
            ORDER BY 1
        """)

        # -- who granted what on ontology (ACL introspection) -----------
        show(db, "ontology schema ACL", """
            SELECT nspname, pg_get_userbyid(nspowner) AS owner, nspacl::text AS acl
            FROM pg_namespace WHERE nspname = 'ontology'
        """)
        show(db, "any grantee with SELECT on an ontology table", """
            SELECT DISTINCT grantee, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema = 'ontology'
            ORDER BY 1,2
        """)

        # -- default-privilege / alternate path check --------------------
        show(db, "can the current user read ontology at all? (definitive test)", """
            SELECT has_schema_privilege('ontology','USAGE') AS ontology_usage,
                   has_schema_privilege('claris_kb','USAGE') AS claris_kb_usage,
                   has_schema_privilege('claris','USAGE') AS claris_usage
        """)

        # -- after witness ---------------------------------------------
        after = row_counts(db)
        after_kb = kb_status_fingerprint(db)
        print("\n" + "=" * 78 + "\nAFTER WITNESS\n" + "=" * 78)
        print(f"   AFTER witness: {after}")
        print(f"   counts identical        : {after == before}")
        print(f"   KB fingerprint identical: {after_kb == before_kb}")
        print(f"   session_is_read_only()  : {db.session_is_read_only()}")
        if after != before or after_kb != before_kb:
            print("   *** STATE MUTATED -- STOP ***")
            return 1
        print("\n   F.1 ACCESS GATE COMPLETE -- ZERO MUTATIONS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
