r"""Gathers everything the Workbench shows, from governed state only.

    .\venv\Scripts\python.exe workbench\collect.py

Writes out\workbench_data.json. Read-only: no INSERT, UPDATE or DELETE, and no
source system is contacted.

WHAT IT REFUSES TO DO
    It does not link a SKU to a launch. SKU_MINTED carries launch_id in the RAW
    event, but no governed property records it, so the Workbench shows the
    linkage as absent rather than reaching into raw to manufacture one. Every
    other column here traces to a folded property or a governed decision.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from decisions.adapters.connection import read_only_connection  # noqa: E402
from decisions.agents.claris.launch_coordination_agent import (  # noqa: E402
    DEFAULT_HORIZON, LaunchCoordinationAgent,
)

OUT = os.path.join(_ROOT, "out")

PROPERTIES_SQL = """
SELECT subject_type, subject_id, property_name, fold_state,
       resolved_value #>> '{}' AS value, value_provenance,
       basis_count, defaulted_count, effective_at, latest_known_arrival_at
FROM   runtime.property_provenance_at(%s::timestamptz)
ORDER  BY subject_type, subject_id, property_name
"""

DECISIONS_SQL = """
SELECT d.decision_id::text, d.decision_type, d.subject_type, d.subject_id,
       d.outcome_code, d.reason_code, d.matched_rule_id, d.state,
       d.governance_basis, d.execution_mode, d.kb_version, d.policy_version,
       d.decided_at::text, d.superseded_by::text, d.input_digest
FROM   claris.decision d
ORDER  BY d.subject_id, d.decided_at
"""

CONFIGURATIONS_SQL = """
SELECT c.configuration_id, c.product_id, c.canonical_identity, c.status,
       c.created_at::text,
       (SELECT count(*) FROM claris.configuration_version v
        WHERE v.configuration_id = c.configuration_id) AS versions
FROM   claris.configuration c
ORDER  BY c.configuration_id
"""

EVIDENCE_SQL = """
SELECT e.subject_type, e.subject_id, e.mapping_id, e.property_name,
       e.asserted_value, e.value_provenance, e.source_system,
       e.source_actor_id, e.source_actor_role,
       e.occurred_at::text, e.arrival_at::text,
       e.evidence_lineage->>'event_type' AS event_type,
       e.evidence_lineage->>'source_path' AS source_path
FROM   runtime.evidence e
ORDER  BY e.arrival_at, e.subject_id, e.mapping_id
"""


def group_properties(rows):
    out: dict = {}
    for row in rows:
        out.setdefault(row["subject_type"], {}) \
           .setdefault(row["subject_id"], {})[row["property_name"]] = {
               "fold_state": row["fold_state"],
               "value": row["value"],
               "provenance": row["value_provenance"],
               "basis_count": row["basis_count"],
               "defaulted_count": row["defaulted_count"],
               "effective_at": row["effective_at"],
               "arrival_at": row["latest_known_arrival_at"],
           }
    return out


def main() -> int:
    with read_only_connection() as db:
        print("reading governed state ...")
        properties = group_properties(db.query(PROPERTIES_SQL,
                                               (DEFAULT_HORIZON,)))
        decisions = db.query(DECISIONS_SQL)
        configurations = db.query(CONFIGURATIONS_SQL)
        evidence = db.query(EVIDENCE_SQL)

        print("running the launch coordination agent ...")
        agent = LaunchCoordinationAgent(db)
        cases = [r.as_dict() for r in agent.run_all()]

        totals = {
            "evidence": len(evidence),
            "observed": sum(1 for e in evidence
                            if e["value_provenance"] == "OBSERVED"),
            "defaulted": sum(1 for e in evidence
                             if e["value_provenance"] == "DEFAULTED"),
            "mappings": len({e["mapping_id"] for e in evidence}),
            "subjects": sum(len(v) for v in properties.values()),
            "property_states": sum(len(p) for v in properties.values()
                                   for p in v.values()),
        }

        payload = {
            "horizon": DEFAULT_HORIZON,
            "generated_from": "governed state only",
            "totals": totals,
            "cases": cases,
            "properties": properties,
            "decisions": decisions,
            "configurations": configurations,
            "evidence": evidence,
        }

        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "workbench_data.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1, sort_keys=True, default=str)
        print(f"wrote {path}")
        print(f"  {totals['evidence']} evidence rows "
              f"({totals['observed']} observed / {totals['defaulted']} "
              f"defaulted) across {totals['mappings']} mappings")
        print(f"  {totals['subjects']} subjects, "
              f"{totals['property_states']} property states")
        print(f"  {len(cases)} launch cases, {len(decisions)} governed "
              f"decisions, {len(configurations)} configurations")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
