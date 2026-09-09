"""D.4D unit tests: governed KB resolution, rule_class separation, safety.

NO PostgreSQL. NO AWS. NO network.
"""

from __future__ import annotations

import pytest
from d4d_support import executable_source

from decisions import RuleClass
from decisions.adapters import kb_postgres
from decisions.adapters.errors import (
    GovernanceVersionAmbiguity,
    KBVersionNotFound,
    MultipleActiveKB,
    NoActiveKB,
    NoExecutableRuleSet,
    UnboundGovernedRule,
)
from decisions.adapters.kb_postgres import (
    ACTIVE_KB_SQL,
    ACTIVE_RULE_COUNT_SQL,
    GOVERNED_RULE_COLUMNS,
    PostgresKBResolver,
    build_rules_sql,
    compute_rule_set_digest,
    map_rule_row,
)
from decisions.ports import GovernedRuleMetadata, RuleClassBinding, bind_rule_metadata

CONDITION = "changed_dimensions = {geo} AND all other dims unchanged"


def rule_row(rule_id="00000000-0000-0000-0000-00000000000a", **overrides):
    base = {
        "decision_rule_id": rule_id,
        "decision_type": "CHANGE_CLASSIFICATION",
        "kb_version": "1.0.1",
        "ontology_version": "O-1",
        "policy_version": "P-1",
        "rule_name": "Single geo dimension modified",
        "condition": CONDITION,
        "outcome_code": "GEO_ADD",
        "precedence": 1,
        "required_evidence": None,
        "missing_evidence_action": "Proceed (accept geo change as sufficient)",
        "contradiction_action": "N/A",
        "status": "ACTIVE",
        "authority": "Product Mgmt",
        "blocking_note": None,
    }
    base.update(overrides)
    return base


class FakeDB:
    def __init__(self, *, kb_rows=None, rule_rows=None, columns=None):
        self.kb_rows = kb_rows if kb_rows is not None else [{"kb_version": "1.0.1"}]
        self.rule_rows = rule_rows if rule_rows is not None else [rule_row()]
        self.columns = columns if columns is not None else list(rule_row())
        self.queries = []

    def query(self, sql, params=None):
        self.queries.append((sql, params))
        if "information_schema.columns" in sql:
            return [{"column_name": c} for c in self.columns]
        if "v_active_kb" in sql:
            return list(self.kb_rows)
        if "v_active_decision_rules" in sql:
            return [{"n": len(self.rule_rows)}]
        return list(self.rule_rows)


# ======================================================================
# rule metadata mapping
# ======================================================================

def test_maps_governed_columns():
    meta = map_rule_row(rule_row())
    assert meta.decision_type == "CHANGE_CLASSIFICATION"
    assert meta.rule_id == "00000000-0000-0000-0000-00000000000a"
    assert meta.rule_name == "Single geo dimension modified"
    assert meta.precedence == 1
    assert meta.outcome_code == "GEO_ADD"
    assert meta.status == "ACTIVE"
    assert meta.authority == "Product Mgmt"


def test_condition_preserved_verbatim_as_metadata():
    meta = map_rule_row(rule_row())
    assert meta.condition_text == CONDITION


def test_missing_and_contradiction_actions_preserved():
    meta = map_rule_row(rule_row())
    assert meta.missing_evidence_action.startswith("Proceed")
    assert meta.contradiction_action == "N/A"


def test_missing_required_column_rejected():
    bad = rule_row()
    del bad["outcome_code"]
    with pytest.raises(KeyError, match="outcome_code"):
        map_rule_row(bad)


def test_rule_set_digest_is_order_independent_and_deterministic():
    a = map_rule_row(rule_row("aaa"))
    b = map_rule_row(rule_row("bbb", outcome_code="TERM_ADD"))
    assert compute_rule_set_digest([a, b]) == compute_rule_set_digest([b, a])
    assert compute_rule_set_digest([a, b]).startswith("v1:sha256:")


