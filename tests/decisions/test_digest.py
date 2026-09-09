"""R / S: input_digest determinism and sensitivity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from d4c_support import HORIZON, KB, TYPE_A, make_context, make_property, make_rule

from decisions import (
    DIGEST_SCHEME_VERSION,
    DigestSerializationError,
    FoldState,
    RuleClass,
    canonical_json,
    compute_input_digest,
)
from decisions.digest import digest_payload


def _ctx(**overrides):
    base = dict(
        rule_set=(make_rule("R", RuleClass.MATCH, 10, "OUT"),),
        properties={
            "alpha": make_property("alpha", "A", assertions=("a-2", "a-1")),
            "beta": make_property("beta", state=FoldState.UNREPORTED),
        },
        facts={"opaque_count": 0},
        required_properties=("alpha", "beta"),
    )
    base.update(overrides)
    return make_context(**base)


# -- R. same inputs -> same digest ---------------------------------------

def test_digest_is_deterministic_across_calls():
    assert compute_input_digest(_ctx()) == compute_input_digest(_ctx())


def test_digest_is_stable_across_processes():
    """Guards against Python's salted hash() ever creeping in."""
    import subprocess
    import sys
    import os

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script = (
        "import sys; sys.path.insert(0, %r); sys.path.insert(0, %r);"
        "from d4c_support import make_context, make_property, make_rule;"
        "from decisions import RuleClass, FoldState, compute_input_digest;"
        "ctx = make_context(rule_set=(make_rule('R', RuleClass.MATCH, 10, 'OUT'),),"
        "properties={'alpha': make_property('alpha','A',assertions=('a-2','a-1'))});"
        "print(compute_input_digest(ctx))"
        % (repo_root, os.path.dirname(__file__))
    )
    runs = set()
    for seed in ("0", "1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env
        )
        assert out.returncode == 0, out.stderr
        runs.add(out.stdout.strip())
    assert len(runs) == 1, f"digest varied with PYTHONHASHSEED: {runs}"


def test_digest_independent_of_property_insertion_order():
    forward = _ctx(
        properties={
            "alpha": make_property("alpha", "A", assertions=("a-2", "a-1")),
            "beta": make_property("beta", state=FoldState.UNREPORTED),
        }
    )
    reverse = _ctx(
        properties={
            "beta": make_property("beta", state=FoldState.UNREPORTED),
            "alpha": make_property("alpha", "A", assertions=("a-2", "a-1")),
        }
    )
    assert compute_input_digest(forward) == compute_input_digest(reverse)


def test_digest_independent_of_basis_assertion_id_order():
    a = _ctx(properties={"alpha": make_property("alpha", "A", assertions=("a-1", "a-2"))})
    b = _ctx(properties={"alpha": make_property("alpha", "A", assertions=("a-2", "a-1"))})
    assert compute_input_digest(a) == compute_input_digest(b)


def test_digest_excludes_audit_only_request_fields():
    from decisions import DecisionContext, DecisionRequest

    base = _ctx()
    noisy = DecisionContext(
        request=DecisionRequest(
            decision_type=base.request.decision_type,
            subject_type=base.request.subject_type,
            subject_id=base.request.subject_id,
            decision_horizon=base.request.decision_horizon,
            requested_by="someone-else",
            correlation_id="a-different-correlation-id",
            requested_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        ),
        fold=base.fold,
        governance=base.governance,
        facts=base.facts,
    )
    assert compute_input_digest(base) == compute_input_digest(noisy)


# -- S. changed input -> changed digest ----------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"subject_id": "SUBJ-OTHER"},
        {"decision_type": "TEST_READINESS"},
        {"kb_version": "9.9.9"},
        {"policy_version": "P-OTHER"},
        {"ontology_version": "O-OTHER"},
        {"rule_set_digest": "rsd-other"},
        {"facts": {"opaque_count": 1}},
        {"properties": {"alpha": make_property("alpha", "DIFFERENT")}},
    ],
)
def test_changed_governed_input_changes_digest(overrides):
    if "subject_id" in overrides:
        overrides["subject_type"] = "test_subject"
    assert compute_input_digest(_ctx()) != compute_input_digest(_ctx(**overrides))


