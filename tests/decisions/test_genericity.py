"""Section 20: genericity proof.

Two unrelated synthetic decision types run on the SAME executor instance with
different rules and different predicates, and produce different governed
outcomes. Neither uses Claris business logic.

This is the test that fails loudly if anyone ever writes

    if decision_type == "IDENTITY_ASSESSMENT": ...

into the executor.
"""

from __future__ import annotations

import inspect

from d4c_support import (
    KB,
    TYPE_A,
    TYPE_B,
    always_match,
    make_context,
    make_executor,
    make_property,
    make_rule,
    match_when_flag,
    match_when_state,
    never_match,
)

from decisions import FoldState, RuleClass
import decisions.contracts as contracts_module
import decisions.digest as digest_module
import decisions.executor as executor_module
import decisions.registry as registry_module
import decisions.rules as rules_module


# ======================================================================
# two decision types, one executor
# ======================================================================

def _two_type_executor():
    return make_executor(
        # TEST_IDENTITY
        (TYPE_A, "TEST-GUARD-001", KB, match_when_state("prop_x", FoldState.UNREPORTED)),
        (TYPE_A, "TEST-MATCH-001", KB, match_when_flag("flag_alpha")),
        (TYPE_A, "TEST-FALLBACK-001", KB, always_match),
        # TEST_READINESS -- deliberately reuses rule ids, different logic
        (TYPE_B, "TEST-GUARD-001", KB, never_match),
        (TYPE_B, "TEST-MATCH-001", KB, match_when_flag("flag_beta")),
        (TYPE_B, "TEST-FALLBACK-001", KB, always_match),
    )


def _rules(decision_type):
    return (
        make_rule("TEST-GUARD-001", RuleClass.GUARD, 10, "BLOCKED_OUTCOME",
                  "GUARD_REASON", decision_type=decision_type),
        make_rule("TEST-MATCH-001", RuleClass.MATCH, 10, f"{decision_type}_MATCHED",
                  "MATCH_REASON", decision_type=decision_type),
        make_rule("TEST-FALLBACK-001", RuleClass.FALLBACK, 99, "FELL_THROUGH",
                  "FALLBACK_REASON", decision_type=decision_type),
    )


def test_same_executor_serves_two_decision_types():
    ex = _two_type_executor()

    a = ex.execute(
        make_context(
            decision_type=TYPE_A,
            rule_set=_rules(TYPE_A),
            properties={"prop_x": make_property("prop_x", "present")},
            facts={"flag_alpha": True, "flag_beta": False},
        )
    )
    b = ex.execute(
        make_context(
            decision_type=TYPE_B,
            rule_set=_rules(TYPE_B),
            properties={"prop_x": make_property("prop_x", "present")},
            facts={"flag_alpha": False, "flag_beta": True},
        )
    )

    assert a.outcome_code == "TEST_IDENTITY_MATCHED"
    assert b.outcome_code == "TEST_READINESS_MATCHED"
    assert a.decision_type != b.decision_type
    assert a.matched_rule_id == b.matched_rule_id == "TEST-MATCH-001"


def test_identical_rule_ids_across_types_do_not_collide():
    ex = _two_type_executor()
    a = ex.execute(
        make_context(
            decision_type=TYPE_A,
            rule_set=_rules(TYPE_A),
            properties={"prop_x": make_property("prop_x", state=FoldState.UNREPORTED)},
            facts={"flag_alpha": True},
        )
    )
    b = ex.execute(
        make_context(
            decision_type=TYPE_B,
            rule_set=_rules(TYPE_B),
            properties={"prop_x": make_property("prop_x", state=FoldState.UNREPORTED)},
            facts={"flag_beta": True},
        )
    )
    # TYPE_A's guard fires on UNREPORTED; TYPE_B's guard never fires
    assert a.outcome_code == "BLOCKED_OUTCOME"
    assert a.matched_rule_class == "GUARD"
    assert b.outcome_code == "TEST_READINESS_MATCHED"
    assert b.matched_rule_class == "MATCH"


def test_each_type_falls_through_independently():
    ex = _two_type_executor()
    a = ex.execute(
        make_context(
            decision_type=TYPE_A,
            rule_set=_rules(TYPE_A),
            properties={"prop_x": make_property("prop_x", "present")},
            facts={"flag_alpha": False},
        )
    )
    assert a.outcome_code == "FELL_THROUGH"
    assert a.matched_rule_id == "TEST-FALLBACK-001"


