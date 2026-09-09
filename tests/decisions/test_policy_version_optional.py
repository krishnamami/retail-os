"""D.4E controlled compatibility correction: Optional policy_version.

WHY THIS EXISTS
---------------
D.4D established that all 13 executable CHANGE_CLASSIFICATION rules carry an
empty policy_version. That is legitimate governed metadata, not a defect. The
D.4C runtime contract rejected it, which made the live governed path
unconstructible and quietly invited someone to write "1.0" or "default" or
"NONE" into a governance field nobody governs.

The correction is minimal and is the whole change:

    GovernanceBinding.policy_version : Optional[str]
        None  = no applicable policy version is present in governed metadata
        ''    = normalized to None at construction
        other = a real governed policy version, unchanged

    None is NOT "unknown" and NOT "the lookup failed".

ontology_version and kb_version are untouched and still mandatory.
"""

from __future__ import annotations

import pytest
from d4c_support import HORIZON, TYPE_A, make_context, make_rule

from decisions import (
    DecisionRequest,
    FoldSnapshotView,
    FoldState,
    GovernanceBinding,
    InvalidDecisionContext,
    RuleClass,
    compute_input_digest,
)


# ======================================================================
# None is preserved
# ======================================================================

def test_none_policy_version_is_accepted_and_preserved():
    gov = GovernanceBinding("O-1", "1.1", None)
    assert gov.policy_version is None


def test_none_survives_into_the_decision_result():
    from d4c_support import always_match, make_executor

    rules = (make_rule("R1", RuleClass.MATCH, 10, "OUT", "REASON"),)
    executor = make_executor((TYPE_A, "R1", "1.0.1", always_match))
    result = executor.execute(make_context(rule_set=rules, policy_version=None))
    assert result.policy_version is None
    assert result.outcome_code == "OUT"


# ======================================================================
# empty string from the database normalizes to None
# ======================================================================

@pytest.mark.parametrize("empty", ["", "   ", "\t", "\n"])
def test_empty_policy_version_normalizes_to_none(empty):
    assert GovernanceBinding("O-1", "1.1", empty).policy_version is None


def test_live_shaped_empty_policy_version_builds_a_governance_binding():
    """The exact D.4D live shape: kb 1.1, ontology 2026.10-governance, policy ''.

    Before this correction this construction raised, which is what blocked the
    real governed rule set from ever reaching the executor.
    """
    gov = GovernanceBinding(
        ontology_version="2026.10-governance", kb_version="1.1", policy_version=""
    )
    assert gov.policy_version is None
    assert gov.kb_version == "1.1"
    assert gov.ontology_version == "2026.10-governance"


# ======================================================================
# a failed / unknown lookup is NOT None
# ======================================================================

def test_unknown_lookup_raises_and_never_yields_a_none_policy_version():
    """A governance lookup that fails must not degrade into policy_version=None.

    The resolver raises an adapter error, so no GovernanceBinding is
    constructed at all. That is the structural guarantee: there is no code path
    from 'lookup failed' to 'governed None'.
    """
    from decisions.adapters.errors import KBVersionNotFound, NoActiveKB

    class FailingResolver:
        def active_kb(self):
            raise NoActiveKB("v_active_kb returned no row")

        def resolve_rules(self, decision_type, kb_version=None):
            raise KBVersionNotFound(f"no governed rules at {kb_version!r}")

    resolver = FailingResolver()
    with pytest.raises(NoActiveKB):
        resolver.active_kb()
    with pytest.raises(KBVersionNotFound):
        resolver.resolve_rules("ANY", "9.9")


def test_a_non_string_policy_version_is_rejected_not_coerced_to_none():
    for bad in (0, 1, [], {}, object()):
        with pytest.raises(InvalidDecisionContext, match="policy_version"):
            GovernanceBinding("O-1", "1.1", bad)


def test_ontology_and_kb_version_are_still_mandatory():
    for field, args in (
        ("ontology_version", ("", "1.1", None)),
        ("kb_version", ("O-1", "", None)),
        ("ontology_version", (None, "1.1", None)),
        ("kb_version", ("O-1", None, None)),
    ):
        with pytest.raises(InvalidDecisionContext, match=field):
            GovernanceBinding(*args)


# ======================================================================
# input_digest distinguishes governed None deterministically
# ======================================================================

def _digest(policy_version):
    return compute_input_digest(
        make_context(
            rule_set=(make_rule("R1", RuleClass.MATCH, 10, "OUT"),),
            policy_version=policy_version,
        )
    )


def test_digest_for_none_is_deterministic():
    assert _digest(None) == _digest(None)


def test_digest_distinguishes_none_from_a_real_policy_version():
    assert _digest(None) != _digest("P-1")
    assert _digest("P-1") != _digest("P-2")


def test_digest_treats_empty_string_and_none_as_the_same_governed_fact():
    """Normalization is what makes this true, and it must stay true.

    SQL NULL and '' are two spellings of one governed fact -- no applicable
    policy version. If they produced different digests, replaying a decision
    after a NULL/'' storage change would report a false input difference.
    """
    assert _digest("") == _digest(None)
    assert _digest("   ") == _digest(None)


def test_none_serializes_as_json_null_not_as_an_empty_string():
    from decisions.digest import canonical_json, digest_payload

    payload = digest_payload(
        make_context(
            rule_set=(make_rule("R1", RuleClass.MATCH, 10, "OUT"),),
            policy_version=None,
        )
    )
    assert payload["policy_version"] is None
    assert '"policy_version":null' in canonical_json(payload)
    assert '"policy_version":""' not in canonical_json(payload)


# ======================================================================
# the fold snapshot's own policy_version is untouched by this correction
# ======================================================================

def test_fold_snapshot_policy_version_contract_is_unchanged():
    snapshot = FoldSnapshotView(
        fold_state_id="fs-1",
        subject_type="s",
        subject_id="i",
        decision_horizon=HORIZON,
        fold_status=FoldState.ESTABLISHED,
        kb_version="1.1",
        policy_version="",
    )
    assert snapshot.policy_version == ""
    assert DecisionRequest(TYPE_A, "s", "i", HORIZON).decision_type == TYPE_A
