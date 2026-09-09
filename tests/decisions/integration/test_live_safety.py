"""Live safety verification and synthetic end-to-end compatibility.

Section 19  -- real Fold -> DecisionContext -> D.4C executor, SYNTHETIC rules
Section 23 K/L/M -- no decision, action or canonical row is created
Section 28  -- before/after counts prove zero writes
"""

from __future__ import annotations

from datetime import timezone

import pytest
from live_support import (
    MUTATION_WITNESS_TABLES,
    SUBJECT_TYPE,
    kb_status_fingerprint,
    row_counts,
)

from decisions import (
    MATCHED,
    NOT_MATCHED,
    DecisionRequest,
    FoldState,
    GovernedDecisionExecutor,
    PredicateRegistry,
    RuleClass,
)
from decisions.context_builder import ContextBuilder
from decisions.ports import (
    GovernedRuleMetadata,
    ResolvedRuleSet,
    RuleClassBinding,
)

# Deliberately synthetic. Not a Claris decision type, not IR-*.
TEST_DECISION_TYPE = "TEST_ADAPTER_COMPATIBILITY"
TEST_KB_VERSION = "TEST-KB"


class SyntheticResolver:
    """Stands in for the KB so no live governed rule is bound to a fake predicate."""

    def active_kb(self):
        from decisions.ports import ActiveKB

        return ActiveKB(kb_version=TEST_KB_VERSION)

    def resolve_rules(self, decision_type, kb_version=None):
        rules = (
            GovernedRuleMetadata(
                decision_type=TEST_DECISION_TYPE,
                rule_id="TEST-GUARD-001",
                kb_version=TEST_KB_VERSION,
                ontology_version="TEST-ONT",
                policy_version="TEST-POL",
                precedence=10,
                outcome_code="TEST_BLOCKED",
                reason_code="TEST_GUARD_FIRED",
            ),
            GovernedRuleMetadata(
                decision_type=TEST_DECISION_TYPE,
                rule_id="TEST-MATCH-001",
                kb_version=TEST_KB_VERSION,
                ontology_version="TEST-ONT",
                policy_version="TEST-POL",
                precedence=10,
                outcome_code="TEST_MATCHED",
                reason_code="TEST_MATCH_FIRED",
            ),
        )
        return ResolvedRuleSet(
            decision_type=TEST_DECISION_TYPE,
            kb_version=TEST_KB_VERSION,
            ontology_version="TEST-ONT",
            policy_version="TEST-POL",
            rules=rules,
            rule_set_digest="v1:sha256:synthetic",
        )


TEST_BINDINGS = {
    "TEST-GUARD-001": RuleClassBinding("TEST-GUARD-001", RuleClass.GUARD, "ref::guard"),
    "TEST-MATCH-001": RuleClassBinding("TEST-MATCH-001", RuleClass.MATCH, "ref::match"),
}


# ======================================================================
# section 28 -- before/after mutation witness
# ======================================================================

@pytest.fixture(scope="module")
def before_counts(db):
    counts = row_counts(db)
    print("\n  BEFORE row counts:")
    for table, n in counts.items():
        print(f"    {table}: {n}")
    return counts


@pytest.fixture(scope="module")
def before_kb_status(db):
    return kb_status_fingerprint(db)


# ======================================================================
# section 19 -- real Fold, synthetic rules, generic executor
# ======================================================================

def test_real_fold_context_runs_through_the_generic_executor(
    db, fold_loader, identity_subjects, before_counts
):
    """Adapter compatibility ONLY.

    This is NOT a Claris governed business decision. The rule ids are TEST-*,
    the decision type is synthetic, the predicates are synthetic, and nothing
    is persisted. It proves one thing: a DecisionContext assembled from real
    governed Fold state is accepted by the D.4C executor.
    """
    target = identity_subjects["complete"][0]
    builder = ContextBuilder(fold_loader, SyntheticResolver())

    request = DecisionRequest(
        decision_type=TEST_DECISION_TYPE,
        subject_type=SUBJECT_TYPE,
        subject_id=target["subject_id"],
        decision_horizon=target["decision_horizon"],
        requested_by="d4d-integration",
    )
    assembly = builder.build(
        request,
        TEST_BINDINGS,
        required_properties=("product_reference", "geography",
                             "term_months", "customer_segment"),
    )
    assert assembly.assembled

    registry = PredicateRegistry()
    registry.register(TEST_DECISION_TYPE, "TEST-GUARD-001", TEST_KB_VERSION,
                      lambda ctx: NOT_MATCHED)
    registry.register(TEST_DECISION_TYPE, "TEST-MATCH-001", TEST_KB_VERSION,
                      lambda ctx: MATCHED)

    result = GovernedDecisionExecutor(registry).execute(assembly.context)

    print(
        f"\n  SYNTHETIC result for {target['subject_id']}: "
        f"outcome={result.outcome_code} rule={result.matched_rule_id} "
        f"digest={result.input_digest[:26]}..."
    )
    print(f"    fold_state_id: {result.fold_state_id}")
    print(f"    missing_evidence: {result.missing_evidence}")
    print(f"    lineage entries: {len(result.fold_lineage)}")

    assert result.outcome_code == "TEST_MATCHED"
    assert result.matched_rule_id == "TEST-MATCH-001"
    assert result.matched_rule_id.startswith("TEST-")
    assert not result.matched_rule_id.startswith("IR-")
    assert result.decision_type == TEST_DECISION_TYPE
    assert result.fold_state_id
    assert result.fold_lineage, "real Fold lineage must reach the result"


