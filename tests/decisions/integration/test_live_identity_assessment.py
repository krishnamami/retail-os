"""D.4E sections 21, 22, 23, 29 -- live READ-ONLY IDENTITY_ASSESSMENT checks.

EVERY result produced here is labelled:

    PROTOTYPE DOMAIN EVALUATION ONLY

It is NOT a governed decision. IR-010..IR-013 are proposed semantic candidates
in claris_kb.identity_rules; there are zero executable IDENTITY_ASSESSMENT rows
in claris_kb.decision_rules and this suite adds none. Nothing is written to
claris.decision. No Product, Configuration or ConfigurationVersion is created.

Every statement is a read, on a session pinned READ ONLY.
"""

from __future__ import annotations

import pytest
from live_support import (
    NON_EXECUTABLE_DECISION_TYPE,
    PROPOSED_IDENTITY_RULES,
    SUBJECT_TYPE,
    kb_status_fingerprint,
    row_counts,
)

from decisions import DecisionRequest, FoldState
from decisions.domains.claris import (
    DECISION_TYPE,
    EXACT_IDENTITY_MATCH_EXISTS,
    EXISTING_CONFIGURATION_COUNT,
    IDENTITY_PROPERTIES,
    PROTOTYPE_ONTOLOGY_VERSION,
    PRODUCT_EXISTS,
    PROTOTYPE_LABEL,
    SEMANTIC_KB_VERSION,
    CanonicalIdentityLookup,
    ClarisIdentityFactProvider,
    LookupSemantics,
    build_prototype_registry,
    missing_identity_properties,
    prototype_governance_binding,
    parse_canonical_identity,
    try_serialize_canonical_identity,
)
from decisions import GovernedDecisionExecutor
from decisions.contracts import DecisionContext

EXPECTED_SUBJECT_HINT = "CONFIG-REQ-2026-007"


# ======================================================================
# section 29 -- before/after mutation witness for THIS suite
# ======================================================================

@pytest.fixture(scope="module")
def d4e_before_counts(db):
    counts = row_counts(db)
    print("\n  D.4E BEFORE row counts:")
    for table, n in counts.items():
        print(f"    {table}: {n}")
    return counts


@pytest.fixture(scope="module")
def d4e_before_kb_status(db):
    return kb_status_fingerprint(db)


# ======================================================================
# fixtures: discover the subjects deterministically, never hard-coded
# ======================================================================

@pytest.fixture(scope="module")
def unreported_subject(db, fold_loader, identity_subjects):
    """The subject with at least one UNREPORTED required identity property."""
    for row in identity_subjects["with_unreported"]:
        snapshot = fold_loader.load(
            SUBJECT_TYPE, row["subject_id"], row["decision_horizon"]
        ).snapshot
        if any(
            snapshot.state_of(name) is FoldState.UNREPORTED
            for name in IDENTITY_PROPERTIES
        ):
            return row, snapshot
    pytest.skip("no subject with an UNREPORTED required identity property")


@pytest.fixture(scope="module")
def complete_subject(fold_loader, identity_subjects):
    row = identity_subjects["complete"][0]
    return row, fold_loader.load(
        SUBJECT_TYPE, row["subject_id"], row["decision_horizon"]
    ).snapshot


@pytest.fixture(scope="module")
def canonical_lookup(db):
    return CanonicalIdentityLookup(db)


def _prototype_context(snapshot, facts):
    return DecisionContext(
        request=DecisionRequest(
            decision_type=DECISION_TYPE,
            subject_type=snapshot.subject_type,
            subject_id=snapshot.subject_id,
            decision_horizon=snapshot.decision_horizon,
            requested_by="d4e-integration",
        ),
        fold=snapshot,
        governance=prototype_governance_binding(),
        facts=facts,
    )


# ======================================================================
# section 21 -- live Fold IA-PRED-001 (semantic candidate IR-011)
# ======================================================================

def test_live_customer_segment_is_still_unreported(unreported_subject, d4e_before_counts):
    row, snapshot = unreported_subject
    unreported = [
        name for name in IDENTITY_PROPERTIES
        if snapshot.state_of(name) is FoldState.UNREPORTED
    ]
    print(f"\n  subject: {row['subject_id']} (expected hint {EXPECTED_SUBJECT_HINT})")
    print(f"  UNREPORTED required identity properties: {unreported}")
    for name in IDENTITY_PROPERTIES:
        prop = snapshot.property_named(name)
        state = prop.fold_state.value if prop else "ABSENT"
        value = prop.resolved_value if prop else None
        print(f"    {name}: {state} = {value!r}")
    assert unreported, "expected at least one UNREPORTED required identity property"


