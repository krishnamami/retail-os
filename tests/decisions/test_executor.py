"""F-Q: guard/match/fallback semantics, ordering, evidence, failure model."""

from __future__ import annotations

import pytest
from d4c_support import (
    KB,
    TYPE_A,
    always_match,
    make_context,
    make_executor,
    make_property,
    make_rule,
    match_when_flag,
    never_match,
)

from decisions import (
    ConflictingDecisionMatch,
    ConflictPolicy,
    EmptyRuleSet,
    ExecutionStatus,
    ExecutorPolicy,
    FoldState,
    GovernedDecisionExecutor,
    InvalidDecisionContext,
    MissingPredicate,
    MultipleFallbackRules,
    PredicateExecutionError,
    PredicateRegistry,
    RuleClass,
    order_bindings,
)


# ======================================================================
# F / G / H -- guard precedes match; matched guard terminates
# ======================================================================

def test_guard_evaluated_before_match_despite_worse_precedence():
    """A GUARD at precedence 99 still beats a MATCH at precedence 1."""
    guard = make_rule("TEST-GUARD-001", RuleClass.GUARD, 99, "CANNOT_DECIDE", "GUARD_FIRED")
    match = make_rule("TEST-MATCH-001", RuleClass.MATCH, 1, "MATCH_OUTCOME", "MATCHED")
    ex = make_executor(
        (TYPE_A, "TEST-GUARD-001", KB, always_match),
        (TYPE_A, "TEST-MATCH-001", KB, always_match),
    )
    result = ex.execute(make_context(rule_set=(match, guard)))
    assert result.matched_rule_id == "TEST-GUARD-001"
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.matched_rule_class == "GUARD"


def test_matched_guard_prevents_match_evaluation():
    calls = []

    def recording_match(context):
        calls.append("match ran")
        return always_match(context)

    ex = make_executor(
        (TYPE_A, "TEST-GUARD-001", KB, always_match),
        (TYPE_A, "TEST-MATCH-001", KB, recording_match),
    )
    ex.execute(
        make_context(
            rule_set=(
                make_rule("TEST-GUARD-001", RuleClass.GUARD, 10, "CANNOT_DECIDE"),
                make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "MATCH_OUTCOME"),
            )
        )
    )
    assert calls == [], "a matched GUARD must terminate evaluation"


def test_unmatched_guard_allows_match_evaluation():
    ex = make_executor(
        (TYPE_A, "TEST-GUARD-001", KB, never_match),
        (TYPE_A, "TEST-MATCH-001", KB, always_match),
    )
    result = ex.execute(
        make_context(
            rule_set=(
                make_rule("TEST-GUARD-001", RuleClass.GUARD, 10, "CANNOT_DECIDE"),
                make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "MATCH_OUTCOME", "OK"),
            )
        )
    )
    assert result.matched_rule_id == "TEST-MATCH-001"
    assert result.outcome_code == "MATCH_OUTCOME"


# ======================================================================
# I / J / K -- precedence and tie-break ordering
# ======================================================================

def test_precedence_ordering_within_guards():
    ex = make_executor(
        (TYPE_A, "TEST-GUARD-LOW", KB, always_match),
        (TYPE_A, "TEST-GUARD-HIGH", KB, always_match),
    )
    result = ex.execute(
        make_context(
            rule_set=(
                make_rule("TEST-GUARD-HIGH", RuleClass.GUARD, 20, "OUT_20"),
                make_rule("TEST-GUARD-LOW", RuleClass.GUARD, 10, "OUT_10"),
            )
        )
    )
    assert result.matched_rule_id == "TEST-GUARD-LOW"
    assert result.outcome_code == "OUT_10"


def test_precedence_ordering_within_matches():
    ex = make_executor(
        (TYPE_A, "TEST-MATCH-A", KB, always_match),
        (TYPE_A, "TEST-MATCH-B", KB, always_match),
    )
    result = ex.execute(
        make_context(
            rule_set=(
                make_rule("TEST-MATCH-B", RuleClass.MATCH, 50, "OUT_50"),
                make_rule("TEST-MATCH-A", RuleClass.MATCH, 5, "OUT_5"),
            )
        )
    )
    assert result.outcome_code == "OUT_5"


def test_rule_id_tiebreak_is_deterministic():
    """Same class, same precedence, only one matching -> rule_id orders them."""
    ex = make_executor(
        (TYPE_A, "TEST-GUARD-AAA", KB, never_match),
        (TYPE_A, "TEST-GUARD-BBB", KB, always_match),
    )
    ordered = order_bindings(
        (
            make_rule("TEST-GUARD-BBB", RuleClass.GUARD, 10, "OUT_B"),
            make_rule("TEST-GUARD-AAA", RuleClass.GUARD, 10, "OUT_A"),
        )
    )
    assert [b.rule_id for b in ordered] == ["TEST-GUARD-AAA", "TEST-GUARD-BBB"]


