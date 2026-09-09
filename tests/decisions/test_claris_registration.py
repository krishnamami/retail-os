"""D.4E sections 10-13 and 20: registration, ordering, governance safety."""

from __future__ import annotations

import pytest
from d4e_support import (
    EXPECTED_CANONICAL_IDENTITY,
    make_context,
    make_facts,
    make_fold,
    prototype_executor,
)

from decisions import FoldState, PredicateRegistry, RuleClass
from decisions.domains.claris import (
    DECISION_TYPE,
    IDENTITY_PROPERTIES,
    IDENTITY_RULE_ORDER,
    SEMANTIC_RULE_ORDER,
    EXECUTABLE_RULE_IDS,
    IDENTITY_SEMANTIC_RULES,
    PROTOTYPE_ONTOLOGY_VERSION,
    PROTOTYPE_VALIDATION_STATUS,
    PROTOTYPE_LABEL,
    SEMANTIC_KB_VERSION,
    SEMANTIC_RULE_STATUS,
    build_prototype_registry,
    identity_class_bindings,
    prototype_governance_binding,
    prototype_rule_bindings,
    register_identity_assessment,
)

INITIAL = dict(
    product_exists=True, existing_configuration_count=0,
    exact_identity_match_exists=False,
)
EXACT = dict(
    product_exists=True, existing_configuration_count=1,
    exact_identity_match_exists=True,
)


def run(fold=None, facts=None):
    return prototype_executor().execute(
        make_context(fold=fold, facts=facts, governance=prototype_governance_binding())
    )


# ======================================================================
# section 10 -- locked classes and precedences
# ======================================================================

def test_rule_classes_and_precedences_are_the_locked_values():
    locked = {
        "IR-011": (RuleClass.GUARD, 1),
        "IR-012": (RuleClass.GUARD, 2),
        "IR-013": (RuleClass.MATCH, 5),
        "IR-010": (RuleClass.MATCH, 6),
    }
    actual = {r.rule_id: (r.rule_class, r.precedence) for r in IDENTITY_SEMANTIC_RULES}
    assert actual == locked


def test_registration_order_is_the_locked_order():
    assert IDENTITY_RULE_ORDER == (
        "IA-PRED-001", "IA-PRED-002", "IA-PRED-003", "IA-PRED-004",
    )
    assert SEMANTIC_RULE_ORDER == ("IR-011", "IR-012", "IR-013", "IR-010")


def test_evaluation_order_is_guards_then_matches_by_precedence():
    ordered = [b.rule_id for b in prototype_rule_bindings()]
    assert ordered == [
        "IA-PRED-001", "IA-PRED-002", "IA-PRED-003", "IA-PRED-004",
    ]
    classes = [b.rule_class for b in prototype_rule_bindings()]
    assert classes == [RuleClass.GUARD, RuleClass.GUARD, RuleClass.MATCH, RuleClass.MATCH]


def test_no_fallback_rule_is_declared_for_identity_assessment():
    assert all(r.rule_class is not RuleClass.FALLBACK for r in IDENTITY_SEMANTIC_RULES)
    assert all(
        b.rule_class is not RuleClass.FALLBACK for b in prototype_rule_bindings()
    )


def test_no_rule_resolved_uses_the_platform_default_not_a_claris_fallback():
    """FoldState.INVALID is claimed by no rule. The generic executor's
    configured no-resolution behaviour applies; the domain invents nothing."""
    result = run(
        fold=make_fold(states={"geography": FoldState.INVALID}),
        facts=make_facts(**INITIAL),
    )
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "NO_RULE_MATCHED"
    assert result.matched_rule_id is None


# ======================================================================
# section 12 -- registration against the generic registry
# ======================================================================

def test_all_four_predicates_register_under_the_decision_type():
    registry = build_prototype_registry()
    assert len(registry) == 4
    for rule_id in IDENTITY_RULE_ORDER:
        assert (DECISION_TYPE, rule_id, SEMANTIC_KB_VERSION) in registry


def test_the_registry_has_a_predicate_for_every_prototype_binding():
    registry = build_prototype_registry()
    assert registry.missing_for(prototype_rule_bindings()) == ()


def test_double_registration_is_refused():
    from decisions import DuplicatePredicateRegistration

    registry = build_prototype_registry()
    with pytest.raises(DuplicatePredicateRegistration):
        register_identity_assessment(registry)


def test_registration_order_cannot_influence_the_outcome():
    """The registry is a dict; order comes from governed class and precedence."""
    forward = build_prototype_registry()
    reverse = PredicateRegistry()
    from decisions.domains.claris.predicates import IDENTITY_PREDICATES

    for semantic_id in reversed(SEMANTIC_RULE_ORDER):
        reverse.register(
            DECISION_TYPE,
            EXECUTABLE_RULE_IDS[semantic_id],
            SEMANTIC_KB_VERSION,
            IDENTITY_PREDICATES[semantic_id],
        )
    assert forward.keys() == reverse.keys()


