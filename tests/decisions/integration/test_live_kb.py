"""Live read-only governed KB integration (section 23 G-J, and section 18).

METADATA INTEGRATION ONLY. No decision is executed. CHANGE_CLASSIFICATION is
resolved but never run, and no fake predicate is registered against a live
governed rule.
"""

from __future__ import annotations

import pytest
from live_support import (
    EXECUTABLE_DECISION_TYPE,
    NON_EXECUTABLE_DECISION_TYPE,
    PROPOSED_IDENTITY_RULES,
)

from decisions.adapters.errors import NoExecutableRuleSet


# -- G. active KB ---------------------------------------------------------

def test_active_kb_resolves(kb_resolver):
    kb = kb_resolver.active_kb()
    print(f"\n  active KB version: {kb.kb_version}")
    print(f"  v_active_kb columns: {sorted(kb.raw)}")
    assert kb.kb_version


# -- H. CHANGE_CLASSIFICATION metadata ------------------------------------

def test_change_classification_metadata_resolves(kb_resolver):
    resolved = kb_resolver.resolve_rules(EXECUTABLE_DECISION_TYPE)
    print(
        f"\n  {EXECUTABLE_DECISION_TYPE}: {len(resolved.rules)} executable rules "
        f"kb={resolved.kb_version} ontology={resolved.ontology_version} "
        f"policy={resolved.policy_version}"
    )
    print(f"  rule_set_digest: {resolved.rule_set_digest}")
    assert resolved.rules, "expected governed CHANGE_CLASSIFICATION rules"
    for rule in resolved.rules:
        print(
            f"    [{rule.precedence}] {rule.rule_id} -> {rule.outcome_code} "
            f"({rule.rule_name})"
        )


def test_rule_identifiers_precedence_and_outcomes_preserved(kb_resolver):
    resolved = kb_resolver.resolve_rules(EXECUTABLE_DECISION_TYPE)
    for rule in resolved.rules:
        assert rule.rule_id
        assert isinstance(rule.precedence, int)
        assert rule.outcome_code
        assert rule.decision_type == EXECUTABLE_DECISION_TYPE


def test_precedence_levels_match_the_governed_shape(kb_resolver):
    resolved = kb_resolver.resolve_rules(EXECUTABLE_DECISION_TYPE)
    levels = sorted({r.precedence for r in resolved.rules})
    print(f"\n  precedence levels present: {levels}")
    assert levels, "no precedence values resolved"


def test_versions_remain_distinct_fields(kb_resolver):
    resolved = kb_resolver.resolve_rules(EXECUTABLE_DECISION_TYPE)
    assert resolved.kb_version
    assert resolved.ontology_version
    # policy_version may legitimately be empty; it must still be its own field
    assert hasattr(resolved, "policy_version")
    assert resolved.kb_version == resolved.rules[0].kb_version


# -- I. condition is metadata only ----------------------------------------

def test_condition_text_is_carried_but_never_executed(kb_resolver):
    resolved = kb_resolver.resolve_rules(EXECUTABLE_DECISION_TYPE)
    with_condition = [r for r in resolved.rules if r.condition_text]
    print(f"\n  rules carrying condition prose: {len(with_condition)}")
    assert with_condition, "expected governed condition text to be preserved"
    sample = with_condition[0]
    print(f"    sample condition: {sample.condition_text[:90]!r}")
    assert isinstance(sample.condition_text, str)
    # nothing derived from it: no compiled form, no callable
    assert not callable(sample.condition_text)
    assert not hasattr(sample, "compiled_condition")
    assert not hasattr(sample, "predicate")


def test_no_rule_class_is_assigned_from_the_kb(kb_resolver):
    """rule_class is domain registration metadata (D.4C), not KB data."""
    resolved = kb_resolver.resolve_rules(EXECUTABLE_DECISION_TYPE)
    for rule in resolved.rules:
        assert not hasattr(rule, "rule_class")
        assert not hasattr(rule, "predicate_ref")


def test_change_classification_is_not_executed(kb_resolver):
    """Resolution returns metadata. It does not evaluate anything."""
    resolved = kb_resolver.resolve_rules(EXECUTABLE_DECISION_TYPE)
    assert not hasattr(resolved, "outcome_code")
    assert not hasattr(resolved, "matched_rule_id")
    assert not hasattr(resolved, "input_digest")


# -- J / section 18. IDENTITY_ASSESSMENT safety boundary ------------------

def test_identity_assessment_has_no_executable_rule_set(kb_resolver):
    """The D.3C safety boundary, as a regression test.

    IR-010..IR-013 are 'proposed' semantic candidates in
    claris_kb.identity_rules. They must not appear as executable rules, and the
    resolver must not promote them.
    """
    with pytest.raises(NoExecutableRuleSet) as excinfo:
        kb_resolver.resolve_rules(NON_EXECUTABLE_DECISION_TYPE)
    message = str(excinfo.value)
    print(f"\n  {NON_EXECUTABLE_DECISION_TYPE} -> NoExecutableRuleSet: {message}")
    assert "CANNOT_DECIDE" not in message, (
        "an absent runtime rule set is a system status, not a business outcome"
    )


def test_no_identity_assessment_rows_exist_in_decision_rules(db):
    rows = db.query(
        "SELECT count(*) AS n FROM claris_kb.decision_rules WHERE decision_type = %s",
        (NON_EXECUTABLE_DECISION_TYPE,),
    )
    print(f"\n  decision_rules rows for {NON_EXECUTABLE_DECISION_TYPE}: {rows[0]['n']}")
    assert rows[0]["n"] == 0


def test_proposed_identity_rules_remain_proposed(db):
    rows = db.query(
        """
        SELECT rule_id, kb_version, status
        FROM claris_kb.identity_rules
        WHERE rule_id = ANY(%s)
        ORDER BY rule_id, kb_version
        """,
        (list(PROPOSED_IDENTITY_RULES),),
    )
    print("\n  semantic identity candidates:")
    for row in rows:
        print(f"    {row['rule_id']} kb={row['kb_version']} status={row['status']}")
    assert rows, "expected IR-010..IR-013 in claris_kb.identity_rules"
    for row in rows:
        assert row["status"] == "proposed", (
            f"{row['rule_id']} status changed to {row['status']!r}; D.4D must not "
            "activate semantic candidates"
        )
        assert row["kb_version"] == "1.0.1"


def test_active_view_exposes_no_identity_assessment_rules(db):
    rows = db.query(
        "SELECT count(*) AS n FROM claris_kb.v_active_decision_rules "
        "WHERE decision_type = %s",
        (NON_EXECUTABLE_DECISION_TYPE,),
    )
    assert rows[0]["n"] == 0
