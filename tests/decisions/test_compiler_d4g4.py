"""D.4G.4 -- deterministic authoring-release compiler."""

from __future__ import annotations

import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ontology_authoring.compiler.compile_release import (  # noqa: E402
    COMPILER_VERSION,
    SECTION_KEYS,
    CompilationError,
    canonical_json,
    compile_release,
    semantic_digest,
)

DOMAIN = "retail"
VERSION = "2026.10-prototype.1"


class FakeDB:
    """Serves rows per table. The compiler must not care about row order."""

    def __init__(self, tables):
        self.tables = tables

    def query(self, sql, params=None):
        table = sql.split("ontology_authoring.")[1].split()[0]
        rows = self.tables.get(table, [])
        if params and "WHERE domain" in sql:
            return [dict(r) for r in rows
                    if r.get("ontology_version") == params[1]]
        return [dict(r) for r in rows]


def _release(**overrides):
    row = dict(domain=DOMAIN, ontology_version=VERSION, status="published",
               release_class="PROTOTYPE",
               validation_status="TO_BE_VALIDATED_WITH_CLARIS",
               parent_ontology_version="2026.10",
               parent_release_class="AUTHORITATIVE")
    row.update(overrides)
    return row


def _dimension(name, ordinal, in_tuple):
    return dict(domain=DOMAIN, ontology_version=VERSION, dimension=name,
                ordinal=ordinal, release_class="PROTOTYPE",
                governance_basis="PROTOTYPE_ASSUMPTION",
                identity_affecting="UNKNOWN",
                proposed_identity_affecting=in_tuple)


def _tables(**overrides):
    tables = {name: [] for name in SECTION_KEYS}
    tables["ontology_release"] = [_release()]
    tables["configuration_dimensions"] = [
        _dimension("product_reference", 0, True),
        _dimension("geography", 1, True),
        _dimension("term_months", 2, True),
        _dimension("customer_segment", 3, True),
        _dimension("user_tier", 4, False),
    ]
    tables["identity_rules"] = [
        dict(domain=DOMAIN, ontology_version=VERSION, rule="IR-002",
             release_class="PROTOTYPE", governance_basis="PROTOTYPE_ASSUMPTION",
             proposed_effect="CREATE_CONFIGURATION", identity_effect=None,
             governance_state="PROPOSED"),
        dict(domain=DOMAIN, ontology_version=VERSION, rule="IR-006",
             release_class="PROTOTYPE", governance_basis="PROTOTYPE_ASSUMPTION",
             proposed_effect=None, identity_effect=None,
             governance_state="UNPROPOSED"),
    ]
    tables["decisions"] = [dict(domain=DOMAIN, ontology_version=VERSION,
                                decision="IDENTITY_ASSESSMENT")]
    tables["decision_outputs"] = [
        dict(domain=DOMAIN, ontology_version=VERSION,
             decision="IDENTITY_ASSESSMENT", outcome=code,
             release_class="PROTOTYPE", governance_basis="PROTOTYPE_ASSUMPTION")
        for code in ("CREATE_CONFIGURATION", "NO_BUSINESS_CHANGE",
                     "CANNOT_DECIDE")]
    tables["decision_rule_bindings"] = [
        dict(domain=DOMAIN, ontology_version=VERSION,
             decision="IDENTITY_ASSESSMENT", rule_id="IA-PRED-001",
             predicate_name="ir_011_missing_required_input", precedence=1,
             expected_outcome="CANNOT_DECIDE", release_class="PROTOTYPE",
             governance_basis="PROTOTYPE_ASSUMPTION"),
        dict(domain=DOMAIN, ontology_version=VERSION,
             decision="IDENTITY_ASSESSMENT", rule_id="IA-PRED-003",
             predicate_name="ir_013_initial_configuration", precedence=5,
             expected_outcome="CREATE_CONFIGURATION", release_class="PROTOTYPE",
             governance_basis="PROTOTYPE_ASSUMPTION"),
    ]
    for key, value in overrides.items():
        tables[key] = value
    return tables


def compile_ok(**overrides):
    return compile_release(FakeDB(_tables(**overrides)), DOMAIN, VERSION)


def compile_fails(match, **overrides):
    with pytest.raises(CompilationError) as excinfo:
        compile_release(FakeDB(_tables(**overrides)), DOMAIN, VERSION)
    assert match in str(excinfo.value), str(excinfo.value)


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------

def test_all_fourteen_sections_are_compiled():
    artifact = compile_ok()
    assert set(artifact.payload["sections"]) == set(SECTION_KEYS)
    assert len(SECTION_KEYS) == 14


def test_classification_is_carried_through_not_raised():
    artifact = compile_ok()
    assert artifact.release_class == "PROTOTYPE"
    assert artifact.governance_basis == "PROTOTYPE_ASSUMPTION"
    assert artifact.validation_status == "TO_BE_VALIDATED_WITH_CLARIS"
    assert artifact.parent_ontology_version == "2026.10"
    assert "AUTHORITATIVE" != artifact.governance_basis


def test_kb_version_is_derived_from_the_release_not_invented():
    assert compile_ok().kb_version == VERSION


