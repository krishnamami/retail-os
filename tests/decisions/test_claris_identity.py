"""D.4E sections 2, 3, 24: identity input contract and canonical serializer."""

from __future__ import annotations

import pytest
from d4e_support import (
    EXPECTED_CANONICAL_IDENTITY,
    identity_property,
    make_fold,
)

from decisions import FoldState
from decisions.domains.claris import (
    IDENTITY_DELIMITER,
    parse_canonical_identity,
    IDENTITY_PROPERTIES,
    contradicted_identity_properties,
    identity_inputs,
    identity_inputs_established,
    missing_identity_properties,
    render_term_months,
    serialize_canonical_identity,
    try_serialize_canonical_identity,
)
from decisions.domains.claris.errors import (
    IdentityNotSerializable,
    InvalidIdentityState,
    InvalidIdentityValue,
)


# ======================================================================
# section 2 -- the input contract
# ======================================================================

def test_identity_tuple_is_exactly_four_properties_in_locked_order():
    assert IDENTITY_PROPERTIES == (
        "product_reference",
        "geography",
        "term_months",
        "customer_segment",
    )


@pytest.mark.parametrize(
    "not_an_identity_dimension",
    ["tier", "package", "slp", "pricing_model", "market", "channel"],
)
def test_no_extra_identity_dimension_is_inferred(not_an_identity_dimension):
    assert not_an_identity_dimension not in IDENTITY_PROPERTIES


def test_identity_order_is_a_tuple_not_a_set():
    """Order is part of the contract, so the container must preserve it."""
    assert isinstance(IDENTITY_PROPERTIES, tuple)


# ======================================================================
# section 3 -- serialization
# ======================================================================

def test_canonical_identity_exact_string():
    assert serialize_canonical_identity(make_fold()) == EXPECTED_CANONICAL_IDENTITY
    assert serialize_canonical_identity(make_fold()) == "v2|8:PROD-001|5:NAMER|2:36|10:enterprise"


def test_delimiter_is_a_pipe_and_separates_the_version_and_four_fields():
    """D.4G.2: four separators now -- the scheme version plus four fields.

    The count is no longer the integrity property; length prefixing is. A
    value containing '|' raises the count without changing what parses.
    """
    identity = serialize_canonical_identity(make_fold())
    assert IDENTITY_DELIMITER == "|"
    assert identity.startswith("v2|")
    assert len(parse_canonical_identity(identity)) == 4


def test_field_order_is_the_locked_order():
    identity = serialize_canonical_identity(
        make_fold(
            values={
                "product_reference": "A",
                "geography": "B",
                "term_months": "1",
                "customer_segment": "D",
            }
        )
    )
    assert identity == "v2|1:A|1:B|1:1|1:D"
    assert parse_canonical_identity(identity) == ("A", "B", "1", "D")


def test_no_case_normalization():
    identity = serialize_canonical_identity(
        make_fold(values={"geography": "NaMeR", "customer_segment": "Enterprise"})
    )
    assert "NaMeR" in identity and "Enterprise" in identity
    assert identity == "v2|8:PROD-001|5:NaMeR|2:36|10:Enterprise"


def test_no_whitespace_normalization():
    identity = serialize_canonical_identity(
        make_fold(values={"geography": " NAMER "})
    )
    assert identity == "v2|8:PROD-001|7: NAMER |2:36|10:enterprise"


def test_a_delimiter_in_a_value_cannot_collide(D4G2=True):
    """D.4G.2: the ambiguity this test used to lock in is now corrected.

    The previous contract joined the four values on '|' with no escaping, so a
    value containing the delimiter produced an identity another tuple could
    also produce. Length prefixing removes the ambiguity without escaping,
    altering or normalizing any business value.
    """
    identity = serialize_canonical_identity(
        make_fold(values={"geography": "NA|MER"})
    )
    assert identity == "v2|8:PROD-001|6:NA|MER|2:36|10:enterprise"
    assert "\\" not in identity  # still no escaping; the length pins the field


def test_canonical_identity_is_not_a_digest():
    identity = serialize_canonical_identity(make_fold())
    assert not identity.startswith("v1:")
    assert "sha256" not in identity
    assert identity == EXPECTED_CANONICAL_IDENTITY


def test_empty_string_established_still_serializes():
    """Section 6: emptiness is not defined as absence by the locked contract."""
    identity = serialize_canonical_identity(make_fold(values={"geography": ""}))
    assert identity == "v2|8:PROD-001|0:|2:36|10:enterprise"


# -- states that must NOT serialize --------------------------------------

