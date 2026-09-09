"""Governed readiness: the rules, exercised without a database.

The test that matters most is the first one. Eight SKUs in the corpus carry
technical_review_result = PASS whose provenance is DEFAULTED -- the value
exists because a COALESCE fallback says PASS, not because any source asserted
it. A readiness decision that accepted those would declare eight SKUs
technically approved on the strength of a constant in mapping code. That is
the failure this entire phase exists to prevent, so it is asserted directly.
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from decisions.domains.claris.readiness import (  # noqa: E402
    CANNOT_DECIDE, NOT_READY, READY, evaluate, evaluate_all,
)
from decisions.domains.claris.readiness.evaluate import (  # noqa: E402
    FAILED, INSUFFICIENT_PROVENANCE, MISSING, SATISFIED, UNRECOGNISED_VALUE,
)


def prop(value, provenance="OBSERVED", fold_state="ESTABLISHED"):
    return {"fold_state": fold_state, "value": value, "provenance": provenance}


def finding(decision, name):
    return next(f for f in decision.findings if f.property_name == name)


# -- the headline ------------------------------------------------------------

def test_defaulted_pass_does_not_make_a_sku_technically_ready():
    d = evaluate("TECHNICAL_READINESS", "SKU-004",
                 {"technical_review_result": prop("PASS", "DEFAULTED")})
    assert d.outcome == CANNOT_DECIDE
    assert finding(d, "technical_review_result").status == INSUFFICIENT_PROVENANCE
    assert d.insufficient_evidence == ("technical_review_result",)
    assert "projection defaults" in d.why_not()


def test_observed_pass_does():
    d = evaluate("TECHNICAL_READINESS", "SKU-999",
                 {"technical_review_result": prop("PASS")})
    assert d.outcome == READY
    assert finding(d, "technical_review_result").status == SATISFIED


def test_defaulted_and_observed_differ_only_by_provenance():
    """Identical value, opposite outcome. The whole point, in one assertion."""
    observed = evaluate("TECHNICAL_READINESS", "S",
                        {"technical_review_result": prop("PASS", "OBSERVED")})
    defaulted = evaluate("TECHNICAL_READINESS", "S",
                         {"technical_review_result": prop("PASS", "DEFAULTED")})
    assert observed.outcome == READY
    assert defaulted.outcome == CANNOT_DECIDE


# -- the three ways of not being ready are distinguishable -------------------

def test_observed_rejection_is_not_ready_not_undecidable():
    d = evaluate("TECHNICAL_READINESS", "SKU-013",
                 {"technical_review_result": prop("REJECTED")})
    assert d.outcome == NOT_READY
    assert d.failures == ("technical_review_result",)


def test_absent_evidence_is_undecidable_not_a_failure():
    d = evaluate("TECHNICAL_READINESS", "SKU-006", {})
    assert d.outcome == CANNOT_DECIDE
    assert d.missing_evidence == ("technical_review_result",)
    assert d.failures == ()


def test_the_three_reasons_are_reported_differently():
    rejected = evaluate("TECHNICAL_READINESS", "a",
                        {"technical_review_result": prop("REJECTED")})
    defaulted = evaluate("TECHNICAL_READINESS", "b",
                         {"technical_review_result": prop("PASS", "DEFAULTED")})
    absent = evaluate("TECHNICAL_READINESS", "c", {})
    assert len({rejected.why_not(), defaulted.why_not(), absent.why_not()}) == 3


def test_contradiction_is_undecidable():
    d = evaluate("TECHNICAL_READINESS", "x",
                 {"technical_review_result": prop("PASS",
                                                  fold_state="CONTRADICTED")})
    assert d.outcome == CANNOT_DECIDE


def test_unrecognised_value_is_not_guessed():
    d = evaluate("TECHNICAL_READINESS", "x",
                 {"technical_review_result": prop("PENDING_REVIEW")})
    assert d.outcome == CANNOT_DECIDE
    assert finding(d, "technical_review_result").status == UNRECOGNISED_VALUE


# -- context inputs never decide ---------------------------------------------

def test_context_inputs_do_not_gate():
    d = evaluate("TECHNICAL_READINESS", "x",
                 {"technical_review_result": prop("PASS"),
                  "sku_status": prop("MINTED", "DEFAULTED")})
    assert d.outcome == READY, "a defaulted context value must not block"
    assert finding(d, "sku_status").blocks is False


# -- pricing approval: two disjoint routes, one gate -------------------------

PRICED = {"pricing_status": prop("DETERMINED"),
          "pricing_value_usd": prop("350000.0")}


def test_final_approval_route_satisfies_pricing():
    d = evaluate("PRICING_READINESS", "SKU-004",
                 dict(PRICED, final_pricing_approval_status=prop("APPROVED")))
    assert d.outcome == READY


def test_confirmed_route_satisfies_pricing():
    d = evaluate("PRICING_READINESS", "SKU-001",
                 dict(PRICED, pricing_confirmed=prop("CONFIRMED")))
    assert d.outcome == READY


def test_neither_route_reported_is_undecidable():
    d = evaluate("PRICING_READINESS", "SKU-007", dict(PRICED))
    assert d.outcome == CANNOT_DECIDE
    assert finding(d, "pricing_approval").status == MISSING


def test_defaulted_approval_route_is_insufficient_not_accepted():
    d = evaluate("PRICING_READINESS", "x",
                 dict(PRICED,
                      final_pricing_approval_status=prop("APPROVED",
                                                         "DEFAULTED")))
    assert d.outcome == CANNOT_DECIDE
    assert finding(d, "pricing_approval").status == INSUFFICIENT_PROVENANCE


def test_missing_price_value_blocks_even_when_approved():
    d = evaluate("PRICING_READINESS", "x",
                 {"pricing_status": prop("DETERMINED"),
                  "final_pricing_approval_status": prop("APPROVED")})
    assert d.outcome == CANNOT_DECIDE
    assert "pricing_value_usd" in d.missing_evidence


# -- precedence --------------------------------------------------------------

def test_a_known_failure_outranks_unknowns():
    d = evaluate("LAUNCH_READINESS", "SKU-013",
                 {"go_live_approval_status": prop("REJECTED")},
                 composed={"TECHNICAL_READINESS": CANNOT_DECIDE,
                           "PRICING_READINESS": CANNOT_DECIDE})
    assert d.outcome == NOT_READY


def test_unknowns_outrank_ready():
    d = evaluate("LAUNCH_READINESS", "x",
                 {"go_live_approval_status": prop("APPROVED")},
                 composed={"TECHNICAL_READINESS": READY,
                           "PRICING_READINESS": CANNOT_DECIDE})
    assert d.outcome == CANNOT_DECIDE


def test_launch_ready_requires_every_subordinate():
    d = evaluate("LAUNCH_READINESS", "x",
                 {"go_live_approval_status": prop("APPROVED")},
                 composed={"TECHNICAL_READINESS": READY,
                           "PRICING_READINESS": READY})
    assert d.outcome == READY


def test_composition_reports_which_subordinate_blocked():
    d = evaluate("LAUNCH_READINESS", "x",
                 {"go_live_approval_status": prop("APPROVED")},
                 composed={"TECHNICAL_READINESS": CANNOT_DECIDE,
                           "PRICING_READINESS": READY})
    assert "TECHNICAL_READINESS is CANNOT_DECIDE" in d.why_not()


# -- the corpus cohorts, as the matrix reports them --------------------------

def test_the_defaulted_cohort_lands_where_expected():
    """SKU-004..012: priced and approved on observed evidence, technically
    undecidable because their PASS is manufactured."""
    decisions = evaluate_all("SKU-004", {
        "sku_status": prop("MINTED"),
        "technical_review_result": prop("PASS", "DEFAULTED"),
        "pricing_status": prop("DETERMINED"),
        "pricing_value_usd": prop("350000.0"),
        "final_pricing_approval_status": prop("APPROVED"),
        "zupdm_approval_status": prop("APPROVED"),
        "all_gates_cleared": prop("YES"),
        "pricing_upload_status": prop("UPLOADED"),
    })
    assert decisions["PRICING_READINESS"].outcome == READY
    assert decisions["TECHNICAL_READINESS"].outcome == CANNOT_DECIDE
    assert decisions["LAUNCH_READINESS"].outcome == CANNOT_DECIDE


def test_the_activation_cohort_lands_where_expected():
    """SKU-001..003: go-live approved and published, but no determination
    evidence ever arrived, so pricing cannot be evidenced."""
    decisions = evaluate_all("SKU-001", {
        "sku_activation_status": prop("ACTIVATED"),
        "pricing_confirmed": prop("CONFIRMED"),
        "pricing_publication_status": prop("PUBLISHED"),
        "go_live_approval_status": prop("APPROVED"),
        "material_activation_status": prop("ACTIVE"),
        "supply_chain_notification_status": prop("NOTIFIED"),
    })
    assert decisions["PRICING_READINESS"].outcome == CANNOT_DECIDE
    assert "pricing_status" in decisions["PRICING_READINESS"].missing_evidence
    assert decisions["LAUNCH_READINESS"].outcome == CANNOT_DECIDE


def test_rejected_sku_is_not_ready_at_launch():
    decisions = evaluate_all("SKU-013", {
        "technical_review_result": prop("REJECTED"),
        "sku_activation_status": prop("ACTIVATED"),
    })
    assert decisions["TECHNICAL_READINESS"].outcome == NOT_READY
    assert decisions["LAUNCH_READINESS"].outcome == NOT_READY


# -- determinism -------------------------------------------------------------

@pytest.mark.parametrize("decision_type",
                         ["TECHNICAL_READINESS", "PRICING_READINESS",
                          "LAUNCH_READINESS"])
def test_repeated_evaluation_is_identical(decision_type):
    props = {"technical_review_result": prop("PASS", "DEFAULTED"),
             "pricing_status": prop("DETERMINED"),
             "pricing_value_usd": prop("1.0"),
             "go_live_approval_status": prop("APPROVED")}
    a = evaluate(decision_type, "x", props)
    b = evaluate(decision_type, "x", props)
    assert a == b


def test_policy_version_is_recorded_on_every_decision():
    for d in evaluate_all("x", {}).values():
        assert d.policy_version.startswith("READINESS-v")
