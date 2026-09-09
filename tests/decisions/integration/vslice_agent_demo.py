r"""CLARIS COORDINATION AGENT -- demo over the existing vertical-slice cases.

Runs the agent against every configuration request the Fold holds, prints the
four demo scenarios in the shape a Workbench would show them, and writes a
reproducible artifact derived entirely from persisted state.

READ ONLY by default. With --persist it additionally records the drafted
communications in claris.communication -- still drafts, still unsent, and
guarded so re-running inserts nothing twice.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_agent_demo.py
    .\venv\Scripts\python.exe tests\decisions\integration\vslice_agent_demo.py --persist

--persist requires RETAIL_OS_DEPLOY_CONFIRM=VSLICE.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone

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

from decisions.adapters.artifact_kb import ArtifactGovernanceResolver  # noqa: E402
from decisions.adapters.connection import (  # noqa: E402
    deploy_connection, read_only_connection)
from decisions.governance_resolver import ExecutionMode  # noqa: E402
from decisions.domains.claris.agent import ClarisCoordinationAgent  # noqa: E402
from decisions.domains.claris.identity import SUBJECT_TYPE  # noqa: E402

#: The four scenarios the brief asks to be exercised, and the subject in this
#: corpus that carries each. Mapped, not invented: each is a real request.
DEMO_CASES = {
    "CONFIG-REQ-2026-001": "A. NEW PRODUCT",
    "CONFIG-REQ-2026-002": "B. NEW GEOGRAPHY",
    "CONFIG-REQ-2026-006": "C. DUPLICATE REQUEST",
    "CONFIG-REQ-2026-007": "D. MISSING CUSTOMER SEGMENT",
}


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def render(title, result) -> None:
    """One case in the shape the Workbench will show it."""
    data = result.as_dict()
    case, status = data["case"], data["status"]
    print("\n" + "-" * 78)
    print(f"{title}   {case['subject_id']}")
    print("-" * 78)

    print("\nEXISTING LAUNCH / CHANGE")
    launch = case.get("launch") or {}
    print(f"   launch            {launch.get('launch_id')}  "
          f"intent={launch.get('intent_classification')}")
    print(f"   raised by role    {launch.get('requested_by_role')}")
    print(f"   raised by actor   {launch.get('requested_by_actor')}"
          f"   (raw: {launch.get('requested_by_actor_raw')})")
    print("   identity requested")
    for name, value in case["identity_tuple"].items():
        print(f"      {name:<20} {value!r:<16} "
              f"[{case['identity_states'].get(name)}]")

    print("\nEVIDENCE")
    for item in data["evidence"]:
        print(f"   {item['property_name']:<22} {str(item['asserted_value'])[:24]:<26}"
              f"role={item['role']}  used_by_fold={item['contributed_to_fold']}")

    print("\nCANONICAL CONTEXT")
    print(f"   product           {(case.get('product') or {}).get('product_id')}"
          f"  {(case.get('product') or {}).get('product_name')}")
    configuration = case.get("configuration") or {}
    print(f"   configuration     {configuration.get('configuration_id')}")
    print(f"   canonical identity{'':<1} {configuration.get('canonical_identity')}")
    print(f"   version           {(case.get('version') or {}).get('version_id')}")

    print("\nGOVERNED DECISION")
    for decision in data["decisions"]:
        print(f"   [{decision['state']:<10}] {decision['outcome']:<22}"
              f"{decision['matched_rule'] or '-':<14}"
              f"reason={decision['reason']}")

    print("\nWHY")
    print(f"   {data['summary']['headline']}")
    for line in _wrap(data["summary"]["explanation"]):
        print(f"   {line}")
    print("   derivation:")
    for step in data["summary"]["derivation"]:
        print(f"      - {step}")

    print("\nCURRENT OWNER / BLOCKER")
    print(f"   status            {status['overall']}   blocked={status['blocked']}")
    print(f"   waiting on        {status['waiting_on']}")
    print(f"   owner role        {status['waiting_on_role']}")
    print(f"   owner actor       {status['waiting_on_actor']}")
    for line in _wrap(f"owner basis: {status['owner_basis']}"):
        print(f"   {line}")
    for blocker in data["blockers"]:
        print(f"   blocker           {blocker['kind']}"
              f"  {blocker.get('property') or blocker.get('decision_id') or ''}")

    print("\nRECOMMENDED ACTION")
    for action in data["recommended_actions"]:
        print(f"   {action['action']}")

    print("\nCOMMUNICATION DRAFT")
    for draft in data["communications"]:
        print(f"   id        {draft['communication_id']}")
        print(f"   channel   {draft['channel']}   type={draft['communication_type']}")
        print(f"   to        role={draft['to_role']}  actor={draft['to_actor']}")
        print(f"   status    {draft['status']}  (nothing has been sent)")
        print(f"   subject   {draft['subject']}")
        for line in draft["body"].splitlines():
            print(f"   | {line}")

    if data["projections"]:
        print("\nPROJECTION PREVIEW")
        for projection in data["projections"]:
            print(f"   {projection['target_system']:<12}"
                  f"{projection['projection_action']:<8}"
                  f"{projection['projection_reason']:<28}"
                  f"new_key={projection['requires_new_target_identity']}"
                  f"  proliferation={projection['counts_as_proliferation']}")
    else:
        print("\nPROJECTION PREVIEW")
        print("   none required")

    print("\nHANDOFF JOURNEY")
    for entry in data["handoff_journey"]:
        print(f"   {str(entry['occurred_at'])[:19]:<20}{str(entry['role']):<24}"
              f"{entry['status']:<12}{entry['event']}")


def _wrap(text, width=72):
    words, line, out = str(text).split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def main(persist: bool) -> int:
    with read_only_connection() as db:
        resolver = ArtifactGovernanceResolver(db, ExecutionMode.PROTOTYPE)
        release = resolver.release
        agent = ClarisCoordinationAgent(db, release, resolver.projection_rules())

        head("CLARIS COORDINATION AGENT")
        print(f"   governance   {release.ontology_version} "
              f"({release.governance_basis}, {release.validation_status})")
        print(f"   digest       {release.content_digest[:16]}...")
        print("   the agent reads governed state. It executes no decision, "
              "concludes no outcome,")
        print("   and sends no message.")

        subjects = agent.subjects(SUBJECT_TYPE)
        head(f"RUNNING OVER {len(subjects)} CONFIGURATION REQUEST(S)")
        results = {}
        for subject_id in subjects:
            result = agent.run(subject_id, SUBJECT_TYPE)
            results[subject_id] = result
            status = result.status
            print(f"   {subject_id:<24}{status['overall']:<34}"
                  f"blocked={status['blocked']}  "
                  f"-> {result.recommended_actions[0]['action']}")

        head("DEMO SCENARIOS")
        for subject_id, title in DEMO_CASES.items():
            if subject_id in results:
                render(title, results[subject_id])
            else:
                print(f"\n{title}: {subject_id} is not in the corpus")

        # ------------------------------------------------------------------
        out_dir = os.path.join(_REPO_ROOT, "out")
        os.makedirs(out_dir, exist_ok=True)
        artifact = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "derived from persisted governed state; regenerating "
                      "this file reproduces it",
            "governance": {
                "ontology_version": release.ontology_version,
                "kb_version": release.kb_version,
                "release_class": release.release_class,
                "governance_basis": release.governance_basis,
                "validation_status": release.validation_status,
                "content_digest": release.content_digest,
                "warning": "PROTOTYPE ASSUMPTION. NOT CLARIS APPROVED. Every "
                           "governed value behind these cases is an engineering "
                           "assumption awaiting validation with Claris.",
            },
            "agent": {
                "kind": "coordination",
                "concludes_governed_outcomes": False,
                "sends_communications": False,
                "uses_language_model": False,
                "status_vocabulary_is_closed": True,
            },
            "demo_cases": {subject_id: title
                           for subject_id, title in DEMO_CASES.items()
                           if subject_id in results},
            "cases": {subject_id: result.as_dict()
                      for subject_id, result in results.items()},
        }
        path = os.path.join(out_dir, "claris_agent_demo.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=2, default=str)
        head("ARTIFACT")
        print(f"   {path}")

        drafts = [draft for result in results.values()
                  for draft in result.communications]
        print(f"   {len(results)} case(s), {len(drafts)} communication draft(s), "
              "0 sent")

    if persist:
        head("PERSIST DRAFTS (still drafts, still unsent)")
        written = _persist(results, release)
        print(f"   {written} communication row(s) written")

    head("AGENT RUN COMPLETE -- NO DECISION EXECUTED, NO MESSAGE SENT")
    return 0


def _persist(results, release) -> int:
    """Record the drafts in claris.communication. Guarded and idempotent."""
    written = 0
    with deploy_connection() as db:
        for result in results.values():
            for draft in result.communications:
                db.execute("""
                    INSERT INTO claris.communication (
                        communication_id, subject_id, launch_id,
                        from_actor_id, from_role, to_actor_id, to_role,
                        channel, communication_type, related_decision_id,
                        subject, body, status, governance_basis,
                        ontology_version)
                    SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s::uuid,%s,%s,'DRAFT',%s,%s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM claris.communication
                        WHERE communication_id = %s)""",
                    (draft["communication_id"], draft["subject_id"],
                     draft["launch_id"], draft["from_actor"], draft["from_role"],
                     draft["to_actor"], draft["to_role"], draft["channel"],
                     draft["communication_type"], draft["related_decision_id"],
                     draft["subject"], draft["body"],
                     release.governance_basis, release.ontology_version,
                     draft["communication_id"]))
                written += 1
        rows = db.query("""
            SELECT communication_id, subject_id, to_role, channel,
                   communication_type, status
            FROM claris.communication ORDER BY created_at, communication_id""")
        for row in rows:
            print(f"   {row['communication_id']}  {row['subject_id']:<24}"
                  f"to_role={row['to_role']}  {row['channel']:<16}"
                  f"{row['communication_type']:<28}{row['status']}")
        sent = db.scalar("""
            SELECT count(*) FROM claris.communication
            WHERE status NOT IN ('DRAFT','SUPERSEDED')""")
        print(f"   rows claiming to have been sent: {sent}")
        db.commit()
    return written


if __name__ == "__main__":
    try:
        sys.exit(main("--persist" in sys.argv))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
