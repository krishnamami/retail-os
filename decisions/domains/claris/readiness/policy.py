"""Governed readiness policy for the Claris prototype.

WHAT THIS FILE IS
    A declaration, not an algorithm. Every rule about what readiness requires
    lives here as data; evaluate.py contains the mechanism and no judgement.
    The point is that the policy can be read and argued with by someone who
    does not read Python, and that changing a rule cannot accidentally change
    the mechanism.

THE RULE THIS EXISTS TO ENFORCE
    A DEFAULTED value is not evidence. runtime.evidence records 39 rows whose
    value no source event ever asserted -- eight of them a technical_review
    PASS that exists because a COALESCE fallback says PASS. A readiness
    decision that accepted those would report eight SKUs technically approved
    on the strength of a constant in mapping code.

    So every gating input declares which provenances satisfy it. Today all of
    them accept OBSERVED only. That is a policy position, recorded as one, and
    reversible by governance rather than by editing an if-statement.

WHY MISSING AND DEFAULTED BOTH YIELD CANNOT_DECIDE, NOT NOT_READY
    NOT_READY asserts a fact: this thing is not ready. Absent evidence and
    manufactured evidence do not support that assertion any more than they
    support READY. Claiming NOT_READY from silence would be the same error as
    claiming READY from a default, pointed the other way. Only an OBSERVED
    value that fails its test produces NOT_READY.

WHAT IS DELIBERATELY NOT MODELLED
    No S1..S19 sequence. Readiness is a statement about current evidence, not
    about how far through a workflow something has travelled; events arrive
    late and out of order, and the fold already carries that.

    No cross-subject composition from configuration or launch subjects. The
    corpus provides no governed link from a sku to its CON/PRD configuration
    -- SKU_MINTED carries launch_id, not con_id -- so composing SAP load, test
    or hierarchy-approval facts into a sku readiness decision would require
    inventing that link. It is recorded as a limitation instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "OBSERVED_ONLY", "OBSERVED_OR_DEFAULTED",
    "Requirement", "AnyOf", "ReadinessPolicy",
    "TECHNICAL_READINESS", "PRICING_READINESS", "LAUNCH_READINESS",
    "POLICIES", "POLICY_VERSION",
]

#: Bumped whenever a rule below changes. Recorded on every decision so an
#: outcome can always be traced to the policy that produced it.
POLICY_VERSION = "READINESS-v1.0.0-PROTOTYPE"

#: Provenance sets a gating input may accept.
OBSERVED_ONLY = frozenset({"OBSERVED"})
OBSERVED_OR_DEFAULTED = frozenset({"OBSERVED", "DEFAULTED"})


@dataclass(frozen=True)
class Requirement:
    """One input to a readiness decision.

    property_name    the folded property, on the decision's subject
    gating           False makes it context: reported, never decisive
    accepts          provenances that satisfy it. A value whose provenance is
                     outside this set is insufficient evidence, not a failure
    satisfied_by     values that satisfy it. None means any non-null value
    failed_by        values that positively fail it. A value that is neither
                     satisfying nor failing is unrecognised, and unrecognised
                     is CANNOT_DECIDE -- guessing which side of the line a new
                     status code falls on is exactly the kind of assumption
                     this system exists to refuse
    why              plain-language statement of what the input is for
    """

    property_name: str
    why: str
    gating: bool = True
    accepts: frozenset = OBSERVED_ONLY
    satisfied_by: Optional[frozenset] = None
    failed_by: frozenset = frozenset()


@dataclass(frozen=True)
class AnyOf:
    """A gate satisfied by any one of several requirements.

    Exists for pricing approval, where the corpus carries two disjoint
    populations: PRICING_CONFIRMED for SKU-001..003 and FINAL_PRICING_APPROVAL
    for SKU-004..012. D4I_003 established these are different events and must
    never be merged into one property. They are still, as a matter of governed
    policy, alternative routes to the same gate -- and saying so here is the
    honest way to express that, because the alternatives stay visible and the
    evidence layer stays unmerged.
    """

    label: str
    why: str
    options: tuple
    gating: bool = True


@dataclass(frozen=True)
class ReadinessPolicy:
    decision_type: str
    subject_type: str
    intent: str
    requirements: tuple = field(default_factory=tuple)
    #: Readiness decisions that must themselves be READY first.
    composes: tuple = field(default_factory=tuple)


TECHNICAL_READINESS = ReadinessPolicy(
    decision_type="TECHNICAL_READINESS",
    subject_type="sku",
    intent="Has this SKU passed technical review on evidence a source asserted?",
    requirements=(
        Requirement(
            property_name="technical_review_result",
            why="the technical gate's own verdict",
            accepts=OBSERVED_ONLY,
            satisfied_by=frozenset({"PASS"}),
            failed_by=frozenset({"REJECTED", "FAIL"}),
        ),
        # Context, not gates. sku_status and activation describe where the SKU
        # is; they do not evidence technical approval, and requiring MINTED
        # would report a missing fact for SKU-001..003, which are observed
        # ACTIVATED. Treating activation as implying minting would be a
        # derivation, and a derivation asserted as observation is the error
        # this whole phase removed.
        Requirement("sku_status", "whether the SKU has been minted",
                    gating=False),
        Requirement("sku_activation_status", "whether the SKU is active",
                    gating=False),
    ),
)

PRICING_READINESS = ReadinessPolicy(
    decision_type="PRICING_READINESS",
    subject_type="sku",
    intent="Is there an approved, evidenced price for this SKU?",
    requirements=(
        Requirement(
            property_name="pricing_status",
            why="a price was actually determined",
            satisfied_by=frozenset({"DETERMINED"}),
        ),
        Requirement(
            property_name="pricing_value_usd",
            why="the determined price itself; readiness without a number is "
                "not readiness",
        ),
        AnyOf(
            label="pricing_approval",
            why="approval by either governed route -- the early cohort is "
                "confirmed, the later cohort is finally approved",
            options=(
                Requirement("final_pricing_approval_status",
                            "FINAL_PRICING_APPROVAL occurred",
                            satisfied_by=frozenset({"APPROVED"})),
                Requirement("pricing_confirmed",
                            "PRICING_CONFIRMED occurred",
                            satisfied_by=frozenset({"CONFIRMED"})),
            ),
        ),
        Requirement("pricing_upload_status", "loaded into the pricing system",
                    gating=False),
        Requirement("pricing_publication_status", "visible downstream",
                    gating=False),
        Requirement("zupdm_approval_status", "ZUPDM sign-off", gating=False),
        Requirement("all_gates_cleared", "every gate reported clear",
                    gating=False),
    ),
)

LAUNCH_READINESS = ReadinessPolicy(
    decision_type="LAUNCH_READINESS",
    subject_type="sku",
    intent="Can this SKU go live?",
    composes=("TECHNICAL_READINESS", "PRICING_READINESS"),
    requirements=(
        Requirement(
            property_name="go_live_approval_status",
            why="explicit go-live approval",
            satisfied_by=frozenset({"APPROVED"}),
            failed_by=frozenset({"REJECTED", "DENIED"}),
        ),
        Requirement("material_activation_status", "material is active",
                    gating=False),
        Requirement("supply_chain_notification_status",
                    "supply chain has been told", gating=False),
    ),
)

POLICIES = {
    p.decision_type: p
    for p in (TECHNICAL_READINESS, PRICING_READINESS, LAUNCH_READINESS)
}
