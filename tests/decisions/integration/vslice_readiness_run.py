r"""Governed readiness across the live corpus. READ ONLY, zero mutations.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_readiness_run.py

Reads runtime.property_provenance_at at the D4I_004 horizon and evaluates the
three governed readiness decisions for every sku subject. No database write, no
model, no agent: an outcome here is a function of folded properties and the
declared policy, which is what makes it replayable.

Exit codes
    0  every expected invariant holds
    4  one does not
"""

from __future__ import annotations

import json
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
from decisions.domains.claris.readiness import (  # noqa: E402
    CANNOT_DECIDE, NOT_READY, READY, POLICY_VERSION, evaluate_all,
)

HORIZON = "2026-07-31 00:00:00+00"
OUT = os.path.join(_REPO_ROOT, "out")
FAILURES: list = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(label)


def load(db):
    rows = db.query("""
        SELECT subject_id, property_name, fold_state,
               resolved_value #>> '{}' AS value, value_provenance
        FROM   runtime.property_provenance_at(%s::timestamptz)
        WHERE  subject_type = 'sku'
        ORDER  BY subject_id, property_name""", (HORIZON,))
    by_subject: dict = {}
    for row in rows:
        by_subject.setdefault(row["subject_id"], {})[row["property_name"]] = {
            "fold_state": row["fold_state"],
            "value": row["value"],
            "provenance": row["value_provenance"],
        }
    return by_subject


def main() -> int:
    with read_only_connection() as db:
        subjects = load(db)
        head(f"GOVERNED READINESS  --  horizon {HORIZON}  --  {POLICY_VERSION}")
        print(f"   {len(subjects)} sku subjects\n")

        results = {sid: evaluate_all(sid, props)
                   for sid, props in sorted(subjects.items())}

        print(f"   {'subject':<10}{'TECHNICAL':<16}{'PRICING':<16}"
              f"{'LAUNCH':<16}why")
        print("   " + "-" * 92)
        for sid, three in results.items():
            launch = three["LAUNCH_READINESS"]
            print(f"   {sid:<10}"
                  f"{three['TECHNICAL_READINESS'].outcome:<16}"
                  f"{three['PRICING_READINESS'].outcome:<16}"
                  f"{launch.outcome:<16}"
                  f"{launch.why_not()[:70]}")

        def tally(kind):
            out = {}
            for three in results.values():
                out[three[kind].outcome] = out.get(three[kind].outcome, 0) + 1
            return out

        head("OUTCOME DISTRIBUTION")
        for kind in ("TECHNICAL_READINESS", "PRICING_READINESS",
                     "LAUNCH_READINESS"):
            print(f"   {kind:<22}{tally(kind)}")

        head("WHY TECHNICAL READINESS IS NOT A SINGLE ANSWER")
        buckets = {"observed failure": [], "manufactured evidence": [],
                   "no evidence": [], "ready": []}
        for sid, three in results.items():
            d = three["TECHNICAL_READINESS"]
            if d.outcome == READY:
                buckets["ready"].append(sid)
            elif d.failures:
                buckets["observed failure"].append(sid)
            elif d.insufficient_evidence:
                buckets["manufactured evidence"].append(sid)
            else:
                buckets["no evidence"].append(sid)
        for name, ids in buckets.items():
            print(f"   {name:<24}{len(ids):>2}  {', '.join(ids)}")

        print("\n   Every SKU above reads PASS or nothing in the raw corpus.")
        print("   Provenance is the only thing separating the middle two "
              "groups,")
        print("   and before D4I_003c they were indistinguishable.")

        head("INVARIANTS")
        check("sku subjects", len(results), 13)
        check("technically ready on observed evidence",
              sorted(buckets["ready"]), [])
        check("blocked by an observed rejection",
              sorted(buckets["observed failure"]), ["SKU-013"])
        check("undecidable because the PASS was manufactured",
              len(buckets["manufactured evidence"]), 8)
        check("pricing ready", tally("PRICING_READINESS").get(READY, 0), 8)
        check("launch ready", tally("LAUNCH_READINESS").get(READY, 0), 0)
        check("launch not ready",
              tally("LAUNCH_READINESS").get(NOT_READY, 0), 1)

        head("SCENARIO EVIDENCE")
        ready_priced = [s for s, t in results.items()
                        if t["PRICING_READINESS"].outcome == READY]
        print(f"   A  pricing READY on fully observed evidence: "
              f"{', '.join(ready_priced)}")
        print(f"   B  genuine blocker: SKU-013 -- "
              f"{results['SKU-013']['TECHNICAL_READINESS'].why_not()}")
        print(f"   E  insufficient information: SKU-006 -- "
              f"{results['SKU-006']['TECHNICAL_READINESS'].why_not()}")

        os.makedirs(OUT, exist_ok=True)
        payload = {
            "horizon": HORIZON,
            "policy_version": POLICY_VERSION,
            "subjects": {
                sid: {
                    kind: {
                        "outcome": d.outcome,
                        "why": d.why_not(),
                        "missing": list(d.missing_evidence),
                        "insufficient": list(d.insufficient_evidence),
                        "failed": list(d.failures),
                        "findings": [
                            {"property": f.property_name, "status": f.status,
                             "gating": f.gating, "value": f.value,
                             "provenance": f.provenance,
                             "fold_state": f.fold_state, "detail": f.detail}
                            for f in d.findings],
                    } for kind, d in three.items()
                } for sid, three in results.items()
            },
        }
        path = os.path.join(OUT, "readiness.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        print(f"\n   wrote {path}")

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        print("   GOVERNED READINESS EXECUTES.")
        print("   0 launch-ready, 1 not ready on observed evidence, "
              "12 undecidable --")
        print("   and the reasons are distinguishable, which is the point.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