def test_class_bindings_carry_rule_class_and_predicate_ref_only():
    bindings = identity_class_bindings()
    assert set(bindings) == set(IDENTITY_RULE_ORDER)
    for rule_id, binding in bindings.items():
        assert binding.rule_id == rule_id
        assert binding.predicate_ref.startswith("claris.identity_assessment.")
        assert not hasattr(binding, "outcome_code")
        assert not hasattr(binding, "kb_version")


def test_no_claris_rule_id_appears_in_a_generic_platform_module():
    import decisions.contracts as contracts
    import decisions.executor as executor
    import decisions.ports as ports
    import decisions.registry as registry_module
    import decisions.rules as rules
    from d4d_support import executable_source

    for module in (contracts, executor, registry_module, rules, ports):
        code = executable_source(module)
        for rule_id in ("ir-010", "ir-011", "ir-012", "ir-013"):
            assert rule_id not in code, f"{module.__name__} names {rule_id}"


# ======================================================================
# section 13 -- governance-binding safety
# ======================================================================

def test_the_prototype_binding_announces_that_it_is_not_governed():
    binding = prototype_governance_binding()
    assert binding.governance_basis == "PROTOTYPE_ASSUMPTION"
    assert binding.ontology_version == PROTOTYPE_ONTOLOGY_VERSION
    assert binding.policy_version is None
    assert PROTOTYPE_LABEL == "PROTOTYPE DOMAIN EVALUATION ONLY"
    assert PROTOTYPE_VALIDATION_STATUS == "TO_BE_VALIDATED_WITH_CLARIS"


def test_a_prototype_result_is_self_identifying():
    """The basis and the release are separate facts, and both survive.

    The retired NON_GOVERNED_PROTOTYPE sentinel carried the first by
    destroying the second: a prototype result could not say which assumptions
    it ran against.
    """
    result = run(facts=make_facts(**INITIAL))
    assert result.governance_basis == "PROTOTYPE_ASSUMPTION"
    assert result.ontology_version == PROTOTYPE_ONTOLOGY_VERSION == "2026.10-prototype.1"
    assert result.policy_version is None


def test_the_semantic_rules_are_still_proposed_and_not_executable():
    for rule in IDENTITY_SEMANTIC_RULES:
        assert rule.status == SEMANTIC_RULE_STATUS == "proposed"
        assert rule.kb_version == "1.0.1"
        assert rule.is_executable_governed_rule is False


def test_the_domain_pack_writes_nothing_to_the_governed_kb():
    import decisions.domains.claris.identity as identity
    import decisions.domains.claris.lookup as lookup
    import decisions.domains.claris.registration as registration
    from d4d_support import executable_source

    for module in (registration, identity, lookup):
        code = executable_source(module)
        assert "decision_rules" not in code
        assert "identity_rules" not in code
        assert "insert" not in code
        assert "update " not in code


# ======================================================================
# section 20 -- ordering scenarios through the real executor
# ======================================================================

def test_guard_ir_011_wins_over_an_exact_identity_match():
    result = run(
        fold=make_fold(states={"customer_segment": FoldState.UNREPORTED}),
        facts=make_facts(**EXACT),
    )
    assert result.matched_rule_id == "IA-PRED-001"
    assert result.matched_rule_class == "GUARD"
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "MISSING_REQUIRED_INPUT"
    assert "customer_segment" in result.missing_evidence


def test_guard_ir_012_wins_over_initial_configuration():
    result = run(
        fold=make_fold(states={"geography": FoldState.CONTRADICTED}),
        facts=make_facts(**INITIAL),
    )
    assert result.matched_rule_id == "IA-PRED-002"
    assert result.matched_rule_class == "GUARD"
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "CONTRADICTED_REQUIRED_INPUT"
    assert "geography" in result.blocking_evidence


def test_ir_011_precedes_ir_012_when_both_conditions_hold():
    result = run(
        fold=make_fold(
            states={
                "customer_segment": FoldState.UNREPORTED,
                "geography": FoldState.CONTRADICTED,
            }
        ),
        facts=make_facts(**INITIAL),
    )
    assert result.matched_rule_id == "IA-PRED-001"
    assert "customer_segment" in result.missing_evidence
    assert "geography" in result.blocking_evidence


def test_ir_013_resolves_an_established_identity_with_no_configuration():
    result = run(facts=make_facts(**INITIAL))
    assert result.matched_rule_id == "IA-PRED-003"
    assert result.matched_rule_class == "MATCH"
    assert result.outcome_code == "CREATE_CONFIGURATION"
    assert result.reason_code == "INITIAL_CONFIGURATION"


def test_ir_010_resolves_an_exact_identity_match():
    result = run(facts=make_facts(**EXACT))
    assert result.matched_rule_id == "IA-PRED-004"
    assert result.matched_rule_class == "MATCH"
    assert result.outcome_code == "NO_BUSINESS_CHANGE"
    assert result.reason_code == "EXACT_IDENTITY_MATCH"


def test_ir_013_and_ir_010_never_tie_because_their_precedences_differ():
    """Both MATCH rules can never collide into GOVERNANCE_AMBIGUITY."""
    precedences = [
        r.precedence for r in IDENTITY_SEMANTIC_RULES if r.rule_class is RuleClass.MATCH
    ]
    assert len(precedences) == len(set(precedences))


