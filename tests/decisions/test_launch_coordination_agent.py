"""The launch coordination agent, exercised without a database.

The agent's value is entirely in what it refuses to do. These tests assert the
refusals as hard as the behaviour: it cannot decide readiness, cannot upgrade
manufactured evidence, cannot name a person, and cannot send anything.
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from decisions.agents.claris.launch_coordination_agent import (  # noqa: E402
    ACTIONS, CHANNELS, CHANNEL_EMAIL_DRAFT, CHANNEL_NOTE, RESPONSIBLE_ROLE,
    STATUS_DRAFT, LaunchCoordinationAgent, is_authorized,
)
from decisions.agents.claris.launch_coordination_agent.reasoning import (  # noqa: E402
    blockers_for, recommend_for, waiting_on_for,
)
from decisions.domains.claris.readiness import evaluate_all  # noqa: E402

HORIZON = "2026-07-31 00:00:00+00"


def prop(value, provenance="OBSERVED", fold_state="ESTABLISHED",
         effective_at="2026-06-15T15:00:00+00:00",
         arrival_at="2026-06-15T15:30:00+00:00"):
    return {"fold_state": fold_state, "value": value,
            "provenance": provenance, "basis_count": 1,
            "defaulted_count": 1 if provenance == "DEFAULTED" else 0,
            "effective_at": effective_at, "arrival_at": arrival_at}


DEFAULTED_PASS = {
    "sku_status": prop("MINTED"),
    "technical_review_result": prop("PASS", "DEFAULTED"),
    "pricing_status": prop("DETERMINED"),
    "pricing_value_usd": prop("350000.0"),
    "final_pricing_approval_status": prop("APPROVED"),
}
REJECTED = {"technical_review_result": prop("REJECTED"),
            "sku_activation_status": prop("ACTIVATED")}
NOTHING = {"sku_status": prop("MINTED")}


class StubDB:
    """Serves runtime.property_provenance_at for a fixed set of subjects."""

    def __init__(self, subjects):
        self.subjects = subjects

    def query(self, sql, params=None):
        if "DISTINCT subject_id" in sql:
            return [{"subject_id": s} for s in sorted(self.subjects)]
        rows = []
        for subject_id, props in sorted(self.subjects.items()):
            for name, p in sorted(props.items()):
                rows.append({"subject_id": subject_id, "property_name": name,
                             "fold_state": p["fold_state"], "value": p["value"],
                             "value_provenance": p["provenance"],
                             "basis_count": p["basis_count"],
                             "defaulted_count": p["defaulted_count"],
                             "effective_at": p["effective_at"],
                             "latest_known_arrival_at": p["arrival_at"]})
        return rows


def agent(subjects):
    return LaunchCoordinationAgent(StubDB(subjects), horizon=HORIZON)


# -- the agent reports decisions, it does not make them ----------------------

def test_agent_outcome_equals_the_governed_decision():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    governed = evaluate_all("SKU-004", DEFAULTED_PASS)
    for view in result.case.readiness:
        assert view.outcome == governed[view.decision_type].outcome


def test_agent_cannot_upgrade_manufactured_evidence():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    technical = result.case.readiness_named("TECHNICAL_READINESS")
    assert technical.outcome == "CANNOT_DECIDE"
    assert "technical_review_result" in technical.insufficient_evidence
    assert "ready" not in result.headline.lower() or "cannot" in result.headline


def test_every_readiness_view_carries_its_policy_version():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    assert all(v.policy_version.startswith("READINESS-v")
               for v in result.case.readiness)


# -- blockers are typed, and the type drives the action ----------------------

def test_manufactured_evidence_asks_for_confirmation_not_for_the_fact():
    decisions = evaluate_all("SKU-004", DEFAULTED_PASS)
    blockers = blockers_for(decisions)
    worst = blockers[0]
    assert worst.kind == "MANUFACTURED_EVIDENCE"
    rec = recommend_for(decisions, blockers, waiting_on_for(blockers))
    assert rec.action == "REQUEST_DECISION"
    assert "no source asserted it" in worst.statement


def test_observed_failure_escalates_and_says_waiting_will_not_help():
    decisions = evaluate_all("SKU-013", REJECTED)
    blockers = blockers_for(decisions)
    assert blockers[0].kind == "OBSERVED_FAILURE"
    rec = recommend_for(decisions, blockers, waiting_on_for(blockers))
    assert rec.action == "ESCALATE"
    assert "will not clear by waiting" in rec.statement


def test_absent_evidence_requests_it():
    decisions = evaluate_all("SKU-006", NOTHING)
    blockers = blockers_for(decisions)
    rec = recommend_for(decisions, blockers, waiting_on_for(blockers))
    assert rec.action == "REQUEST_EVIDENCE"


def test_observed_failure_outranks_manufactured_and_absent():
    mixed = dict(DEFAULTED_PASS, technical_review_result=prop("REJECTED"))
    blockers = blockers_for(evaluate_all("X", mixed))
    assert blockers[0].kind == "OBSERVED_FAILURE"


def test_every_recommended_action_is_in_the_closed_list():
    for props in (DEFAULTED_PASS, REJECTED, NOTHING, {}):
        decisions = evaluate_all("X", props)
        blockers = blockers_for(decisions)
        rec = recommend_for(decisions, blockers, waiting_on_for(blockers))
        assert is_authorized(rec.action), rec.action
        assert rec.action in ACTIONS


# -- owners: a role, never a person ------------------------------------------

def test_waiting_on_names_a_role_and_no_actor():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    assert result.waiting_on.role == "Technical Review"
    assert result.waiting_on.actor is None


def test_owner_uncertainty_is_cited_not_resolved():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    assert "Q-002" in result.waiting_on.open_question
    assert result.waiting_on.governance_basis == "PROTOTYPE_ASSUMPTION"


def test_no_simulated_actor_becomes_an_owner_or_recipient():
    """An actor id may appear as EVIDENCE. It may never become a party.

    go_live_approved_by genuinely reads SIMULATED/exec in the corpus, and
    hiding observed evidence would be worse than showing it. What must not
    happen is that id turning into someone the case is waiting on, or someone
    a draft is addressed to.
    """
    props = dict(DEFAULTED_PASS,
                 go_live_approved_by=prop("SIMULATED/exec"),
                 pricing_published_by=prop("SIMULATED/pricing"))
    result = agent({"SKU-004": props}).run("SKU-004")
    assert result.waiting_on.actor is None
    assert all(c.to_actor is None for c in result.communications)
    assert "SIMULATED/" not in result.headline
    assert "SIMULATED/" not in result.recommendation.statement
    for draft in result.communications:
        assert "SIMULATED/" not in draft.subject
        assert "SIMULATED/" not in draft.body


def test_simulated_actor_values_are_flagged_not_hidden():
    props = dict(DEFAULTED_PASS, go_live_approved_by=prop("SIMULATED/exec"))
    result = agent({"SKU-004": props}).run("SKU-004")
    entry = result.case.properties["go_live_approved_by"]
    assert entry["value"] == "SIMULATED/exec", "evidence must not be erased"
    assert entry["simulated_actor"] is True
    assert entry["is_actor_reference"] is True


def test_a_real_actor_value_would_not_be_flagged_as_simulated():
    props = dict(DEFAULTED_PASS, go_live_approved_by=prop("a.patel"))
    result = agent({"SKU-004": props}).run("SKU-004")
    assert result.case.properties["go_live_approved_by"]["simulated_actor"] is False


@pytest.mark.parametrize("property_name", sorted(RESPONSIBLE_ROLE))
def test_every_routed_role_is_a_role_not_a_name(property_name):
    role = RESPONSIBLE_ROLE[property_name]
    assert role and role[0].isupper()
    assert "@" not in role and "/" not in role


# -- communication: drafts only ----------------------------------------------

def test_a_note_is_always_drafted():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    notes = [c for c in result.communications if c.channel == CHANNEL_NOTE]
    assert len(notes) == 1


def test_email_draft_addresses_a_role_and_stays_a_draft():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    emails = [c for c in result.communications
              if c.channel == CHANNEL_EMAIL_DRAFT]
    assert len(emails) == 1
    assert emails[0].to_role == "Technical Review"
    assert emails[0].to_actor is None
    assert emails[0].status == STATUS_DRAFT
    assert "not sent" in emails[0].body


def test_every_communication_is_a_draft_on_an_allowed_channel():
    for subject, props in (("SKU-004", DEFAULTED_PASS), ("SKU-013", REJECTED),
                           ("SKU-006", NOTHING)):
        result = agent({subject: props}).run(subject)
        for draft in result.communications:
            assert draft.channel in CHANNELS
            assert draft.status == STATUS_DRAFT


def test_communication_ids_are_stable_across_runs():
    first = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    second = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    assert ([c.communication_id for c in first.communications]
            == [c.communication_id for c in second.communications])


# -- journey -----------------------------------------------------------------

def test_journey_runs_evidence_to_handoff_and_ends_with_a_person():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    stages = [step["stage"] for step in result.journey]
    assert stages[0] == "EVIDENCE"
    assert stages[-1] == "HANDOFF"
    assert "GOVERNED DECISION" in stages
    assert "a person decides" in result.journey[-1]["statement"]


def test_journey_is_not_a_workflow():
    result = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    blob = str(result.journey)
    for step in ("S1", "S5", "S16", "S19"):
        assert step not in blob


# -- determinism and shape ---------------------------------------------------

def test_repeated_runs_are_identical():
    a = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    b = agent({"SKU-004": DEFAULTED_PASS}).run("SKU-004")
    assert a.as_dict() == b.as_dict()


def test_unknown_subject_returns_nothing_rather_than_a_guess():
    assert agent({"SKU-004": DEFAULTED_PASS}).run("SKU-999") is None


def test_run_all_covers_every_subject():
    subjects = {"SKU-004": DEFAULTED_PASS, "SKU-013": REJECTED,
                "SKU-006": NOTHING}
    results = agent(subjects).run_all()
    assert sorted(r.case.subject_id for r in results) == sorted(subjects)


def test_stub_answers_every_column_the_loader_selects():
    """Guards the fixture against the query drifting away from it.

    This suite went red once because effective_at was added to the loader's
    SELECT for the Workbench and the stub was not updated -- the live path was
    fine and only the fixture was stale. Parsing the real SQL keeps the two in
    step.
    """
    import re
    from decisions.agents.claris.launch_coordination_agent import context
    select = context._PROPERTY_SQL.split("FROM")[0]
    aliased = set(re.findall(r"AS\s+(\w+)", select))
    plain = {line.strip().rstrip(",")
             for line in select.splitlines()[1:]
             if line.strip() and " AS " not in line
             and "#>>" not in line and "SELECT" not in line}
    expected = {c for c in aliased | plain if c and c.isidentifier()}
    row = StubDB({"SKU-004": DEFAULTED_PASS}).query(
        context._PROPERTY_SQL, (HORIZON, "sku"))[0]
    missing = expected - set(row)
    assert not missing, f"stub is missing columns the loader reads: {missing}"
