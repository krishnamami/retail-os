r"""Corpus facts and the readiness-governance gap. READ ONLY, zero mutations.

Answers steps 7 and 8 of the verification brief from persisted data, so the
findings are measured rather than asserted. Nothing here infers beyond what a
row states, and where a fact is absent it is reported as absent.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_corpus_facts.py

Exit codes
    0  every stated fact was confirmed against the database
    4  at least one was not -- the report says which
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

from decisions.adapters.artifact_kb import ArtifactGovernanceResolver  # noqa: E402
from decisions.adapters.connection import read_only_connection  # noqa: E402
from decisions.governance_resolver import ExecutionMode  # noqa: E402
from decisions.domains.claris.registration import PREDICATES_BY_NAME  # noqa: E402

FAILURES: list = []
PRICING_PROPERTIES = ("pricing_status", "pricing_confirmed", "pricing_value_usd")


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def sub(t):
    print(f"\n-- {t}")


def show(rows, limit=60, indent="   "):
    if not rows:
        print(f"{indent}(no rows)")
        return
    for row in rows[:limit]:
        print(indent + " | ".join(f"{k}={row[k]!r}" for k in row))
    if len(rows) > limit:
        print(f"{indent}... {len(rows) - limit} more")


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    with read_only_connection() as db:
        # ==============================================================
        head("A. LAUNCH-001 -- the identity / canonicalization half")
        sub("events carrying launch_id = LAUNCH-001")
        show(db.query("""
            SELECT event_type, count(*) AS n
            FROM raw.raw_event WHERE launch_id = 'LAUNCH-001'
            GROUP BY 1 ORDER BY 1"""))

        check("configuration requests on LAUNCH-001", db.scalar("""
            SELECT count(*) FROM raw.raw_event
            WHERE launch_id='LAUNCH-001'
              AND event_type='CONFIGURATION_REQUESTED'"""), 7)

        sub("its configuration_request subjects, and what became of them")
        show(db.query("""
            SELECT s.subject_id, s.fold_status,
                   (SELECT count(*) FROM claris.decision d
                     WHERE d.subject_id = s.subject_id) AS decisions,
                   (SELECT count(*) FROM claris.decision d
                     WHERE d.subject_id = s.subject_id
                       AND d.state='current') AS current_decisions
            FROM state.fold_state_snapshot s
            WHERE s.subject_type='configuration_request'
            ORDER BY s.subject_id"""))

        sub("canonical objects that exist at all")
        show(db.query("""
            SELECT 'product' AS kind, product_id AS id, product_name AS detail
            FROM claris.product
            UNION ALL
            SELECT 'configuration', configuration_id, canonical_identity
            FROM claris.configuration
            UNION ALL
            SELECT 'version', version_id, identity_assessment_outcome
            FROM claris.configuration_version
            ORDER BY 1, 2"""))

        sub("SKU-side flow on LAUNCH-001 -- expected to be absent")
        sku_side = db.scalar("""
            SELECT count(*) FROM raw.raw_event
            WHERE launch_id='LAUNCH-001'
              AND event_type IN ('SKU_MINTED','SKU_ACTIVATED','TECHNICAL_REVIEW',
                                 'PRICING_DETERMINED','FINAL_PRICING_APPROVAL',
                                 'PRICING_CONFIRMED','FULLY_APPROVED')""")
        check("SKU/pricing events on LAUNCH-001", sku_side, 0)

        # ==============================================================
        head("B. LAUNCH-004..012 -- the SKU / pricing half")
        sub("SKU_MINTED, and the launch each SKU belongs to")
        show(db.query("""
            SELECT launch_id, sku_id, occurred_at
            FROM raw.raw_event WHERE event_type='SKU_MINTED'
            ORDER BY launch_id"""))
        check("every SKU_MINTED carries a launch_id", db.scalar("""
            SELECT count(*) FROM raw.raw_event
            WHERE event_type='SKU_MINTED' AND launch_id IS NULL"""), 0)

        sub("approval-side event volumes")
        show(db.query("""
            SELECT event_type, count(*) AS n,
                   count(*) FILTER (WHERE launch_id IS NOT NULL) AS with_launch,
                   count(DISTINCT sku_id) AS distinct_sku
            FROM raw.raw_event
            WHERE event_type IN ('TECHNICAL_REVIEW','PRICING_DETERMINED',
                                 'FINAL_PRICING_APPROVAL','PRICING_CONFIRMED',
                                 'FULLY_APPROVED','ZUPDM_APPROVED')
            GROUP BY 1 ORDER BY 1"""))

        sub("pricing_confirmed exists on only a subset of SKUs")
        confirmed = db.query("""
            SELECT subject_id, asserted_value FROM runtime.evidence
            WHERE property_name='pricing_confirmed' ORDER BY subject_id""")
        show(confirmed)
        priced = db.query("""
            SELECT DISTINCT subject_id FROM runtime.evidence
            WHERE property_name='pricing_status' ORDER BY subject_id""")
        print(f"   SKUs with pricing_status : {len(priced)}")
        print(f"   SKUs with pricing_confirmed: {len(confirmed)}")
        check("pricing_confirmed is a strict subset of pricing_status",
              len(confirmed) < len(priced), True)

        # ==============================================================
        head("C. SKU-004 -- one real stall, entirely from persisted evidence")
        show(db.query("""
            SELECT property_name, asserted_value, source_system,
                   source_actor_role, occurred_at
            FROM runtime.evidence WHERE subject_id='SKU-004'
            ORDER BY occurred_at, property_name"""))
        held = {row["property_name"] for row in db.query("""
            SELECT property_name FROM runtime.evidence
            WHERE subject_id='SKU-004'""")}
        check("SKU-004 has sku_status", "sku_status" in held, True)
        check("SKU-004 has technical_review_result",
              "technical_review_result" in held, True)
        check("SKU-004 has pricing_status", "pricing_status" in held, True)
        check("SKU-004 has pricing_value_usd", "pricing_value_usd" in held, True)
        check("SKU-004 has NO pricing_confirmed -- the stall",
              "pricing_confirmed" in held, False)

        sub("its folded state, which is what a decision would read")
        show(db.query("""
            SELECT p->>'property_name' AS property_name,
                   p->>'fold_state'    AS fold_state,
                   p->>'resolved_value' AS resolved_value
            FROM state.fold_state_snapshot s,
                 LATERAL jsonb_array_elements(s.folded_properties) AS p
            WHERE s.subject_type='sku' AND s.subject_id='SKU-004'
            ORDER BY 1"""))

        # ==============================================================
        head("D. WHY THE SKU HALF WAS NEVER CANONICALIZED")
        check("configuration_request subjects for SKU-side launches",
              db.scalar("""
                  SELECT count(*) FROM raw.raw_event
                  WHERE event_type='CONFIGURATION_REQUESTED'
                    AND launch_id <> 'LAUNCH-001'"""), 0)
        check("IDENTITY_ASSESSMENT decisions on any sku subject", db.scalar("""
            SELECT count(*) FROM claris.decision WHERE subject_type='sku'"""), 0)
        sub("identity properties present on a sku fold snapshot")
        show(db.query("""
            SELECT DISTINCT p->>'property_name' AS property_name
            FROM state.fold_state_snapshot s,
                 LATERAL jsonb_array_elements(s.folded_properties) AS p
            WHERE s.subject_type='sku'
              AND p->>'property_name' IN ('product_reference','geography',
                                          'term_months','customer_segment')
            ORDER BY 1"""))
        print("   (an empty list here is the reason: no identity tuple exists "
              "on a sku subject,\n    so IDENTITY_ASSESSMENT has nothing to "
              "serialize and no canonical object can form)")

        # ==============================================================
        head("E. READINESS GOVERNANCE -- what is and is not executable")
        sub("claris_kb.decision_rules by decision type")
        show(db.query("""
            SELECT decision_type, count(*) AS rules
            FROM claris_kb.decision_rules GROUP BY 1 ORDER BY 1"""))
        check("any readiness decision type in the legacy rule table",
              db.scalar("""
                  SELECT count(*) FROM claris_kb.decision_rules
                  WHERE decision_type IN ('LAUNCH_READINESS',
                                          'PRICING_READINESS',
                                          'LEGACY_PROJECTION_REQUIREMENT')"""),
              0)

        resolver = ArtifactGovernanceResolver(db, ExecutionMode.PROTOTYPE)
        release = resolver.release
        bound = sorted({row["decision"] for row in
                        release.rows("decision_rule_bindings")})
        sub(f"decision types the ACTIVE prototype artifact binds "
            f"({release.ontology_version})")
        print(f"   {bound}")
        check("exactly one executable decision type", bound,
              ["IDENTITY_ASSESSMENT"])

        sub("declared decisions in the release, executable or not")
        show(db.query("""
            SELECT decision, mode, phase, status, blocked_on
            FROM ontology_authoring.decisions
            WHERE ontology_version = %s ORDER BY ordinal""",
            (release.ontology_version,)))

        sub("registered predicates the domain pack exports")
        for name in sorted(PREDICATES_BY_NAME):
            print(f"   {name}")
        check("no predicate concludes a pricing or readiness outcome",
              [n for n in PREDICATES_BY_NAME
               if "pricing" in n or "readiness" in n or "launch" in n], [])

        # ==============================================================
        head("F. FINANCE -- role is governed, person is not")
        sub("ontology_authoring.actors, from the active release")
        show(db.query("""
            SELECT actor, display_name, actor_kind, responsibility,
                   owns_steps_today
            FROM ontology_authoring.actors
            WHERE ontology_version = %s ORDER BY ordinal""",
            (release.ontology_version,)))
        finance = db.query("""
            SELECT actor, display_name, responsibility, owns_steps_today
            FROM ontology_authoring.actors
            WHERE ontology_version = %s AND actor = 'finance'""",
            (release.ontology_version,))
        check("a governed finance role exists", len(finance), 1)
        if finance:
            print(f"\n   finance responsibility : "
                  f"{finance[0]['responsibility']}")
            print(f"   finance owns steps     : "
                  f"{finance[0]['owns_steps_today']}")

        sub("dimension ownership in the active release")
        show(db.query("""
            SELECT dimension, owner, authority, governance_state, status
            FROM ontology_authoring.configuration_dimensions
            WHERE ontology_version = %s ORDER BY ordinal""",
            (release.ontology_version,)))
        check("dimensions carrying a governed owner", db.scalar("""
            SELECT count(*) FROM ontology_authoring.configuration_dimensions
            WHERE ontology_version = %s AND owner IS NOT NULL""",
            (release.ontology_version,)), 0)

        sub("actor identities in the evidence layer")
        show(db.query("""
            SELECT DISTINCT source_actor_id, source_actor_role
            FROM runtime.evidence
            WHERE source_actor_id IS NOT NULL
            ORDER BY 1"""))
        print("   every value above is a simulation marker, not a person; the "
              "agent returns\n   the role and leaves the actor null")

        # ==============================================================
        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} stated fact(s) NOT confirmed:")
            for item in FAILURES:
                print(f"     - {item}")
            return 4
        print("   EVERY STATED CORPUS AND GOVERNANCE FACT CONFIRMED.")
        print("   Zero mutations.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
