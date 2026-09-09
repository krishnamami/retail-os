r"""CLARIS VERTICAL SLICE -- discovery (READ ONLY, zero mutations).

Establishes, from the LIVE database rather than from repository DDL, exactly
what the vertical slice has to work with.

CORRECTION (second run)
-----------------------
The first version named raw.raw_event columns it had read out of a repository
DDL file -- business_object_type, business_object_id -- and the live table has
neither. That is the same defect three times over now, so this version does not
name a column it has not first seen in information_schema, and no single failing
query can end the run: every section reports its own failure and discovery
continues.

    .\venv\Scripts\python.exe tests\decisions\integration\vslice_discovery.py
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

FAILED: list = []


def head(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def sub(title: str) -> None:
    print(f"\n-- {title}")


def show(rows, limit: int = 40, indent: str = "   ") -> None:
    if not rows:
        print(f"{indent}(no rows)")
        return
    for row in rows[:limit]:
        if isinstance(row, dict):
            print(indent + " | ".join(f"{k}={row[k]!r}" for k in row))
        else:
            print(indent + repr(row))
    if len(rows) > limit:
        print(f"{indent}... {len(rows) - limit} more")


def q(db, label, sql, params=None, limit: int = 40):
    """Run one read. A failure is reported and discovery continues."""
    sub(label)
    try:
        rows = db.query(sql, params)
    except Exception as exc:  # noqa: BLE001
        print(f"   QUERY FAILED: {type(exc).__name__}: {str(exc).strip()[:300]}")
        FAILED.append(label)
        return []
    show(rows, limit=limit)
    return rows


def table_exists(db, schema: str, table: str) -> bool:
    try:
        return bool(db.scalar("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema=%s AND table_name=%s""", (schema, table)))
    except Exception:  # noqa: BLE001
        return False


def columns_of(db, schema: str, table: str) -> list:
    return db.query("""
        SELECT column_name, data_type, is_nullable, column_default,
               character_maximum_length, numeric_precision
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
        ORDER BY ordinal_position""", (schema, table))


def describe(db, schema: str, table: str, count: bool = True) -> list:
    """Print the real shape. Returns the live column names, or []."""
    sub(f"{schema}.{table}")
    if not table_exists(db, schema, table):
        print("   DOES NOT EXIST")
        return []
    cols = columns_of(db, schema, table)
    for c in cols:
        default = f" default={c['column_default']}" if c["column_default"] else ""
        null = "" if c["is_nullable"] == "YES" else " NOT NULL"
        # the width is part of the type. Printing 'character varying' without
        # it is how code gets written against a column that cannot hold what it
        # is given -- which is exactly what happened to identity_digest.
        width = (f"({c['character_maximum_length']})"
                 if c.get("character_maximum_length") else "")
        print(f"   {c['column_name']:<30} {c['data_type']}{width}{null}{default}")
    if count:
        try:
            print(f"   rows: {db.scalar(f'SELECT count(*) FROM {schema}.{table}')}")
        except Exception as exc:  # noqa: BLE001
            print(f"   count failed: {exc}")
    return [c["column_name"] for c in cols]


def pick(available, *candidates):
    """The first candidate column this deployment actually has."""
    for name in candidates:
        if name in available:
            return name
    return None


