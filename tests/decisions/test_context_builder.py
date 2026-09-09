"""D.4D unit tests: context assembly and the read-only connection gate.

NO PostgreSQL. NO AWS. NO network.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from d4c_support import HORIZON
from d4d_support import executable_source

from decisions import (
    DecisionContext,
    DecisionRequest,
    DomainFacts,
    FoldProperty,
    FoldSnapshotView,
    FoldState,
    GovernedDecisionExecutor,
    Known,
    PredicateRegistry,
    RuleClass,
    MATCHED,
)
from decisions.adapters import connection as connection_module
from decisions.adapters.errors import ReadOnlyViolation, UnboundGovernedRule
from decisions.context_builder import ContextBuilder, governance_from_rule_set
from decisions.ports import (
    FoldLoadResult,
    FoldLoadStatus,
    GovernedRuleMetadata,
    ResolvedRuleSet,
    RuleClassBinding,
)

SUBJECT_TYPE = "configuration_request"
SUBJECT_ID = "CONFIG-REQ-2026-006"


def snapshot(properties=None):
    return FoldSnapshotView(
        fold_state_id="fs-1",
        subject_type=SUBJECT_TYPE,
        subject_id=SUBJECT_ID,
        decision_horizon=HORIZON,
        fold_status=FoldState.ESTABLISHED,
        kb_version="1.0.1",
        policy_version="P-1",
        properties=properties
        or {
            "alpha": FoldProperty("alpha", "A", "string", FoldState.ESTABLISHED,
                                  basis_assertion_ids=("a-1",)),
            "beta": FoldProperty("beta", None, None, FoldState.UNREPORTED),
        },
    )


def rule_set(rule_ids=("R1",)):
    rules = tuple(
        GovernedRuleMetadata(
            decision_type="TEST_ADAPTER",
            rule_id=rid,
            kb_version="1.0.1",
            ontology_version="O-1",
            policy_version="P-1",
            precedence=10,
            outcome_code="TEST_OUTCOME",
            condition_text="prose that must never be executed",
        )
        for rid in rule_ids
    )
    return ResolvedRuleSet(
        decision_type="TEST_ADAPTER",
        kb_version="1.0.1",
        ontology_version="O-1",
        policy_version="P-1",
        rules=rules,
        rule_set_digest="v1:sha256:deadbeef",
    )


class FakeLoader:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def load(self, subject_type, subject_id, decision_horizon):
        self.calls.append((subject_type, subject_id, decision_horizon))
        return self.result


class FakeResolver:
    def __init__(self, resolved=None):
        self.resolved = resolved or rule_set()
        self.calls = []

    def active_kb(self):
        from decisions.ports import ActiveKB

        return ActiveKB(kb_version="1.0.1")

    def resolve_rules(self, decision_type, kb_version=None):
        self.calls.append((decision_type, kb_version))
        return self.resolved


def request(**overrides):
    kwargs = dict(
        decision_type="TEST_ADAPTER",
        subject_type=SUBJECT_TYPE,
        subject_id=SUBJECT_ID,
        decision_horizon=HORIZON,
    )
    kwargs.update(overrides)
    return DecisionRequest(**kwargs)


BINDINGS = {"R1": RuleClassBinding("R1", RuleClass.MATCH, "ref::R1")}


# ======================================================================
# assembly
# ======================================================================

def test_builds_a_valid_decision_context():
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot())), FakeResolver()
    )
    result = builder.build(request(), BINDINGS, required_properties=("alpha", "beta"))
    assert result.assembled
    assert isinstance(result.context, DecisionContext)
    assert result.context.fold.subject_id == SUBJECT_ID
    assert result.context.governance.kb_version == "1.0.1"
    assert result.context.governance.required_properties == ("alpha", "beta")


def test_lineage_survives_assembly():
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot())), FakeResolver()
    )
    ctx = builder.build(request(), BINDINGS).context
    assert ctx.property_named("alpha").basis_assertion_ids == ("a-1",)
    assert ctx.state_of("beta") is FoldState.UNREPORTED
    assert ctx.fold.fold_state_id == "fs-1"


def test_not_found_returns_status_without_a_context():
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.NOT_FOUND, detail="nothing at horizon")),
        FakeResolver(),
    )
    result = builder.build(request(), BINDINGS)
    assert not result.assembled
    assert result.context is None
    assert result.fold_status is FoldLoadStatus.NOT_FOUND
    assert "nothing at horizon" in result.detail


def test_not_found_does_not_become_a_business_outcome():
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.NOT_FOUND)), FakeResolver()
    )
    result = builder.build(request(), BINDINGS)
    assert not hasattr(result, "outcome_code")
    assert "CANNOT_DECIDE" not in str(result.detail)


def test_requested_kb_version_is_passed_through_for_replay():
    resolver = FakeResolver()
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot())), resolver
    )
    builder.build(request(requested_kb_version="1.0.0"), BINDINGS)
    assert resolver.calls == [("TEST_ADAPTER", "1.0.0")]


def test_horizon_is_forwarded_verbatim_to_the_loader():
    loader = FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot()))
    ContextBuilder(loader, FakeResolver()).build(request(), BINDINGS)
    assert loader.calls == [(SUBJECT_TYPE, SUBJECT_ID, HORIZON)]


def test_domain_facts_default_to_empty():
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot())), FakeResolver()
    )
    ctx = builder.build(request(), BINDINGS).context
    assert ctx.facts.facts == {}


def test_optional_fact_provider_is_used_when_supplied():
    class Provider:
        def facts_for(self, req, fold):
            return DomainFacts({"synthetic_flag": Known(True)})

    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot())),
        FakeResolver(),
        Provider(),
    )
    ctx = builder.build(request(), BINDINGS).context
    assert ctx.facts.value_of("synthetic_flag") is True


def test_unbound_rule_stops_assembly():
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot())),
        FakeResolver(rule_set(("R1", "R_UNBOUND"))),
    )
    with pytest.raises(UnboundGovernedRule, match="R_UNBOUND"):
        builder.build(request(), BINDINGS)


def test_governance_binding_carries_excluded_rules():
    resolved = ResolvedRuleSet(
        decision_type="TEST_ADAPTER",
        kb_version="1.0.1",
        ontology_version="O-1",
        policy_version="P-1",
        rules=rule_set().rules,
        excluded_rules=(("R9", "status=proposed"),),
        rule_set_digest="v1:sha256:beef",
    )
    binding = governance_from_rule_set(resolved, BINDINGS)
    assert binding.excluded_rules == (("R9", "status=proposed"),)


def test_context_builder_performs_no_canonical_lookup():
    """claris.product / claris.configuration belong to D.4E."""
    import decisions.context_builder as module

    code = executable_source(module)
    for token in ("claris.product", "claris.configuration", "select"):
        assert token not in code


# ======================================================================
# read-only connection gate
# ======================================================================

class RecordingCursor:
    def __init__(self, store):
        self.store = store
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.store.append(sql)

    def fetchall(self):
        return []


class RecordingConnection:
    def __init__(self):
        self.statements = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return RecordingCursor(self.statements)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO claris.decision VALUES (1)",
        "UPDATE claris_kb.decision_rules SET status='ACTIVE'",
        "DELETE FROM state.fold_state_snapshot",
        "ALTER TABLE claris.decision ADD COLUMN x int",
        "CREATE TABLE t (id int)",
        "  insert into x values (1)",
    ],
)
def test_write_statements_are_refused_before_reaching_the_database(sql):
    conn = RecordingConnection()
    with connection_module.read_only_connection(conn) as db:
        with pytest.raises(ReadOnlyViolation):
            db.query(sql)
    assert not any(
        s.strip().lower().startswith(("insert", "update", "delete", "alter", "create"))
        for s in conn.statements
    )


def test_select_and_with_are_permitted():
    conn = RecordingConnection()
    with connection_module.read_only_connection(conn) as db:
        db.query("SELECT 1")
        db.query("WITH x AS (SELECT 1) SELECT * FROM x")
    assert any(s.startswith("SELECT 1") for s in conn.statements)


class SetSessionConnection(RecordingConnection):
    """A driver that exposes psycopg2's set_session(), like the real one."""

    def __init__(self):
        super().__init__()
        self.session_kwargs = None

    def set_session(self, **kwargs):
        self.session_kwargs = kwargs


