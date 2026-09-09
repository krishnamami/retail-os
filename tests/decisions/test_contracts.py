"""A. DecisionRequest validation, B. immutability, C. Fold property preservation."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from d4c_support import HORIZON, TYPE_A, make_context, make_property

from decisions import (
    DecisionRequest,
    FoldProperty,
    FoldSnapshotView,
    FoldState,
    GovernanceBinding,
    InvalidDecisionContext,
    InvalidDecisionRequest,
    RuleClass,
)
from decisions.rules import RuleDefinition
from decisions.errors import InvalidRuleDefinition


# -- A. DecisionRequest validation --------------------------------------

def test_valid_request_constructs():
    req = DecisionRequest(TYPE_A, "test_subject", "SUBJ-001", HORIZON)
    assert req.decision_type == TYPE_A
    assert req.decision_horizon.tzinfo is not None


@pytest.mark.parametrize("field_name", ["decision_type", "subject_type", "subject_id"])
@pytest.mark.parametrize("bad", ["", "   ", None, 42])
def test_request_rejects_empty_identifiers(field_name, bad):
    kwargs = dict(
        decision_type=TYPE_A,
        subject_type="test_subject",
        subject_id="SUBJ-001",
        decision_horizon=HORIZON,
    )
    kwargs[field_name] = bad
    with pytest.raises(InvalidDecisionRequest):
        DecisionRequest(**kwargs)


def test_request_rejects_naive_datetime():
    naive = datetime(2026, 2, 1, 0, 0, 0)
    with pytest.raises(InvalidDecisionRequest, match="timezone-aware"):
        DecisionRequest(TYPE_A, "test_subject", "SUBJ-001", naive)


def test_request_accepts_non_utc_timezone():
    tz = timezone(timedelta(hours=-7))
    req = DecisionRequest(TYPE_A, "s", "i", datetime(2026, 2, 1, tzinfo=tz))
    assert req.decision_horizon.tzinfo is tz


def test_caller_cannot_supply_executor_outputs():
    """outcome_code / reason_code / matched_rule_id are not request fields."""
    for forbidden in ("outcome_code", "reason_code", "matched_rule_id"):
        with pytest.raises(TypeError):
            DecisionRequest(
                decision_type=TYPE_A,
                subject_type="s",
                subject_id="i",
                decision_horizon=HORIZON,
                **{forbidden: "SOMETHING"},
            )


# -- B. immutability -----------------------------------------------------

def test_request_is_frozen():
    req = DecisionRequest(TYPE_A, "s", "i", HORIZON)
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.decision_type = "OTHER"


def test_context_is_frozen():
    ctx = make_context()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.request = None


def test_fold_property_is_frozen():
    prop = make_property("p", "v")
    with pytest.raises(dataclasses.FrozenInstanceError):
        prop.resolved_value = "tampered"


def test_snapshot_properties_mapping_is_read_only():
    ctx = make_context(properties={"p": make_property("p", "v")})
    with pytest.raises(TypeError):
        ctx.fold.properties["p"] = make_property("p", "tampered")
    with pytest.raises(TypeError):
        del ctx.fold.properties["p"]


def test_domain_facts_mapping_is_read_only():
    ctx = make_context(facts={"flag": True})
    with pytest.raises(TypeError):
        ctx.facts.facts["flag"] = None


def test_basis_assertion_ids_must_be_tuple_not_list():
    """A list would be mutable through the frozen dataclass."""
    with pytest.raises(InvalidDecisionContext, match="tuple"):
        FoldProperty(
            property_name="p",
            resolved_value="v",
            property_value_type="string",
            fold_state=FoldState.ESTABLISHED,
            basis_assertion_ids=["a-1"],
        )


# -- C. Fold property preservation ---------------------------------------

def test_all_seven_fold_fields_are_preserved():
    prop = make_property("geo_like", "VALUE", assertions=("a-9", "a-2"))
    assert prop.property_name == "geo_like"
    assert prop.resolved_value == "VALUE"
    assert prop.property_value_type == "string"
    assert prop.fold_state is FoldState.ESTABLISHED
    assert prop.effective_at is not None
    assert prop.latest_known_arrival_at is not None
    assert prop.basis_assertion_ids == ("a-9", "a-2")


def test_all_five_governed_states_are_representable():
    for state in FoldState:
        prop = FoldProperty("p", None, None, state)
        assert prop.fold_state is state
    names = {s.value for s in FoldState}
    assert {"ESTABLISHED", "UNREPORTED", "EXPLICITLY_UNDEFINED", "CONTRADICTED"} <= names


def test_unknown_fold_state_rejected():
    with pytest.raises(InvalidDecisionContext, match="unknown fold_state"):
        FoldState.parse("PROBABLY_FINE")


def test_lineage_is_not_flattened_away():
    ctx = make_context(
        properties={"p": make_property("p", "v", assertions=("a-3", "a-1", "a-2"))}
    )
    prop = ctx.property_named("p")
    assert prop.basis_assertion_ids == ("a-3", "a-1", "a-2")
    assert prop.effective_at is not None
    assert prop.latest_known_arrival_at is not None


def test_naive_timestamps_rejected_on_fold_property():
    with pytest.raises(InvalidDecisionContext, match="timezone-aware"):
        FoldProperty(
            "p", "v", "string", FoldState.ESTABLISHED,
            effective_at=datetime(2026, 2, 1),
        )


def test_snapshot_key_must_agree_with_property_name():
    with pytest.raises(InvalidDecisionContext, match="disagrees"):
        FoldSnapshotView(
            fold_state_id="fs-1",
            subject_type="s",
            subject_id="i",
            decision_horizon=HORIZON,
            fold_status=FoldState.ESTABLISHED,
            kb_version="1.0.1",
            policy_version="P-1",
            properties={"wrong_key": make_property("actual_name", "v")},
        )


# -- context consistency --------------------------------------------------

def test_context_rejects_subject_id_mismatch():
    from decisions import DecisionContext

    with pytest.raises(InvalidDecisionContext, match="subject_id mismatch"):
        DecisionContext(
            request=DecisionRequest(TYPE_A, "test_subject", "SUBJ-001", HORIZON),
            fold=FoldSnapshotView(
                fold_state_id="fs-1",
                subject_type="test_subject",
                subject_id="SUBJ-999",  # disagrees with the request
                decision_horizon=HORIZON,
                fold_status=FoldState.ESTABLISHED,
                kb_version="1.0.1",
                policy_version="P-1",
            ),
            governance=GovernanceBinding("O-1", "1.0.1", "P-1"),
        )


def test_context_rejects_horizon_mismatch():
    from decisions import DecisionContext

    other = HORIZON + timedelta(days=1)
    with pytest.raises(InvalidDecisionContext, match="decision_horizon mismatch"):
        DecisionContext(
            request=DecisionRequest(TYPE_A, "test_subject", "SUBJ-001", HORIZON),
            fold=FoldSnapshotView(
                fold_state_id="fs-1",
                subject_type="test_subject",
                subject_id="SUBJ-001",
                decision_horizon=other,
                fold_status=FoldState.ESTABLISHED,
                kb_version="1.0.1",
                policy_version="P-1",
            ),
            governance=GovernanceBinding("O-1", "1.0.1", "P-1"),
        )


def test_governance_versions_are_independent():
    gov = GovernanceBinding(
        ontology_version="O-9", kb_version="1.0.1", policy_version="P-3"
    )
    assert (gov.ontology_version, gov.kb_version, gov.policy_version) == (
        "O-9", "1.0.1", "P-3",
    )


# -- rule definition validation ------------------------------------------

def test_rule_definition_requires_kb_version_in_key():
    definition = RuleDefinition(TYPE_A, "IR-001", "1.0.1", RuleClass.MATCH, 10, "OUT")
    assert definition.key == (TYPE_A, "IR-001", "1.0.1")


def test_same_rule_id_different_kb_version_are_distinct_identities():
    a = RuleDefinition(TYPE_A, "IR-001", "1.0", RuleClass.MATCH, 10, "OUT_A")
    b = RuleDefinition(TYPE_A, "IR-001", "1.0.1", RuleClass.MATCH, 10, "OUT_B")
    assert a.key != b.key


@pytest.mark.parametrize("bad_precedence", ["10", 1.5, True, None])
def test_rule_definition_rejects_non_int_precedence(bad_precedence):
    with pytest.raises(InvalidRuleDefinition):
        RuleDefinition(TYPE_A, "R", "1.0.1", RuleClass.MATCH, bad_precedence, "OUT")


def test_rule_definition_rejects_non_ruleclass():
    with pytest.raises(InvalidRuleDefinition, match="rule_class"):
        RuleDefinition(TYPE_A, "R", "1.0.1", "GUARD", 10, "OUT")
