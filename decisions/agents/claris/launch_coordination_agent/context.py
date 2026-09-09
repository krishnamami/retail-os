"""Loads the governed state a launch case rests on. Reads only.

Everything here comes from runtime.property_provenance_at and the readiness
evaluator. No raw events, no source systems, no interpretation: if a fact is
not in governed state, this module does not know it, which is the intended
limitation rather than a gap to be filled in later.
"""

from __future__ import annotations

from typing import Optional

from decisions.domains.claris.agent.case import is_simulated_actor
from decisions.domains.claris.readiness import evaluate_all

from .models import LaunchCase, ReadinessView

__all__ = ["DEFAULT_HORIZON", "ACTOR_PROPERTIES", "LaunchContextLoader"]

#: Properties whose VALUE is an actor identifier rather than a business fact.
#: Every one of them reads SIMULATED/... in this corpus. They are real observed
#: evidence and are reported as such -- but they are flagged, because showing
#: "approved by SIMULATED/exec" as though a person approved something is the
#: kind of quiet fiction this prototype exists to eliminate. The flag lets the
#: Workbench render them as simulation artefacts and lets the agent refuse to
#: treat them as owners.
ACTOR_PROPERTIES = frozenset({
    "pricing_published_by", "go_live_requested_by", "go_live_approved_by",
    "supply_chain_notified_by", "material_activated_by", "sap_con_test_actor",
    "sap_prd_promotion_actor", "sap_con_load_actor",
    "hierarchy_approval_authority",
})

#: The horizon D4I_004 folded at: after the latest assertion arrival
#: (2026-07-16), so the snapshot sees every fact the corpus contains.
DEFAULT_HORIZON = "2026-07-31 00:00:00+00"

_PROPERTY_SQL = """
SELECT subject_id,
       property_name,
       fold_state,
       resolved_value #>> '{}' AS value,
       value_provenance,
       basis_count,
       defaulted_count,
       effective_at,
       latest_known_arrival_at
FROM   runtime.property_provenance_at(%s::timestamptz)
WHERE  subject_type = %s
ORDER  BY subject_id, property_name
"""


class LaunchContextLoader:
    def __init__(self, db, horizon: str = DEFAULT_HORIZON,
                 subject_type: str = "sku") -> None:
        self._db = db
        self._horizon = horizon
        self._subject_type = subject_type

    def subjects(self) -> tuple:
        rows = self._db.query(
            """SELECT DISTINCT subject_id
               FROM   runtime.property_provenance_at(%s::timestamptz)
               WHERE  subject_type = %s
               ORDER  BY subject_id""",
            (self._horizon, self._subject_type))
        return tuple(row["subject_id"] for row in rows)

    def _properties(self) -> dict:
        rows = self._db.query(_PROPERTY_SQL,
                              (self._horizon, self._subject_type))
        out: dict = {}
        for row in rows:
            simulated = (row["property_name"] in ACTOR_PROPERTIES
                         and row["value"] is not None
                         and is_simulated_actor(row["value"]))
            out.setdefault(row["subject_id"], {})[row["property_name"]] = {
                "fold_state": row["fold_state"],
                "value": row["value"],
                "provenance": row["value_provenance"],
                "basis_count": row["basis_count"],
                "defaulted_count": row["defaulted_count"],
                "is_actor_reference": row["property_name"] in ACTOR_PROPERTIES,
                "simulated_actor": simulated,
                "effective_at": row["effective_at"],
                "arrival_at": row["latest_known_arrival_at"],
            }
        return out

    def load(self, subject_id: str) -> Optional[LaunchCase]:
        properties = self._properties().get(subject_id)
        if properties is None:
            return None
        return self._build(subject_id, properties)

    def load_all(self) -> tuple:
        return tuple(self._build(subject_id, props)
                     for subject_id, props in sorted(self._properties().items()))

    def _build(self, subject_id: str, properties: dict) -> LaunchCase:
        decisions = evaluate_all(subject_id, properties)
        readiness = tuple(
            ReadinessView(
                decision_type=kind,
                outcome=decision.outcome,
                why=decision.why_not(),
                intent=decision.intent,
                policy_version=decision.policy_version,
                missing_evidence=decision.missing_evidence,
                insufficient_evidence=decision.insufficient_evidence,
                failed=decision.failures,
            )
            for kind, decision in decisions.items())

        established = sum(1 for p in properties.values()
                          if p["fold_state"] == "ESTABLISHED")
        defaulted = sum(1 for p in properties.values()
                        if p.get("provenance") == "DEFAULTED")
        unreported = sum(1 for p in properties.values()
                         if p["fold_state"] != "ESTABLISHED")

        return LaunchCase(
            subject_type=self._subject_type,
            subject_id=subject_id,
            decision_horizon=self._horizon,
            readiness=readiness,
            properties=properties,
            established=established,
            defaulted=defaulted,
            unreported=unreported,
        )

    def decisions_for(self, subject_id: str, properties: dict) -> dict:
        """The governed decisions themselves, for callers that need findings."""
        return evaluate_all(subject_id, properties)
