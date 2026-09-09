"""How the agent turns governed decisions into blockers, an owner and an action.

THE BOUNDARY THIS FILE DEFENDS
    Every statement here is derived from a readiness decision that already
    exists. The agent never decides whether a SKU is ready, never reclassifies
    evidence, never resolves a contradiction and never converts an absent fact
    into a present one. If the governed decision says CANNOT_DECIDE, the agent
    explains why it cannot be decided -- it does not decide it.

WHAT IS GENUINELY THE AGENT'S OWN
    Two things, and both are declared rather than inferred:
      * the routing table below, which maps a blocking property to the role
        responsible for supplying it. That is coordination knowledge, not a
        business fact, and it is marked PROTOTYPE_ASSUMPTION because Claris has
        not confirmed it.
      * the choice of which single action to recommend, from a closed list.
"""

from __future__ import annotations

from typing import Optional

from .actions import (ADD_NOTE, AWAIT_EVIDENCE, ESCALATE, NO_ACTION,
                      REQUEST_EVIDENCE, REQUEST_REVIEW)
from .models import Blocker, Recommendation, WaitingOn

__all__ = ["RESPONSIBLE_ROLE", "blockers_for", "waiting_on_for",
           "recommend_for", "headline_for", "journey_for"]

#: property -> role responsible for supplying it.
#: PROTOTYPE_ASSUMPTION. Claris has not confirmed these, and Q-002 (who owns a
#: decision) is open. A role is the most this may ever name: the corpus carries
#: only simulated actor ids, so naming a person would be inventing one.
RESPONSIBLE_ROLE = {
    "technical_review_result": "Technical Review",
    "sku_status": "SAP Operations",
    "sku_activation_status": "SAP Operations",
    "pricing_status": "Pricing",
    "pricing_value_usd": "Pricing",
    "pricing_approval": "Finance",
    "final_pricing_approval_status": "Finance",
    "pricing_confirmed": "Finance",
    "pricing_upload_status": "Pricing Operations",
    "pricing_publication_status": "Pricing Operations",
    "zupdm_approval_status": "Master Data",
    "all_gates_cleared": "Launch Governance",
    "go_live_approval_status": "Launch Governance",
    "material_activation_status": "Supply Chain",
    "supply_chain_notification_status": "Supply Chain",
}

OPEN_QUESTION_OWNER = ("Q-002 -- decision ownership is not established for "
                       "this dimension; the role below is a prototype "
                       "assumption, not confirmed Claris policy")

_KIND_FOR_STATUS = {
    "FAILED": "OBSERVED_FAILURE",
    "INSUFFICIENT_PROVENANCE": "MANUFACTURED_EVIDENCE",
    "MISSING": "ABSENT_EVIDENCE",
    "CONTRADICTED": "CONTRADICTED_EVIDENCE",
    "UNRECOGNISED_VALUE": "ABSENT_EVIDENCE",
}

#: Worst first. An observed failure outranks a manufactured value, which
#: outranks silence: a thing known to have failed is more actionable than a
#: thing not yet known.
_KIND_RANK = {
    "OBSERVED_FAILURE": 0,
    "CONTRADICTED_EVIDENCE": 1,
    "MANUFACTURED_EVIDENCE": 2,
    "ABSENT_EVIDENCE": 3,
    "SUBORDINATE": 4,
}


def _statement(finding, decision_type: str) -> str:
    name = finding.property_name
    if finding.status == "FAILED":
        return (f"{name} was observed as {finding.value!r}, which fails "
                f"{decision_type}")
    if finding.status == "INSUFFICIENT_PROVENANCE":
        return (f"{name} reads {finding.value!r}, but no source asserted it -- "
                f"the value was supplied by a projection default, so it cannot "
                f"evidence {decision_type}")
    if finding.status == "CONTRADICTED":
        return f"sources disagree about {name}; nobody has reconciled them"
    if finding.status == "UNRECOGNISED_VALUE":
        return (f"{name} reads {finding.value!r}, which is not a value this "
                f"gate classifies")
    return f"no source has reported {name}"


def blockers_for(decisions) -> tuple:
    """Every blocking finding across the governed decisions, worst first.

    decisions is the mapping returned by readiness.evaluate_all.
    """
    found = []
    for decision_type, decision in decisions.items():
        if decision.outcome == "READY":
            continue
        for finding in decision.blocking:
            found.append(Blocker(
                kind=_KIND_FOR_STATUS.get(finding.status, "ABSENT_EVIDENCE"),
                decision_type=decision_type,
                property_name=finding.property_name,
                statement=_statement(finding, decision_type),
                evidence_value=finding.value,
                provenance=finding.provenance,
            ))
        for name, outcome in decision.composed_from:
            if outcome != "READY":
                found.append(Blocker(
                    kind="SUBORDINATE", decision_type=decision_type,
                    property_name=None,
                    statement=f"{name} is {outcome}, so {decision_type} "
                              f"cannot be satisfied"))
    found.sort(key=lambda b: (_KIND_RANK.get(b.kind, 9),
                              b.property_name or "", b.decision_type))
    return tuple(found)


