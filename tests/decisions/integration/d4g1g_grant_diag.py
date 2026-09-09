r"""STEP 5G.6 D.4G.1G.1 -- grant diagnostic (READ-ONLY, ~2 seconds).

The audit aborted with usage_ok=False. This determines WHY, so the fix is one
step rather than several. Reads pg_catalog only. No GRANT, no SET ROLE, no
ALTER, no impersonation.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g1g_grant_diag.py
"""

from __future__ import annotations

import os
import sys
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (_REPO_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from decisions.adapters.connection import read_only_connection  # noqa: E402


def show(db, label, sql, params=None):
    print(f"\n-- {label} " + "-" * max(0, 58 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:200]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for r in rows:
        print("   " + " | ".join(f"{k}={'NULL' if v is None else v}"
                                 for k, v in r.items())
              .encode("ascii", "replace").decode("ascii"))
    return rows


def main() -> int:
    with read_only_connection() as db:
        print("=" * 70 + "\nD.4G.1G.1 GRANT DIAGNOSTIC\n" + "=" * 70)

        show(db, "which database am I actually in?",
             "SELECT current_database(), current_user, session_user, version()")

        show(db, "does the reader role exist, and does the login INHERIT?", """
            SELECT rolname, rolcanlogin, rolinherit, rolsuper
            FROM pg_roles
            WHERE rolname IN ('claris_ingestion','claris_governance_reader')
            ORDER BY 1
        """)

        show(db, "membership edges involving either role", """
            SELECT r.rolname AS role_granted, me.rolname AS granted_to,
                   m.admin_option
            FROM pg_auth_members m
            JOIN pg_roles r  ON r.oid  = m.roleid
            JOIN pg_roles me ON me.oid = m.member
            WHERE r.rolname  IN ('claris_governance_reader')
               OR me.rolname IN ('claris_ingestion','claris_governance_reader')
            ORDER BY 1,2
        """)

        show(db, "ontology schema ACL now (did GRANT USAGE land here?)", """
            SELECT nspname, pg_get_userbyid(nspowner) AS owner,
                   coalesce(nspacl::text,'<NULL - no grants>') AS acl
            FROM pg_namespace WHERE nspname='ontology'
        """)

        show(db, "SELECT grants on ontology tables, by grantee", """
            SELECT grantee, count(*) AS tables_with_select
            FROM information_schema.role_table_grants
            WHERE table_schema='ontology' AND privilege_type='SELECT'
            GROUP BY 1 ORDER BY 1
        """)

        show(db, "effective privilege: direct vs via reader role", """
            SELECT has_schema_privilege('claris_ingestion','ontology','USAGE')
                     AS ingestion_usage,
                   has_schema_privilege('claris_governance_reader','ontology','USAGE')
                     AS reader_usage,
                   pg_has_role('claris_ingestion','claris_governance_reader','USAGE')
                     AS ingestion_can_use_reader,
                   pg_has_role('claris_ingestion','claris_governance_reader','MEMBER')
                     AS ingestion_is_member
        """)

        print("\n" + "=" * 70)
        print("INTERPRETATION KEY")
        print("=" * 70)
        print("  reader_usage=true + ingestion_is_member=false")
        print("     -> the membership GRANT was not run. Fix: one statement.")
        print("  ingestion_is_member=true + ingestion_can_use_reader=false")
        print("     -> claris_ingestion has NOINHERIT. Fix: ALTER ROLE ... INHERIT")
        print("        (or use a login that inherits).")
        print("  reader_usage=false + acl NULL")
        print("     -> the grants did not land in database 'accord'.")
        print("  reader role absent entirely")
        print("     -> the DDL ran elsewhere or was rolled back.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
