r"""STEP 5G.6 PHASE D.4F -- READ-ONLY discovery, round 3 (short).

Round 2 completed every query but crashed in print() on a cp1252 console
before its AFTER witness ran. This run re-establishes the section 23 witness
and closes three small gaps. Output is forced to UTF-8 with replacement so a
console encoding cannot abort it again.

    .\venv\Scripts\python.exe tests\decisions\integration\d4f_discovery_3.py
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


def show(db, label, sql, params=None, width=6000):
    print(f"\n-- {label} " + "-" * max(0, 66 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:300]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for row in rows:
        if len(row) == 1:
            (v,) = row.values()
            text = "NULL" if v is None else str(v)[:width]
            print("   " + text.encode("ascii", "replace").decode("ascii"))
        else:
            parts = [f"{k}={'NULL' if v is None else str(v)[:width]}" for k, v in row.items()]
            print("   " + " | ".join(parts).encode("ascii", "replace").decode("ascii"))
    return rows


def main() -> int:
    with read_only_connection() as db:
        print("=" * 78 + "\nD.4F ROUND 3 -- WITNESS AND REMAINING GAPS\n" + "=" * 78)
        print(f"   session_is_read_only(): {db.session_is_read_only()}")
        before_counts, before_kb = row_counts(db), kb_status_fingerprint(db)
        print(f"   BEFORE: {before_counts}")

        # -- V-5: can a v1:sha256:<64hex> digest actually fit? ----------
        show(db, "claris.decision column widths (V-5 fit check)", """
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_schema='claris' AND table_name='decision'
              AND data_type='character varying'
            ORDER BY ordinal_position
        """)
        show(db, "indexes / unique constraints on claris.decision and decision_evidence", """
            SELECT t.relname AS table_name, i.relname AS index_name,
                   pg_get_indexdef(ix.indexrelid) AS definition
            FROM pg_index ix
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname='claris' AND t.relname IN ('decision','decision_evidence')
            ORDER BY 1,2
        """)

        # -- does ontology.decision_outputs (used by is_valid_outcome) exist?
        show(db, "relations that DO exist in schema ontology (pg_class, bypasses USAGE)", """
            SELECT c.relname, c.relkind
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='ontology' AND c.relkind IN ('r','v','m','p')
            ORDER BY 1
        """)
        show(db, "can claris_ingestion read ontology.decision_outputs?", """
            SELECT has_schema_privilege('ontology','USAGE') AS schema_usage,
                   to_regclass('ontology.decision_outputs') AS decision_outputs_oid
        """)

        # -- section 22: the remaining function ------------------------
        show(db, "authorize_action_execution() SOURCE", """
            SELECT pg_get_functiondef(p.oid) AS d FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='claris' AND p.proname='authorize_action_execution'
        """)

        # -- section 6 proof: status is NOT an execution gate -----------
        show(db, "PROOF: rows visible through v_active_decision_rules, by status", """
            SELECT status, count(*) AS visible_in_active_view
            FROM claris_kb.v_active_decision_rules GROUP BY 1 ORDER BY 1
        """)
        show(db, "PROOF: base-table rows NOT visible in the active view", """
            SELECT r.kb_version, coalesce(r.status,'<NULL>') AS status, count(*) AS hidden
            FROM claris_kb.decision_rules r
            WHERE NOT EXISTS (SELECT 1 FROM claris_kb.v_active_decision_rules v
                              WHERE v.decision_rule_id = r.decision_rule_id)
            GROUP BY 1,2 ORDER BY 1,2
        """)

        # -- AFTER witness ---------------------------------------------
        after_counts, after_kb = row_counts(db), kb_status_fingerprint(db)
        print("\n" + "=" * 78 + "\nAFTER WITNESS\n" + "=" * 78)
        print(f"   AFTER : {after_counts}")
        print(f"   counts identical        : {after_counts == before_counts}")
        print(f"   KB fingerprint identical: {after_kb == before_kb}")
        print(f"   session_is_read_only()  : {db.session_is_read_only()}")
        if after_counts != before_counts or after_kb != before_kb:
            print("   *** D.4F DISCOVERY FAILED -- DATABASE STATE MUTATED ***")
            return 1
        print("\n   D.4F ROUND 3 COMPLETE -- ZERO MUTATIONS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
