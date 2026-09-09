"""D.4G.2 -- runtime / persistence contract corrections."""

from __future__ import annotations

import io
import itertools
import os
import re

import pytest
from d4e_support import make_facts, make_fold, make_context, prototype_executor

from decisions.contracts import GovernanceBinding
from decisions.digest import DIGEST_SCHEME_VERSION
from decisions.domains.claris import (
    IDENTITY_PROPERTIES,
    PROTOTYPE_ONTOLOGY_VERSION,
    encode_identity_values,
    parse_canonical_identity,
    prototype_governance_binding,
    serialize_canonical_identity,
)
from decisions.outcome_validation import (
    OutcomeNotDeclared,
    OutcomeVocabulary,
    OutcomeVocabularyMismatch,
    validate_outcome,
    validate_result,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIGRATION = os.path.join(ROOT, "database", "migrations",
                         "D4G2_001_prototype_runtime_contract.sql")
PROTOTYPE_RELEASE = os.path.join(ROOT, "ontology_authoring", "restore",
                                 "003_prototype_2026_10_P1.sql")

PROTOTYPE_OUTCOMES = frozenset({
    "CREATE_PRODUCT", "CREATE_CONFIGURATION", "USE_EXISTING",
    "NEW_VERSION", "NO_BUSINESS_CHANGE", "CANNOT_DECIDE",
})
LEGACY_OUTCOMES = frozenset({
    "READY_FOR_LAUNCH", "MISSING_REQUIRED_DIMENSIONS",
    "CONTRADICTED_IDENTITY_EVIDENCE",
})

INITIAL = dict(product_exists=True, existing_configuration_count=0,
               exact_identity_match_exists=False)
EXACT = dict(product_exists=True, existing_configuration_count=1,
             exact_identity_match_exists=True)


def _read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def _sql_body(text):
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("--"))


def run(fold=None, facts=None):
    return prototype_executor().execute(
        make_context(fold=fold, facts=facts,
                     governance=prototype_governance_binding()))


@pytest.fixture(scope="module")
def migration():
    return _read(MIGRATION)


def prototype_vocabulary():
    return OutcomeVocabulary(
        ontology_version=PROTOTYPE_ONTOLOGY_VERSION,
        governance_basis="PROTOTYPE_ASSUMPTION",
        decision_type="IDENTITY_ASSESSMENT",
        outcomes=PROTOTYPE_OUTCOMES,
    )


def legacy_vocabulary():
    return OutcomeVocabulary(
        ontology_version="1.0",
        governance_basis="AUTHORITATIVE",
        decision_type="IDENTITY_ASSESSMENT",
        outcomes=LEGACY_OUTCOMES,
    )


# ======================================================================
# section 3 -- version-scoped outcome validation
# ======================================================================

@pytest.mark.parametrize("outcome", sorted(PROTOTYPE_OUTCOMES))
def test_prototype_outcomes_validate_against_the_prototype_vocabulary(outcome):
    validate_outcome(prototype_vocabulary(), "IDENTITY_ASSESSMENT", outcome,
                     PROTOTYPE_ONTOLOGY_VERSION, "PROTOTYPE_ASSUMPTION")


@pytest.mark.parametrize("outcome", sorted(PROTOTYPE_OUTCOMES))
def test_prototype_outcomes_are_rejected_by_the_legacy_vocabulary(outcome):
    """The contamination this correction exists to prevent, in both directions."""
    with pytest.raises((OutcomeNotDeclared, OutcomeVocabularyMismatch)):
        validate_outcome(legacy_vocabulary(), "IDENTITY_ASSESSMENT", outcome,
                         PROTOTYPE_ONTOLOGY_VERSION, "PROTOTYPE_ASSUMPTION")


