"""IDENTITY_ASSESSMENT predicates.

WHAT A PREDICATE IS ALLOWED TO DO
---------------------------------
Read the DecisionContext. Return MATCHED / NOT_MATCHED. That is all.

A predicate never returns outcome_code or reason_code -- the KB owns those and
they arrive through the RuleBinding. A predicate never opens a connection,
never sees SQL, never sees a database row, and never reads Evidence, an
Assertion or a source system: the Fold is the authoritative input, and domain
facts arrive pre-computed from the lookup adapter.

THE FOUR ORIGINAL PREDICATES (semantic candidates, claris_kb.identity_rules,
kb 1.0.1)
------------------------------------------------------------------------------
    IR-011  GUARD  Missing Required Identity Input
                   -> CANNOT_DECIDE / MISSING_REQUIRED_INPUT
    IR-012  GUARD  Contradicted Required Identity Input
                   -> CANNOT_DECIDE / CONTRADICTED_REQUIRED_INPUT
    IR-013  MATCH  Initial Configuration for Existing Product
                   -> CREATE_CONFIGURATION / INITIAL_CONFIGURATION
    IR-010  MATCH  Exact Identity Tuple Match
                   -> NO_BUSINESS_CHANGE / EXACT_IDENTITY_MATCH

TWO MORE, ADDED FOR THE VERTICAL SLICE (2026.10-prototype.2)
-------------------------------------------------------------
The prototype release already declares CREATE_PRODUCT and CREATE_CONFIGURATION
as governed outcomes and already carries IR-001..IR-004 as prototype
assumptions. Nothing executable reached them, so every corpus scenario
concluded CANNOT_DECIDE: the first request could not create the product it
needed, and every later request found a product that already had a
configuration and so failed IR-013's initial-configuration condition.

These two predicates make the existing assumptions reachable. They introduce
no new assumption, read no new dimension, and change no part of the locked
identity tuple.

    IA-PRED-005  MATCH  No Canonical Product
                        -> CREATE_PRODUCT / NEW_PRODUCT_FAMILY
                        renders IR-001 (new_product_family -> CREATE_PRODUCT),
                        which the source calls tautological and which reads no
                        dimension at all.

    IA-PRED-006  MATCH  Additional Configuration for Existing Product
                        -> CREATE_CONFIGURATION / NEW_IDENTITY_TUPLE
                        renders IR-002, IR-003 and IR-004 jointly. All three
                        propose CREATE_CONFIGURATION, and the dimensions they
                        read -- geography, term_months, customer_segment -- are
                        three of the four locked identity properties. A tuple
                        that differs from every live configuration of an
                        existing product differs in at least one of them, so
                        one predicate carries all three faithfully. Splitting
                        it into three would require deciding WHICH dimension
                        changed, and the Fold does not carry that: a snapshot
                        states what the identity IS, not what it was before.

A CONCLUSION IS NOT AN ACTION (section 27)
------------------------------------------
IR-013 concluding CREATE_CONFIGURATION creates nothing, and neither does
IA-PRED-005 concluding CREATE_PRODUCT. Materialization is a separate act,
performed by a separate component, from a persisted decision. The predicates
state what the governed model concludes; they do not carry it out.
"""

from __future__ import annotations

from ....contracts import (
    NOT_MATCHED,
    DecisionContext,
    Known,
    PredicateResult,
    PredicateVerdict,
)
from ..errors import InvalidDomainFact
from ..identity import identity_inputs, identity_inputs_established
from ..lookup import (
    EXACT_IDENTITY_MATCH_EXISTS,
    EXISTING_CONFIGURATION_COUNT,
    PRODUCT_EXISTS,
)

__all__ = [
    "IR_001",
    "IR_010",
    "IR_011",
    "IR_012",
    "IR_013",
    "IR_002_004",
    "ir_011_missing_required_input",
    "ir_012_contradicted_required_input",
    "ir_013_initial_configuration",
    "ir_010_exact_identity_match",
    "ir_001_no_canonical_product",
    "additional_configuration_for_existing_product",
    "IDENTITY_PREDICATES",
    "PREDICATES_BY_NAME",
]

IR_001 = "IR-001"
IR_010 = "IR-010"
IR_011 = "IR-011"
IR_012 = "IR-012"
IR_013 = "IR-013"

#: The three governed assumptions IA-PRED-006 renders jointly. A tuple, not a
#: single id, because there is no single governed rule that says "a new tuple
#: under an existing product": there are three, one per dimension, and they
#: agree.
IR_002_004: tuple[str, ...] = ("IR-002", "IR-003", "IR-004")


# ======================================================================
# typed domain-fact access
# ======================================================================

def _known_bool(context: DecisionContext, name: str) -> bool | None:
    """A Known boolean fact, or None when the fact is Unavailable/absent.

    A wrong TYPE raises: section 25 lists 'invalid domain fact type' as a
    system failure. Coercing Known('false') to True would fabricate a governed
    outcome from a formatting mistake.
    """
    fact = context.fact(name)
    if fact is None or not isinstance(fact, Known):
        return None
    if not isinstance(fact.value, bool):
        raise InvalidDomainFact(
            f"domain fact {name!r} must be a bool, got "
            f"{type(fact.value).__name__}: {fact.value!r}"
        )
    return fact.value


