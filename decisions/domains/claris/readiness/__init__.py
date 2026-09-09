"""Governed readiness decisions for the Claris prototype.

policy.py declares what readiness requires. evaluate.py applies it. Nothing
here reads a database, calls a model, or reasons: a readiness outcome is a
function of folded properties and a declared policy, and that is what makes it
a governed decision rather than an opinion.
"""

from .policy import (  # noqa: F401
    OBSERVED_ONLY,
    OBSERVED_OR_DEFAULTED,
    POLICIES,
    POLICY_VERSION,
    AnyOf,
    ReadinessPolicy,
    Requirement,
)
from .evaluate import (  # noqa: F401
    CANNOT_DECIDE,
    NOT_READY,
    READY,
    InputFinding,
    ReadinessDecision,
    evaluate,
    evaluate_all,
)

__all__ = [
    "POLICIES", "POLICY_VERSION", "Requirement", "AnyOf", "ReadinessPolicy",
    "OBSERVED_ONLY", "OBSERVED_OR_DEFAULTED",
    "READY", "NOT_READY", "CANNOT_DECIDE",
    "InputFinding", "ReadinessDecision", "evaluate", "evaluate_all",
]