def test_ordering_contract_class_dominates_precedence():
    ordered = order_bindings(
        (
            make_rule("F", RuleClass.FALLBACK, 1, "OUT"),
            make_rule("M", RuleClass.MATCH, 1, "OUT"),
            make_rule("G", RuleClass.GUARD, 99, "OUT"),
        )
    )
    assert [b.rule_id for b in ordered] == ["G", "M", "F"]


# -- T. ordering independent of input ordering ---------------------------

def test_ordering_independent_of_input_sequence():
    import itertools

    rules = (
        make_rule("G2", RuleClass.GUARD, 20, "OUT"),
        make_rule("G1", RuleClass.GUARD, 10, "OUT"),
        make_rule("M2", RuleClass.MATCH, 20, "OUT"),
        make_rule("M1", RuleClass.MATCH, 10, "OUT"),
        make_rule("F1", RuleClass.FALLBACK, 99, "OUT"),
    )
    expected = [b.rule_id for b in order_bindings(rules)]
    for permutation in itertools.permutations(rules):
        assert [b.rule_id for b in order_bindings(permutation)] == expected
    assert expected == ["G1", "G2", "M1", "M2", "F1"]


def test_result_independent_of_registration_order():
    def build(order):
        registry = PredicateRegistry()
        for rule_id in order:
            registry.register(TYPE_A, rule_id, KB, always_match)
        return GovernedDecisionExecutor(registry)

    rule_set = (
        make_rule("TEST-MATCH-B", RuleClass.MATCH, 10, "OUT_B"),
        make_rule("TEST-MATCH-A", RuleClass.MATCH, 10, "OUT_A"),
    )
    forward = build(["TEST-MATCH-A", "TEST-MATCH-B"])
    reverse = build(["TEST-MATCH-B", "TEST-MATCH-A"])
    policy = ExecutorPolicy(conflict_policy=ConflictPolicy.RAISE)
    # both matched at the same precedence -> both must detect the same conflict
    for ex in (forward, reverse):
        engine = GovernedDecisionExecutor(ex._registry, policy=policy)
        with pytest.raises(ConflictingDecisionMatch) as exc:
            engine.execute(make_context(rule_set=rule_set))
        assert exc.value.rule_ids == ("TEST-MATCH-A", "TEST-MATCH-B")


# ======================================================================
# L / M / N -- fallback semantics
# ======================================================================

def test_fallback_runs_only_after_guards_and_matches_fail():
    ex = make_executor(
        (TYPE_A, "TEST-GUARD-001", KB, never_match),
        (TYPE_A, "TEST-MATCH-001", KB, never_match),
        (TYPE_A, "TEST-FALLBACK-001", KB, always_match),
    )
    result = ex.execute(
        make_context(
            rule_set=(
                make_rule("TEST-GUARD-001", RuleClass.GUARD, 10, "G_OUT"),
                make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "M_OUT"),
                make_rule("TEST-FALLBACK-001", RuleClass.FALLBACK, 99,
                          "CANNOT_DECIDE", "GOVERNANCE_REQUIRED"),
            )
        )
    )
    assert result.matched_rule_id == "TEST-FALLBACK-001"
    assert result.reason_code == "GOVERNANCE_REQUIRED"


def test_no_fallback_yields_cannot_decide_no_rule_matched():
    """D.4B section C locks this as a BUSINESS outcome, not an error."""
    ex = make_executor((TYPE_A, "TEST-MATCH-001", KB, never_match))
    result = ex.execute(
        make_context(rule_set=(make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "M"),))
    )
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "NO_RULE_MATCHED"
    assert result.matched_rule_id is None
    assert result.execution_status is ExecutionStatus.DECIDED


def test_multiple_fallbacks_fail_closed():
    ex = make_executor(
        (TYPE_A, "F1", KB, always_match),
        (TYPE_A, "F2", KB, always_match),
    )
    with pytest.raises(MultipleFallbackRules, match="at most one"):
        ex.execute(
            make_context(
                rule_set=(
                    make_rule("F1", RuleClass.FALLBACK, 98, "OUT"),
                    make_rule("F2", RuleClass.FALLBACK, 99, "OUT"),
                )
            )
        )


# ======================================================================
# same-precedence MATCH conflict (D.4B V-3)
# ======================================================================

def test_same_precedence_conflict_default_is_business_cannot_decide():
    ex = make_executor(
        (TYPE_A, "TEST-MATCH-A", KB, always_match),
        (TYPE_A, "TEST-MATCH-B", KB, always_match),
    )
    result = ex.execute(
        make_context(
            rule_set=(
                make_rule("TEST-MATCH-A", RuleClass.MATCH, 10, "OUT_A"),
                make_rule("TEST-MATCH-B", RuleClass.MATCH, 10, "OUT_B"),
            )
        )
    )
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "GOVERNANCE_AMBIGUITY"
    assert "TEST-MATCH-A" in result.blocking_evidence
    assert "TEST-MATCH-B" in result.blocking_evidence
    assert result.matched_rule_id is None, "the executor must not pick a tied rule"


