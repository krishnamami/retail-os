"""Rule classification, governed rule metadata, and deterministic ordering.

Separation held here (D.4B section 6):

    RuleDefinition  -- governed SEMANTIC metadata. Mirrors what the KB owns:
                       identity, class, precedence, and the outcome/reason the
                       rule sanctions. Contains no executable logic.
    RuleBinding     -- RuleDefinition + a predicate reference. The runtime
                       binding between governed metadata and executable code.

The executor reads RuleBinding. It never reads a condition string, and there
is no code path that interprets prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidRuleDefinition

__all__ = ["RuleClass", "RuleDefinition", "RuleBinding", "order_bindings"]


class RuleClass(Enum):
    """Generic rule classification.

    D.4C keeps rule_class as runtime/domain registration metadata. It is
    deliberately NOT a claris_kb.decision_rules column yet -- the concept is
    validated across multiple decision types before promotion into governed
    KB metadata (open decision V-1).
    """

    GUARD = "GUARD"
    MATCH = "MATCH"
    FALLBACK = "FALLBACK"

    @property
    def evaluation_order(self) -> int:
        return _CLASS_ORDER[self]


_CLASS_ORDER = {RuleClass.GUARD: 0, RuleClass.MATCH: 1, RuleClass.FALLBACK: 2}


@dataclass(frozen=True)
class RuleDefinition:
    """Governed semantic metadata for one rule. Immutable."""

    decision_type: str
    rule_id: str
    kb_version: str
    rule_class: RuleClass
    precedence: int
    outcome_code: str
    reason_code: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("decision_type", "rule_id", "kb_version", "outcome_code"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidRuleDefinition(
                    f"RuleDefinition.{field_name} must be a non-empty string, got {value!r}"
                )
        if not isinstance(self.rule_class, RuleClass):
            raise InvalidRuleDefinition(
                f"RuleDefinition.rule_class must be a RuleClass, got {self.rule_class!r}"
            )
        if not isinstance(self.precedence, int) or isinstance(self.precedence, bool):
            raise InvalidRuleDefinition(
                f"RuleDefinition.precedence must be an int, got {self.precedence!r}"
            )
        if self.reason_code is not None and (
            not isinstance(self.reason_code, str) or not self.reason_code.strip()
        ):
            raise InvalidRuleDefinition(
                f"RuleDefinition.reason_code must be a non-empty string or None, "
                f"got {self.reason_code!r}"
            )

    @property
    def key(self) -> tuple[str, str, str]:
        """Governed identity: (decision_type, rule_id, kb_version).

        kb_version is part of the key, not decoration. D.4A established that
        rule_id is NOT unique across KB versions -- IR-001 is
        'new_product_family' at kb 1.0.1 and 'primary_user_identifier' at
        kb 1.0. A two-part key would silently bind the wrong predicate.
        """
        return (self.decision_type, self.rule_id, self.kb_version)


@dataclass(frozen=True)
class RuleBinding:
    """A governed rule bound to an executable predicate reference. Immutable."""

    definition: RuleDefinition
    predicate_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.definition, RuleDefinition):
            raise InvalidRuleDefinition(
                f"RuleBinding.definition must be a RuleDefinition, got {self.definition!r}"
            )
        if not isinstance(self.predicate_ref, str) or not self.predicate_ref.strip():
            raise InvalidRuleDefinition(
                f"RuleBinding.predicate_ref must be a non-empty string, "
                f"got {self.predicate_ref!r}"
            )

    # convenience passthroughs -- read-only
    @property
    def decision_type(self) -> str:
        return self.definition.decision_type

    @property
    def rule_id(self) -> str:
        return self.definition.rule_id

    @property
    def kb_version(self) -> str:
        return self.definition.kb_version

    @property
    def rule_class(self) -> RuleClass:
        return self.definition.rule_class

    @property
    def precedence(self) -> int:
        return self.definition.precedence


def _sort_key(binding: RuleBinding) -> tuple[int, int, str]:
    return (
        binding.rule_class.evaluation_order,
        binding.precedence,
        binding.rule_id,
    )


def order_bindings(bindings: tuple[RuleBinding, ...]) -> tuple[RuleBinding, ...]:
    """Total, deterministic ordering over rule bindings.

    ORDERING CONTRACT
    -----------------
    1. rule_class:  GUARD (0) before MATCH (1) before FALLBACK (2).
       Class dominates precedence absolutely. A GUARD at precedence 99 is
       still evaluated before a MATCH at precedence 1.
    2. precedence:  lower number first, within a class.
    3. rule_id:     ascending string comparison, as a total tie-break.

    The result depends ONLY on these three governed values. It is independent
    of registration order, database row order, dict insertion order, and
    filesystem order. Two callers supplying the same bindings in different
    sequences obtain byte-identical ordering.
    """
    return tuple(sorted(bindings, key=_sort_key))
