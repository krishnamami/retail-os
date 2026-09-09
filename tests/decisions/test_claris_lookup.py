"""D.4E sections 4, 5, 14, 15: the read-only canonical lookup adapter."""

from __future__ import annotations

import pytest
from d4e_support import EXPECTED_CANONICAL_IDENTITY, FakeCanonicalDB, make_fold

from decisions import FoldState, Known, Unavailable
from decisions.domains.claris import (
    DOMAIN_FACT_NAMES,
    EXACT_IDENTITY_MATCH_EXISTS,
    EXISTING_CONFIGURATION_COUNT,
    PRODUCT_EXISTS,
    REPLAY_SAFETY,
    CanonicalIdentityLookup,
    ClarisIdentityFactProvider,
    LookupSemantics,
)
from decisions.domains.claris.errors import CanonicalLookupError
from decisions.domains.claris.lookup import (
    UNAVAILABLE_IDENTITY_NOT_SERIALIZABLE,
    UNAVAILABLE_PRODUCT_REFERENCE_NOT_ESTABLISHED,
)


def lookup(**kwargs) -> CanonicalIdentityLookup:
    return CanonicalIdentityLookup(FakeCanonicalDB(**kwargs))


# ======================================================================
# section 14 -- exactly three facts, and nothing else, cross the boundary
# ======================================================================

def test_exactly_the_three_required_facts_are_produced():
    facts = lookup(products=("PROD-001",)).lookup_for_fold(make_fold()).to_domain_facts()
    assert set(facts.facts) == set(DOMAIN_FACT_NAMES)
    assert DOMAIN_FACT_NAMES == (
        "product_exists",
        "existing_configuration_count",
        "exact_identity_match_exists",
    )


def test_no_database_handle_or_row_reaches_the_domain_facts():
    facts = lookup(products=("PROD-001",)).lookup_for_fold(make_fold()).to_domain_facts()
    for value in facts.facts.values():
        assert isinstance(value, (Known, Unavailable))
        if isinstance(value, Known):
            assert isinstance(value.value, (bool, int))


# ======================================================================
# section 15 -- empty canonical tables are a valid current-state answer
# ======================================================================

def test_empty_canonical_tables_give_false_zero_false():
    result = lookup().lookup_for_fold(make_fold())
    assert result.product_exists is False
    assert result.existing_configuration_count == 0
    assert result.exact_identity_match_exists is False
    assert result.canonical_identity == EXPECTED_CANONICAL_IDENTITY


def test_product_exists_with_no_configurations():
    result = lookup(products=("PROD-001",)).lookup_for_fold(make_fold())
    assert result.product_exists is True
    assert result.existing_configuration_count == 0
    assert result.exact_identity_match_exists is False


def test_exact_identity_match_is_found_when_a_configuration_carries_it():
    result = lookup(
        products=("PROD-001",),
        configurations=(("PROD-001", EXPECTED_CANONICAL_IDENTITY),),
    ).lookup_for_fold(make_fold())
    assert result.existing_configuration_count == 1
    assert result.exact_identity_match_exists is True


def test_a_different_identity_under_the_same_product_is_not_an_exact_match():
    result = lookup(
        products=("PROD-001",),
        configurations=(("PROD-001", "PROD-001|EMEA|36|enterprise"),),
    ).lookup_for_fold(make_fold())
    assert result.existing_configuration_count == 1
    assert result.exact_identity_match_exists is False


# ======================================================================
# unavailable, never fabricated
# ======================================================================

def test_unserializable_identity_yields_an_unavailable_match_fact():
    fold = make_fold(states={"customer_segment": FoldState.UNREPORTED})
    facts = lookup(products=("PROD-001",)).lookup_for_fold(fold).to_domain_facts()
    match = facts.get(EXACT_IDENTITY_MATCH_EXISTS)
    assert isinstance(match, Unavailable)
    assert match.reason == UNAVAILABLE_IDENTITY_NOT_SERIALIZABLE
    # product_reference is still ESTABLISHED, so those two remain answerable
    assert facts.get(PRODUCT_EXISTS) == Known(True)
    assert facts.get(EXISTING_CONFIGURATION_COUNT) == Known(0)


