"""D.4G.1G.5 -- authoring foundation structural tests.

These tests read the implementation artifacts as text. They assert the
invariants the D.4G.1G.4 design locked, and in particular that the
restoration crosses no governance gate:

  * UNKNOWN stays UNKNOWN
  * an unsigned source confirmation restores as a proposal
  * no question is closed
  * no authority is populated
  * no decision becomes executable

Nothing here connects to a database.
"""

from __future__ import annotations

import importlib.util
import io
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DDL = os.path.join(ROOT, "ontology_authoring", "ddl",
                   "001_ontology_authoring_schema.sql")
RESTORE = os.path.join(ROOT, "ontology_authoring", "restore",
                       "002_restore_2026_10.sql")
BUILDER = os.path.join(ROOT, "ontology_authoring", "restore",
                       "build_restoration.py")
GOVDOCS = os.path.join(ROOT, "docs", "governance")

FIRST_RELEASE_TABLES = {
    "ontology_release", "ontology_notes", "enums", "enum_values", "actors",
    "configuration_dimensions", "identity_rules", "decisions",
    "decision_outputs", "decision_dependencies", "projection_rules",
    "evidence_reference", "decision_reason_codes",
    # added at D.4G.1G.5P.1: G.4 classified this as REQUIRED ONLY BEFORE
    # EXECUTABLE KB ACTIVATION, and prototype execution is that activation.
    "decision_rule_bindings",
}

DEFERRED_TABLES = {
    "decision_inputs", "action_types", "action_authorizations", "read_grants",
    "configuration_dimension_values", "evidence_types", "object_types",
    "object_properties", "links",
}

EXPECTED_ROW_COUNTS = {
    "ontology_release": 1, "actors": 7, "ontology_notes": 7, "enums": 11,
    "enum_values": 46, "configuration_dimensions": 8, "identity_rules": 9,
    "decisions": 5, "decision_outputs": 27, "decision_reason_codes": 6,
    "decision_dependencies": 4, "projection_rules": 4,
}

IA_PRED_RESERVATION = {
    "IA-PRED-001": "missing required input",
    "IA-PRED-002": "contradicted required input",
    "IA-PRED-003": "initial configuration",
    "IA-PRED-004": "exact identity match",
}


def _read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def ddl():
    return _read(DDL)


@pytest.fixture(scope="module")
def restore():
    return _read(RESTORE)


def _strip_sql_comments(sql):
    """Drop -- comment lines and COMMENT ON prose. Documentation that
    describes a rule is not the same thing as a column that breaks it."""
    kept = [l for l in sql.splitlines() if not l.lstrip().startswith("--")]
    return re.sub(r"COMMENT ON .*?';", "", "\n".join(kept), flags=re.S)


def _values_block(sql, table):
    """One INSERT statement. Ends at ');' terminating a line, because a
    semicolon can and does appear inside a quoted value."""
    match = re.search(
        r"INSERT INTO ontology_authoring\.%s\b.*?\);\n" % re.escape(table),
        sql, re.S)
    return match.group(0) if match else ""


def _columns(block):
    head = re.search(r"\(\n?\s*(.*?)\)\nVALUES", block, re.S).group(1)
    return [c.strip() for c in head.replace("\n", " ").split(",")]


def _rows(block):
    """Split each VALUES tuple into fields, honouring quoted commas."""
    out = []
    for raw in re.findall(r"^    \((.*)\)[,;]$", block, re.M):
        fields, buf, in_str = [], [], False
        i = 0
        while i < len(raw):
            ch = raw[i]
            if in_str:
                if ch == "'" and raw[i:i + 2] == "''":
                    buf.append("''")
                    i += 2
                    continue
                if ch == "'":
                    in_str = False
                buf.append(ch)
            elif ch == "'":
                in_str = True
                buf.append(ch)
            elif ch == ",":
                fields.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
            i += 1
        fields.append("".join(buf).strip())
        out.append(fields)
    return out


def _row_count(sql, table):
    block = _values_block(sql, table)
    if not block:
        return 0
    return len(_rows(block))


# ---------------------------------------------------------------------------
# schema shape
# ---------------------------------------------------------------------------

