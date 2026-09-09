"""Ports and governance metadata carried between adapters and the executor.

THE rule_class SEPARATION (D.4D section 11)
-------------------------------------------
`claris_kb.decision_rules` has no rule_class column, and D.4C deliberately
keeps GUARD/MATCH/FALLBACK as runtime registration metadata. So this module
holds two distinct things and never conflates them:

    GovernedRuleMetadata -- what the KB owns. No rule_class. No predicate.
    RuleClassBinding     -- what a domain pack owns. rule_class + predicate_ref.

`bind_rule_metadata()` is the only place they meet, and it is called by a
domain pack, never by the KB resolver. rule_class is never inferred from
prose, from outcome_code, or from precedence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence

from .contracts import DecisionRequest, DomainFacts, FoldSnapshotView
from .rules import RuleBinding, RuleClass, RuleDefinition

__all__ = [
    "FoldLoadStatus",
    "FoldLoadResult",
    "GovernedRuleMetadata",
    "ActiveKB",
    "ResolvedRuleSet",
    "RuleClassBinding",
    "bind_rule_metadata",
    "FoldLoaderPort",
    "GovernanceResolverPort",
    "DomainFactProviderPort",
]


# ======================================================================
# Fold loading
# ======================================================================

class FoldLoadStatus(Enum):
    """Outcome of a Fold snapshot lookup.

    NOT_FOUND is a STATUS, not an exception. D.4B open decision V-2 has not
    settled whether 'no governed state at this horizon' is a business
    CANNOT_DECIDE or a system failure, so the loader reports the fact and
    leaves the classification to the phase that consumes it. Malformed or
    duplicate data raises, because those are defects either way.
    """

    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class FoldLoadResult:
    status: FoldLoadStatus
    snapshot: Optional[FoldSnapshotView] = None
    detail: str = ""

    @property
    def found(self) -> bool:
        return self.status is FoldLoadStatus.FOUND


# ======================================================================
# Governed KB metadata -- no rule_class, no predicate
# ======================================================================

@dataclass(frozen=True)
class GovernedRuleMetadata:
    """One governed rule as the KB holds it.

    `condition_text` is carried verbatim as METADATA ONLY. Nothing in this
    codebase parses, evaluates, translates or transmits it. Executable
    behaviour comes from registered deterministic predicates.
    """

    decision_type: str
    rule_id: str
    kb_version: str
    ontology_version: str
    policy_version: str
    precedence: int
    outcome_code: str
    rule_name: Optional[str] = None
    reason_code: Optional[str] = None
    condition_text: Optional[str] = None
    required_evidence: Optional[str] = None
    missing_evidence_action: Optional[str] = None
    contradiction_action: Optional[str] = None
    status: Optional[str] = None
    authority: Optional[str] = None
    blocking_note: Optional[str] = None

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.decision_type, self.rule_id, self.kb_version)


@dataclass(frozen=True)
class ActiveKB:
    kb_version: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedRuleSet:
    """Governed rule metadata for one decision type at one KB version."""

    decision_type: str
    kb_version: str
    ontology_version: str
    policy_version: str
    rules: tuple[GovernedRuleMetadata, ...]
    excluded_rules: tuple[tuple[str, str], ...] = ()
    rule_set_digest: str = ""


# ======================================================================
# Domain-owned executable registration metadata
# ======================================================================

@dataclass(frozen=True)
class RuleClassBinding:
    """Supplied by a DOMAIN PACK, never by the KB resolver."""

    rule_id: str
    rule_class: RuleClass
    predicate_ref: str
    precedence_override: Optional[int] = None


def bind_rule_metadata(
    metadata: Sequence[GovernedRuleMetadata],
    class_bindings: Mapping[str, RuleClassBinding],
    *,
    strict: bool = True,
) -> tuple[RuleBinding, ...]:
    """Combine governed KB metadata with domain executable registration.

    This is the ONLY place rule_class enters the runtime. A domain pack calls
    it; the KB resolver does not. With strict=True (default), governed rules
    without a domain binding raise rather than being silently dropped -- the
    same reasoning as D.4C strict mode.
    """
    from .adapters.errors import UnboundGovernedRule  # local: avoid cycle

    bound: list[RuleBinding] = []
    unbound: list[str] = []
    for item in metadata:
        binding = class_bindings.get(item.rule_id)
        if binding is None:
            unbound.append(item.rule_id)
            continue
        bound.append(
            RuleBinding(
                definition=RuleDefinition(
                    decision_type=item.decision_type,
                    rule_id=item.rule_id,
                    kb_version=item.kb_version,
                    rule_class=binding.rule_class,
                    precedence=(
                        binding.precedence_override
                        if binding.precedence_override is not None
                        else item.precedence
                    ),
                    outcome_code=item.outcome_code,
                    reason_code=item.reason_code,
                ),
                predicate_ref=binding.predicate_ref,
            )
        )
    if unbound and strict:
        raise UnboundGovernedRule(
            "governed rules have no domain rule_class binding: " + ", ".join(sorted(unbound))
        )
    return tuple(bound)


# ======================================================================
# Ports
# ======================================================================

class FoldLoaderPort(Protocol):
    def load(
        self, subject_type: str, subject_id: str, decision_horizon: datetime
    ) -> FoldLoadResult: ...


class GovernanceResolverPort(Protocol):
    def active_kb(self) -> ActiveKB: ...

    def resolve_rules(
        self, decision_type: str, kb_version: Optional[str] = None
    ) -> ResolvedRuleSet: ...


class DomainFactProviderPort(Protocol):
    def facts_for(
        self, request: DecisionRequest, fold: FoldSnapshotView
    ) -> DomainFacts: ...
