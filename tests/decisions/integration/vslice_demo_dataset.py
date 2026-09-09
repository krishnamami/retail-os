r"""CLARIS VERTICAL SLICE -- build the demo dataset from PERSISTED state.

READ ONLY. Writes two files and touches no database row.

WHY THIS EXISTS SEPARATELY FROM THE RUNNER
-------------------------------------------
vslice_run.py wrote the dataset from its own in-memory variables, so replaying
the slice overwrote the first run's output with the replay's -- six
NO_BUSINESS_CHANGE rows instead of the canonicalization that actually happened.
That was a defect: a deliverable derived from a process's transient state exists
only as long as nobody runs the process again.

Everything needed is already in the database. claris.decision holds every
governed decision with its outcome, matched rule, reason, digest and lineage;
claris.configuration_version.identity_assessment_id names the decision that
created each version; the projection rules travel in the active artifact. So the
dataset is DERIVED, repeatable, and survives any number of replays -- which is
also the shape a Workbench would read it in.

DECISION HISTORY IS PRESERVED, NOT FLATTENED
--------------------------------------------
A subject may carry several decisions: each evaluation is a fact about a moment,
and a later NO_BUSINESS_CHANGE does not erase the earlier CREATE_CONFIGURATION
that brought the configuration into existence. The dataset reports the full
history per subject and marks which decision each canonical row actually points
at, rather than picking one and discarding the rest.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_demo_dataset.py
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

from decisions.adapters.artifact_kb import ArtifactGovernanceResolver  # noqa: E402
from decisions.adapters.connection import read_only_connection  # noqa: E402
from decisions.governance_resolver import ExecutionMode  # noqa: E402
from decisions.domains.claris.canonical import (  # noqa: E402
    MATERIALIZING_OUTCOMES, MaterializationResult, preview_projections)
from decisions.domains.claris.identity import (  # noqa: E402
    DECISION_TYPE, IDENTITY_PROPERTIES, SUBJECT_TYPE)

DOMAIN = "retail"


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def main() -> int:
    with read_only_connection() as db:
        resolver = ArtifactGovernanceResolver(db, ExecutionMode.PROTOTYPE)
        release = resolver.release
        projection_rules = resolver.projection_rules()

        head("1. GOVERNANCE THIS DATASET RESTS ON")
        print(f"   ontology_version  {release.ontology_version}")
        print(f"   governance_basis  {release.governance_basis}")
        print(f"   validation_status {release.validation_status}")
        print(f"   content_digest    {release.content_digest}")

        # -- the identity tuple each request asked for, from the Fold --------
        tuples: dict = {}
        for row in db.query("""
            SELECT s.subject_id,
                   p->>'property_name'  AS property_name,
                   p->>'fold_state'     AS fold_state,
                   p->>'resolved_value' AS resolved_value
            FROM state.fold_state_snapshot s,
                 LATERAL jsonb_array_elements(s.folded_properties) AS p
            WHERE s.subject_type = %s
              AND p->>'property_name' = ANY(%s)""",
                (SUBJECT_TYPE, list(IDENTITY_PROPERTIES))):
            tuples.setdefault(row["subject_id"], {})[row["property_name"]] = (
                row["resolved_value"] if row["fold_state"] == "ESTABLISHED"
                else None)

        # -- every governed decision, oldest first ---------------------------
        decisions = db.query("""
            SELECT decision_id, subject_id, decision_type, outcome_code,
                   reason_code, matched_rule_id, matched_rule_class,
                   confidence_level, missing_evidence, blocking_evidence,
                   ontology_version, kb_version, governance_basis,
                   execution_mode, input_digest, fold_state_id, state,
                   superseded_by, decided_at, decided_by
            FROM claris.decision
            WHERE decision_type = %s
            ORDER BY subject_id, decided_at""", (DECISION_TYPE,))

        # -- which decision each canonical row actually points at -------------
        versions = {
            str(row["identity_assessment_id"]): row
            for row in db.query("""
                SELECT v.version_id, v.configuration_id, v.status,
                       v.identity_assessment_outcome, v.identity_assessment_id,
                       c.canonical_identity, c.product_id
                FROM claris.configuration_version v
                JOIN claris.configuration c
                  ON c.configuration_id = v.configuration_id""")
            if row["identity_assessment_id"] is not None
        }
        identity_to_configuration = {
            row["canonical_identity"]: row
            for row in db.query("""
                SELECT configuration_id, product_id, canonical_identity, status
                FROM claris.configuration""")
        }

        head("2. DECISION HISTORY PER SUBJECT")
        by_subject: dict = {}
        for decision in decisions:
            by_subject.setdefault(decision["subject_id"], []).append(decision)
        multiple_current = []
        for subject, history in sorted(by_subject.items()):
            current = [d for d in history if d["state"] == "current"]
            print(f"   {subject:<24} {len(history)} decision(s), "
                  f"{len(current)} at state='current'")
            for decision in history:
                marker = "  <- created a canonical version" if str(
                    decision["decision_id"]) in versions else ""
                print(f"      {decision['decided_at']}  "
                      f"{decision['outcome_code']:<22}"
                      f"{decision['matched_rule_id'] or '-':<14}"
                      f"state={decision['state']}{marker}")
            if len(current) > 1:
                multiple_current.append((subject, len(current)))

        head("3. FINDING -- decision supersession")
        if multiple_current:
            print("   claris.execute_decision_v2 did NOT supersede the earlier")
            print("   decision when a second was recorded for the same subject")
            print("   and decision type. These subjects now carry more than one")
            print("   decision at state='current', with different outcomes:")
            for subject, count in multiple_current:
                print(f"      {subject}: {count} current")
            print("\n   This is a persistence-contract finding, not a slice")
            print("   defect: claris.decision has state, superseded_by and")
            print("   superseded_at columns and a 'superseded' state in its")
            print("   CHECK constraint, so the model expects supersession to")
            print("   happen. Nothing in the vertical slice is entitled to")
            print("   decide that policy, so nothing here writes it.")
        else:
            print("   every subject carries exactly one decision at "
                  "state='current'")

        # ==================================================================
        head("4. BUILD THE DATASET")
        records = []
        for subject, history in sorted(by_subject.items()):
            requested = tuples.get(subject, {})
            for ordinal, decision in enumerate(history):
                version = versions.get(str(decision["decision_id"]))
                identity = _identity_of(requested)
                configuration = (
                    identity_to_configuration.get(identity) if identity else None)

                previews = ()
                if decision["outcome_code"] in MATERIALIZING_OUTCOMES and version:
                    previews = preview_projections(
                        MaterializationResult(
                            subject_id=subject,
                            outcome_code=decision["outcome_code"],
                            configuration_id=version["configuration_id"],
                            version_id=version["version_id"],
                            canonical_identity=identity),
                        projection_rules)

                records.append({
                    "subject_id": subject,
                    "evaluation_ordinal": ordinal + 1,
                    "source_change": _source_change(requested),
                    "identity_tuple": requested,
                    "product_reference": requested.get("product_reference"),
                    "canonical_identity": identity,
                    "configuration_id": (
                        version["configuration_id"] if version
                        else configuration["configuration_id"] if configuration
                        else None),
                    "version_id": version["version_id"] if version else None,
                    "decision_id": str(decision["decision_id"]),
                    "decision_outcome": decision["outcome_code"],
                    "reason": decision["reason_code"],
                    "matched_rule": decision["matched_rule_id"],
                    "matched_rule_class": decision["matched_rule_class"],
                    "confidence": decision["confidence_level"],
                    "governance_basis": decision["governance_basis"],
                    "execution_mode": decision["execution_mode"],
                    "ontology_version": decision["ontology_version"],
                    "kb_version": decision["kb_version"],
                    "validation_status": release.validation_status,
                    "input_digest": decision["input_digest"],
                    "fold_state_id": decision["fold_state_id"],
                    "decision_state": decision["state"],
                    "decided_at": decision["decided_at"],
                    "evidence_status": {
                        "missing": list(decision["missing_evidence"] or ()),
                        "blocking": list(decision["blocking_evidence"] or ()),
                    },
                    "canonical_action": _canonical_action(decision, version),
                    "canonical_configuration_created": version is not None,
                    "human_review_required":
                        decision["outcome_code"] == "CANNOT_DECIDE",
                    "legacy_physical_row_required": bool(previews),
                    "proliferation_avoided": decision["outcome_code"] in
                        ("NO_BUSINESS_CHANGE", "USE_EXISTING", "NEW_VERSION"),
                    "projections": [p.as_row() for p in previews],
                })

        summary = _summary(db, records, by_subject)

        out_dir = os.path.join(_REPO_ROOT, "out")
        os.makedirs(out_dir, exist_ok=True)
        dataset = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "derived from persisted claris.decision and canonical "
                      "tables; regenerating this file reproduces it",
            "governance": {
                "ontology_version": release.ontology_version,
                "kb_version": release.kb_version,
                "release_class": release.release_class,
                "governance_basis": release.governance_basis,
                "validation_status": release.validation_status,
                "content_digest": release.content_digest,
                "warning": "PROTOTYPE ASSUMPTION. NOT CLARIS APPROVED. Every "
                           "governed value in this release is an engineering "
                           "assumption awaiting validation with Claris. The "
                           "user_tier assumption behind IR-005 is the most "
                           "consequential and the most expensive to get wrong.",
            },
            "summary": summary,
            "scenarios": records,
        }
        json_path = os.path.join(out_dir, "vslice_demo.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(dataset, handle, indent=2, default=str)
        print(f"\n   {json_path}")

        flat = _flatten(records)
        csv_path = os.path.join(out_dir, "vslice_demo.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(flat[0]))
            writer.writeheader()
            writer.writerows(flat)
        print(f"   {csv_path}  ({len(flat)} rows)")

        head("5. SUMMARY")
        for key, value in summary.items():
            print(f"   {key:<48} {value}")

        head("DATASET REBUILT FROM PERSISTED STATE -- ZERO MUTATIONS")
        return 0


def _identity_of(requested: dict):
    if any(requested.get(name) is None for name in IDENTITY_PROPERTIES):
        return None
    return "|".join(("v2",) + tuple(
        f"{len(str(requested[name]))}:{requested[name]}"
        for name in IDENTITY_PROPERTIES))


def _source_change(requested: dict) -> str:
    missing = [n for n in IDENTITY_PROPERTIES if requested.get(n) is None]
    if missing:
        return "incomplete request: " + ", ".join(missing) + " not established"
    return ", ".join(f"{n}={requested[n]}" for n in IDENTITY_PROPERTIES)


def _canonical_action(decision, version) -> str:
    if decision["outcome_code"] == "CANNOT_DECIDE":
        return "NONE -- retained for human review"
    if version:
        return (f"CREATED configuration {version['configuration_id']} "
                f"version {version['version_id']}")
    return "REUSED existing canonical identity"


def _summary(db, records, by_subject) -> dict:
    outcomes: dict = {}
    for record in records:
        outcomes[record["decision_outcome"]] = \
            outcomes.get(record["decision_outcome"], 0) + 1
    first = [history[0] for history in by_subject.values()]
    first_outcomes: dict = {}
    for decision in first:
        first_outcomes[decision["outcome_code"]] = \
            first_outcomes.get(decision["outcome_code"], 0) + 1
    return {
        "configuration requests in the corpus": len(by_subject),
        "governed decisions recorded (all evaluations)": len(records),
        "first-evaluation outcomes": first_outcomes,
        "outcomes across every evaluation": outcomes,
        "canonical Products": db.scalar("SELECT count(*) FROM claris.product"),
        "canonical Configurations": db.scalar(
            "SELECT count(*) FROM claris.configuration"),
        "canonical ConfigurationVersions": db.scalar(
            "SELECT count(*) FROM claris.configuration_version"),
        "legacy projection previews required": sum(
            len(r["projections"]) for r in records),
        "requests that would mint a legacy row today (PR-001)": len(by_subject),
        "canonical configurations avoided": len(by_subject) - db.scalar(
            "SELECT count(*) FROM claris.configuration"),
        "requests refused rather than guessed": sum(
            1 for d in first if d["outcome_code"] == "CANNOT_DECIDE"),
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
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
