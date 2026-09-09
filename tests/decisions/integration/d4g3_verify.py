r"""STEP 5G.6 PHASE D.4G.3 -- DEPLOYMENT VERIFICATION (READ ONLY).

The acceptance test for the deployment. It lives on its own so it can be run
after a DBA has applied the four files by hand: d4g3_deploy.py refuses once
ontology_authoring exists, which would otherwise leave a manual deployment
with nothing to check it.

    .\\venv\\Scripts\\python.exe tests\\decisions\\integration\\d4g3_verify.py

Reads only. Calls claris.is_valid_outcome_v2, which is STABLE and writes
nothing. Executes no decision and materializes nothing.

Exit codes
    0  every check passed
    4  at least one check failed (each is named)
"""

from __future__ import annotations

import os
import sys
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _path in (_REPO_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from decisions.adapters.connection import read_only_connection  # noqa: E402

EXPECTED_TABLES = {
    "ontology_release", "ontology_notes", "enums", "enum_values", "actors",
    "configuration_dimensions", "identity_rules", "decisions",
    "decision_outputs", "decision_dependencies", "projection_rules",
    "evidence_reference", "decision_reason_codes", "decision_rule_bindings",
}

AUTHORITATIVE_COUNTS = {
    "ontology_release": 1, "actors": 7, "ontology_notes": 7, "enums": 11,
    "enum_values": 46, "configuration_dimensions": 8, "identity_rules": 9,
    "decisions": 5, "decision_outputs": 27, "decision_reason_codes": 6,
    "decision_dependencies": 4, "projection_rules": 4,
}
PROTOTYPE_COUNTS = {
    "ontology_release": 1, "actors": 7, "decisions": 1, "decision_outputs": 6,
    "configuration_dimensions": 7, "identity_rules": 8,
    "decision_rule_bindings": 4,
}

WITNESS_TABLES = (
    "claris.product", "claris.configuration", "claris.configuration_version",
    "claris.decision", "claris.action_record",
    "claris_kb.decision_rules", "claris_kb.identity_rules",
    "ontology.decisions", "ontology.decision_outputs",
)
UPSTREAM_TABLES = ("raw.material", "raw.material_change", "claris.evidence",
                   "claris.assertion", "claris.configuration_state")

FAILURES: list = []


def head(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(f"{label}: got {actual!r}, expected {expected!r}")
    return ok


def show(db, label, sql, params=None, width=300):
    print(f"\n-- {label} " + "-" * max(0, 56 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:200]}")
        return []
    if not rows:
        print("   (no rows)")
    for row in rows:
        text = " | ".join(
            f"{k}={'NULL' if v is None else str(v)[:width]}" for k, v in row.items())
        print("   " + text.encode("ascii", "replace").decode("ascii"))
    return rows


#: Schemas whose contents must be byte-for-byte unchanged by this deployment.
#: ontology_authoring is deliberately excluded: it is what the deployment
#: creates.
WITNESS_SCHEMAS = ("claris", "claris_kb", "ontology", "raw", "state",
                   "payments", "audit", "runtime", "public")


def schema_census(db):
    """Exact row counts for EVERY table in the witness schemas.

    A hand-picked witness list is only as good as the guesses in it: the live
    preflight showed three of the names carried from repository DDL
    (raw.material, raw.material_change, claris.assertion) do not exist, so a
    list-based witness was quietly proving less than it claimed. Enumerating
    the catalogue cannot miss a table nobody thought to name.
    """
    tables = db.query("""
        SELECT schemaname AS schema, tablename AS table
        FROM pg_tables WHERE schemaname = ANY(%s)
        ORDER BY 1, 2
    """, (list(WITNESS_SCHEMAS),))
    census = {}
    for row in tables:
        qualified = f'{row["schema"]}.{row["table"]}'
        census[qualified] = db.scalar(
            f'SELECT count(*) FROM "{row["schema"]}"."{row["table"]}"')
    return census



def run_verification(db) -> list:
    """Sections 5-12. Returns the list of failures; empty when clean."""
    FAILURES.clear()
    head("5. VERIFY -- 14 AUTHORING TABLES")
    tables = {r["tablename"] for r in db.query(
        "SELECT tablename FROM pg_tables WHERE schemaname='ontology_authoring'")}
    check("authoring table count", len(tables), 14)
    check("authoring table set", sorted(tables), sorted(EXPECTED_TABLES))

    show(db, "structural protections present", """
        SELECT count(*) FILTER (WHERE column_name='release_class')     AS release_class,
               count(*) FILTER (WHERE column_name='governance_basis')  AS governance_basis,
               count(*) FILTER (WHERE column_name='validation_status') AS validation_status
        FROM information_schema.columns WHERE table_schema='ontology_authoring'
    """)
    constraints = {r["conname"] for r in db.query("""
        SELECT c.conname FROM pg_constraint c
        JOIN pg_namespace n ON n.oid=c.connamespace
        WHERE n.nspname='ontology_authoring'
    """)}
    for name in ("ck_ontology_release_validation_status",
                 "ck_ontology_release_parent_class",
                 "fk_ontology_release_parent_is_authoritative",
                 "ck_configuration_dimensions_assumption_is_never_confirmed",
                 "ck_identity_rules_assumption_is_never_confirmed",
                 "ck_identity_rules_ir_namespace",
                 "ck_decision_rule_bindings_not_ir_namespace",
                 "ck_configuration_dimensions_confirmed_is_signed"):
        check(f"constraint {name}", name in constraints, True)

    head("6. VERIFY -- RUNTIME PERSISTENCE CONTRACT")
    show(db, "column widths after migration", """
        SELECT table_name, column_name, character_maximum_length AS width,
               is_nullable
        FROM information_schema.columns
        WHERE table_schema='claris' AND table_name IN ('decision','configuration_state')
          AND column_name IN ('input_digest','kb_version','policy_version')
        ORDER BY 1,2
    """)
    widths = {(r["table_name"], r["column_name"]): r["width"] for r in db.query("""
        SELECT table_name, column_name, character_maximum_length
               AS width FROM information_schema.columns
        WHERE table_schema='claris' AND table_name IN ('decision','configuration_state')
          AND column_name IN ('input_digest','kb_version','policy_version')""")}
    check("decision.input_digest width >= 74",
          (widths.get(("decision", "input_digest")) or 0) >= 74, True)
    check("configuration_state.input_digest width >= 74",
          (widths.get(("configuration_state", "input_digest")) or 0) >= 74, True)
    check("decision.kb_version holds '2026.10-prototype.1'",
          (widths.get(("decision", "kb_version")) or 0) >= 19, True)

    lineage = {r["column_name"] for r in db.query("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='claris' AND table_name='decision'""")}
    for column in ("ontology_version", "governance_basis", "execution_mode",
                   "fold_state_id", "matched_rule_id", "matched_rule_class",
                   "matched_rule_kb_version", "executor_version",
                   "digest_scheme_version"):
        check(f"claris.decision.{column}", column in lineage, True)

    show(db, "outcome persistence column (live contract)", """
        SELECT data_type, character_maximum_length AS width, is_nullable
        FROM information_schema.columns
        WHERE table_schema='claris' AND table_name='decision'
          AND column_name='outcome_code'
    """)
    outcome_column = db.query("""
        SELECT data_type, character_maximum_length AS width
        FROM information_schema.columns
        WHERE table_schema='claris' AND table_name='decision'
          AND column_name='outcome_code'""")
    check("claris.decision.outcome_code exists", bool(outcome_column), True)
    if outcome_column:
        check("outcome_code type", outcome_column[0]["data_type"],
              "character varying")
        check("outcome_code width >= 64",
              (outcome_column[0]["width"] or 0) >= 64, True)
    check("no claris_decision_outcome type was created", db.scalar(
        "SELECT count(*) FROM pg_type WHERE typname='claris_decision_outcome'"), 0)
    # the unrelated enum one schema away, which an earlier draft of the
    # migration was in danger of reaching for. It must still be there, and it
    # must still have the labels it always had.
    check("payments.decision_outcome still exists", db.scalar("""
        SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
        WHERE n.nspname='payments' AND t.typname='decision_outcome'"""), 1)
    check("no prototype outcome leaked into payments.decision_outcome", db.scalar("""
        SELECT count(*) FROM pg_enum e
        JOIN pg_type t ON t.oid=e.enumtypid
        JOIN pg_namespace n ON n.oid=t.typnamespace
        WHERE n.nspname='payments' AND t.typname='decision_outcome'
          AND e.enumlabel IN ('CREATE_PRODUCT','CREATE_CONFIGURATION',
                              'NO_BUSINESS_CHANGE')"""), 0)

    # D.4G.3: section 2 of the migration drops and recreates three views to
    # get past the kb_version / policy_version type change. They must all be
    # back, selectable, and still readable by the runtime login.
    for view in ("v_workbench_stage5_policy", "v_workbench_stage6_decision",
                 "v_workbench_full_workflow"):
        check(f"view claris.{view} restored", db.scalar(
            "SELECT to_regclass(%s) IS NOT NULL", (f"claris.{view}",)), True)
        try:
            db.query(f"SELECT * FROM claris.{view} LIMIT 0")
            selectable = True
        except Exception:  # noqa: BLE001
            selectable = False
        check(f"view claris.{view} is selectable", selectable, True)
        check(f"view claris.{view} still granted to claris_ingestion", db.scalar("""
            SELECT count(*) FROM information_schema.role_table_grants
            WHERE table_schema='claris' AND table_name=%s
              AND grantee='claris_ingestion' AND privilege_type='SELECT'""",
            (view,)), 1)
    check("the six untouched dependent views are still present", db.scalar("""
        SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='claris' AND c.relkind='v' AND c.relname IN
          ('action_approval_status','decision_summary',
           'v_workbench_stage3_established_facts','v_workbench_stage4_problems',
           'v_workbench_stage7_action','v_workbench_stage9_execution')"""), 6)

    functions = {r["proname"] for r in db.query("""
        SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='claris' AND p.proname IN
          ('is_valid_outcome','execute_decision','is_valid_outcome_v2',
           'execute_decision_v2')""")}
    for name in ("is_valid_outcome_v2", "execute_decision_v2"):
        check(f"function {name} deployed", name in functions, True)
    for name in ("is_valid_outcome", "execute_decision"):
        check(f"v1 function {name} preserved", name in functions, True)

    head("7. VERIFY -- AUTHORITATIVE RESTORATION")
    total = 0
    for table, expected in sorted(AUTHORITATIVE_COUNTS.items()):
        actual = db.scalar(
            f"SELECT count(*) FROM ontology_authoring.{table} "
            "WHERE ontology_version='2026.10'")
        total += actual
        check(f"2026.10 {table}", actual, expected)
    check("authoritative total rows", total, 135)
    check("evidence_reference is empty",
          db.scalar("SELECT count(*) FROM ontology_authoring.evidence_reference"), 0)

    show(db, "authoritative release metadata", """
        SELECT ontology_version, release_class, validation_status, status,
               parent_ontology_version
        FROM ontology_authoring.ontology_release WHERE ontology_version='2026.10'
    """)
    check("all 8 dimensions UNKNOWN", db.scalar("""
        SELECT count(*) FROM ontology_authoring.configuration_dimensions
        WHERE ontology_version='2026.10' AND identity_affecting='UNKNOWN'"""), 8)
    check("no dimension confirmed", db.scalar("""
        SELECT count(*) FROM ontology_authoring.configuration_dimensions
        WHERE ontology_version='2026.10' AND identity_affecting<>'UNKNOWN'"""), 0)
    check("all 9 rules unconfirmed", db.scalar("""
        SELECT count(*) FROM ontology_authoring.identity_rules
        WHERE ontology_version='2026.10' AND identity_effect IS NULL
          AND governance_state='PROPOSED'"""), 9)
    check("Q-001..Q-007 all OPEN", db.scalar("""
        SELECT count(*) FROM ontology_authoring.ontology_notes
        WHERE ontology_version='2026.10' AND status='OPEN'"""), 7)
    check("no fabricated signature", db.scalar("""
        SELECT count(*) FROM ontology_authoring.configuration_dimensions
        WHERE ontology_version='2026.10'
          AND (confirmed_by IS NOT NULL OR confirmed_on IS NOT NULL
               OR authority IS NOT NULL)"""), 0)
    check("no prototype basis in authoritative release", db.scalar("""
        SELECT count(*) FROM ontology_authoring.configuration_dimensions
        WHERE ontology_version='2026.10'
          AND governance_basis<>'AUTHORITATIVE'"""), 0)

    head("8. VERIFY -- PROTOTYPE RELEASE")
    total = 0
    for table, expected in sorted(PROTOTYPE_COUNTS.items()):
        actual = db.scalar(
            f"SELECT count(*) FROM ontology_authoring.{table} "
            "WHERE ontology_version='2026.10-prototype.1'")
        total += actual
        check(f"prototype {table}", actual, expected)
    check("prototype total rows", total, 34)

    show(db, "prototype release metadata", """
        SELECT ontology_version, release_class, validation_status, status,
               parent_ontology_version, parent_release_class
        FROM ontology_authoring.ontology_release
        WHERE ontology_version='2026.10-prototype.1'
    """)
    release = db.query("""
        SELECT release_class, validation_status, parent_ontology_version,
               parent_release_class FROM ontology_authoring.ontology_release
        WHERE ontology_version='2026.10-prototype.1'""")[0]
    check("release_class", release["release_class"], "PROTOTYPE")
    check("validation_status", release["validation_status"],
          "TO_BE_VALIDATED_WITH_CLARIS")
    check("parent_ontology_version", release["parent_ontology_version"], "2026.10")
    check("parent_release_class", release["parent_release_class"], "AUTHORITATIVE")

    for table in ("configuration_dimensions", "identity_rules",
                  "decision_outputs", "decision_rule_bindings"):
        check(f"{table} all PROTOTYPE_ASSUMPTION", db.scalar(f"""
            SELECT count(*) FROM ontology_authoring.{table}
            WHERE ontology_version='2026.10-prototype.1'
              AND governance_basis<>'PROTOTYPE_ASSUMPTION'"""), 0)
    check("no prototype row is CONFIRMED", db.scalar("""
        SELECT count(*) FROM ontology_authoring.configuration_dimensions
        WHERE ontology_version='2026.10-prototype.1'
          AND (governance_state='CONFIRMED' OR identity_affecting<>'UNKNOWN'
               OR confirmed_by IS NOT NULL OR confirmed_on IS NOT NULL
               OR authority IS NOT NULL)"""), 0)
    check("no prototype rule carries a confirmed effect", db.scalar("""
        SELECT count(*) FROM ontology_authoring.identity_rules
        WHERE ontology_version='2026.10-prototype.1'
          AND (identity_effect IS NOT NULL OR confirmed_by IS NOT NULL
               OR confirmed_on IS NOT NULL OR authority IS NOT NULL)"""), 0)

    head("9. VERIFY -- IDENTITY CONTRACT")
    show(db, "prototype identity tuple (ordinal order)", """
        SELECT ordinal, dimension FROM ontology_authoring.configuration_dimensions
        WHERE ontology_version='2026.10-prototype.1'
          AND proposed_identity_affecting IS TRUE ORDER BY ordinal
    """)
    tuple_members = [r["dimension"] for r in db.query("""
        SELECT dimension FROM ontology_authoring.configuration_dimensions
        WHERE ontology_version='2026.10-prototype.1'
          AND proposed_identity_affecting IS TRUE ORDER BY ordinal""")]
    check("locked identity tuple", tuple_members,
          ["product_reference", "geography", "term_months", "customer_segment"])
    check("package_format is NOT in the tuple",
          "package_format" not in tuple_members, True)

    show(db, "executable prototype assumptions", """
        SELECT rule, change_type, proposed_effect, governance_state, status
        FROM ontology_authoring.identity_rules
        WHERE ontology_version='2026.10-prototype.1' ORDER BY ordinal
    """)
    executable = {r["rule"]: r["proposed_effect"] for r in db.query("""
        SELECT rule, proposed_effect FROM ontology_authoring.identity_rules
        WHERE ontology_version='2026.10-prototype.1'
          AND proposed_effect IS NOT NULL""")}
    check("executable assumptions", executable, {
        "IR-001": "CREATE_PRODUCT", "IR-002": "CREATE_CONFIGURATION",
        "IR-003": "CREATE_CONFIGURATION", "IR-004": "CREATE_CONFIGURATION",
        "IR-005": "NEW_VERSION", "IR-008": "NEW_VERSION",
        "IR-009": "NO_BUSINESS_CHANGE"})
    check("IR-006 is not executable", db.scalar("""
        SELECT count(*) FROM ontology_authoring.identity_rules
        WHERE ontology_version='2026.10-prototype.1' AND rule='IR-006'
          AND proposed_effect IS NULL AND governance_state='UNPROPOSED'
          AND status='undefined'"""), 1)
    check("IR-007 absent from the prototype release", db.scalar("""
        SELECT count(*) FROM ontology_authoring.identity_rules
        WHERE ontology_version='2026.10-prototype.1' AND rule='IR-007'"""), 0)

    head("10. VERIFY -- DECISION RULE BINDINGS")
    show(db, "prototype bindings", """
        SELECT rule_id, predicate_name, rule_class, precedence, expected_outcome
        FROM ontology_authoring.decision_rule_bindings
        WHERE ontology_version='2026.10-prototype.1' ORDER BY precedence
    """)
    bindings = [(r["rule_id"], r["predicate_name"], r["rule_class"],
                 r["precedence"], r["expected_outcome"]) for r in db.query("""
        SELECT rule_id, predicate_name, rule_class, precedence, expected_outcome
        FROM ontology_authoring.decision_rule_bindings
        WHERE ontology_version='2026.10-prototype.1' ORDER BY precedence""")]
    check("bindings", bindings, [
        ("IA-PRED-001", "ir_011_missing_required_input", "GUARD", 1, "CANNOT_DECIDE"),
        ("IA-PRED-002", "ir_012_contradicted_required_input", "GUARD", 2, "CANNOT_DECIDE"),
        ("IA-PRED-003", "ir_013_initial_configuration", "MATCH", 5, "CREATE_CONFIGURATION"),
        ("IA-PRED-004", "ir_010_exact_identity_match", "MATCH", 6, "NO_BUSINESS_CHANGE")])
    check("no IR-nnn stored as an executable binding", db.scalar("""
        SELECT count(*) FROM ontology_authoring.decision_rule_bindings
        WHERE rule_id ~ '^IR-[0-9]{3}$'"""), 0)
    check("no FALLBACK", db.scalar("""
        SELECT count(*) FROM ontology_authoring.decision_rule_bindings
        WHERE rule_class='FALLBACK'"""), 0)

    head("10B. VERIFY -- GOVERNED OUTCOME VOCABULARY (not an enum)")
    for outcome in ("CREATE_PRODUCT", "CREATE_CONFIGURATION", "USE_EXISTING",
                    "NEW_VERSION", "NO_BUSINESS_CHANGE", "CANNOT_DECIDE"):
        check(f"prototype declares {outcome}", db.scalar("""
            SELECT count(*) FROM ontology_authoring.decision_outputs
            WHERE ontology_version='2026.10-prototype.1'
              AND decision='IDENTITY_ASSESSMENT' AND outcome=%s
              AND governance_basis='PROTOTYPE_ASSUMPTION'""", (outcome,)), 1)
        check(f"is_valid_outcome_v2 accepts {outcome}", db.scalar(
            "SELECT claris.is_valid_outcome_v2(%s,%s,%s,%s,%s)",
            ("retail", "2026.10-prototype.1", "IDENTITY_ASSESSMENT",
             outcome, "PROTOTYPE_ASSUMPTION")), True)
    # cross-version and cross-basis contamination must stay rejected
    check("is_valid_outcome_v2 rejects a legacy outcome", db.scalar(
        "SELECT claris.is_valid_outcome_v2(%s,%s,%s,%s,%s)",
        ("retail", "2026.10-prototype.1", "IDENTITY_ASSESSMENT",
         "READY_FOR_LAUNCH", "PROTOTYPE_ASSUMPTION")), False)
    check("is_valid_outcome_v2 rejects the wrong version", db.scalar(
        "SELECT claris.is_valid_outcome_v2(%s,%s,%s,%s,%s)",
        ("retail", "2026.10", "IDENTITY_ASSESSMENT",
         "CREATE_CONFIGURATION", "PROTOTYPE_ASSUMPTION")), False)
    check("is_valid_outcome_v2 rejects the wrong basis", db.scalar(
        "SELECT claris.is_valid_outcome_v2(%s,%s,%s,%s,%s)",
        ("retail", "2026.10-prototype.1", "IDENTITY_ASSESSMENT",
         "CREATE_CONFIGURATION", "AUTHORITATIVE")), False)
    check("is_valid_outcome_v2 fails closed on a NULL scope", db.scalar(
        "SELECT claris.is_valid_outcome_v2(%s,NULL,%s,%s,%s)",
        ("retail", "IDENTITY_ASSESSMENT", "CREATE_CONFIGURATION",
         "PROTOTYPE_ASSUMPTION")), False)

    head("11. VERIFY -- PRODUCTION / PROTOTYPE ISOLATION")
    show(db, "releases", """
        SELECT ontology_version, release_class, validation_status,
               parent_ontology_version, status
        FROM ontology_authoring.ontology_release ORDER BY ontology_version
    """)
    check("exactly two releases",
          db.scalar("SELECT count(*) FROM ontology_authoring.ontology_release"), 2)
    check("no authoritative row claims a prototype basis", db.scalar("""
        SELECT count(*) FROM ontology_authoring.configuration_dimensions
        WHERE release_class='AUTHORITATIVE'
          AND governance_basis='PROTOTYPE_ASSUMPTION'"""), 0)
    check("no prototype row claims an authoritative basis", db.scalar("""
        SELECT count(*) FROM ontology_authoring.configuration_dimensions
        WHERE release_class='PROTOTYPE' AND governance_basis='AUTHORITATIVE'"""), 0)
    check("authoritative release has no parent", db.scalar("""
        SELECT count(*) FROM ontology_authoring.ontology_release
        WHERE release_class='AUTHORITATIVE'
          AND parent_ontology_version IS NOT NULL"""), 0)
    check("both releases are draft, nothing activated", db.scalar("""
        SELECT count(*) FROM ontology_authoring.ontology_release
        WHERE status='draft'"""), 2)

    head("12. WITNESS -- CANONICAL AND UPSTREAM STATE")
    census = schema_census(db)
    print(f"   {len(census)} table(s), {sum(census.values())} row(s) across "
          f"{len(WITNESS_SCHEMAS)} schema(s)")
    for table, n in sorted(census.items()):
        if n:
            print(f"      {table:<44} {n}")
    for table in ("claris.product", "claris.configuration",
                  "claris.configuration_version", "claris.decision",
                  "claris.action_record"):
        if table in census:
            check(f"{table} holds no rows", census[table], 0)
    check("claris_kb.decision_rules unchanged",
          census.get("claris_kb.decision_rules"), 13)
    check("claris_kb.identity_rules unchanged",
          census.get("claris_kb.identity_rules"), 19)
    check("ontology.decisions unchanged", census.get("ontology.decisions"), 6)
    check("ontology.decision_outputs unchanged",
          census.get("ontology.decision_outputs"), 12)

    return list(FAILURES)


def main() -> int:
    with read_only_connection() as db:
        failures = run_verification(db)
        head("RESULT")
        if failures:
            print(f"   {len(failures)} VERIFICATION FAILURE(S):")
            for item in failures:
                print(f"     - {item}")
            return 4
        print("   D.4G.3 DEPLOYMENT VERIFIED -- all checks passed")
        print("   Nothing compiled. Nothing activated. No decision executed.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