def test_the_compiler_stamps_its_own_version():
    assert compile_ok().payload["compiler_version"] == COMPILER_VERSION


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------

def test_compiling_twice_reproduces_the_digest():
    assert compile_ok().semantic_digest == compile_ok().semantic_digest


def test_row_order_in_the_database_cannot_change_the_digest():
    baseline = compile_ok().semantic_digest
    shuffled = _tables()
    for key in ("configuration_dimensions", "decision_outputs",
                "decision_rule_bindings", "identity_rules"):
        shuffled[key] = list(reversed(shuffled[key]))
    assert compile_release(FakeDB(shuffled), DOMAIN, VERSION).semantic_digest \
        == baseline


def test_the_digest_carries_no_wall_clock_value():
    payload = compile_ok().payload
    rendered = canonical_json(payload)
    for stamp in ("generated_at", "deployed_at", "now()"):
        assert stamp not in rendered


def test_a_real_content_change_does_change_the_digest():
    baseline = compile_ok().semantic_digest
    changed = _tables()
    changed["identity_rules"][0]["proposed_effect"] = "NEW_VERSION"
    assert compile_release(FakeDB(changed), DOMAIN, VERSION).semantic_digest \
        != baseline


def test_canonical_json_is_key_order_independent():
    assert semantic_digest({"a": 1, "b": 2}) == semantic_digest({"b": 2, "a": 1})


# ---------------------------------------------------------------------------
# fail closed
# ---------------------------------------------------------------------------

def test_a_draft_release_cannot_compile():
    compile_fails("published", ontology_release=[_release(status="draft")])


def test_exactly_one_release_row_is_required():
    compile_fails("exactly one release row", ontology_release=[])


def test_a_prototype_must_declare_it_awaits_claris():
    compile_fails("TO_BE_VALIDATED_WITH_CLARIS",
                  ontology_release=[_release(validation_status=None)])


def test_a_prototype_must_descend_from_an_authoritative_release():
    compile_fails("must descend from an AUTHORITATIVE",
                  ontology_release=[_release(parent_release_class="PROTOTYPE")])


def test_a_prototype_assumption_cannot_occupy_identity_affecting():
    tables = _tables()
    tables["configuration_dimensions"][0]["identity_affecting"] = "TRUE"
    compile_fails("cannot occupy identity_affecting", **tables)


def test_a_prototype_assumption_cannot_occupy_identity_effect():
    tables = _tables()
    tables["identity_rules"][0]["identity_effect"] = "CREATE_CONFIGURATION"
    compile_fails("cannot occupy identity_effect", **tables)


def test_classification_contamination_fails_closed():
    tables = _tables()
    tables["identity_rules"][0]["governance_basis"] = "AUTHORITATIVE"
    compile_fails("in a PROTOTYPE release", **tables)


def test_a_binding_cannot_reference_an_unknown_decision():
    tables = _tables()
    tables["decision_rule_bindings"][0]["decision"] = "LAUNCH_READINESS"
    compile_fails("references unknown decision", **tables)


def test_a_binding_cannot_expect_an_undeclared_outcome():
    tables = _tables()
    tables["decision_rule_bindings"][0]["expected_outcome"] = "READY_FOR_LAUNCH"
    compile_fails("does not declare", **tables)


def test_a_binding_must_name_a_predicate():
    tables = _tables()
    tables["decision_rule_bindings"][0]["predicate_name"] = ""
    compile_fails("names no predicate", **tables)


def test_a_business_rule_id_cannot_be_bound_as_a_predicate():
    tables = _tables()
    tables["decision_rule_bindings"][0]["rule_id"] = "IR-011"
    compile_fails("must not\nbe bound as an executable predicate".replace("\n", " "),
                  **tables)


def test_duplicate_precedence_fails_closed():
    tables = _tables()
    tables["decision_rule_bindings"][1]["precedence"] = 1
    compile_fails("duplicate precedence", **tables)


def test_an_unresolved_rule_cannot_look_resolved():
    tables = _tables()
    tables["identity_rules"][1]["governance_state"] = "PROPOSED"
    compile_fails("must be visibly unresolved", **tables)


def test_the_locked_identity_tuple_is_enforced():
    tables = _tables()
    tables["configuration_dimensions"][4]["proposed_identity_affecting"] = True
    compile_fails("not the locked", **tables)


def test_a_missing_tuple_member_fails_closed():
    tables = _tables()
    tables["configuration_dimensions"][0]["proposed_identity_affecting"] = False
    compile_fails("not the locked", **tables)


def test_failure_produces_no_artifact():
    """A release that cannot be proven valid yields nothing, not a warning."""
    with pytest.raises(CompilationError) as excinfo:
        compile_release(FakeDB(_tables(ontology_release=[_release(status="draft")])),
                        DOMAIN, VERSION)
    assert "no artifact produced" in str(excinfo.value)


def test_every_failure_is_reported_not_just_the_first():
    tables = _tables(ontology_release=[_release(status="draft",
                                                validation_status=None)])
    with pytest.raises(CompilationError) as excinfo:
        compile_release(FakeDB(tables), DOMAIN, VERSION)
    assert "published" in str(excinfo.value)
    assert "TO_BE_VALIDATED_WITH_CLARIS" in str(excinfo.value)
