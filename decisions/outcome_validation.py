"""Version-scoped outcome validation (D.4G.2).

THE DEFECT THIS CORRECTS
------------------------
claris.is_valid_outcome() reads ontology.decision_outputs -- the frozen legacy
KB 1.0 vocabulary -- and its kb_version argument defaults to NULL, so an
omitted argument silently validates against whatever the legacy layer happens
to contain. Three of the six prototype identity effects (CREATE_PRODUCT,
CREATE_CONFIGURATION, NO_BUSINESS_CHANGE) do not exist there at all, so a
correct prototype decision would be rejected as invalid, and a legacy outcome
such as READY_FOR_LAUNCH would be accepted for a decision that never governed
it.

THE INVARIANT
-------------
    a decision executed against governance version X
    is validated against the outcomes declared by version X

There is no global ACTIVE lookup here, and no default that means "any
version". A vocabulary is bound to exactly one (ontology_version,
governance_basis, decision_type) triple, and validation fails closed when the
result and the vocabulary disagree about any of them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import GOVERNANCE_BASES
from .errors import DecisionExecutionError

__all__ = [
    "OutcomeNotDeclared",
    "OutcomeVocabulary",
    "OutcomeVocabularyMismatch",
    "validate_outcome",
    "validate_result",
]


class OutcomeNotDeclared(DecisionExecutionError):
    """The outcome is not in the vocabulary this governance version declares."""


class OutcomeVocabularyMismatch(DecisionExecutionError):
    """The vocabulary does not govern this decision, version or basis."""


@dataclass(frozen=True)
class OutcomeVocabulary:
    """The outcomes ONE governance version declares for ONE decision type."""

    ontology_version: str
    governance_basis: str
    decision_type: str
    outcomes: frozenset

    def __post_init__(self) -> None:
        if self.governance_basis not in GOVERNANCE_BASES:
            raise OutcomeVocabularyMismatch(
                f"unknown governance_basis {self.governance_basis!r}"
            )
        if not self.ontology_version or not self.decision_type:
            raise OutcomeVocabularyMismatch(
                "an outcome vocabulary must name its ontology version and "
                "decision type"
            )
        if not self.outcomes:
            raise OutcomeVocabularyMismatch(
                "an empty outcome vocabulary cannot validate anything; a "
                "governance version that declares no outcome is a defect, not "
                "a permissive default"
            )
        object.__setattr__(self, "outcomes", frozenset(self.outcomes))


def validate_outcome(
    vocabulary: OutcomeVocabulary,
    decision_type: str,
    outcome_code: str,
    ontology_version: str,
    governance_basis: str,
) -> None:
    """Fail closed unless the outcome belongs to exactly this version."""
    if vocabulary.decision_type != decision_type:
        raise OutcomeVocabularyMismatch(
            f"vocabulary governs {vocabulary.decision_type}, not {decision_type}"
        )
    if vocabulary.ontology_version != ontology_version:
        raise OutcomeVocabularyMismatch(
            f"vocabulary is for ontology_version {vocabulary.ontology_version!r};"
            f" the decision used {ontology_version!r}"
        )
    if vocabulary.governance_basis != governance_basis:
        raise OutcomeVocabularyMismatch(
            f"vocabulary basis {vocabulary.governance_basis!r} does not govern a"
            f" {governance_basis!r} decision"
        )
    if outcome_code not in vocabulary.outcomes:
        raise OutcomeNotDeclared(
            f"{outcome_code!r} is not declared by {decision_type} at "
            f"{ontology_version} ({governance_basis}); declared: "
            + ", ".join(sorted(vocabulary.outcomes))
        )


def validate_result(vocabulary: OutcomeVocabulary, result) -> None:
    """validate_outcome against a DecisionResult, reading its own versions."""
    validate_outcome(
        vocabulary,
        result.decision_type,
        result.outcome_code,
        result.ontology_version,
        result.governance_basis,
    )
