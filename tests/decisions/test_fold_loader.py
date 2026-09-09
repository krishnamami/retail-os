"""D.4D unit tests: Fold row -> FoldProperty conversion and validation.

NO PostgreSQL. NO AWS. NO network. A fake row source stands in for the driver.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from d4c_support import HORIZON

from decisions import FoldState
from decisions.adapters.errors import (
    DuplicateFoldSnapshot,
    InvalidFoldPropertyState,
    MalformedFoldSnapshot,
)
from decisions.adapters.fold_postgres import (
    FOLD_SNAPSHOT_SQL,
    PostgresFoldLoader,
    build_snapshot_view,
    parse_assertion_ids,
    parse_fold_property,
    parse_folded_properties,
    parse_timestamp,
)
from decisions.ports import FoldLoadStatus

EFFECTIVE = datetime(2026, 2, 1, tzinfo=timezone.utc)
ARRIVED = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)


def element(
    name="customer_segment",
    value="enterprise",
    value_type="string",
    state="ESTABLISHED",
    assertions=("f1331653-a064-4d2b-802d-9e948f9984a1",),
):
    return {
        "property_name": name,
        "resolved_value": value,
        "property_value_type": value_type,
        "fold_state": state,
        "effective_at": EFFECTIVE if state == "ESTABLISHED" else None,
        "latest_known_arrival_at": ARRIVED if state == "ESTABLISHED" else None,
        "basis_assertion_ids": list(assertions) if state == "ESTABLISHED" else [],
    }


def row(properties=None, **overrides):
    base = {
        "fold_state_id": "8b1d0c3e-0000-0000-0000-000000000001",
        "decision_horizon": HORIZON,
        "subject_type": "configuration_request",
        "subject_id": "CONFIG-REQ-2026-001",
        "fold_status": "ESTABLISHED",
        "folded_properties": properties if properties is not None else [element()],
        "basis_assertion_ids": [],
        "kb_version": "1.0.1",
        "policy_version": "P-1",
        "fold_computed_at": ARRIVED,
    }
    base.update(overrides)
    return base


class FakeDB:
    """Stands in for ReadOnlyDatabase. Records the SQL it was asked to run."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query(self, sql, params=None):
        self.calls.append((sql, params))
        return list(self.rows)


# ======================================================================
# JSONB array parsing
# ======================================================================

def test_parses_jsonb_array_of_property_objects():
    props = parse_folded_properties([element("geography", "NAMER"), element()])
    assert set(props) == {"geography", "customer_segment"}
    assert props["geography"].resolved_value == "NAMER"


def test_parses_array_supplied_as_json_text():
    raw = json.dumps([element("geography", "NAMER")], default=str)
    props = parse_folded_properties(raw)
    assert props["geography"].resolved_value == "NAMER"


def test_all_seven_governed_keys_survive_conversion():
    prop = parse_fold_property(element("term_months", 36, "integer"))
    assert prop.property_name == "term_months"
    assert prop.resolved_value == 36
    assert prop.property_value_type == "integer"
    assert prop.fold_state is FoldState.ESTABLISHED
    assert prop.effective_at == EFFECTIVE
    assert prop.latest_known_arrival_at == ARRIVED
    assert prop.basis_assertion_ids == ("f1331653-a064-4d2b-802d-9e948f9984a1",)


# ======================================================================
# governed state preservation -- no business interpretation
# ======================================================================

def test_unreported_is_preserved_not_coerced():
    prop = parse_fold_property(element("customer_segment", None, None, "UNREPORTED"))
    assert prop.fold_state is FoldState.UNREPORTED
    assert prop.resolved_value is None
    assert prop.property_value_type is None
    assert prop.basis_assertion_ids == ()
    # emphatically NOT turned into an ESTABLISHED null
    assert prop.fold_state is not FoldState.ESTABLISHED


def test_contradicted_is_preserved_not_turned_into_an_outcome():
    prop = parse_fold_property(element("geography", None, None, "CONTRADICTED"))
    assert prop.fold_state is FoldState.CONTRADICTED
    assert not hasattr(prop, "outcome_code")


def test_explicitly_undefined_is_preserved():
    prop = parse_fold_property(element("x", None, None, "EXPLICITLY_UNDEFINED"))
    assert prop.fold_state is FoldState.EXPLICITLY_UNDEFINED