def test_ir_013_wins_when_both_match_conditions_somehow_hold():
    result = run(
        facts=make_facts(
            product_exists=True, existing_configuration_count=0,
            exact_identity_match_exists=True,
        )
    )
    assert result.matched_rule_id == "IA-PRED-003"


# ======================================================================
# the record a prototype evaluation produces
# ======================================================================

def test_required_properties_are_the_four_identity_properties():
    assert prototype_governance_binding().required_properties == IDENTITY_PROPERTIES


def test_the_result_carries_full_fold_lineage_and_the_facts_it_used():
    result = run(facts=make_facts(**INITIAL))
    lineage = dict((name, state) for name, state, _ in result.fold_lineage)
    assert set(lineage) == set(IDENTITY_PROPERTIES)
    assert all(state == "ESTABLISHED" for state in lineage.values())
    used = dict(result.domain_facts_used)
    assert used["product_exists"] == "KNOWN:True"
    assert used["existing_configuration_count"] == "KNOWN:0"


def test_an_unavailable_fact_is_recorded_as_unavailable_not_as_false():
    result = run(
        fold=make_fold(states={"customer_segment": FoldState.UNREPORTED}),
        facts=make_facts(
            product_exists=True, existing_configuration_count=0,
            exact_identity_match_exists="IDENTITY_NOT_SERIALIZABLE",
        ),
    )
    used = dict(result.domain_facts_used)
    assert used["exact_identity_match_exists"] == (
        "UNAVAILABLE:IDENTITY_NOT_SERIALIZABLE"
    )


def test_the_prototype_evaluation_is_deterministic():
    a = run(facts=make_facts(**INITIAL))
    b = run(facts=make_facts(**INITIAL))
    assert a.input_digest == b.input_digest
    assert a.outcome_code == b.outcome_code


def test_a_different_identity_produces_a_different_digest():
    a = run(facts=make_facts(**INITIAL))
    b = prototype_executor().execute(
        make_context(
            fold=make_fold(values={"geography": "EMEA"}),
            facts=make_facts(**INITIAL),
            governance=prototype_governance_binding(),
        )
    )
    assert a.input_digest != b.input_digest


def test_canonical_identity_is_not_the_input_digest():
    from decisions.domains.claris import serialize_canonical_identity

    result = run(facts=make_facts(**INITIAL))
    identity = serialize_canonical_identity(make_fold())
    assert identity == EXPECTED_CANONICAL_IDENTITY
    assert identity != result.input_digest
    assert result.input_digest.startswith("v1:sha256:")


# ======================================================================
# D.4E CORRECTION -- archived-only identity through the real executor
# ======================================================================

def _run_against_canonical(configurations, products=("PROD-001",)):
    """Real executor + real lookup adapter over an in-memory canonical table."""
    from d4e_support import FakeCanonicalDB
    from decisions.domains.claris import (
        CanonicalIdentityLookup,
        ClarisIdentityFactProvider,
    )

    fold = make_fold()
    facts = ClarisIdentityFactProvider(
        CanonicalIdentityLookup(
            FakeCanonicalDB(products=products, configurations=configurations)
        )
    ).facts_for(None, fold)
    return prototype_executor().execute(
        make_context(fold=fold, facts=facts, governance=prototype_governance_binding())
    )


def test_an_active_exact_match_still_concludes_no_business_change():
    result = _run_against_canonical(
        (("PROD-001", EXPECTED_CANONICAL_IDENTITY, "active", None),)
    )
    assert result.matched_rule_id == "IA-PRED-004"
    assert result.outcome_code == "NO_BUSINESS_CHANGE"


def test_an_archived_only_exact_match_does_not_conclude_no_business_change():
    """The correction, end to end.

    IR-013 does not fire (a configuration has existed, so this is not the
    initial one) and IR-010 does not fire (the match is not currently
    eligible). No rule resolves, so the platform's own no-resolution behaviour
    applies -- the domain pack invents no archived-match outcome.
    """
    result = _run_against_canonical(
        (("PROD-001", EXPECTED_CANONICAL_IDENTITY, "archived", "2026-01-01T00:00:00Z"),)
    )
    assert result.outcome_code != "NO_BUSINESS_CHANGE"
    assert result.matched_rule_id != "IA-PRED-004"
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "NO_RULE_MATCHED"
    assert dict(result.domain_facts_used)["exact_identity_match_exists"] == "KNOWN:False"
    assert dict(result.domain_facts_used)["existing_configuration_count"] == "KNOWN:1"


def test_an_archived_configuration_still_blocks_ir_013():
    """existing_configuration_count keeps counting archived rows, by design."""
    result = _run_against_canonical(
        (("PROD-001", "PROD-001|EMEA|12|smb", "archived", "2026-01-01T00:00:00Z"),)
    )
    assert result.matched_rule_id != "IA-PRED-003"
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "NO_RULE_MATCHED"


def test_ir_013_still_fires_when_the_product_has_never_had_a_configuration():
    result = _run_against_canonical(())
    assert result.matched_rule_id == "IA-PRED-003"
    assert result.outcome_code == "CREATE_CONFIGURATION"
