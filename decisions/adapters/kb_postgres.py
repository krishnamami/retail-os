"""Read-only governed KB resolver.

Resolves governance metadata. Embeds no business logic, evaluates no rule, and
parses no prose.

SAFETY PROPERTIES THIS MODULE GUARANTEES
----------------------------------------
1. It never reads claris_kb.identity_rules. Semantic candidates -- IR-010..
   IR-013, status 'proposed' -- are never promoted into executable
   RuleBindings. A unit test asserts the string 'identity_rules' does not
   appear in this module's source.
2. It never assigns rule_class. rule_class is domain registration metadata
   (see decisions/ports.py). It is not inferred from prose, outcome_code or
   precedence.
3. `condition` is carried verbatim as metadata and never parsed, evaluated,
   translated or transmitted. A unit test asserts no eval/exec/compile/ast use.
4. kb_version, ontology_version and policy_version stay distinct. If a
   decision type's rules disagree on the triple, that is reported as
   GovernanceVersionAmbiguity, not resolved by guessing.
5. A decision type with no executable rules raises NoExecutableRuleSet, a
   SYSTEM status -- never a business CANNOT_DECIDE.

SOURCE OF TRUTH
    Governed rule metadata is read from claris_kb.decision_rules, not from
    claris_kb.v_active_decision_rules. The live D.4D run established that the
    view does not expose policy_version, so a fixed column list against it
    fails outright. The base table carries the full governed column set; the
    active KB version selects the right rows; the view is consulted separately
    only to report how many rules it considers active.

    The selected column list is built from information_schema at runtime, so a
    deployment missing an optional governed column degrades explicitly instead
    of raising UndefinedColumn.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Optional, Sequence

from ..digest import canonical_json
from ..ports import ActiveKB, GovernedRuleMetadata, ResolvedRuleSet
from .errors import (
    GovernanceVersionAmbiguity,
    KBVersionNotFound,
    MultipleActiveKB,
    NoActiveKB,
    NoExecutableRuleSet,
)

__all__ = [
    "ACTIVE_STATUS",
    "ACTIVE_KB_SQL",
    "ACTIVE_RULE_IDS_SQL",
    "ACTIVE_RULE_COUNT_SQL",
    "COLUMNS_SQL",
    "GOVERNED_RULE_COLUMNS",
    "REQUIRED_RULE_COLUMNS",
    "build_rules_sql",
    "map_rule_row",
    "compute_rule_set_digest",
    "PostgresKBResolver",
]

ACTIVE_STATUS = "ACTIVE"

ACTIVE_KB_SQL = "SELECT * FROM claris_kb.v_active_kb"

RULE_SCHEMA = "claris_kb"
RULE_TABLE = "decision_rules"
ACTIVE_RULE_VIEW = "v_active_decision_rules"

# Governed columns we map when present. REQUIRED ones must exist.
REQUIRED_RULE_COLUMNS = (
    "decision_rule_id", "decision_type", "kb_version", "ontology_version",
    "outcome_code",
)
OPTIONAL_RULE_COLUMNS = (
    "policy_version", "rule_name", "condition", "precedence",
    "required_evidence", "missing_evidence_action", "contradiction_action",
    "status", "authority", "blocking_note",
)
GOVERNED_RULE_COLUMNS = REQUIRED_RULE_COLUMNS + OPTIONAL_RULE_COLUMNS

COLUMNS_SQL = """
SELECT column_name
FROM information_schema.columns
WHERE table_schema = %s AND table_name = %s
ORDER BY ordinal_position
"""

ACTIVE_RULE_IDS_SQL = f"""
SELECT decision_rule_id
FROM {RULE_SCHEMA}.{ACTIVE_RULE_VIEW}
WHERE decision_type = %s
"""

ACTIVE_RULE_COUNT_SQL = f"""
SELECT count(*) AS n
FROM {RULE_SCHEMA}.{ACTIVE_RULE_VIEW}
WHERE decision_type = %s
"""


def build_rules_sql(available: set) -> str:
    """SELECT only the governed columns this deployment actually exposes.

    claris_kb.decision_rules is the authority for governed rule metadata:
    D.4D's live run established that claris_kb.v_active_decision_rules does
    NOT expose policy_version, so selecting a fixed column list from the view
    fails. The base table is read for metadata; the view is consulted
    separately for which rules are active.
    """
    missing_required = [c for c in REQUIRED_RULE_COLUMNS if c not in available]
    if missing_required:
        raise KeyError(
            f"{RULE_SCHEMA}.{RULE_TABLE} is missing required governed columns: "
            f"{', '.join(missing_required)}"
        )
    selected = [c for c in GOVERNED_RULE_COLUMNS if c in available]
    quoted = ", ".join(f'"{c}"' for c in selected)
    return (
        f"SELECT {quoted}\n"
        f"FROM {RULE_SCHEMA}.{RULE_TABLE}\n"
        "WHERE decision_type = %s AND kb_version = %s"
    )


# ======================================================================
# pure mapping -- no I/O
# ======================================================================

def map_rule_row(row: Mapping[str, Any]) -> GovernedRuleMetadata:
    """Map one governed rule row to metadata.

    `rule_id` is taken from `decision_rule_id`, the table's primary key and
    therefore its governed identity. `rule_name` is preserved separately.
    NOTE: claris_kb.decision_rules has no `rule_id` column, unlike
    claris_kb.identity_rules where IR-010..IR-013 live. Which identifier a
    domain pack keys predicates on is a D.4E decision; both are carried here
    so neither is lost.
    """
    for column in ("decision_rule_id", "decision_type", "kb_version",
                   "ontology_version", "outcome_code"):
        if column not in row:
            raise KeyError(f"governed rule row is missing column {column!r}")

    precedence = row.get("precedence")
    if precedence is None:
        precedence = 0
    if isinstance(precedence, bool) or not isinstance(precedence, int):
        try:
            precedence = int(precedence)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"rule {row.get('decision_rule_id')!r}: precedence is not an "
                f"integer: {precedence!r}"
            ) from exc

    return GovernedRuleMetadata(
        decision_type=row["decision_type"],
        rule_id=str(row["decision_rule_id"]),
        kb_version=row["kb_version"],
        ontology_version=row["ontology_version"],
        policy_version=row.get("policy_version") or "",
        precedence=precedence,
        outcome_code=row["outcome_code"],
        rule_name=row.get("rule_name"),
        reason_code=None,  # no reason_code column exists in the governed table
        condition_text=row.get("condition"),  # METADATA ONLY -- never evaluated
        required_evidence=row.get("required_evidence"),
        missing_evidence_action=row.get("missing_evidence_action"),
        contradiction_action=row.get("contradiction_action"),
        status=row.get("status"),
        authority=row.get("authority"),
        blocking_note=row.get("blocking_note"),
    )


def compute_rule_set_digest(rules: Sequence[GovernedRuleMetadata]) -> str:
    """Deterministic fingerprint of a resolved rule set.

    Feeds input_digest so that a change to the governed rule set is visible in
    every decision made under it. Ordered by rule_id, so storage order cannot
    alter it.
    """
    payload = [
        {
            "decision_type": r.decision_type,
            "rule_id": r.rule_id,
            "kb_version": r.kb_version,
            "ontology_version": r.ontology_version,
            "policy_version": r.policy_version,
            "precedence": r.precedence,
            "outcome_code": r.outcome_code,
            "status": r.status,
        }
        for r in sorted(rules, key=lambda r: r.rule_id)
    ]
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"v1:sha256:{digest}"


# ======================================================================
# live resolver
# ======================================================================

class PostgresKBResolver:
    """Reads claris_kb governance metadata. Read-only."""

    __slots__ = ("_db", "_columns")

    def __init__(self, db) -> None:
        self._db = db
        self._columns: Optional[set] = None

    # -- schema introspection -------------------------------------------

    def available_rule_columns(self) -> set:
        """Governed columns actually present, discovered once and cached."""
        if self._columns is None:
            rows = self._db.query(COLUMNS_SQL, (RULE_SCHEMA, RULE_TABLE))
            self._columns = {r["column_name"] for r in rows}
        return self._columns

    def missing_governed_columns(self) -> tuple:
        available = self.available_rule_columns()
        return tuple(c for c in GOVERNED_RULE_COLUMNS if c not in available)

    def active_rule_count(self, decision_type: str) -> int:
        """How many rules the active view exposes. Reporting only."""
        rows = self._db.query(ACTIVE_RULE_COUNT_SQL, (decision_type,))
        return rows[0]["n"] if rows else 0

    # -- active KB ------------------------------------------------------

    def active_kb(self) -> ActiveKB:
        rows = self._db.query(ACTIVE_KB_SQL)
        if not rows:
            raise NoActiveKB("claris_kb.v_active_kb returned no row")
        if len(rows) > 1:
            raise MultipleActiveKB(
                f"claris_kb.v_active_kb returned {len(rows)} rows; exactly one "
                "active KB is required for deterministic resolution"
            )
        row = rows[0]
        version = row.get("kb_version")
        if not version:
            raise NoActiveKB(
                "claris_kb.v_active_kb has no usable kb_version; available "
                f"columns: {sorted(row)}"
            )
        return ActiveKB(kb_version=str(version), raw=dict(row))

    # -- rules ----------------------------------------------------------

    def resolve_rules(
        self, decision_type: str, kb_version: Optional[str] = None
    ) -> ResolvedRuleSet:
        """Resolve executable governed rule metadata for one decision type.

        kb_version=None  -> the active KB, read from v_active_decision_rules
        kb_version given -> replay against claris_kb.decision_rules
        """
        explicit = kb_version is not None
        resolved_version = kb_version if explicit else self.active_kb().kb_version

        sql = build_rules_sql(self.available_rule_columns())
        rows = self._db.query(sql, (decision_type, resolved_version))
        if not rows and explicit:
            raise KBVersionNotFound(
                f"no governed rules for decision_type={decision_type!r} at "
                f"kb_version={kb_version!r}"
            )

        executable: list[GovernedRuleMetadata] = []
        excluded: list[tuple[str, str]] = []
        for row in rows:
            metadata = map_rule_row(row)
            status = (metadata.status or "").upper()
            if status and status != ACTIVE_STATUS:
                excluded.append((metadata.rule_id, f"status={metadata.status}"))
                continue
            executable.append(metadata)

        if not executable:
            raise NoExecutableRuleSet(
                f"no executable governed rules for decision_type={decision_type!r} "
                f"at kb_version={resolved_version!r}"
                + (
                    f"; {len(excluded)} rule(s) excluded by status"
                    if excluded
                    else ". Semantic candidates in claris_kb.identity_rules are NOT "
                    "promoted into executable rules."
                )
            )

        triples = {
            (r.kb_version, r.ontology_version, r.policy_version) for r in executable
        }
        if len(triples) > 1:
            raise GovernanceVersionAmbiguity(
                f"decision_type={decision_type!r} resolves to {len(triples)} distinct "
                "(kb_version, ontology_version, policy_version) triples: "
                f"{sorted(triples)}. The adapter will not choose one."
            )
        kb_v, ontology_v, policy_v = next(iter(triples))

        return ResolvedRuleSet(
            decision_type=decision_type,
            kb_version=kb_v,
            ontology_version=ontology_v,
            policy_version=policy_v,
            rules=tuple(sorted(executable, key=lambda r: r.rule_id)),
            excluded_rules=tuple(sorted(excluded)),
            rule_set_digest=compute_rule_set_digest(executable),
        )