@pytest.mark.parametrize("outcome", sorted(LEGACY_OUTCOMES))
def test_legacy_outcomes_are_rejected_by_the_prototype_vocabulary(outcome):
    with pytest.raises(OutcomeNotDeclared):
        validate_outcome(prototype_vocabulary(), "IDENTITY_ASSESSMENT", outcome,
                         PROTOTYPE_ONTOLOGY_VERSION, "PROTOTYPE_ASSUMPTION")


def test_a_matching_outcome_from_the_wrong_version_is_still_rejected():
    """CANNOT_DECIDE exists in both vocabularies; the version still governs."""
    with pytest.raises(OutcomeVocabularyMismatch):
        validate_outcome(prototype_vocabulary(), "IDENTITY_ASSESSMENT",
                         "CANNOT_DECIDE", "1.0", "PROTOTYPE_ASSUMPTION")


def test_a_matching_outcome_from_the_wrong_basis_is_rejected():
    with pytest.raises(OutcomeVocabularyMismatch):
        validate_outcome(prototype_vocabulary(), "IDENTITY_ASSESSMENT",
                         "CANNOT_DECIDE", PROTOTYPE_ONTOLOGY_VERSION,
                         "AUTHORITATIVE")


def test_a_vocabulary_does_not_govern_another_decision_type():
    with pytest.raises(OutcomeVocabularyMismatch):
        validate_outcome(prototype_vocabulary(), "LAUNCH_READINESS",
                         "CANNOT_DECIDE", PROTOTYPE_ONTOLOGY_VERSION,
                         "PROTOTYPE_ASSUMPTION")


def test_an_empty_vocabulary_is_a_defect_not_a_permissive_default():
    with pytest.raises(OutcomeVocabularyMismatch):
        OutcomeVocabulary(PROTOTYPE_ONTOLOGY_VERSION, "PROTOTYPE_ASSUMPTION",
                          "IDENTITY_ASSESSMENT", frozenset())


def test_a_real_prototype_result_validates_against_its_own_version():
    validate_result(prototype_vocabulary(), run(facts=make_facts(**INITIAL)))


def test_a_real_prototype_result_is_rejected_by_the_legacy_vocabulary():
    with pytest.raises((OutcomeNotDeclared, OutcomeVocabularyMismatch)):
        validate_result(legacy_vocabulary(), run(facts=make_facts(**INITIAL)))


def test_the_migrated_validator_never_reads_the_legacy_schema(migration):
    body = _sql_body(migration)
    function = body.split("is_valid_outcome_v2")[1].split("$$ LANGUAGE")[0]
    assert "ontology_authoring.decision_outputs" in function
    assert "ontology.decision_outputs" not in function.replace(
        "ontology_authoring.decision_outputs", "")
    assert "v_active_kb" not in function
    # every scoping argument is mandatory: a NULL fails closed
    assert "RETURN false" in function


# ======================================================================
# section 4 -- digest persistence
# ======================================================================

def test_the_digest_format_is_what_the_platform_computes():
    digest = run(facts=make_facts(**INITIAL)).input_digest
    assert re.fullmatch(r"v1:sha256:[0-9a-f]{64}", digest)
    assert len(digest) == 74
    assert digest.startswith(DIGEST_SCHEME_VERSION + ":")


def test_the_migration_widens_input_digest_beyond_the_actual_length(migration):
    body = _sql_body(migration)
    assert "ALTER COLUMN input_digest TYPE VARCHAR(128)" in body
    assert body.count("ALTER COLUMN input_digest TYPE VARCHAR(128)") == 2
    # no digest column is left at the old width (other columns may legitimately
    # be VARCHAR(32); executor_version is one)
    assert not re.search(r"input_digest[^\n]*VARCHAR\(32\)", body)
    assert 128 > 74


def test_the_migration_neither_truncates_nor_rehashes(migration):
    body = _sql_body(migration).lower()
    for banned in ("substring(", "left(", "md5(", "digest(input_digest"):
        assert banned not in body


