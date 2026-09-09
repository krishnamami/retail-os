"""The smallest boundary that turns real governed data into a DecisionContext.

    DecisionRequest
      + FoldLoader result          (state.fold_state_snapshot)
      + ResolvedRuleSet            (governed rule metadata)
      + rule_class bindings        (a domain pack, or a compiled artifact)
      + optional domain facts
      -> DecisionContext                                (D.4C contract)

This module performs no I/O of its own. It depends on ports, not on psycopg2.

GOVERNANCE BASIS (vertical slice)
---------------------------------
`governance_basis` is threaded through as a parameter that defaults to
AUTHORITATIVE. A caller that does not think about it gets production
governance, and prototype execution is reachable only by asking for it -- the
same shape as ExecutionMode. It is passed rather than inferred because the
builder must not guess: the basis is a property of the release the rules came
from, and only the resolver knows which release that was.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from .contracts import (
    GOVERNANCE_BASIS_AUTHORITATIVE,
    DecisionContext,
    DecisionRequest,
    DomainFacts,
    ExecutionMetadata,
    FoldSnapshotView,
    GovernanceBinding,
)
from .ports import (
    FoldLoaderPort,
    FoldLoadStatus,
    GovernanceResolverPort,
    ResolvedRuleSet,
    RuleClassBinding,
    bind_rule_metadata,
)

__all__ = ["ContextAssemblyResult", "ContextBuilder", "governance_from_rule_set"]


@dataclass(frozen=True)
class ContextAssemblyResult:
    """Either an assembled context, or the reason no governed state existed."""

    context: Optional[DecisionContext]
    fold_status: FoldLoadStatus
    rule_set: Optional[ResolvedRuleSet] = None
    detail: str = ""

    @property
    def assembled(self) -> bool:
        return self.context is not None


def governance_from_rule_set(
    rule_set: ResolvedRuleSet,
    class_bindings: Mapping[str, RuleClassBinding],
    required_properties: Sequence[str] = (),
    *,
    strict: bool = True,
    governance_basis: str = GOVERNANCE_BASIS_AUTHORITATIVE,
) -> GovernanceBinding:
    """Combine governed metadata with executable registration into D.4C's binding.

    `class_bindings` comes from a domain pack on the legacy path, and from the
    compiled artifact on the artifact path. Either way the KB resolver does not
    invent rule_class.

    `governance_basis` travels into the binding and from there into every
    DecisionResult built from it, so a result can never claim a basis its
    governance did not have. GovernanceBinding validates the value.
    """
    return GovernanceBinding(
        ontology_version=rule_set.ontology_version,
        kb_version=rule_set.kb_version,
        policy_version=rule_set.policy_version,
        rule_set=bind_rule_metadata(rule_set.rules, class_bindings, strict=strict),
        rule_set_digest=rule_set.rule_set_digest,
        required_properties=tuple(required_properties),
        excluded_rules=rule_set.excluded_rules,
        governance_basis=governance_basis,
    )


class ContextBuilder:
    """Assembles a D.4C DecisionContext from live governed sources."""

    __slots__ = ("_fold_loader", "_resolver", "_fact_provider")

    def __init__(
        self,
        fold_loader: FoldLoaderPort,
        resolver: GovernanceResolverPort,
        fact_provider=None,
    ) -> None:
        self._fold_loader = fold_loader
        self._resolver = resolver
        self._fact_provider = fact_provider

    def build(
        self,
        request: DecisionRequest,
        class_bindings: Mapping[str, RuleClassBinding],
        required_properties: Sequence[str] = (),
        *,
        strict: bool = True,
        governance_basis: str = GOVERNANCE_BASIS_AUTHORITATIVE,
    ) -> ContextAssemblyResult:
        fold_result = self._fold_loader.load(
            request.subject_type, request.subject_id, request.decision_horizon
        )
        if not fold_result.found:
            # Not converted into a business outcome here: D.4B V-2 has not
            # settled whether absent governed state is business or system.
            return ContextAssemblyResult(
                context=None,
                fold_status=fold_result.status,
                detail=fold_result.detail,
            )

        rule_set = self._resolver.resolve_rules(
            request.decision_type, request.requested_kb_version
        )
        governance = governance_from_rule_set(
            rule_set, class_bindings, required_properties, strict=strict,
            governance_basis=governance_basis,
        )
        facts = self._facts(request, fold_result.snapshot)

        return ContextAssemblyResult(
            context=DecisionContext(
                request=request,
                fold=fold_result.snapshot,
                governance=governance,
                facts=facts,
                execution=ExecutionMetadata(),
            ),
            fold_status=fold_result.status,
            rule_set=rule_set,
        )

    def _facts(self, request: DecisionRequest, fold: FoldSnapshotView) -> DomainFacts:
        if self._fact_provider is None:
            return DomainFacts()
        return self._fact_provider.facts_for(request, fold)
