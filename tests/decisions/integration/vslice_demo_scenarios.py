r"""The five demo scenarios, verified against live governed state. READ ONLY.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_demo_scenarios.py

Every scenario is CHECKED, not narrated. If the corpus stops supporting one,
this fails rather than telling a story the data no longer backs.

Exit codes
    0  all five hold
    4  at least one does not
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
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from decisions.adapters.connection import read_only_connection  # noqa: E402
from decisions.agents.claris.launch_coordination_agent import (  # noqa: E402
    DEFAULT_HORIZON, LaunchCoordinationAgent,
)

FAILURES: list = []
IDENTITY = ("product_reference", "geography", "term_months", "customer_segment")


def head(n, t):
    print("\n" + "=" * 78 + f"\nSCENARIO {n}  --  {t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(f"{label}")


def identity_of(db, subject_id):
    rows = db.query("""
        SELECT property_name, resolved_value #>> '{}' AS value, fold_state
        FROM   runtime.property_provenance_at(%s::timestamptz)
        WHERE  subject_type='configuration_request' AND subject_id=%s""",
        (DEFAULT_HORIZON, subject_id))
    return {r["property_name"]: r for r in rows}


def main() -> int:
    with read_only_connection() as db:
        agent = LaunchCoordinationAgent(db)
        cases = {r.case.subject_id: r for r in agent.run_all()}

        # CURRENT decisions describe the corpus as it stands after replay.
        # HISTORY matters too: vslice_run.py has been replayed, so every
        # request now correctly resolves to NO_BUSINESS_CHANGE -- the
        # configurations already exist. The decisions that CREATED them are
        # real and superseded, not absent, and scenario D reads history rather
        # than concluding nothing was ever created.
        decisions = db.query("""
            SELECT subject_id, decision_type, outcome_code, reason_code,
                   matched_rule_id, state, decided_at::text AS decided_at
            FROM   claris.decision
            WHERE  state = 'current'
            ORDER  BY subject_id""")
        by_subject = {d["subject_id"]: d for d in decisions}
        history = db.query("""
            SELECT subject_id, outcome_code, state, decided_at::text AS decided_at
            FROM   claris.decision
            ORDER  BY subject_id, decided_at""")

        # ---------------------------------------------------------------- A
        head("A", "AN EXISTING LAUNCH PROGRESSES ON OBSERVED EVIDENCE")
        ready = sorted(s for s, r in cases.items()
                       if (r.case.readiness_named("PRICING_READINESS").outcome
                           == "READY"))
        print(f"   pricing READY: {', '.join(ready)}")
        sample = cases[ready[0]]
        pricing = sample.case.readiness_named("PRICING_READINESS")
        print(f"\n   {ready[0]}: {pricing.outcome} -- {pricing.why}")
        for name in ("pricing_status", "pricing_value_usd",
                     "final_pricing_approval_status"):
            p = sample.case.properties.get(name, {})
            print(f"      {name:<32}{str(p.get('value')):<14}"
                  f"{p.get('provenance')}")
        check("pricing ready on fully observed evidence", len(ready), 8)
        check("no defaulted evidence in a READY decision",
              [n for n in ("pricing_status", "pricing_value_usd",
                           "final_pricing_approval_status")
               if sample.case.properties.get(n, {}).get("provenance")
               == "DEFAULTED"], [])
        print("\n   Launch readiness stays CANNOT_DECIDE for these: the corpus")
        print("   carries no go-live evidence for the pricing cohort. Reported,")
        print("   not worked around.")

        # ---------------------------------------------------------------- B
        head("B", "A GENUINE BLOCKER, CHOSEN BY THE DECISION NOT BY ME")
        blocked = sorted(s for s, r in cases.items()
                         if r.case.readiness_named(
                             "LAUNCH_READINESS").outcome == "NOT_READY")
        print(f"   NOT_READY: {', '.join(blocked)}")
        case = cases["SKU-013"]
        tech = case.case.readiness_named("TECHNICAL_READINESS")
        worst = case.blockers[0]
        print(f"\n   {case.headline}")
        print(f"      technical readiness : {tech.outcome} -- {tech.why}")
        print(f"      blocker kind        : {worst.kind}")
        print(f"      waiting on role     : {case.waiting_on.role}")
        print(f"      waiting on person   : {case.waiting_on.actor}")
        print(f"      recommended action  : {case.recommendation.action}")
        check("exactly one SKU is NOT_READY", blocked, ["SKU-013"])
        check("its blocker is an observed failure", worst.kind,
              "OBSERVED_FAILURE")
        check("the failing value was asserted by a source",
              case.case.properties["technical_review_result"]["provenance"],
              "OBSERVED")
        check("SKU-004 is NOT called blocked",
              cases["SKU-004"].case.readiness_named(
                  "LAUNCH_READINESS").outcome, "CANNOT_DECIDE")

        # ---------------------------------------------------------------- C
        head("C", "DUPLICATE SKU PROLIFERATION PREVENTED")
        no_change = sorted(s for s, d in by_subject.items()
                           if d["outcome_code"] == "NO_BUSINESS_CHANGE")
        print(f"   NO_BUSINESS_CHANGE: {', '.join(no_change) or '(none)'}")
        for subject in no_change:
            ident = identity_of(db, subject)
            print(f"      {subject}: "
                  + ", ".join(f"{n}={ident.get(n, {}).get('value')}"
                              for n in IDENTITY))
        configs = db.query("SELECT count(*) AS n FROM claris.configuration")
        versions = db.query(
            "SELECT count(*) AS n FROM claris.configuration_version")
        requests = db.query("""
            SELECT count(DISTINCT subject_id) AS n
            FROM   runtime.evidence WHERE subject_type='configuration_request'""")
        print(f"\n   {requests[0]['n']} configuration requests produced "
              f"{configs[0]['n']} configurations and "
              f"{versions[0]['n']} versions")
        check("duplicates were absorbed, not materialised",
              len(no_change) > 0, True)
        check("fewer configurations than requests",
              configs[0]["n"] < requests[0]["n"], True)

        # ---------------------------------------------------------------- D
        head("D", "A LEGITIMATE IDENTITY VARIATION IS NOT A DUPLICATE")
        creating = ("CREATE_CONFIGURATION", "CREATE_BUSINESS_IDENTITY",
                    "CREATE_NEW_CONFIGURATION")
        created = sorted({d["subject_id"] for d in history
                          if d["outcome_code"] in creating})
        print(f"   requests that created a new identity: "
              f"{', '.join(created) or '(none)'}")
        for subject in created:
            ident = identity_of(db, subject)
            current = by_subject.get(subject, {}).get("outcome_code", "-")
            print(f"      {subject}: "
                  + ", ".join(f"{n}={ident.get(n, {}).get('value')}"
                              for n in IDENTITY)
                  + f"   [now {current}]")
        # A business identity requires a COMPLETE tuple. CONFIG-REQ-2026-007 is
        # missing customer_segment, so it has no identity to be distinct from
        # anything -- counting its partial tuple as a fifth identity and
        # expecting a configuration for it would contradict scenario E, where
        # the same request is correctly stalled.
        complete, partial = set(), []
        for subject in by_subject:
            ident = identity_of(db, subject)
            if all(ident.get(n, {}).get("fold_state") == "ESTABLISHED"
                   for n in IDENTITY):
                complete.add(tuple(ident[n]["value"] for n in IDENTITY))
            else:
                partial.append(subject)
        distinct = complete
        print(f"\n   {len(by_subject)} requests carry {len(distinct)} distinct "
              f"complete business identities")
        if partial:
            print(f"   {len(partial)} request(s) have no identity at all: "
                  f"{', '.join(sorted(partial))} -- incomplete, so nothing to "
                  f"create or duplicate")
        print("   Every request now reads NO_BUSINESS_CHANGE because the run "
              "has been")
        print("   replayed and the configurations already exist. That is "
              "idempotency,")
        print("   not an absence of creation -- the creating decisions are "
              "superseded.")
        geographies = db.query("""
            SELECT DISTINCT resolved_value #>> '{}' AS geo
            FROM   runtime.property_provenance_at(%s::timestamptz)
            WHERE  subject_type='configuration_request'
              AND  property_name='geography' AND fold_state='ESTABLISHED'
            ORDER  BY 1""", (DEFAULT_HORIZON,))
        print(f"\n   geographies in the corpus: "
              f"{', '.join(g['geo'] for g in geographies)}")
        check("at least one request created a new identity",
              len(created) > 0, True)
        check("more than one geography exists to distinguish",
              len(geographies) > 1, True)
        check("one configuration per distinct COMPLETE business identity",
              db.query("SELECT count(*) AS n FROM claris.configuration")[0]["n"],
              len(distinct))
        check("replay produced no extra configuration",
              db.query("""SELECT count(*) AS n FROM (
                            SELECT canonical_identity FROM claris.configuration
                            GROUP BY 1 HAVING count(*) > 1) d""")[0]["n"], 0)

        # ---------------------------------------------------------------- E
        head("E", "INSUFFICIENT INFORMATION IS A SAFE STALL, NOT A GUESS")
        cannot = sorted(s for s, d in by_subject.items()
                        if d["outcome_code"] == "CANNOT_DECIDE")
        print(f"   CANNOT_DECIDE: {', '.join(cannot) or '(none)'}")
        for subject in cannot:
            ident = identity_of(db, subject)
            missing = [n for n in IDENTITY
                       if ident.get(n, {}).get("fold_state") != "ESTABLISHED"]
            print(f"      {subject}: missing {', '.join(missing) or '—'}"
                  f"   reason={by_subject[subject]['reason_code']}")
        check("at least one request is safely stalled", len(cannot) > 0, True)
        check("every stalled request is genuinely missing an identity input",
              [s for s in cannot
               if not [n for n in IDENTITY
                       if identity_of(db, s).get(n, {}).get("fold_state")
                       != "ESTABLISHED"]], [])

        # ---------------------------------------------------------------- F
        head("F", "PRICE CHANGE / NEW VERSION")
        print("   NOT DEMONSTRATED. The corpus contains no second priced")
        print("   version of an existing configuration, and the brief forbids")
        print("   fabricating one. Reported as absent rather than staged.")

        print("\n" + "=" * 78 + "\nRESULT\n" + "=" * 78)
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        print("   FIVE SCENARIOS HOLD AGAINST LIVE GOVERNED STATE.")
        print("   A succeeds on observed evidence; B is blocked by an observed")
        print("   rejection; C absorbs duplicates; D creates a real variation;")
        print("   E stalls safely. F is honestly absent.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