def test_the_persisted_digest_check_accepts_the_real_digest(migration):
    pattern = re.search(r"input_digest ~ '(\^[^']+)'", migration).group(1)
    digest = run(facts=make_facts(**INITIAL)).input_digest
    assert re.fullmatch(pattern.replace("\\\\", "\\"), digest)


def test_the_digest_is_deterministic_for_identical_inputs():
    first = run(facts=make_facts(**INITIAL)).input_digest
    second = run(facts=make_facts(**INITIAL)).input_digest
    assert first == second


# ======================================================================
# section 5 -- decision lineage
# ======================================================================

@pytest.mark.parametrize("column", [
    "ontology_version", "governance_basis", "execution_mode", "fold_state_id",
    "matched_rule_id", "matched_rule_class", "matched_rule_kb_version",
    "executor_version", "digest_scheme_version",
])
def test_the_migration_persists_the_lineage_field(column, migration):
    assert re.search(r"ADD COLUMN IF NOT EXISTS %s\s" % column, migration)


def test_the_persisted_basis_cannot_misdescribe_the_execution_mode(migration):
    assert "ck_decision_basis_matches_mode" in migration
    block = migration.split("ck_decision_basis_matches_mode")[1].split(";")[0]
    assert "'AUTHORITATIVE'" in block and "'PRODUCTION'" in block
    assert "'PROTOTYPE_ASSUMPTION'" in block and "'PROTOTYPE'" in block


def test_a_business_identity_rule_can_never_be_the_matched_rule(migration):
    assert "ck_decision_matched_rule_not_ir" in migration
    block = migration.split("ck_decision_matched_rule_not_ir")[1].split(";")[0]
    assert "!~ '^IR-[0-9]{3}$'" in block


def test_the_runtime_never_emits_a_business_rule_id_as_matched():
    for facts in (make_facts(**INITIAL), make_facts(**EXACT)):
        result = run(facts=facts)
        assert result.matched_rule_id.startswith("IA-PRED-")
        assert not re.fullmatch(r"IR-\d{3}", result.matched_rule_id)


def test_the_result_answers_the_four_lineage_questions():
    result = run(facts=make_facts(**INITIAL))
    assert result.fold_state_id            # what state was evaluated
    assert result.matched_rule_id          # which predicate matched
    assert result.ontology_version         # which governance version
    assert result.outcome_code             # what was concluded
    assert result.governance_basis == "PROTOTYPE_ASSUMPTION"


def test_the_migration_creates_or_alters_no_type(migration):
    """Corrected at the D.4G.3 pre-deployment correction.

    An earlier draft added three values to an enum claris_decision_outcome.
    A live preflight established that no such type exists and that the outcome
    column is claris.decision.outcome_code character varying(64). The
    assumption came from database/ddl/001_core_schema.sql, which declares such
    a type; the deployed schema diverges from that file, and repository DDL is
    not evidence of the live contract.
    """
    body = _sql_body(migration)
    assert "claris_decision_outcome" not in body
    assert "ALTER TYPE" not in body
    assert "CREATE TYPE" not in body


def test_the_migration_does_not_touch_the_unrelated_payments_enum(migration):
    assert "payments.decision_outcome" not in _sql_body(migration)
    assert "payments." not in _sql_body(migration)


def test_the_outcome_is_persisted_verbatim_without_a_cast(migration):
    insert = migration.split("INSERT INTO claris.decision")[1].split(";")[0]
    assert "outcome_code, reason_code," in insert
    assert "recommendation" not in insert
    assert "::claris_decision_outcome" not in insert
    assert "p_outcome_code, p_reason_code," in insert


def test_outcome_legitimacy_is_governed_by_version_not_by_a_type(migration):
    """The invariant the enum could never have expressed.

    An enum is global and unversioned: it would have accepted a prototype
    outcome for a production decision and a legacy outcome for a prototype one.
    is_valid_outcome_v2 is scoped to the exact release that produced the
    decision, which is the property that actually matters.
    """
    function = _sql_body(migration).split("is_valid_outcome_v2")[1].split("$$ LANGUAGE")[0]
    for scope in ("p_domain", "p_ontology_version", "p_decision_type",
                  "p_outcome_code", "p_governance_basis"):
        assert scope in function
    assert "ontology_authoring.decision_outputs" in function