def test_live_ir_011_prototype_evaluation(unreported_subject, canonical_lookup):
    """PROTOTYPE DOMAIN EVALUATION ONLY -- not a governed persisted decision."""
    row, snapshot = unreported_subject

    facts = ClarisIdentityFactProvider(canonical_lookup).facts_for(None, snapshot)
    result = GovernedDecisionExecutor(build_prototype_registry()).execute(
        _prototype_context(snapshot, facts)
    )

    print(f"\n  === {PROTOTYPE_LABEL} ===")
    print(f"  subject          : {row['subject_id']}")
    print(f"  decision_type    : {result.decision_type}")
    print(f"  outcome_code     : {result.outcome_code}")
    print(f"  reason_code      : {result.reason_code}")
    print(f"  matched_rule_id  : {result.matched_rule_id} ({result.matched_rule_class})")
    print(f"  missing_evidence : {result.missing_evidence}")
    print(f"  blocking_evidence: {result.blocking_evidence}")
    print(f"  ontology_version : {result.ontology_version}")
    print(f"  policy_version   : {result.policy_version!r}")
    print(f"  input_digest     : {result.input_digest}")
    print(f"  fold_state_id    : {result.fold_state_id}")
    print(f"  domain_facts_used: {dict(result.domain_facts_used)}")

    assert result.outcome_code == "CANNOT_DECIDE"
    assert result.reason_code == "MISSING_REQUIRED_INPUT"
    # D.4G.2: executable predicates are IA-PRED-nnn; IR-nnn remains the id
    # of the proposed semantic candidate in claris_kb.identity_rules.
    assert result.matched_rule_id == "IA-PRED-001"
    assert result.matched_rule_class == "GUARD"
    assert result.missing_evidence
    assert set(result.missing_evidence) == set(missing_identity_properties(snapshot))

    # self-identifying as a prototype, never as a governed decision
    assert result.ontology_version == PROTOTYPE_ONTOLOGY_VERSION
    assert result.governance_basis == "PROTOTYPE_ASSUMPTION"
    assert result.policy_version is None


def test_live_identity_does_not_serialize_for_the_unreported_subject(unreported_subject):
    _, snapshot = unreported_subject
    assert try_serialize_canonical_identity(snapshot) is None


def test_live_complete_subject_serializes_a_canonical_identity(complete_subject):
    row, snapshot = complete_subject
    identity = try_serialize_canonical_identity(snapshot)
    print(f"\n  {row['subject_id']} canonical_identity: {identity!r}")
    assert identity is not None
    # FOUR delimiters, not three: the D.4G.2 length-prefixed encoding carries a
    # version marker ahead of the four fields -- v2|8:PROD-001|5:NAMER|2:36|...
    # This assertion counted the bare joins of the v1 format and was missed when
    # the encoding changed.
    assert identity.count("|") == len(IDENTITY_PROPERTIES)
    assert identity.startswith("v2|")
    # the point of the encoding is that it is injective, so assert the property
    # rather than its shape: the exact field values must come back out
    recovered = parse_canonical_identity(identity)
    assert len(recovered) == len(IDENTITY_PROPERTIES)
    assert recovered[0] == snapshot.property_named("product_reference").resolved_value
    assert not identity.startswith("v1:")  # identity is not a digest


# ======================================================================
# section 22 -- live canonical lookup
# ======================================================================

def test_live_canonical_lookup(canonical_lookup, complete_subject, db):
    """Reported from the actual database. Nothing here is hard-coded."""
    row, snapshot = complete_subject
    product_reference = snapshot.property_named("product_reference").resolved_value
    identity = try_serialize_canonical_identity(snapshot)

    result = canonical_lookup.lookup(product_reference, identity)
    facts = result.to_domain_facts()

    print("\n  === LIVE CANONICAL LOOKUP (CURRENT-STATE) ===")
    print(f"  subject                     : {row['subject_id']}")
    print(f"  product_reference           : {product_reference!r}")
    print(f"  canonical_identity          : {identity!r}")
    print(f"  product_exists              : {result.product_exists}")
    print(f"  existing_configuration_count: {result.existing_configuration_count}")
    print(f"  exact_identity_match_exists : {result.exact_identity_match_exists}"
          "   (TRUE only for a currently ACTIVE, non-archived configuration)")
    print(f"  eligible_identity_matches   : {result.eligible_identity_matches}")
    print(f"  ineligible_identity_matches : {result.ineligible_identity_matches}")
    print(f"  semantics                   : {result.semantics.value}")
    print(f"  replay_safety               : {result.replay_safety}")

    assert set(facts.facts) == {
        PRODUCT_EXISTS, EXISTING_CONFIGURATION_COUNT, EXACT_IDENTITY_MATCH_EXISTS
    }
    assert isinstance(result.product_exists, bool)
    assert isinstance(result.existing_configuration_count, int)
    assert result.semantics is LookupSemantics.CURRENT_STATE


