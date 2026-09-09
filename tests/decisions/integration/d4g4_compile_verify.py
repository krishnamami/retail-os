r"""STEP 5G.6 PHASE D.4G.4 -- COMPILE AND VERIFY (READ ONLY).

Compiles the deployed prototype authoring release and verifies the result back
against that same deployed source. Writes NOTHING to the database: the artifact
lands in out/ as a file so the digest and the verification can be reviewed
before anything is published.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g4_compile_verify.py

Exit codes
    0  compiled and verified
    2  compilation failed closed (no artifact produced)
    4  compiled, but verification against the deployed source failed
"""

from __future__ import annotations

import io
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
    COMPILER_VERSION,
    DIGEST_ALGORITHM,
    SECTIONS,
    CompilationError,
    canonical_json,
    compile_release,
)

DOMAIN = "retail"
VERSION = "2026.10-prototype.1"
OUT = os.path.join(_REPO_ROOT, "out", "d4g4_artifact_2026_10_prototype_1.json")

LOCKED_TUPLE = ["product_reference", "geography", "term_months",
                "customer_segment"]
EXPECTED_BINDINGS = [
    ("IA-PRED-001", "ir_011_missing_required_input", "GUARD", 1, "CANNOT_DECIDE"),
    ("IA-PRED-002", "ir_012_contradicted_required_input", "GUARD", 2, "CANNOT_DECIDE"),
    ("IA-PRED-003", "ir_013_initial_configuration", "MATCH", 5, "CREATE_CONFIGURATION"),
    ("IA-PRED-004", "ir_010_exact_identity_match", "MATCH", 6, "NO_BUSINESS_CHANGE"),
]
EXPECTED_OUTCOMES = {"CREATE_PRODUCT", "CREATE_CONFIGURATION", "USE_EXISTING",
                     "NEW_VERSION", "NO_BUSINESS_CHANGE", "CANNOT_DECIDE"}
EXPECTED_ASSUMPTIONS = {
    "IR-001": "CREATE_PRODUCT", "IR-002": "CREATE_CONFIGURATION",
    "IR-003": "CREATE_CONFIGURATION", "IR-004": "CREATE_CONFIGURATION",
    "IR-005": "NEW_VERSION", "IR-008": "NEW_VERSION",
    "IR-009": "NO_BUSINESS_CHANGE",
}

FAILURES: list = []


