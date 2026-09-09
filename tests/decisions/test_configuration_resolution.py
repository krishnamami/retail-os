"""The configuration-resolution defect, reproduced and fixed.

THE DEFECT
    CaseContextAssembler._configuration resolved a configuration ONLY through
    claris.configuration_version.identity_assessment_id. A NO_BUSINESS_CHANGE
    decision deliberately creates no version -- creating nothing is what makes
    it a duplicate -- so the lookup found nothing and the case context reported
    `configuration: None` for precisely the scenario the prototype exists to
    demonstrate: a duplicate request absorbed into an existing configuration.

    The request WAS resolved to a configuration. The absence of a version is
    the evidence of that, not a reason to disclaim it.

THE FIX
    A second path, used only when the first finds nothing: re-derive the
    canonical identity with the governed encoder and match it exactly. It is a
    lookup, not a guess -- it can only find the configuration this identity
    denotes -- and it refuses to run on an incomplete tuple, because that is
    the CANNOT_DECIDE case and inventing a configuration for it would
    manufacture certainty the fold declined to supply.

No database. These are pure assembly-logic tests over a stub reader.
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from decisions.domains.claris.agent.case import CaseContextAssembler  # noqa: E402
from decisions.domains.claris.identity import (  # noqa: E402
    IDENTITY_PROPERTIES,
    encode_identity_values,
)

COMPLETE = {
    "product_reference": "PROD-001",
    "geography": "NAMER",
    "term_months": "36",
    "customer_segment": "enterprise",
}
ESTABLISHED = {name: "ESTABLISHED" for name in IDENTITY_PROPERTIES}

CONFIG_ROW = {
    "configuration_id": "CFG-PROD-001-abcd1234",
    "product_id": "PROD-001",
    "canonical_identity": encode_identity_values(
        (COMPLETE[n] for n in IDENTITY_PROPERTIES)),
    "identity_digest": None,
    "status": "active",
    "governed_identity": True,
    "created_at": None,
    "created_by": "vertical-slice",
    "archived_at": None,
}


class StubDB:
    """Answers the two queries _configuration makes, and records them."""

    def __init__(self, version_rows=(), identity_rows=()):
        self.version_rows = list(version_rows)
        self.identity_rows = list(identity_rows)
        self.calls = []

    def query(self, sql, params=None):
        self.calls.append((sql, params))
        if "configuration_version v" in sql:
            return list(self.version_rows)
        if "c.canonical_identity = %s" in sql:
            return list(self.identity_rows)
        return []


def assembler(db):
    return CaseContextAssembler(db, release=None,
                                identity_properties=IDENTITY_PROPERTIES)


DECISION = {"decision_id": "11111111-1111-1111-1111-111111111111"}


# -- path 1: a decision that created a version -------------------------------

def test_version_link_still_wins_and_is_labelled():
    db = StubDB(version_rows=[CONFIG_ROW])
    row = assembler(db)._configuration([DECISION], "PROD-001",
                                       COMPLETE, ESTABLISHED)
    assert row["configuration_id"] == "CFG-PROD-001-abcd1234"
    assert row["resolved_via"] == "version"
    # the identity lookup must not even be attempted
    assert not any("c.canonical_identity = %s" in s for s, _ in db.calls)


# -- path 2: NO_BUSINESS_CHANGE, the defect ----------------------------------

def test_duplicate_with_no_version_now_resolves():
    """The reproduction. Before the fix this returned None."""
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    row = assembler(db)._configuration([DECISION], "PROD-001",
                                       COMPLETE, ESTABLISHED)
    assert row is not None, "a duplicate must name the configuration it joined"
    assert row["configuration_id"] == "CFG-PROD-001-abcd1234"
    assert row["resolved_via"] == "canonical_identity"


def test_absorbed_is_distinguishable_from_created():
    created = assembler(StubDB(version_rows=[CONFIG_ROW]))._configuration(
        [DECISION], "PROD-001", COMPLETE, ESTABLISHED)
    absorbed = assembler(StubDB(identity_rows=[CONFIG_ROW]))._configuration(
        [DECISION], "PROD-001", COMPLETE, ESTABLISHED)
    assert created["resolved_via"] != absorbed["resolved_via"]


def test_identity_lookup_uses_the_governed_encoding():
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    assembler(db)._configuration([DECISION], "PROD-001", COMPLETE, ESTABLISHED)
    identity_calls = [p for s, p in db.calls if "c.canonical_identity = %s" in s]
    assert identity_calls, "the identity path was never taken"
    canonical, product = identity_calls[0]
    assert canonical == encode_identity_values(
        (COMPLETE[n] for n in IDENTITY_PROPERTIES))
    assert product == "PROD-001"
    # length-prefixed v2 encoding, not a bare join
    assert canonical.startswith("v2|")
    assert canonical.count("|") == len(IDENTITY_PROPERTIES)


# -- path 2 refuses to run on anything less than a complete tuple ------------

@pytest.mark.parametrize("missing", list(IDENTITY_PROPERTIES))
def test_incomplete_identity_resolves_to_nothing(missing):
    states = dict(ESTABLISHED, **{missing: "UNREPORTED"})
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    assert assembler(db)._configuration([DECISION], "PROD-001",
                                        COMPLETE, states) is None
    assert not any("c.canonical_identity = %s" in s for s, _ in db.calls)


def test_contradicted_identity_resolves_to_nothing():
    states = dict(ESTABLISHED, geography="CONTRADICTED")
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    assert assembler(db)._configuration([DECISION], "PROD-001",
                                        COMPLETE, states) is None


def test_missing_product_reference_resolves_to_nothing():
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    assert assembler(db)._configuration([DECISION], None,
                                        COMPLETE, ESTABLISHED) is None


def test_no_matching_configuration_resolves_to_nothing():
    db = StubDB(version_rows=[], identity_rows=[])
    assert assembler(db)._configuration([DECISION], "PROD-001",
                                        COMPLETE, ESTABLISHED) is None


# -- rendering is the governed renderer, not a local str() -------------------

def test_integer_term_months_renders_canonically():
    values = dict(COMPLETE, term_months=36)
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    assembler(db)._configuration([DECISION], "PROD-001", values, ESTABLISHED)
    canonical = [p for s, p in db.calls
                 if "c.canonical_identity = %s" in s][0][0]
    assert canonical == CONFIG_ROW["canonical_identity"]


def test_float_term_months_is_refused_rather_than_rounded():
    values = dict(COMPLETE, term_months=36.0)
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    assert assembler(db)._configuration([DECISION], "PROD-001",
                                        values, ESTABLISHED) is None


def test_boolean_value_is_refused():
    values = dict(COMPLETE, geography=True)
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    assert assembler(db)._configuration([DECISION], "PROD-001",
                                        values, ESTABLISHED) is None


def test_no_decisions_at_all_still_resolves_by_identity():
    """A subject with no decision yet is not a reason to hide the config."""
    db = StubDB(version_rows=[], identity_rows=[CONFIG_ROW])
    row = assembler(db)._configuration([], "PROD-001", COMPLETE, ESTABLISHED)
    assert row["resolved_via"] == "canonical_identity"
