"""D.4E sections 6-9 and 16-19: the four IDENTITY_ASSESSMENT predicates."""

from __future__ import annotations

import pytest
from d4e_support import make_context, make_facts, make_fold

from decisions import FoldState, PredicateVerdict
from decisions.domains.claris import IDENTITY_PROPERTIES
from decisions.domains.claris.errors import InvalidDomainFact
from decisions.domains.claris.predicates import (
    ir_010_exact_identity_match,
    ir_011_missing_required_input,
    ir_012_contradicted_required_input,
    ir_013_initial_configuration,
)

ESTABLISHED_FACTS_INITIAL = dict(
    product_exists=True, existing_configuration_count=0,
    exact_identity_match_exists=False,
)
ESTABLISHED_FACTS_MATCH = dict(
    product_exists=True, existing_configuration_count=1,
    exact_identity_match_exists=True,
)


# ======================================================================
# section 16 -- IR-011  Missing Required Identity Input
# ======================================================================

def test_ir_011_matches_the_live_customer_segment_unreported_case():
    context = make_context(
        fold=make_fold(states={"customer_segment": FoldState.UNREPORTED})
    )
    result = ir_011_missing_required_input(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert "customer_segment" in result.detail["missing_evidence"]


@pytest.mark.parametrize("name", IDENTITY_PROPERTIES)
def test_ir_011_matches_each_required_property_unreported_separately(name):
    context = make_context(fold=make_fold(states={name: FoldState.UNREPORTED}))
    result = ir_011_missing_required_input(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert result.detail["missing_evidence"] == (name,)


@pytest.mark.parametrize("name", IDENTITY_PROPERTIES)
def test_ir_011_matches_each_required_property_explicitly_undefined(name):
    context = make_context(
        fold=make_fold(states={name: FoldState.EXPLICITLY_UNDEFINED})
    )
    result = ir_011_missing_required_input(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert result.detail["missing_evidence"] == (name,)


@pytest.mark.parametrize("name", IDENTITY_PROPERTIES)
def test_ir_011_matches_each_required_property_absent(name):
    """Absent from the snapshot is distinct from UNREPORTED, and still missing."""
    context = make_context(fold=make_fold(omit=(name,)))
    result = ir_011_missing_required_input(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert result.detail["missing_evidence"] == (name,)


def test_ir_011_reports_every_missing_property_not_just_the_first():
    context = make_context(
        fold=make_fold(
            states={
                "geography": FoldState.UNREPORTED,
                "customer_segment": FoldState.EXPLICITLY_UNDEFINED,
            },
            omit=("term_months",),
        )
    )
    result = ir_011_missing_required_input(context)
    assert result.detail["missing_evidence"] == (
        "customer_segment",
        "geography",
        "term_months",
    )


def test_ir_011_does_not_match_when_everything_is_established():
    assert ir_011_missing_required_input(make_context()).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_011_does_not_treat_contradiction_as_missing():
    """That is IR-012's condition. Reporting it here would misdescribe it."""
    context = make_context(fold=make_fold(states={"geography": FoldState.CONTRADICTED}))
    assert ir_011_missing_required_input(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_011_does_not_treat_an_established_empty_string_as_missing():
    """Section 6: the locked contract does not define emptiness as absence."""
    context = make_context(fold=make_fold(values={"geography": ""}))
    assert ir_011_missing_required_input(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_011_ignores_non_identity_properties():
    from d4e_support import identity_property

    fold = make_fold()
    properties = dict(fold.properties)
    properties["tier"] = identity_property(
        "tier", state=FoldState.UNREPORTED
    )
    from decisions import FoldSnapshotView

    extended = FoldSnapshotView(
        fold_state_id=fold.fold_state_id,
        subject_type=fold.subject_type,
        subject_id=fold.subject_id,
        decision_horizon=fold.decision_horizon,
        fold_status=fold.fold_status,
        kb_version=fold.kb_version,
        policy_version=fold.policy_version,
        properties=properties,
    )
    assert ir_011_missing_required_input(
        make_context(fold=extended)
    ).verdict is PredicateVerdict.NOT_MATCHED


# ======================================================================
# section 17 -- IR-012  Contradicted Required Identity Input
# ======================================================================

def test_ir_012_matches_a_contradicted_geography():
    context = make_context(fold=make_fold(states={"geography": FoldState.CONTRADICTED}))
    result = ir_012_contradicted_required_input(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert "geography" in result.detail["blocking_evidence"]


@pytest.mark.parametrize("name", IDENTITY_PROPERTIES)
def test_ir_012_matches_each_required_property_contradicted(name):
    context = make_context(fold=make_fold(states={name: FoldState.CONTRADICTED}))
    result = ir_012_contradicted_required_input(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert result.detail["blocking_evidence"] == (name,)


def test_ir_012_reports_every_contradicted_property_sorted():
    context = make_context(
        fold=make_fold(
            states={
                "term_months": FoldState.CONTRADICTED,
                "geography": FoldState.CONTRADICTED,
            }
        )
    )
    result = ir_012_contradicted_required_input(context)
    assert result.detail["blocking_evidence"] == ("geography", "term_months")


def test_ir_012_does_not_match_without_a_contradiction():
    assert ir_012_contradicted_required_input(make_context()).verdict is (
        PredicateVerdict.NOT_MATCHED
    )
    unreported = make_context(
        fold=make_fold(states={"customer_segment": FoldState.UNREPORTED})
    )
    assert ir_012_contradicted_required_input(unreported).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


# ======================================================================
# section 18 -- IR-013  Initial Configuration for Existing Product
# ======================================================================

def test_ir_013_matches_established_identity_existing_product_no_configuration():
    context = make_context(facts=make_facts(**ESTABLISHED_FACTS_INITIAL))
    result = ir_013_initial_configuration(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert result.detail["product_exists"] is True
    assert result.detail["existing_configuration_count"] == 0


def test_ir_013_does_not_match_when_the_product_does_not_exist():
    context = make_context(
        facts=make_facts(
            product_exists=False, existing_configuration_count=0,
            exact_identity_match_exists=False,
        )
    )
    assert ir_013_initial_configuration(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


@pytest.mark.parametrize("count", [1, 2, 17])
def test_ir_013_does_not_match_when_configurations_already_exist(count):
    context = make_context(
        facts=make_facts(
            product_exists=True, existing_configuration_count=count,
            exact_identity_match_exists=False,
        )
    )
    assert ir_013_initial_configuration(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_013_does_not_match_when_an_identity_input_is_missing():
    context = make_context(
        fold=make_fold(states={"customer_segment": FoldState.UNREPORTED}),
        facts=make_facts(**ESTABLISHED_FACTS_INITIAL),
    )
    assert ir_013_initial_configuration(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_013_does_not_match_on_an_unavailable_product_fact():
    """Unavailable means the platform could not look, not that nothing is there."""
    context = make_context(
        facts=make_facts(
            product_exists="PRODUCT_REFERENCE_NOT_ESTABLISHED",
            existing_configuration_count="PRODUCT_REFERENCE_NOT_ESTABLISHED",
            exact_identity_match_exists="IDENTITY_NOT_SERIALIZABLE",
        )
    )
    assert ir_013_initial_configuration(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_013_does_not_match_when_facts_are_absent_entirely():
    assert ir_013_initial_configuration(make_context()).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_013_creates_nothing():
    """Section 27: the predicate concludes. It does not act."""
    import decisions.domains.claris.predicates.identity_assessment as module
    from d4d_support import executable_source

    code = executable_source(module)
    for forbidden in ("insert", "commit", "execute(", "cursor", "create_product",
                      "create_configuration", "write", "save", "persist"):
        assert forbidden not in code, f"predicate module performs an action: {forbidden!r}"


# ======================================================================
# section 19 -- IR-010  Exact Identity Tuple Match
# ======================================================================

def test_ir_010_matches_an_exact_identity_match():
    context = make_context(facts=make_facts(**ESTABLISHED_FACTS_MATCH))
    result = ir_010_exact_identity_match(context)
    assert result.verdict is PredicateVerdict.MATCHED
    assert result.detail["exact_identity_match_exists"] is True


def test_ir_010_does_not_match_without_an_exact_match():
    context = make_context(facts=make_facts(**ESTABLISHED_FACTS_INITIAL))
    assert ir_010_exact_identity_match(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_010_does_not_match_when_the_identity_never_serialized():
    context = make_context(
        fold=make_fold(states={"customer_segment": FoldState.UNREPORTED}),
        facts=make_facts(
            product_exists=True, existing_configuration_count=1,
            exact_identity_match_exists="IDENTITY_NOT_SERIALIZABLE",
        ),
    )
    assert ir_010_exact_identity_match(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


def test_ir_010_requires_established_inputs_even_if_a_match_fact_claims_true():
    """A stale or wrong fact must not override the governed Fold state."""
    context = make_context(
        fold=make_fold(states={"geography": FoldState.CONTRADICTED}),
        facts=make_facts(**ESTABLISHED_FACTS_MATCH),
    )
    assert ir_010_exact_identity_match(context).verdict is (
        PredicateVerdict.NOT_MATCHED
    )


# ======================================================================
# section 25 -- an invalid domain fact type is a system failure
# ======================================================================

@pytest.mark.parametrize(
    "predicate,facts",
    [
        (ir_013_initial_configuration, {"product_exists": "TRUE"}),
        (ir_010_exact_identity_match, {"exact_identity_match_exists": 1}),
    ],
)
def test_a_wrongly_typed_domain_fact_raises_rather_than_being_coerced(predicate, facts):
    from decisions import DomainFacts, Known

    context = make_context(facts=DomainFacts({k: Known(v) for k, v in facts.items()}))
    with pytest.raises(InvalidDomainFact):
        predicate(context)


def test_a_boolean_configuration_count_is_refused():
    from decisions import DomainFacts, Known

    context = make_context(
        facts=DomainFacts(
            {"product_exists": Known(True), "existing_configuration_count": Known(False)}
        )
    )
    with pytest.raises(InvalidDomainFact):
        ir_013_initial_configuration(context)


# ======================================================================
# predicates never produce outcomes
# ======================================================================

@pytest.mark.parametrize(
    "predicate",
    [
        ir_011_missing_required_input,
        ir_012_contradicted_required_input,
        ir_013_initial_configuration,
        ir_010_exact_identity_match,
    ],
)
def test_no_predicate_returns_an_outcome_or_reason_code(predicate):
    context = make_context(facts=make_facts(**ESTABLISHED_FACTS_MATCH))
    result = predicate(context)
    assert not hasattr(result, "outcome_code")
    assert not hasattr(result, "reason_code")
    assert "outcome_code" not in result.detail
    assert "reason_code" not in result.detail