def test_set_session_is_preferred_when_the_driver_offers_it():
    """SET SESSION CHARACTERISTICS inside an already-open transaction affects
    only SUBSEQUENT transactions, so the session stayed read-write. The live
    D.4D run caught exactly that. set_session() pins it before any transaction
    starts, and autocommit stops one failed statement aborting all later reads."""
    conn = SetSessionConnection()
    with connection_module.read_only_connection(conn):
        pass
    assert conn.session_kwargs == {"readonly": True, "autocommit": True}
    assert "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY" not in conn.statements


def test_session_is_pinned_read_only_and_timeout_set():
    conn = RecordingConnection()
    with connection_module.read_only_connection(conn):
        pass
    assert "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY" in conn.statements
    assert any(s.startswith("SET statement_timeout") for s in conn.statements)


def test_connection_is_rolled_back_deterministically():
    conn = RecordingConnection()
    with connection_module.read_only_connection(conn):
        pass
    assert conn.rolled_back
    assert not conn.closed, "a borrowed connection must not be closed by the adapter"


def test_rollback_happens_even_on_error():
    conn = RecordingConnection()
    with pytest.raises(RuntimeError):
        with connection_module.read_only_connection(conn):
            raise RuntimeError("boom")
    assert conn.rolled_back


def test_no_credential_is_logged_or_returned():
    code = executable_source(connection_module)
    assert "print(" not in code
    assert "logging" not in code
    for leak in ("password'", 'password"'):
        assert f"print({leak}" not in code


# ======================================================================
# synthetic end-to-end adapter compatibility  (section 19)
# ======================================================================

def test_assembled_context_is_accepted_by_the_d4c_executor():
    """Adapter compatibility only. TEST rule ids, synthetic predicate,
    no Claris business meaning, nothing persisted."""
    builder = ContextBuilder(
        FakeLoader(FoldLoadResult(FoldLoadStatus.FOUND, snapshot())), FakeResolver()
    )
    ctx = builder.build(request(), BINDINGS, required_properties=("alpha", "beta")).context

    registry = PredicateRegistry()
    registry.register("TEST_ADAPTER", "R1", "1.0.1", lambda c: MATCHED)
    result = GovernedDecisionExecutor(registry).execute(ctx)

    assert result.outcome_code == "TEST_OUTCOME"
    assert result.matched_rule_id == "R1"
    assert result.input_digest.startswith("v1:sha256:")
    assert result.missing_evidence == ("beta",)  # UNREPORTED survived the whole path
    assert result.fold_state_id == "fs-1"
    assert not result.matched_rule_id.startswith("IR-")