def test_policy_version_may_be_absent(migration):
    assert "ALTER COLUMN policy_version DROP NOT NULL" in migration
    assert run(facts=make_facts(**INITIAL)).policy_version is None


def test_version_columns_can_hold_the_prototype_release_name(migration):
    body = _sql_body(migration)
    assert "ALTER COLUMN kb_version TYPE VARCHAR(64)" in body
    assert len(PROTOTYPE_ONTOLOGY_VERSION) > 16   # VARCHAR(16) could not
    assert len(PROTOTYPE_ONTOLOGY_VERSION) <= 64


# ======================================================================
# section 6 -- execute_decision contract
# ======================================================================

@pytest.mark.parametrize("parameter", [
    "p_ontology_version", "p_governance_basis", "p_execution_mode",
    "p_decision_type", "p_subject_type", "p_subject_id", "p_outcome_code",
    "p_reason_code", "p_input_digest", "p_fold_state_id", "p_matched_rule_id",
    "p_kb_version", "p_policy_version", "p_horizon_as_of",
])
def test_execute_decision_v2_carries_the_runtime_contract(parameter, migration):
    signature = migration.split("execute_decision_v2(")[1].split(")\nRETURNS")[0]
    assert parameter in signature


def test_execute_decision_v2_validates_before_it_writes(migration):
    body = migration.split("execute_decision_v2(")[1]
    validation = body.index("is_valid_outcome_v2")
    insertion = body.index("INSERT INTO claris.decision")
    assert validation < insertion


def test_the_legacy_execution_path_is_not_dropped(migration):
    body = _sql_body(migration)
    assert "DROP FUNCTION" not in body
    assert "execute_decision_v2" in body   # additive, alongside v1


# ======================================================================
# section 9 -- identity serialization collision resistance
# ======================================================================

def test_the_documented_collision_pair_no_longer_collides():
    left = encode_identity_values(("A|B", "C", "1", "D"))
    right = encode_identity_values(("A", "B|C", "1", "D"))
    assert left != right
    assert parse_canonical_identity(left) == ("A|B", "C", "1", "D")
    assert parse_canonical_identity(right) == ("A", "B|C", "1", "D")


@pytest.mark.parametrize("values", list(itertools.product(
    ["", "|", "a|b", "1:2", "::", "x"], repeat=2)))
def test_no_two_distinct_tuples_share_an_encoding(values):
    left = encode_identity_values((values[0], values[1], "1", "z"))
    right = encode_identity_values((values[1], values[0], "1", "z"))
    if values[0] != values[1]:
        assert left != right
    assert parse_canonical_identity(left)[:2] == (values[0], values[1])


def test_encoding_is_deterministic_and_replayable():
    values = ("PROD-1", "NAMER", "36", "enterprise")
    assert encode_identity_values(values) == encode_identity_values(values)
    assert parse_canonical_identity(encode_identity_values(values)) == values


def test_encoding_alters_no_business_value():
    values = (" A ", "NaMeR", "36", "Enterprise|X")
    assert parse_canonical_identity(encode_identity_values(values)) == values


def test_the_tuple_membership_is_unchanged():
    assert IDENTITY_PROPERTIES == (
        "product_reference", "geography", "term_months", "customer_segment")
    assert len(parse_canonical_identity(
        serialize_canonical_identity(make_fold()))) == 4


# ======================================================================
# section 16 -- prototype execution matrix
# ======================================================================

def test_missing_required_input_is_guarded_by_ia_pred_001():
    from decisions import FoldState
    result = run(fold=make_fold(states={"geography": FoldState.UNREPORTED}),
                 facts=make_facts(**INITIAL))
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.matched_rule_id == "IA-PRED-001"