def test_changed_horizon_changes_digest():
    from decisions import DecisionContext, DecisionRequest, FoldSnapshotView

    base = _ctx()
    later = HORIZON + timedelta(days=1)
    shifted = DecisionContext(
        request=DecisionRequest(TYPE_A, "test_subject", "SUBJ-001", later),
        fold=FoldSnapshotView(
            fold_state_id=base.fold.fold_state_id,
            subject_type="test_subject",
            subject_id="SUBJ-001",
            decision_horizon=later,
            fold_status=FoldState.ESTABLISHED,
            kb_version=base.fold.kb_version,
            policy_version=base.fold.policy_version,
            properties=dict(base.fold.properties),
        ),
        governance=base.governance,
        facts=base.facts,
    )
    assert compute_input_digest(base) != compute_input_digest(shifted)


def test_fold_state_change_alone_changes_digest():
    established = _ctx(properties={"alpha": make_property("alpha", "A", assertions=())})
    unreported = _ctx(
        properties={"alpha": make_property("alpha", state=FoldState.UNREPORTED)}
    )
    assert compute_input_digest(established) != compute_input_digest(unreported)


def test_unreported_property_differs_from_absent_property():
    """null and absent must not digest identically."""
    present = _ctx(properties={"alpha": make_property("alpha", state=FoldState.UNREPORTED)})
    absent = _ctx(properties={})
    assert compute_input_digest(present) != compute_input_digest(absent)


def test_unavailable_fact_differs_from_known_and_from_absent():
    from decisions import DecisionContext, DomainFacts, Known, Unavailable

    def with_facts(facts):
        base = _ctx()
        return DecisionContext(
            request=base.request,
            fold=base.fold,
            governance=base.governance,
            facts=DomainFacts(facts),
        )

    known = with_facts({"f": Known(False)})
    unavailable = with_facts({"f": Unavailable("IDENTITY_NOT_SERIALIZABLE")})
    absent = with_facts({})
    digests = {
        compute_input_digest(known),
        compute_input_digest(unavailable),
        compute_input_digest(absent),
    }
    assert len(digests) == 3


# -- format and canonicalization -----------------------------------------

def test_digest_is_tagged_and_hex():
    digest = compute_input_digest(_ctx())
    scheme, algorithm, hexdigest = digest.split(":")
    assert scheme == DIGEST_SCHEME_VERSION == "v1"
    assert algorithm == "sha256"
    assert len(hexdigest) == 64
    assert hexdigest == hexdigest.lower()
    int(hexdigest, 16)  # valid hex


def test_canonical_json_sorts_keys():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_has_no_insignificant_whitespace():
    assert " " not in canonical_json({"a": [1, 2], "b": {"c": 3}})


def test_canonical_json_timestamp_format():
    ts = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert canonical_json(ts) == '"2026-02-01T00:00:00.000000Z"'


def test_canonical_json_normalizes_offset_to_utc():
    utc = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    offset = datetime(2026, 1, 31, 17, 0, tzinfo=timezone(timedelta(hours=-7)))
    assert canonical_json(utc) == canonical_json(offset)


def test_canonical_json_integers_have_no_exponent_or_decimal():
    assert canonical_json(36) == "36"
    assert canonical_json(10 ** 20) == "100000000000000000000"


def test_canonical_json_booleans_are_lowercase():
    assert canonical_json({"t": True, "f": False}) == '{"f":false,"t":true}'


def test_canonical_json_null_distinct_from_empty_string():
    assert canonical_json(None) != canonical_json("")


def test_float_is_rejected():
    with pytest.raises(DigestSerializationError, match="float"):
        canonical_json(1.5)


def test_naive_datetime_is_rejected():
    with pytest.raises(DigestSerializationError, match="timezone"):
        canonical_json(datetime(2026, 2, 1))


def test_unsupported_type_is_rejected():
    with pytest.raises(DigestSerializationError, match="unsupported type"):
        canonical_json(object())


def test_payload_excludes_evaluated_at_and_executor_metadata():
    payload = digest_payload(_ctx())
    for excluded in (
        "evaluated_at", "executor_version", "requested_at",
        "correlation_id", "requested_by", "decided_at",
    ):
        assert excluded not in payload


def test_payload_includes_the_locked_field_set():
    payload = digest_payload(_ctx())
    for required in (
        "decision_type", "subject_type", "subject_id", "decision_horizon",
        "ontology_version", "kb_version", "policy_version", "rule_set_digest",
        "fold_state_id", "folded_properties", "domain_facts",
        "digest_scheme_version",
    ):
        assert required in payload
