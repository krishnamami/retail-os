"""Predicate registry: governed identity -> executable predicate.

Dispatch is a dictionary lookup on governed identity. There is no switch
statement, no if/elif chain on decision_type, and no dynamic code execution.

The registry is an OBJECT, injected into the executor. It is deliberately not
a module-level global: a global would make domain packs order-dependent at
import time and would leak between tests.
"""

from __future__ import annotations

from typing import Callable, Iterator, Mapping

from .contracts import DecisionContext, PredicateResult
from .errors import DuplicatePredicateRegistration, MissingPredicate
from .rules import RuleBinding

__all__ = ["Predicate", "PredicateRegistry"]

Predicate = Callable[[DecisionContext], PredicateResult]

_Key = tuple[str, str, str]  # (decision_type, rule_id, kb_version)


class PredicateRegistry:
    """Keyed by (decision_type, rule_id, kb_version).

    kb_version is part of the key because D.4A established that rule_id is NOT
    unique across KB versions: IR-001 is 'new_product_family' at kb 1.0.1 and
    'primary_user_identifier' at kb 1.0. Keying on (decision_type, rule_id)
    alone would silently bind the wrong predicate.

    Different decision types may safely reuse the same rule_id -- the
    decision_type is the first key element.
    """

    __slots__ = ("_predicates",)

    def __init__(self) -> None:
        self._predicates: dict[_Key, Predicate] = {}

    # -- registration ---------------------------------------------------

    def register(
        self,
        decision_type: str,
        rule_id: str,
        kb_version: str,
        predicate: Predicate,
    ) -> None:
        """Bind a predicate to one governed rule identity.

        Duplicate registration raises. Never last-wins: silently overwriting
        would rebind a governed rule to different logic with no signal.
        """
        for name, value in (
            ("decision_type", decision_type),
            ("rule_id", rule_id),
            ("kb_version", kb_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise MissingPredicate(
                    f"register(): {name} must be a non-empty string, got {value!r}"
                )
        if not callable(predicate):
            raise MissingPredicate(
                f"register(): predicate for {decision_type}/{rule_id} is not callable"
            )

        key: _Key = (decision_type, rule_id, kb_version)
        if key in self._predicates:
            raise DuplicatePredicateRegistration(
                f"predicate already registered for decision_type={decision_type!r} "
                f"rule_id={rule_id!r} kb_version={kb_version!r}"
            )
        self._predicates[key] = predicate

    # -- resolution -----------------------------------------------------

    def resolve(self, decision_type: str, rule_id: str, kb_version: str) -> Predicate:
        """Return the exact registered predicate, or fail explicitly.

        Never returns a no-op placeholder and never silently skips: an active
        governed rule without an implementation must stop execution, or the
        executor could return an outcome the KB does not sanction.
        """
        key: _Key = (decision_type, rule_id, kb_version)
        try:
            return self._predicates[key]
        except KeyError:
            raise MissingPredicate(
                f"no predicate registered for decision_type={decision_type!r} "
                f"rule_id={rule_id!r} kb_version={kb_version!r}"
            ) from None

    def resolve_binding(self, binding: RuleBinding) -> Predicate:
        return self.resolve(binding.decision_type, binding.rule_id, binding.kb_version)

    # -- introspection --------------------------------------------------

    def __contains__(self, key: object) -> bool:
        return key in self._predicates

    def __len__(self) -> int:
        return len(self._predicates)

    def __iter__(self) -> Iterator[_Key]:
        return iter(sorted(self._predicates))

    def keys(self) -> tuple[_Key, ...]:
        return tuple(sorted(self._predicates))

    def missing_for(self, bindings: tuple[RuleBinding, ...]) -> tuple[_Key, ...]:
        """Governed identities in `bindings` with no registered predicate."""
        return tuple(
            sorted(
                (b.decision_type, b.rule_id, b.kb_version)
                for b in bindings
                if (b.decision_type, b.rule_id, b.kb_version) not in self._predicates
            )
        )

    def as_mapping(self) -> Mapping[_Key, Predicate]:
        return dict(self._predicates)
