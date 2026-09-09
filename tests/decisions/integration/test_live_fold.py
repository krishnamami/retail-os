"""Live read-only Fold integration (section 23 A-F)."""

from __future__ import annotations

import pytest
from live_support import IDENTITY_PROPERTIES, SUBJECT_TYPE

from decisions import FoldState
from decisions.ports import FoldLoadStatus


# -- A / B. connection and read-only session ----------------------------

def test_connection_succeeds_through_established_credentials(db):
    context = db.context()
    print(f"\n  connected: db={context['database']} role={context['role']}")
    assert context["database"]
    assert context["role"]


def test_session_is_read_only(db):
    assert db.session_is_read_only(), "session must be pinned READ ONLY"


# -- discovery -----------------------------------------------------------

def test_identity_subjects_discovered(identity_subjects):
    print(f"\n  subjects carrying identity properties: {len(identity_subjects['all'])}")
    for row in identity_subjects["all"]:
        print(
            f"    {row['subject_id']} @ {row['decision_horizon']} "
            f"established={row['established']} unreported={row['unreported']}"
        )
    assert identity_subjects["all"], "no configuration_request identity subjects found"
    assert identity_subjects["complete"], "expected at least one fully ESTABLISHED subject"
    assert identity_subjects["with_unreported"], (
        "expected the known configuration_request with customer_segment UNREPORTED"
    )


# -- C / D. snapshot loads, ESTABLISHED properties correct ---------------

def test_fold_snapshot_loads_for_a_complete_subject(fold_loader, identity_subjects):
    target = identity_subjects["complete"][0]
    result = fold_loader.load(
        SUBJECT_TYPE, target["subject_id"], target["decision_horizon"]
    )
    assert result.status is FoldLoadStatus.FOUND
    snapshot = result.snapshot
    print(
        f"\n  loaded {snapshot.subject_id}: fold_state_id={snapshot.fold_state_id} "
        f"properties={len(snapshot.properties)} status={snapshot.fold_status.value}"
    )
    for name in IDENTITY_PROPERTIES:
        prop = snapshot.property_named(name)
        assert prop is not None, f"{name} absent from snapshot"
        assert prop.fold_state is FoldState.ESTABLISHED
        assert prop.resolved_value is not None
        print(f"    {name} = {prop.resolved_value!r} ({prop.property_value_type})")


def test_term_months_keeps_its_governed_value_type(fold_loader, identity_subjects):
    target = identity_subjects["complete"][0]
    prop = fold_loader.load(
        SUBJECT_TYPE, target["subject_id"], target["decision_horizon"]
    ).snapshot.property_named("term_months")
    assert prop.property_value_type == "integer"
    assert not isinstance(prop.resolved_value, float)


# -- E. UNREPORTED survives ----------------------------------------------

def test_unreported_customer_segment_is_preserved(fold_loader, identity_subjects):
    target = identity_subjects["with_unreported"][0]
    snapshot = fold_loader.load(
        SUBJECT_TYPE, target["subject_id"], target["decision_horizon"]
    ).snapshot

    unreported = [
        name for name in IDENTITY_PROPERTIES
        if snapshot.state_of(name) is FoldState.UNREPORTED
    ]
    print(f"\n  {target['subject_id']} UNREPORTED identity properties: {unreported}")
    assert unreported, "expected at least one UNREPORTED identity property"

    for name in unreported:
        prop = snapshot.property_named(name)
        assert prop.fold_state is FoldState.UNREPORTED
        assert prop.fold_state is not FoldState.ESTABLISHED
        assert prop.resolved_value is None
        assert prop.basis_assertion_ids == ()


# -- F. lineage survives conversion --------------------------------------

def test_basis_assertion_ids_survive_conversion(fold_loader, identity_subjects):
    target = identity_subjects["complete"][0]
    snapshot = fold_loader.load(
        SUBJECT_TYPE, target["subject_id"], target["decision_horizon"]
    ).snapshot
    with_lineage = {
        name: prop.basis_assertion_ids
        for name, prop in snapshot.properties.items()
        if prop.basis_assertion_ids
    }
    print(f"\n  properties carrying assertion lineage: {len(with_lineage)}")
    assert with_lineage, "no per-property lineage survived"
    for name, ids in with_lineage.items():
        assert all(isinstance(i, str) and i for i in ids)


def test_temporal_fields_survive_conversion(fold_loader, identity_subjects):
    target = identity_subjects["complete"][0]
    snapshot = fold_loader.load(
        SUBJECT_TYPE, target["subject_id"], target["decision_horizon"]
    ).snapshot
    established = [p for p in snapshot.properties.values()
                   if p.fold_state is FoldState.ESTABLISHED]
    assert established
    for prop in established:
        assert prop.effective_at is not None
        assert prop.effective_at.tzinfo is not None
        assert prop.latest_known_arrival_at is not None


# -- horizon semantics ----------------------------------------------------

def test_exact_horizon_equality_is_the_lookup(fold_loader, identity_subjects):
    from datetime import timedelta

    target = identity_subjects["complete"][0]
    horizon = target["decision_horizon"]
    assert fold_loader.load(SUBJECT_TYPE, target["subject_id"], horizon).found

    shifted = fold_loader.load(
        SUBJECT_TYPE, target["subject_id"], horizon + timedelta(microseconds=1)
    )
    assert shifted.status is FoldLoadStatus.NOT_FOUND, (
        "lookup must be exact equality, not nearest-earlier-horizon"
    )


def test_unknown_subject_is_not_found_not_an_error(fold_loader, identity_subjects):
    target = identity_subjects["complete"][0]
    result = fold_loader.load(
        SUBJECT_TYPE, "CONFIG-REQ-DOES-NOT-EXIST", target["decision_horizon"]
    )
    assert result.status is FoldLoadStatus.NOT_FOUND
    assert result.snapshot is None