def test_invalid_state_is_representable_but_flagged_by_the_contract():
    """INVALID is in the enum (claris_config_state_type) though the row-level
    CHECK omits it. The loader represents it; the executor treats it as
    blocking evidence."""
    prop = parse_fold_property(element("x", None, None, "INVALID"))
    assert prop.fold_state is FoldState.INVALID


def test_unknown_state_is_rejected():
    with pytest.raises(InvalidFoldPropertyState, match="outside the governed vocabulary"):
        parse_fold_property(element("x", None, None, "PROBABLY_FINE"))


def test_rejection_message_explains_the_unconstrained_element_state():
    with pytest.raises(InvalidFoldPropertyState, match="element-level fold_state is unconstrained"):
        parse_fold_property(element("x", None, None, "NOPE"))


# ======================================================================
# malformed data is surfaced, never repaired
# ======================================================================

def test_missing_property_name_rejected():
    bad = element()
    del bad["property_name"]
    with pytest.raises(MalformedFoldSnapshot, match="property_name"):
        parse_fold_property(bad)


@pytest.mark.parametrize("name", ["", "   ", None, 7])
def test_blank_property_name_rejected(name):
    with pytest.raises(MalformedFoldSnapshot, match="property_name"):
        parse_fold_property(element(name))


def test_missing_governed_key_rejected():
    bad = element()
    del bad["basis_assertion_ids"]
    with pytest.raises(MalformedFoldSnapshot, match="missing governed keys"):
        parse_fold_property(bad)


def test_duplicate_property_name_rejected():
    with pytest.raises(MalformedFoldSnapshot, match="duplicate property_name"):
        parse_folded_properties([element("geography"), element("geography")])


def test_non_array_folded_properties_rejected():
    with pytest.raises(MalformedFoldSnapshot, match="must be a JSON array"):
        parse_folded_properties({"geography": "NAMER"})


def test_null_folded_properties_rejected():
    with pytest.raises(MalformedFoldSnapshot, match="null"):
        parse_folded_properties(None)


def test_invalid_json_rejected():
    with pytest.raises(MalformedFoldSnapshot, match="not valid JSON"):
        parse_folded_properties("{not json")


def test_element_that_is_not_an_object_rejected():
    with pytest.raises(MalformedFoldSnapshot, match="must be an object"):
        parse_folded_properties(["just a string"])


@pytest.mark.parametrize("bad", [["not-a-list-entry", 5], "{}", 42])
def test_invalid_basis_assertion_ids_rejected(bad):
    with pytest.raises(MalformedFoldSnapshot):
        parse_assertion_ids(bad, property_name="p")


def test_naive_timestamp_rejected():
    with pytest.raises(MalformedFoldSnapshot, match="not timezone-aware"):
        parse_timestamp(datetime(2026, 2, 1), field="effective_at", property_name="p")


def test_unparseable_timestamp_rejected():
    with pytest.raises(MalformedFoldSnapshot, match="not a valid timestamp"):
        parse_timestamp("last Tuesday", field="effective_at", property_name="p")


@pytest.mark.parametrize(
    "text",
    [
        "2026-02-01 00:00:00+00",     # PostgreSQL default rendering
        "2026-02-01 00:00:00+0000",
        "2026-02-01 00:00:00+00:00",
        "2026-02-01T00:00:00Z",
        "2026-02-01T00:00:00+00:00",
    ],
)
def test_timestamp_accepted_from_every_postgres_offset_form(text):
    """Python 3.10 rejects a '+00' offset that 3.11+ accepts; the loader
    normalises so behaviour is identical across 3.10/3.11/3.12."""
    assert parse_timestamp(text, field="effective_at", property_name="p") == EFFECTIVE


def test_offset_normalisation_is_explicit():
    from decisions.adapters.fold_postgres import _normalise_iso

    assert _normalise_iso("2026-02-01 00:00:00+00") == "2026-02-01T00:00:00+00:00"
    assert _normalise_iso("2026-02-01 00:00:00-0700") == "2026-02-01T00:00:00-07:00"
    assert _normalise_iso("2026-02-01T00:00:00Z") == "2026-02-01T00:00:00+00:00"


