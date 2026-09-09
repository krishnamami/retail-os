"""Prototype / production governance resolver boundary (D.4G.1G.5P.1).

The boundary is a candidate-set filter, not a preference order. The production
resolver does not rank prototype governance lower -- it never sees it. There is
therefore no fallback to disable, and no code path along which a prototype
assumption can satisfy a production request.

Both modes fail closed on an empty candidate set. Neither degrades.

This module implements only the selection contract. Loading candidates from a
live artifact store is D.4G.2 work and is deliberately absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts import (
    GOVERNANCE_BASIS_AUTHORITATIVE,
    GOVERNANCE_BASIS_PROTOTYPE,
)
from .errors import DecisionExecutionError

__all__ = [
    "AmbiguousGovernance",
    "ExecutionMode",
    "NoEligibleGovernance",
    "RELEASE_CLASS_AUTHORITATIVE",
    "RELEASE_CLASS_PROTOTYPE",
    "ReleaseCandidate",
    "VALIDATION_STATUS_PROTOTYPE",
    "select_release",
]

RELEASE_CLASS_AUTHORITATIVE = "AUTHORITATIVE"
RELEASE_CLASS_PROTOTYPE = "PROTOTYPE"
VALIDATION_STATUS_PROTOTYPE = "TO_BE_VALIDATED_WITH_CLARIS"

#: The basis each release class is permitted to carry. A release cannot hold
#: governance of the other kind; the database enforces the same pairing with a
#: composite foreign key and a CHECK.
_BASIS_FOR_CLASS = {
    RELEASE_CLASS_AUTHORITATIVE: GOVERNANCE_BASIS_AUTHORITATIVE,
    RELEASE_CLASS_PROTOTYPE: GOVERNANCE_BASIS_PROTOTYPE,
}


class ExecutionMode(Enum):
    """Which governance the caller is willing to execute against.

    PRODUCTION is the default everywhere. A caller that forgets to choose gets
    the safe one, and prototype execution is reachable only by asking for it.
    """

    PRODUCTION = "PRODUCTION"
    PROTOTYPE = "PROTOTYPE"


class NoEligibleGovernance(DecisionExecutionError):
    """No candidate satisfied the mode. Fail closed; never degrade."""


class AmbiguousGovernance(DecisionExecutionError):
    """More than one candidate satisfied the mode. Fail closed."""


class IncoherentReleaseCandidate(DecisionExecutionError):
    """A candidate's class, basis and validation status disagree."""


@dataclass(frozen=True)
class ReleaseCandidate:
    """One activated governance release the resolver may consider."""

    ontology_version: str
    release_class: str
    governance_basis: str
    artifact_status: str
    validation_status: str | None = None

    def __post_init__(self) -> None:
        expected = _BASIS_FOR_CLASS.get(self.release_class)
        if expected is None:
            raise IncoherentReleaseCandidate(
                "unknown release_class %r" % self.release_class
            )
        if self.governance_basis != expected:
            raise IncoherentReleaseCandidate(
                "release_class %s requires governance_basis %s; got %r"
                % (self.release_class, expected, self.governance_basis)
            )
        if self.release_class == RELEASE_CLASS_PROTOTYPE:
            if self.validation_status != VALIDATION_STATUS_PROTOTYPE:
                raise IncoherentReleaseCandidate(
                    "a prototype release must carry validation_status %s"
                    % VALIDATION_STATUS_PROTOTYPE
                )
        elif self.validation_status is not None:
            raise IncoherentReleaseCandidate(
                "an authoritative release carries no validation_status; got %r"
                % (self.validation_status,)
            )

    @property
    def is_prototype(self) -> bool:
        return self.release_class == RELEASE_CLASS_PROTOTYPE


def _eligible(candidate: ReleaseCandidate, mode: ExecutionMode) -> bool:
    if candidate.artifact_status != "active":
        return False
    if mode is ExecutionMode.PRODUCTION:
        return (candidate.release_class == RELEASE_CLASS_AUTHORITATIVE
                and candidate.governance_basis == GOVERNANCE_BASIS_AUTHORITATIVE)
    return (candidate.release_class == RELEASE_CLASS_PROTOTYPE
            and candidate.governance_basis == GOVERNANCE_BASIS_PROTOTYPE)


def select_release(
    candidates,
    mode: ExecutionMode = ExecutionMode.PRODUCTION,
) -> ReleaseCandidate:
    """The single release this mode may execute against.

    Raises NoEligibleGovernance when nothing qualifies -- including when the
    only governance present is of the other class. That is the whole point:
    production asked for confirmed governance, prototype governance is not
    confirmed governance, and answering with it would be a lie the caller
    could not detect.
    """
    if not isinstance(mode, ExecutionMode):
        raise NoEligibleGovernance("execution mode must be an ExecutionMode")

    eligible = [c for c in candidates if _eligible(c, mode)]
    if not eligible:
        raise NoEligibleGovernance(
            "no active %s governance release is available (%d candidate(s) "
            "considered); refusing to fall back"
            % (mode.value, len(list(candidates)))
        )
    if len(eligible) > 1:
        raise AmbiguousGovernance(
            "%d active %s governance releases; exactly one is required: %s"
            % (len(eligible), mode.value,
               ", ".join(sorted(c.ontology_version for c in eligible)))
        )
    return eligible[0]
