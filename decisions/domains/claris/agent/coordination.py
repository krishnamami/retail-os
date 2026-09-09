"""Coordination and stall analysis. Pure functions over an assembled case.

THE ONE RULE THIS MODULE EXISTS TO ENFORCE
-------------------------------------------
Every status, blocker, owner and recommendation is DERIVED from governed state
by an explicit rule that can be read here and checked against the data. Nothing
is inferred by judgement, and no language model is consulted. If the governed
layer cannot support a conclusion, the conclusion is CANNOT_DETERMINE and the
case is routed to a human -- which is the same discipline the identity
predicates follow, applied one layer up.

The agent is not a decision maker. It never produces CREATE_PRODUCT,
CREATE_CONFIGURATION, NEW_VERSION, NO_BUSINESS_CHANGE, USE_EXISTING,
LAUNCH_READY or BLOCKED-as-an-outcome. Those belong to governed decision
services. What it produces is a reading of decisions that already exist, an
account of what is missing, and a recommendation about who to ask.

WHY "WAITING ON FINANCE" DOES NOT APPEAR FOR THIS CORPUS
---------------------------------------------------------
It would be easy, and wrong. Three things would have to be true and none is:

    1. A governed decision type for pricing or launch readiness would have to be
       EXECUTABLE. claris_kb.decision_rules carries thirteen
       CHANGE_CLASSIFICATION rules and nothing else, and none of them has a
       registered predicate, so no such decision exists to be blocked on.
    2. The pricing evidence in this corpus (pricing_status, pricing_confirmed,
       pricing_value_usd) is recorded against CON-* and SKU-* subjects. The
       requests this platform canonicalized are CONFIG-REQ-* subjects. Nothing
       in the data joins them.
    3. Dimension ownership would have to be established. On the active prototype
       release every dimension carries owner=NULL, and Q-002 -- who owns the
       identity dimensions -- is OPEN.

So this module reports what is genuinely derivable, and names the gap where a
richer answer would require data that does not exist. That refusal is the
product.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

__all__ = [
    "STATUSES",
    "ACTIONS",
    "Coordination",
    "JourneyEntry",
    "analyse",
    "build_journey",
]

# -- closed vocabularies ------------------------------------------------
#
# Closed on purpose. A free-text status is a place for an invented judgement to
# hide; every value below is produced by exactly one rule in `analyse`.

STATUS_IDENTITY_ESTABLISHED = "GOVERNED_IDENTITY_ESTABLISHED"
STATUS_NO_CHANGE = "NO_BUSINESS_CHANGE_CONFIRMED"
STATUS_BLOCKED_MISSING = "BLOCKED_MISSING_EVIDENCE"
STATUS_BLOCKED_CONTRADICTED = "BLOCKED_CONTRADICTED_EVIDENCE"
STATUS_AMBIGUOUS = "AMBIGUOUS_GOVERNANCE"
STATUS_NO_DECISION = "NO_GOVERNED_DECISION"
STATUS_CANNOT_DETERMINE = "CANNOT_DETERMINE"

STATUSES = (STATUS_IDENTITY_ESTABLISHED, STATUS_NO_CHANGE,
            STATUS_BLOCKED_MISSING, STATUS_BLOCKED_CONTRADICTED,
            STATUS_AMBIGUOUS, STATUS_NO_DECISION, STATUS_CANNOT_DETERMINE)

ACTION_REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
ACTION_ESTABLISH_OWNER = "ESTABLISH_DECISION_OWNER"
ACTION_RESOLVE_AMBIGUITY = "RESOLVE_GOVERNANCE_AMBIGUITY"
ACTION_HUMAN_REVIEW = "HUMAN_REVIEW"
ACTION_NONE = "NO_ACTION_REQUIRED"
ACTION_AWAIT_GOVERNANCE = "AWAIT_GOVERNED_DECISION_TYPE"

ACTIONS = (ACTION_REQUEST_EVIDENCE, ACTION_ESTABLISH_OWNER,
           ACTION_RESOLVE_AMBIGUITY, ACTION_HUMAN_REVIEW, ACTION_NONE,
           ACTION_AWAIT_GOVERNANCE)

#: Outcomes that mean the governed layer reached a conclusion and the canonical
#: layer already reflects it.
_CLEARED = frozenset({"CREATE_PRODUCT", "CREATE_CONFIGURATION", "NEW_VERSION",
                      "NO_BUSINESS_CHANGE", "USE_EXISTING"})
_NO_CANONICAL_CHANGE = frozenset({"NO_BUSINESS_CHANGE", "USE_EXISTING"})

IDENTITY_ASSESSMENT = "IDENTITY_ASSESSMENT"


@dataclass(frozen=True)
class Coordination:
    overall_status: str
    blocked: bool
    current_owner_role: Optional[str]
    current_owner_actor: Optional[str]
    owner_basis: str
    waiting_on: Optional[str]
    waiting_since: Any = None
    missing_evidence: tuple = ()
    blocking_decisions: tuple = ()
    cleared_decisions: tuple = ()
    needs_review: tuple = ()
    recommended_next_action: str = ACTION_NONE
    explanation: str = ""
    derivation: tuple = ()

    def as_dict(self) -> dict:
        return {
            "overall_status": self.overall_status,
            "blocked": self.blocked,
            "current_owner_role": self.current_owner_role,
            "current_owner_actor": self.current_owner_actor,
            "owner_basis": self.owner_basis,
            "waiting_on": self.waiting_on,
            "waiting_since": self.waiting_since,
            "missing_evidence": list(self.missing_evidence),
            "blocking_decisions": list(self.blocking_decisions),
            "cleared_decisions": list(self.cleared_decisions),
            "needs_review": list(self.needs_review),
            "recommended_next_action": self.recommended_next_action,
            "explanation": self.explanation,
            "derivation": list(self.derivation),
        }


@dataclass(frozen=True)
class JourneyEntry:
    role: Optional[str]
    actor: Optional[str]
    event: str
    object_affected: Optional[str]
    status: str
    occurred_at: Any
    decision_dependency: Optional[str]
    explanation: str

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "role", "actor", "event", "object_affected", "status",
            "occurred_at", "decision_dependency", "explanation")}


# ======================================================================
# ownership -- from governed metadata, or not at all
# ======================================================================

def _owner_of_dimension(case, dimension: str):
    """(role, actor, basis) for the dimension holding up this case.

    Returns a role only when the ACTIVE release states one. On a prototype
    release every dimension carries owner=NULL, so this returns None with a
    basis that says why -- which is what lets the Workbench show "nobody owns
    this yet, and here is the open question that would settle it" instead of
    routing the request to a team that never agreed to own it.
    """
    for row in case.dimension_governance:
        if row["dimension"] != dimension:
            continue
        if row.get("owner"):
            return row["owner"], None, "governed: configuration_dimensions.owner"
        question = next(
            (q for q in case.open_questions
             if q.get("topic") in ("identity_dimensions", "sellable_definition")
             and q.get("status") == "OPEN"), None)
        if question:
            return None, None, (
                f"NOT ESTABLISHED. {case.governance['ontology_version']} carries "
                f"no owner for {dimension!r}, and {question['note_id']} "
                f"({question['topic']}) is open: {question['question']}")
        return None, None, (
            f"NOT ESTABLISHED. {case.governance['ontology_version']} carries no "
            f"owner for {dimension!r}.")
    return None, None, f"{dimension!r} is not a governed dimension in this release"


def _requesting_role(case):
    if case.launch and case.launch.get("requested_by_role"):
        return (case.launch["requested_by_role"],
                case.launch.get("requested_by_actor"),
                "observed: launch change_requester_role")
    for item in case.evidence:
        if item.get("role"):
            return item["role"], item.get("actor"), "observed: evidence actor role"
    return None, None, "no actor role observed on any evidence for this subject"


# ======================================================================
# the analysis
# ======================================================================

def analyse(case) -> Coordination:
    """Derive coordination state. One rule per branch, all of them auditable."""
    derivation: list = []
    current = case.current_decisions
    identity = current.get(IDENTITY_ASSESSMENT, ())

    # -- no governed decision at all -----------------------------------
    if not identity:
        role, actor, basis = _requesting_role(case)
        derivation.append(
            "no current IDENTITY_ASSESSMENT decision exists for this subject")
        return Coordination(
            overall_status=STATUS_NO_DECISION,
            blocked=True,
            current_owner_role=role, current_owner_actor=actor,
            owner_basis=basis,
            waiting_on="governed evaluation",
            needs_review=(case.subject_id,),
            recommended_next_action=ACTION_HUMAN_REVIEW,
            explanation=(
                "No governed IDENTITY_ASSESSMENT has been recorded for this "
                "change. The platform will not infer one, so the case cannot "
                "advance until the decision is executed."),
            derivation=tuple(derivation))

    # -- more than one current decision --------------------------------
    if len(identity) > 1:
        outcomes = sorted({d["outcome_code"] for d in identity})
        derivation.append(
            f"{len(identity)} decisions claim state='current' for "
            f"{IDENTITY_ASSESSMENT}: outcomes {outcomes}")
        role, actor, basis = _requesting_role(case)
        return Coordination(
            overall_status=STATUS_AMBIGUOUS,
            blocked=True,
            current_owner_role=role, current_owner_actor=actor,
            owner_basis=basis,
            waiting_on="governance",
            missing_evidence=(),
            blocking_decisions=tuple(d["decision_id"] for d in identity),
            needs_review=(case.subject_id,),
            recommended_next_action=ACTION_RESOLVE_AMBIGUITY,
            explanation=(
                f"{len(identity)} IDENTITY_ASSESSMENT decisions are recorded as "
                f"current for this change, concluding {' and '.join(outcomes)}. "
                "The agent will not choose between them: which governed decision "
                "supersedes which is not its call. Re-evaluating the subject "
                "retires the older decision and resolves this."),
            derivation=tuple(derivation))

    decision = identity[0]
    outcome = decision["outcome_code"]
    derivation.append(
        f"current {IDENTITY_ASSESSMENT}: {outcome} "
        f"({decision.get('reason_code')}) via {decision.get('matched_rule_id')}")

    # -- CANNOT_DECIDE -------------------------------------------------
    if outcome == "CANNOT_DECIDE":
        missing = tuple(decision.get("missing_evidence") or ())
        blocking = tuple(decision.get("blocking_evidence") or ())
        contradicted = case.contradicted_identity_properties
        waiting_since = _earliest_evidence_time(case)

        if contradicted or blocking:
            subject_property = (contradicted or blocking)[0]
            status = STATUS_BLOCKED_CONTRADICTED
            reason_text = (
                f"Two sources disagree about {subject_property!r} and the "
                "contradiction has not been reconciled.")
        else:
            subject_property = missing[0] if missing else None
            status = STATUS_BLOCKED_MISSING
            reason_text = (
                f"{', '.join(missing)} has not been established by anyone."
                if missing else
                "A required identity input is not established.")

        role, actor, basis = (_owner_of_dimension(case, subject_property)
                              if subject_property
                              else (None, None, "no property identified"))
        if role is None:
            requesting_role, requesting_actor, requesting_basis = \
                _requesting_role(case)
            derivation.append(
                "no governed owner for the blocking dimension; falling back to "
                "the role that raised the change, which is observed rather than "
                "governed")
            role, actor = requesting_role, requesting_actor
            basis = basis + f"  Falling back to {requesting_basis}."
            action = ACTION_ESTABLISH_OWNER
        else:
            action = ACTION_REQUEST_EVIDENCE

        derivation.append(f"blocking properties: {list(missing or blocking)}")
        return Coordination(
            overall_status=status,
            blocked=True,
            current_owner_role=role, current_owner_actor=actor,
            owner_basis=basis,
            waiting_on=subject_property,
            waiting_since=waiting_since,
            missing_evidence=missing,
            blocking_decisions=(decision["decision_id"],),
            needs_review=(case.subject_id,),
            recommended_next_action=action,
            explanation=(
                f"The governed decision concluded CANNOT_DECIDE. {reason_text} "
                "No canonical Product, Configuration or ConfigurationVersion "
                "was created, and none will be until the gap is closed -- the "
                "platform names what it needs rather than guessing."),
            derivation=tuple(derivation))

    # -- a cleared outcome ---------------------------------------------
    if outcome in _CLEARED:
        role, actor, basis = _requesting_role(case)
        no_change = outcome in _NO_CANONICAL_CHANGE
        status = STATUS_NO_CHANGE if no_change else STATUS_IDENTITY_ESTABLISHED

        executable = _other_executable_decision_types(case)
        if executable:
            action = ACTION_AWAIT_GOVERNANCE
            tail = (f"Further governed decision types are declared but not yet "
                    f"evaluated for this subject: {', '.join(executable)}.")
        else:
            action = ACTION_NONE
            tail = (
                "No further governed decision type is executable for this "
                "subject in this release, so the platform cannot say whether "
                "the launch is ready -- and does not pretend to. "
                "IDENTITY_ASSESSMENT is the only decision with executable "
                "bindings.")
        derivation.append(
            f"executable-but-unevaluated decision types: {executable or 'none'}")

        if no_change:
            explanation = (
                "The requested identity already exists as "
                f"{case.configuration['configuration_id'] if case.configuration else 'an existing configuration'}"
                ". No new Configuration and no new ConfigurationVersion were "
                "created, and no target-system row is required. " + tail)
        else:
            explanation = (
                f"The governed decision concluded {outcome}. The canonical "
                "identity is established and the projection previews show what "
                "each target system would need. " + tail)

        return Coordination(
            overall_status=status,
            blocked=False,
            current_owner_role=role, current_owner_actor=actor,
            owner_basis=basis,
            waiting_on=None,
            waiting_since=None,
            cleared_decisions=(decision["decision_id"],),
            recommended_next_action=action,
            explanation=explanation,
            derivation=tuple(derivation))

    # -- an outcome this analyser does not recognise --------------------
    derivation.append(f"unrecognised outcome {outcome!r}")
    return Coordination(
        overall_status=STATUS_CANNOT_DETERMINE,
        blocked=True,
        current_owner_role=None, current_owner_actor=None,
        owner_basis="not determined",
        waiting_on=None,
        needs_review=(case.subject_id,),
        recommended_next_action=ACTION_HUMAN_REVIEW,
        explanation=(
            f"The current decision concluded {outcome!r}, which this "
            "coordination layer has no rule for. Rather than guess what it "
            "implies for the launch, the case is routed to a human."),
        derivation=tuple(derivation))


def _other_executable_decision_types(case) -> tuple:
    """Decision types the ACTIVE release binds a predicate for, minus the one
    already evaluated. Empty for this release, and saying so is the point."""
    declared = {row.get("decision")
                for row in case.governance.get("bound_decision_types", ())}
    return tuple(sorted(declared - set(case.current_decisions)))


def _earliest_evidence_time(case):
    times = [item["occurred_at"] for item in case.evidence
             if item.get("occurred_at") is not None]
    return min(times) if times else None


# ======================================================================
# handoff journey
# ======================================================================

def build_journey(case) -> tuple:
    """Observed business participation, in the order it was observed.

    NOT a workflow. There is no S1..S19 here, no expected next step and no
    notion of a stage being 'skipped': events arrive asynchronously and the
    journey reports what actually happened. An entry exists because a row
    exists.
    """
    entries: list = []

    if case.launch and case.launch.get("observed"):
        entries.append(JourneyEntry(
            role=case.launch.get("requested_by_role"),
            actor=case.launch.get("requested_by_actor"),
            event="Change intent recorded",
            object_affected=case.launch["launch_id"],
            status="complete",
            occurred_at=None,
            decision_dependency=None,
            explanation=(
                f"Intent classified as "
                f"{case.launch.get('intent_classification')!r} on "
                f"{case.launch['launch_id']}.")))

    by_role: dict = {}
    for item in case.evidence:
        by_role.setdefault(item.get("role") or "unattributed", []).append(item)

    for role, items in sorted(by_role.items()):
        items.sort(key=lambda i: (i["occurred_at"] is None, i["occurred_at"]))
        properties = sorted({i["property_name"] for i in items})
        contributing = [i for i in items if i["contributed_to_fold"]]
        entries.append(JourneyEntry(
            role=role,
            actor=next((i["actor"] for i in items if i["actor"]), None),
            event=f"Evidence supplied: {', '.join(properties)}",
            object_affected=case.subject_id,
            status="complete" if contributing else "recorded",
            occurred_at=items[0]["occurred_at"],
            decision_dependency=None,
            explanation=(
                f"{len(items)} evidence record(s), {len(contributing)} of which "
                "the Fold used as the basis for a governed property.")))

    for decision in case.decisions:
        entries.append(JourneyEntry(
            role="platform",
            actor=None,
            event=f"{decision['decision_type']} -> {decision['outcome_code']}",
            object_affected=case.subject_id,
            status=("current" if decision["state"] == "current"
                    else decision["state"]),
            occurred_at=decision["decided_at"],
            decision_dependency=decision["decision_id"],
            explanation=(
                f"Matched {decision.get('matched_rule_id')} "
                f"({decision.get('matched_rule_class')}), reason "
                f"{decision.get('reason_code')}, under "
                f"{decision['ontology_version']} "
                f"({decision['governance_basis']}).")))

    if case.version:
        entries.append(JourneyEntry(
            role="platform",
            actor=None,
            event="Canonical version established",
            object_affected=case.version["version_id"],
            status=case.version.get("status") or "established",
            occurred_at=case.version.get("created_at"),
            decision_dependency=str(case.version.get("identity_assessment_id")),
            explanation=(
                f"Created from {case.version.get('identity_assessment_outcome')}"
                f" under configuration {case.version['configuration_id']}.")))

    entries.sort(key=lambda e: (e.occurred_at is None, e.occurred_at))
    return tuple(entries)
