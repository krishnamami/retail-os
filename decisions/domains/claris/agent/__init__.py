"""The Claris coordination agent.

ONE agent, deliberately. Not a Marketing agent, a Finance agent, an IS&T agent
and an Ops agent -- those are a later question, and building five before one has
proved useful would be building an organisation chart rather than a capability.

    case.py           reads one change out of persisted state
    coordination.py   derives status, blocker, owner and next action by rule
    communication.py  drafts the message; sends nothing
    agent.py          puts the three together into the Workbench contract

The agent observes. Claris's own systems start launches; governed decision
services conclude; this layer explains where a change is waiting and on whom,
and prepares what a person would send. It never concludes a governed outcome
and never contacts anyone.
"""

from __future__ import annotations

from .agent import AgentResult, ClarisCoordinationAgent
from .case import CaseContext, CaseContextAssembler, is_simulated_actor
from .communication import (
    CHANNELS,
    COMMUNICATION_TYPES,
    STATUS_DRAFT,
    CommunicationDraft,
    draft_for,
)
from .coordination import (
    ACTIONS,
    STATUSES,
    Coordination,
    JourneyEntry,
    analyse,
    build_journey,
)

__all__ = [
    "ACTIONS",
    "STATUSES",
    "CHANNELS",
    "COMMUNICATION_TYPES",
    "STATUS_DRAFT",
    "AgentResult",
    "CaseContext",
    "CaseContextAssembler",
    "ClarisCoordinationAgent",
    "CommunicationDraft",
    "Coordination",
    "JourneyEntry",
    "analyse",
    "build_journey",
    "draft_for",
    "is_simulated_actor",
]