def _known_int(context: DecisionContext, name: str) -> int | None:
    fact = context.fact(name)
    if fact is None or not isinstance(fact, Known):
        return None
    if isinstance(fact.value, bool) or not isinstance(fact.value, int):
        raise InvalidDomainFact(
            f"domain fact {name!r} must be an int, got "
            f"{type(fact.value).__name__}: {fact.value!r}"
        )
    return fact.value


# ======================================================================
# IR-011  GUARD  Missing Required Identity Input
# ======================================================================

def ir_011_missing_required_input(context: DecisionContext) -> PredicateResult:
    """MATCHED iff a required identity property is missing.

    Missing means, per section 6, exactly three things: UNREPORTED,
    EXPLICITLY_UNDEFINED, or absent from the Fold snapshot entirely.

    CONTRADICTED is deliberately NOT missing -- it is IR-012's condition, and a
    contradiction reported as a missing input would misdescribe what happened.
    An ESTABLISHED empty string is NOT missing either: the locked contract does
    not define emptiness as absence, and inventing that rule here would make an
    empty geography vanish from the identity tuple.

    `detail` carries the missing property names for audit. The executor builds
    the authoritative `missing_evidence` array itself, from
    governance.required_properties, so the record is complete even when this
    guard short-circuits the evaluation.
    """
    missing = identity_inputs(context.fold).missing
    if not missing:
        return NOT_MATCHED
    return PredicateResult(
        verdict=PredicateVerdict.MATCHED,
        detail={"missing_evidence": missing, "rule_id": IR_011},
    )


# ======================================================================
# IR-012  GUARD  Contradicted Required Identity Input
# ======================================================================

def ir_012_contradicted_required_input(context: DecisionContext) -> PredicateResult:
    """MATCHED iff a required identity property has fold_state CONTRADICTED.

    The Fold's CONTRADICTED state is the whole input. This predicate does not
    open a source system, does not compare Evidence records, and does not try
    to adjudicate which side of the contradiction is right -- resolving a
    contradiction is the Fold's job, and second-guessing it here would put an
    ungoverned tie-break inside a governed decision.
    """
    contradicted = tuple(sorted(identity_inputs(context.fold).contradicted))
    if not contradicted:
        return NOT_MATCHED
    return PredicateResult(
        verdict=PredicateVerdict.MATCHED,
        detail={"blocking_evidence": contradicted, "rule_id": IR_012},
    )


# ======================================================================
# IA-PRED-005  MATCH  No Canonical Product   (renders IR-001)
# ======================================================================

def ir_001_no_canonical_product(context: DecisionContext) -> PredicateResult:
    """MATCHED iff the identity is complete and no canonical Product exists.

    IR-001 is the one identity rule the source describes as tautological: a new
    product family is a new commercial product by definition, and it reads no
    dimension. The executable condition is therefore not "was this called a new
    family" -- nothing in the Fold says that -- but the fact the canonical layer
    can actually answer: there is no Product carrying this product_reference.

    Why the full tuple must still be ESTABLISHED
    --------------------------------------------
    CREATE_PRODUCT is the head of the bootstrap sequence, and the very next
    step is an initial Configuration whose identity is the four-part tuple. A
    product created from a request whose geography or term was never
    established would be a product nothing could configure, and the guards at
    precedence 1 and 2 exist precisely so that an incomplete request concludes
    CANNOT_DECIDE rather than starting a sequence it cannot finish.

    An Unavailable `product_exists` is NOT a match. Unavailable means the
    platform could not look; concluding CREATE_PRODUCT from it would mint a
    canonical product family on the strength of a failed lookup.
    """
    if not identity_inputs_established(context.fold):
        return NOT_MATCHED

    if _known_bool(context, PRODUCT_EXISTS) is not False:
        return NOT_MATCHED

    return PredicateResult(
        verdict=PredicateVerdict.MATCHED,
        detail={"rule_id": IR_001, PRODUCT_EXISTS: False},
    )


# ======================================================================
# IR-013  MATCH  Initial Configuration for Existing Product
# ======================================================================

def ir_013_initial_configuration(context: DecisionContext) -> PredicateResult:
    """MATCHED iff all identity inputs are ESTABLISHED, the product exists, and
    it has no configuration yet.

    An Unavailable fact is NOT a match. `product_exists` unavailable means the
    platform could not look, which is not the same as a product that is absent,
    and concluding CREATE_CONFIGURATION from it would sanction creating a
    configuration under a product nobody confirmed.
    """
    if not identity_inputs_established(context.fold):
        return NOT_MATCHED

    product_exists = _known_bool(context, PRODUCT_EXISTS)
    configuration_count = _known_int(context, EXISTING_CONFIGURATION_COUNT)
    if product_exists is not True or configuration_count != 0:
        return NOT_MATCHED

    return PredicateResult(
        verdict=PredicateVerdict.MATCHED,
        detail={
            "rule_id": IR_013,
            PRODUCT_EXISTS: True,
            EXISTING_CONFIGURATION_COUNT: 0,
        },
    )