def test_contradicted_required_input_is_guarded_by_ia_pred_002():
    from decisions import FoldState
    result = run(fold=make_fold(states={"geography": FoldState.CONTRADICTED}),
                 facts=make_facts(**INITIAL))
    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.matched_rule_id == "IA-PRED-002"


def test_initial_configuration_is_ia_pred_003():
    result = run(facts=make_facts(**INITIAL))
    assert result.outcome_code == "CREATE_CONFIGURATION"
    assert result.matched_rule_id == "IA-PRED-003"


def test_exact_identity_match_is_ia_pred_004():
    result = run(facts=make_facts(**EXACT))
    assert result.outcome_code == "NO_BUSINESS_CHANGE"
    assert result.matched_rule_id == "IA-PRED-004"


def test_every_matrix_outcome_is_declared_by_the_prototype_vocabulary():
    for outcome in ("CREATE_PRODUCT", "CREATE_CONFIGURATION", "NEW_VERSION",
                    "NO_BUSINESS_CHANGE", "CANNOT_DECIDE"):
        validate_outcome(prototype_vocabulary(), "IDENTITY_ASSESSMENT",
                         outcome, PROTOTYPE_ONTOLOGY_VERSION,
                         "PROTOTYPE_ASSUMPTION")


def test_all_six_prototype_outcomes_are_declared_by_the_release():
    """Their validity comes from the governed vocabulary, not from a type."""
    release = _read(PROTOTYPE_RELEASE)
    block = re.search(
        r"INSERT INTO ontology_authoring\.decision_outputs.*?\);\n", release, re.S)
    assert block
    declared = set(re.findall(r"'IDENTITY_ASSESSMENT', '([A-Z_]+)'", block.group(0)))
    assert declared == PROTOTYPE_OUTCOMES
    assert "PROTOTYPE_ASSUMPTION" in block.group(0)
    assert "CONFIRMED" not in block.group(0)


def test_repackage_is_not_executable_in_the_prototype_release():
    """IR-006 is retained for provenance and cannot be reached by execution."""
    release = _read(PROTOTYPE_RELEASE)
    row = [l for l in release.splitlines() if "'IR-006'" in l]
    assert len(row) == 1
    assert "'UNPROPOSED'" in row[0]
    assert "'undefined'" in row[0]
    assert "'CREATE_CONFIGURATION'" not in row[0]


def test_reclassify_slp_is_absent_from_the_prototype_release():
    release = _read(PROTOTYPE_RELEASE)
    assert "'IR-007'" not in release
    assert "'reclassify'" not in release
    assert "'slp_code'" not in release


def test_the_executable_assumptions_are_exactly_the_permitted_six():
    release = _read(PROTOTYPE_RELEASE)
    executable = re.findall(
        r"\('retail', '2026\.10-prototype\.1', '(IR-\d{3})', \d+, 'PROTOTYPE', "
        r"'PROTOTYPE_ASSUMPTION', '[a-z_]+', (?:'[a-z_]+'|NULL), '([A-Z_]+)'",
        release)
    assert dict(executable) == {
        "IR-001": "CREATE_PRODUCT",
        "IR-002": "CREATE_CONFIGURATION",
        "IR-003": "CREATE_CONFIGURATION",
        "IR-004": "CREATE_CONFIGURATION",
        "IR-005": "NEW_VERSION",
        "IR-008": "NEW_VERSION",
        "IR-009": "NO_BUSINESS_CHANGE",
    }


# ======================================================================
# section 17 -- migration safety
# ======================================================================

def test_the_migration_is_additive_only(migration):
    body = _sql_body(migration)
    for banned in ("DROP TABLE", "TRUNCATE", "DELETE FROM", "DROP COLUMN",
                   "DROP TYPE", "DROP SCHEMA"):
        assert banned not in body


