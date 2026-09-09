"""The actions this agent may recommend. A closed list, on purpose.

Every one is a draft or a request. None of them changes a business fact, sends
anything, or writes to a source system. The agent recommends; a person acts.
"""

from __future__ import annotations

__all__ = ["ACTIONS", "REQUEST_EVIDENCE", "REQUEST_REVIEW", "ESCALATE",
           "ADD_NOTE", "AWAIT_EVIDENCE", "NO_ACTION", "is_authorized"]

REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
REQUEST_REVIEW = "REQUEST_DECISION"
ESCALATE = "ESCALATE"
ADD_NOTE = "ADD_NOTE"
AWAIT_EVIDENCE = "AWAIT_EVIDENCE"
NO_ACTION = "NO_ACTION_REQUIRED"

#: action -> what it means and what it may not do.
ACTIONS = {
    REQUEST_EVIDENCE: "Draft a request to the responsible role for a fact no "
                      "source has reported. Never fabricates the fact.",
    REQUEST_REVIEW:   "Draft a request for a governed decision that has not "
                      "been made. Never makes it.",
    ESCALATE:         "Draft an escalation where evidence is contradicted or "
                      "observed to fail. Never resolves the contradiction.",
    ADD_NOTE:         "Record a workbench note stating current governed "
                      "state. Never asserts more than the decisions do.",
    AWAIT_EVIDENCE:   "Do nothing and say so, because the case is waiting on "
                      "an event that has not arrived.",
    NO_ACTION:        "Nothing is required; readiness is satisfied.",
}


def is_authorized(action: str) -> bool:
    return action in ACTIONS
