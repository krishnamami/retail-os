r"""Compile, verify and stage a prototype release. READ ONLY against the database.

Compiles one deployed authoring release with the existing D.4G.4 compiler,
verifies the artifact against the live source it came from, writes it to
out/, and GENERATES the publish migration from the exact bytes it verified --
so the SQL that gets applied cannot drift from the artifact that was checked.

Writes nothing to the database. The generated migration is applied separately.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_compile_release.py
    .\venv\Scripts\python.exe tests\decisions\integration\vslice_compile_release.py 2026.10-prototype.2

Exit codes
    0  compiled and verified; migration written
    4  a verification failed -- no migration is written
"""

from __future__ import annotations

import json
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
from ontology_authoring.compiler.compile_release import (  # noqa: E402
    canonical_json, compile_release, semantic_digest)

DOMAIN = "retail"
DEFAULT_VERSION = "2026.10-prototype.2"

#: What the vertical slice needs to be executable, in evaluation order.
EXPECTED_BINDINGS = (
    ("IA-PRED-001", "GUARD", 1, "ir_011_missing_required_input", "CANNOT_DECIDE"),
    ("IA-PRED-002", "GUARD", 2, "ir_012_contradicted_required_input", "CANNOT_DECIDE"),
    ("IA-PRED-005", "MATCH", 3, "ir_001_no_canonical_product", "CREATE_PRODUCT"),
    ("IA-PRED-003", "MATCH", 5, "ir_013_initial_configuration", "CREATE_CONFIGURATION"),
    ("IA-PRED-004", "MATCH", 6, "ir_010_exact_identity_match", "NO_BUSINESS_CHANGE"),
    ("IA-PRED-006", "MATCH", 7, "additional_configuration_for_existing_product",
     "CREATE_CONFIGURATION"),
)

LOCKED_TUPLE = ("product_reference", "geography", "term_months", "customer_segment")
EXPECTED_PROJECTION_RULES = ("PR-001", "PR-002", "PR-003", "PR-004")

FAILURES: list = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"\n            expected {expected!r}"))
    if not ok:
        FAILURES.append(label)


