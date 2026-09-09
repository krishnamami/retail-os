"""The readiness mechanism. Contains no policy and no judgement.

Every rule lives in policy.py. This file only applies them, in one order, to
one set of folded properties, and records why it reached what it reached.

DETERMINISM
    Pure. Same properties plus same policy give the same decision, every time,
    with no clock, no database and no ordering dependence. That is what makes a
    readiness outcome replayable rather than merely repeatable.

OUTCOME PRECEDENCE, AND WHY IT IS THIS WAY
    NOT_READY  >  CANNOT_DECIDE  >  READY

    A known failure is decisive: once one gate is observed to fail, no amount
    of unknown elsewhere makes the thing ready, so NOT_READY outranks the
    unknowns. CANNOT_DECIDE outranks READY because readiness is a positive
    claim and every gate must be evidenced to make it. Silence never becomes
    consent in either direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional

from .policy import POLICIES, POLICY_VERSION, AnyOf, ReadinessPolicy

__all__ = [
    "READY", "NOT_READY", "CANNOT_DECIDE",
    "InputFinding", "ReadinessDecision", "evaluate", "evaluate_all",
]

READY = "READY"
NOT_READY = "NOT_READY"
CANNOT_DECIDE = "CANNOT_DECIDE"

_RANK = {READY: 0, CANNOT_DECIDE: 1, NOT_READY: 2}

#: Why a single input did not satisfy its gate. These are the words the
#: Workbench shows, so they are part of the contract, not debug text.
SATISFIED = "SATISFIED"
FAILED = "FAILED"
MISSING = "MISSING"
INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"
CONTRADICTED = "CONTRADICTED"
UNRECOGNISED_VALUE = "UNRECOGNISED_VALUE"


@dataclass(frozen=True)
class InputFinding:
    property_name: str
    status: str
    gating: bool
    why: str
    fold_state: Optional[str] = None
    value: Any = None
    provenance: Optional[str] = None
    detail: str = ""

    @property
    def blocks(self) -> bool:
        return self.gating and self.status != SATISFIED


@dataclass(frozen=True)
class ReadinessDecision:
    decision_type: str
    subject_type: str
    subject_id: str
    outcome: str
    intent: str
    policy_version: str
    findings: tuple = field(default_factory=tuple)
    composed_from: tuple = field(default_factory=tuple)

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.blocks)

    @property
    def missing_evidence(self) -> tuple:
        return tuple(f.property_name for f in self.findings
                     if f.gating and f.status == MISSING)

    @property
    def insufficient_evidence(self) -> tuple:
        """Present, but manufactured. The distinction D4I_003c bought."""
        return tuple(f.property_name for f in self.findings
                     if f.gating and f.status == INSUFFICIENT_PROVENANCE)

    @property
    def failures(self) -> tuple:
        return tuple(f.property_name for f in self.findings
                     if f.gating and f.status == FAILED)

    def why_not(self) -> str:
        """One sentence a person can act on. Never a list of internals."""
        if self.outcome == READY:
            return "every required input is satisfied by observed evidence"
        parts = []
        if self.failures:
            parts.append("failed on " + ", ".join(self.failures))
        if self.missing_evidence:
            parts.append("no evidence for " + ", ".join(self.missing_evidence))
        if self.insufficient_evidence:
            parts.append(
                "evidence for " + ", ".join(self.insufficient_evidence)
                + " was supplied by projection defaults, not asserted by any "
                  "source")
        for name, outcome in self.composed_from:
            if outcome != READY:
                parts.append(f"{name} is {outcome}")
        return "; ".join(parts) or "no gating input was satisfied"


def _assess(req, properties: Mapping[str, Mapping[str, Any]]) -> InputFinding:
    prop = properties.get(req.property_name)
    if prop is None or prop.get("fold_state") in (None, "UNREPORTED", "ABSENT"):
        return InputFinding(
            req.property_name, MISSING, req.gating, req.why,
            fold_state=(prop or {}).get("fold_state", "ABSENT"),
            detail="no source has reported this")

    state = prop.get("fold_state")
    value = prop.get("value")
    provenance = prop.get("provenance")

    if state == "CONTRADICTED":
        return InputFinding(req.property_name, CONTRADICTED, req.gating,
                            req.why, state, value, provenance,
                            "sources disagree; a decision here would pick a "
                            "side the evidence does not")
    if state != "ESTABLISHED":
        return InputFinding(req.property_name, MISSING, req.gating, req.why,
                            state, value, provenance,
                            f"fold state is {state}")

    if provenance not in req.accepts:
        return InputFinding(
            req.property_name, INSUFFICIENT_PROVENANCE, req.gating, req.why,
            state, value, provenance,
            f"value is {value!r} but its provenance is {provenance}; this gate "
            f"accepts {', '.join(sorted(req.accepts))} only")

    text = None if value is None else str(value)
    if req.failed_by and text in req.failed_by:
        return InputFinding(req.property_name, FAILED, req.gating, req.why,
                            state, value, provenance,
                            f"observed value {text!r} fails this gate")
    if req.satisfied_by is None:
        if value is None or text == "":
            return InputFinding(req.property_name, MISSING, req.gating,
                                req.why, state, value, provenance,
                                "established but empty")
        return InputFinding(req.property_name, SATISFIED, req.gating, req.why,
                            state, value, provenance)
    if text in req.satisfied_by:
        return InputFinding(req.property_name, SATISFIED, req.gating, req.why,
                            state, value, provenance)
    return InputFinding(
        req.property_name, UNRECOGNISED_VALUE, req.gating, req.why, state,
        value, provenance,
        f"observed value {text!r} is neither satisfying nor failing for this "
        f"gate; it is not classified, and guessing which it is would invent a "
        f"business rule")


def _assess_any_of(group: AnyOf, properties) -> tuple:
    """The group's verdict, followed by each route as non-gating evidence.

    Only the GROUP gates. The per-route findings are returned so a reader can
    see which route satisfied it and what the others said, but a route that was
    simply not taken must never block: SKU-004 is approved via
    FINAL_PRICING_APPROVAL and has no PRICING_CONFIRMED, and treating that
    absence as a failure would veto a gate the evidence satisfies.
    """
    findings = tuple(replace(_assess(option, properties), gating=False)
                     for option in group.options)
    satisfied = [f for f in findings if f.status == SATISFIED]
    if satisfied:
        best = satisfied[0]
        return (InputFinding(group.label, SATISFIED, group.gating, group.why,
                             best.fold_state, best.value, best.provenance,
                             f"satisfied by {best.property_name}"),) + findings
    failed = [f for f in findings if f.status == FAILED]
    if failed and all(f.status == FAILED for f in findings):
        return (InputFinding(group.label, FAILED, group.gating, group.why,
                             detail="every route was observed to fail"),
                ) + findings
    insufficient = [f for f in findings
                    if f.status == INSUFFICIENT_PROVENANCE]
    if insufficient:
        return (InputFinding(
            group.label, INSUFFICIENT_PROVENANCE, group.gating, group.why,
            detail="the only route with a value rests on a projection default"),
            ) + findings
    return (InputFinding(group.label, MISSING, group.gating, group.why,
                         detail="no route has been reported"),) + findings


def _outcome(findings, composed) -> str:
    outcome = READY
    for finding in findings:
        if not finding.gating or finding.status == SATISFIED:
            continue
        candidate = NOT_READY if finding.status == FAILED else CANNOT_DECIDE
        if _RANK[candidate] > _RANK[outcome]:
            outcome = candidate
    for _, sub in composed:
        if _RANK[sub] > _RANK[outcome]:
            outcome = sub
    return outcome


def evaluate(decision_type: str, subject_id: str,
             properties: Mapping[str, Mapping[str, Any]],
             composed: Mapping[str, str] = None) -> ReadinessDecision:
    """Evaluate one readiness decision from folded properties.

    properties maps property_name -> {fold_state, value, provenance}. That is
    exactly what runtime.property_provenance_at returns, which is why the
    evaluator needs no database of its own.
    """
    policy: ReadinessPolicy = POLICIES[decision_type]
    composed = composed or {}

    findings = []
    for req in policy.requirements:
        if isinstance(req, AnyOf):
            findings.extend(_assess_any_of(req, properties))
        else:
            findings.append(_assess(req, properties))

    composed_from = tuple(
        (name, composed.get(name, CANNOT_DECIDE)) for name in policy.composes)

    return ReadinessDecision(
        decision_type=decision_type,
        subject_type=policy.subject_type,
        subject_id=subject_id,
        outcome=_outcome(findings, composed_from),
        intent=policy.intent,
        policy_version=POLICY_VERSION,
        findings=tuple(findings),
        composed_from=composed_from,
    )


def evaluate_all(subject_id: str, properties) -> dict:
    """The three readiness decisions, composed in dependency order."""
    technical = evaluate("TECHNICAL_READINESS", subject_id, properties)
    pricing = evaluate("PRICING_READINESS", subject_id, properties)
    launch = evaluate(
        "LAUNCH_READINESS", subject_id, properties,
        composed={"TECHNICAL_READINESS": technical.outcome,
                  "PRICING_READINESS": pricing.outcome})
    return {"TECHNICAL_READINESS": technical,
            "PRICING_READINESS": pricing,
            "LAUNCH_READINESS": launch}
