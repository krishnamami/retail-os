"""Claris IDENTITY_ASSESSMENT input contract and canonical identity serializer.

THE LOCKED PROTOTYPE IDENTITY TUPLE (D.4E sections 2 and 3)
-----------------------------------------------------------
Exactly four properties, in exactly this order:

    product_reference | geography | term_months | customer_segment

Nothing else is an identity dimension. tier, package, SLP, pricing_model,
market and channel are deliberately NOT inferred: they are not part of the
locked prototype tuple, and inventing one would silently change what a
configuration IS.

    canonical_identity  is the BUSINESS identity of a configuration.
    input_digest        is a REPLAY fingerprint of one decision's inputs.

They are different things and this module never conflates them. No hash is
ever used as a business identity.

SERIALIZATION RULES (locked)
    * exact field order, delimiter '|', every field LENGTH-PREFIXED (D.4G.2)
    * values come from the Fold's resolved_value
    * term_months renders as a decimal integer string
    * NO case normalization, NO whitespace normalization
    * a missing, EXPLICITLY_UNDEFINED or CONTRADICTED required property MUST
      NOT serialize
    * an invalid state fails as a system/configuration error

There is no escaping, so a '|' inside a value would be ambiguous. That is a
property of the locked prototype format, not an oversight; it is asserted in
the tests so a future format change is a deliberate act.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ...contracts import DecisionContext, FoldSnapshotView, FoldState
from .errors import (
    IdentityNotSerializable,
    InvalidIdentityState,
    InvalidIdentityValue,
)

__all__ = [
    "DECISION_TYPE",
    "SUBJECT_TYPE",
    "IDENTITY_PROPERTIES",
    "IDENTITY_DELIMITER",
    "IDENTITY_ENCODING_VERSION",
    "parse_canonical_identity",
    "NOT_SERIALIZABLE_STATES",
    "IdentityInputState",
    "identity_inputs",
    "missing_identity_properties",
    "contradicted_identity_properties",
    "identity_inputs_established",
    "render_term_months",
    "serialize_canonical_identity",
    "try_serialize_canonical_identity",
]

DECISION_TYPE = "IDENTITY_ASSESSMENT"
SUBJECT_TYPE = "configuration_request"

#: Required logical identity order. Order is part of the contract, so this is a
#: tuple and never a set.
IDENTITY_PROPERTIES: tuple[str, ...] = (
    "product_reference",
    "geography",
    "term_months",
    "customer_segment",
)

IDENTITY_DELIMITER = "|"

#: Serialization scheme version. Bumped at D.4G.2 when length prefixing was
#: introduced; see the module docstring note on the collision defect.
IDENTITY_ENCODING_VERSION = "v2"

#: Governed states in which a required property cannot contribute a value.
#: FoldState.INVALID is deliberately NOT here -- it is a system/configuration
#: error (section 3), not a "cannot serialize" business condition.
NOT_SERIALIZABLE_STATES = frozenset(
    {FoldState.UNREPORTED, FoldState.EXPLICITLY_UNDEFINED, FoldState.CONTRADICTED}
)

#: A canonical decimal integer: no leading '+', no leading zeros, no
#: whitespace, no exponent, no decimal point. '036', ' 36' and '36.0' are
#: REJECTED rather than repaired -- silently normalizing them would make the
#: business identity depend on how a source system happened to spell a number.
_DECIMAL_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")


# ======================================================================
# input inspection -- Fold is the only authority
# ======================================================================

@dataclass(frozen=True)
class IdentityInputState:
    """How each required identity property stands, read from the Fold alone.

    Never from Evidence, never from a source system, never from the raw layer.
    """

    absent: tuple[str, ...]
    unreported: tuple[str, ...]
    explicitly_undefined: tuple[str, ...]
    contradicted: tuple[str, ...]
    invalid: tuple[str, ...]
    established: tuple[str, ...]

    @property
    def missing(self) -> tuple[str, ...]:
        """Section 6: absent, UNREPORTED or EXPLICITLY_UNDEFINED, sorted.

        Sorted, not in tuple order, so the evidence array is stable regardless
        of which property happened to be inspected first.
        """
        return tuple(sorted(self.absent + self.unreported + self.explicitly_undefined))

    @property
    def all_established(self) -> bool:
        return len(self.established) == len(IDENTITY_PROPERTIES)


def identity_inputs(fold: FoldSnapshotView) -> IdentityInputState:
    """Classify every required identity property by its governed Fold state."""
    absent, unreported, undefined, contradicted, invalid, established = (
        [], [], [], [], [], []
    )
    for name in IDENTITY_PROPERTIES:
        prop = fold.property_named(name)
        if prop is None:
            absent.append(name)
            continue
        state = prop.fold_state
        if state is FoldState.ESTABLISHED:
            established.append(name)
        elif state is FoldState.UNREPORTED:
            unreported.append(name)
        elif state is FoldState.EXPLICITLY_UNDEFINED:
            undefined.append(name)
        elif state is FoldState.CONTRADICTED:
            contradicted.append(name)
        elif state is FoldState.INVALID:
            invalid.append(name)
    return IdentityInputState(
        absent=tuple(absent),
        unreported=tuple(unreported),
        explicitly_undefined=tuple(undefined),
        contradicted=tuple(contradicted),
        invalid=tuple(invalid),
        established=tuple(established),
    )


def missing_identity_properties(fold: FoldSnapshotView) -> tuple[str, ...]:
    """Section 6: required properties that are absent, UNREPORTED or
    EXPLICITLY_UNDEFINED. Sorted."""
    return identity_inputs(fold).missing


def contradicted_identity_properties(fold: FoldSnapshotView) -> tuple[str, ...]:
    """Section 7: required properties whose fold_state is CONTRADICTED. Sorted."""
    return tuple(sorted(identity_inputs(fold).contradicted))


def identity_inputs_established(fold: FoldSnapshotView) -> bool:
    """True iff all four required identity properties are ESTABLISHED."""
    return identity_inputs(fold).all_established


# ======================================================================
# value rendering -- Claris domain logic, never the platform's
# ======================================================================

def render_term_months(value: object) -> str:
    """Render a governed term_months as a canonical decimal integer string.

    Section 24. Live Fold supplies resolved_value '36' with
    property_value_type 'integer'; jsonb can equally deliver the Python int 36.
    Both render as '36'.

    float is refused outright rather than converted: 36.0 and 36 would render
    identically today and diverge on the first value binary floating point
    cannot hold exactly, which would make the business identity of a
    configuration depend on a rounding artefact.

    bool is refused because Python's bool is an int, and True would otherwise
    render as the term '1'.
    """
    if isinstance(value, bool):
        raise InvalidIdentityValue(
            f"term_months must not be a boolean, got {value!r}"
        )
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise InvalidIdentityValue(
            f"term_months must not be a float ({value!r}); binary rounding is "
            "not a sound basis for a canonical business identity"
        )
    if isinstance(value, str):
        if not _DECIMAL_INTEGER.match(value):
            raise InvalidIdentityValue(
                f"term_months {value!r} is not a canonical decimal integer; "
                "leading '+', leading zeros, surrounding whitespace, decimal "
                "points and exponents are rejected rather than repaired"
            )
        return value
    raise InvalidIdentityValue(
        f"term_months has unsupported type {type(value).__name__}: {value!r}"
    )


def _rendered_value(name: str, prop) -> str:
    """The exact string this property contributes to the canonical identity."""
    value = prop.resolved_value
    if value is None:
        raise InvalidIdentityValue(
            f"{name} is ESTABLISHED but its resolved_value is None; that is "
            "malformed governed state, not a business condition"
        )
    if name == "term_months":
        return render_term_months(value)
    if isinstance(value, bool) or not isinstance(value, str):
        raise InvalidIdentityValue(
            f"{name} must be a string in the prototype identity tuple, got "
            f"{type(value).__name__}: {value!r}"
        )
    # No case normalization. No whitespace normalization. Deliberate.
    return value


# ======================================================================
# canonical identity serialization
# ======================================================================

def serialize_canonical_identity(source) -> str:
    """The locked Claris prototype canonical identity, or an exception.

    Accepts a FoldSnapshotView or a DecisionContext.

    Raises
        IdentityNotSerializable  a required property is absent, UNREPORTED,
                                 EXPLICITLY_UNDEFINED or CONTRADICTED
        InvalidIdentityState     a required property is INVALID (system)
        InvalidIdentityValue     an ESTABLISHED value cannot be rendered (system)
    """
    fold = source.fold if isinstance(source, DecisionContext) else source
    if not isinstance(fold, FoldSnapshotView):
        raise InvalidIdentityValue(
            "serialize_canonical_identity requires a FoldSnapshotView or a "
            f"DecisionContext, got {type(source).__name__}"
        )

    inputs = identity_inputs(fold)
    if inputs.invalid:
        raise InvalidIdentityState(
            "required identity properties carry FoldState.INVALID: "
            + ", ".join(sorted(inputs.invalid))
        )
    unusable = inputs.missing + tuple(sorted(inputs.contradicted))
    if unusable:
        raise IdentityNotSerializable(
            "canonical identity cannot be serialized; required properties are "
            "not ESTABLISHED: " + ", ".join(sorted(set(unusable)))
        )

    return encode_identity_values(
        _rendered_value(name, fold.property_named(name))
        for name in IDENTITY_PROPERTIES
    )


def encode_identity_values(values) -> str:
    """Length-prefixed canonical encoding. Injective for any input.

    D.4G.2 correction. The previous encoding was a bare '|' join with no
    escaping, so two different tuples could serialize identically:

        ('A|B', 'C', '1', 'D')  ->  'A|B|C|1|D'
        ('A',   'B|C', '1', 'D') ->  'A|B|C|1|D'

    Two distinct business identities collapsing into one canonical identity is
    the worst failure this module could have: the exact-match predicate would
    report NO_BUSINESS_CHANGE for a genuinely different configuration.

    Each field is emitted as <character length>:<value>, so the boundaries are
    pinned by the lengths rather than inferred from the separator. The result
    is uniquely parseable (see parse_canonical_identity), which is what makes
    the encoding injective. No value is escaped, altered or normalized -- the
    business values still travel through verbatim.
    """
    rendered = tuple(values)
    return IDENTITY_DELIMITER.join(
        (IDENTITY_ENCODING_VERSION,)
        + tuple(f"{len(value)}:{value}" for value in rendered)
    )


def parse_canonical_identity(identity: str) -> tuple[str, ...]:
    """Recover the exact field values from a canonical identity.

    Exists to make the injectivity of encode_identity_values testable rather
    than asserted. A canonical identity that does not parse is malformed.
    """
    if not isinstance(identity, str):
        raise InvalidIdentityValue("canonical identity must be a string")
    prefix, separator, remainder = identity.partition(IDENTITY_DELIMITER)
    if prefix != IDENTITY_ENCODING_VERSION or not separator:
        raise InvalidIdentityValue(
            f"canonical identity must begin {IDENTITY_ENCODING_VERSION!r}"
            f"{IDENTITY_DELIMITER!r}; got {identity!r}"
        )
    values: list[str] = []
    position = 0
    while position <= len(remainder):
        marker = remainder.find(":", position)
        if marker < 0:
            raise InvalidIdentityValue(f"malformed canonical identity: {identity!r}")
        digits = remainder[position:marker]
        if not digits.isdigit():
            raise InvalidIdentityValue(f"malformed length prefix in {identity!r}")
        width = int(digits)
        start = marker + 1
        end = start + width
        if end > len(remainder):
            raise InvalidIdentityValue(f"truncated canonical identity: {identity!r}")
        values.append(remainder[start:end])
        if end == len(remainder):
            return tuple(values)
        if remainder[end] != IDENTITY_DELIMITER:
            raise InvalidIdentityValue(f"malformed canonical identity: {identity!r}")
        position = end + 1
    raise InvalidIdentityValue(f"malformed canonical identity: {identity!r}")


def try_serialize_canonical_identity(source) -> Optional[str]:
    """Serialize, or return None when the identity legitimately cannot form.

    None is returned ONLY for the IdentityNotSerializable condition -- the same
    situation IR-011 and IR-012 report as a governed CANNOT_DECIDE. INVALID
    states and unrenderable ESTABLISHED values still raise: section 25 forbids
    turning a system failure into a business outcome, and returning None for
    them would do exactly that one step later.
    """
    try:
        return serialize_canonical_identity(source)
    except IdentityNotSerializable:
        return None
