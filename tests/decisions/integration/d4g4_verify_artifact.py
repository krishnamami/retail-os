r"""STEP 5G.6 PHASE D.4G.4 -- ARTIFACT VERIFICATION GATE (READ ONLY).

Run AFTER publishing at COMPILED and BEFORE promoting to VERIFIED/ACTIVE.

Proves the payload that actually landed in claris_kb.kb_artifact still
re-digests to the value the compiler produced -- that the round trip through
jsonb preserved the artifact's semantics -- and that it still verifies against
the deployed authoring release it was compiled from.

Run it again after activation: it also checks the activation state and that
production still resolves to its own artifact.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g4_verify_artifact.py

Exit codes
    0  the stored artifact verifies
    2  the artifact is not published yet
    4  verification failed -- do NOT promote or activate
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
from ontology_authoring.compiler.compile_release import (  # noqa: E402
    canonical_json, compile_release, semantic_digest)

DOMAIN, VERSION = "retail", "2026.10-prototype.1"
PRODUCTION_KB = "1.1"
FAILURES: list = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(f"{label}: got {actual!r}, expected {expected!r}")


def main() -> int:
    with read_only_connection() as db:
        head("1. THE STORED ARTIFACT")
        rows = db.query("""
            SELECT kb_version, ontology_version, status, release_class,
                   governance_basis, validation_status, content_digest,
                   source_system, source_schema, generated_at
            FROM claris_kb.kb_artifact WHERE kb_version=%s""", (VERSION,))
        if not rows:
            print(f"   {VERSION} is not published yet. Apply "
                  "D4G4_002_publish_prototype_artifact.sql first.")
            return 2
        stored = rows[0]
        for key, value in stored.items():
            print(f"   {key:<20} {value}")

        head("2. ROUND TRIP -- does the stored payload still digest the same?")
        payload = db.scalar(
            "SELECT kb_json FROM claris_kb.kb_artifact WHERE kb_version=%s",
            (VERSION,))
        recomputed = semantic_digest(payload)
        print(f"   recorded   : {stored['content_digest']}")
        print(f"   recomputed : {recomputed}")
        check("stored payload re-digests to its recorded digest",
              recomputed, stored["content_digest"])

        head("3. AGAINST SOURCE -- recompile the release and compare")
        fresh = compile_release(db, DOMAIN, VERSION)
        check("recompiled digest matches the stored artifact",
              fresh.semantic_digest, stored["content_digest"])
        check("stored payload equals a fresh compilation",
              canonical_json(payload) == canonical_json(fresh.payload), True)

        head("4. CLASSIFICATION AS STORED")
        check("release_class", stored["release_class"], "PROTOTYPE")
        check("governance_basis", stored["governance_basis"],
              "PROTOTYPE_ASSUMPTION")
        check("validation_status", stored["validation_status"],
              "TO_BE_VALIDATED_WITH_CLARIS")
        check("compiled from the authoring model, not a projection",
              stored["source_schema"], "ontology_authoring")

        head("5. LIFECYCLE AND ISOLATION")
        print(f"   status: {stored['status']}")
        production = db.query("SELECT * FROM claris_kb.v_active_kb")
        prototype = db.query("SELECT * FROM claris_kb.v_active_prototype_kb")
        check("production resolves to exactly one artifact", len(production), 1)
        check("production artifact is unchanged",
              production[0]["kb_version"] if production else None, PRODUCTION_KB)
        check("production never returns the prototype",
              VERSION not in {r["kb_version"] for r in production}, True)
        if stored["status"] == "ACTIVE":
            check("prototype resolves to exactly one artifact", len(prototype), 1)
            check("and it is this one",
                  prototype[0]["kb_version"] if prototype else None, VERSION)
            check("its basis travels with it",
                  prototype[0]["governance_basis"] if prototype else None,
                  "PROTOTYPE_ASSUMPTION")
            check("and so does its validation status",
                  prototype[0]["validation_status"] if prototype else None,
                  "TO_BE_VALIDATED_WITH_CLARIS")
        else:
            check("not active yet, so the prototype door is empty",
                  len(prototype), 0)

        head("6. PROTECTED TABLES")
        for table in ("claris.product", "claris.configuration",
                      "claris.configuration_version", "claris.decision",
                      "claris.action_record"):
            check(f"{table} holds no rows",
                  db.scalar(f"SELECT count(*) FROM {table}"), 0)
        check("the three historical artifacts are untouched", db.scalar("""
            SELECT count(*) FROM claris_kb.kb_artifact
            WHERE kb_version IN ('1.0','1.0.1','1.1')
              AND release_class='AUTHORITATIVE'"""), 3)

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S) -- DO NOT PROMOTE OR ACTIVATE:")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        if stored["status"] == "COMPILED":
            print("   ARTIFACT VERIFIED. Safe to promote to VERIFIED, then ACTIVE.")
        elif stored["status"] == "ACTIVE":
            print("   ARTIFACT VERIFIED AND SCOPED-ACTIVE. Production untouched.")
        else:
            print(f"   ARTIFACT VERIFIED at status {stored['status']}.")
        print("   No decision executed. No canonical object materialized.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