def test_exactly_fourteen_first_release_tables(ddl):
    created = set(re.findall(r"CREATE TABLE ontology_authoring\.(\w+)", ddl))
    assert created == FIRST_RELEASE_TABLES
    assert len(created) == 14


def test_deferred_tables_are_absent(ddl):
    created = set(re.findall(r"CREATE TABLE ontology_authoring\.(\w+)", ddl))
    assert created & DEFERRED_TABLES == set()


def test_no_example_or_derived_tables(ddl):
    created = set(re.findall(r"CREATE TABLE ontology_authoring\.(\w+)", ddl))
    for banned in ("change_impact", "projection_matrix"):
        assert banned not in created
    assert not [t for t in created if t.startswith("example_")]


def test_ddl_targets_only_the_authoring_schema(ddl):
    """No legacy or runtime object is created, altered or dropped."""
    for stmt in ("CREATE TABLE", "ALTER TABLE", "DROP TABLE", "TRUNCATE"):
        for target in re.findall(re.escape(stmt) + r"\s+(?:IF EXISTS\s+)?(\S+)",
                                 ddl):
            assert target.startswith("ontology_authoring."), target
    body = _strip_sql_comments(ddl).replace("ontology_authoring.", "")
    # claris_kb is named once, inside the CHECK that forbids it as a release
    # source; that occurrence is asserted positively by its own test.
    body = re.sub(r"CONSTRAINT ck_ontology_release_source_not_projection.*?\)\)",
                  "", body, flags=re.S)
    for legacy in ("ontology.", "claris_kb", "claris.", "runtime.", "state."):
        assert legacy not in body


# ---------------------------------------------------------------------------
# UNKNOWN is first class
# ---------------------------------------------------------------------------

def test_identity_affecting_is_three_valued_and_defaults_unknown(ddl):
    assert "identity_affecting            varchar(8)   NOT NULL DEFAULT 'UNKNOWN'" in ddl
    assert ("CHECK (identity_affecting IN ('TRUE', 'FALSE', 'UNKNOWN'))" in ddl)


def test_no_boolean_default_false_anywhere(ddl):
    """A boolean defaulting to false asserts an answer nobody gave."""
    assert not re.search(r"boolean[^,\n]*DEFAULT\s+false",
                         _strip_sql_comments(ddl), re.I)


def test_proposed_identity_affecting_has_no_default(ddl):
    line = [l for l in ddl.splitlines()
            if "proposed_identity_affecting" in l and "boolean" in l]
    assert line and "DEFAULT" not in line[0]


# ---------------------------------------------------------------------------
# signature invariants
# ---------------------------------------------------------------------------

def test_open_question_cannot_carry_a_resolution(ddl):
    assert "ck_ontology_notes_open_is_empty" in ddl
    block = ddl.split("ck_ontology_notes_open_is_empty")[1].split("CONSTRAINT")[0]
    for field in ("resolution IS NULL", "authority IS NULL",
                  "confirmed_by IS NULL", "confirmed_on IS NULL",
                  "resolution_evidence IS NULL"):
        assert field in block


def test_answered_question_requires_complete_signed_evidence(ddl):
    assert "ck_ontology_notes_answered_is_complete" in ddl
    block = ddl.split("ck_ontology_notes_answered_is_complete")[1].split(")\n);")[0]
    for field in ("resolution IS NOT NULL", "authority IS NOT NULL",
                  "confirmed_by IS NOT NULL", "confirmed_on IS NOT NULL",
                  "resolution_evidence IS NOT NULL"):
        assert field in block


def test_confirmed_dimension_requires_authority_signature_and_evidence(ddl):
    assert "ck_configuration_dimensions_confirmed_is_signed" in ddl
    block = ddl.split("ck_configuration_dimensions_confirmed_is_signed")[1]
    block = block.split("CONSTRAINT")[0]
    assert "identity_affecting = 'UNKNOWN'" in block
    for field in ("authority IS NOT NULL", "confirmed_by IS NOT NULL",
                  "confirmed_on IS NOT NULL", "resolution_evidence IS NOT NULL"):
        assert field in block


