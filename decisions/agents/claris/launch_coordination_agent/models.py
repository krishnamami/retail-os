"""Shapes the launch coordination agent produces. No logic lives here.

Every field is either copied from a governed decision or derived from one by a
rule declared in reasoning.py. Nothing in this module can originate a business
fact, which is the property that keeps the agent an observer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = [
    "ReadinessView", "Blocker", "WaitingOn", "Recommendation",
    "LaunchCase", "AgentResult",
]


@dataclass(frozen=True)
class ReadinessView:
    """A governed readiness decision, as the agent reports it. Read-only."""

    decision_type: str
    outcome: str
    why: str
    intent: str
    policy_version: str
    missing_evidence: tuple = field(default_factory=tuple)
    insufficient_evidence: tuple = field(default_factory=tuple)
    failed: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "decision_type": self.decision_type,
            "outcome": self.outcome,
            "why": self.why,
            "intent": self.intent,
            "policy_version": self.policy_version,
            "missing_evidence": list(self.missing_evidence),
            "insufficient_evidence": list(self.insufficient_evidence),
            "failed": list(self.failed),
        }


@dataclass(frozen=True)
class Blocker:
    """One reason a subject is not ready, traced to the decision that said so.

    kind is the governed distinction, not a severity:
        OBSERVED_FAILURE        a source asserted a failing value
        MANUFACTURED_EVIDENCE   a value exists but no source asserted it
        ABSENT_EVIDENCE         nothing has been reported
        CONTRADICTED_EVIDENCE   sources disagree
        SUBORDINATE             a composed readiness decision is not READY
    """

    kind: str
    decision_type: str
    property_name: Optional[str]
    statement: str
    evidence_value: Any = None
    provenance: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "decision_type": self.decision_type,
            "property_name": self.property_name,
            "statement": self.statement,
            "evidence_value": self.evidence_value,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class WaitingOn:
    """Who the case is waiting on.

    role is routed from the blocking property by a declared table. actor is
    almost always None and that is deliberate: the corpus carries only
    simulated actor ids, and naming a person the evidence does not identify
    would be the agent inventing a fact. Q-002 (decision ownership) is open and
    is cited rather than answered.
    """

    role: Optional[str]
    actor: Optional[str] = None
    basis: str = ""
    governance_basis: str = "PROTOTYPE_ASSUMPTION"
    open_question: Optional[str] = None

    def as_dict(self) -> dict:
        return {"role": self.role, "actor": self.actor, "basis": self.basis,
                "governance_basis": self.governance_basis,
                "open_question": self.open_question}


@dataclass(frozen=True)
class Recommendation:
    action: str
    statement: str
    target_role: Optional[str] = None
    property_name: Optional[str] = None
    authorized: bool = True

    def as_dict(self) -> dict:
        return {"action": self.action, "statement": self.statement,
                "target_role": self.target_role,
                "property_name": self.property_name,
                "authorized": self.authorized}


@dataclass(frozen=True)
class LaunchCase:
    subject_type: str
    subject_id: str
    decision_horizon: str
    readiness: tuple = field(default_factory=tuple)
    properties: dict = field(default_factory=dict)
    established: int = 0
    defaulted: int = 0
    unreported: int = 0

    @property
    def first_activity(self) -> Optional[str]:
        stamps = [p.get("effective_at") for p in self.properties.values()
                  if p.get("effective_at")]
        return min(stamps) if stamps else None

    @property
    def last_activity(self) -> Optional[str]:
        """Latest ARRIVAL, not latest occurrence.

        A case is stale by when we last heard something, not by when the last
        thing happened -- those differ by a month for the late-arriving facts
        in this corpus, and using occurrence would make a quiet case look busy.
        """
        stamps = [p.get("arrival_at") for p in self.properties.values()
                  if p.get("arrival_at")]
        return max(stamps) if stamps else None

    def readiness_named(self, decision_type: str) -> Optional[ReadinessView]:
        for view in self.readiness:
            if view.decision_type == decision_type:
                return view
        return None

    def as_dict(self) -> dict:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "decision_horizon": self.decision_horizon,
            "readiness": [v.as_dict() for v in self.readiness],
            "evidence_counts": {"established": self.established,
                                "defaulted": self.defaulted,
                                "unreported": self.unreported},
            "first_activity": self.first_activity,
            "last_activity": self.last_activity,
            "properties": self.properties,
        }


@dataclass(frozen=True)
class AgentResult:
    case: LaunchCase
    headline: str
    blockers: tuple = field(default_factory=tuple)
    waiting_on: Optional[WaitingOn] = None
    recommendation: Optional[Recommendation] = None
    communications: tuple = field(default_factory=tuple)
    journey: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "case": self.case.as_dict(),
            "headline": self.headline,
            "blockers": [b.as_dict() for b in self.blockers],
            "waiting_on": self.waiting_on.as_dict() if self.waiting_on else None,
            "recommendation": (self.recommendation.as_dict()
                               if self.recommendation else None),
            "communications": [c.as_dict() for c in self.communications],
            "journey": list(self.journey),
        }
