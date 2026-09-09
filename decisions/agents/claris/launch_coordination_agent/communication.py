"""Drafts. Never sends.

Channels and statuses match the existing Claris agent contract exactly, so the
Workbench renders both agents' output the same way:

    WORKBENCH_NOTE   a note recorded against the case
    EMAIL_DRAFT      an email a person may choose to send

    DRAFT            the only status this module ever produces
    SUPERSEDED       set when a later draft replaces an earlier one

There is no transport here and there is not going to be one in the prototype.
No SMTP, no Gmail, no queue. A draft is business evidence that a coordination
step was proposed -- it is not a message, and the difference is the point.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

__all__ = ["CHANNEL_NOTE", "CHANNEL_EMAIL_DRAFT", "CHANNELS",
           "STATUS_DRAFT", "STATUS_SUPERSEDED", "Draft", "draft_for"]

CHANNEL_NOTE = "WORKBENCH_NOTE"
CHANNEL_EMAIL_DRAFT = "EMAIL_DRAFT"
CHANNELS = (CHANNEL_NOTE, CHANNEL_EMAIL_DRAFT)

STATUS_DRAFT = "DRAFT"
STATUS_SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class Draft:
    communication_id: str
    channel: str
    status: str
    to_role: Optional[str]
    to_actor: Optional[str]
    subject: str
    body: str

    def as_dict(self) -> dict:
        return {"communication_id": self.communication_id,
                "channel": self.channel, "status": self.status,
                "to_role": self.to_role, "to_actor": self.to_actor,
                "subject": self.subject, "body": self.body}


def _identifier(case, channel: str, marker: str) -> str:
    seed = f"{case.subject_type}|{case.subject_id}|{channel}|{marker}"
    return "COMM-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _readiness_block(case) -> str:
    return "\n".join(
        f"  {v.decision_type:<22}{v.outcome:<16}{v.why}"
        for v in case.readiness)


def draft_for(case, blockers, waiting_on, recommendation) -> tuple:
    """A workbench note always; an email draft only when someone is waited on.

    The email names a ROLE, never a person. Every actor id in this corpus is
    simulated, and addressing a draft to an invented individual would be the
    one kind of fabrication that looks most like competence.
    """
    drafts = []
    worst = blockers[0] if blockers else None

    note_body = (
        f"Governed state for {case.subject_id} at horizon "
        f"{case.decision_horizon}\n\n"
        f"{_readiness_block(case)}\n\n"
        f"Evidence: {case.established} established "
        f"({case.defaulted} resting on projection defaults), "
        f"{case.unreported} never reported.\n"
    )
    if worst:
        note_body += f"\nPrimary blocker: {worst.statement}\n"
    if recommendation:
        note_body += f"Recommended: {recommendation.statement}\n"
    note_body += ("\nThis note records governed decisions. The agent did not "
                  "make them and has changed no business fact.")

    drafts.append(Draft(
        communication_id=_identifier(case, CHANNEL_NOTE,
                                     worst.property_name if worst else "ready"),
        channel=CHANNEL_NOTE, status=STATUS_DRAFT,
        to_role=None, to_actor=None,
        subject=f"{case.subject_id}: governed readiness summary",
        body=note_body))

    if waiting_on and waiting_on.role and worst:
        if worst.kind == "MANUFACTURED_EVIDENCE":
            ask = (f"Our records show {worst.property_name} as "
                   f"{worst.evidence_value!r}, but that value was supplied by "
                   f"a projection default -- no source system asserted it. "
                   f"Could you confirm it explicitly, or tell us it is not "
                   f"the case?")
        elif worst.kind == "OBSERVED_FAILURE":
            ask = (f"{worst.property_name} was reported as "
                   f"{worst.evidence_value!r}. This is an observed outcome, "
                   f"so the case cannot proceed until it is revisited.")
        else:
            ask = (f"We have no report of {worst.property_name} for "
                   f"{case.subject_id}. Could you supply it, or confirm it "
                   f"does not apply?")

        drafts.append(Draft(
            communication_id=_identifier(case, CHANNEL_EMAIL_DRAFT,
                                         worst.property_name or "blocker"),
            channel=CHANNEL_EMAIL_DRAFT, status=STATUS_DRAFT,
            to_role=waiting_on.role, to_actor=None,
            subject=f"{case.subject_id}: {worst.property_name} needed to "
                    f"progress",
            body=(f"{ask}\n\n"
                  f"Current governed readiness:\n{_readiness_block(case)}\n\n"
                  f"Addressed to the {waiting_on.role} role rather than an "
                  f"individual: {waiting_on.open_question}\n\n"
                  f"DRAFT -- not sent. Nothing in this prototype sends mail.")))

    return tuple(drafts)
