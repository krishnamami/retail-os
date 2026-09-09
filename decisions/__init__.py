"""Generic governed decision platform.

STEP 5G.6 PHASE D.4C -- executor core only.

This package is DOMAIN-AGNOSTIC. It must never import from
`decisions.domains.*`; the dependency points one way only. Domain packs are
injected at construction time.

Not in this phase: PostgreSQL, Fold loader, KB resolver, Claris predicates,
decision persistence, authorization, actions, projections.
"""

from __future__ import annotations

from .contracts import (
    MATCHED,
    NOT_APPLICABLE,
    NOT_MATCHED,
    DecisionContext,
    DecisionRequest,
    DecisionResult,
    DomainFacts,
    ExecutionMetadata,
    ExecutionStatus,
    FoldProperty,
    FoldSnapshotView,
    FoldState,
    GovernanceBinding,
    Known,
    PredicateResult,
    PredicateVerdict,
    Unavailable,
)
from .digest import DIGEST_SCHEME_VERSION, canonical_json, compute_input_digest
from .errors import (
    ConflictingDecisionMatch,
    DecisionExecutionError,
    DigestSerializationError,
    DuplicatePredicateRegistration,
    EmptyRuleSet,
    InvalidDecisionContext,
    InvalidDecisionRequest,
    InvalidRuleDefinition,
    MissingPredicate,
    MultipleFallbackRules,
    NoDecisionResolved,
    PredicateExecutionError,
)
from .executor import (
    EXECUTOR_VERSION,
    ConflictPolicy,
    ExecutorPolicy,
    GovernedDecisionExecutor,
)
from .registry import Predicate, PredicateRegistry
from .rules import RuleBinding, RuleClass, RuleDefinition, order_bindings

__version__ = EXECUTOR_VERSION

__all__ = [
    "DecisionContext",
    "DecisionRequest",
    "DecisionResult",
    "DomainFacts",
    "ExecutionMetadata",
    "ExecutionStatus",
    "FoldProperty",
    "FoldSnapshotView",
    "FoldState",
    "GovernanceBinding",
    "Known",
    "Unavailable",
    "PredicateResult",
    "PredicateVerdict",
    "MATCHED",
    "NOT_MATCHED",
    "NOT_APPLICABLE",
    "RuleBinding",
    "RuleClass",
    "RuleDefinition",
    "order_bindings",
    "Predicate",
    "PredicateRegistry",
    "GovernedDecisionExecutor",
    "ExecutorPolicy",
    "ConflictPolicy",
    "EXECUTOR_VERSION",
    "canonical_json",
    "compute_input_digest",
    "DIGEST_SCHEME_VERSION",
    "DecisionExecutionError",
    "InvalidDecisionRequest",
    "InvalidDecisionContext",
    "InvalidRuleDefinition",
    "MultipleFallbackRules",
    "EmptyRuleSet",
    "DuplicatePredicateRegistration",
    "MissingPredicate",
    "PredicateExecutionError",
    "ConflictingDecisionMatch",
    "NoDecisionResolved",
    "DigestSerializationError",
]