def waiting_on_for(blockers) -> Optional[WaitingOn]:
    """The role responsible for the worst blocker. Never a person.

    A blocker on an actor-valued property (go_live_approved_by and friends)
    still routes to a ROLE. The recorded value there is an actor id, and every
    one of them is simulated in this corpus; treating it as the party to chase
    would turn a simulation artefact into a named owner.
    """
    for blocker in blockers:
        if blocker.kind == "SUBORDINATE" or not blocker.property_name:
            continue
        role = RESPONSIBLE_ROLE.get(blocker.property_name)
        if role is None:
            return WaitingOn(
                role=None, actor=None,
                basis=f"no role is declared for {blocker.property_name}",
                open_question=OPEN_QUESTION_OWNER)
        return WaitingOn(
            role=role, actor=None,
            basis=f"{blocker.property_name} is the highest-ranked blocker and "
                  f"{role} is the declared owner of that input",
            open_question=OPEN_QUESTION_OWNER)
    return None


def recommend_for(decisions, blockers, waiting_on) -> Recommendation:
    """One action, chosen from the closed list, matched to the worst blocker."""
    if not blockers:
        return Recommendation(
            NO_ACTION, "every governed readiness decision is satisfied")

    worst = blockers[0]
    role = waiting_on.role if waiting_on else None

    if worst.kind == "OBSERVED_FAILURE":
        return Recommendation(
            ESCALATE,
            f"escalate to {role or 'the responsible role'}: "
            f"{worst.statement}. This is an observed failure, not a gap -- it "
            f"will not clear by waiting",
            role, worst.property_name)

    if worst.kind == "CONTRADICTED_EVIDENCE":
        return Recommendation(
            ESCALATE,
            f"escalate to {role or 'the responsible role'}: {worst.statement}",
            role, worst.property_name)

    if worst.kind == "MANUFACTURED_EVIDENCE":
        return Recommendation(
            REQUEST_REVIEW,
            f"ask {role or 'the responsible role'} to confirm "
            f"{worst.property_name} explicitly. A value is present but no "
            f"source asserted it, so confirming it is a decision someone must "
            f"actually make rather than a fact to look up",
            role, worst.property_name)

    if worst.kind == "ABSENT_EVIDENCE":
        return Recommendation(
            REQUEST_EVIDENCE,
            f"ask {role or 'the responsible role'} for {worst.property_name}; "
            f"nothing has been reported and the decision cannot be made "
            f"without it",
            role, worst.property_name)

    return Recommendation(
        AWAIT_EVIDENCE,
        "a subordinate readiness decision is unresolved; nothing at this level "
        "can proceed until it is", role)


def headline_for(subject_id: str, decisions, blockers) -> str:
    launch = decisions.get("LAUNCH_READINESS")
    outcome = launch.outcome if launch else "UNKNOWN"
    if outcome == "READY":
        return f"{subject_id} is ready to launch on observed evidence"
    if not blockers:
        return f"{subject_id} is {outcome}"
    worst = blockers[0]
    if worst.kind == "OBSERVED_FAILURE":
        return f"{subject_id} is blocked: {worst.statement}"
    if worst.kind == "MANUFACTURED_EVIDENCE":
        return (f"{subject_id} cannot be decided: {worst.property_name} looks "
                f"satisfied but nothing asserted it")
    return (f"{subject_id} cannot be decided: waiting on "
            f"{worst.property_name or 'a subordinate decision'}")


def journey_for(case, decisions, blockers, recommendation) -> tuple:
    """Evidence -> governed decision -> recommendation -> handoff.

    Deliberately not a workflow. It shows what was observed, what was decided
    from it, and what a person is being asked to do -- never a sequence of
    process steps, because events arrive late and out of order.
    """
    steps = [{
        "stage": "EVIDENCE",
        "statement": (f"{case.established} properties established, "
                      f"{case.defaulted} of them resting on projection "
                      f"defaults, {case.unreported} never reported"),
    }]
    for view in case.readiness:
        steps.append({
            "stage": "GOVERNED DECISION",
            "statement": f"{view.decision_type}: {view.outcome} -- {view.why}",
            "policy_version": view.policy_version,
        })
    if blockers:
        steps.append({
            "stage": "BLOCKER",
            "statement": blockers[0].statement,
            "kind": blockers[0].kind,
        })
    if recommendation:
        steps.append({
            "stage": "RECOMMENDED ACTION",
            "statement": recommendation.statement,
            "action": recommendation.action,
        })
    steps.append({
        "stage": "HANDOFF",
        "statement": ("a person decides and acts; the agent has drafted, not "
                      "sent, and has changed no business fact"),
    })
    return tuple(steps)