def head(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(f"{label}: got {actual!r}, expected {expected!r}")


def main() -> int:
    with read_only_connection() as db:
        head("1. COMPILATION SOURCE")
        release = db.query("""
            SELECT ontology_version, release_class, validation_status, status,
                   parent_ontology_version, parent_release_class
            FROM ontology_authoring.ontology_release
            WHERE domain=%s AND ontology_version=%s""", (DOMAIN, VERSION))
        if not release:
            print(f"   release {VERSION} not found")
            return 2
        print(f"   {release[0]}")
        if release[0]["status"] != "published":
            print(f"\n   *** release is {release[0]['status']!r}, not 'published'.")
            print("   The compiler refuses a draft: publication is a separate,")
            print("   deliberate act and a draft is not a release. Publish it,")
            print("   then re-run. Nothing has been compiled.")
            return 2

        head("2. COMPILE")
        try:
            artifact = compile_release(db, DOMAIN, VERSION)
        except CompilationError as exc:
            print(f"   COMPILATION FAILED CLOSED -- no artifact produced\n\n{exc}")
            return 2
        print(f"   compiler            : {COMPILER_VERSION}")
        print(f"   kb_version (derived): {artifact.kb_version}")
        print(f"   ontology_version    : {artifact.ontology_version}")
        print(f"   parent              : {artifact.parent_ontology_version}")
        print(f"   release_class       : {artifact.release_class}")
        print(f"   governance_basis    : {artifact.governance_basis}")
        print(f"   validation_status   : {artifact.validation_status}")
        print(f"   digest ({DIGEST_ALGORITHM})     : {artifact.semantic_digest}")

        head("3. DETERMINISM -- compile again, compare")
        second = compile_release(db, DOMAIN, VERSION)
        check("digest reproduces", second.semantic_digest, artifact.semantic_digest)
        check("payload reproduces byte for byte",
              canonical_json(second.payload) == canonical_json(artifact.payload), True)

        head("4. CENSUS -- artifact against deployed source")
        total = 0
        for table, _ in SECTIONS:
            compiled = artifact.census[table]
            total += compiled
            if table == "evidence_reference":
                live = db.scalar(
                    "SELECT count(*) FROM ontology_authoring.evidence_reference")
            else:
                live = db.scalar(
                    f"SELECT count(*) FROM ontology_authoring.{table} "
                    "WHERE domain=%s AND ontology_version=%s", (DOMAIN, VERSION))
            check(f"{table}", compiled, live)
        print(f"\n   compiled rows total: {total}")

        head("5. VERIFY -- classification preserved")
        check("release_class", artifact.release_class, "PROTOTYPE")
        check("governance_basis", artifact.governance_basis, "PROTOTYPE_ASSUMPTION")
        check("validation_status", artifact.validation_status,
              "TO_BE_VALIDATED_WITH_CLARIS")
        check("parent", artifact.parent_ontology_version, "2026.10")
        sections = artifact.payload["sections"]
        for name in ("configuration_dimensions", "identity_rules",
                     "decision_outputs", "decision_rule_bindings"):
            bases = {r.get("governance_basis") for r in sections[name]}
            check(f"{name} basis", bases or {"PROTOTYPE_ASSUMPTION"},
                  {"PROTOTYPE_ASSUMPTION"})
        check("no dimension carries a confirmed identity",
              [r["dimension"] for r in sections["configuration_dimensions"]
               if r.get("identity_affecting") != "UNKNOWN"], [])
        check("no rule carries a confirmed effect",
              [r["rule"] for r in sections["identity_rules"]
               if r.get("identity_effect") is not None], [])

        head("6. VERIFY -- identity contract")
        tuple_members = [r["dimension"] for r in
                         sorted(sections["configuration_dimensions"],
                                key=lambda r: r.get("ordinal") or 0)
                         if r.get("proposed_identity_affecting") is True]
        check("locked identity tuple", tuple_members, LOCKED_TUPLE)
        check("package_format is not in the tuple",
              "package_format" not in tuple_members, True)

        head("7. VERIFY -- identity semantics")
        executable = {r["rule"]: r["proposed_effect"]
                      for r in sections["identity_rules"]
                      if r.get("proposed_effect")}
        check("executable assumptions", executable, EXPECTED_ASSUMPTIONS)
        unresolved = {r["rule"] for r in sections["identity_rules"]
                      if not r.get("proposed_effect")}
        check("IR-006 remains unresolved", "IR-006" in unresolved, True)
        check("IR-007 absent", any(r["rule"] == "IR-007"
                                   for r in sections["identity_rules"]), False)

        head("8. VERIFY -- outcome vocabulary and predicate bindings")
        check("governed outcomes",
              {r["outcome"] for r in sections["decision_outputs"]},
              EXPECTED_OUTCOMES)
        bindings = [(r["rule_id"], r["predicate_name"], r["rule_class"],
                     r["precedence"], r["expected_outcome"])
                    for r in sorted(sections["decision_rule_bindings"],
                                    key=lambda r: r["precedence"])]
        check("predicate bindings", bindings, EXPECTED_BINDINGS)
        check("no FALLBACK", any(b[2] == "FALLBACK" for b in bindings), False)
        check("no IR-nnn bound as a predicate",
              any(b[0].startswith("IR-") for b in bindings), False)

        head("9. VERIFY -- no authoritative contamination")
        check("artifact contains no AUTHORITATIVE basis",
              "\"governance_basis\":\"AUTHORITATIVE\"" in canonical_json(artifact.payload),
              False)
        check("artifact names only its own release",
              {r.get("ontology_version") for r in sections["configuration_dimensions"]},
              {VERSION})

        head("10. WRITE ARTIFACT TO FILE (no database write)")
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with io.open(OUT, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({
                "kb_version": artifact.kb_version,
                "ontology_version": artifact.ontology_version,
                "content_digest": artifact.semantic_digest,
                "digest_algorithm": DIGEST_ALGORITHM,
                "compiler_version": COMPILER_VERSION,
                "release_class": artifact.release_class,
                "governance_basis": artifact.governance_basis,
                "validation_status": artifact.validation_status,
                "kb_json": artifact.payload,
            }, indent=2, sort_keys=True, ensure_ascii=False))
        print(f"   written: {OUT}")
        print(f"   digest : {artifact.semantic_digest}")

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} VERIFICATION FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        print("   COMPILED AND VERIFIED against the deployed authoring source.")
        print("   Nothing published. Nothing activated. No decision executed.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