def test_live_canonical_tables_are_reported_not_assumed(db):
    counts = {
        table: db.scalar(f"SELECT count(*) FROM {table}")
        for table in ("claris.product", "claris.configuration",
                      "claris.configuration_version")
    }
    print(f"\n  live canonical row counts: {counts}")
    for table, n in counts.items():
        assert n >= 0


def test_live_configuration_eligibility_is_determinable(canonical_lookup):
    """D.4E correction, section 5 -- the STOP condition, re-checked live.

    exact_identity_match_exists is TRUE only for a CURRENTLY ELIGIBLE
    configuration. That requires the deployed schema to define an unambiguous
    active/archived lifecycle. If it does not, this test fails and D.4E is:

        ARCHIVED IDENTITY MATCH SEMANTICS BLOCKED -- ACTIVE CONFIGURATION
        ELIGIBILITY CANNOT BE DETERMINED
    """
    capability = canonical_lookup.eligibility_capability()
    print("\n  === CONFIGURATION ELIGIBILITY CAPABILITY (measured) ===")
    print(f"    columns                 : {capability['columns']}")
    for name, definition in capability["check_constraints"].items():
        print(f"    constraint {name}: {definition}")
    print(f"    governed vocabulary     : {capability['governed_vocabulary']}")
    print(f"    eligibility_determinable: {capability['eligibility_determinable']}")
    assert capability["has_status"], (
        "ARCHIVED IDENTITY MATCH SEMANTICS BLOCKED -- ACTIVE CONFIGURATION "
        "ELIGIBILITY CANNOT BE DETERMINED (no status column)"
    )
    assert capability["has_archived_at"], (
        "ARCHIVED IDENTITY MATCH SEMANTICS BLOCKED -- ACTIVE CONFIGURATION "
        "ELIGIBILITY CANNOT BE DETERMINED (no archived_at column)"
    )
    assert capability["vocabulary_closed_to_active_archived"], (
        "ARCHIVED IDENTITY MATCH SEMANTICS BLOCKED -- ACTIVE CONFIGURATION "
        "ELIGIBILITY CANNOT BE DETERMINED (status vocabulary is not closed to "
        "active/archived)"
    )


def test_live_identity_match_eligibility_breakdown(canonical_lookup, complete_subject):
    """Report the eligible / ineligible split behind exact_identity_match_exists."""
    _, snapshot = complete_subject
    identity = try_serialize_canonical_identity(snapshot)
    counts = canonical_lookup.classify_identity_matches(identity)
    print("\n  === EXACT IDENTITY MATCH CLASSIFICATION ===")
    print(f"    canonical_identity   : {identity!r}")
    print(f"    eligible (active)    : {counts['eligible_matches']}")
    print(f"    ineligible (archived): {counts['ineligible_matches']}")
    print(f"    unclassifiable       : {counts['unclassifiable_matches']}")
    print(f"    total                : {counts['total_matches']}")
    assert counts["unclassifiable_matches"] == 0, (
        "configuration rows carry a status outside the governed vocabulary; "
        "eligibility cannot be determined for them"
    )


def test_live_as_of_capability_is_measured_from_the_real_schema(canonical_lookup):
    """Carried-open item V-4, answered against the deployed schema."""
    capability = canonical_lookup.temporal_capability()
    print("\n  === V-4 AS-OF CAPABILITY (measured) ===")
    for table, columns in capability["columns"].items():
        print(f"    claris.{table}: {list(columns)}")
    print(f"    product_supports_as_of      : {capability['product_supports_as_of']}")
    print(f"    configuration_supports_as_of: {capability['configuration_supports_as_of']}")
    print(f"    as_of_supported             : {capability['as_of_supported']}")
    print(f"    lookup semantics            : {capability['semantics']}")
    print(f"    replay safety               : {capability['replay_safety']}")
    assert capability["semantics"] == "CURRENT_STATE"
    assert capability["replay_safety"] == "PARTIAL / NOT YET REPLAY-SAFE"


# ======================================================================
# section 23 -- IR-010 / IR-013 live limitation, reported honestly
# ======================================================================

def test_live_ir_013_demonstration_availability(canonical_lookup, complete_subject, db):
    _, snapshot = complete_subject
    product_reference = snapshot.property_named("product_reference").resolved_value
    exists = canonical_lookup.product_exists(product_reference)
    count = canonical_lookup.configuration_count(product_reference)
    if not exists:
        print(
            f"\n  IR-013 live demonstration: NOT AVAILABLE -- PRODUCT DOES NOT EXIST "
            f"({product_reference!r} absent from claris.product)"
        )
    elif count != 0:
        print(f"\n  IR-013 live demonstration: NOT AVAILABLE -- {count} configurations exist")
    else:
        print("\n  IR-013 live demonstration: AVAILABLE")
    assert isinstance(exists, bool)