def test_confirmed_identity_rule_requires_signature(ddl):
    assert "ck_identity_rules_confirmed_is_signed" in ddl
    block = ddl.split("ck_identity_rules_confirmed_is_signed")[1]
    block = block.split("CONSTRAINT")[0]
    assert "identity_effect IS NULL" in block
    for field in ("authority IS NOT NULL", "confirmed_by IS NOT NULL",
                  "confirmed_on IS NOT NULL", "evidence_reference IS NOT NULL"):
        assert field in block


# ---------------------------------------------------------------------------
# namespaces
# ---------------------------------------------------------------------------

def test_ir_namespace_excludes_executable_predicates(ddl):
    assert "ck_identity_rules_ir_namespace" in ddl
    assert "rule ~ '^IR-[0-9]{3}$'" in ddl


@pytest.mark.parametrize("predicate_id", sorted(IA_PRED_RESERVATION))
def test_executable_predicates_never_enter_identity_rules(predicate_id, ddl,
                                                          restore):
    assert predicate_id not in ddl
    assert predicate_id not in restore
    assert not re.match(r"^IR-[0-9]{3}$", predicate_id)


def test_release_source_can_never_be_a_projection_or_artifact_store(ddl):
    assert "ck_ontology_release_source_not_projection" in ddl
    block = ddl.split("ck_ontology_release_source_not_projection")[1]
    for forbidden in ("'claris_kb'", "'claris_kb.kb_artifact'", "'runtime'"):
        assert forbidden in block


# ---------------------------------------------------------------------------
# no activation, no executable content
# ---------------------------------------------------------------------------

def test_authoring_schema_has_no_activation_semantics(ddl):
    body = _strip_sql_comments(ddl)
    assert not re.search(r"^\s+(is_)?active\b", body, re.M | re.I)
    assert "'active'" not in body.lower()


def test_decisions_hold_no_executable_content(ddl):
    block = ddl.split("CREATE TABLE ontology_authoring.decisions")[1]
    block = block.split("CREATE TABLE")[0]
    for banned in ("predicate", "expression", "python", "code", "lambda"):
        assert banned not in block.lower()


def test_evidence_reference_is_append_only(ddl):
    assert "trg_evidence_reference_append_only" in ddl
    assert "BEFORE UPDATE OR DELETE ON ontology_authoring.evidence_reference" in ddl
    assert "deny_evidence_mutation" in ddl


def test_reason_code_scope_binding(ddl):
    assert "ck_decision_reason_codes_scope_binding" in ddl
    block = ddl.split("ck_decision_reason_codes_scope_binding")[1]
    assert "scope = 'PLATFORM'" in block and "decision_type IS NULL" in block
    assert "scope = 'DECISION_SPECIFIC'" in block
    assert "decision_type IS NOT NULL" in block


# ---------------------------------------------------------------------------
# restoration content
# ---------------------------------------------------------------------------

def test_restoration_row_counts(restore):
    for table, expected in EXPECTED_ROW_COUNTS.items():
        assert _row_count(restore, table) == expected, table


def test_restoration_holds_no_evidence_rows(restore):
    assert _row_count(restore, "evidence_reference") == 0


def test_every_dimension_restores_as_unknown(restore):
    block = _values_block(restore, "configuration_dimensions")
    assert block
    assert set(re.findall(r"'(TRUE|FALSE|UNKNOWN)'", block)) == {"UNKNOWN"}


def test_unsigned_source_confirmation_restores_unconfirmed(restore):
    """description was CONFIRMED / FALSE at source with no signature."""
    line = [l for l in restore.splitlines() if "'description', 7," in l]
    assert len(line) == 1
    row = line[0]
    assert "'UNKNOWN'" in row
    assert "'PROPOSED'" in row
    assert "'proposed'" in row
    assert "'CONFIRMED'" not in row


def test_ir_009_restores_as_proposed(restore):
    line = [l for l in restore.splitlines() if "'IR-009'" in l]
    assert len(line) == 1
    assert "'proposed'" in line[0]
    assert "'confirmed'" not in line[0]


def test_no_identity_effect_is_confirmed(restore):
    """identity_effect is the confirmed answer. It must be NULL everywhere."""
    block = _values_block(restore, "identity_rules")
    for row in re.findall(r"^    \((.*)\)[,;]$", block, re.M):
        fields = row.split(", ")
        # ... proposed_effect, identity_effect, governance_state ...
        assert "'PROPOSED'" in row
        assert re.search(r"'[A-Z_]+', NULL, 'PROPOSED'", row), row