def test_rule_set_digest_changes_when_the_rule_set_changes():
    a = map_rule_row(rule_row("aaa"))
    b = map_rule_row(rule_row("aaa", precedence=99))
    assert compute_rule_set_digest([a]) != compute_rule_set_digest([b])


# ======================================================================
# rule_class is NOT in the KB and is NOT inferred
# ======================================================================

def test_governed_metadata_carries_no_rule_class():
    meta = map_rule_row(rule_row())
    assert not hasattr(meta, "rule_class")
    assert not hasattr(meta, "predicate_ref")


def test_resolver_never_assigns_rule_class():
    code = executable_source(kb_postgres)
    for token in ("ruleclass", "rule_class", "guard", "fallback", "predicate_ref"):
        assert token not in code, f"{token!r} appears in KB resolver logic"


def test_rule_class_enters_only_through_a_domain_binding():
    meta = map_rule_row(rule_row("R1"))
    bound = bind_rule_metadata(
        [meta],
        {"R1": RuleClassBinding("R1", RuleClass.GUARD, "ref::R1")},
    )
    assert bound[0].rule_class is RuleClass.GUARD
    assert bound[0].predicate_ref == "ref::R1"
    # governed values survive the binding untouched
    assert bound[0].definition.outcome_code == "GEO_ADD"
    assert bound[0].precedence == 1


def test_unbound_governed_rule_is_not_silently_dropped():
    meta = map_rule_row(rule_row("R1"))
    with pytest.raises(UnboundGovernedRule, match="R1"):
        bind_rule_metadata([meta], {})


def test_domain_may_override_precedence_explicitly():
    meta = map_rule_row(rule_row("R1"))
    bound = bind_rule_metadata(
        [meta],
        {"R1": RuleClassBinding("R1", RuleClass.MATCH, "ref", precedence_override=42)},
    )
    assert bound[0].precedence == 42


# ======================================================================
# condition is never executed
# ======================================================================

def test_no_dynamic_execution_anywhere_in_the_adapters():
    """`re.compile` is fine; bare eval/exec/compile/__import__ are not."""
    import re as _re

    from decisions.adapters import connection, fold_postgres

    forbidden = _re.compile(r"(?<![\w.])(eval|exec|compile|__import__)\s*\(")
    for module in (kb_postgres, fold_postgres, connection):
        code = executable_source(module)
        hits = forbidden.findall(code)
        assert not hits, f"dynamic execution in {module.__name__}: {hits}"
        assert "ast.parse" not in code


def test_condition_text_is_carried_verbatim_and_nothing_more():
    """The resolver stores the prose and offers no way to interpret it."""
    weird = "IF x = true: REQUIRE y; |changed| > 1 AND no rule resolves"
    meta = map_rule_row(rule_row(condition=weird))
    assert meta.condition_text == weird

    # no attribute, method or function anywhere in the resolver evaluates it
    for name in dir(kb_postgres):
        assert "parse_condition" not in name
        assert "eval_condition" not in name
    assert not hasattr(meta, "evaluate")
    assert not hasattr(meta, "matches")


# ======================================================================
# active KB resolution
# ======================================================================

def test_active_kb_resolved():
    kb = PostgresKBResolver(FakeDB()).active_kb()
    assert kb.kb_version == "1.0.1"
    assert kb.raw["kb_version"] == "1.0.1"


def test_no_active_kb_fails_safely():
    with pytest.raises(NoActiveKB, match="no row"):
        PostgresKBResolver(FakeDB(kb_rows=[])).active_kb()


def test_multiple_active_kb_fails_safely():
    with pytest.raises(MultipleActiveKB, match="2 rows"):
        PostgresKBResolver(
            FakeDB(kb_rows=[{"kb_version": "1.0.1"}, {"kb_version": "1.0.2"}])
        ).active_kb()


def test_active_kb_without_kb_version_column_reports_available_columns():
    with pytest.raises(NoActiveKB, match="available columns"):
        PostgresKBResolver(FakeDB(kb_rows=[{"something_else": 1}])).active_kb()


def test_requested_kb_version_not_found():
    resolver = PostgresKBResolver(FakeDB(rule_rows=[]))
    with pytest.raises(KBVersionNotFound, match="9.9.9"):
        resolver.resolve_rules("CHANGE_CLASSIFICATION", "9.9.9")


