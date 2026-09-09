"""Unit tests for the coordination agent. No database, no network.

Every case here is constructed in memory, so these assert the RULES rather than
the current contents of one deployment. The rules are the part that must not
drift: an agent that quietly starts guessing an owner, or picking between two
contradictory decisions, would look fine in a demo and be wrong in a way nobody
notices until it matters.
"""

from __future__ import annotations

import pytest

from decisions.domains.claris.agent.case import CaseContext, is_simulated_actor
from decisions.domains.claris.agent.communication import (
    CHANNELS,
    COMMUNICATION_TYPES,
    STATUS_DRAFT,
    draft_for,
)
from decisions.domains.claris.agent.coordination import (
    ACTIONS,
    STATUSES,
    analyse,
    build_journey,
)

GOVERNED_OUTCOMES = {
    "CREATE_PRODUCT", "CREATE_CONFIGURATION", "NEW_VERSION",
    "NO_BUSINESS_CHANGE", "USE_EXISTING", "CANNOT_DECIDE",
}

GOVERNANCE = {
    "ontology_version": "2026.10-prototype.2",
    "kb_version": "2026.10-prototype.2",
    "release_class": "PROTOTYPE",
    "governance_basis": "PROTOTYPE_ASSUMPTION",
    "validation_status": "TO_BE_VALIDATED_WITH_CLARIS",
    "content_digest": "21af9be6",
    "bound_decision_types": ({"decision": "IDENTITY_ASSESSMENT"},),
}

UNOWNED_DIMENSIONS = (
    {"dimension": "customer_segment", "label": "Customer segment",
     "identity_affecting": "UNKNOWN", "governance_state": "PROPOSED",
     "blocks_identity_assessment": True, "owner": None, "authority": None,
     "status": "proposed"},
)

OWNED_DIMENSIONS = (
    {"dimension": "customer_segment", "label": "Customer segment",
     "identity_affecting": "UNKNOWN", "governance_state": "PROPOSED",
     "blocks_identity_assessment": True, "owner": "Product Management",
     "authority": "Product Management", "status": "proposed"},
)

OPEN_Q002 = ({"note_id": "Q-002", "topic": "identity_dimensions",
              "question": "Who owns the identity dimensions?",
              "owner": "Product Management", "status": "OPEN"},)


def _decision(outcome, state="current", **overrides):
    decision = {
        "decision_id": overrides.get("decision_id", "dec-1"),
        "decision_type": "IDENTITY_ASSESSMENT",
        "subject_type": "configuration_request",
        "subject_id": "CONFIG-REQ-2026-001",
        "outcome_code": outcome,
        "reason_code": overrides.get("reason_code", "EXACT_IDENTITY_MATCH"),
        "matched_rule_id": overrides.get("matched_rule_id", "IA-PRED-004"),
        "matched_rule_class": "MATCH",
        "matched_rule_kb_version": "2026.10-prototype.2",
        "confidence_level": "HIGH",
        "missing_evidence": overrides.get("missing_evidence", []),
        "blocking_evidence": overrides.get("blocking_evidence", []),
        "ontology_version": "2026.10-prototype.2",
        "kb_version": "2026.10-prototype.2",
        "policy_version": None,
        "governance_basis": "PROTOTYPE_ASSUMPTION",
        "execution_mode": "PROTOTYPE",
        "input_digest": "v1:sha256:" + "0" * 64,
        "fold_state_id": "fold-1",
        "state": state,
        "superseded_by": None,
        "superseded_at": None,
        "decided_at": overrides.get("decided_at", "2026-09-08T21:02:22Z"),
        "decided_by": "vertical-slice",
        "horizon_as_of": "2026-06-20T10:45:00Z",
    }
    decision.update({k: v for k, v in overrides.items() if k in decision})
    return decision


def _case(decisions=(), identity_states=None, dimensions=UNOWNED_DIMENSIONS,
          **overrides):
    states = identity_states or {
        "product_reference": "ESTABLISHED", "geography": "ESTABLISHED",
        "term_months": "ESTABLISHED", "customer_segment": "ESTABLISHED"}
    defaults = dict(
        subject_id="CONFIG-REQ-2026-001",
        subject_type="configuration_request",
        decision_horizon="2026-06-20T10:45:00Z",
        fold_status="ESTABLISHED",
        identity_tuple={"product_reference": "PROD-001", "geography": "NAMER",
                        "term_months": "36", "customer_segment": "enterprise"},
        identity_states=states,
        decisions=tuple(decisions),
        evidence=(),
        dimension_governance=dimensions,
        governance=GOVERNANCE,
        open_questions=OPEN_Q002,
        launch={"launch_id": "LAUNCH-001", "observed": True,
                "intent_classification": "market_expansion",
                "requested_by_role": "product_manager",
                "requested_by_actor": None,
                "requested_by_actor_raw": "SIMULATED/product-manager"},
    )
    defaults.update(overrides)
    return CaseContext(**defaults)


# ======================================================================
# the agent must never conclude a governed outcome
# ======================================================================

