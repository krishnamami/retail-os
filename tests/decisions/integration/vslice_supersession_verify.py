r"""Prove current-decision semantics against the live database. READ ONLY.

Run AFTER applying D4I_001 and re-running vslice_run.py, which is what
exercises the new supersession path.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_supersession_verify.py

Exit codes
    0  every invariant holds
    4  at least one does not
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

FAILURES: list = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    with read_only_connection() as db:
        head("1. DECISION HISTORY")
        for row in db.query("""
            SELECT subject_id, decision_type, count(*) AS total,
                   count(*) FILTER (WHERE state='current')    AS current,
                   count(*) FILTER (WHERE state='superseded') AS superseded
            FROM claris.decision GROUP BY 1,2 ORDER BY 1,2"""):
            print(f"   {row['subject_id']:<24}{row['decision_type']:<22}"
                  f"total={row['total']} current={row['current']} "
                  f"superseded={row['superseded']}")

        head("2. ONE CURRENT DECISION PER SUBJECT, TYPE AND GOVERNANCE SCOPE")
        offenders = db.query("""
            SELECT subject_type, subject_id, decision_type, governance_basis,
                   execution_mode, count(*) AS n
            FROM claris.decision
            WHERE state = 'current'
            GROUP BY 1,2,3,4,5 HAVING count(*) > 1
            ORDER BY 2""")
        for row in offenders:
            print(f"   {row['subject_id']} / {row['decision_type']} / "
                  f"{row['governance_basis']}: {row['n']} current")
        check("scopes carrying more than one current decision",
              len(offenders), 0)

        head("3. HISTORY IS PRESERVED, NOT DELETED")
        superseded = db.query("""
            SELECT decision_id, subject_id, outcome_code, reason_code,
                   matched_rule_id, input_digest, superseded_by, superseded_at,
                   decided_at
            FROM claris.decision WHERE state = 'superseded'
            ORDER BY decided_at""")
        print(f"   {len(superseded)} superseded decision(s) still queryable")
        check("every superseded decision kept its outcome",
              [d["decision_id"] for d in superseded if not d["outcome_code"]], [])
        check("every superseded decision kept its input digest",
              [d["decision_id"] for d in superseded
               if not d["input_digest"]], [])

        head("4. SUPERSESSION LINEAGE")
        check("every superseded decision names its successor",
              db.scalar("""
                  SELECT count(*) FROM claris.decision
                  WHERE state='superseded' AND superseded_by IS NULL"""), 0)
        check("every superseded decision records when",
              db.scalar("""
                  SELECT count(*) FROM claris.decision
                  WHERE state='superseded' AND superseded_at IS NULL"""), 0)
        check("no successor points backwards in time", db.scalar("""
            SELECT count(*) FROM claris.decision old
            JOIN claris.decision new ON new.decision_id = old.superseded_by
            WHERE new.decided_at < old.decided_at"""), 0)
        check("superseded_at equals the successor's decided_at", db.scalar("""
            SELECT count(*) FROM claris.decision old
            JOIN claris.decision new ON new.decision_id = old.superseded_by
            WHERE old.superseded_at IS DISTINCT FROM new.decided_at"""), 0)
        check("a successor never supersedes across governance scope",
              db.scalar("""
                  SELECT count(*) FROM claris.decision old
                  JOIN claris.decision new ON new.decision_id = old.superseded_by
                  WHERE new.governance_basis <> old.governance_basis
                     OR new.execution_mode  <> old.execution_mode
                     OR new.decision_type   <> old.decision_type
                     OR new.subject_id      <> old.subject_id"""), 0)
        check("no decision supersedes itself", db.scalar("""
            SELECT count(*) FROM claris.decision
            WHERE superseded_by = decision_id"""), 0)

        head("5. PRODUCTION ISOLATION")
        check("no production-governance decision exists at all", db.scalar("""
            SELECT count(*) FROM claris.decision
            WHERE governance_basis = 'AUTHORITATIVE'
               OR execution_mode = 'PRODUCTION'"""), 0)
        check("production still resolves to KB 1.1",
              db.scalar("SELECT kb_version FROM claris_kb.v_active_kb"), "1.1")

        head("6. CANONICAL LAYER UNCHANGED BY RE-EVALUATION")
        counts = {
            "product": db.scalar("SELECT count(*) FROM claris.product"),
            "configuration": db.scalar(
                "SELECT count(*) FROM claris.configuration"),
            "configuration_version": db.scalar(
                "SELECT count(*) FROM claris.configuration_version"),
        }
        print(f"   {counts}")
        check("one product", counts["product"], 1)
        check("four configurations", counts["configuration"], 4)
        check("four versions", counts["configuration_version"], 4)
        check("no duplicate canonical identity", db.scalar("""
            SELECT count(*) FROM (
              SELECT canonical_identity FROM claris.configuration
              GROUP BY 1 HAVING count(*) > 1) d"""), 0)
        check("every version still points at a real decision", db.scalar("""
            SELECT count(*) FROM claris.configuration_version v
            WHERE v.identity_assessment_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM claris.decision d
                              WHERE d.decision_id = v.identity_assessment_id)"""),
              0)

        head("7. A SUPERSEDED DECISION STILL EXPLAINS A CANONICAL OBJECT")
        rows = db.query("""
            SELECT v.version_id, v.identity_assessment_outcome,
                   d.outcome_code, d.state
            FROM claris.configuration_version v
            JOIN claris.decision d ON d.decision_id = v.identity_assessment_id
            ORDER BY v.version_id""")
        for row in rows:
            print(f"   {row['version_id']:<30}{row['outcome_code']:<22}"
                  f"decision state={row['state']}")
        check("every version's originating outcome still matches its decision",
              [r["version_id"] for r in rows
               if r["identity_assessment_outcome"] != r["outcome_code"]], [])

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        print("   CURRENT-DECISION SEMANTICS VERIFIED.")
        print("   One current decision per scope; history intact; lineage "
              "correct; canonical layer idempotent.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