def test_no_signature_is_ever_restored(restore):
    assert "confirmed_by" not in restore
    assert "confirmed_on" not in restore


def test_no_authority_is_ever_restored(restore):
    for table in ("configuration_dimensions", "identity_rules",
                  "projection_rules", "decisions"):
        block = _values_block(restore, table)
        index = _columns(block).index("authority")
        rows = _rows(block)
        assert rows
        for row in rows:
            assert row[index] == "NULL", (table, row[index])


def test_all_questions_restore_open(restore):
    block = _values_block(restore, "ontology_notes")
    rows = re.findall(r"^    \((.*)\)[,;]$", block, re.M)
    assert len(rows) == 7
    for row in rows:
        assert row.rstrip().endswith("'OPEN'"), row[:60]


def test_restored_question_ids_are_q001_to_q007(restore):
    block = _values_block(restore, "ontology_notes")
    ids = re.findall(r"'(Q-\d{3})'", block)
    assert ids == ["Q-001", "Q-002", "Q-003", "Q-004", "Q-005", "Q-006", "Q-007"]


def test_identity_assessment_is_not_executable(restore, ddl):
    """Nothing in the authoring foundation can make a decision executable."""
    assert "executable" not in _strip_sql_comments(ddl).lower()
    assert "executable" not in _strip_sql_comments(restore).lower()
    block = _values_block(restore, "decisions")
    assert "'IDENTITY_ASSESSMENT'" in block
    assert "'Q-002'" in block  # recorded as blocked


def test_restoration_uses_no_forbidden_source(restore):
    body = _strip_sql_comments(restore)
    for forbidden in ("claris_kb", "kb_artifact", "KB 1.1", "retail_ontology."):
        assert forbidden not in body
    assert "claris_ontology.sql" in restore  # provenance lives in the header


