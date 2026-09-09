r"""CLARIS VERTICAL SLICE -- raw governed state to canonical identity to legacy
projection preview.

    Fold (governed state)
      -> Identity Context
      -> governed IDENTITY_ASSESSMENT against the ACTIVE PROTOTYPE artifact
      -> persisted decision (claris.execute_decision_v2)
      -> canonical Product / Configuration / ConfigurationVersion
      -> legacy projection PREVIEW
      -> demo dataset

WHAT IT REUSES, AND BUILDS NOTHING NEW FOR
    PostgresFoldLoader              state.fold_state_snapshot -> D.4C contracts
    ArtifactGovernanceResolver      the ACTIVE prototype artifact -> bindings
    CanonicalIdentityLookup         claris.product / claris.configuration
    ClarisIdentityFactProvider      the three domain facts
    ContextBuilder                  assembles the DecisionContext
    GovernedDecisionExecutor        the deterministic executor, unmodified
    OutcomeVocabulary               version-scoped outcome validation
    claris.execute_decision_v2      decision persistence and lineage
    CanonicalMaterializer           the canonical write side

SAFETY
    Writes only claris.product, claris.configuration,
    claris.configuration_version and claris.decision (through
    execute_decision_v2). Touches no raw event, no evidence, no assertion, no
    fold snapshot, no KB artifact and no authoring row. Never writes to a
    target system: projections are previews.

    --dry-run executes everything and rolls back, so the outcomes can be seen
    before anything is kept.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_run.py --dry-run
    .\venv\Scripts\python.exe tests\decisions\integration\vslice_run.py

Requires RETAIL_OS_DEPLOY_CONFIRM=VSLICE in the environment.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from datetime import datetime, timezone

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

from decisions.adapters.artifact_kb import (  # noqa: E402
    ArtifactGovernanceResolver, build_registry)
from decisions.adapters.connection import deploy_connection  # noqa: E402
from decisions.adapters.fold_postgres import PostgresFoldLoader  # noqa: E402
from decisions.context_builder import ContextBuilder  # noqa: E402
from decisions.contracts import (  # noqa: E402
    GOVERNANCE_BASIS_PROTOTYPE, DecisionRequest)
from decisions.executor import GovernedDecisionExecutor  # noqa: E402
from decisions.governance_resolver import ExecutionMode  # noqa: E402
from decisions.outcome_validation import (  # noqa: E402
    OutcomeVocabulary, validate_result)
from decisions.domains.claris.canonical import (  # noqa: E402
    CanonicalMaterializer, preview_projections)
from decisions.domains.claris.identity import (  # noqa: E402
    DECISION_TYPE, IDENTITY_PROPERTIES, SUBJECT_TYPE)
from decisions.domains.claris.lookup import (  # noqa: E402
    CanonicalIdentityLookup, ClarisIdentityFactProvider)
from decisions.domains.claris.registration import (  # noqa: E402
    PREDICATES_BY_NAME, REASON_CODES_BY_NAME)

DOMAIN = "retail"
EXPECTED_VERSION = "2026.10-prototype.2"
PRODUCT_SUBJECT_TYPE = "product"
PRODUCT_NAME_PROPERTY = "product_name"

FAILURES: list = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(f"{label}: got {actual!r}, expected {expected!r}")
    return ok


def canonical_counts(db) -> dict:
    return {
        "product": db.scalar("SELECT count(*) FROM claris.product"),
        "configuration": db.scalar("SELECT count(*) FROM claris.configuration"),
        "configuration_version": db.scalar(
            "SELECT count(*) FROM claris.configuration_version"),
        "decision": db.scalar("SELECT count(*) FROM claris.decision"),
    }


def main(dry_run: bool) -> int:
    with deploy_connection() as db:
        # ==============================================================
        head("0. PREFLIGHT -- refuse to run against the wrong governance")
        active = db.query("SELECT * FROM claris_kb.v_active_prototype_kb")
        check("exactly one ACTIVE prototype artifact", len(active), 1)
        if not active:
            db.rollback()
            return 4
        check("and it is the release this slice expects",
              active[0]["kb_version"], EXPECTED_VERSION)
        production = db.query("SELECT kb_version FROM claris_kb.v_active_kb")
        check("production still resolves to KB 1.1",
              production[0]["kb_version"] if production else None, "1.1")

        print("\n   outcome vocabulary, as the database validates it:")
        for outcome in ("CREATE_PRODUCT", "CREATE_CONFIGURATION", "NEW_VERSION",
                        "NO_BUSINESS_CHANGE", "USE_EXISTING", "CANNOT_DECIDE"):
            valid = db.scalar(
                "SELECT claris.is_valid_outcome_v2(%s,%s,%s,%s,%s)",
                (DOMAIN, EXPECTED_VERSION, DECISION_TYPE, outcome,
                 GOVERNANCE_BASIS_PROTOTYPE))
            print(f"      is_valid_outcome_v2({outcome:<20}) = {valid}")
            if valid is not True:
                FAILURES.append(
                    f"is_valid_outcome_v2 rejects {outcome} at "
                    f"{EXPECTED_VERSION}; execute_decision_v2 would refuse it")

        # Can the canonical columns actually HOLD what this slice writes?
        # A width is part of a column's type, and a mid-run
        # StringDataRightTruncation leaves a half-materialized transaction to
        # unpick. Checked here so the answer is a refusal, not a crash.
        widths = {r["column_name"]: r["character_maximum_length"]
                  for r in db.query("""
                      SELECT column_name, character_maximum_length
                      FROM information_schema.columns
                      WHERE table_schema='claris'
                        AND table_name='configuration'""")}
        print("\n   canonical column widths the slice depends on:")
        # canonical_identity and configuration_id are load-bearing: a value
        # that does not fit cannot be written at all. identity_digest is
        # advisory -- nothing resolves a configuration by it -- so a narrow
        # column is reported and the digest is left NULL rather than truncated.
        for column, needed, blocking in (("canonical_identity", 128, True),
                                         ("configuration_id", 64, True),
                                         ("identity_digest", 74, False)):
            actual = widths.get(column)
            fits = actual is not None and actual >= needed
            verdict = "ok" if fits else ("TOO NARROW" if blocking
                                         else "too narrow -- digest left NULL")
            print(f"      claris.configuration.{column:<20} varchar({actual}) "
                  f"needs >= {needed}  {verdict}")
            if not fits and blocking:
                FAILURES.append(
                    f"claris.configuration.{column} is varchar({actual}); the "
                    f"governed value needs at least {needed} characters")

        before = canonical_counts(db)
        print(f"\n   canonical layer before: {before}")

        if FAILURES:
            head("PREFLIGHT FAILED -- nothing executed, nothing written")
            for item in FAILURES:
                print(f"     - {item}")
            db.rollback()
            return 4

        # ==============================================================
        head("1. WIRE THE EXISTING COMPONENTS TOGETHER")
        resolver = ArtifactGovernanceResolver(
            db, ExecutionMode.PROTOTYPE, reason_codes=REASON_CODES_BY_NAME)
        release = resolver.release
        print(f"   selected release   : {release.kb_version}")
        print(f"   governance_basis   : {release.governance_basis}")
        print(f"   validation_status  : {release.validation_status}")
        print(f"   digest             : {release.content_digest[:16]}...")

        class_bindings = resolver.class_bindings(DECISION_TYPE,
                                                 PREDICATES_BY_NAME)
        registry = build_registry(resolver, DECISION_TYPE, PREDICATES_BY_NAME)
        print(f"   executable bindings: {len(class_bindings)}")
        for rule_id, binding in sorted(
                class_bindings.items(),
                key=lambda kv: kv[1].precedence_override or 0):
            print(f"      {rule_id:<14} {binding.rule_class.value:<6} "
                  f"prec={binding.precedence_override:<3} "
                  f"{binding.predicate_ref}")

        vocabulary = OutcomeVocabulary(
            ontology_version=release.ontology_version,
            governance_basis=release.governance_basis,
            decision_type=DECISION_TYPE,
            outcomes=resolver.outcomes_for(DECISION_TYPE))
        projection_rules = resolver.projection_rules()
        print(f"   governed outcomes  : {sorted(vocabulary.outcomes)}")
        print(f"   projection rules   : "
              f"{[r['rule'] for r in projection_rules]}")

        fold_loader = PostgresFoldLoader(db)
        lookup = CanonicalIdentityLookup(db)
        fact_provider = ClarisIdentityFactProvider(lookup)
        builder = ContextBuilder(fold_loader, resolver, fact_provider)
        executor = GovernedDecisionExecutor(registry)
        materializer = CanonicalMaterializer(db, created_by="vertical-slice")

        # ==============================================================
        head("2. THE CORPUS -- every configuration request the Fold holds")
        subjects = db.query("""
            SELECT subject_id, decision_horizon, fold_status
            FROM state.fold_state_snapshot
            WHERE subject_type = %s
            ORDER BY subject_id""", (SUBJECT_TYPE,))
        for row in subjects:
            print(f"   {row['subject_id']:<24} horizon={row['decision_horizon']} "
                  f"fold_status={row['fold_status']}")
        print(f"   {len(subjects)} configuration request(s)")

        product_names = {
            row["subject_id"]: _property_value(row["folded_properties"],
                                               PRODUCT_NAME_PROPERTY)
            for row in db.query("""
                SELECT subject_id, folded_properties
                FROM state.fold_state_snapshot
                WHERE subject_type = %s""", (PRODUCT_SUBJECT_TYPE,))
        }
        print(f"   governed product names: {product_names}")

        # ==============================================================
        head("3. EXECUTE, PERSIST, MATERIALIZE")
        records: list = []
        first_tuple_by_product: dict = {}

        for row in subjects:
            subject_id = row["subject_id"]
            horizon = row["decision_horizon"]
            print(f"\n-- {subject_id}")

            request = DecisionRequest(
                decision_type=DECISION_TYPE,
                subject_type=SUBJECT_TYPE,
                subject_id=subject_id,
                decision_horizon=horizon,
                requested_by="vertical-slice",
            )
            assembly = builder.build(
                request, class_bindings, IDENTITY_PROPERTIES,
                governance_basis=release.governance_basis)
            if not assembly.assembled:
                print(f"   NO GOVERNED STATE ({assembly.fold_status.value}); "
                      "no decision executed")
                FAILURES.append(f"{subject_id}: no fold snapshot")
                continue

            context = assembly.context
            result = executor.execute(context)
            validate_result(vocabulary, result)

            lookup_result = fact_provider.last_result
            identity = lookup_result.canonical_identity
            product_reference = lookup_result.product_reference
            requested = _requested_tuple(context)

            print(f"   identity   : {identity}")
            print(f"   facts      : product_exists="
                  f"{lookup_result.product_exists} configurations="
                  f"{lookup_result.existing_configuration_count} exact_match="
                  f"{lookup_result.exact_identity_match_exists}")
            print(f"   OUTCOME    : {result.outcome_code}"
                  f"  reason={result.reason_code}"
                  f"  rule={result.matched_rule_id}"
                  f" ({result.matched_rule_class})")
            print(f"   confidence : {result.confidence_level}"
                  f"  missing={list(result.missing_evidence)}"
                  f"  blocking={list(result.blocking_evidence)}")

            persisted = db.query("""
                SELECT * FROM claris.execute_decision_v2(
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s)""", (
                DOMAIN, result.ontology_version, result.governance_basis,
                ExecutionMode.PROTOTYPE.value, result.decision_type,
                result.subject_type, result.subject_id, result.outcome_code,
                result.reason_code, result.kb_version, result.policy_version,
                result.horizon_as_of, result.input_digest, result.fold_state_id,
                result.matched_rule_id, result.matched_rule_class,
                result.matched_rule_kb_version, result.confidence_level,
                list(result.missing_evidence), list(result.blocking_evidence),
                result.executor_version, result.digest_scheme_version,
                "vertical-slice"))
            decision_id = str(persisted[0]["decision_id"]) if persisted else None
            print(f"   decision   : {decision_id} "
                  f"state={persisted[0]['state'] if persisted else '?'}")

            materialized = materializer.materialize(
                subject_id=subject_id,
                outcome_code=result.outcome_code,
                product_reference=product_reference,
                canonical_identity=identity,
                product_name=product_names.get(product_reference),
                decision_id=decision_id)
            print(f"   canonical  : {materialized.canonical_action}"
                  f"  configuration={materialized.configuration_id}"
                  f"  version={materialized.version_id}")

            previews = preview_projections(materialized, projection_rules)
            for preview in previews:
                print(f"   projection : {preview.target_system:<12}"
                      f"{preview.projection_action:<8}"
                      f"{preview.projection_reason:<28}"
                      f"new_key={preview.requires_new_target_identity}"
                      f"  proliferation={preview.counts_as_proliferation}")

            if product_reference not in first_tuple_by_product and identity:
                first_tuple_by_product[product_reference] = requested
            differs = _differs_in(
                requested, first_tuple_by_product.get(product_reference))

            records.append({
                "subject_id": subject_id,
                "source_change": differs or "baseline configuration",
                "identity_tuple": requested,
                "product_reference": product_reference,
                "canonical_identity": identity,
                "configuration_id": materialized.configuration_id,
                "version_id": materialized.version_id,
                "version_sequence": materialized.version_sequence,
                "decision_id": decision_id,
                "decision_type": result.decision_type,
                "decision_outcome": result.outcome_code,
                "reason": result.reason_code,
                "matched_rule": result.matched_rule_id,
                "matched_rule_class": result.matched_rule_class,
                "governance_basis": result.governance_basis,
                "ontology_version": result.ontology_version,
                "kb_version": result.kb_version,
                "validation_status": release.validation_status,
                "input_digest": result.input_digest,
                "fold_state_id": result.fold_state_id,
                "evidence_status": {
                    "missing": list(result.missing_evidence),
                    "blocking": list(result.blocking_evidence),
                    "confidence": result.confidence_level,
                },
                "canonical_action": materialized.canonical_action,
                "canonical_configuration_created":
                    "configuration" in materialized.created,
                "human_review_required": materialized.human_review_required,
                "legacy_physical_row_required": bool(previews),
                "proliferation_avoided": result.outcome_code in
                    ("NO_BUSINESS_CHANGE", "USE_EXISTING", "NEW_VERSION"),
                "note": materialized.note,
                "projections": [p.as_row() for p in previews],
            })

        # ==============================================================
        head("4. WHAT THE CANONICAL LAYER NOW HOLDS")
        after = canonical_counts(db)
        print(f"   before: {before}")
        print(f"   after : {after}")
        for table in ("product", "configuration", "configuration_version"):
            for r in db.query(f"SELECT * FROM claris.{table} ORDER BY 1"):
                print(f"   {table:<22} " +
                      " | ".join(f"{k}={r[k]!r}" for k in list(r)[:6]))

        head("5. INVARIANTS")
        check("CANNOT_DECIDE created no configuration",
              [r["subject_id"] for r in records
               if r["decision_outcome"] == "CANNOT_DECIDE"
               and r["canonical_configuration_created"]], [])
        check("NO_BUSINESS_CHANGE created no configuration",
              [r["subject_id"] for r in records
               if r["decision_outcome"] == "NO_BUSINESS_CHANGE"
               and r["canonical_configuration_created"]], [])
        check("every created configuration carries a distinct identity",
              db.scalar("""SELECT count(*) FROM (
                  SELECT canonical_identity FROM claris.configuration
                  GROUP BY canonical_identity HAVING count(*) > 1) d"""), 0)
        check("every configuration has at least one version",
              db.scalar("""SELECT count(*) FROM claris.configuration c
                  WHERE NOT EXISTS (
                      SELECT 1 FROM claris.configuration_version v
                      WHERE v.configuration_id = c.configuration_id)"""), 0)
        check("every decision names the prototype release",
              db.scalar("""SELECT count(*) FROM claris.decision
                  WHERE ontology_version <> %s OR governance_basis <> %s
                     OR execution_mode <> 'PROTOTYPE'""",
                        (EXPECTED_VERSION, GOVERNANCE_BASIS_PROTOTYPE)), 0)
        check("no decision was recorded against production governance",
              db.scalar("""SELECT count(*) FROM claris.decision
                  WHERE governance_basis = 'AUTHORITATIVE'"""), 0)

        # ==============================================================
        head("6. RUN TRANSCRIPT (the demo dataset is built separately,\n   from persisted state, by vslice_demo_dataset.py)")
        out_dir = os.path.join(_REPO_ROOT, "out")
        os.makedirs(out_dir, exist_ok=True)
        summary = _summary(records, after)
        dataset = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "governance": {
                "ontology_version": release.ontology_version,
                "kb_version": release.kb_version,
                "release_class": release.release_class,
                "governance_basis": release.governance_basis,
                "validation_status": release.validation_status,
                "content_digest": release.content_digest,
                "warning": "PROTOTYPE ASSUMPTION. NOT CLARIS APPROVED. Every "
                           "governed value in this release is an engineering "
                           "assumption awaiting validation with Claris.",
            },
            "summary": summary,
            "scenarios": records,
        }
        # NOT vslice_demo.json: this file is one run's transcript, and a
        # replay must not overwrite the dataset built from persisted
        # state. vslice_demo_dataset.py owns the deliverable.
        json_path = os.path.join(out_dir, "vslice_lastrun.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(dataset, handle, indent=2, default=str)
        print(f"   {json_path}")

        csv_path = os.path.join(out_dir, "vslice_lastrun.csv")
        flat = _flatten(records)
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(flat[0]) if flat
                                    else ["subject_id"])
            writer.writeheader()
            writer.writerows(flat)
        print(f"   {csv_path}  ({len(flat)} rows)")

        head("7. SUMMARY")
        for key, value in summary.items():
            print(f"   {key:<44} {value}")

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            db.rollback()
            print("   rolled back; nothing was kept")
            return 4
        if dry_run:
            db.rollback()
            print("   DRY RUN -- everything above was executed and rolled back.")
        else:
            db.commit()
            print("   COMMITTED.")
        print("   No target system was written. Projections are previews.")
        return 0


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _property_value(folded, name):
    if isinstance(folded, str):
        folded = json.loads(folded)
    for item in folded or ():
        if item.get("property_name") == name and \
                item.get("fold_state") == "ESTABLISHED":
            return item.get("resolved_value")
    return None


def _requested_tuple(context) -> dict:
    return {
        name: (context.fold.property_named(name).resolved_value
               if context.fold.property_named(name) is not None else None)
        for name in IDENTITY_PROPERTIES
    }


def _differs_in(requested: dict, baseline) -> str:
    if not baseline or requested == baseline:
        return ""
    changed = [f"{k}: {baseline.get(k)!r} -> {v!r}"
               for k, v in requested.items() if baseline.get(k) != v]
    return "; ".join(changed)


def _summary(records, after) -> dict:
    by_outcome: dict = {}
    for record in records:
        by_outcome[record["decision_outcome"]] = \
            by_outcome.get(record["decision_outcome"], 0) + 1
    governed = sum(n for outcome, n in by_outcome.items()
                   if outcome != "CANNOT_DECIDE")
    projections = sum(len(r["projections"]) for r in records)
    duplicates = by_outcome.get("NO_BUSINESS_CHANGE", 0) + \
        by_outcome.get("USE_EXISTING", 0)
    return {
        "configuration requests processed": len(records),
        "governed automatically": governed,
        "CANNOT_DECIDE (retained for human review)":
            by_outcome.get("CANNOT_DECIDE", 0),
        "outcomes": by_outcome,
        "canonical Products": after["product"],
        "canonical Configurations": after["configuration"],
        "canonical ConfigurationVersions": after["configuration_version"],
        "persisted decisions": after["decision"],
        "legacy projection previews required": projections,
        "requests that would have minted a legacy row today (PR-001)":
            len(records),
        "unnecessary canonical configurations avoided": duplicates,
    }


def _flatten(records) -> list:
    rows = []
    for record in records:
        base = {k: (json.dumps(v, default=str) if isinstance(v, (dict, list))
                    else v)
                for k, v in record.items() if k != "projections"}
        if not record["projections"]:
            rows.append({**base, "target_system": None,
                         "projection_action": None, "projection_reason": None,
                         "requires_new_target_identity": None,
                         "counts_as_proliferation": None})
            continue
        for projection in record["projections"]:
            rows.append({**base,
                         "target_system": projection["target_system"],
                         "projection_action": projection["projection_action"],
                         "projection_reason": projection["projection_reason"],
                         "requires_new_target_identity":
                             projection["requires_new_target_identity"],
                         "counts_as_proliferation":
                             projection["counts_as_proliferation"]})
    return rows


if __name__ == "__main__":
    try:
        sys.exit(main("--dry-run" in sys.argv))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
