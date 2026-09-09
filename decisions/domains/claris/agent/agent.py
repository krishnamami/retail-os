"""The Claris coordination agent. One agent, no specialists.

POSITIONING -- WHAT THIS PLATFORM IS FOR
-----------------------------------------
Claris's existing tools and processes initiate launches and changes. Nothing
here creates one, and there is deliberately no "create launch" entry point.

This agent observes the evidence those systems leave behind, reconstructs the
business context, reads the governed decisions that were made about it, works
out where the change is waiting and on whom, and drafts the message that would
move it. It coordinates around decisions; it does not make them.

WHAT IT IS NOT ALLOWED TO CONCLUDE
-----------------------------------
CREATE_PRODUCT, CREATE_CONFIGURATION, NEW_VERSION, NO_BUSINESS_CHANGE,
USE_EXISTING, CANNOT_DECIDE, LAUNCH_READY -- none of these is ever produced
here. They come from governed decision services and this agent reads them. The
one thing it decides is what to recommend a human do next, from a closed
vocabulary of six actions, by rules written down in `coordination.py`.

There is no language model in this path. Every field is derived from a row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ..canonical import MATERIALIZING_OUTCOMES, MaterializationResult, \
    preview_projections
from ..identity import IDENTITY_PROPERTIES, SUBJECT_TYPE
from .case import CaseContext, CaseContextAssembler
from .communication import draft_for
from .coordination import Coordination, analyse, build_journey

__all__ = ["AgentResult", "ClarisCoordinationAgent"]


@dataclass(frozen=True)
class AgentResult:
    """The stable structure the Workbench consumes.

    No presentation in it: no HTML, no styling, no copy written for a specific
    screen. A field is a fact or a drafted message, and how it is shown is the
    UI's business.
    """

    case: Mapping[str, Any]
    status: Mapping[str, Any]
    summary: Mapping[str, Any]
    decisions: tuple
    evidence: tuple
    handoff_journey: tuple
    blockers: tuple
    recommended_actions: tuple
    communications: tuple
    projections: tuple
    governance: Mapping[str, Any]

    def as_dict(self) -> dict:
        return {
            "case": dict(self.case),
            "status": dict(self.status),
            "summary": dict(self.summary),
            "decisions": list(self.decisions),
            "evidence": list(self.evidence),
            "handoff_journey": list(self.handoff_journey),
            "blockers": list(self.blockers),
            "recommended_actions": list(self.recommended_actions),
            "communications": list(self.communications),
            "projections": list(self.projections),
            "governance": dict(self.governance),
        }


class ClarisCoordinationAgent:
    """Assemble, analyse, draft. Reads only."""

    __slots__ = ("_assembler", "_release", "_projection_rules")

    def __init__(self, db, release, projection_rules=()) -> None:
        self._assembler = CaseContextAssembler(db, release, IDENTITY_PROPERTIES)
        self._release = release
        self._projection_rules = tuple(projection_rules)

    # ------------------------------------------------------------------

    def subjects(self, subject_type: str = SUBJECT_TYPE) -> tuple:
        return self._assembler.subjects(subject_type)

    def run(self, subject_id: str,
            subject_type: str = SUBJECT_TYPE) -> AgentResult:
        case = self._assembler.assemble(subject_id, subject_type)
        coordination = analyse(case)
        journey = build_journey(case)
        projections = self._projections(case)
        drafts = draft_for(case, coordination)

        return AgentResult(
            case={
                "subject_id": case.subject_id,
                "subject_type": case.subject_type,
                "decision_horizon": case.decision_horizon,
                "fold_status": case.fold_status,
                "launch": case.launch,
                "identity_tuple": dict(case.identity_tuple),
                "identity_states": dict(case.identity_states),
                "canonical_identity": case.canonical_identity,
                "product": case.product,
                "configuration": case.configuration,
                "version": case.version,
            },
            status={
                "overall": coordination.overall_status,
                "blocked": coordination.blocked,
                "waiting_on": coordination.waiting_on,
                "waiting_on_role": coordination.current_owner_role,
                "waiting_on_actor": coordination.current_owner_actor,
                "owner_basis": coordination.owner_basis,
                "waiting_since": coordination.waiting_since,
                # No target date is emitted. Nothing in this corpus records a
                # launch target date, and a coordination tool that invents a
                # deadline is worse than one that has none.
                "target_date": None,
                "target_date_basis": "not recorded in any observed evidence",
            },
            summary={
                "headline": _headline(case, coordination),
                "explanation": coordination.explanation,
                "derivation": list(coordination.derivation),
            },
            decisions=tuple(_decision_view(d) for d in case.decisions),
            evidence=tuple(_evidence_view(e) for e in case.evidence),
            handoff_journey=tuple(entry.as_dict() for entry in journey),
            blockers=_blockers(case, coordination),
            recommended_actions=(
                {
                    "action": coordination.recommended_next_action,
                    "rationale": coordination.explanation,
                    "owner_role": coordination.current_owner_role,
                    "owner_actor": coordination.current_owner_actor,
                    "owner_basis": coordination.owner_basis,
                },
            ),
            communications=tuple(draft.as_dict() for draft in drafts),
            projections=projections,
            governance=dict(case.governance),
        )

    # ------------------------------------------------------------------

    def _projections(self, case: CaseContext) -> tuple:
        """Previews for the version this case created, recomputed from the
        active release's projection rules. Writes to no target system, ever."""
        if not case.version or not case.configuration:
            return ()
        outcome = case.version.get("identity_assessment_outcome")
        if outcome not in MATERIALIZING_OUTCOMES:
            return ()
        previews = preview_projections(
            MaterializationResult(
                subject_id=case.subject_id,
                outcome_code=outcome,
                configuration_id=case.configuration["configuration_id"],
                version_id=case.version["version_id"],
                canonical_identity=case.configuration.get("canonical_identity")),
            self._projection_rules)
        return tuple(preview.as_row() for preview in previews)