def test_restoration_is_deterministic():
    spec = importlib.util.spec_from_file_location("build_restoration", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    first = module.build()
    second = module.build()
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert first[3] == second[3]


# ---------------------------------------------------------------------------
# question identifiers in the session package
# ---------------------------------------------------------------------------

def test_session_package_uses_only_approved_question_ids():
    approved = {"Q-%03d" % n for n in range(1, 13)}
    for name in os.listdir(GOVDOCS):
        if not name.endswith(".md"):
            continue
        found = set(re.findall(r"Q-\d{3}", _read(os.path.join(GOVDOCS, name))))
        assert found <= approved, (name, sorted(found - approved))


def test_retired_question_ids_are_gone():
    for name in os.listdir(GOVDOCS):
        text = _read(os.path.join(GOVDOCS, name))
        assert "Q-013" not in text
        assert "Q-014" not in text


def test_capture_file_has_no_duplicate_question_entries():
    text = _read(os.path.join(GOVDOCS, "claris_governance_confirmation.md"))
    entries = re.findall(r"^### (Q-[0-9a-z.\-]+)$", text, re.M)
    assert len(entries) == len(set(entries))


def test_capture_file_records_no_answer():
    text = _read(os.path.join(GOVDOCS, "claris_governance_confirmation.md"))
    populated = []
    for line in text.splitlines():
        match = re.match(
            r"^\s{2,}(answer|conditions|examples|observed_from|observed_on|"
            r"authority|resolved_answer|resolved_by|resolved_on|"
            r"evidence_reference|follow_up_required):\s*(.+)$", line)
        if match and not match.group(2).strip().startswith("<"):
            populated.append(line.strip())
    assert populated == []
    statuses = set(re.findall(r"^answer_status:\s*(\S+)$", text, re.M))
    assert statuses == {"UNANSWERED"}


# ---------------------------------------------------------------------------
# legacy non-interference
# ---------------------------------------------------------------------------

def test_no_artifact_touches_legacy_or_runtime():
    for path in (DDL, RESTORE, BUILDER):
        text = _read(path)
        for stmt in ("DROP ", "TRUNCATE ", "DELETE FROM ", "UPDATE "):
            for hit in re.findall(re.escape(stmt) + r"\S+", text):
                assert "ontology_authoring" in hit or "TG_OP" in text, hit


# ---------------------------------------------------------------------------
# D.4G.1G.5P.1 -- prototype / production governance boundary
# ---------------------------------------------------------------------------

PROTOTYPE_SQL = os.path.join(ROOT, "ontology_authoring", "restore",
                             "003_prototype_2026_10_P1.sql")
PROTOTYPE_VERSION = "2026.10-prototype.1"
IA_PRED_IDS = ("IA-PRED-001", "IA-PRED-002", "IA-PRED-003", "IA-PRED-004")


@pytest.fixture(scope="module")
def prototype():
    return _read(PROTOTYPE_SQL)


def test_prototype_assumption_can_never_be_confirmed(ddl):
    """The basis and the confirmed fields are mutually exclusive by CHECK."""
    for constraint, guard in (
        ("ck_configuration_dimensions_assumption_is_never_confirmed",
         "identity_affecting = 'UNKNOWN'"),
        ("ck_identity_rules_assumption_is_never_confirmed",
         "identity_effect IS NULL"),
        ("ck_decision_outputs_assumption_is_never_confirmed",
         "governance_state <> 'CONFIRMED'"),
    ):
        assert constraint in ddl
        block = ddl.split(constraint)[1].split("CONSTRAINT")[0]
        assert "governance_basis <> 'PROTOTYPE_ASSUMPTION'" in block
        assert guard in block


def test_prototype_rows_cannot_exist_outside_a_prototype_release(ddl):
    for table in ("configuration_dimensions", "identity_rules",
                  "decision_outputs", "decision_rule_bindings"):
        constraint = "ck_%s_basis_needs_prototype_release" % table
        assert constraint in ddl
        block = ddl.split(constraint)[1].split("CONSTRAINT")[0]
        assert "governance_basis <> 'PROTOTYPE_ASSUMPTION'" in block
        assert "release_class = 'PROTOTYPE'" in block
    # and the class itself cannot disagree with the release it points at
    for table in ("configuration_dimensions", "identity_rules"):
        block = ddl.split("CREATE TABLE ontology_authoring.%s" % table)[1]
        block = block.split("CREATE TABLE")[0]
        assert "FOREIGN KEY (domain, ontology_version, release_class)" in block


def test_prototype_release_requires_an_authoritative_parent(ddl):
    assert "ck_ontology_release_prototype_has_parent" in ddl
    assert "ck_ontology_release_parent_class" in ddl
    block = ddl.split("ck_ontology_release_parent_class")[1].split(");")[0]
    assert "parent_release_class = 'AUTHORITATIVE'" in block


def test_authoritative_release_cannot_descend_from_a_prototype(ddl):
    """The literal 'AUTHORITATIVE' in the parent tuple makes it one-way."""
    assert "fk_ontology_release_parent_is_authoritative" in ddl
    block = ddl.split("fk_ontology_release_parent_is_authoritative")[1]
    block = block.split("CONSTRAINT")[0]
    assert "(domain, parent_ontology_version, parent_release_class)" in block
    assert "(domain, ontology_version, release_class)" in block


def test_release_class_and_validation_status_agree(ddl):
    assert "ck_ontology_release_validation_status" in ddl
    block = ddl.split("ck_ontology_release_validation_status")[1]
    block = block.split("CONSTRAINT")[0]
    assert "release_class = 'PROTOTYPE'" in block
    assert "validation_status = 'TO_BE_VALIDATED_WITH_CLARIS'" in block
    assert "validation_status IS NULL" in block


def test_prototype_release_is_classified(prototype):
    assert "'%s'" % PROTOTYPE_VERSION in prototype
    assert "'PROTOTYPE'" in prototype
    assert "'TO_BE_VALIDATED_WITH_CLARIS'" in prototype
    assert "NOT CLARIS APPROVED" in prototype
    assert "FOR DEMONSTRATION ONLY" in prototype


def test_prototype_rows_carry_no_fabricated_authority_or_signature(prototype):
    # no signature COLUMN is written anywhere. Prose that explains why a
    # source row is unsigned is documentation, not a signature.
    for block in re.findall(r"INSERT INTO ontology_authoring\.\w+\n\s*\((.*?)\)\nVALUES",
                            prototype, re.S):
        columns = [c.strip() for c in block.replace("\n", " ").split(",")]
        assert "confirmed_by" not in columns
        assert "confirmed_on" not in columns
        assert "resolution_evidence" not in columns
        assert "evidence_reference" not in columns
    for table in ("configuration_dimensions", "identity_rules"):
        block = _values_block(prototype, table)
        index = _columns(block).index("authority")
        rows = _rows(block)
        assert rows
        for row in rows:
            assert row[index] == "NULL", (table, row[index])


def test_prototype_dimensions_stay_unknown(prototype):
    block = _values_block(prototype, "configuration_dimensions")
    assert set(re.findall(r"'(TRUE|FALSE|UNKNOWN)'", block)) == {"UNKNOWN"}
    assert len(_rows(block)) == 7


def test_prototype_identity_effect_is_never_set(prototype):
    block = _values_block(prototype, "identity_rules")
    rows = _rows(block)
    columns = _columns(block)
    index = columns.index("identity_effect")
    assert len(rows) == 8
    for row in rows:
        assert row[index] == "NULL"
        assert row[columns.index("governance_basis")] == "'PROTOTYPE_ASSUMPTION'"


def test_prototype_excludes_ir_007_slp(prototype):
    assert "'IR-007'" not in prototype
    assert "'reclassify'" not in prototype
    assert "'slp_code'" not in prototype
    for rule in ("IR-001", "IR-002", "IR-003", "IR-004", "IR-005", "IR-006",
                 "IR-008", "IR-009"):
        assert "'%s'" % rule in prototype


def test_prototype_tuple_is_the_locked_four(prototype):
    block = _values_block(prototype, "configuration_dimensions")
    columns = _columns(block)
    dimension = columns.index("dimension")
    proposed = columns.index("proposed_identity_affecting")
    ordinal = columns.index("ordinal")
    tuple_members = sorted(
        (int(r[ordinal]), r[dimension].strip("'"))
        for r in _rows(block) if r[proposed] == "true")
    assert [name for _o, name in tuple_members] == [
        "product_reference", "geography", "term_months", "customer_segment"]


@pytest.mark.parametrize("predicate_id", IA_PRED_IDS)
def test_ia_pred_ids_appear_only_in_decision_rule_bindings(predicate_id,
                                                           prototype):
    bindings = _values_block(prototype, "decision_rule_bindings")
    ids = [r[_columns(bindings).index("rule_id")] for r in _rows(bindings)]
    assert "'%s'" % predicate_id in ids
    # it must not be an identifier in any governed table. Prose that mentions
    # a predicate while explaining a conflict is documentation, not a binding.
    for table, key in (("identity_rules", "rule"),
                       ("configuration_dimensions", "dimension"),
                       ("decision_outputs", "outcome")):
        block = _values_block(prototype, table)
        index = _columns(block).index(key)
        assert "'%s'" % predicate_id not in [r[index] for r in _rows(block)]


def test_bindings_declare_no_fallback(prototype):
    block = _values_block(prototype, "decision_rule_bindings")
    rows = _rows(block)
    classes = [r[_columns(block).index("rule_class")] for r in rows]
    assert classes == ["'GUARD'", "'GUARD'", "'MATCH'", "'MATCH'"]
    assert "'FALLBACK'" not in block


def test_authoritative_restoration_stays_authoritative(restore):
    for table in ("configuration_dimensions", "identity_rules",
                  "decision_outputs"):
        block = _values_block(restore, table)
        index = _columns(block).index("governance_basis")
        for row in _rows(block):
            assert row[index] == "'AUTHORITATIVE'"
    release = _values_block(restore, "ontology_release")
    columns = _columns(release)
    row = _rows(release)[0]
    assert row[columns.index("release_class")] == "'AUTHORITATIVE'"
    assert row[columns.index("validation_status")] == "NULL"


def test_authoritative_restoration_row_count_is_unchanged(restore):
    assert sum(_row_count(restore, t) for t in EXPECTED_ROW_COUNTS) == 135


# ---------------------------------------------------------------------------
# resolver boundary
# ---------------------------------------------------------------------------

from decisions.governance_resolver import (  # noqa: E402
    AmbiguousGovernance,
    ExecutionMode,
    IncoherentReleaseCandidate,
    NoEligibleGovernance,
    ReleaseCandidate,
    select_release,
)

AUTHORITATIVE = ReleaseCandidate("2026.10", "AUTHORITATIVE", "AUTHORITATIVE",
                                 "active")
PROTOTYPE_CANDIDATE = ReleaseCandidate(
    PROTOTYPE_VERSION, "PROTOTYPE", "PROTOTYPE_ASSUMPTION", "active",
    "TO_BE_VALIDATED_WITH_CLARIS")


def test_production_resolver_excludes_prototype():
    chosen = select_release([AUTHORITATIVE, PROTOTYPE_CANDIDATE])
    assert chosen is AUTHORITATIVE


def test_production_fails_closed_when_only_prototype_exists():
    with pytest.raises(NoEligibleGovernance):
        select_release([PROTOTYPE_CANDIDATE])


def test_prototype_requires_explicit_opt_in():
    # the default mode is PRODUCTION, so a caller that forgets cannot get it
    with pytest.raises(NoEligibleGovernance):
        select_release([PROTOTYPE_CANDIDATE])
    assert select_release([PROTOTYPE_CANDIDATE],
                          ExecutionMode.PROTOTYPE) is PROTOTYPE_CANDIDATE


def test_prototype_mode_never_selects_authoritative():
    with pytest.raises(NoEligibleGovernance):
        select_release([AUTHORITATIVE], ExecutionMode.PROTOTYPE)


def test_both_modes_fail_closed_on_an_empty_candidate_set():
    for mode in ExecutionMode:
        with pytest.raises(NoEligibleGovernance):
            select_release([], mode)


def test_ambiguous_governance_fails_closed():
    other = ReleaseCandidate("2026.11", "AUTHORITATIVE", "AUTHORITATIVE",
                             "active")
    with pytest.raises(AmbiguousGovernance):
        select_release([AUTHORITATIVE, other])


def test_an_inactive_artifact_is_not_a_candidate():
    inactive = ReleaseCandidate("2026.10", "AUTHORITATIVE", "AUTHORITATIVE",
                                "verified")
    with pytest.raises(NoEligibleGovernance):
        select_release([inactive])


def test_a_candidate_cannot_mix_class_and_basis():
    with pytest.raises(IncoherentReleaseCandidate):
        ReleaseCandidate("x", "AUTHORITATIVE", "PROTOTYPE_ASSUMPTION", "active")
    with pytest.raises(IncoherentReleaseCandidate):
        ReleaseCandidate("x", "PROTOTYPE", "AUTHORITATIVE", "active",
                         "TO_BE_VALIDATED_WITH_CLARIS")
    with pytest.raises(IncoherentReleaseCandidate):
        ReleaseCandidate("x", "PROTOTYPE", "PROTOTYPE_ASSUMPTION", "active")


# ---------------------------------------------------------------------------
# decision record carries the basis
# ---------------------------------------------------------------------------

def test_prototype_binding_carries_basis_and_real_version():
    from decisions.domains.claris.registration import (
        PROTOTYPE_ONTOLOGY_VERSION,
        prototype_governance_binding,
    )
    binding = prototype_governance_binding()
    assert binding.governance_basis == "PROTOTYPE_ASSUMPTION"
    assert binding.ontology_version == PROTOTYPE_ONTOLOGY_VERSION
    assert binding.ontology_version == PROTOTYPE_VERSION


def test_governance_basis_is_validated():
    from decisions.contracts import GovernanceBinding
    from decisions.errors import InvalidDecisionContext
    with pytest.raises(InvalidDecisionContext):
        GovernanceBinding(ontology_version="x", kb_version="y",
                          policy_version=None, governance_basis="CONFIRMED")


def test_default_basis_is_authoritative():
    from decisions.contracts import GovernanceBinding
    binding = GovernanceBinding(ontology_version="x", kb_version="y",
                                policy_version=None)
    assert binding.governance_basis == "AUTHORITATIVE"


def test_retired_sentinel_is_gone():
    import decisions.domains.claris.registration as registration
    assert not hasattr(registration, "NON_GOVERNED_PROTOTYPE")