# ======================================================================
# static proof: no domain vocabulary inside the platform
# ======================================================================

FORBIDDEN_TOKENS = (
    "claris",
    "sap",
    "filemaker",
    "sku",
    "product_reference",
    "geography",
    "term_months",
    "customer_segment",
    "canonical_identity",
    "identity_assessment",
    "change_classification",
    "launch_readiness",
    "ir-010",
    "ir-011",
    "ir-012",
    "ir-013",
)

PLATFORM_MODULES = (
    contracts_module,
    digest_module,
    executor_module,
    registry_module,
    rules_module,
)


def _executable_source(module):
    """Module source with comments and docstrings removed.

    Documentation may legitimately cite D.4A findings -- why kb_version is part
    of the rule key, which enum the state vocabulary mirrors. Executable code
    may not. `ast` drops comments for free; docstring nodes are stripped
    explicitly.
    """
    import ast

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body.pop(0)
                if not body:
                    body.append(ast.Pass())
    return ast.unparse(tree).lower()


def test_platform_modules_contain_no_domain_vocabulary_in_code():
    offenders = {}
    for module in PLATFORM_MODULES:
        code = _executable_source(module)
        hits = [token for token in FORBIDDEN_TOKENS if token in code]
        if hits:
            offenders[module.__name__] = hits
    assert not offenders, f"domain vocabulary leaked into platform code: {offenders}"


def test_no_platform_module_compares_decision_type_to_a_literal():
    """`b.decision_type == request.decision_type` is generic filtering and fine.

    `decision_type == "IDENTITY_ASSESSMENT"` is not. Only comparisons against a
    string literal are branching on a domain value.
    """
    import re

    pattern = re.compile(
        r"""decision_type\s*(?:==|!=|\sin\s)\s*[\[(]?\s*["']""", re.IGNORECASE
    )
    offenders = {}
    for module in PLATFORM_MODULES:
        code = _executable_source(module)
        matches = pattern.findall(code)
        if matches:
            offenders[module.__name__] = matches
    assert not offenders, f"platform branches on a decision_type literal: {offenders}"


def test_executor_compares_decision_type_only_against_the_request():
    """The single decision_type comparison filters the rule set. Nothing else."""
    code = _executable_source(executor_module)
    comparisons = [
        line.strip() for line in code.splitlines() if "decision_type ==" in line
    ]
    assert len(comparisons) == 1, comparisons
    assert "b.decision_type == decision_type" in comparisons[0]


def test_platform_does_not_import_domain_packs():
    for module in PLATFORM_MODULES:
        source = inspect.getsource(module)
        assert "decisions.domains" not in source
        assert "from .domains" not in source


def test_domain_pack_holds_exactly_the_identity_assessment_predicates():
    """SUPERSEDES the D.4C assertion that this subtree is empty.

    D.4C section 18 required no Claris business predicates at all, and asserted
    `dir(pkg) == []`. D.4E section 1 implements the first real domain pack, so
    that assertion is now wrong by design and is replaced rather than deleted:
    the subtree must hold the four IDENTITY_ASSESSMENT predicates and nothing
    beyond them, so an unrelated predicate appearing here still fails loudly.
    """
    import decisions.domains.claris.predicates as pkg

    exported = {name for name in pkg.__all__}
    assert exported == {
        "IR_010",
        "IR_011",
        "IR_012",
        "IR_013",
        "ir_010_exact_identity_match",
        "ir_011_missing_required_input",
        "ir_012_contradicted_required_input",
        "ir_013_initial_configuration",
        "IDENTITY_PREDICATES",
    }
    assert set(pkg.IDENTITY_PREDICATES) == {"IR-010", "IR-011", "IR-012", "IR-013"}


def test_the_platform_still_does_not_import_the_domain_pack():
    """The one-way dependency must survive the arrival of a real domain pack."""
    for module in PLATFORM_MODULES:
        source = inspect.getsource(module)
        assert "decisions.domains" not in source
        assert "from .domains" not in source
        assert "identity_assessment" not in _executable_source(module)


def test_the_domain_pack_imports_the_platform_and_not_the_reverse():
    import decisions.domains.claris.predicates.identity_assessment as predicates

    source = inspect.getsource(predicates)
    assert "from ....contracts import" in source
