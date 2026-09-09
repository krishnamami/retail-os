"""Execution error model for the generic governed decision executor.

CRITICAL DISTINCTION (D.4B section O):

    Business outcome   -> a DecisionResult with outcome_code CANNOT_DECIDE.
                          Legitimate, persistable, NOT retryable.
    System failure     -> an exception from this module. No decision is
                          produced, nothing is persisted, and it IS retryable.

A system failure must never be converted into a business CANNOT_DECIDE.
Doing so would fabricate a governed statement: asserting that the business
could not decide when in truth the platform did not run.
"""

from __future__ import annotations

__all__ = [
    "DecisionExecutionError",
    "InvalidDecisionRequest",
    "InvalidDecisionContext",
    "InvalidRuleDefinition",
    "DuplicatePredicateRegistration",
    "MissingPredicate",
    "ConflictingDecisionMatch",
    "MultipleFallbackRules",
    "EmptyRuleSet",
    "PredicateExecutionError",
    "DigestSerializationError",
    "NoDecisionResolved",
]


class DecisionExecutionError(Exception):
    """Base class for every system/execution failure.

    Catching this type catches all system failures and no business outcomes.
    """


# -- request / context / rule configuration ------------------------------

class InvalidDecisionRequest(DecisionExecutionError):
    """The DecisionRequest is structurally invalid."""


class InvalidDecisionContext(DecisionExecutionError):
    """The DecisionContext is structurally invalid or internally inconsistent."""


class InvalidRuleDefinition(DecisionExecutionError):
    """A RuleDefinition/RuleBinding is malformed or governance-inconsistent."""


class MultipleFallbackRules(InvalidRuleDefinition):
    """More than one FALLBACK rule was supplied for a decision type.

    D.4B section C locks at most one FALLBACK per decision type. Two fallbacks
    make the terminal outcome non-deterministic, so this fails closed at
    validation time rather than picking one.
    """


class EmptyRuleSet(DecisionExecutionError):
    """No executable rules were supplied for the decision type.

    D.4B section G: this is a platform misconfiguration, NOT a business
    CANNOT_DECIDE. The governed rule set is missing, so nothing was evaluated.
    """


# -- registry ------------------------------------------------------------

class DuplicatePredicateRegistration(DecisionExecutionError):
    """A predicate is already registered for this (decision_type, rule_id, kb_version).

    Never last-wins: a silent overwrite would rebind a governed rule to
    different logic with no signal.
    """


class MissingPredicate(DecisionExecutionError):
    """An active governed rule has no registered predicate.

    D.4B section B: strict mode. Silently skipping an active rule would let
    the executor return an outcome the KB does not sanction.
    """


# -- evaluation ----------------------------------------------------------

class PredicateExecutionError(DecisionExecutionError):
    """A predicate raised, or returned something that is not a PredicateResult.

    Predicates signal 'this rule does not apply' with NOT_MATCHED. An exception
    is always a defect, never an ordinary outcome.
    """


class ConflictingDecisionMatch(DecisionExecutionError):
    """Two or more MATCH rules matched at the same precedence.

    Raised only under ConflictPolicy.RAISE. Under the D.4B-recommended default
    (ConflictPolicy.CANNOT_DECIDE) the same situation yields a business
    CANNOT_DECIDE / GOVERNANCE_AMBIGUITY instead. See open decision V-3.
    """

    def __init__(self, decision_type: str, precedence: int, rule_ids: tuple[str, ...]):
        self.decision_type = decision_type
        self.precedence = precedence
        self.rule_ids = rule_ids
        super().__init__(
            f"{decision_type}: {len(rule_ids)} MATCH rules matched at precedence "
            f"{precedence}: {', '.join(rule_ids)}"
        )


class NoDecisionResolved(DecisionExecutionError):
    """Evaluation completed without producing an outcome.

    Defensive. Under the locked contract every path terminates in an outcome
    (guard, match, fallback, or CANNOT_DECIDE / NO_RULE_MATCHED), so reaching
    this indicates an executor defect rather than a governance condition.
    """


# -- digest --------------------------------------------------------------

class DigestSerializationError(DecisionExecutionError):
    """A value could not be canonically serialized for input_digest."""