def test_live_ir_010_demonstration_availability(canonical_lookup, complete_subject):
    _, snapshot = complete_subject
    identity = try_serialize_canonical_identity(snapshot)
    match = canonical_lookup.exact_identity_match_exists(identity)
    counts = canonical_lookup.classify_identity_matches(identity)
    if not match:
        detail = (
            f"no configuration carries {identity!r}"
            if counts["total_matches"] == 0
            else f"{counts['ineligible_matches']} archived match(es) only -- "
                 "an archived configuration is not an exact identity match"
        )
        print(
            "\n  IR-010 live demonstration: NOT AVAILABLE -- NO ACTIVE CANONICAL "
            f"MATCH DATA ({detail})"
        )
    else:
        print("\n  IR-010 live demonstration: AVAILABLE")
    assert isinstance(match, bool)


def test_no_product_or_configuration_was_seeded(db, d4e_before_counts):
    for table in ("claris.product", "claris.configuration",
                  "claris.configuration_version"):
        assert db.scalar(f"SELECT count(*) FROM {table}") == d4e_before_counts[table]


# ======================================================================
# section 29 / 11 -- the governed safety boundary is intact
# ======================================================================

def test_zero_executable_identity_assessment_rules_exist(db):
    for relation in ("claris_kb.decision_rules", "claris_kb.v_active_decision_rules"):
        n = db.scalar(
            f"SELECT count(*) FROM {relation} WHERE decision_type = %s",
            (NON_EXECUTABLE_DECISION_TYPE,),
        )
        print(f"\n  {relation} IDENTITY_ASSESSMENT rows: {n}")
        assert n == 0, "D.4E must not create executable IDENTITY_ASSESSMENT rules"


def test_the_kb_resolver_still_refuses_identity_assessment(kb_resolver):
    """The resolver must not promote a proposed candidate into an executable rule."""
    from decisions.adapters.errors import NoExecutableRuleSet

    with pytest.raises(NoExecutableRuleSet):
        kb_resolver.resolve_rules(NON_EXECUTABLE_DECISION_TYPE)


def test_ir_rules_remain_proposed_semantic_candidates(db):
    rows = db.query(
        """
        SELECT rule_id, kb_version, status
        FROM claris_kb.identity_rules
        WHERE rule_id = ANY(%s)
        ORDER BY rule_id
        """,
        (list(PROPOSED_IDENTITY_RULES),),
    )
    print("\n  claris_kb.identity_rules:")
    for row in rows:
        print(f"    {row['rule_id']} kb={row['kb_version']} status={row['status']}")
    assert rows, "IR-010..IR-013 should still exist as semantic candidates"
    for row in rows:
        assert row["status"] == "proposed", f"{row['rule_id']} is no longer proposed"


def test_the_semantic_kb_version_the_domain_pack_uses_matches_the_kb(db):
    versions = {
        row["kb_version"]
        for row in db.query(
            "SELECT DISTINCT kb_version FROM claris_kb.identity_rules "
            "WHERE rule_id = ANY(%s)",
            (list(PROPOSED_IDENTITY_RULES),),
        )
    }
    print(f"\n  identity_rules kb_versions: {sorted(versions)}")
    assert SEMANTIC_KB_VERSION in versions


def test_every_decision_rests_on_prototype_governance(db):
    """D.4E forbade writing a decision at all, and this asserted zero rows.

    The vertical slice writes decisions deliberately, so counting rows no longer
    tests anything true. What it was PROTECTING still holds and is asserted
    instead: no decision may claim production governance, and the database's own
    ck_decision_basis_matches_mode keeps basis and mode in agreement.
    """
    rows = db.query("""
        SELECT governance_basis, execution_mode, ontology_version, count(*) AS n
        FROM claris.decision GROUP BY 1,2,3 ORDER BY 1,2,3""")
    print("\n  decisions by governance:")
    for row in rows:
        print(f"    {row['governance_basis']} / {row['execution_mode']} / "
              f"{row['ontology_version']}: {row['n']}")
    assert all(row["governance_basis"] == "PROTOTYPE_ASSUMPTION" for row in rows)
    assert all(row["execution_mode"] == "PROTOTYPE" for row in rows)
    assert db.scalar("""
        SELECT count(*) FROM claris.decision
        WHERE governance_basis = 'AUTHORITATIVE'""") == 0


def test_d4e_created_no_rows_anywhere(db, d4e_before_counts):
    after = row_counts(db)
    print("\n  D.4E AFTER row counts:")
    for table, n in after.items():
        print(f"    {table}: {n}  (before {d4e_before_counts[table]})")
    assert after == d4e_before_counts, "D.4E must not create, update or delete any row"


def test_d4e_changed_no_kb_status(db, d4e_before_kb_status):
    assert kb_status_fingerprint(db) == d4e_before_kb_status


def test_the_session_is_still_read_only(db):
    assert db.session_is_read_only()
