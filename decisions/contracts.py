"""Immutable contracts for the generic governed decision executor.

Nothing in this module knows about Claris, SAP, SKUs, product_reference,
geography, term_months, customer_segment, or canonical identity. Fold property
names are opaque strings; domain facts are an opaque mapping.

Fold governed states are PRESERVED here, never interpreted. The executor
carries ESTABLISHED / UNREPORTED / EXPLICITLY_UNDEFINED / CONTRADICTED /
INVALID through to the result. What any of them MEANS for a business decision
is a domain predicate's judgement, not the platform's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .errors import InvalidDecisionContext, InvalidDecisionRequest
from .rules import RuleBinding

__all__ = [
    "FoldState",
    "FoldProperty",
    "FoldSnapshotView",
    "FactValue",
    "Known",
    "Unavailable",
    "DomainFacts",
    "GovernanceBinding",
    "ExecutionMetadata",
    "DecisionRequest",
    "DecisionContext",
    "PredicateVerdict",
    "PredicateResult",
    "ExecutionStatus",
    "DecisionResult",
    "MATCHED",
    "NOT_MATCHED",
    "NOT_APPLICABLE",
]


# ======================================================================
# Fold-derived governed state
# ======================================================================

class FoldState(Enum):
    """Governed state vocabulary, mirroring public.claris_config_state_type.

    The generic executor assigns NO business meaning to these values. It
    preserves them and reports them. Predicates decide what they imply.
    """

    ESTABLISHED = "ESTABLISHED"
    UNREPORTED = "UNREPORTED"
    EXPLICITLY_UNDEFINED = "EXPLICITLY_UNDEFINED"
    CONTRADICTED = "CONTRADICTED"
    INVALID = "INVALID"

    @classmethod
    def parse(cls, raw: str) -> "FoldState":
        try:
            return cls(raw)
        except ValueError as exc:
            raise InvalidDecisionContext(
                f"unknown fold_state {raw!r}; permitted: "
                f"{', '.join(m.value for m in cls)}"
            ) from exc


@dataclass(frozen=True)
class FoldProperty:
    """One folded property, with its lineage intact.

    Mirrors an element of state.fold_state_snapshot.folded_properties. Lineage
    is NEVER flattened away: basis_assertion_ids, effective_at and
    latest_known_arrival_at travel with the value all the way to the result.
    """

    property_name: str
    resolved_value: Any
    property_value_type: str | None
    fold_state: FoldState
    effective_at: datetime | None = None
    latest_known_arrival_at: datetime | None = None
    basis_assertion_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.property_name, str) or not self.property_name.strip():
            raise InvalidDecisionContext(
                f"FoldProperty.property_name must be a non-empty string, "
                f"got {self.property_name!r}"
            )
        if not isinstance(self.fold_state, FoldState):
            raise InvalidDecisionContext(
                f"FoldProperty.fold_state must be a FoldState, got {self.fold_state!r}"
            )
        if not isinstance(self.basis_assertion_ids, tuple):
            raise InvalidDecisionContext(
                "FoldProperty.basis_assertion_ids must be a tuple (immutability), "
                f"got {type(self.basis_assertion_ids).__name__}"
            )
        for ts_name in ("effective_at", "latest_known_arrival_at"):
            ts = getattr(self, ts_name)
            if ts is not None:
                if not isinstance(ts, datetime):
                    raise InvalidDecisionContext(
                        f"FoldProperty.{ts_name} must be a datetime or None, got {ts!r}"
                    )
                if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
                    raise InvalidDecisionContext(
                        f"FoldProperty.{ts_name} must be timezone-aware"
                    )


@dataclass(frozen=True)
class FoldSnapshotView:
    """One Fold snapshot for one subject at one decision horizon."""

    fold_state_id: str
    subject_type: str
    subject_id: str
    decision_horizon: datetime
    fold_status: FoldState
    kb_version: str
    policy_version: str
    properties: Mapping[str, FoldProperty] = field(default_factory=dict)
    fold_computed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.fold_status, FoldState):
            raise InvalidDecisionContext(
                f"FoldSnapshotView.fold_status must be a FoldState, got {self.fold_status!r}"
            )
        if self.decision_horizon.tzinfo is None:
            raise InvalidDecisionContext(
                "FoldSnapshotView.decision_horizon must be timezone-aware"
            )
        for name, prop in self.properties.items():
            if not isinstance(prop, FoldProperty):
                raise InvalidDecisionContext(
                    f"properties[{name!r}] must be a FoldProperty, got {prop!r}"
                )
            if prop.property_name != name:
                raise InvalidDecisionContext(
                    f"properties key {name!r} disagrees with "
                    f"FoldProperty.property_name {prop.property_name!r}"
                )
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))

    def property_named(self, name: str) -> FoldProperty | None:
        return self.properties.get(name)

    def state_of(self, name: str) -> FoldState | None:
        prop = self.properties.get(name)
        return prop.fold_state if prop is not None else None


# ======================================================================
# Domain facts (opaque to the platform)
# ======================================================================

@dataclass(frozen=True)
class FactValue:
    """Base for a domain fact value."""


@dataclass(frozen=True)
class Known(FactValue):
    value: Any


@dataclass(frozen=True)
class Unavailable(FactValue):
    """A fact that could not be computed, and why.

    Required for digest correctness, not convenience: without an explicit
    marker the digest would differ depending on which guard fired, and replay
    would break.
    """

    reason: str


@dataclass(frozen=True)
class DomainFacts:
    """Namespaced facts supplied by a domain adapter. Opaque to the executor.

    The platform never inspects a fact name or value. It carries them into the
    digest and the result.
    """

    facts: Mapping[str, FactValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in self.facts.items():
            if not isinstance(value, FactValue):
                raise InvalidDecisionContext(
                    f"domain fact {name!r} must be Known(...) or Unavailable(...), "
                    f"got {value!r}"
                )
        object.__setattr__(self, "facts", MappingProxyType(dict(self.facts)))

    def get(self, name: str) -> FactValue | None:
        return self.facts.get(name)

    def value_of(self, name: str, default: Any = None) -> Any:
        fact = self.facts.get(name)
        return fact.value if isinstance(fact, Known) else default


# ======================================================================
# Governance and execution metadata
# ======================================================================

#: Governance basis -- D.4G.1G.5P / G.5P.1.
#:
#: A prototype assumption is not a weaker confirmation, it is a different
#: basis. The value travels with the governance into the result, so a decision
#: record can never claim a basis its governance did not have. Production
#: execution requires AUTHORITATIVE; there is no fallback from it to prototype.
GOVERNANCE_BASIS_AUTHORITATIVE = "AUTHORITATIVE"
GOVERNANCE_BASIS_PROTOTYPE = "PROTOTYPE_ASSUMPTION"
GOVERNANCE_BASES = frozenset(
    {GOVERNANCE_BASIS_AUTHORITATIVE, GOVERNANCE_BASIS_PROTOTYPE}
)


@dataclass(frozen=True)
class GovernanceBinding:
    """Resolved governance versions and the executable rule set.

    ontology_version, kb_version and policy_version are carried INDEPENDENTLY.
    They are not assumed to move together (D.4B section G).

    POLICY VERSION NULLABILITY -- D.4E controlled compatibility correction
    ---------------------------------------------------------------------
    `policy_version` is Optional. None means exactly one thing:

        no applicable policy version is present in the governed metadata.

    It does NOT mean "unknown", and it does NOT mean "the lookup failed". A
    governance lookup that fails or cannot be resolved raises an adapter error
    (NoActiveKB, KBVersionNotFound, NoExecutableRuleSet,
    GovernanceVersionAmbiguity) and no GovernanceBinding is constructed at all,
    so a system failure can never arrive here disguised as a governed None.

    An empty or whitespace-only string is normalized to None at construction.
    Governed storage spells "absent" as SQL NULL and the KB adapter maps a
    missing column to '', and two spellings of one governed fact must not
    produce two different input_digest values.

    ontology_version and kb_version are unchanged: mandatory, non-empty.

    Why this is not a silent weakening: D.4D established that all 13 executable
    CHANGE_CLASSIFICATION rules carry an empty policy_version, which is
    legitimate governed metadata. Rejecting it made the live governed path
    unusable while inviting a fabricated "1.0" / "default" / "NONE" -- a
    governance value nobody governs. Optional[str] records the absence
    truthfully instead.
    """

    ontology_version: str
    kb_version: str
    policy_version: str | None
    rule_set: tuple[RuleBinding, ...] = ()
    rule_set_digest: str = ""
    required_properties: tuple[str, ...] = ()
    excluded_rules: tuple[tuple[str, str], ...] = ()
    governance_basis: str = GOVERNANCE_BASIS_AUTHORITATIVE

    def __post_init__(self) -> None:
        if self.governance_basis not in GOVERNANCE_BASES:
            raise InvalidDecisionContext(
                "governance_basis must be one of %s; got %r"
                % (sorted(GOVERNANCE_BASES), self.governance_basis)
            )
        for field_name in ("ontology_version", "kb_version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidDecisionContext(
                    f"GovernanceBinding.{field_name} must be a non-empty string, "
                    f"got {value!r}"
                )
        if self.policy_version is not None:
            if not isinstance(self.policy_version, str):
                raise InvalidDecisionContext(
                    "GovernanceBinding.policy_version must be a string or None "
                    "(None = no applicable governed policy version), got "
                    f"{self.policy_version!r}"
                )
            if not self.policy_version.strip():
                object.__setattr__(self, "policy_version", None)
        if not isinstance(self.rule_set, tuple):
            raise InvalidDecisionContext("GovernanceBinding.rule_set must be a tuple")
        for binding in self.rule_set:
            if not isinstance(binding, RuleBinding):
                raise InvalidDecisionContext(
                    f"rule_set entries must be RuleBinding, got {binding!r}"
                )
        if not isinstance(self.required_properties, tuple):
            raise InvalidDecisionContext(
                "GovernanceBinding.required_properties must be a tuple"
            )


@dataclass(frozen=True)
class ExecutionMetadata:
    """Executor-owned metadata. evaluated_at is excluded from input_digest."""

    executor_version: str = "d4c/1.0"
    digest_scheme_version: str = "v1"
    evaluated_at: datetime | None = None


# ======================================================================
# Request
# ======================================================================

@dataclass(frozen=True)
class DecisionRequest:
    """What to decide about. Never what was decided.

    A caller cannot supply outcome_code, reason_code or matched_rule_id --
    they are not fields, so passing them raises TypeError at construction.
    Those are executor outputs.
    """

    decision_type: str
    subject_type: str
    subject_id: str
    decision_horizon: datetime
    requested_by: str | None = None
    correlation_id: str | None = None
    requested_at: datetime | None = None
    requested_kb_version: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("decision_type", "subject_type", "subject_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidDecisionRequest(
                    f"DecisionRequest.{field_name} must be a non-empty string, "
                    f"got {value!r}"
                )
        if not isinstance(self.decision_horizon, datetime):
            raise InvalidDecisionRequest(
                f"DecisionRequest.decision_horizon must be a datetime, "
                f"got {self.decision_horizon!r}"
            )
        if (
            self.decision_horizon.tzinfo is None
            or self.decision_horizon.tzinfo.utcoffset(self.decision_horizon) is None
        ):
            raise InvalidDecisionRequest(
                "DecisionRequest.decision_horizon must be timezone-aware; a naive "
                "datetime cannot identify a Fold snapshot unambiguously"
            )
        if self.requested_at is not None:
            if not isinstance(self.requested_at, datetime):
                raise InvalidDecisionRequest(
                    f"DecisionRequest.requested_at must be a datetime or None, "
                    f"got {self.requested_at!r}"
                )
            if self.requested_at.tzinfo is None:
                raise InvalidDecisionRequest(
                    "DecisionRequest.requested_at must be timezone-aware"
                )


# ======================================================================
# Context
# ======================================================================

@dataclass(frozen=True)
class DecisionContext:
    """Everything a predicate may see. Immutable, and the sole predicate input.

    Four clearly separated segments (D.4B section E):
        request     -- what was asked
        fold        -- Fold-derived governed state, lineage intact
        facts       -- domain lookup facts, opaque to the platform
        governance  -- resolved versions and executable rule set
        execution   -- executor-owned metadata
    """

    request: DecisionRequest
    fold: FoldSnapshotView
    governance: GovernanceBinding
    facts: DomainFacts = field(default_factory=DomainFacts)
    execution: ExecutionMetadata = field(default_factory=ExecutionMetadata)

    def __post_init__(self) -> None:
        if not isinstance(self.request, DecisionRequest):
            raise InvalidDecisionContext("DecisionContext.request must be a DecisionRequest")
        if not isinstance(self.fold, FoldSnapshotView):
            raise InvalidDecisionContext("DecisionContext.fold must be a FoldSnapshotView")
        if not isinstance(self.governance, GovernanceBinding):
            raise InvalidDecisionContext(
                "DecisionContext.governance must be a GovernanceBinding"
            )
        if self.fold.subject_type != self.request.subject_type:
            raise InvalidDecisionContext(
                f"context subject_type mismatch: request={self.request.subject_type!r} "
                f"fold={self.fold.subject_type!r}"
            )
        if self.fold.subject_id != self.request.subject_id:
            raise InvalidDecisionContext(
                f"context subject_id mismatch: request={self.request.subject_id!r} "
                f"fold={self.fold.subject_id!r}"
            )
        if self.fold.decision_horizon != self.request.decision_horizon:
            raise InvalidDecisionContext(
                "context decision_horizon mismatch between request and Fold snapshot"
            )

    # -- read-only convenience for predicates ---------------------------
    def property_named(self, name: str) -> FoldProperty | None:
        return self.fold.property_named(name)

    def state_of(self, name: str) -> FoldState | None:
        return self.fold.state_of(name)

    def fact(self, name: str) -> FactValue | None:
        return self.facts.get(name)


# ======================================================================
# Predicate result
# ======================================================================

class PredicateVerdict(Enum):
    """Ordinary predicate outcomes. Never signalled by exception."""

    MATCHED = "MATCHED"
    NOT_MATCHED = "NOT_MATCHED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class PredicateResult:
    """A predicate's answer: does this rule apply, plus optional audit detail.

    A predicate NEVER returns outcome_code, reason_code, evidence or
    confidence. The KB owns outcomes; the executor owns evidence.
    """

    verdict: PredicateVerdict
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, PredicateVerdict):
            raise InvalidDecisionContext(
                f"PredicateResult.verdict must be a PredicateVerdict, got {self.verdict!r}"
            )
        object.__setattr__(self, "detail", MappingProxyType(dict(self.detail)))

    @property
    def matched(self) -> bool:
        return self.verdict is PredicateVerdict.MATCHED


MATCHED = PredicateResult(PredicateVerdict.MATCHED)
NOT_MATCHED = PredicateResult(PredicateVerdict.NOT_MATCHED)
NOT_APPLICABLE = PredicateResult(PredicateVerdict.NOT_APPLICABLE)


# ======================================================================
# Result
# ======================================================================

class ExecutionStatus(Enum):
    DECIDED = "DECIDED"


@dataclass(frozen=True)
class DecisionResult:
    """The in-memory governed result. Carries no persistence responsibility.

    decided_by and decided_at are deliberately ABSENT: they describe the act of
    recording, are set by the DecisionWriter in a later phase, and would put
    non-deterministic values inside a replayable object.
    """

    decision_type: str
    subject_type: str
    subject_id: str
    horizon_as_of: datetime
    outcome_code: str
    reason_code: str | None
    ontology_version: str
    kb_version: str
    policy_version: str | None
    input_digest: str
    matched_rule_id: str | None
    matched_rule_kb_version: str | None
    matched_rule_class: str | None
    missing_evidence: tuple[str, ...]
    blocking_evidence: tuple[str, ...]
    confidence_level: str
    fold_state_id: str
    fold_lineage: tuple[tuple[str, str, tuple[str, ...]], ...]
    domain_facts_used: tuple[tuple[str, str], ...]
    excluded_rules: tuple[tuple[str, str], ...]
    execution_status: ExecutionStatus
    executor_version: str
    digest_scheme_version: str
    #: Which governance the outcome rests on. PROTOTYPE_ASSUMPTION means an
    #: engineering assumption awaiting validation with Claris, never a
    #: confirmed business policy.
    governance_basis: str = GOVERNANCE_BASIS_AUTHORITATIVE
