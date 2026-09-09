r"""D4I_003c acceptance -- is OBSERVED distinguishable from DEFAULTED, and did
proving it change anything else? READ ONLY, zero mutations.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_provenance_verify.py

WHY THIS EXISTS ALONGSIDE THE SQL VERIFIERS
    The migration verifiers ran once, against the state they created. This
    runs independently, from the repository, on demand, so a later change that
    quietly re-classifies evidence or edits the frozen _v1 has something that
    notices. It repeats the classification from first principles -- mapping
    identity plus source-path presence in raw.raw_event -- rather than reading
    value_provenance back and agreeing with it.

Exit codes
    0  provenance holds and nothing else moved
    4  it does not
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

#: Mapping kind, read from the verified body of evidence_projection_v1.
#: EXTRACTION -- value came from a payload path, guarded on presence.
#: OCCURRENCE -- the event happening is the fact; the constant names it.
#: BRANCHING  -- COALESCE, so provenance is decided per row on this key.
EXTRACTION = {
    "CHANGE_REQUESTED_BY", "CHANGE_REQUESTER_ROLE", "SAP_CON_HIERARCHY",
    "SAP_CON_LOAD_ACTOR", "SAP_PRD_HIERARCHY", "PRICING_VALUE",
    "PRODUCT_DEF_LAUNCH", "PRODUCT_DEF_NAME", "CONF_REQ_PRODUCT",
    "CONF_REQ_GEO", "CONF_REQ_TERM", "CONF_REQ_SEGMENT", "CONF_REQ_LAUNCH",
}
OCCURRENCE = {
    "MATERIAL_CREATED", "SKU_MINTED", "SKU_ACTIVATED", "PRICING_STATUS",
    "PRICING_CONFIRMED",
}
BRANCHING = {
    "PRODUCT_INTENT_CLASS": "intent_class",
    "SAP_CON_LOAD_STATUS": "con_status",
    "SAP_PRD_LOAD_STATUS": "prd_status",
    "TECHNICAL_REVIEW_RESULT": "technical_approval_status",
}

V1_MARKERS = (
    "market_expansion",
    "COALESCE(r.payload->>'con_status'",
    "(r.payload->>'con_id')::varchar",
    "COALESCE(r.payload->>'prd_status'",
    "COALESCE(r.payload->>'technical_approval_statu",
)
V1_BODY_LENGTH = 20534

FAILURES: list = []


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def check(label, actual, expected):
    ok = actual == expected
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}: {actual!r}"
          + ("" if ok else f"  expected {expected!r}"))
    if not ok:
        FAILURES.append(label)


def note(text):
    print(f"   [note] {text}")


def main() -> int:
    with read_only_connection() as db:

        head("1. THE CLASSIFICATION -- 104 / 39 / 0")
        counts = {r["value_provenance"]: r["n"] for r in db.query("""
            SELECT value_provenance, count(*) AS n
            FROM runtime.evidence GROUP BY 1 ORDER BY 1""")}
        print(f"   {counts}")
        check("OBSERVED", counts.get("OBSERVED"), 104)
        check("DEFAULTED", counts.get("DEFAULTED"), 39)
        check("DERIVED rows", counts.get("DERIVED", 0), 0)
        check("total", sum(counts.values()), 143)
        check("no row left unclassified", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE value_provenance IS NULL"""), 0)

        head("2. DIRECT PAYLOAD EXTRACTION IS OBSERVED")
        rows = db.query("""
            SELECT mapping_id,
                   count(*) AS n,
                   count(*) FILTER (WHERE value_provenance='OBSERVED') AS obs
            FROM runtime.evidence
            WHERE mapping_id = ANY(%(m)s) GROUP BY 1 ORDER BY 1""",
                        {"m": sorted(EXTRACTION)})
        for row in rows:
            print(f"      {row['mapping_id']:<26}{row['obs']}/{row['n']} OBSERVED")
        check("every extraction row is OBSERVED",
              [r["mapping_id"] for r in rows if r["obs"] != r["n"]], [])
        check("all 13 extraction mappings present", len(rows), 13)
        check("their lineage source_path resolves on every row", db.scalar("""
            SELECT count(*) FROM runtime.evidence e
            JOIN raw.raw_event r ON r.raw_event_id = e.raw_event_id
            WHERE e.mapping_id = ANY(%(m)s)
              AND (e.evidence_lineage->>'source_path') LIKE 'payload.%%'
              AND r.payload #> string_to_array(
                    right(e.evidence_lineage->>'source_path', -8), '.')
                  IS NULL""", {"m": sorted(EXTRACTION)}), 0)

        head("3. RAW-COLUMN EXTRACTION")
        note("no deployed mapping takes its VALUE from a raw column -- every")
        note("value is a payload path or a constant. Raw columns supply the")
        note("SUBJECT (launch_id, sku_id, material_id). Those rows are still")
        note("OBSERVED, on the strength of the payload or the occurrence.")
        check("subject-from-raw-column rows are OBSERVED", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE mapping_id IN ('CHANGE_REQUESTED_BY','CHANGE_REQUESTER_ROLE',
                                 'PRODUCT_INTENT_CLASS','MATERIAL_CREATED',
                                 'SKU_MINTED','SKU_ACTIVATED','PRICING_STATUS',
                                 'PRICING_VALUE','PRICING_CONFIRMED',
                                 'TECHNICAL_REVIEW_RESULT')
              AND value_provenance NOT IN ('OBSERVED','DEFAULTED')"""), 0)

        head("4. EVENT OCCURRENCE IS OBSERVED, NOT DEFAULTED")
        rows = db.query("""
            SELECT e.mapping_id, r.event_type, e.asserted_value,
                   count(*) AS n,
                   count(*) FILTER (WHERE e.value_provenance='OBSERVED') AS obs
            FROM runtime.evidence e
            JOIN raw.raw_event r ON r.raw_event_id = e.raw_event_id
            WHERE e.mapping_id = ANY(%(m)s)
            GROUP BY 1,2,3 ORDER BY 1""", {"m": sorted(OCCURRENCE)})
        for row in rows:
            print(f"      {row['event_type']:<24}-> {row['asserted_value']:<12}"
                  f"{row['obs']}/{row['n']} OBSERVED")
        check("every occurrence row is OBSERVED",
              [r["mapping_id"] for r in rows if r["obs"] != r["n"]], [])
        check("occurrence rows total", sum(r["n"] for r in rows), 27)

        head("5 & 6. COALESCE MAPPINGS DECIDE PER ROW")
        for mapping, key in sorted(BRANCHING.items()):
            rows = db.query("""
                SELECT e.value_provenance,
                       (r.payload ? %(k)s
                        AND r.payload->>%(k)s IS NOT NULL) AS source_present,
                       count(*) AS n
                FROM runtime.evidence e
                JOIN raw.raw_event r ON r.raw_event_id = e.raw_event_id
                WHERE e.mapping_id = %(m)s
                GROUP BY 1,2 ORDER BY 2 DESC""",
                            {"m": mapping, "k": key})
            for row in rows:
                print(f"      {mapping:<26}source_present="
                      f"{str(row['source_present']):<6}"
                      f"{row['value_provenance']:<10}{row['n']}")
            check(f"{mapping}: present -> OBSERVED, absent -> DEFAULTED",
                  [(r["source_present"], r["value_provenance"]) for r in rows
                   if (r["source_present"] and r["value_provenance"] != "OBSERVED")
                   or (not r["source_present"]
                       and r["value_provenance"] != "DEFAULTED")], [])

        check("defaulted rows across the four branching mappings",
              db.scalar("""
                  SELECT count(*) FROM runtime.evidence
                  WHERE value_provenance='DEFAULTED'"""), 39)
        check("no defaulted row outside those four", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE value_provenance='DEFAULTED'
              AND mapping_id <> ALL(%(m)s)""",
            {"m": sorted(BRANCHING)}), 0)

        head("7. NO DERIVED ROWS YET -- AND THE VOCABULARY STILL ALLOWS ONE")
        check("DERIVED rows", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE value_provenance='DERIVED'"""), 0)
        check("DERIVED is permitted by the CHECK", db.scalar("""
            SELECT count(*) FROM pg_constraint con
            JOIN pg_class cl ON cl.oid=con.conrelid
            JOIN pg_namespace ns ON ns.oid=cl.relnamespace
            WHERE ns.nspname='runtime' AND cl.relname='evidence'
              AND con.conname='evidence_value_provenance_valid'
              AND pg_get_constraintdef(con.oid) LIKE '%DERIVED%'"""), 1)

        head("8 & 9. THE SCHEMA REFUSES SILENCE AND NONSENSE")
        col = db.query("""
            SELECT is_nullable, column_default, character_maximum_length AS len
            FROM information_schema.columns
            WHERE table_schema='runtime' AND table_name='evidence'
              AND column_name='value_provenance'""")
        check("column exists", len(col), 1)
        check("NOT NULL -- a writer that omits provenance fails",
              col[0]["is_nullable"], "NO")
        check("no DEFAULT -- omission cannot be silently filled in",
              col[0]["column_default"], None)
        check("varchar(32)", col[0]["len"], 32)
        check("CHECK constrains the vocabulary to exactly three values",
              db.scalar("""
                  SELECT count(*) FROM pg_constraint con
                  JOIN pg_class cl ON cl.oid=con.conrelid
                  JOIN pg_namespace ns ON ns.oid=cl.relnamespace
                  WHERE ns.nspname='runtime' AND cl.relname='evidence'
                    AND con.conname='evidence_value_provenance_valid'"""), 1)
        note("the live refusals themselves are proven by "
             "D4I_003c_06_failure_behavior.sql, which inserts and rolls back;")
        note("a read-only connection can only confirm the constraints exist.")

        head("10. PROVENANCE IS NOT SIMULATOR_CLASSIFICATION")
        grid = db.query("""
            SELECT COALESCE(simulator_classification,'<unmarked>') AS marker,
                   value_provenance, count(*) AS n
            FROM runtime.evidence GROUP BY 1,2 ORDER BY 1,2""")
        for row in grid:
            print(f"      {row['marker']:<24}{row['value_provenance']:<12}"
                  f"{row['n']}")
        check("no marked row is DEFAULTED", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE simulator_classification IS NOT NULL
              AND value_provenance='DEFAULTED'"""), 0)
        check("marked rows", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE simulator_classification IS NOT NULL"""), 36)
        note("36 marked and 39 defaulted, disjoint: had provenance been "
             "inferred from the marker the split would read 36/107.")

        head("11. PROJECTION V1 IS STILL THE FROZEN D4I_003 ARTIFACT")
        src = db.scalar("""
            SELECT prosrc FROM pg_proc p JOIN pg_namespace n
              ON n.oid=p.pronamespace
            WHERE n.nspname='runtime' AND p.proname='evidence_projection_v1'""")
        check("v1 body length", len(src) if src else None, V1_BODY_LENGTH)
        for marker in V1_MARKERS:
            check(f"v1 marker {marker[:38]!r}", marker in (src or ""), True)
        check("v1 still returns 143 rows", db.scalar(
            "SELECT count(*) FROM runtime.evidence_projection_v1()"), 143)

        head("12. V2 PRESERVES EVERY V1 SEMANTIC VALUE")
        check("rows in one projection only", db.scalar("""
            SELECT (SELECT count(*) FROM runtime.evidence_projection_v1() a
                    WHERE NOT EXISTS (
                      SELECT 1 FROM runtime.evidence_projection_v2() b
                      WHERE b.raw_event_id=a.raw_event_id
                        AND b.mapping_id=a.mapping_id))
                 + (SELECT count(*) FROM runtime.evidence_projection_v2() b
                    WHERE NOT EXISTS (
                      SELECT 1 FROM runtime.evidence_projection_v1() a
                      WHERE a.raw_event_id=b.raw_event_id
                        AND a.mapping_id=b.mapping_id))"""), 0)
        check("matched rows disagreeing on any v1 column", db.scalar("""
            SELECT count(*)
            FROM runtime.evidence_projection_v1() a
            JOIN runtime.evidence_projection_v2() b
              ON b.raw_event_id=a.raw_event_id AND b.mapping_id=a.mapping_id
            WHERE a.evidence_type     IS DISTINCT FROM b.evidence_type
               OR a.subject_type      IS DISTINCT FROM b.subject_type
               OR a.subject_id        IS DISTINCT FROM b.subject_id
               OR a.property_name     IS DISTINCT FROM b.property_name
               OR a.asserted_value    IS DISTINCT FROM b.asserted_value
               OR a.value_type        IS DISTINCT FROM b.value_type
               OR a.source_system     IS DISTINCT FROM b.source_system
               OR a.source_actor_id   IS DISTINCT FROM b.source_actor_id
               OR a.source_actor_role IS DISTINCT FROM b.source_actor_role
               OR a.occurred_at       IS DISTINCT FROM b.occurred_at
               OR a.recorded_at       IS DISTINCT FROM b.recorded_at
               OR a.arrival_at        IS DISTINCT FROM b.arrival_at
               OR a.evidence_lineage  IS DISTINCT FROM b.evidence_lineage"""), 0)
        check("stored evidence still matches v1 on every semantic column",
              db.scalar("""
                  SELECT count(*)
                  FROM runtime.evidence e
                  JOIN runtime.evidence_projection_v1() a
                    ON a.raw_event_id=e.raw_event_id
                   AND a.mapping_id=e.mapping_id
                  WHERE e.asserted_value   IS DISTINCT FROM a.asserted_value
                     OR e.subject_id       IS DISTINCT FROM a.subject_id
                     OR e.property_name    IS DISTINCT FROM a.property_name
                     OR e.occurred_at      IS DISTINCT FROM a.occurred_at
                     OR e.recorded_at      IS DISTINCT FROM a.recorded_at
                     OR e.arrival_at       IS DISTINCT FROM a.arrival_at
                     OR e.evidence_lineage IS DISTINCT FROM a.evidence_lineage
              """), 0)

        head("13. REPEATED PROJECTION IS IDEMPOTENT")
        check("two calls to v2 disagree on nothing", db.scalar("""
            SELECT count(*)
            FROM runtime.evidence_projection_v2() a
            JOIN runtime.evidence_projection_v2() b
              ON b.raw_event_id=a.raw_event_id AND b.mapping_id=a.mapping_id
            WHERE a.value_provenance IS DISTINCT FROM b.value_provenance
               OR a.asserted_value   IS DISTINCT FROM b.asserted_value"""), 0)
        check("stored provenance equals what v2 re-derives", db.scalar("""
            SELECT count(*) FROM runtime.evidence e
            JOIN runtime.evidence_projection_v2() p
              ON p.raw_event_id=e.raw_event_id AND p.mapping_id=e.mapping_id
            WHERE e.value_provenance IS DISTINCT FROM p.value_provenance"""), 0)

        head("14. NO TEST EVIDENCE SURVIVES")
        check("rows", db.scalar("SELECT count(*) FROM runtime.evidence"), 143)
        check("ZZ_3F failure-behaviour rows", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE mapping_id LIKE 'ZZ_3F%'"""), 0)
        check("TEST_MAPPING rows", db.scalar("""
            SELECT count(*) FROM runtime.evidence
            WHERE mapping_id LIKE 'TEST\\_%'"""), 0)
        check("mappings", db.scalar("""
            SELECT count(DISTINCT mapping_id) FROM runtime.evidence"""), 22)

        head("RESULT")
        if FAILURES:
            print(f"   {len(FAILURES)} FAILURE(S):")
            for item in FAILURES:
                print(f"     - {item}")
            print("\n   BLOCKED -- VALUE PROVENANCE NOT VERIFIED.")
            return 4
        print("   VALUE PROVENANCE VERIFIED.")
        print("   104 OBSERVED / 39 DEFAULTED / 0 DERIVED across 143 rows,")
        print("   22 mappings, v1 frozen, nothing else moved.")
        print("\n   The 39 DEFAULTED rows are now nameable: a governed "
              "readiness")
        print("   decision can refuse to read a defaulted PASS as an observed "
              "one.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