def main(version: str) -> int:
    with read_only_connection() as db:
        head(f"1. SOURCE -- the deployed authoring release {version}")
        rows = db.query("""
            SELECT ontology_version, release_class, validation_status, status,
                   parent_ontology_version, parent_release_class, description
            FROM ontology_authoring.ontology_release
            WHERE domain=%s AND ontology_version=%s""", (DOMAIN, version))
        if not rows:
            print(f"   {version} does not exist in ontology_authoring. "
                  "Apply the release migration first.")
            return 4
        for k, v in rows[0].items():
            print(f"   {k:<26} {v}")

        head("2. COMPILE")
        artifact = compile_release(db, DOMAIN, version)
        print(f"   compiler            : {artifact.payload['compiler_version']}")
        print(f"   kb_version (derived): {artifact.kb_version}")
        print(f"   release_class       : {artifact.release_class}")
        print(f"   governance_basis    : {artifact.governance_basis}")
        print(f"   validation_status   : {artifact.validation_status}")
        print(f"   parent              : {artifact.parent_ontology_version}")
        print(f"   digest (sha256)     : {artifact.semantic_digest}")

        head("3. DETERMINISM -- compile again, compare")
        again = compile_release(db, DOMAIN, version)
        check("digest reproduces", again.semantic_digest, artifact.semantic_digest)
        check("payload reproduces byte for byte",
              canonical_json(again.payload) == canonical_json(artifact.payload), True)

        head("4. CENSUS -- artifact against a fresh count of the live source")
        total = 0
        for section, rows_ in sorted(artifact.payload["sections"].items()):
            n = len(rows_)
            total += n
            if section == "evidence_reference":
                live = db.scalar(
                    "SELECT count(*) FROM ontology_authoring.evidence_reference")
            else:
                live = db.scalar(
                    f"SELECT count(*) FROM ontology_authoring.{section} "
                    "WHERE domain=%s AND ontology_version=%s", (DOMAIN, version))
            check(f"{section}", n, live)
        print(f"   compiled rows total: {total}")

        head("5. CLASSIFICATION -- nothing was raised during compilation")
        check("release_class", artifact.release_class, "PROTOTYPE")
        check("governance_basis", artifact.governance_basis, "PROTOTYPE_ASSUMPTION")
        check("validation_status", artifact.validation_status,
              "TO_BE_VALIDATED_WITH_CLARIS")
        check("parent is the authoritative release",
              artifact.parent_ontology_version, "2026.10")
        for section in ("configuration_dimensions", "identity_rules",
                        "decision_outputs", "decision_rule_bindings"):
            bases = {r.get("governance_basis")
                     for r in artifact.payload["sections"][section]}
            check(f"{section} basis", bases, {"PROTOTYPE_ASSUMPTION"})
        check("no dimension carries a confirmed identity",
              [r["dimension"] for r in
               artifact.payload["sections"]["configuration_dimensions"]
               if r.get("identity_affecting") != "UNKNOWN"], [])
        check("no rule carries a confirmed effect",
              [r["rule"] for r in artifact.payload["sections"]["identity_rules"]
               if r.get("identity_effect") is not None], [])

        head("6. IDENTITY CONTRACT -- unchanged from prototype.1")
        members = tuple(
            r["dimension"] for r in
            sorted(artifact.payload["sections"]["configuration_dimensions"],
                   key=lambda r: r.get("ordinal") or 0)
            if r.get("proposed_identity_affecting") is True)
        check("locked identity tuple", members, LOCKED_TUPLE)
        rules = {r["rule"]: r.get("proposed_effect")
                 for r in artifact.payload["sections"]["identity_rules"]}
        check("IR-006 remains unresolved", rules.get("IR-006"), None)
        check("IR-007 absent", "IR-007" in rules, False)
        check("the eight identity rules are unchanged in number",
              len(rules), 8)

        head("7. EXECUTABLE BINDINGS -- the whole point of this release")
        bindings = sorted(
            artifact.payload["sections"]["decision_rule_bindings"],
            key=lambda r: int(r["precedence"]))
        actual = tuple(
            (b["rule_id"], b["rule_class"], int(b["precedence"]),
             b["predicate_name"], b["expected_outcome"])
            for b in bindings)
        for row in actual:
            print(f"   {row[0]:<14} {row[1]:<6} prec={row[2]:<3} "
                  f"{row[3]:<46} -> {row[4]}")
        check("bindings, in precedence order", actual, EXPECTED_BINDINGS)
        check("no FALLBACK is declared",
              [b["rule_id"] for b in bindings if b["rule_class"] == "FALLBACK"], [])
        check("no business identity rule is bound as a predicate",
              [b["rule_id"] for b in bindings
               if str(b["rule_id"]).startswith("IR-")], [])
        outcomes = {r["outcome"] for r in
                    artifact.payload["sections"]["decision_outputs"]}
        check("every expected outcome is declared",
              sorted(o for _, _, _, _, o in EXPECTED_BINDINGS if o not in outcomes),
              [])
        check("governed outcome vocabulary", sorted(outcomes),
              ["CANNOT_DECIDE", "CREATE_CONFIGURATION", "CREATE_PRODUCT",
               "NEW_VERSION", "NO_BUSINESS_CHANGE", "USE_EXISTING"])

        head("8. PROJECTION RULES -- carried, not re-authored")
        projections = sorted(artifact.payload["sections"]["projection_rules"],
                             key=lambda r: r.get("ordinal") or 0)
        for p in projections:
            print(f"   {p['rule']:<8} {str(p.get('source_object')):<14} -> "
                  f"{p['target_system']:<12} {str(p.get('proposed_action')):<9} "
                  f"new_identity={p.get('requires_new_target_identity')!r:<6} "
                  f"status={p.get('status')}")
        check("projection rules present",
              tuple(p["rule"] for p in projections), EXPECTED_PROJECTION_RULES)
        source = {r["rule"]: r for r in db.query("""
            SELECT * FROM ontology_authoring.projection_rules
            WHERE domain=%s AND ontology_version='2026.10'""", (DOMAIN,))}
        drift = []
        for p in projections:
            origin = source.get(p["rule"], {})
            for column in ("source_object", "target_system", "proposed_action",
                           "requires_new_target_identity", "projection_reason",
                           "proliferation_classification", "status", "owner",
                           "target_object_type"):
                if str(origin.get(column)) != str(p.get(column)):
                    drift.append(f"{p['rule']}.{column}: "
                                 f"2026.10={origin.get(column)!r} "
                                 f"prototype.2={p.get(column)!r}")
        check("carried verbatim from 2026.10 (no column altered)", drift, [])

        head("9. NO AUTHORITATIVE CONTAMINATION")
        blob = canonical_json(artifact.payload)
        check("artifact contains no AUTHORITATIVE basis",
              '"governance_basis":"AUTHORITATIVE"' in blob, False)
        versions = {r.get("ontology_version")
                    for section in artifact.payload["sections"].values()
                    for r in section if isinstance(r, dict)
                    and r.get("ontology_version") is not None}
        check("artifact names only its own release", versions, {version})

    # ------------------------------------------------------------------
    head("10. STAGE -- write the artifact and generate its publish migration")
    out_dir = os.path.join(_REPO_ROOT, "out")
    os.makedirs(out_dir, exist_ok=True)
    slug = version.replace(".", "_").replace("-", "_")
    artifact_path = os.path.join(out_dir, f"vslice_artifact_{slug}.json")

    if FAILURES:
        print(f"\n   {len(FAILURES)} verification(s) FAILED -- writing nothing:")
        for item in FAILURES:
            print(f"     - {item}")
        return 4

    payload_json = canonical_json(artifact.payload)
    with open(artifact_path, "w", encoding="utf-8") as handle:
        handle.write(payload_json)
    print(f"   artifact : {artifact_path}")

    # re-read and re-digest what actually landed on disk, so the migration is
    # generated from bytes that have made a full round trip
    with open(artifact_path, encoding="utf-8") as handle:
        on_disk = json.load(handle)
    disk_digest = semantic_digest(on_disk)
    if disk_digest != artifact.semantic_digest:
        print(f"   FAIL: the file on disk digests to {disk_digest}, not "
              f"{artifact.semantic_digest}")
        return 4
    print(f"   digest   : {disk_digest} (verified after round trip)")

    if "$kb$" in payload_json:
        print("   FAIL: the payload contains the dollar-quote delimiter")
        return 4

    migration_path = os.path.join(
        _REPO_ROOT, "database", "migrations",
        f"D4H_002_publish_{slug}.sql")
    with open(migration_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_migration(artifact, payload_json, disk_digest))
    print(f"   migration: {migration_path}")

    head("RESULT")
    print(f"   {version} COMPILED AND VERIFIED against the deployed source.")
    print("   Nothing published. Nothing activated. No decision executed.")
    return 0


