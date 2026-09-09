"""Shared constants and helpers for the live integration suite.

Uniquely named, not `conftest`: this repository has several conftest.py files
and no packages, so importing `conftest` from a test module is unreliable.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DECISIONS = os.path.abspath(os.path.join(_HERE, ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _path in (_REPO_ROOT, _TESTS_DECISIONS, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

IDENTITY_PROPERTIES = ("product_reference", "geography", "term_months", "customer_segment")
SUBJECT_TYPE = "configuration_request"
EXECUTABLE_DECISION_TYPE = "CHANGE_CLASSIFICATION"
NON_EXECUTABLE_DECISION_TYPE = "IDENTITY_ASSESSMENT"
PROPOSED_IDENTITY_RULES = ("IR-010", "IR-011", "IR-012", "IR-013")

MUTATION_WITNESS_TABLES = (
    "claris.decision",
    "claris.action_record",
    "claris.product",
    "claris.configuration",
    "claris.configuration_version",
    "claris_kb.decision_rules",
    "claris_kb.identity_rules",
)


def row_counts(db) -> dict:
    """Row counts for every table D.4D must not modify."""
    counts = {}
    for table in MUTATION_WITNESS_TABLES:
        schema, name = table.split(".")
        exists = db.scalar("SELECT to_regclass(%s)", (table,))
        counts[table] = (
            db.scalar(f"SELECT count(*) FROM {schema}.{name}") if exists else None
        )
    return counts


def kb_status_fingerprint(db) -> list:
    """Status distribution across governed rule tables, to prove no activation."""
    return db.query(
        """
        SELECT 'decision_rules' AS source, decision_type AS scope, status, count(*) AS n
        FROM claris_kb.decision_rules GROUP BY 1, 2, 3
        UNION ALL
        SELECT 'identity_rules', kb_version, status, count(*)
        FROM claris_kb.identity_rules GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
        """
    )