def test_no_status_is_a_governed_outcome():
    """The vocabularies must not overlap.

    If a status were ever spelled CREATE_CONFIGURATION, a reader could not tell
    an agent's reading from a governance decision -- which is the whole
    distinction this layer exists to keep.
    """
    assert not (set(STATUSES) & GOVERNED_OUTCOMES)


def test_no_recommended_action_is_a_governed_outcome():
    assert not (set(ACTIONS) & GOVERNED_OUTCOMES)


@pytest.mark.parametrize("outcome", sorted(GOVERNED_OUTCOMES))
def test_analysis_reports_outcomes_it_never_invents_them(outcome):
    result = analyse(_case([_decision(outcome)]))
    assert result.overall_status in STATUSES
    assert result.recommended_next_action in ACTIONS


# ======================================================================
# no governed decision
# ======================================================================

def test_no_decision_routes_to_a_human():
    result = analyse(_case([]))
    assert result.overall_status == "NO_GOVERNED_DECISION"
    assert result.blocked is True
    assert result.recommended_next_action == "HUMAN_REVIEW"
    assert "CONFIG-REQ-2026-001" in result.needs_review


# ======================================================================
# two current decisions -- the replay condition
# ======================================================================

def test_two_current_decisions_are_reported_not_resolved():
    result = analyse(_case([
        _decision("CREATE_CONFIGURATION", decision_id="dec-1"),
        _decision("NO_BUSINESS_CHANGE", decision_id="dec-2"),
    ]))
    assert result.overall_status == "AMBIGUOUS_GOVERNANCE"
    assert result.blocked is True
    assert result.recommended_next_action == "RESOLVE_GOVERNANCE_AMBIGUITY"
    assert set(result.blocking_decisions) == {"dec-1", "dec-2"}
    # both outcomes must be named; picking one is exactly what it must not do
    assert "CREATE_CONFIGURATION" in result.explanation
    assert "NO_BUSINESS_CHANGE" in result.explanation


def test_a_superseded_decision_does_not_create_ambiguity():
    result = analyse(_case([
        _decision("CREATE_CONFIGURATION", state="superseded", decision_id="old"),
        _decision("NO_BUSINESS_CHANGE", decision_id="new"),
    ]))
    assert result.overall_status == "NO_BUSINESS_CHANGE_CONFIRMED"
    assert result.blocked is False


# ======================================================================
# CANNOT_DECIDE -- and who to ask
# ======================================================================

def test_cannot_decide_with_no_governed_owner_asks_for_an_owner():
    """The prototype release carries owner=NULL on every dimension.

    The agent must NOT route this to a plausible-sounding team. It must say the
    owner is not established, name the open question, and make establishing
    ownership the recommended action.
    """
    result = analyse(_case(
        [_decision("CANNOT_DECIDE", reason_code="MISSING_REQUIRED_INPUT",
                   matched_rule_id="IA-PRED-001",
                   missing_evidence=["customer_segment"])],
        identity_states={"product_reference": "ESTABLISHED",
                         "geography": "ESTABLISHED",
                         "term_months": "ESTABLISHED",
                         "customer_segment": "UNREPORTED"}))
    assert result.overall_status == "BLOCKED_MISSING_EVIDENCE"
    assert result.blocked is True
    assert result.missing_evidence == ("customer_segment",)
    assert result.recommended_next_action == "ESTABLISH_DECISION_OWNER"
    assert "NOT ESTABLISHED" in result.owner_basis
    assert "Q-002" in result.owner_basis


def test_cannot_decide_with_a_governed_owner_requests_evidence_from_them():
    result = analyse(_case(
        [_decision("CANNOT_DECIDE", reason_code="MISSING_REQUIRED_INPUT",
                   matched_rule_id="IA-PRED-001",
                   missing_evidence=["customer_segment"])],
        dimensions=OWNED_DIMENSIONS,
        identity_states={"product_reference": "ESTABLISHED",
                         "geography": "ESTABLISHED",
                         "term_months": "ESTABLISHED",
                         "customer_segment": "UNREPORTED"}))
    assert result.recommended_next_action == "REQUEST_EVIDENCE"
    assert result.current_owner_role == "Product Management"
    assert result.owner_basis.startswith("governed:")


def test_contradicted_input_is_reported_as_contradiction_not_absence():
    result = analyse(_case(
        [_decision("CANNOT_DECIDE", reason_code="CONTRADICTED_REQUIRED_INPUT",
                   matched_rule_id="IA-PRED-002",
                   blocking_evidence=["geography"])],
        identity_states={"product_reference": "ESTABLISHED",
                         "geography": "CONTRADICTED",
                         "term_months": "ESTABLISHED",
                         "customer_segment": "ESTABLISHED"}))
    assert result.overall_status == "BLOCKED_CONTRADICTED_EVIDENCE"
    assert "disagree" in result.explanation


def test_cannot_decide_never_reports_a_canonical_effect():
    result = analyse(_case(
        [_decision("CANNOT_DECIDE", missing_evidence=["customer_segment"])]))
    assert result.cleared_decisions == ()