def test_the_migration_touches_no_business_data(migration):
    """No DML, ever.

    Narrowed at D.4G.3: a recreated view body legitimately *names*
    claris.configuration_version and claris.action_record, because that is what
    the view selects from. The property that matters is that no statement
    writes to a business table, not that the string never appears.
    """
    # function bodies are deferred code, not migration-time statements:
    # execute_decision_v2 legitimately contains INSERT INTO claris.decision,
    # which is what the function is FOR. Only what the migration itself
    # executes counts.
    body = re.sub(r"\$\$.*?\$\$", " <function body> ", _sql_body(migration),
                  flags=re.S)
    for verb in ("UPDATE", "DELETE FROM", "INSERT INTO", "TRUNCATE"):
        assert not re.search(r"\b%s\s+claris\." % verb, body), verb
    for schema in ("raw.", "state."):
        assert schema not in body


def test_the_migration_drops_and_recreates_exactly_the_blocking_views(migration):
    """Three views depend on kb_version / policy_version and must round-trip."""
    body = _sql_body(migration)
    dropped = re.findall(r"^DROP VIEW (\S+);", body, re.M)
    created = re.findall(r"^CREATE VIEW (\S+) AS", body, re.M)
    expected = {"claris.v_workbench_full_workflow",
                "claris.v_workbench_stage6_decision",
                "claris.v_workbench_stage5_policy"}
    assert set(dropped) == expected
    assert set(created) == expected
    # recreation is the exact reverse of the drop, so dependents come back last
    assert created == list(reversed(dropped))


def test_the_migration_never_uses_cascade(migration):
    """CASCADE would silently destroy an object nobody knew depended on these."""
    assert "CASCADE" not in _sql_body(migration).upper()


def test_the_migration_restores_every_dropped_view_grant(migration):
    body = _sql_body(migration)
    for view in ("v_workbench_full_workflow", "v_workbench_stage6_decision",
                 "v_workbench_stage5_policy"):
        assert re.search(
            r"GRANT SELECT ON claris\.%s\s+TO claris_ingestion;" % view, body)


@pytest.mark.parametrize("view", [
    "v_workbench_stage5_policy", "v_workbench_stage6_decision",
    "v_workbench_full_workflow"])
def test_the_recreated_body_matches_the_recovered_source(view, migration):
    """The migration and the recovered source cannot drift apart."""
    source = _read(os.path.join(ROOT, "database", "views", "claris",
                                "%s.sql" % view))
    recovered = source.split("CREATE OR REPLACE VIEW claris.%s AS\n" % view)[1]
    recovered = recovered.split("\n\nGRANT")[0]
    in_migration = migration.split("CREATE VIEW claris.%s AS\n" % view)[1]
    in_migration = in_migration.split("\n\n")[0]
    assert in_migration.strip() == recovered.strip()


def test_the_migration_only_targets_the_decision_persistence_path(migration):
    body = _sql_body(migration)
    targets = set(re.findall(r"ALTER TABLE (\S+)", body))
    assert targets == {"claris.decision", "claris.configuration_state"}


# ======================================================================
# governance basis propagation
# ======================================================================

def test_governance_basis_and_version_propagate_into_the_result():
    result = run(facts=make_facts(**INITIAL))
    assert result.governance_basis == "PROTOTYPE_ASSUMPTION"
    assert result.ontology_version == PROTOTYPE_ONTOLOGY_VERSION


def test_an_authoritative_binding_produces_an_authoritative_result():
    binding = GovernanceBinding(
        ontology_version="2026.10", kb_version="1.0.1", policy_version=None,
        rule_set=prototype_governance_binding().rule_set,
        required_properties=IDENTITY_PROPERTIES)
    result = prototype_executor().execute(
        make_context(facts=make_facts(**INITIAL), governance=binding))
    assert result.governance_basis == "AUTHORITATIVE"
    assert result.ontology_version == "2026.10"
