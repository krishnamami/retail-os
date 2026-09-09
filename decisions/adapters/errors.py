"""Adapter-layer failures. All subclass D.4C's DecisionExecutionError.

Held here rather than in decisions/errors.py so the D.4C core files stay
byte-unchanged by D.4D.
"""

from __future__ import annotations

from ..errors import (
    DecisionExecutionError,
    EmptyRuleSet,
    InvalidDecisionContext,
)

__all__ = [
    "AdapterError",
    "ReadOnlyViolation",
    "DuplicateFoldSnapshot",
    "MalformedFoldSnapshot",
    "InvalidFoldPropertyState",
    "NoActiveKB",
    "MultipleActiveKB",
    "KBVersionNotFound",
    "GovernanceVersionAmbiguity",
    "NoExecutableRuleSet",
    "UnboundGovernedRule",
]


class AdapterError(DecisionExecutionError):
    """Base for live-adapter system failures."""


class ReadOnlyViolation(AdapterError):
    """A statement that is not a read was submitted through a read-only adapter.

    Enforced in code as well as by the server-side read-only session, because
    a defect should fail before it reaches the database, not after.
    """


# -- Fold ----------------------------------------------------------------

class DuplicateFoldSnapshot(AdapterError):
    """More than one snapshot for (decision_horizon, subject_type, subject_id).

    `fold_state_unique_horizon` makes this unreachable under exact-equality
    lookup. It is checked anyway: a uniqueness constraint is a promise, and
    the loader should fail loudly rather than silently take row zero if the
    promise is ever broken.
    """


class MalformedFoldSnapshot(InvalidDecisionContext):
    """folded_properties is not the governed structure.

    Not repaired, not coerced, not defaulted. Malformed governed state is
    surfaced.
    """


class InvalidFoldPropertyState(MalformedFoldSnapshot):
    """An element carries a fold_state outside the governed vocabulary.

    D.4A established that the CHECK constraint protects only the row-level
    `fold_status` column; the element-level `fold_state` inside the jsonb
    array is unconstrained. This loader is the only place it is validated.
    """


# -- Governance ----------------------------------------------------------

class NoActiveKB(AdapterError):
    """claris_kb.v_active_kb returned no row."""


class MultipleActiveKB(AdapterError):
    """claris_kb.v_active_kb returned more than one row."""


class KBVersionNotFound(AdapterError):
    """An explicitly requested KB version has no governed rules."""


class GovernanceVersionAmbiguity(AdapterError):
    """Rules in one resolved set disagree on ontology/policy version.

    D.4B section G carries the three versions independently and does not
    assume they move together. If a decision type's rules disagree, the
    correct triple cannot be chosen by the adapter, so it is reported rather
    than invented.
    """


class NoExecutableRuleSet(EmptyRuleSet):
    """No executable governed rules exist for a decision type.

    This is a SYSTEM status, never a business CANNOT_DECIDE. It is what
    IDENTITY_ASSESSMENT must produce today: IR-010..IR-013 are semantic
    candidates in claris_kb.identity_rules with status 'proposed' and have no
    executable rows in claris_kb.decision_rules. The resolver must not promote
    them.
    """


class UnboundGovernedRule(AdapterError):
    """A governed rule has no domain rule_class/predicate binding."""