# ----------------------------------------------------------------------

def _headline(case, coordination) -> str:
    product = ((case.product or {}).get("product_name")
               or case.identity_tuple.get("product_reference")
               or case.subject_id)
    if coordination.blocked:
        return (f"{product}: {case.subject_id} is blocked — "
                f"{coordination.overall_status}")
    return (f"{product}: {case.subject_id} — {coordination.overall_status}")


def _decision_view(decision) -> dict:
    return {
        "decision_id": decision["decision_id"],
        "decision_type": decision["decision_type"],
        "outcome": decision["outcome_code"],
        "reason": decision["reason_code"],
        "matched_rule": decision["matched_rule_id"],
        "matched_rule_class": decision["matched_rule_class"],
        "confidence": decision["confidence_level"],
        "missing_evidence": list(decision["missing_evidence"] or ()),
        "blocking_evidence": list(decision["blocking_evidence"] or ()),
        "state": decision["state"],
        "superseded_by": decision["superseded_by"],
        "superseded_at": decision["superseded_at"],
        "decided_at": decision["decided_at"],
        "ontology_version": decision["ontology_version"],
        "governance_basis": decision["governance_basis"],
        "execution_mode": decision["execution_mode"],
        "input_digest": decision["input_digest"],
        "fold_state_id": decision["fold_state_id"],
    }


def _evidence_view(item) -> dict:
    return {
        "evidence_id": item["evidence_id"],
        "evidence_type": item["evidence_type"],
        "property_name": item["property_name"],
        "asserted_value": item["asserted_value"],
        "role": item["role"],
        "actor": item["actor"],
        "actor_is_simulated": item["actor"] is None,
        "source_system": item["source_system"],
        "occurred_at": item["occurred_at"],
        "contributed_to_fold": item["contributed_to_fold"],
        "simulator_classification": item["simulator_classification"],
    }


def _blockers(case, coordination) -> tuple:
    if not coordination.blocked:
        return ()
    blockers = []
    for name in coordination.missing_evidence:
        owner = next((row for row in case.dimension_governance
                      if row["dimension"] == name), {})
        blockers.append({
            "kind": "MISSING_IDENTITY_INPUT",
            "property": name,
            "fold_state": case.identity_states.get(name),
            "owner_role": owner.get("owner"),
            "owner_authority": owner.get("authority"),
            "owner_established": bool(owner.get("owner")),
            "governance_state": owner.get("governance_state"),
            "blocks_identity_assessment":
                owner.get("blocks_identity_assessment"),
            "explanation": coordination.owner_basis,
        })
    for decision_id in coordination.blocking_decisions:
        if not coordination.missing_evidence:
            blockers.append({
                "kind": "GOVERNANCE_AMBIGUITY",
                "decision_id": decision_id,
                "explanation": coordination.explanation,
            })
    if not blockers:
        blockers.append({
            "kind": "NO_GOVERNED_DECISION",
            "subject_id": case.subject_id,
            "explanation": coordination.explanation,
        })
    return tuple(blockers)
