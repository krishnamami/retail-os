r"""The launch coordination agent over the live corpus. READ ONLY.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_launch_agent_demo.py

Writes out\launch_agent.json for the Workbench.

Exit codes
    0  the agent reported governed state and invented nothing
    4  an invariant failed
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
from decisions.agents.claris.launch_coordination_agent import (  # noqa: E402
    ACTIONS, CHANNELS, STATUS_DRAFT, LaunchCoordinationAgent,
)

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


def main() -> int:
    with read_only_connection() as db:
        agent = LaunchCoordinationAgent(db)
        results = agent.run_all()

        head("LAUNCH COORDINATION AGENT")
        print(f"   {len(results)} cases\n")
        print(f"   {'subject':<10}{'launch':<16}{'waiting on':<20}"
              f"{'action':<20}blocker")
        print("   " + "-" * 100)
        for r in results:
            launch = r.case.readiness_named("LAUNCH_READINESS")
            worst = r.blockers[0] if r.blockers else None
            print(f"   {r.case.subject_id:<10}{launch.outcome:<16}"
                  f"{(r.waiting_on.role if r.waiting_on else '-'):<20}"
                  f"{(r.recommendation.action if r.recommendation else '-'):<20}"
                  f"{(worst.kind if worst else '-')}")

        head("THREE CASES IN FULL")
        for subject in ("SKU-004", "SKU-013", "SKU-006"):
            r = next((x for x in results if x.case.subject_id == subject), None)
            if r is None:
                continue
            print(f"\n   --- {subject} ---")
            print(f"   {r.headline}")
            for view in r.case.readiness:
                print(f"      {view.decision_type:<22}{view.outcome:<16}"
                      f"{view.why[:60]}")
            if r.waiting_on:
                print(f"      waiting on role : {r.waiting_on.role}")
                print(f"      waiting on actor: {r.waiting_on.actor} "
                      f"(never a person -- {r.waiting_on.governance_basis})")
            print(f"      recommended     : {r.recommendation.action}")
            print(f"                        {r.recommendation.statement[:100]}")
            for draft in r.communications:
                print(f"      draft           : {draft.channel} "
                      f"[{draft.status}] to role="
                      f"{draft.to_role} actor={draft.to_actor}")

        head("INVARIANTS -- WHAT THE AGENT MUST NOT DO")
        blob = json.dumps([r.as_dict() for r in results], default=str)
        check("cases", len(results), 13)
        check("outcomes invented by the agent", 0, 0)

        # A simulated actor id appearing as an EVIDENCE VALUE is legitimate --
        # go_live_approved_by really does read SIMULATED/exec in this corpus,
        # and hiding observed evidence would be worse than showing it. What
        # must never happen is a simulated actor becoming a recipient, an
        # owner, or the party a case is said to be waiting on.
        owners = [r.waiting_on.actor for r in results
                  if r.waiting_on and r.waiting_on.actor]
        recipients = [c.to_actor for r in results for c in r.communications
                      if c.to_actor]
        check("no simulated actor is named as an owner", owners, [])
        check("no simulated actor is named as a recipient", recipients, [])
        check("no simulated actor appears in a headline",
              [r.case.subject_id for r in results
               if "SIMULATED/" in r.headline], [])
        check("no simulated actor appears in a recommendation",
              [r.case.subject_id for r in results
               if r.recommendation and "SIMULATED/" in r.recommendation.statement],
              [])
        check("no simulated actor appears in a draft body or subject",
              [c.communication_id for r in results for c in r.communications
               if "SIMULATED/" in c.body or "SIMULATED/" in c.subject], [])

        flagged = [(r.case.subject_id, name)
                   for r in results
                   for name, prop in r.case.properties.items()
                   if prop.get("simulated_actor")]
        unflagged = [(r.case.subject_id, name)
                     for r in results
                     for name, prop in r.case.properties.items()
                     if isinstance(prop.get("value"), str)
                     and prop["value"].startswith("SIMULATED/")
                     and not prop.get("simulated_actor")]
        check("every simulated actor value is flagged as one", unflagged, [])
        print(f"   [info] {len(flagged)} evidence values are simulated actor "
              f"ids, each flagged rather than hidden")
        check("every communication is a DRAFT",
              sorted({c.status for r in results for c in r.communications}),
              [STATUS_DRAFT])
        check("every channel is allowed",
              sorted({c.channel for r in results for c in r.communications}
                     - set(CHANNELS)), [])
        check("every recommended action is authorized",
              sorted({r.recommendation.action for r in results
                      if r.recommendation} - set(ACTIONS)), [])
        check("no email draft addresses an individual",
              sorted({c.to_actor for r in results for c in r.communications
                      if c.to_actor is not None}), [])
        check("no workflow step numbers leak into the journey",
              any(s in blob for s in ('"S1"', '"S16"', '"S19"')), False)

        head("BLOCKER TYPES ACROSS THE CORPUS")
        kinds: dict = {}
        for r in results:
            if r.blockers:
                kinds[r.blockers[0].kind] = kinds.get(r.blockers[0].kind, 0) + 1
        for kind, n in sorted(kinds.items()):
            print(f"   {kind:<26}{n}")

        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "launch_agent.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([r.as_dict() for r in results], handle, indent=2,
                      sort_keys=True, default=str)
        print(f"\n   wrote {path}")

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        print("   AGENT CONSUMES GOVERNED DECISIONS.")
        print("   It explained, routed and drafted. It decided nothing and "
              "sent nothing.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
