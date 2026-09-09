"""Shared builders and synthetic predicates for the D.4C executor core tests.

Deliberately NOT named conftest.py. The repository contains several
conftest.py files and no Python packages, so `import conftest` resolves to
whichever one pytest imported first -- tests/evidence/conftest.py wins in a
full-suite run. A unique module name removes that ambiguity entirely.

NO PostgreSQL. NO AWS. NO network. Every context is built in memory.

Predicates here are neutral and synthetic (TEST-GUARD-001, TEST-MATCH-001,
TEST-FALLBACK-001 and friends). They deliberately encode no Claris business
logic: the point is to prove the executor is not an IDENTITY_ASSESSMENT
implementation.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Make the repository root importable regardless of how pytest is invoked.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from decisions import (  # noqa: E402
    MATCHED,
    NOT_MATCHED,
    DecisionContext,
    DecisionRequest,
    DomainFacts,
    FoldProperty,
    FoldSnapshotView,
    FoldState,
    GovernanceBinding,
    GovernedDecisionExecutor,
    Known,
    PredicateRegistry,
    RuleBinding,
    RuleClass,
    RuleDefinition,
)

HORIZON = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
EFFECTIVE = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
ARRIVED = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)

TYPE_A = "TEST_IDENTITY"
TYPE_B = "TEST_READINESS"
KB = "1.0.1"


# ----------------------------------------------------------------------
# synthetic predicates -- neutral, no domain meaning
# ----------------------------------------------------------------------

def always_match(context):
    return MATCHED


def never_match(context):
    return NOT_MATCHED


def match_when_flag(flag_name: str):
    """Match iff a named opaque domain fact is truthy.

    The executor never learns what the fact means -- that is the point.
    """

    def _predicate(context):
        return MATCHED if context.facts.value_of(flag_name) else NOT_MATCHED

    return _predicate


def match_when_state(property_name: str, state: FoldState):
    """Match iff a named property carries a given governed state."""

    def _predicate(context):
        return MATCHED if context.state_of(property_name) is state else NOT_MATCHED

    return _predicate


# ----------------------------------------------------------------------
# builders
# ----------------------------------------------------------------------

def make_property(
    name: str,
    value=None,
    state: FoldState = FoldState.ESTABLISHED,
    value_type: str | None = "string",
    assertions: tuple[str, ...] = ("a-1",),
) -> FoldProperty:
    if state is not FoldState.ESTABLISHED:
        value, value_type, assertions = None, None, ()
    return FoldProperty(
        property_name=name,
        resolved_value=value,
        property_value_type=value_type,
        fold_state=state,
        effective_at=EFFECTIVE if state is FoldState.ESTABLISHED else None,
        latest_known_arrival_at=ARRIVED if state is FoldState.ESTABLISHED else None,
        basis_assertion_ids=assertions,
    )


def make_rule(
    rule_id: str,
    rule_class: RuleClass,
    precedence: int,
    outcome_code: str,
    reason_code: str | None = None,
    decision_type: str = TYPE_A,
    kb_version: str = KB,
    predicate_ref: str | None = None,
) -> RuleBinding:
    return RuleBinding(
        definition=RuleDefinition(
            decision_type=decision_type,
            rule_id=rule_id,
            kb_version=kb_version,
            rule_class=rule_class,
            precedence=precedence,
            outcome_code=outcome_code,
            reason_code=reason_code,
        ),
        predicate_ref=predicate_ref or f"ref::{rule_id}",
    )


def make_context(
    rule_set: tuple[RuleBinding, ...] = (),
    properties: dict | None = None,
    facts: dict | None = None,
    required_properties: tuple[str, ...] = (),
    decision_type: str = TYPE_A,
    subject_type: str = "test_subject",
    subject_id: str = "SUBJ-001",
    kb_version: str = KB,
    policy_version: str = "P-1",
    ontology_version: str = "O-1",
    rule_set_digest: str = "rsd-1",
    excluded_rules: tuple = (),
) -> DecisionContext:
    props = properties if properties is not None else {}
    return DecisionContext(
        request=DecisionRequest(
            decision_type=decision_type,
            subject_type=subject_type,
            subject_id=subject_id,
            decision_horizon=HORIZON,
        ),
        fold=FoldSnapshotView(
            fold_state_id="fs-0001",
            subject_type=subject_type,
            subject_id=subject_id,
            decision_horizon=HORIZON,
            fold_status=FoldState.ESTABLISHED,
            kb_version=kb_version,
            policy_version=policy_version,
            properties=props,
        ),
        governance=GovernanceBinding(
            ontology_version=ontology_version,
            kb_version=kb_version,
            policy_version=policy_version,
            rule_set=rule_set,
            rule_set_digest=rule_set_digest,
            required_properties=required_properties,
            excluded_rules=excluded_rules,
        ),
        facts=DomainFacts({k: Known(v) for k, v in (facts or {}).items()}),
    )


def make_executor(*registrations, policy=None) -> GovernedDecisionExecutor:
    """registrations: (decision_type, rule_id, kb_version, predicate) tuples."""
    registry = PredicateRegistry()
    for decision_type, rule_id, kb_version, predicate in registrations:
        registry.register(decision_type, rule_id, kb_version, predicate)
    return GovernedDecisionExecutor(registry, policy=policy)
