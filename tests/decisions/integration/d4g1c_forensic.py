r"""STEP 5G.6 PHASE D.4G.1C -- READ-ONLY forensic recovery of the governance overlay.

Compares the IMMUTABLE kb_json of KB 1.0.1 and KB 1.1 to reconstruct the
32-entity 2026.10-governance overlay, and searches for the compiler.

NOTE: the two artifacts use DIFFERENT kb_json shapes (1.0.1 wraps each section
as {"rows": [...]}, 1.1 stores sections as bare arrays), so section access is
shape-tolerant and the shape itself is reported as evidence.

No writes. SELECT/WITH only, READ ONLY session, before/after witness.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g1c_forensic.py
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
from live_support import kb_status_fingerprint, row_counts  # noqa: E402


def head(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def show(db, label, sql, params=None, width=900, limit=200):
    print(f"\n-- {label} " + "-" * max(0, 62 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:250]}")
        return []
    if not rows:
        print("   (no rows)")
        return rows
    for row in rows[:limit]:
        if len(row) == 1:
            (v,) = row.values()
            t = "NULL" if v is None else str(v)[:width]
        else:
            t = " | ".join(f"{k}={'NULL' if v is None else str(v)[:width]}"
                           for k, v in row.items())
        print("   " + t.encode("ascii", "replace").decode("ascii"))
    if len(rows) > limit:
        print(f"   ... {len(rows)-limit} more")
    return rows


# Shape-tolerant section accessor: 1.0.1 uses {"rows":[...]}, 1.1 uses [...]
SECT = """
    CASE WHEN jsonb_typeof(a.kb_json->'sections'->k) = 'array'
         THEN a.kb_json->'sections'->k
         ELSE a.kb_json->'sections'->k->'rows' END
