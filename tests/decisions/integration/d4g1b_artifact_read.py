r"""STEP 5G.6 PHASE D.4G.1B -- READ-ONLY read of the ACTIVE KB artifact.

The deployed ontology revision 2026.10-governance is not in the repository and
schema `ontology` is unreadable. But claris_kb.kb_artifact.kb_json IS readable
by claris_ingestion and carries 14 compiled sections -- including
ontology_notes and configuration_dimensions. That is an ALREADY-AUTHORIZED
path to deployed governance content, and this reads it.

Compiled output is NOT treated as equivalent to authoritative source; sections
absent from the artifact are reported absent, never inferred.

    .\venv\Scripts\python.exe tests\decisions\integration\d4g1b_artifact_read.py
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


def show(db, label, sql, params=None, width=1500):
    print(f"\n-- {label} " + "-" * max(0, 64 - len(label)))
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   [UNAVAILABLE] {type(exc).__name__}: {str(exc).strip()[:250]}")
        return []
    if not rows:
        print("   (no rows / ABSENT)")
        return rows
    for row in rows:
        if len(row) == 1:
            (v,) = row.values()
            t = "NULL" if v is None else str(v)[:width]
        else:
            t = " | ".join(f"{k}={'NULL' if v is None else str(v)[:width]}"
                           for k, v in row.items())
        print("   " + t.encode("ascii", "replace").decode("ascii"))
    return rows


def main() -> int:
    with read_only_connection() as db:
        print("=" * 78 + "\nD.4G.1B -- ACTIVE KB ARTIFACT AS DEPLOYED-GOVERNANCE EVIDENCE\n" + "=" * 78)
        print(f"   session_is_read_only(): {db.session_is_read_only()}")
        before_counts, before_kb = row_counts(db), kb_status_fingerprint(db)
        print(f"   BEFORE: {before_counts}")

        show(db, "artifact identity", """
            SELECT kb_version, ontology_version,
                   coalesce(policy_version,'<NULL>') AS policy_version,
                   status, source_system, source_catalog, source_schema,
                   generated_at, deployed_at, content_digest
            FROM claris_kb.kb_artifact WHERE status='ACTIVE'
        """)

        show(db, "sections present in ACTIVE kb_json + element counts", """
            SELECT k AS section,
                   CASE jsonb_typeof(a.kb_json->'sections'->k)
                        WHEN 'array' THEN jsonb_array_length(a.kb_json->'sections'->k)
                        ELSE NULL END AS n_elements,
                   jsonb_typeof(a.kb_json->'sections'->k) AS json_type
            FROM claris_kb.kb_artifact a,
                 jsonb_object_keys(a.kb_json->'sections') k
            WHERE a.status='ACTIVE' ORDER BY 1
        """)
        show(db, "top-level kb_json keys (metadata outside 'sections')", """
            SELECT jsonb_object_keys(kb_json) AS top_level_key
            FROM claris_kb.kb_artifact WHERE status='ACTIVE' ORDER BY 1
        """)
        show(db, "kb_metadata block if present", """
            SELECT kb_json - 'sections' AS metadata
            FROM claris_kb.kb_artifact WHERE status='ACTIVE'
        """)

        # ---- Q-002 as DEPLOYED -------------------------------------
        show(db, "DEPLOYED ontology_notes (Q-001..Q-00n)", """
            SELECT n AS note
            FROM claris_kb.kb_artifact a,
                 jsonb_array_elements(a.kb_json->'sections'->'ontology_notes') n
            WHERE a.status='ACTIVE'
        """)
        show(db, "DEPLOYED ontology_notes projected into claris_kb", """
            SELECT * FROM claris_kb.ontology_notes ORDER BY 1,2
        """)
        show(db, "DEPLOYED v_active_ontology_notes", """
            SELECT * FROM claris_kb.v_active_ontology_notes
        """)

        # ---- dimensions as DEPLOYED --------------------------------
        show(db, "DEPLOYED configuration_dimensions (kb_json)", """
            SELECT d AS dimension
            FROM claris_kb.kb_artifact a,
                 jsonb_array_elements(a.kb_json->'sections'->'configuration_dimensions') d
            WHERE a.status='ACTIVE'
        """)
        show(db, "DEPLOYED configuration_dimensions projected table", """
            SELECT * FROM claris_kb.configuration_dimensions ORDER BY 1,2
        """)

        # ---- decisions / outputs / inputs as DEPLOYED --------------
        show(db, "DEPLOYED decisions section (kb_json)", """
            SELECT d AS decision
            FROM claris_kb.kb_artifact a,
                 jsonb_array_elements(a.kb_json->'sections'->'decisions') d
            WHERE a.status='ACTIVE'
        """)
        show(db, "DEPLOYED decision_outputs section (kb_json)", """
            SELECT o AS decision_output
            FROM claris_kb.kb_artifact a,
                 jsonb_array_elements(a.kb_json->'sections'->'decision_outputs') o
            WHERE a.status='ACTIVE'
        """)
        show(db, "DEPLOYED use_cases mentioning identity", """
            SELECT u AS use_case
            FROM claris_kb.kb_artifact a,
                 jsonb_array_elements(a.kb_json->'sections'->'use_cases') u
            WHERE a.status='ACTIVE' AND u::text ILIKE '%identit%'
        """)

        # ---- sections the parent has that the artifact may NOT -----
        show(db, "ABSENCE CHECK: sections NOT in the ACTIVE artifact", """
            SELECT s AS expected_section,
                   (SELECT a.kb_json->'sections' ? s
                    FROM claris_kb.kb_artifact a WHERE a.status='ACTIVE') AS present
            FROM unnest(ARRAY['decision_reason_code','enums','enum_values',
                              'action_types','action_authorizations','read_grants',
                              'roles','decision_dependencies','open_questions',
                              'ontology_notes','configuration_dimensions',
                              'contradiction_checks','policy_versions']) s
            ORDER BY 1
        """)

        after_counts, after_kb = row_counts(db), kb_status_fingerprint(db)
        print("\n" + "=" * 78 + "\nAFTER WITNESS\n" + "=" * 78)
        print(f"   AFTER : {after_counts}")
        print(f"   counts identical        : {after_counts == before_counts}")
        print(f"   KB fingerprint identical: {after_kb == before_kb}")
        print(f"   session_is_read_only()  : {db.session_is_read_only()}")
        if after_counts != before_counts or after_kb != before_kb:
            print("   *** D.4G.1B FAILED -- GOVERNED STATE MUTATED ***")
            return 1
        print("\n   D.4G.1B ARTIFACT READ COMPLETE -- ZERO MUTATIONS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(2)