def test_unavailable_product_reference_makes_both_product_facts_unavailable():
    fold = make_fold(states={"product_reference": FoldState.CONTRADICTED})
    facts = lookup().lookup_for_fold(fold).to_domain_facts()
    for name in (PRODUCT_EXISTS, EXISTING_CONFIGURATION_COUNT):
        fact = facts.get(name)
        assert isinstance(fact, Unavailable)
        assert fact.reason == UNAVAILABLE_PRODUCT_REFERENCE_NOT_ESTABLISHED


def test_unavailable_reasons_are_fixed_strings_so_the_digest_stays_stable():
    """An Unavailable reason enters input_digest. It must not carry a subject
    id, a timestamp or any other per-execution value."""
    a = lookup().lookup_for_fold(
        make_fold(subject_id="CONFIG-REQ-A", states={"geography": FoldState.UNREPORTED})
    )
    b = lookup().lookup_for_fold(
        make_fold(subject_id="CONFIG-REQ-B", states={"geography": FoldState.UNREPORTED})
    )
    assert a.unavailable == b.unavailable


def test_an_invalid_state_still_raises_rather_than_becoming_unavailable():
    """Section 25 again: INVALID is a system failure, not a missing fact."""
    from decisions.domains.claris.errors import InvalidIdentityState

    with pytest.raises(InvalidIdentityState):
        lookup().lookup_for_fold(make_fold(states={"geography": FoldState.INVALID}))


# ======================================================================
# section 25 -- a database failure is a system failure
# ======================================================================

def test_database_failure_raises_and_is_never_reported_as_a_business_fact():
    broken = CanonicalIdentityLookup(FakeCanonicalDB(fail_with=RuntimeError("boom")))
    with pytest.raises(CanonicalLookupError, match="system failure"):
        broken.lookup_for_fold(make_fold())


def test_a_lookup_without_a_database_is_refused_at_construction():
    with pytest.raises(CanonicalLookupError):
        CanonicalIdentityLookup(None)
    with pytest.raises(CanonicalLookupError):
        CanonicalIdentityLookup(object())


# ======================================================================
# section 4 -- read-only, parameterized
# ======================================================================

def test_every_statement_is_a_parameterized_select():
    db = FakeCanonicalDB(products=("PROD-001",))
    CanonicalIdentityLookup(db).lookup_for_fold(make_fold())
    assert db.calls
    for sql, params in db.calls:
        normalized = " ".join(sql.split()).lower()
        assert normalized.startswith("select")
        assert "%s" in sql, f"statement is not parameterized: {sql!r}"
        assert params is not None


def test_no_mutating_sql_appears_anywhere_in_the_lookup_module():
    import decisions.domains.claris.lookup as module
    from d4d_support import executable_source

    code = executable_source(module)
    for forbidden in (
        "insert into", "update ", "delete from", "drop ", "alter ", "truncate",
        "create table", "grant ", "merge into",
    ):
        assert forbidden not in code, f"mutating SQL in lookup module: {forbidden!r}"


def test_canonical_table_names_do_not_leak_into_the_predicates():
    import decisions.domains.claris.predicates.identity_assessment as predicates
    from d4d_support import executable_source

    code = executable_source(predicates)
    for leaked in ("claris.product", "claris.configuration", "select", "%s"):
        assert leaked not in code, f"database detail leaked into predicates: {leaked!r}"


def test_platform_modules_never_learn_the_canonical_table_names():
    import decisions.contracts as contracts
    import decisions.executor as executor
    import decisions.registry as registry
    from d4d_support import executable_source

    for module in (contracts, executor, registry):
        code = executable_source(module)
        for leaked in (
            "claris",
            "claris.product",
            "claris.configuration",
            "product_exists",
            "existing_configuration_count",
            "exact_identity_match_exists",
            "canonical_identity",
        ):
            assert leaked not in code, (
                f"{module.__name__} learned a domain name: {leaked!r}"
            )


# ======================================================================
# section 5 (V-4) -- as-of vs current state
# ======================================================================

def test_results_declare_current_state_semantics():
    result = lookup().lookup_for_fold(make_fold())
    assert result.semantics is LookupSemantics.CURRENT_STATE
    assert result.replay_safety == "PARTIAL / NOT YET REPLAY-SAFE"
    assert REPLAY_SAFETY == "PARTIAL / NOT YET REPLAY-SAFE"