def test_snapshot_missing_column_rejected():
    bad = row()
    del bad["kb_version"]
    with pytest.raises(MalformedFoldSnapshot, match="missing column"):
        build_snapshot_view(bad)


def test_snapshot_invalid_fold_status_rejected():
    with pytest.raises(InvalidFoldPropertyState):
        build_snapshot_view(row(fold_status="SOMEWHAT_ESTABLISHED"))


# ======================================================================
# lineage preservation
# ======================================================================

def test_snapshot_lineage_preserved():
    view = build_snapshot_view(row())
    assert view.fold_state_id == "8b1d0c3e-0000-0000-0000-000000000001"
    assert view.subject_type == "configuration_request"
    assert view.subject_id == "CONFIG-REQ-2026-001"
    assert view.decision_horizon == HORIZON
    assert view.kb_version == "1.0.1"
    assert view.policy_version == "P-1"
    assert view.fold_computed_at == ARRIVED


def test_per_property_assertion_ids_preserved_in_order():
    view = build_snapshot_view(
        row([element("geography", "NAMER", assertions=("a-2", "a-1", "a-3"))])
    )
    assert view.properties["geography"].basis_assertion_ids == ("a-2", "a-1", "a-3")


# ======================================================================
# lookup semantics
# ======================================================================

def test_lookup_uses_exact_horizon_equality():
    """The governed convention, established from the repository."""
    assert "decision_horizon = %s" in FOLD_SNAPSHOT_SQL
    assert "<=" not in FOLD_SNAPSHOT_SQL
    assert "ORDER BY" not in FOLD_SNAPSHOT_SQL.upper().split("WHERE")[-1]


def test_loader_passes_all_three_key_components():
    db = FakeDB([row()])
    PostgresFoldLoader(db).load("configuration_request", "CONFIG-REQ-2026-001", HORIZON)
    _sql, params = db.calls[0]
    assert params == ("configuration_request", "CONFIG-REQ-2026-001", HORIZON)


def test_snapshot_found():
    result = PostgresFoldLoader(FakeDB([row()])).load(
        "configuration_request", "CONFIG-REQ-2026-001", HORIZON
    )
    assert result.status is FoldLoadStatus.FOUND
    assert result.found
    assert result.snapshot.subject_id == "CONFIG-REQ-2026-001"


def test_snapshot_not_found_is_a_status_not_an_exception():
    """D.4B V-2 is open, so the loader reports rather than classifying."""
    result = PostgresFoldLoader(FakeDB([])).load("configuration_request", "X", HORIZON)
    assert result.status is FoldLoadStatus.NOT_FOUND
    assert not result.found
    assert result.snapshot is None
    assert "no Fold snapshot" in result.detail


def test_duplicate_snapshot_raises():
    with pytest.raises(DuplicateFoldSnapshot, match="fold_state_unique_horizon"):
        PostgresFoldLoader(FakeDB([row(), row()])).load(
            "configuration_request", "CONFIG-REQ-2026-001", HORIZON
        )


def test_naive_horizon_rejected_before_query():
    db = FakeDB([row()])
    with pytest.raises(MalformedFoldSnapshot, match="timezone-aware"):
        PostgresFoldLoader(db).load("configuration_request", "X", datetime(2026, 2, 1))
    assert db.calls == [], "must fail before touching the database"


def test_different_horizon_is_a_different_lookup():
    db = FakeDB([])
    loader = PostgresFoldLoader(db)
    loader.load("configuration_request", "X", HORIZON)
    loader.load("configuration_request", "X", HORIZON + timedelta(days=1))
    assert db.calls[0][1][2] != db.calls[1][1][2]


# ======================================================================
# the loader is domain-agnostic
# ======================================================================

def test_fold_loader_knows_no_decision_type():
    """Documentation may name decision types to say it ignores them.
    Executable code may not mention them at all."""
    import decisions.adapters.fold_postgres as module
    from d4d_support import executable_source

    code = executable_source(module)
    for token in ("identity_assessment", "change_classification", "launch_readiness",
                  "canonical_identity", "ir-010", "ir-011", "ir-012", "ir-013",
                  "product_reference", "customer_segment"):
        assert token not in code, f"{token!r} leaked into fold loader logic"
