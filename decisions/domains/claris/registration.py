"""IDENTITY_ASSESSMENT domain-pack registration and binding.

WHAT THIS MODULE IS FOR
-----------------------
The generic PredicateRegistry knows how to map (decision_type, rule_id,
kb_version) to a callable. It does not know that IR-011 is a GUARD or that
IR-013 concludes CREATE_CONFIGURATION. That mapping is Claris business
metadata and it lives here, in the domain pack, so no Claris rule id ever
appears inside a generic executor module.

GOVERNANCE BOUNDARY -- READ THIS BEFORE USING ANYTHING BELOW (section 13)
-------------------------------------------------------------------------
IR-010..IR-013 are PROPOSED SEMANTIC CANDIDATES in claris_kb.identity_rules at
kb_version 1.0.1. They are not executable governed rules:

    claris_kb.decision_rules            IDENTITY_ASSESSMENT rows: ZERO
    claris_kb.v_active_decision_rules   IDENTITY_ASSESSMENT rows: ZERO

Nothing in this module writes to either. Nothing here promotes, activates or
projects a semantic candidate into an executable row. A real GOVERNED
IDENTITY_ASSESSMENT execution remains BLOCKED until executable projection and
activation are designed, and D.4E does not design them.

So `prototype_governance_binding()` exists, and it labels itself. From
D.4G.1G.5P.1 the label is a dedicated field rather than a sentinel in a
version column: the binding carries

    governance_basis = PROTOTYPE_ASSUMPTION
    ontology_version = 2026.10-prototype.1   (the real prototype release)

and both travel into DecisionResult. The earlier design overloaded
ontology_version with the literal NON_GOVERNED_PROTOTYPE, which conflated two
facts -- "this is a prototype" and "this is the release it used" -- so a
prototype result could not say which governance it actually ran against. That
sentinel is retired. A result produced through this binding is still
self-identifying, and now it is also traceable.

RULE ORDER (locked, section 10)
    class order  GUARD before MATCH before FALLBACK, absolutely
    IR-011  GUARD  precedence 1
    IR-012  GUARD  precedence 2
    IR-013  MATCH  precedence 5
    IR-010  MATCH  precedence 6

No FALLBACK is declared for IDENTITY_ASSESSMENT. D.4B locked none, and
inventing one would give the decision type a terminal outcome no governance
authority ever sanctioned. When no rule resolves, the generic executor's
configured no-resolution behaviour applies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ...contracts import GOVERNANCE_BASIS_PROTOTYPE, GovernanceBinding
from ...ports import RuleClassBinding
from ...registry import PredicateRegistry
from ...rules import RuleBinding, RuleClass, RuleDefinition, order_bindings
from .identity import DECISION_TYPE, IDENTITY_PROPERTIES, SUBJECT_TYPE
from .predicates.identity_assessment import (
    IDENTITY_PREDICATES,
    PREDICATES_BY_NAME,
    IR_010,
    IR_011,
    IR_012,
    IR_013,
)

__all__ = [
    "DECISION_TYPE",
    "SUBJECT_TYPE",
    "SEMANTIC_KB_VERSION",
    "SEMANTIC_RULE_STATUS",
    "EXECUTABLE_RULE_IDS",
    "IA_PRED_001",
    "IA_PRED_002",
    "IA_PRED_003",
    "IA_PRED_004",
    "SEMANTIC_RULE_ORDER",
    "executable_rule_id",
    "PROTOTYPE_ONTOLOGY_VERSION",
    "PROTOTYPE_VALIDATION_STATUS",
    "PROTOTYPE_LABEL",
    "SemanticRule",
    "IDENTITY_SEMANTIC_RULES",
    "IDENTITY_RULE_ORDER",
    "PREDICATES_BY_NAME",
    "REASON_CODES_BY_NAME",
    "identity_class_bindings",
    "register_identity_assessment",
    "prototype_rule_bindings",
    "prototype_governance_binding",
    "build_prototype_registry",
]

#: The kb_version IR-010..IR-013 carry in claris_kb.identity_rules.
SEMANTIC_KB_VERSION = "1.0.1"

#: Their governed status there. Unchanged by D.4E.
SEMANTIC_RULE_STATUS = "proposed"

#: The prototype governance release this domain pack evaluates against.
#: A real ontology_version, not a sentinel: the basis is carried separately
#: in GovernanceBinding.governance_basis.
PROTOTYPE_ONTOLOGY_VERSION = "2026.10-prototype.1"

#: What the prototype release is still waiting for.
PROTOTYPE_VALIDATION_STATUS = "TO_BE_VALIDATED_WITH_CLARIS"

#: Human-readable label required by section 21 for any result produced this way.
PROTOTYPE_LABEL = "PROTOTYPE DOMAIN EVALUATION ONLY"

#: SEMANTIC CANDIDATE id -> EXECUTABLE TECHNICAL PREDICATE id  (D.4G.2 s.5/s.7)
#:
#: IR-nnn identifies a governed BUSINESS identity/change rule -- a change type
#: with a proposed business effect, an owner and a confirmation state. The four
#: objects below are none of those things: they are boolean predicates with a
#: class and a precedence. Sharing the IR namespace with business rules made
#: two different kinds of object indistinguishable by identifier, so at
#: D.4G.1G.4 the executable series was separated to IA-PRED-nnn.
#:
#: The mapping is applied at the EXECUTABLE boundary only. IDENTITY_SEMANTIC_RULES
#: keeps its IR-nnn ids, because those really are the ids of the proposed
#: semantic candidates in claris_kb.identity_rules at 1.0.1. What executes is
#: IA-PRED-nnn; what was proposed is IR-nnn; they are not the same object.
EXECUTABLE_RULE_IDS: Mapping[str, str] = {
    IR_011: "IA-PRED-001",
    IR_012: "IA-PRED-002",
    IR_013: "IA-PRED-003",
    IR_010: "IA-PRED-004",
}

IA_PRED_001 = EXECUTABLE_RULE_IDS[IR_011]
IA_PRED_002 = EXECUTABLE_RULE_IDS[IR_012]
IA_PRED_003 = EXECUTABLE_RULE_IDS[IR_013]
IA_PRED_004 = EXECUTABLE_RULE_IDS[IR_010]


@dataclass(frozen=True)
class SemanticRule:
    """One proposed identity rule, as claris_kb.identity_rules describes it.

    This is SEMANTIC metadata mirrored into code for organization and testing.
    It is not, and must not be represented as, an executable governed row.
    """

    rule_id: str
    rule_name: str
    rule_class: RuleClass
    precedence: int
    outcome_code: str
    reason_code: str
    kb_version: str = SEMANTIC_KB_VERSION
    status: str = SEMANTIC_RULE_STATUS

    @property
    def is_executable_governed_rule(self) -> bool:
        """Always False in D.4E. Asserted by a test, not merely documented."""
        return False


IDENTITY_SEMANTIC_RULES: tuple[SemanticRule, ...] = (
    SemanticRule(
        rule_id=IR_011,
        rule_name="Missing Required Identity Input",
        rule_class=RuleClass.GUARD,
        precedence=1,
        outcome_code="CANNOT_DECIDE",
        reason_code="MISSING_REQUIRED_INPUT",
    ),
    SemanticRule(
        rule_id=IR_012,
        rule_name="Contradicted Required Identity Input",
        rule_class=RuleClass.GUARD,
        precedence=2,
        outcome_code="CANNOT_DECIDE",
        reason_code="CONTRADICTED_REQUIRED_INPUT",
    ),
    SemanticRule(
        rule_id=IR_013,
        rule_name="Initial Configuration for Existing Product",
        rule_class=RuleClass.MATCH,
        precedence=5,
        outcome_code="CREATE_CONFIGURATION",
        reason_code="INITIAL_CONFIGURATION",
    ),
    SemanticRule(
        rule_id=IR_010,
        rule_name="Exact Identity Tuple Match",
        rule_class=RuleClass.MATCH,
        precedence=6,
        outcome_code="NO_BUSINESS_CHANGE",
        reason_code="EXACT_IDENTITY_MATCH",
    ),
)

#: Registration order, section 10. Evaluation order is computed by the
#: platform's order_bindings() from class and precedence, never from this.
IDENTITY_RULE_ORDER: tuple[str, ...] = (
    IA_PRED_001, IA_PRED_002, IA_PRED_003, IA_PRED_004,
)

#: The semantic candidates in their registration order, for lookups that need
#: the proposed business rule behind an executable predicate.
SEMANTIC_RULE_ORDER: tuple[str, ...] = (IR_011, IR_012, IR_013, IR_010)


#: predicate_name -> reason_code.
#:
#: WHY THIS IS HERE AND NOT IN THE ARTIFACT
#: ontology_authoring.decision_rule_bindings has no reason_code column, and the
#: compiler reads every column a table has, so adding one would change the
#: semantic digest of every release compiled afterwards -- including
#: 2026.10-prototype.1, which is already published, verified and depended upon
#: by a gate that recompiles it. The cost of carrying reason codes in governed
#: metadata is therefore a re-digest of published history, and it is not worth
#: paying yet. They stay here, as domain registration metadata, and travel into
#: the runtime through the same predicate_name key as the callables.
#:
#: THESE ARE NOT THE GOVERNED REASON CODES. 2026.10 declares a six-value
#: `decision_reason_code` enum -- IDENTITY_POLICY_NOT_DEFINED, EVIDENCE_ABSENT,
#: EVIDENCE_CONTRADICTED, EVIDENCE_REJECTED, DEPENDENCY_UNRESOLVED,
#: REQUEST_UNDERSPECIFIED. The four below were coined by D.4E for the identity
#: predicates and none of them appears in that enum. Mapping one vocabulary onto
#: the other is a real governance question (is a missing identity input
#: EVIDENCE_ABSENT or REQUEST_UNDERSPECIFIED?) and it is not answered here.
REASON_CODES_BY_NAME: Mapping[str, str] = {
    "ir_011_missing_required_input": "MISSING_REQUIRED_INPUT",
    "ir_012_contradicted_required_input": "CONTRADICTED_REQUIRED_INPUT",
    "ir_013_initial_configuration": "INITIAL_CONFIGURATION",
    "ir_010_exact_identity_match": "EXACT_IDENTITY_MATCH",
    "ir_001_no_canonical_product": "NEW_PRODUCT_FAMILY",
    "additional_configuration_for_existing_product": "NEW_IDENTITY_TUPLE",
}


def _rule(rule_id: str) -> SemanticRule:
    for rule in IDENTITY_SEMANTIC_RULES:
        if rule.rule_id == rule_id:
            return rule
    raise KeyError(f"unknown IDENTITY_ASSESSMENT semantic rule {rule_id!r}")


def executable_rule_id(semantic_rule_id: str) -> str:
    """The IA-PRED-nnn predicate that carries out one semantic candidate."""
    try:
        return EXECUTABLE_RULE_IDS[semantic_rule_id]
    except KeyError:
        raise KeyError(
            f"no executable predicate for semantic rule {semantic_rule_id!r}"
        ) from None


# ======================================================================
# the governed path: rule_class bindings for bind_rule_metadata()
# ======================================================================

def identity_class_bindings(
    kb_version: str = SEMANTIC_KB_VERSION,
) -> Mapping[str, RuleClassBinding]:
    """Domain-owned rule_class + predicate_ref, keyed by rule_id.

    This is what a domain pack hands to ports.bind_rule_metadata() once
    executable governed rows exist. It supplies rule_class and a predicate
    reference and nothing else -- the KB keeps ownership of outcome, reason and
    kb_version.

    It is exported now so the governed path needs no new code later, and it is
    inert today because there are no executable IDENTITY_ASSESSMENT rows for it
    to bind to.
    """
    return {
        EXECUTABLE_RULE_IDS[rule.rule_id]: RuleClassBinding(
            rule_id=EXECUTABLE_RULE_IDS[rule.rule_id],
            rule_class=rule.rule_class,
            predicate_ref=f"claris.identity_assessment.{rule.rule_id}",
            precedence_override=rule.precedence,
        )
        for rule in IDENTITY_SEMANTIC_RULES
    }


def register_identity_assessment(
    registry: PredicateRegistry,
    kb_version: str = SEMANTIC_KB_VERSION,
) -> PredicateRegistry:
    """Bind the four predicates into a generic registry. Returns it.

    Registration order follows IDENTITY_RULE_ORDER for readability only. The
    registry is a dictionary and the executor derives evaluation order from
    governed class and precedence, so registration order cannot influence any
    outcome -- which is asserted by an ordering test rather than assumed.
    """
    for semantic_id in SEMANTIC_RULE_ORDER:
        registry.register(
            DECISION_TYPE,
            EXECUTABLE_RULE_IDS[semantic_id],
            kb_version,
            IDENTITY_PREDICATES[semantic_id],
        )
    return registry


# ======================================================================
# the prototype path: explicitly NON-GOVERNED
# ======================================================================

def prototype_rule_bindings(
    kb_version: str = SEMANTIC_KB_VERSION,
) -> tuple[RuleBinding, ...]:
    """RuleBindings built from the SEMANTIC candidates, for prototype use only.

    These are not governed executable rules and this function does not pretend
    otherwise. It exists so the four predicates can be exercised together,
    through the real generic executor, with the real ordering contract.
    """
    return order_bindings(
        tuple(
            RuleBinding(
                definition=RuleDefinition(
                    decision_type=DECISION_TYPE,
                    rule_id=EXECUTABLE_RULE_IDS[rule.rule_id],
                    kb_version=kb_version,
                    rule_class=rule.rule_class,
                    precedence=rule.precedence,
                    outcome_code=rule.outcome_code,
                    reason_code=rule.reason_code,
                ),
                predicate_ref=f"claris.identity_assessment.{rule.rule_id}",
            )
            for rule in IDENTITY_SEMANTIC_RULES
        )
    )


def prototype_governance_binding(
    kb_version: str = SEMANTIC_KB_VERSION,
    policy_version: Optional[str] = None,
    rule_set_digest: str = "",
) -> GovernanceBinding:
    """A GovernanceBinding that announces it is NOT confirmed governance.

    governance_basis is PROTOTYPE_ASSUMPTION and propagates into
    DecisionResult.governance_basis, so a result carrying it can never be read
    as a confirmed IDENTITY_ASSESSMENT decision. ontology_version carries the
    real prototype release, so the result also says which assumptions it used.

    policy_version defaults to None, which under the D.4E contract correction
    means "no applicable governed policy version is present" -- the truthful
    answer here, since no governed policy applies to a proposed candidate.
    """
    return GovernanceBinding(
        ontology_version=PROTOTYPE_ONTOLOGY_VERSION,
        governance_basis=GOVERNANCE_BASIS_PROTOTYPE,
        kb_version=kb_version,
        policy_version=policy_version,
        rule_set=prototype_rule_bindings(kb_version),
        rule_set_digest=rule_set_digest,
        required_properties=IDENTITY_PROPERTIES,
    )


def build_prototype_registry(
    kb_version: str = SEMANTIC_KB_VERSION,
) -> PredicateRegistry:
    """A fresh registry carrying only the IDENTITY_ASSESSMENT predicates."""
    return register_identity_assessment(PredicateRegistry(), kb_version)