def _migration(artifact, payload_json: str, digest: str) -> str:
    version = artifact.ontology_version
    return f"""\
-- ============================================================================
-- VERTICAL SLICE -- publish the compiled {version} artifact at COMPILED
-- ============================================================================
-- GENERATED by tests/decisions/integration/vslice_compile_release.py from the
-- artifact it had just verified against the deployed authoring release, after
-- re-digesting the file it wrote. Do not edit by hand; regenerate.
--
--   kb_version        {version}
--   ontology_version  {version}
--   parent            {artifact.parent_ontology_version}
--   release_class     {artifact.release_class}
--   governance_basis  {artifact.governance_basis}
--   validation_status {artifact.validation_status}
--   compiler          {artifact.payload['compiler_version']}
--   digest (sha256)   {digest}
--
-- PUBLISHES AT 'COMPILED' ONLY. Not VERIFIED, not ACTIVE. The lifecycle stays
-- three deliberate acts, because KB 1.1 became ACTIVE while still internally
-- READY_FOR_VERIFICATION and that collapse is what this sequence prevents.
--
-- Touches no existing artifact. 2026.10-prototype.1 keeps its payload, its
-- digest and its ACTIVE status until a separate activation migration moves it.
--
-- APPLY IN ONE TRANSACTION. Idempotent: re-running inserts nothing twice.
-- ============================================================================

INSERT INTO claris_kb.kb_artifact (
    kb_version, ontology_version, policy_version,
    content_digest, kb_json, generated_at, status,
    source_system, source_catalog, source_schema,
    release_class, governance_basis, validation_status
)
SELECT
    '{version}',
    '{version}',
    NULL,                       -- policy_version is derived-or-absent
    '{digest}',
    $kb${payload_json}$kb$::jsonb,
    now(),
    'COMPILED',
    '{artifact.payload['compiler_version']}',
    'accord',
    'ontology_authoring',
    '{artifact.release_class}',
    '{artifact.governance_basis}',
    '{artifact.validation_status}'
WHERE NOT EXISTS (
    SELECT 1 FROM claris_kb.kb_artifact WHERE kb_version = '{version}'
);

-- what landed, and proof both doors are still where they were
SELECT kb_version, status, release_class, governance_basis, validation_status,
       left(content_digest, 16) || '...' AS digest
FROM   claris_kb.kb_artifact ORDER BY kb_version;

SELECT (SELECT count(*) FROM claris_kb.v_active_kb)           AS production_active,
       (SELECT kb_version FROM claris_kb.v_active_kb)         AS production_kb,
       (SELECT count(*) FROM claris_kb.v_active_prototype_kb) AS prototype_active,
       (SELECT kb_version FROM claris_kb.v_active_prototype_kb) AS prototype_kb;
"""


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VERSION))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