# ======================================================================
# IR-010  MATCH  Exact Identity Tuple Match
# ======================================================================

def ir_010_exact_identity_match(context: DecisionContext) -> PredicateResult:
    """MATCHED iff all identity inputs are ESTABLISHED and an existing
    configuration already carries this exact canonical identity.

    The canonical identity must have serialized successfully for the fact to be
    Known at all: the lookup adapter reports `Unavailable` when it could not
    form one, and an Unavailable fact never matches. So this predicate cannot
    conclude NO_BUSINESS_CHANGE on an identity that was never computed.

    Concluding NO_BUSINESS_CHANGE mutates nothing and creates no duplicate
    configuration. It is a statement, not an instruction.
    """
    if not identity_inputs_established(context.fold):
        return NOT_MATCHED

    if _known_bool(context, EXACT_IDENTITY_MATCH_EXISTS) is not True:
        return NOT_MATCHED

    return PredicateResult(
        verdict=PredicateVerdict.MATCHED,
        detail={"rule_id": IR_010, EXACT_IDENTITY_MATCH_EXISTS: True},
    )


# ======================================================================
# IA-PRED-006  MATCH  Additional Configuration for Existing Product
#                     (renders IR-002, IR-003, IR-004)
# ======================================================================

def additional_configuration_for_existing_product(
    context: DecisionContext,
) -> PredicateResult:
    """MATCHED iff the identity is complete, the product exists and already has
    at least one configuration, and no live configuration carries this exact
    canonical identity.

    This is where a geography, term or segment addition lands. IR-002, IR-003
    and IR-004 each propose CREATE_CONFIGURATION for their own dimension, and
    each of those dimensions is one of the four locked identity properties, so
    a tuple that matches no live configuration under an existing product must
    differ in at least one of them. Rendering the three as one predicate is
    faithful because they agree on the outcome; rendering them as three would
    require naming which dimension changed, and a Fold snapshot states what the
    identity IS, not what it previously was.

    ORDERING IS LOAD-BEARING. This runs at precedence 7, after IR-010 at 6.
    Placed before it, a request whose identity already exists would create a
    second configuration carrying an identity that is by construction unique --
    which is the exact proliferation this platform exists to stop.

    product_reference is the fourth locked property, and it is NOT what
    distinguishes this rule: a request naming a product that does not exist is
    IA-PRED-005's business, and it is checked first at precedence 3.

    Every fact must be Known. An Unavailable exact-match fact means the
    platform could not determine whether this identity already exists, and
    creating a configuration on that basis is precisely the duplicate this
    rule's ordering is designed to prevent.
    """
    if not identity_inputs_established(context.fold):
        return NOT_MATCHED

    product_exists = _known_bool(context, PRODUCT_EXISTS)
    configuration_count = _known_int(context, EXISTING_CONFIGURATION_COUNT)
    exact_match = _known_bool(context, EXACT_IDENTITY_MATCH_EXISTS)

    if product_exists is not True:
        return NOT_MATCHED
    if configuration_count is None or configuration_count <= 0:
        return NOT_MATCHED
    if exact_match is not False:
        return NOT_MATCHED

    return PredicateResult(
        verdict=PredicateVerdict.MATCHED,
        detail={
            "rule_id": IR_002_004,
            PRODUCT_EXISTS: True,
            EXISTING_CONFIGURATION_COUNT: configuration_count,
            EXACT_IDENTITY_MATCH_EXISTS: False,
        },
    )


#: Semantic rule id -> predicate, for the four original candidates. Consumed by
#: registration.py's code-built prototype path.
IDENTITY_PREDICATES = {
    IR_010: ir_010_exact_identity_match,
    IR_011: ir_011_missing_required_input,
    IR_012: ir_012_contradicted_required_input,
    IR_013: ir_013_initial_configuration,
}

#: predicate_name -> predicate.
#:
#: This is the seam the ARTIFACT binds through. A compiled release names the
#: predicate it expects in decision_rule_bindings.predicate_name, and the
#: artifact adapter resolves that name here. A name the domain pack does not
#: export fails the resolution outright: a governed binding pointing at code
#: that does not exist is a deployment defect, never a silently skipped rule.
PREDICATES_BY_NAME = {
    "ir_010_exact_identity_match": ir_010_exact_identity_match,
    "ir_011_missing_required_input": ir_011_missing_required_input,
    "ir_012_contradicted_required_input": ir_012_contradicted_required_input,
    "ir_013_initial_configuration": ir_013_initial_configuration,
    "ir_001_no_canonical_product": ir_001_no_canonical_product,
    "additional_configuration_for_existing_product":
        additional_configuration_for_existing_product,
}