def main() -> int:
    with read_only_connection() as db:
        head("0. CONNECTION")
        for k, v in db.context().items():
            print(f"   {k:<16} {v}")

        # ==================================================================
        head("1. ACTIVE GOVERNANCE -- both doors")
        q(db, "claris_kb.kb_artifact", """
            SELECT kb_version, ontology_version, status, release_class,
                   governance_basis, validation_status,
                   left(content_digest,16)||'...' AS digest
            FROM claris_kb.kb_artifact ORDER BY kb_version""")
        q(db, "v_active_kb (production)", "SELECT * FROM claris_kb.v_active_kb")
        q(db, "v_active_prototype_kb", "SELECT * FROM claris_kb.v_active_prototype_kb")

        sub("prototype artifact payload -- section row counts")
        payload = None
        try:
            payload = db.scalar("""
                SELECT kb_json FROM claris_kb.kb_artifact
                WHERE status='ACTIVE' AND release_class='PROTOTYPE'""")
        except Exception as exc:  # noqa: BLE001
            print(f"   FAILED: {exc}")
            FAILED.append("prototype payload")
        if payload is None:
            print("   no active prototype artifact")
        else:
            if isinstance(payload, str):
                payload = json.loads(payload)
            for name, rows in sorted(payload.get("sections", {}).items()):
                print(f"   {name:<28} {len(rows)}")
            sub("decision_rule_bindings as compiled (what can execute)")
            for r in payload["sections"].get("decision_rule_bindings", []):
                print(f"   {r['rule_id']:<14} {r['rule_class']:<6} "
                      f"prec={r['precedence']:<3} {r['predicate_name']:<38} "
                      f"-> {r['expected_outcome']}")
            sub("decision_outputs (governed outcome vocabulary)")
            for r in sorted(payload["sections"].get("decision_outputs", []),
                            key=lambda x: x["ordinal"]):
                print(f"   {r['ordinal']}  {r['outcome']}")

        # ==================================================================
        head("2. RAW CORPUS -- columns read from the live table, never assumed")
        raw_cols = describe(db, "raw", "raw_event")
        if raw_cols:
            type_col = pick(raw_cols, "event_type", "record_type", "type")
            time_col = pick(raw_cols, "occurred_at", "recorded_at", "arrival_at",
                            "ingested_at", "created_at")
            src_col = pick(raw_cols, "source_record_id", "source_id", "external_id")
            obj_col = pick(raw_cols, "business_object_id", "object_id",
                           "subject_id", "entity_id")
            obj_type_col = pick(raw_cols, "business_object_type", "object_type",
                                "subject_type", "entity_type")
            pay_col = pick(raw_cols, "payload", "payload_json", "body", "data",
                           "raw_payload", "event_payload")
            print(f"\n   using: type={type_col} time={time_col} source={src_col} "
                  f"object={obj_col} object_type={obj_type_col} payload={pay_col}")

            if type_col:
                q(db, f"by {type_col}", f"""
                    SELECT {type_col} AS event_type, count(*) AS n
                    FROM raw.raw_event GROUP BY 1 ORDER BY 2 DESC, 1""", limit=60)

            selected = [c for c in (type_col, obj_type_col, obj_col, src_col, time_col)
                        if c]
            if selected and type_col:
                cols_sql = ", ".join(selected)
                order_sql = ", ".join(c for c in (time_col, src_col) if c) or selected[0]
                q(db, "the two prototype event types, in full", f"""
                    SELECT {cols_sql}
                    FROM raw.raw_event
                    WHERE {type_col} IN ('PRODUCT_DEFINED','CONFIGURATION_REQUESTED')
                    ORDER BY {order_sql}""", limit=40)

            if pay_col and type_col:
                sub("prototype payloads, verbatim")
                try:
                    for row in db.query(f"""
                        SELECT {pay_col} AS payload FROM raw.raw_event
                        WHERE {type_col} IN
                              ('PRODUCT_DEFINED','CONFIGURATION_REQUESTED')
                        ORDER BY {(time_col or pay_col)}"""):
                        print(f"   {row['payload']}")
                except Exception as exc:  # noqa: BLE001
                    print(f"   FAILED: {exc}")
                    FAILED.append("prototype payloads")

                sub("payload key vocabulary across ALL raw events")
                try:
                    show(db.query(f"""
                        SELECT k AS payload_key, count(*) AS n
                        FROM raw.raw_event r,
                             LATERAL jsonb_object_keys(
                                 CASE jsonb_typeof(r.{pay_col}::jsonb)
                                      WHEN 'object' THEN r.{pay_col}::jsonb
                                      ELSE '{{}}'::jsonb END) AS k
                        GROUP BY 1 ORDER BY 2 DESC, 1"""), limit=60)
                except Exception as exc:  # noqa: BLE001
                    print(f"   FAILED: {exc}")
                    FAILED.append("payload keys")

            sub("one full raw row, every column")
            try:
                rows = db.query("SELECT * FROM raw.raw_event LIMIT 1")
                if rows:
                    for k, v in rows[0].items():
                        print(f"   {k:<30} {v!r}")
            except Exception as exc:  # noqa: BLE001
                print(f"   FAILED: {exc}")

        # ==================================================================
        head("3. EVIDENCE AND ASSERTIONS")
        ev_cols = describe(db, "runtime", "evidence")
        if ev_cols:
            prop = pick(ev_cols, "property_name", "property", "attribute_name")
            if prop:
                q(db, "evidence property vocabulary", f"""
                    SELECT {prop} AS property_name, count(*) AS n
                    FROM runtime.evidence GROUP BY 1 ORDER BY 1""", limit=60)
            subj = pick(ev_cols, "subject_id", "business_object_id", "entity_id")
            if subj:
                q(db, "evidence subjects", f"""
                    SELECT {subj} AS subject, count(*) AS n
                    FROM runtime.evidence GROUP BY 1 ORDER BY 1""", limit=60)

        as_cols = describe(db, "runtime", "assertion")
        if as_cols:
            prop = pick(as_cols, "property_name", "property", "attribute_name")
            if prop:
                q(db, "assertion property vocabulary", f"""
                    SELECT {prop} AS property_name, count(*) AS n
                    FROM runtime.assertion GROUP BY 1 ORDER BY 1""", limit=60)
            subj = pick(as_cols, "subject_id", "business_object_id", "entity_id")
            if subj:
                q(db, "assertion subjects", f"""
                    SELECT {subj} AS subject, count(*) AS n
                    FROM runtime.assertion GROUP BY 1 ORDER BY 1""", limit=60)
            if prop and subj:
                val = pick(as_cols, "asserted_value", "value", "property_value",
                           "resolved_value")
                if val:
                    q(db, "assertions in full (the identity inputs)", f"""
                        SELECT {subj} AS subject, {prop} AS property, {val} AS value
                        FROM runtime.assertion ORDER BY 1, 2""", limit=80)

        # ==================================================================
        head("4. FOLD -- the governed state the slice will read")
        fold_cols = describe(db, "state", "fold_state_snapshot")
        if fold_cols:
            propcol = pick(fold_cols, "folded_properties")
            if propcol:
                q(db, "folded_properties shape", f"""
                    SELECT jsonb_typeof({propcol}) AS shape, count(*) AS n
                    FROM state.fold_state_snapshot GROUP BY 1""")
            base = [c for c in ("subject_type", "subject_id", "decision_horizon",
                                "fold_status", "kb_version", "policy_version")
                    if c in fold_cols]
            if base:
                q(db, "snapshots", f"""
                    SELECT {', '.join(base)}
                    FROM state.fold_state_snapshot
                    ORDER BY {base[1] if len(base) > 1 else base[0]}""", limit=60)
            if propcol:
                q(db, "folded property vocabulary and states", f"""
                    SELECT p->>'property_name' AS property_name,
                           p->>'fold_state'    AS fold_state,
                           count(*) AS n
                    FROM state.fold_state_snapshot s,
                         LATERAL jsonb_array_elements(
                             CASE jsonb_typeof(s.{propcol})
                                  WHEN 'array' THEN s.{propcol}
                                  ELSE '[]'::jsonb END) AS p
                    GROUP BY 1,2 ORDER BY 1,2""", limit=80)
                q(db, "per-subject identity coverage", f"""
                    SELECT s.subject_id,
                           p->>'property_name' AS property_name,
                           p->>'fold_state'    AS fold_state,
                           p->>'resolved_value' AS resolved_value
                    FROM state.fold_state_snapshot s,
                         LATERAL jsonb_array_elements(
                             CASE jsonb_typeof(s.{propcol})
                                  WHEN 'array' THEN s.{propcol}
                                  ELSE '[]'::jsonb END) AS p
                    WHERE p->>'property_name' IN
                          ('product_reference','geography','term_months',
                           'customer_segment')
                    ORDER BY 1, 2""", limit=120)
                sub("one full snapshot, verbatim")
                try:
                    row = db.query(f"""
                        SELECT subject_id, decision_horizon, {propcol}
                        FROM state.fold_state_snapshot
                        ORDER BY subject_id LIMIT 1""")
                    if row:
                        print(f"   {row[0]['subject_id']} @ {row[0]['decision_horizon']}")
                        props = row[0][propcol]
                        if isinstance(props, str):
                            props = json.loads(props)
                        print("   " + json.dumps(props, indent=2, default=str)[:3000])
                except Exception as exc:  # noqa: BLE001
                    print(f"   FAILED: {exc}")

        # ==================================================================
        head("5. CANONICAL TABLES -- real shapes, not repository DDL")
        for table in ("product", "configuration", "configuration_version",
                      "decision", "decision_evidence", "action_record",
                      "configuration_state", "configuration_assertion"):
            describe(db, "claris", table)

        sub("check constraints on the canonical tables")
        q(db, "constraints", """
            SELECT t.relname AS table_name, c.conname,
                   pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname='claris'
              AND t.relname IN ('product','configuration','configuration_version',
                                'decision','action_record')
            ORDER BY 1, 2""", limit=80)

        # ==================================================================
        head("6. PROJECTION MODEL -- whatever exists")
        q(db, "tables/views matching projection/legacy/sku/material/target", """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_name ILIKE ANY (ARRAY['%projection%','%legacy%','%sku%',
                                              '%material%','%target%'])
              AND table_schema NOT IN ('pg_catalog','information_schema')
            ORDER BY 1,2""", limit=60)
        for schema, table in (("claris", "projection"),
                              ("claris", "legacy_projection"),
                              ("claris", "projection_record"),
                              ("runtime", "projection"),
                              ("ontology_authoring", "projection_rules")):
            if table_exists(db, schema, table):
                describe(db, schema, table)

        q(db, "projection_rules in the AUTHORITATIVE authoring release", """
            SELECT rule, ordinal, source_object, target_system, proposed_action,
                   requires_new_target_identity, status, owner, rationale
            FROM ontology_authoring.projection_rules
            WHERE ontology_version='2026.10'
            ORDER BY ordinal""", limit=20)

        # ==================================================================
        head("7. LEGACY EXECUTABLE RULE SET")
        rule_cols = describe(db, "claris_kb", "decision_rules", count=True)
        if rule_cols:
            dt = pick(rule_cols, "decision_type")
            kbv = pick(rule_cols, "kb_version")
            if dt and kbv:
                q(db, "by decision_type and kb_version", f"""
                    SELECT {dt} AS decision_type, {kbv} AS kb_version, count(*) AS n
                    FROM claris_kb.decision_rules GROUP BY 1,2 ORDER BY 1,2""",
                  limit=40)
            wanted = [c for c in ("decision_rule_id", "kb_version", "precedence",
                                  "outcome_code", "rule_name", "status")
                      if c in rule_cols]
            if dt and wanted:
                q(db, "CHANGE_CLASSIFICATION rules in detail", f"""
                    SELECT {', '.join(wanted)}
                    FROM claris_kb.decision_rules
                    WHERE {dt}='CHANGE_CLASSIFICATION'
                    ORDER BY {'precedence' if 'precedence' in wanted else wanted[0]}""",
                  limit=40)
        q(db, "v_active_decision_rules by decision_type", """
            SELECT decision_type, count(*) AS n
            FROM claris_kb.v_active_decision_rules GROUP BY 1 ORDER BY 1""")

        # ==================================================================
        head("8. RUNTIME FUNCTIONS -- real signatures")
        q(db, "functions", """
            SELECT n.nspname AS schema, p.proname AS name,
                   pg_get_function_identity_arguments(p.oid) AS arguments,
                   pg_get_function_result(p.oid) AS returns
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname IN ('claris','claris_kb','runtime','state','public')
              AND p.proname ~ '(decision|outcome|fold|projection|identity)'
            ORDER BY 1,2""", limit=60)

        # ==================================================================
        head("9. AUTHORING SOURCE")
        sub("row counts per release")
        for table in ("ontology_release", "decisions", "decision_outputs",
                      "decision_rule_bindings", "identity_rules",
                      "configuration_dimensions", "projection_rules",
                      "actors", "enums", "enum_values", "decision_reason_codes",
                      "decision_dependencies", "ontology_notes",
                      "evidence_reference"):
            if not table_exists(db, "ontology_authoring", table):
                print(f"   ontology_authoring.{table:<26} DOES NOT EXIST")
                continue
            try:
                rows = db.query(f"""
                    SELECT ontology_version, count(*) AS n
                    FROM ontology_authoring.{table}
                    GROUP BY 1 ORDER BY 1""")
                counts = ", ".join(f"{r['ontology_version']}={r['n']}" for r in rows)
                print(f"   ontology_authoring.{table:<26} {counts or '(empty)'}")
            except Exception as exc:  # noqa: BLE001
                print(f"   ontology_authoring.{table:<26} FAILED: {exc}")

        describe(db, "ontology_authoring", "decision_rule_bindings", count=False)
        describe(db, "ontology_authoring", "projection_rules", count=False)
        describe(db, "ontology_authoring", "ontology_release", count=False)

        q(db, "the prototype.1 bindings as authored", """
            SELECT rule_id, rule_class, precedence, predicate_name,
                   expected_outcome, status, decision
            FROM ontology_authoring.decision_rule_bindings
            WHERE ontology_version='2026.10-prototype.1'
            ORDER BY precedence""", limit=20)

        # ==================================================================
        head("10. WRITE-SIDE GRANTS the slice will need")
        q(db, "grants", """
            SELECT table_name, privilege_type, grantee
            FROM information_schema.table_privileges
            WHERE table_schema='claris'
              AND table_name IN ('product','configuration','configuration_version',
                                 'decision','action_record')
              AND privilege_type IN ('INSERT','UPDATE','SELECT')
            ORDER BY table_name, grantee, privilege_type""", limit=80)
        q(db, "sequences the canonical tables depend on", """
            SELECT sequence_schema, sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema IN ('claris','runtime','state')
            ORDER BY 1,2""", limit=40)

        head("DISCOVERY COMPLETE -- ZERO MUTATIONS")
        if FAILED:
            print(f"   {len(FAILED)} section(s) could not be read:")
            for item in FAILED:
                print(f"     - {item}")
        else:
            print("   every section read successfully")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