def test_same_precedence_conflict_raise_policy():
    registry = PredicateRegistry()
    registry.register(TYPE_A, "TEST-MATCH-A", KB, always_match)
    registry.register(TYPE_A, "TEST-MATCH-B", KB, always_match)
    ex = GovernedDecisionExecutor(
        registry, policy=ExecutorPolicy(conflict_policy=ConflictPolicy.RAISE)
    )
    with pytest.raises(ConflictingDecisionMatch, match="precedence 10"):
        ex.execute(
            make_context(
                rule_set=(
                    make_rule("TEST-MATCH-A", RuleClass.MATCH, 10, "OUT_A"),
                    make_rule("TEST-MATCH-B", RuleClass.MATCH, 10, "OUT_B"),
                )
            )
        )


def test_different_precedence_matches_are_not_a_conflict():
    ex = make_executor(
        (TYPE_A, "TEST-MATCH-A", KB, always_match),
        (TYPE_A, "TEST-MATCH-B", KB, always_match),
    )
    result = ex.execute(
        make_context(
            rule_set=(
                make_rule("TEST-MATCH-A", RuleClass.MATCH, 10, "OUT_A"),
                make_rule("TEST-MATCH-B", RuleClass.MATCH, 20, "OUT_B"),
            )
        )
    )
    assert result.outcome_code == "OUT_A"


# ======================================================================
# O -- system failures are never converted into CANNOT_DECIDE
# ======================================================================

def test_missing_predicate_is_system_failure_not_cannot_decide():
    ex = GovernedDecisionExecutor(PredicateRegistry())
    with pytest.raises(MissingPredicate):
        ex.execute(
            make_context(rule_set=(make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "M"),))
        )


def test_raising_predicate_is_system_failure_not_cannot_decide():
    def broken(context):
        raise ZeroDivisionError("boom")

    ex = make_executor((TYPE_A, "TEST-MATCH-001", KB, broken))
    with pytest.raises(PredicateExecutionError, match="ZeroDivisionError"):
        ex.execute(
            make_context(rule_set=(make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "M"),))
        )


def test_predicate_returning_wrong_type_is_system_failure():
    ex = make_executor((TYPE_A, "TEST-MATCH-001", KB, lambda ctx: True))
    with pytest.raises(PredicateExecutionError, match="expected PredicateResult"):
        ex.execute(
            make_context(rule_set=(make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "M"),))
        )


def test_empty_rule_set_is_system_failure_not_cannot_decide():
    ex = GovernedDecisionExecutor(PredicateRegistry())
    with pytest.raises(EmptyRuleSet, match="platform misconfiguration"):
        ex.execute(make_context(rule_set=()))


def test_rules_for_other_decision_types_do_not_count():
    ex = make_executor(("OTHER_TYPE", "R", KB, always_match))
    with pytest.raises(EmptyRuleSet):
        ex.execute(
            make_context(
                rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT",
                                    decision_type="OTHER_TYPE"),)
            )
        )


def test_execute_rejects_non_context():
    ex = GovernedDecisionExecutor(PredicateRegistry())
    with pytest.raises(InvalidDecisionContext, match="requires a DecisionContext"):
        ex.execute({"not": "a context"})


# ======================================================================
# P -- a predicate cannot mutate the context
# ======================================================================

def test_predicate_cannot_mutate_context():
    import dataclasses

    seen = {}

    def tamperer(context):
        try:
            context.request = None
        except dataclasses.FrozenInstanceError:
            seen["frozen_request"] = True
        try:
            context.fold.properties["p"] = None
        except TypeError:
            seen["readonly_properties"] = True
        try:
            context.facts.facts["flag"] = None
        except TypeError:
            seen["readonly_facts"] = True
        return always_match(context)

    ex = make_executor((TYPE_A, "TEST-MATCH-001", KB, tamperer))
    ctx = make_context(
        rule_set=(make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "OUT"),),
        properties={"p": make_property("p", "v")},
        facts={"flag": True},
    )
    ex.execute(ctx)
    assert seen == {
        "frozen_request": True,
        "readonly_properties": True,
        "readonly_facts": True,
    }
    assert ctx.property_named("p").resolved_value == "v"
    assert ctx.facts.value_of("flag") is True


# ======================================================================
# Q -- DecisionResult content
# ======================================================================

