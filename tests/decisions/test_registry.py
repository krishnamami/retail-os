"""D. duplicate registration rejected, E. missing predicate fails explicitly."""

from __future__ import annotations

import pytest
from d4c_support import KB, TYPE_A, TYPE_B, always_match, never_match

from decisions import (
    DuplicatePredicateRegistration,
    MissingPredicate,
    PredicateRegistry,
)


# -- D. duplicate registration -------------------------------------------

def test_duplicate_registration_rejected(registry):
    registry.register(TYPE_A, "TEST-GUARD-001", KB, always_match)
    with pytest.raises(DuplicatePredicateRegistration, match="already registered"):
        registry.register(TYPE_A, "TEST-GUARD-001", KB, never_match)


def test_duplicate_rejection_is_not_last_wins(registry):
    registry.register(TYPE_A, "R", KB, always_match)
    with pytest.raises(DuplicatePredicateRegistration):
        registry.register(TYPE_A, "R", KB, never_match)
    assert registry.resolve(TYPE_A, "R", KB) is always_match


def test_same_rule_id_different_decision_type_is_allowed(registry):
    registry.register(TYPE_A, "IR-011", KB, always_match)
    registry.register(TYPE_B, "IR-011", KB, never_match)
    assert registry.resolve(TYPE_A, "IR-011", KB) is always_match
    assert registry.resolve(TYPE_B, "IR-011", KB) is never_match


def test_same_rule_id_different_kb_version_is_allowed(registry):
    """D.4A: IR-001 is a different rule at kb 1.0 than at kb 1.0.1."""
    registry.register(TYPE_A, "IR-001", "1.0", always_match)
    registry.register(TYPE_A, "IR-001", "1.0.1", never_match)
    assert registry.resolve(TYPE_A, "IR-001", "1.0") is always_match
    assert registry.resolve(TYPE_A, "IR-001", "1.0.1") is never_match


# -- E. missing predicate -------------------------------------------------

def test_missing_predicate_raises_explicitly(registry):
    with pytest.raises(MissingPredicate, match="no predicate registered"):
        registry.resolve(TYPE_A, "TEST-MATCH-404", KB)


def test_missing_predicate_names_the_governed_identity(registry):
    with pytest.raises(MissingPredicate) as excinfo:
        registry.resolve(TYPE_A, "TEST-MATCH-404", "9.9")
    message = str(excinfo.value)
    assert TYPE_A in message and "TEST-MATCH-404" in message and "9.9" in message


def test_wrong_kb_version_is_missing_not_fallback(registry):
    registry.register(TYPE_A, "R", "1.0.1", always_match)
    with pytest.raises(MissingPredicate):
        registry.resolve(TYPE_A, "R", "2.0.0")


def test_missing_for_reports_all_gaps(registry):
    from d4c_support import make_rule
    from decisions import RuleClass

    registry.register(TYPE_A, "R1", KB, always_match)
    bindings = (
        make_rule("R1", RuleClass.MATCH, 10, "OUT"),
        make_rule("R2", RuleClass.MATCH, 20, "OUT"),
        make_rule("R3", RuleClass.GUARD, 10, "OUT"),
    )
    assert registry.missing_for(bindings) == (
        (TYPE_A, "R2", KB),
        (TYPE_A, "R3", KB),
    )


# -- registration validation ----------------------------------------------

@pytest.mark.parametrize("bad", ["", "  ", None, 7])
def test_register_rejects_bad_identifiers(registry, bad):
    with pytest.raises(MissingPredicate):
        registry.register(bad, "R", KB, always_match)
    with pytest.raises(MissingPredicate):
        registry.register(TYPE_A, bad, KB, always_match)
    with pytest.raises(MissingPredicate):
        registry.register(TYPE_A, "R", bad, always_match)


def test_register_rejects_non_callable(registry):
    with pytest.raises(MissingPredicate, match="not callable"):
        registry.register(TYPE_A, "R", KB, "not-a-function")


# -- introspection ---------------------------------------------------------

def test_registry_iteration_is_sorted_and_stable():
    a, b = PredicateRegistry(), PredicateRegistry()
    a.register(TYPE_B, "Z", KB, always_match)
    a.register(TYPE_A, "B", KB, always_match)
    a.register(TYPE_A, "A", KB, always_match)
    # same content, opposite registration order
    b.register(TYPE_A, "A", KB, always_match)
    b.register(TYPE_A, "B", KB, always_match)
    b.register(TYPE_B, "Z", KB, always_match)
    assert a.keys() == b.keys()
    assert list(a.keys()) == sorted(a.keys())


def test_registry_len_and_contains(registry):
    registry.register(TYPE_A, "R", KB, always_match)
    assert len(registry) == 1
    assert (TYPE_A, "R", KB) in registry
    assert (TYPE_A, "R", "9.9") not in registry
