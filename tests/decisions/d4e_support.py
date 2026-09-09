"""Shared builders for the D.4E Claris IDENTITY_ASSESSMENT domain-pack tests.

Uniquely named for the same reason as d4c_support.py and d4d_support.py: this
repository has several conftest.py files and no packages, so `import conftest`
is unreliable.

NO PostgreSQL. NO AWS. NO network. Every context here is built in memory, and
the fake database is a dictionary.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _path in (_REPO_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from decisions import (  # noqa: E402
    DecisionContext,
    DecisionRequest,
    DomainFacts,
    FoldProperty,
    FoldSnapshotView,
    FoldState,
    GovernedDecisionExecutor,
    Known,
    Unavailable,
)
from decisions.domains.claris import (  # noqa: E402
    DECISION_TYPE,
    EXACT_IDENTITY_MATCH_EXISTS,
    EXISTING_CONFIGURATION_COUNT,
    IDENTITY_PROPERTIES,
    PRODUCT_EXISTS,
    SEMANTIC_KB_VERSION,
    SUBJECT_TYPE,
    build_prototype_registry,
    prototype_governance_binding,
)

HORIZON = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
EFFECTIVE = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
ARRIVED = datetime(2026, 1, 16, 10, 0, 0, tzinfo=timezone.utc)

SUBJECT_ID = "CONFIG-REQ-2026-007"

#: The live-shaped fully ESTABLISHED identity tuple.
ESTABLISHED_VALUES = {
    "product_reference": "PROD-001",
    "geography": "NAMER",
    "term_months": "36",
    "customer_segment": "enterprise",
}

EXPECTED_CANONICAL_IDENTITY = "v2|8:PROD-001|5:NAMER|2:36|10:enterprise"


# ----------------------------------------------------------------------
# Fold builders
# ----------------------------------------------------------------------

def identity_property(
    name: str,
    value=None,
    state: FoldState = FoldState.ESTABLISHED,
    value_type: str | None = None,
    assertions: tuple[str, ...] = ("assn-1",),
) -> FoldProperty:
    """One folded identity property.

    A non-ESTABLISHED property is built exactly as the live Fold delivers one:
    resolved_value None, no value type, no lineage.
    """
    if state is not FoldState.ESTABLISHED:
        value, value_type, assertions = None, None, ()
    else:
        if value is None:
            value = ESTABLISHED_VALUES.get(name, "x")
        if value_type is None:
            value_type = "integer" if name == "term_months" else "string"
    return FoldProperty(
        property_name=name,
        resolved_value=value,
        property_value_type=value_type,
        fold_state=state,
        effective_at=EFFECTIVE if state is FoldState.ESTABLISHED else None,
        latest_known_arrival_at=ARRIVED if state is FoldState.ESTABLISHED else None,
        basis_assertion_ids=assertions,
    )


def make_fold(
    states: dict | None = None,
    values: dict | None = None,
    omit: tuple[str, ...] = (),
    subject_id: str = SUBJECT_ID,
    horizon: datetime = HORIZON,
    fold_status: FoldState = FoldState.ESTABLISHED,
) -> FoldSnapshotView:
    """A Fold snapshot over the four identity properties.

    states  per-property FoldState overrides; default ESTABLISHED
    values  per-property resolved_value overrides
    omit    property names left OUT of the snapshot entirely (absent != UNREPORTED)
    """
    states = states or {}
    values = values or {}
    properties = {}
    for name in IDENTITY_PROPERTIES:
        if name in omit:
            continue
        properties[name] = identity_property(
            name,
            value=values.get(name),
            state=states.get(name, FoldState.ESTABLISHED),
        )
    return FoldSnapshotView(
        fold_state_id="fs-d4e-0001",
        subject_type=SUBJECT_TYPE,
        subject_id=subject_id,
        decision_horizon=horizon,
        fold_status=fold_status,
        kb_version=SEMANTIC_KB_VERSION,
        policy_version="",
        properties=properties,
    )


def make_facts(
    product_exists=None,
    existing_configuration_count=None,
    exact_identity_match_exists=None,
) -> DomainFacts:
    """Synthetic domain facts. Pass a string to build an Unavailable fact."""
    facts = {}
    for name, value in (
        (PRODUCT_EXISTS, product_exists),
        (EXISTING_CONFIGURATION_COUNT, existing_configuration_count),
        (EXACT_IDENTITY_MATCH_EXISTS, exact_identity_match_exists),
    ):
        if value is None:
            continue
        facts[name] = Unavailable(value) if isinstance(value, str) else Known(value)
    return DomainFacts(facts)


def make_context(
    fold: FoldSnapshotView | None = None,
    facts: DomainFacts | None = None,
    governance=None,
    subject_id: str = SUBJECT_ID,
) -> DecisionContext:
    fold = fold if fold is not None else make_fold(subject_id=subject_id)
    return DecisionContext(
        request=DecisionRequest(
            decision_type=DECISION_TYPE,
            subject_type=SUBJECT_TYPE,
            subject_id=fold.subject_id,
            decision_horizon=fold.decision_horizon,
        ),
        fold=fold,
        governance=governance if governance is not None else prototype_governance_binding(),
        facts=facts if facts is not None else DomainFacts(),
    )


def prototype_executor() -> GovernedDecisionExecutor:
    """The real generic executor carrying only the four identity predicates."""
    return GovernedDecisionExecutor(build_prototype_registry())


# ----------------------------------------------------------------------
# fake read-only database
# ----------------------------------------------------------------------

def _configuration_row(entry) -> tuple:
    """Normalize a test configuration entry to (product, identity, status, archived_at)."""
    if len(entry) == 2:
        return (entry[0], entry[1], "active", None)
    if len(entry) == 3:
        return (entry[0], entry[1], entry[2], None)
    return tuple(entry)


class FakeCanonicalDB:
    """In-memory stand-in for ReadOnlyDatabase over the canonical tables.

    Answers the three canonical questions from dictionaries. Records every
    (sql, params) pair so tests can assert the SQL was parameterized and that
    no statement other than a SELECT was ever submitted.
    """

    def __init__(
        self,
        products: tuple[str, ...] = (),
        configurations: tuple = (),
        columns: tuple[tuple[str, str], ...] = (),
        fail_with: Exception | None = None,
    ) -> None:
        """configurations entries are (product_id, canonical_identity) or
        (product_id, canonical_identity, status, archived_at).

        A two-element entry defaults to the live-schema default: status
        'active', archived_at None.
        """
        self.products = set(products)
        self.configurations = tuple(
            _configuration_row(entry) for entry in configurations
        )
        self.columns = columns or (
            ("product", "product_id"),
            ("product", "product_name"),
            ("product", "created_at"),
            ("configuration", "configuration_id"),
            ("configuration", "product_id"),
            ("configuration", "canonical_identity"),
            ("configuration", "identity_digest"),
            ("configuration", "status"),
            ("configuration", "governed_identity"),
            ("configuration", "created_at"),
            ("configuration", "created_by"),
            ("configuration", "archived_at"),
        )
        self.check_constraints = [
            {
                "conname": "check_configuration_status",
                "definition": "CHECK (((status)::text = ANY "
                              "((ARRAY['active'::character varying, "
                              "'archived'::character varying])::text[])))",
            }
        ]
        self.fail_with = fail_with
        self.calls: list = []

    def query(self, sql: str, params=None):
        self.calls.append((sql, params))
        if self.fail_with is not None:
            raise self.fail_with
        normalized = " ".join(sql.split()).lower()
        if not normalized.startswith(("select", "with")):
            raise AssertionError(f"non-read statement submitted: {sql!r}")
        if "information_schema.columns" in normalized:
            if "is_nullable" in normalized:
                wanted = params[2] if params and len(params) > 2 else ()
                return [
                    {"column_name": c, "is_nullable": "YES"}
                    for t, c in self.columns
                    if t == params[1] and c in wanted
                ]
            return [
                {"table_name": t, "column_name": c}
                for t, c in self.columns
                if t in (params[1] if params else ())
            ]
        if "from claris.product" in normalized:
            return [{"product_exists": params[0] in self.products}]
        if "count(*) as n" in normalized and "from claris.configuration" in normalized:
            # existing_configuration_count -- archived rows included, by design
            return [{"n": sum(1 for r in self.configurations if r[0] == params[0])}]
        if "canonical_identity = %s" in normalized:
            active, archived = params[0], params[1]
            identity = params[-1]
            rows = [r for r in self.configurations if r[1] == identity]
            eligible = [r for r in rows if r[2] == active and r[3] is None]
            ineligible = [r for r in rows if r[2] == archived or r[3] is not None]
            unclassifiable = [
                r for r in rows
                if r[2] not in (active, archived) and r[3] is None
            ]
            return [
                {
                    "eligible_matches": len(eligible),
                    "ineligible_matches": len(ineligible),
                    "unclassifiable_matches": len(unclassifiable),
                    "total_matches": len(rows),
                }
            ]
        if "pg_constraint" in normalized:
            return list(self.check_constraints)
        raise AssertionError(f"unexpected query: {sql!r}")

    def scalar(self, sql: str, params=None):
        rows = self.query(sql, params)
        return next(iter(rows[0].values())) if rows else None