def test_real_unreported_subject_reaches_the_executor_as_missing_evidence(
    fold_loader, identity_subjects
):
    """The live UNREPORTED property survives the entire adapter path.

    Still synthetic rules -- this asserts data fidelity, not a business outcome.
    """
    target = identity_subjects["with_unreported"][0]
    builder = ContextBuilder(fold_loader, SyntheticResolver())
    request = DecisionRequest(
        decision_type=TEST_DECISION_TYPE,
        subject_type=SUBJECT_TYPE,
        subject_id=target["subject_id"],
        decision_horizon=target["decision_horizon"],
    )
    assembly = builder.build(
        request,
        TEST_BINDINGS,
        required_properties=("product_reference", "geography",
                             "term_months", "customer_segment"),
    )
    registry = PredicateRegistry()
    registry.register(TEST_DECISION_TYPE, "TEST-GUARD-001", TEST_KB_VERSION,
                      lambda ctx: NOT_MATCHED)
    registry.register(TEST_DECISION_TYPE, "TEST-MATCH-001", TEST_KB_VERSION,
                      lambda ctx: MATCHED)
    result = GovernedDecisionExecutor(registry).execute(assembly.context)

    print(f"\n  {target['subject_id']} missing_evidence={result.missing_evidence}")
    assert result.missing_evidence, (
        "the live UNREPORTED property should appear as missing evidence"
    )
    unreported = [
        name for name, prop in assembly.context.fold.properties.items()
        if prop.fold_state is FoldState.UNREPORTED
    ]
    assert set(result.missing_evidence) <= set(unreported) | set(
        assembly.context.governance.required_properties
    )


# ======================================================================
# section 23 K/L/M + 28 -- nothing was written
# ======================================================================

def test_no_rows_created_anywhere(db, before_counts):
    after = row_counts(db)
    print("\n  AFTER row counts:")
    for table, n in after.items():
        print(f"    {table}: {n}  (before {before_counts[table]})")
    assert after == before_counts, "D.4D must not create, update or delete any row"


def test_no_decision_was_written_against_production_governance(db):
    """Was: claris.decision must be empty. D.4D wrote no decisions, so counting
    rows was a sound proxy for "this phase wrote nothing".

    The vertical slice writes decisions, so the proxy is gone but the safety
    property is not: production governance must never be the basis of a written
    decision. That is what this now asserts, and it is the assertion that would
    actually catch a prototype run leaking into production.
    """
    assert db.scalar("""
        SELECT count(*) FROM claris.decision
        WHERE governance_basis = 'AUTHORITATIVE'
           OR execution_mode = 'PRODUCTION'""") == 0


def test_claris_action_record_still_empty(db):
    assert db.scalar("SELECT count(*) FROM claris.action_record") == 0


def test_no_kb_status_or_activation_change(db, before_kb_status):
    after = kb_status_fingerprint(db)
    print("\n  KB status fingerprint unchanged:")
    for row in after:
        print(f"    {row['source']} {row['scope']} {row['status']}: {row['n']}")
    assert after == before_kb_status, "no KB status or rule activation may change"


def test_session_remained_read_only_throughout(db):
    assert db.session_is_read_only()


def test_write_attempt_is_refused_by_the_adapter(db):
    """Belt and braces: the gate refuses before the server would."""
    from decisions.adapters.errors import ReadOnlyViolation

    with pytest.raises(ReadOnlyViolation):
        db.query("INSERT INTO claris.decision (decision_id) VALUES (gen_random_uuid())")