def test_no_statement_filters_on_a_decision_horizon():
    """A horizon filter would dress a current-state read as historical replay."""
    db = FakeCanonicalDB(products=("PROD-001",))
    CanonicalIdentityLookup(db).lookup_for_fold(make_fold())
    for sql, _ in db.calls:
        lowered = sql.lower()
        assert "decision_horizon" not in lowered
        assert "as of" not in lowered


def test_temporal_capability_reports_the_schema_cannot_support_as_of():
    """Measured from information_schema, not asserted from the docstring.

    claris.product has created_at and nothing that records an end of life, so
    'did this product exist at horizon T' is unanswerable from this schema.
    """
    capability = CanonicalIdentityLookup(FakeCanonicalDB()).temporal_capability()
    assert capability["product_supports_as_of"] is False
    assert capability["as_of_supported"] is False
    assert capability["semantics"] == "CURRENT_STATE"
    assert capability["replay_safety"] == "PARTIAL / NOT YET REPLAY-SAFE"
    assert "created_at" in capability["columns"]["product"]
    assert "archived_at" in capability["columns"]["configuration"]


# ======================================================================
# the fact provider port
# ======================================================================

def test_fact_provider_implements_the_port_and_records_its_last_result():
    provider = ClarisIdentityFactProvider(
        CanonicalIdentityLookup(FakeCanonicalDB(products=("PROD-001",)))
    )
    fold = make_fold()

    class _Request:
        decision_type = "IDENTITY_ASSESSMENT"

    facts = provider.facts_for(_Request(), fold)
    assert facts.get(PRODUCT_EXISTS) == Known(True)
    assert provider.last_result.canonical_identity == EXPECTED_CANONICAL_IDENTITY
    assert provider.last_result.semantics is LookupSemantics.CURRENT_STATE


def test_fact_provider_requires_a_real_lookup():
    with pytest.raises(CanonicalLookupError):
        ClarisIdentityFactProvider(FakeCanonicalDB())


def test_archived_configurations_still_count_towards_the_configuration_count():
    """Documented choice: an archived configuration means the product has had
    one, so IR-013's 'initial configuration' condition is not satisfied."""
    result = lookup(
        products=("PROD-001",),
        configurations=(("PROD-001", "PROD-001|EMEA|12|smb"),),
    ).lookup_for_fold(make_fold())
    assert result.existing_configuration_count == 1


# ======================================================================
# D.4E CORRECTION -- archived exact identity semantics
# ======================================================================

ARCHIVED_AT = "2026-01-01T00:00:00Z"


def test_active_exact_match_returns_true():
    """The required case: a currently eligible configuration matches."""
    result = lookup(
        products=("PROD-001",),
        configurations=(("PROD-001", EXPECTED_CANONICAL_IDENTITY, "active", None),),
    ).lookup_for_fold(make_fold())
    assert result.exact_identity_match_exists is True
    assert result.eligible_identity_matches == 1
    assert result.ineligible_identity_matches == 0


def test_archived_only_exact_match_returns_false():
    """The correction. An archived configuration is NOT an exact identity match.

    Treating it as one let IR-010 conclude NO_BUSINESS_CHANGE against a
    configuration that is no longer live -- a governance semantic that was
    never established.
    """
    result = lookup(
        products=("PROD-001",),
        configurations=(
            ("PROD-001", EXPECTED_CANONICAL_IDENTITY, "archived", ARCHIVED_AT),
        ),
    ).lookup_for_fold(make_fold())
    assert result.exact_identity_match_exists is False
    assert result.eligible_identity_matches == 0
    assert result.ineligible_identity_matches == 1


def test_archived_configuration_still_contributes_to_the_configuration_count():
    """The two facts answer different questions and must not move together.

    'has this product ever had a configuration' (IR-013) vs 'is this exact
    identity live right now' (IR-010).
    """
    result = lookup(
        products=("PROD-001",),
        configurations=(
            ("PROD-001", EXPECTED_CANONICAL_IDENTITY, "archived", ARCHIVED_AT),
        ),
    ).lookup_for_fold(make_fold())
    assert result.existing_configuration_count == 1
    assert result.exact_identity_match_exists is False