@pytest.mark.parametrize("name", IDENTITY_PROPERTIES)
@pytest.mark.parametrize(
    "state", [FoldState.UNREPORTED, FoldState.EXPLICITLY_UNDEFINED, FoldState.CONTRADICTED]
)
def test_non_established_required_property_does_not_serialize(name, state):
    with pytest.raises(IdentityNotSerializable, match=name):
        serialize_canonical_identity(make_fold(states={name: state}))


@pytest.mark.parametrize("name", IDENTITY_PROPERTIES)
def test_absent_required_property_does_not_serialize(name):
    with pytest.raises(IdentityNotSerializable, match=name):
        serialize_canonical_identity(make_fold(omit=(name,)))


def test_try_serialize_returns_none_instead_of_raising():
    assert try_serialize_canonical_identity(
        make_fold(states={"customer_segment": FoldState.UNREPORTED})
    ) is None
    assert try_serialize_canonical_identity(make_fold()) == EXPECTED_CANONICAL_IDENTITY


# -- invalid state is a SYSTEM failure ------------------------------------

def test_invalid_state_is_a_system_error_not_a_not_serializable_condition():
    with pytest.raises(InvalidIdentityState, match="INVALID"):
        serialize_canonical_identity(make_fold(states={"geography": FoldState.INVALID}))


def test_try_serialize_does_not_swallow_an_invalid_state():
    """Section 25: a system failure must never become a business outcome."""
    with pytest.raises(InvalidIdentityState):
        try_serialize_canonical_identity(
            make_fold(states={"geography": FoldState.INVALID})
        )


def test_established_property_with_none_value_is_a_system_error():
    fold = make_fold()
    broken = dict(fold.properties)
    broken["geography"] = identity_property(
        "geography", value="x", state=FoldState.ESTABLISHED
    )
    object.__setattr__(broken["geography"], "resolved_value", None)
    from decisions import FoldSnapshotView

    rebuilt = FoldSnapshotView(
        fold_state_id=fold.fold_state_id,
        subject_type=fold.subject_type,
        subject_id=fold.subject_id,
        decision_horizon=fold.decision_horizon,
        fold_status=fold.fold_status,
        kb_version=fold.kb_version,
        policy_version=fold.policy_version,
        properties=broken,
    )
    with pytest.raises(InvalidIdentityValue, match="resolved_value is None"):
        serialize_canonical_identity(rebuilt)


# ======================================================================
# section 24 -- term_months
# ======================================================================

def test_live_shaped_string_integer_renders_unchanged():
    assert render_term_months("36") == "36"


def test_python_int_renders_as_a_decimal_string():
    assert render_term_months(36) == "36"
    assert render_term_months(0) == "0"
    assert render_term_months(-12) == "-12"


@pytest.mark.parametrize(
    "bad",
    ["36.0", "36.", "3.6e1", " 36", "36 ", "+36", "036", "", "thirty-six", "1_000", "0x24"],
)
def test_invalid_integer_representations_are_rejected(bad):
    with pytest.raises(InvalidIdentityValue):
        render_term_months(bad)


def test_float_is_refused_rather_than_converted():
    with pytest.raises(InvalidIdentityValue, match="float"):
        render_term_months(36.0)


def test_bool_is_refused_because_python_bools_are_ints():
    with pytest.raises(InvalidIdentityValue, match="boolean"):
        render_term_months(True)


def test_invalid_term_months_fails_the_whole_serialization():
    with pytest.raises(InvalidIdentityValue, match="term_months"):
        serialize_canonical_identity(make_fold(values={"term_months": "36.0"}))


def test_a_non_string_non_integer_identity_value_is_refused():
    with pytest.raises(InvalidIdentityValue, match="geography"):
        serialize_canonical_identity(make_fold(values={"geography": 42}))


# ======================================================================
# input inspection helpers
# ======================================================================

def test_all_established_is_reported():
    inputs = identity_inputs(make_fold())
    assert inputs.all_established
    assert identity_inputs_established(make_fold())
    assert inputs.missing == ()
    assert inputs.contradicted == ()


def test_missing_covers_unreported_undefined_and_absent_but_not_contradicted():
    fold = make_fold(
        states={
            "customer_segment": FoldState.UNREPORTED,
            "geography": FoldState.EXPLICITLY_UNDEFINED,
            "product_reference": FoldState.CONTRADICTED,
        },
        omit=("term_months",),
    )
    assert missing_identity_properties(fold) == (
        "customer_segment",
        "geography",
        "term_months",
    )
    assert contradicted_identity_properties(fold) == ("product_reference",)


def test_missing_is_sorted_regardless_of_tuple_order():
    fold = make_fold(
        states={
            "term_months": FoldState.UNREPORTED,
            "customer_segment": FoldState.UNREPORTED,
            "geography": FoldState.UNREPORTED,
        }
    )
    result = missing_identity_properties(fold)
    assert result == tuple(sorted(result))
