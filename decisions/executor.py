"""The generic governed decision executor.

This module contains no reference to Claris, SAP, SKUs, product_reference,
geography, term_months, customer_segment or canonical identity, and no branch
on any decision_type value. It understands exactly six things:

    DecisionRequest, DecisionContext, RuleBinding, RuleClass,
    PredicateResult, DecisionResult

EVALUATION ALGORITHM
    0. validate context and rule set
    1. order bindings: GUARD -> MATCH -> FALLBACK; then precedence asc;
       then rule_id asc  (see rules.order_bindings)
    2. assemble evidence by scanning governance.required_properties
    3. evaluate GUARD rules in order; first MATCHED terminates and yields its
       governed outcome. No MATCH rule executes afterward.
    4. otherwise evaluate MATCH rules in order; first MATCHED wins, unless
       another MATCH rule at the SAME precedence also matched (see
       ConflictPolicy)
    5. otherwise the single FALLBACK rule, if declared
    6. otherwise CANNOT_DECIDE / NO_RULE_MATCHED

The executor never learns WHY a predicate matched. That is the predicate's
business, and the executor's ignorance of it is what keeps the platform
generic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts import (
    DecisionContext,
    DecisionResult,
    ExecutionStatus,
    FoldState,
    Known,
    PredicateResult,
    Unavailable,
)
from .digest import DIGEST_SCHEME_VERSION, compute_input_digest
from .errors import (
    ConflictingDecisionMatch,
    EmptyRuleSet,
    InvalidDecisionContext,
    MissingPredicate,
    MultipleFallbackRules,
    NoDecisionResolved,
    PredicateExecutionError,
)
from .registry import PredicateRegistry
from .rules import RuleBinding, RuleClass, order_bindings

__all__ = [
    "ConflictPolicy",
    "ExecutorPolicy",
    "GovernedDecisionExecutor",
    "EXECUTOR_VERSION",
]

EXECUTOR_VERSION = "d4c/1.0"

# States that make a required property unusable. The executor does not decide
# what they MEAN; it only reports which required properties are in them, so the
# evidence arrays are complete regardless of which rule fired.
_MISSING_STATES = frozenset({FoldState.UNREPORTED})
_BLOCKING_STATES = frozenset({FoldState.CONTRADICTED, FoldState.INVALID})


class ConflictPolicy(Enum):
    """Behaviour when two MATCH rules match at the same precedence.

    D.4B open decision V-3. The default is D.4B's recommendation.
    """

    CANNOT_DECIDE = "CANNOT_DECIDE"  # business outcome, persistable
    RAISE = "RAISE"                  # ConflictingDecisionMatch, system failure


@dataclass(frozen=True)
class ExecutorPolicy:
    """Platform-level vocabulary and behaviour.

    The outcome/reason strings are parameters rather than constants so the
    platform does not hard-code one domain's vocabulary. The defaults are the
    D.4B-locked values.
    """

    conflict_policy: ConflictPolicy = ConflictPolicy.CANNOT_DECIDE
    cannot_decide_outcome: str = "CANNOT_DECIDE"
    no_rule_matched_reason: str = "NO_RULE_MATCHED"
    ambiguity_reason: str = "GOVERNANCE_AMBIGUITY"
    confidence_high: str = "HIGH"
    confidence_low: str = "LOW"


class GovernedDecisionExecutor:
    """Deterministic, side-effect-free governed decision evaluation.

    Writes nothing. Opens no connection. Returns a value.
    """

    __slots__ = ("_registry", "_policy")

    def __init__(
        self,
        registry: PredicateRegistry,
        policy: ExecutorPolicy | None = None,
    ) -> None:
        if not isinstance(registry, PredicateRegistry):
            raise InvalidDecisionContext(
                f"registry must be a PredicateRegistry, got {registry!r}"
            )
        self._registry = registry
        self._policy = policy or ExecutorPolicy()

    @property
    def policy(self) -> ExecutorPolicy:
        return self._policy

    # ==================================================================
    # public entry point
    # ==================================================================

    def execute(self, context: DecisionContext) -> DecisionResult:
        """Evaluate one governed decision.

        Returns a DecisionResult, or raises a DecisionExecutionError subclass.
        A system failure is NEVER converted into a business CANNOT_DECIDE.
        """
        if not isinstance(context, DecisionContext):
            raise InvalidDecisionContext(
                f"execute() requires a DecisionContext, got {type(context).__name__}"
            )

        bindings = self._validated_bindings(context)
        missing_evidence, blocking_evidence = self._assemble_evidence(context)
        digest = compute_input_digest(context)

        guards = tuple(b for b in bindings if b.rule_class is RuleClass.GUARD)
        matches = tuple(b for b in bindings if b.rule_class is RuleClass.MATCH)
        fallbacks = tuple(b for b in bindings if b.rule_class is RuleClass.FALLBACK)

        # -- 3. guards ---------------------------------------------------
        for binding in guards:
            if self._evaluate(binding, context).matched:
                return self._result(
                    context, binding, digest, missing_evidence, blocking_evidence
                )

        # -- 4. matches --------------------------------------------------
        matched = [b for b in matches if self._evaluate(b, context).matched]
        if matched:
            winner = matched[0]
            tied = tuple(b for b in matched if b.precedence == winner.precedence)
            if len(tied) > 1:
                return self._ambiguous(
                    context, tied, digest, missing_evidence, blocking_evidence
                )
            return self._result(
                context, winner, digest, missing_evidence, blocking_evidence
            )

        # -- 5. fallback -------------------------------------------------
        if fallbacks:
            return self._result(
                context, fallbacks[0], digest, missing_evidence, blocking_evidence
            )

        # -- 6. nothing resolved ----------------------------------------
        return self._synthetic(
            context,
            outcome_code=self._policy.cannot_decide_outcome,
            reason_code=self._policy.no_rule_matched_reason,
            digest=digest,
            missing_evidence=missing_evidence,
            blocking_evidence=blocking_evidence,
        )

    # ==================================================================
    # internals
    # ==================================================================

    def _validated_bindings(self, context: DecisionContext) -> tuple[RuleBinding, ...]:
        decision_type = context.request.decision_type
        rule_set = context.governance.rule_set

        relevant = tuple(b for b in rule_set if b.decision_type == decision_type)
        if not relevant:
            raise EmptyRuleSet(
                f"no executable rules for decision_type={decision_type!r}; "
                "the governed rule set is missing, which is a platform "
                "misconfiguration and not a business CANNOT_DECIDE"
            )

        fallbacks = [b for b in relevant if b.rule_class is RuleClass.FALLBACK]
        if len(fallbacks) > 1:
            raise MultipleFallbackRules(
                f"{decision_type}: {len(fallbacks)} FALLBACK rules declared "
                f"({', '.join(sorted(b.rule_id for b in fallbacks))}); at most one "
                "is permitted, otherwise the terminal outcome is non-deterministic"
            )

        seen: dict[tuple[str, str, str], RuleBinding] = {}
        for binding in relevant:
            if binding.definition.key in seen:
                raise InvalidDecisionContext(
                    f"duplicate rule in rule_set: {binding.definition.key}"
                )
            seen[binding.definition.key] = binding

        absent = self._registry.missing_for(relevant)
        if absent:
            raise MissingPredicate(
                "active governed rules have no registered predicate (strict mode): "
                + ", ".join(f"{d}/{r}@{k}" for d, r, k in absent)
            )

        return order_bindings(relevant)

    def _evaluate(self, binding: RuleBinding, context: DecisionContext) -> PredicateResult:
        predicate = self._registry.resolve_binding(binding)
        try:
            result = predicate(context)
        except Exception as exc:  # noqa: BLE001 - deliberate: any escape is a defect
            raise PredicateExecutionError(
                f"predicate for {binding.decision_type}/{binding.rule_id}"
                f"@{binding.kb_version} raised {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(result, PredicateResult):
            raise PredicateExecutionError(
                f"predicate for {binding.decision_type}/{binding.rule_id}"
                f"@{binding.kb_version} returned {type(result).__name__}, "
                "expected PredicateResult"
            )
        return result

    def _assemble_evidence(
        self, context: DecisionContext
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Full scan of declared required properties.

        D.4B section N: the OUTCOME comes from the first matching rule, but the
        evidence arrays are built from every required property, so the record
        is complete even when a guard short-circuits.

        The executor does not know what any property means. It only reads
        governed state.
        """
        missing: list[str] = []
        blocking: list[str] = []
        for name in context.governance.required_properties:
            prop = context.fold.property_named(name)
            if prop is None:
                missing.append(name)          # absent is distinct from UNREPORTED
            elif prop.fold_state in _MISSING_STATES:
                missing.append(name)
            elif prop.fold_state in _BLOCKING_STATES:
                blocking.append(name)
        return tuple(sorted(missing)), tuple(sorted(blocking))

    def _confidence(
        self,
        binding: RuleBinding | None,
        missing_evidence: tuple[str, ...],
        blocking_evidence: tuple[str, ...],
    ) -> str:
        if missing_evidence or blocking_evidence:
            return self._policy.confidence_low
        if binding is None or binding.rule_class is not RuleClass.MATCH:
            return self._policy.confidence_low
        return self._policy.confidence_high

    def _lineage(
        self, context: DecisionContext
    ) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
        return tuple(
            (
                name,
                context.fold.properties[name].fold_state.value,
                tuple(sorted(context.fold.properties[name].basis_assertion_ids)),
            )
            for name in sorted(context.fold.properties)
        )

    def _facts_used(self, context: DecisionContext) -> tuple[tuple[str, str], ...]:
        used: list[tuple[str, str]] = []
        for name in sorted(context.facts.facts):
            fact = context.facts.facts[name]
            if isinstance(fact, Known):
                used.append((name, f"KNOWN:{fact.value!r}"))
            elif isinstance(fact, Unavailable):
                used.append((name, f"UNAVAILABLE:{fact.reason}"))
        return tuple(used)

    def _build(
        self,
        context: DecisionContext,
        *,
        outcome_code: str,
        reason_code: str | None,
        binding: RuleBinding | None,
        digest: str,
        missing_evidence: tuple[str, ...],
        blocking_evidence: tuple[str, ...],
    ) -> DecisionResult:
        gov = context.governance
        if not outcome_code:
            raise NoDecisionResolved(
                "evaluation completed without an outcome_code; executor defect"
            )
        return DecisionResult(
            decision_type=context.request.decision_type,
            subject_type=context.request.subject_type,
            subject_id=context.request.subject_id,
            horizon_as_of=context.request.decision_horizon,
            outcome_code=outcome_code,
            reason_code=reason_code,
            ontology_version=gov.ontology_version,
            kb_version=gov.kb_version,
            policy_version=gov.policy_version,
            input_digest=digest,
            matched_rule_id=binding.rule_id if binding else None,
            matched_rule_kb_version=binding.kb_version if binding else None,
            matched_rule_class=binding.rule_class.value if binding else None,
            missing_evidence=missing_evidence,
            blocking_evidence=blocking_evidence,
            confidence_level=self._confidence(binding, missing_evidence, blocking_evidence),
            fold_state_id=context.fold.fold_state_id,
            fold_lineage=self._lineage(context),
            domain_facts_used=self._facts_used(context),
            excluded_rules=gov.excluded_rules,
            execution_status=ExecutionStatus.DECIDED,
            executor_version=context.execution.executor_version or EXECUTOR_VERSION,
            digest_scheme_version=DIGEST_SCHEME_VERSION,
            governance_basis=gov.governance_basis,
        )

    def _result(
        self,
        context: DecisionContext,
        binding: RuleBinding,
        digest: str,
        missing_evidence: tuple[str, ...],
        blocking_evidence: tuple[str, ...],
    ) -> DecisionResult:
        return self._build(
            context,
            outcome_code=binding.definition.outcome_code,
            reason_code=binding.definition.reason_code,
            binding=binding,
            digest=digest,
            missing_evidence=missing_evidence,
            blocking_evidence=blocking_evidence,
        )

    def _synthetic(
        self,
        context: DecisionContext,
        *,
        outcome_code: str,
        reason_code: str,
        digest: str,
        missing_evidence: tuple[str, ...],
        blocking_evidence: tuple[str, ...],
    ) -> DecisionResult:
        return self._build(
            context,
            outcome_code=outcome_code,
            reason_code=reason_code,
            binding=None,
            digest=digest,
            missing_evidence=missing_evidence,
            blocking_evidence=blocking_evidence,
        )

    def _ambiguous(
        self,
        context: DecisionContext,
        tied: tuple[RuleBinding, ...],
        digest: str,
        missing_evidence: tuple[str, ...],
        blocking_evidence: tuple[str, ...],
    ) -> DecisionResult:
        rule_ids = tuple(sorted(b.rule_id for b in tied))
        if self._policy.conflict_policy is ConflictPolicy.RAISE:
            raise ConflictingDecisionMatch(
                context.request.decision_type, tied[0].precedence, rule_ids
            )
        # D.4B default: a governance ambiguity is a governed situation the KB
        # failed to resolve, so it is a business outcome. The executor must not
        # silently pick one of the tied rules.
        return self._synthetic(
            context,
            outcome_code=self._policy.cannot_decide_outcome,
            reason_code=self._policy.ambiguity_reason,
            digest=digest,
            missing_evidence=missing_evidence,
            blocking_evidence=tuple(sorted(set(blocking_evidence) | set(rule_ids))),
        )