def test_an_active_match_alongside_an_archived_one_is_still_a_match():
    result = lookup(
        products=("PROD-001",),
        configurations=(
            ("PROD-001", EXPECTED_CANONICAL_IDENTITY, "archived", ARCHIVED_AT),
            ("PROD-001", EXPECTED_CANONICAL_IDENTITY, "active", None),
        ),
    ).lookup_for_fold(make_fold())
    assert result.exact_identity_match_exists is True
    assert result.existing_configuration_count == 2
    assert result.eligible_identity_matches == 1
    assert result.ineligible_identity_matches == 1


def test_status_active_but_archived_at_set_is_treated_as_archived():
    """Contradictory row. The conservative reading never invents reactivation."""
    result = lookup(
        products=("PROD-001",),
        configurations=(
            ("PROD-001", EXPECTED_CANONICAL_IDENTITY, "active", ARCHIVED_AT),
        ),
    ).lookup_for_fold(make_fold())
    assert result.exact_identity_match_exists is False
    assert result.ineligible_identity_matches == 1


def test_no_reactivation_semantics_are_implemented():
    """An archived-only match must not be turned into a reuse instruction."""
    import decisions.domains.claris.lookup as module
    from d4d_support import executable_source

    code = executable_source(module)
    for invented in ("reactivat", "revive", "unarchive", "restore", "use_existing"):
        assert invented not in code, f"reactivation semantics invented: {invented!r}"


@pytest.mark.parametrize("unknown_status", [None, "proposed", "confirmed", "disputed"])
def test_an_ungoverned_status_raises_rather_than_being_guessed(unknown_status):
    """Section 5's STOP condition, enforced per row at runtime.

    'proposed' / 'confirmed' / 'disputed' come from the ontology's OTHER
    configuration_status vocabulary. If one ever appears in this column the
    row's eligibility is genuinely undetermined, and guessing either way would
    invent governance.
    """
    from decisions.domains.claris.errors import ConfigurationEligibilityUnknown

    with pytest.raises(ConfigurationEligibilityUnknown, match="cannot be determined"):
        lookup(
            products=("PROD-001",),
            configurations=(
                ("PROD-001", EXPECTED_CANONICAL_IDENTITY, unknown_status, None),
            ),
        ).lookup_for_fold(make_fold())


def test_an_ungoverned_status_with_archived_at_is_safely_ineligible():
    """Undetermined status but demonstrably archived: never eligible, no raise."""
    result = lookup(
        products=("PROD-001",),
        configurations=(
            ("PROD-001", EXPECTED_CANONICAL_IDENTITY, "proposed", ARCHIVED_AT),
        ),
    ).lookup_for_fold(make_fold())
    assert result.exact_identity_match_exists is False


def test_eligibility_capability_is_measured_from_the_schema():
    capability = CanonicalIdentityLookup(FakeCanonicalDB()).eligibility_capability()
    assert capability["has_status"] is True
    assert capability["has_archived_at"] is True
    assert capability["vocabulary_closed_to_active_archived"] is True
    assert capability["eligibility_determinable"] is True
    assert capability["governed_vocabulary"] == ("active", "archived")


def test_the_governed_vocabulary_is_exactly_active_and_archived():
    from decisions.domains.claris.lookup import (
        ACTIVE_STATUS,
        ARCHIVED_STATUS,
        CONFIGURATION_STATUS_VOCABULARY,
    )

    assert ACTIVE_STATUS == "active"
    assert ARCHIVED_STATUS == "archived"
    assert CONFIGURATION_STATUS_VOCABULARY == ("active", "archived")


def test_the_eligibility_query_is_still_parameterized_and_read_only():
    db = FakeCanonicalDB(
        products=("PROD-001",),
        configurations=(("PROD-001", EXPECTED_CANONICAL_IDENTITY),),
    )
    CanonicalIdentityLookup(db).lookup_for_fold(make_fold())
    identity_calls = [c for c in db.calls if "canonical_identity = %s" in c[0]]
    assert identity_calls
    for sql, params in identity_calls:
        assert " ".join(sql.split()).lower().startswith("select")
        assert params[-1] == EXPECTED_CANONICAL_IDENTITY
        assert "active" in params and "archived" in params