"""


def main() -> int:
    with read_only_connection() as db:
        head("0. READ-ONLY + BEFORE WITNESS")
        print(f"   session_is_read_only(): {db.session_is_read_only()}")
        before_counts, before_kb = row_counts(db), kb_status_fingerprint(db)
        before_digest = db.query(
            "SELECT kb_version, content_digest, count(*) OVER () AS active_n "
            "FROM claris_kb.kb_artifact WHERE status='ACTIVE'")
        print(f"   BEFORE: {before_counts}")
        print(f"   ACTIVE digest: {before_digest}")

        # ==============================================================
        head("1. SECTION 8 -- FULL KB ARTIFACT HISTORY")
        show(db, "kb_artifact, every column except payload", """
            SELECT kb_version, ontology_version,
                   coalesce(policy_version,'<NULL>') AS policy_version,
                   status, source_system, source_catalog, source_schema,
                   generated_at, deployed_at, content_digest
            FROM claris_kb.kb_artifact ORDER BY deployed_at
        """)
        show(db, "kb_json top-level metadata per artifact", """
            SELECT kb_version, kb_json - 'sections' AS metadata
            FROM claris_kb.kb_artifact ORDER BY kb_version
        """, width=2000)

        # ==============================================================
        head("2. SECTION 3/9 -- ENTITY COUNTS AND THE 32-ENTITY CLAIM")
        show(db, "section inventory + row counts, ALL artifacts (shape-tolerant)", f"""
            SELECT a.kb_version, k AS section,
                   jsonb_typeof(a.kb_json->'sections'->k) AS raw_type,
                   CASE WHEN jsonb_typeof({SECT}) = 'array'
                        THEN jsonb_array_length({SECT}) END AS n_rows
            FROM claris_kb.kb_artifact a, jsonb_object_keys(a.kb_json->'sections') k
            ORDER BY a.kb_version, k
        """)
        show(db, "TOTAL rows per artifact", f"""
            SELECT a.kb_version,
                   count(*) AS n_sections,
                   sum(CASE WHEN jsonb_typeof({SECT}) = 'array'
                            THEN jsonb_array_length({SECT}) ELSE 0 END) AS total_rows
            FROM claris_kb.kb_artifact a, jsonb_object_keys(a.kb_json->'sections') k
            GROUP BY 1 ORDER BY 1
        """)
        show(db, "SECTIONS IN 1.1 BUT NOT IN 1.0.1 (overlay candidate)", f"""
            WITH s AS (
              SELECT a.kb_version, k AS section,
                     CASE WHEN jsonb_typeof({SECT}) = 'array'
                          THEN jsonb_array_length({SECT}) ELSE 0 END AS n
              FROM claris_kb.kb_artifact a, jsonb_object_keys(a.kb_json->'sections') k
            )
            SELECT section, n AS rows_in_1_1
            FROM s WHERE kb_version='1.1'
              AND section NOT IN (SELECT section FROM s WHERE kb_version='1.0.1')
            ORDER BY 1
        """)
        show(db, "SUM of 1.1-only sections (is it 32?)", f"""
            WITH s AS (
              SELECT a.kb_version, k AS section,
                     CASE WHEN jsonb_typeof({SECT}) = 'array'
                          THEN jsonb_array_length({SECT}) ELSE 0 END AS n
              FROM claris_kb.kb_artifact a, jsonb_object_keys(a.kb_json->'sections') k
            )
            SELECT sum(n) AS sum_of_1_1_only_sections
            FROM s WHERE kb_version='1.1'
              AND section NOT IN (SELECT section FROM s WHERE kb_version='1.0.1')
        """)
        show(db, "PER-SECTION row-count delta for SHARED sections", f"""
            WITH s AS (
              SELECT a.kb_version, k AS section,
                     CASE WHEN jsonb_typeof({SECT}) = 'array'
                          THEN jsonb_array_length({SECT}) ELSE 0 END AS n
              FROM claris_kb.kb_artifact a, jsonb_object_keys(a.kb_json->'sections') k
            )
            SELECT b.section, b.n AS in_1_0_1, c.n AS in_1_1, c.n - b.n AS delta
            FROM s b JOIN s c ON b.section = c.section
            WHERE b.kb_version='1.0.1' AND c.kb_version='1.1'
            ORDER BY 1
        """)

        # ==============================================================
        head("3. SECTIONS 12-17 -- RECORD-LEVEL PROVENANCE, 1.0.1 vs 1.1")
        for section in ("configuration_dimensions", "ontology_notes", "identity_rules",
                        "actors", "use_cases", "projection_rules", "departments",
                        "evidence_types", "configuration_dimension_values", "phases"):
            show(db, f"{section} @ 1.0.1", f"""
                SELECT r AS record FROM claris_kb.kb_artifact a,
                       jsonb_array_elements(
                         CASE WHEN jsonb_typeof(a.kb_json->'sections'->%s)='array'
                              THEN a.kb_json->'sections'->%s
                              ELSE a.kb_json->'sections'->%s->'rows' END) r
                WHERE a.kb_version='1.0.1'
            """, (section, section, section), width=600, limit=30)
            show(db, f"{section} @ 1.1", f"""
                SELECT r AS record FROM claris_kb.kb_artifact a,
                       jsonb_array_elements(
                         CASE WHEN jsonb_typeof(a.kb_json->'sections'->%s)='array'
                              THEN a.kb_json->'sections'->%s
                              ELSE a.kb_json->'sections'->%s->'rows' END) r
                WHERE a.kb_version='1.1'
            """, (section, section, section), width=600, limit=30)

        # ==============================================================
        head("4. SECTION 4 -- COMPLETE claris_kb OBJECT INVENTORY")
        show(db, "every relation in claris_kb with row counts", """
            SELECT c.relname, c.relkind,
                   CASE c.relkind WHEN 'r' THEN c.reltuples::bigint END AS approx_rows
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='claris_kb' AND c.relkind IN ('r','v','m','p')
            ORDER BY c.relkind, c.relname
        """)
        show(db, "distinct kb_version / ontology_version per claris_kb table", """
            SELECT 'actors' t, kb_version, ontology_version, count(*) FROM claris_kb.actors GROUP BY 2,3
            UNION ALL SELECT 'configuration_dimensions', kb_version, ontology_version, count(*) FROM claris_kb.configuration_dimensions GROUP BY 2,3
            UNION ALL SELECT 'configuration_dimension_values', kb_version, ontology_version, count(*) FROM claris_kb.configuration_dimension_values GROUP BY 2,3
            UNION ALL SELECT 'decision_inputs', kb_version, ontology_version, count(*) FROM claris_kb.decision_inputs GROUP BY 2,3
            UNION ALL SELECT 'decision_outputs', kb_version, ontology_version, count(*) FROM claris_kb.decision_outputs GROUP BY 2,3
            UNION ALL SELECT 'decision_rules', kb_version, ontology_version, count(*) FROM claris_kb.decision_rules GROUP BY 2,3
            UNION ALL SELECT 'decisions', kb_version, ontology_version, count(*) FROM claris_kb.decisions GROUP BY 2,3
            UNION ALL SELECT 'departments', kb_version, ontology_version, count(*) FROM claris_kb.departments GROUP BY 2,3
            UNION ALL SELECT 'evidence_types', kb_version, ontology_version, count(*) FROM claris_kb.evidence_types GROUP BY 2,3
            UNION ALL SELECT 'identity_rules', kb_version, ontology_version, count(*) FROM claris_kb.identity_rules GROUP BY 2,3
            UNION ALL SELECT 'ontology_notes', kb_version, ontology_version, count(*) FROM claris_kb.ontology_notes GROUP BY 2,3
            UNION ALL SELECT 'phases', kb_version, ontology_version, count(*) FROM claris_kb.phases GROUP BY 2,3
            UNION ALL SELECT 'projection_rules', kb_version, ontology_version, count(*) FROM claris_kb.projection_rules GROUP BY 2,3
            UNION ALL SELECT 'use_cases', kb_version, ontology_version, count(*) FROM claris_kb.use_cases GROUP BY 2,3
            ORDER BY 1,2
        """)
        show(db, "kb_projection_backup tables", """
            SELECT 'kb_projection_backup_1_0' t, count(*) FROM claris_kb.kb_projection_backup_1_0
            UNION ALL SELECT 'kb_projection_backup_1_0_1', count(*) FROM claris_kb.kb_projection_backup_1_0_1
        """)
        show(db, "columns of kb_projection_backup_1_0_1", """
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema='claris_kb' AND table_name='kb_projection_backup_1_0_1'
            ORDER BY ordinal_position
        """)

        # ==============================================================
        head("5. SECTIONS 5/6 -- OVERLAY MARKERS AND COMPILER PROVENANCE")
        show(db, "objects/comments mentioning compiler or governance", """
            SELECT n.nspname AS schema, c.relname AS object, d.description
            FROM pg_description d
            JOIN pg_class c ON c.oid=d.objoid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE d.description ~* '(phase5b|compiler|compile|governance|overlay|artifact|digest)'
            ORDER BY 1,2
        """)
        show(db, "functions whose SOURCE mentions compiler/overlay markers", """
            SELECT n.nspname AS schema, p.proname
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema')
              AND pg_get_functiondef(p.oid) ~* '(phase5b0|2026\\.10-governance|governance overlay|KB-1\\.1|READY_FOR_VERIFICATION)'
            ORDER BY 1,2
        """)
        show(db, "ALL functions in project schemas (name only)", """
            SELECT n.nspname AS schema, p.proname, p.prokind
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname IN ('claris','claris_kb','ontology','runtime','state','audit','raw')
            ORDER BY 1,2
        """)
        show(db, "any table anywhere whose name suggests staging/history/overlay", """
            SELECT table_schema, table_name FROM information_schema.tables
            WHERE table_name ~* '(overlay|staging|stage|history|archive|backup|audit|snapshot|import|load)'
              AND table_schema NOT IN ('pg_catalog','information_schema')
            ORDER BY 1,2
        """)
        show(db, "readable schemas for this principal", """
            SELECT nspname, has_schema_privilege(nspname,'USAGE') AS usage
            FROM pg_namespace
            WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
            ORDER BY 1
        """)

        # ==============================================================
        head("6. SECTION 18/27 -- POLICY v1.1 AND VIEW DRIFT")
        show(db, "anything mentioning v1.1 in kb_artifact metadata", """
            SELECT kb_version, kb_json->'policy_version' AS policy_in_json,
                   policy_version AS policy_column
            FROM claris_kb.kb_artifact ORDER BY kb_version
        """)
        show(db, "the three 1.0.1-pinned view definitions", """
            SELECT viewname, definition FROM pg_views
            WHERE schemaname='claris_kb'
              AND viewname IN ('v_active_ontology_notes','v_active_identity_rules','v_active_actors')
            ORDER BY 1
        """, width=1200)

        # ==============================================================
        head("7. AFTER WITNESS")
        after_counts, after_kb = row_counts(db), kb_status_fingerprint(db)
        after_digest = db.query(
            "SELECT kb_version, content_digest, count(*) OVER () AS active_n "
            "FROM claris_kb.kb_artifact WHERE status='ACTIVE'")
        print(f"   AFTER : {after_counts}")
        print(f"   ACTIVE digest: {after_digest}")
        ok = (after_counts == before_counts and after_kb == before_kb
              and after_digest == before_digest)
        print(f"   counts identical        : {after_counts == before_counts}")
        print(f"   KB fingerprint identical: {after_kb == before_kb}")
        print(f"   ACTIVE digest identical : {after_digest == before_digest}")
        print(f"   session_is_read_only()  : {db.session_is_read_only()}")
        if not ok:
            print("   *** D.4G.1C FAILED -- FORENSIC DISCOVERY MUTATED STATE ***")
            return 1
        print("\n   D.4G.1C FORENSIC READ COMPLETE -- ZERO MUTATIONS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