# ======================================================================
# proposed / non-executable rule safety  (the D.3C boundary)
# ======================================================================

def test_no_resolver_sql_touches_identity_rules():
    """IR-010..IR-013 live in claris_kb.identity_rules as 'proposed'.

    Behavioural, not a source grep: every statement the resolver actually
    issues is inspected. (The word appears in one error message, which says
    those rules are NOT promoted -- that is the opposite of reading them.)
    """
    for sql in (ACTIVE_KB_SQL, ACTIVE_RULE_COUNT_SQL,
                kb_postgres.ACTIVE_RULE_IDS_SQL,
                build_rules_sql(set(GOVERNED_RULE_COLUMNS))):
        assert "identity_rules" not in sql

    db = FakeDB()
    resolver = PostgresKBResolver(db)
    resolver.resolve_rules("CHANGE_CLASSIFICATION")
    resolver.resolve_rules("CHANGE_CLASSIFICATION", "1.0.1")
    try:
        PostgresKBResolver(FakeDB(rule_rows=[])).resolve_rules("IDENTITY_ASSESSMENT")
    except NoExecutableRuleSet:
        pass
    assert db.queries, "expected the resolver to have issued statements"
    for sql, _params in db.queries:
        assert "identity_rules" not in sql, f"resolver queried identity_rules: {sql}"


def test_empty_rule_set_is_a_system_status_not_cannot_decide():
    resolver = PostgresKBResolver(FakeDB(rule_rows=[]))
    with pytest.raises(NoExecutableRuleSet) as excinfo:
        resolver.resolve_rules("IDENTITY_ASSESSMENT")
    message = str(excinfo.value)
    assert "CANNOT_DECIDE" not in message
    assert "identity_rules are NOT promoted" in message


def test_non_active_status_rules_are_excluded_not_executed():
    resolver = PostgresKBResolver(
        FakeDB(rule_rows=[rule_row("R1"), rule_row("R2", status="proposed")])
    )
    resolved = resolver.resolve_rules("CHANGE_CLASSIFICATION")
    assert [r.rule_id for r in resolved.rules] == ["R1"]
    assert resolved.excluded_rules == (("R2", "status=proposed"),)


def test_all_rules_proposed_yields_no_executable_rule_set():
    resolver = PostgresKBResolver(
        FakeDB(rule_rows=[rule_row("R1", status="proposed")])
    )
    with pytest.raises(NoExecutableRuleSet, match="excluded by status"):
        resolver.resolve_rules("IDENTITY_ASSESSMENT")


# ======================================================================
# version distinctness
# ======================================================================

def test_kb_policy_ontology_versions_stay_distinct():
    resolved = PostgresKBResolver(
        FakeDB(rule_rows=[rule_row(kb_version="1.0.1",
                                   ontology_version="O-7",
                                   policy_version="P-3")])
    ).resolve_rules("CHANGE_CLASSIFICATION")
    assert resolved.kb_version == "1.0.1"
    assert resolved.ontology_version == "O-7"
    assert resolved.policy_version == "P-3"
    assert len({resolved.kb_version, resolved.ontology_version, resolved.policy_version}) == 3


def test_conflicting_versions_are_reported_not_invented():
    resolver = PostgresKBResolver(
        FakeDB(rule_rows=[rule_row("R1", policy_version="P-1"),
                          rule_row("R2", policy_version="P-2")])
    )
    with pytest.raises(GovernanceVersionAmbiguity, match="will not choose"):
        resolver.resolve_rules("CHANGE_CLASSIFICATION")


def test_resolved_rules_are_sorted_by_rule_id():
    resolver = PostgresKBResolver(
        FakeDB(rule_rows=[rule_row("ccc"), rule_row("aaa"), rule_row("bbb")])
    )
    resolved = resolver.resolve_rules("CHANGE_CLASSIFICATION")
    assert [r.rule_id for r in resolved.rules] == ["aaa", "bbb", "ccc"]