# ======================================================================
# cleared outcomes
# ======================================================================

def test_create_configuration_is_established_and_not_blocked():
    result = analyse(_case([_decision("CREATE_CONFIGURATION")]))
    assert result.overall_status == "GOVERNED_IDENTITY_ESTABLISHED"
    assert result.blocked is False
    assert result.recommended_next_action == "NO_ACTION_REQUIRED"


def test_no_business_change_is_its_own_status():
    result = analyse(_case([_decision("NO_BUSINESS_CHANGE")]))
    assert result.overall_status == "NO_BUSINESS_CHANGE_CONFIRMED"
    assert result.blocked is False


def test_a_cleared_case_does_not_claim_launch_readiness():
    """No decision type for launch readiness is executable in this release.

    The agent must not imply the launch is ready just because identity was
    settled -- that is a different governed question nobody has asked.
    """
    result = analyse(_case([_decision("CREATE_CONFIGURATION")]))
    assert "READY" not in result.overall_status
    assert "cannot say whether" in result.explanation


def test_unknown_outcome_is_routed_to_a_human_not_guessed():
    result = analyse(_case([_decision("SOMETHING_NEW")]))
    assert result.overall_status == "CANNOT_DETERMINE"
    assert result.recommended_next_action == "HUMAN_REVIEW"


# ======================================================================
# actors
# ======================================================================

@pytest.mark.parametrize("actor", [
    "SIMULATED/product-manager", "config_governance_system", "SYSTEM",
    "vertical-slice", None, "",
])
def test_simulation_markers_are_not_people(actor):
    assert is_simulated_actor(actor) is True


def test_a_real_looking_actor_is_allowed_through():
    assert is_simulated_actor("daniel.park@example.com") is False


def test_the_launch_actor_is_never_the_raw_simulation_marker():
    result = analyse(_case([_decision("CREATE_CONFIGURATION")]))
    assert result.current_owner_actor is None
    assert result.current_owner_role == "product_manager"


# ======================================================================
# communication
# ======================================================================

def test_every_draft_is_a_draft_on_an_allowed_channel():
    for outcome in ("CANNOT_DECIDE", "CREATE_CONFIGURATION",
                    "NO_BUSINESS_CHANGE", "SOMETHING_NEW"):
        case = _case([_decision(outcome, missing_evidence=["customer_segment"]
                                if outcome == "CANNOT_DECIDE" else [])])
        for draft in draft_for(case, analyse(case)):
            assert draft.status == STATUS_DRAFT
            assert draft.channel in CHANNELS
            assert draft.communication_type in COMMUNICATION_TYPES


def test_a_draft_never_invents_a_recipient():
    case = _case([_decision("CANNOT_DECIDE",
                            missing_evidence=["customer_segment"])])
    drafts = draft_for(case, analyse(case))
    assert drafts
    for draft in drafts:
        assert draft.to_actor is None
        assert draft.to_role is not None or "not been established" in draft.body


def test_a_draft_carries_the_prototype_warning():
    case = _case([_decision("CREATE_CONFIGURATION")])
    for draft in draft_for(case, analyse(case)):
        assert "PROTOTYPE ASSUMPTION" in draft.body
        assert "2026.10-prototype.2" in draft.body


def test_a_draft_never_claims_to_have_been_sent():
    case = _case([_decision("CANNOT_DECIDE",
                            missing_evidence=["customer_segment"])])
    for draft in draft_for(case, analyse(case)):
        assert "sent" not in draft.body.lower().replace("presented", "")
        assert draft.status != "SENT"


def test_draft_ids_are_stable_for_an_unchanged_case():
    case = _case([_decision("CANNOT_DECIDE",
                            missing_evidence=["customer_segment"])])
    first = [d.communication_id for d in draft_for(case, analyse(case))]
    second = [d.communication_id for d in draft_for(case, analyse(case))]
    assert first == second


def test_a_cleared_case_produces_a_note_and_nothing_to_chase():
    case = _case([_decision("NO_BUSINESS_CHANGE")])
    drafts = draft_for(case, analyse(case))
    assert len(drafts) == 1
    assert drafts[0].communication_type == "NOTE"


# ======================================================================
# journey
# ======================================================================

def test_journey_reports_only_what_was_observed():
    case = _case([_decision("CREATE_CONFIGURATION")])
    journey = build_journey(case)
    events = [entry.event for entry in journey]
    # no fabricated stages: the corpus has no pricing or approval evidence here
    assert not any("Pricing" in event for event in events)
    assert any("IDENTITY_ASSESSMENT" in event for event in events)


def test_journey_marks_a_superseded_decision_as_superseded():
    case = _case([
        _decision("CREATE_CONFIGURATION", state="superseded", decision_id="old"),
        _decision("NO_BUSINESS_CHANGE", decision_id="new"),
    ])
    statuses = {entry.status for entry in build_journey(case)
                if entry.role == "platform"}
    assert "superseded" in statuses
    assert "current" in statuses
