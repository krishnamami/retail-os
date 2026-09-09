"""The launch coordination agent.

WHAT IT DOES
    Gathers governed state for a SKU, reads the readiness decisions already
    made about it, explains what is blocking, names the responsible role,
    recommends one authorized action, and drafts the communication that action
    implies.

WHAT IT CANNOT DO, BY CONSTRUCTION
    It has no decision logic. Outcomes come from
    decisions.domains.claris.readiness, which is pure and declarative. The
    agent cannot mark a SKU ready, cannot reclassify DEFAULTED evidence as
    OBSERVED, cannot resolve a contradiction and cannot name a person the
    evidence does not identify. Remove the readiness module and this agent has
    nothing to say -- which is the correct dependency direction.

    It also sends nothing. Every communication it produces is a DRAFT.
"""

from __future__ import annotations

from typing import Optional

from .communication import draft_for
from .context import DEFAULT_HORIZON, LaunchContextLoader
from .models import AgentResult
from .reasoning import (blockers_for, headline_for, journey_for,
                        recommend_for, waiting_on_for)

__all__ = ["LaunchCoordinationAgent"]


class LaunchCoordinationAgent:
    """Read-only coordination over governed readiness."""

    def __init__(self, db, horizon: str = DEFAULT_HORIZON,
                 subject_type: str = "sku") -> None:
        self._loader = LaunchContextLoader(db, horizon, subject_type)

    def subjects(self) -> tuple:
        return self._loader.subjects()

    def run(self, subject_id: str) -> Optional[AgentResult]:
        case = self._loader.load(subject_id)
        if case is None:
            return None
        return self._analyse(case)

    def run_all(self) -> tuple:
        return tuple(self._analyse(case) for case in self._loader.load_all())

    def _analyse(self, case) -> AgentResult:
        decisions = self._loader.decisions_for(case.subject_id, case.properties)
        blockers = blockers_for(decisions)
        waiting_on = waiting_on_for(blockers)
        recommendation = recommend_for(decisions, blockers, waiting_on)
        return AgentResult(
            case=case,
            headline=headline_for(case.subject_id, decisions, blockers),
            blockers=blockers,
            waiting_on=waiting_on,
            recommendation=recommendation,
            communications=draft_for(case, blockers, waiting_on,
                                     recommendation),
            journey=journey_for(case, decisions, blockers, recommendation),
        )
