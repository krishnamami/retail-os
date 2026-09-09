r"""D4I_003 acceptance -- does the reconstructed contract reproduce the deployed
evidence layer? READ ONLY, zero mutations.

WHY A FULL-COLUMN DIFF AND NOT A COUNT
---------------------------------------
Two different mapping contracts can produce 143 rows. A count check would pass
both. So this compares every semantic column of every row, keyed on
(raw_event_id, mapping_id), and reports rows that exist on one side only and
rows that exist on both but disagree about a value.

That is the only evidence that the function in D4I_003 IS the deployed contract
rather than merely a plausible one.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_evidence_contract_verify.py

Exit codes
    0  the projection reproduces the deployed evidence exactly
    4  it does not -- D4I_003 is not canonical, do NOT proceed to D4I_004
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

#: The columns that carry meaning. evidence_id and created_at are excluded:
#: one is a surrogate key and the other records when a projection ran, and
#: neither is part of what the evidence asserts.
SEMANTIC_COLUMNS = (
    "evidence_type", "subject_type", "subject_id", "property_name",
    "asserted_value", "value_type", "source_system", "source_actor_id",
    "source_actor_role", "occurred_at", "recorded_at", "arrival_at",
)

FAILURES: list = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(label)


def main() -> int:
    with read_only_connection() as db:
        head("1. THE FUNCTION EXISTS AND IS PURE")
        exists = db.scalar("""
            SELECT count(*) FROM pg_proc p JOIN pg_namespace n
              ON n.oid = p.pronamespace
            WHERE n.nspname='runtime' AND p.proname='evidence_projection_v1'""")
        check("runtime.evidence_projection_v1 is deployed", exists, 1)
        if not exists:
            print("   Apply D4I_003 first.")
            return 4
        check("it is declared STABLE, so it cannot write", db.scalar("""
            SELECT provolatile FROM pg_proc p JOIN pg_namespace n
              ON n.oid = p.pronamespace
            WHERE n.nspname='runtime' AND p.proname='evidence_projection_v1'"""),
              "s")

        head("2. TOTALS")
        deployed = db.scalar("SELECT count(*) FROM runtime.evidence")
        projected = db.scalar(
            "SELECT count(*) FROM runtime.evidence_projection_v1()")
        print(f"   deployed  : {deployed}")
        print(f"   projected : {projected}")
        check("row counts match", projected, deployed)

        head("3. DISTRIBUTION BY MAPPING -- semantic, not just total")
        rows = db.query("""
            WITH d AS (
              SELECT mapping_id, count(*) n, count(DISTINCT subject_id) s
              FROM runtime.evidence GROUP BY 1),
            p AS (
              SELECT mapping_id, count(*) n, count(DISTINCT subject_id) s
              FROM runtime.evidence_projection_v1() GROUP BY 1)
            SELECT COALESCE(d.mapping_id, p.mapping_id) AS mapping_id,
                   d.n AS deployed_rows, p.n AS projected_rows,
                   d.s AS deployed_subjects, p.s AS projected_subjects,
                   (d.n IS NOT DISTINCT FROM p.n
                    AND d.s IS NOT DISTINCT FROM p.s) AS agrees
            FROM d FULL OUTER JOIN p USING (mapping_id)
            ORDER BY 1""")
        for row in rows:
            flag = "ok " if row["agrees"] else "DIFF"
            print(f"   [{flag}] {row['mapping_id']:<26}"
                  f"deployed {str(row['deployed_rows']):>4}/"
                  f"{str(row['deployed_subjects']):<4}"
                  f"projected {str(row['projected_rows']):>4}/"
                  f"{str(row['projected_subjects']):<4}")
        check("every mapping agrees on rows and subjects",
              [r["mapping_id"] for r in rows if not r["agrees"]], [])
        check("mapping count", len(rows), 22)

        head("4. ROWS ON ONE SIDE ONLY")
        only_deployed = db.query("""
            SELECT e.mapping_id, e.subject_id, e.property_name, e.asserted_value
            FROM runtime.evidence e
            WHERE NOT EXISTS (
              SELECT 1 FROM runtime.evidence_projection_v1() p
              WHERE p.raw_event_id = e.raw_event_id
                AND p.mapping_id  = e.mapping_id)
            ORDER BY 1,2 LIMIT 40""")
        only_projected = db.query("""
            SELECT p.mapping_id, p.subject_id, p.property_name, p.asserted_value
            FROM runtime.evidence_projection_v1() p
            WHERE NOT EXISTS (
              SELECT 1 FROM runtime.evidence e
              WHERE e.raw_event_id = p.raw_event_id
                AND e.mapping_id  = p.mapping_id)
            ORDER BY 1,2 LIMIT 40""")
        print(f"   deployed but not projected : {len(only_deployed)}")
        for row in only_deployed:
            print(f"      {row['mapping_id']:<26}{row['subject_id']:<24}"
                  f"{row['property_name']}={row['asserted_value']!r}")
        print(f"   projected but not deployed : {len(only_projected)}")
        for row in only_projected:
            print(f"      {row['mapping_id']:<26}{row['subject_id']:<24}"
                  f"{row['property_name']}={row['asserted_value']!r}")
        check("no row exists on only one side",
              len(only_deployed) + len(only_projected), 0)

        head("5. VALUE DISAGREEMENTS ON MATCHED ROWS")
        comparisons = " OR ".join(
            f"e.{c} IS DISTINCT FROM p.{c}" for c in SEMANTIC_COLUMNS)
        selected = ", ".join(
            f"e.{c} AS deployed_{c}, p.{c} AS projected_{c}"
            for c in SEMANTIC_COLUMNS)
        mismatches = db.query(f"""
            SELECT e.mapping_id, e.raw_event_id, {selected}
            FROM runtime.evidence e
            JOIN runtime.evidence_projection_v1() p
              ON p.raw_event_id = e.raw_event_id
             AND p.mapping_id  = e.mapping_id
            WHERE {comparisons}
            ORDER BY e.mapping_id LIMIT 40""")
        print(f"   matched rows that disagree on any semantic column: "
              f"{len(mismatches)}")
        for row in mismatches:
            print(f"      {row['mapping_id']} / {row['raw_event_id']}")
            for column in SEMANTIC_COLUMNS:
                a, b = row[f"deployed_{column}"], row[f"projected_{column}"]
                if a != b:
                    print(f"         {column}: deployed={a!r} projected={b!r}")
        check("no matched row disagrees on any semantic column",
              len(mismatches), 0)

        head("6. TIMESTAMPS PASS THROUGH UNMODIFIED")
        check("occurred/recorded/arrival equal the raw event on every row",
              db.scalar("""
                  SELECT count(*) FROM runtime.evidence_projection_v1() p
                  JOIN raw.raw_event r ON r.raw_event_id = p.raw_event_id
                  WHERE p.occurred_at IS DISTINCT FROM r.occurred_at
                     OR p.recorded_at IS DISTINCT FROM r.recorded_at
                     OR p.arrival_at  IS DISTINCT FROM r.arrival_at"""), 0)
        print("\n   the late arrival this preserves:")
        for row in db.query("""
            SELECT p.subject_id, p.property_name, p.occurred_at, p.recorded_at,
                   p.arrival_at
            FROM runtime.evidence_projection_v1() p
            WHERE p.arrival_at::date <> p.occurred_at::date
            ORDER BY p.subject_id, p.property_name LIMIT 20"""):
            print(f"      {row['subject_id']:<12}{row['property_name']:<26}"
                  f"occurred={str(row['occurred_at'])[:10]} "
                  f"recorded={str(row['recorded_at'])[:10]} "
                  f"arrival={str(row['arrival_at'])[:10]}")

        head("7. THE APPROVAL CHAIN IS STILL ABSENT -- D4I_003 ADDS NOTHING")
        check("no approval-chain event is projected yet", db.scalar("""
            SELECT count(*) FROM runtime.evidence_projection_v1() p
            JOIN raw.raw_event r ON r.raw_event_id = p.raw_event_id
            WHERE r.event_type IN
                  ('FINAL_PRICING_APPROVAL','FULLY_APPROVED','ZUPDM_APPROVED',
                   'PRICING_UPLOADED','PRICING_PUBLISHED','OVERNIGHT_PUSH',
                   'GO_LIVE_APPROVAL_REQUESTED','GO_LIVE_APPROVED',
                   'SUPPLY_CHAIN_NOTIFIED','MATERIAL_ACTIVATED','CON_VERIFIED',
                   'SAP_CON_TESTED','SAP_PRD_PROMOTED','HIERARCHY_APPROVAL')"""),
              0)
        check("FINAL_PRICING_APPROVAL and PRICING_CONFIRMED stay distinct",
              db.scalar("""
                  SELECT count(*) FROM runtime.evidence_projection_v1() p
                  JOIN raw.raw_event r ON r.raw_event_id = p.raw_event_id
                  WHERE r.event_type = 'FINAL_PRICING_APPROVAL'
                    AND p.property_name = 'pricing_confirmed'"""), 0)

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            print("\n   BLOCKED -- DEPLOYED EVIDENCE CONTRACT NOT REPRODUCIBLE.")
            print("   Do not proceed to D4I_004.")
            return 4
        print("   DEPLOYED EVIDENCE CONTRACT REPRODUCED.")
        print("   143 rows, 22 mappings, every semantic column identical.")
        print("   Safe to proceed to D4I_004.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