def test_result_carries_rule_outcome_reason_and_versions():
    ex = make_executor((TYPE_A, "TEST-MATCH-001", KB, always_match))
    result = ex.execute(
        make_context(
            rule_set=(make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, "OUT", "BECAUSE"),),
            properties={"p": make_property("p", "v")},
        )
    )
    assert result.matched_rule_id == "TEST-MATCH-001"
    assert result.matched_rule_kb_version == KB
    assert result.matched_rule_class == "MATCH"
    assert result.outcome_code == "OUT"
    assert result.reason_code == "BECAUSE"
    assert result.ontology_version == "O-1"
    assert result.kb_version == KB
    assert result.policy_version == "P-1"
    assert result.fold_state_id == "fs-0001"
    assert result.input_digest.startswith("v1:sha256:")
    assert result.execution_status is ExecutionStatus.DECIDED


def test_result_has_no_persistence_fields():
    """decided_by / decided_at belong to the writer, not the executor."""
    ex = make_executor((TYPE_A, "R", KB, always_match))
    result = ex.execute(
        make_context(rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),))
    )
    assert not hasattr(result, "decided_by")
    assert not hasattr(result, "decided_at")


def test_result_lineage_preserves_assertions():
    ex = make_executor((TYPE_A, "R", KB, always_match))
    result = ex.execute(
        make_context(
            rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),),
            properties={
                "alpha": make_property("alpha", "v", assertions=("a-2", "a-1")),
                "beta": make_property("beta", None, state=FoldState.UNREPORTED),
            },
        )
    )
    lineage = dict((name, (state, ids)) for name, state, ids in result.fold_lineage)
    assert lineage["alpha"] == ("ESTABLISHED", ("a-1", "a-2"))
    assert lineage["beta"] == ("UNREPORTED", ()), "absence of evidence is itself evidence"


# ======================================================================
# evidence assembly -- full scan, not just the firing rule
# ======================================================================

def test_evidence_scans_all_required_properties_not_only_the_firing_guard():
    ex = make_executor((TYPE_A, "TEST-GUARD-001", KB, always_match))
    result = ex.execute(
        make_context(
            rule_set=(make_rule("TEST-GUARD-001", RuleClass.GUARD, 10, "CANNOT_DECIDE"),),
            properties={
                "p1": make_property("p1", "v"),
                "p2": make_property("p2", state=FoldState.UNREPORTED),
                "p3": make_property("p3", state=FoldState.CONTRADICTED),
                "p4": make_property("p4", state=FoldState.INVALID),
            },
            required_properties=("p1", "p2", "p3", "p4", "p5_absent"),
        )
    )
    assert result.missing_evidence == ("p2", "p5_absent")
    assert result.blocking_evidence == ("p3", "p4")


def test_absent_property_is_missing_evidence():
    ex = make_executor((TYPE_A, "R", KB, always_match))
    result = ex.execute(
        make_context(
            rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),),
            required_properties=("never_folded",),
        )
    )
    assert result.missing_evidence == ("never_folded",)


def test_evidence_arrays_are_empty_tuples_not_none():
    ex = make_executor((TYPE_A, "R", KB, always_match))
    result = ex.execute(
        make_context(rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),))
    )
    assert result.missing_evidence == ()
    assert result.blocking_evidence == ()


def test_confidence_downgraded_when_evidence_incomplete():
    ex = make_executor((TYPE_A, "R", KB, always_match))
    clean = ex.execute(
        make_context(
            rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),),
            properties={"p": make_property("p", "v")},
            required_properties=("p",),
        )
    )
    dirty = ex.execute(
        make_context(
            rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),),
            properties={"p": make_property("p", state=FoldState.UNREPORTED)},
            required_properties=("p",),
        )
    )
    assert clean.confidence_level == "HIGH"
    assert dirty.confidence_level == "LOW"


# ======================================================================
# the executor learns nothing about WHY a predicate matched
# ======================================================================

def test_executor_does_not_inspect_predicate_detail():
    from decisions import PredicateResult, PredicateVerdict

    def chatty(context):
        return PredicateResult(
            PredicateVerdict.MATCHED, {"because": "some domain-specific reason"}
        )

    ex = make_executor((TYPE_A, "R", KB, chatty))
    result = ex.execute(
        make_context(rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT", "KB_REASON"),))
    )
    # reason_code comes from governed KB metadata, never from the predicate
    assert result.reason_code == "KB_REASON"
    assert "because" not in str(result.reason_code)


def test_opaque_domain_facts_drive_predicates_without_executor_knowledge():
    ex = make_executor((TYPE_A, "R", KB, match_when_flag("some_opaque_fact")))
    matched = ex.execute(
        make_context(
            rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),),
            facts={"some_opaque_fact": True},
        )
    )
    unmatched = ex.execute(
        make_context(
            rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),),
            facts={"some_opaque_fact": False},
        )
    )
    assert matched.outcome_code == "OUT"
    assert unmatched.outcome_code == "CANNOT_DECIDE"
