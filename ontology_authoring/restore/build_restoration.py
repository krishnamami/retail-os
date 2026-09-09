"""Deterministically build the D.4G.1G.5 restoration from repository 2026.10.

READ ONLY with respect to every existing artifact. Parses
``ontology/source/claris_ontology.sql`` and emits:

    ontology_authoring/restore/002_restore_2026_10.sql
    ontology_authoring/restore/restoration_provenance.md

The generated SQL is NOT executed by this script. Nothing here connects to a
database.

Restoration is conservative by construction. Every transformation that lowers
a governance claim is recorded in the provenance report; no transformation
raises one. In particular a source row marked ``confirmed`` without a
``confirmed_by`` / ``confirmed_on`` signature is restored as *proposed*,
because an unsigned confirmation is not a confirmation.
"""

from __future__ import annotations

import hashlib
import io
import os
import re

DOMAIN = "retail"
ONTOLOGY_VERSION = "2026.10"
RESTORED_BY = "engineering:D.4G.1G.5"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SOURCE = os.path.join(ROOT, "ontology", "source", "claris_ontology.sql")
OUT_SQL = os.path.join(HERE, "002_restore_2026_10.sql")
OUT_DOC = os.path.join(HERE, "restoration_provenance.md")

# Reason codes are promoted out of enum_values into their own table, so that
# a reason code can carry governance state. enum_values has no such columns.
PROMOTED_ENUM = "decision_reason_code"
DECISION_SPECIFIC_REASONS = {"IDENTITY_POLICY_NOT_DEFINED": "IDENTITY_ASSESSMENT"}


# --------------------------------------------------------------------------
# source parsing
# --------------------------------------------------------------------------

def read_source():
    with io.open(SOURCE, encoding="utf-8") as handle:
        return handle.read()


def source_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_tuple(body):
    """Split one VALUES tuple into raw fields, honouring \\' escapes."""
    fields, buf, in_str, escaped = [], [], False, False
    for ch in body:
        if in_str:
            if escaped:
                buf.append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_str = False
                buf.append(ch)
            else:
                buf.append(ch)
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == ",":
            fields.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    fields.append("".join(buf).strip())
    return fields


def _unquote(field):
    if field.upper() == "NULL":
        return None
    if field.startswith("'") and field.endswith("'"):
        return field[1:-1].replace("\\'", "'")
    if field.upper() in ("TRUE", "FALSE"):
        return field.upper() == "TRUE"
    try:
        return int(field)
    except ValueError:
        return field


def rows_of(text, table):
    """Every VALUES tuple of one source table, as lists of python values."""
    pattern = (r"CREATE OR REPLACE TABLE claris\.retail_ontology\." + table
               + r"\s*\(.*?\nINSERT INTO [^\n]*\n(.*?)(?=\nCREATE OR REPLACE |\Z)")
    match = re.search(pattern, text, re.S)
    if not match:
        raise LookupError("source table not found: %s" % table)
    out = []
    depth, buf = 0, []
    in_str, escaped = False, False
    for ch in match.group(1):
        if in_str:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_str = False
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == "(":
            depth += 1
            if depth == 1:
                buf = []
            else:
                buf.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:
                out.append([_unquote(f) for f in _split_tuple("".join(buf))])
            else:
                buf.append(ch)
        elif depth:
            buf.append(ch)
    return out


# --------------------------------------------------------------------------
# SQL emission
# --------------------------------------------------------------------------

def lit(value):
    if value is None:
        return "NULL"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert(table, columns, records):
    if not records:
        return "-- %s: no rows restored\n" % table
    head = "INSERT INTO ontology_authoring.%s\n    (%s)\nVALUES\n" % (
        table, ", ".join(columns))
    body = ",\n".join(
        "    (" + ", ".join(lit(v) for v in rec) + ")" for rec in records)
    return head + body + ";\n"


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build():
    text = read_source()
    digest = source_digest(text)
    notes = []          # provenance entries
    chunks = []
    counts = {}

    def record(subject, field, was, now, why):
        notes.append((subject, field, was, now, why))

    # ---- 1. ontology_release -------------------------------------------
    src_release = rows_of(text, "ontology_release")[0]
    release = [[DOMAIN, ONTOLOGY_VERSION, src_release[2], "draft",
                "AUTHORITATIVE", None, None, None,
                "repository:ontology/source/claris_ontology.sql",
                src_release[4], digest, RESTORED_BY]]
    record("ontology_release", "status", src_release[3], "draft",
           "A restored release begins as a draft. Publication is a separate, "
           "deliberate act and a draft cannot compile.")
    chunks.append(insert("ontology_release",
        ["domain", "ontology_version", "description", "status",
         "release_class", "validation_status", "parent_ontology_version",
         "parent_release_class", "source_namespace", "source_sha256",
         "content_digest", "created_by"], release))
    counts["ontology_release"] = len(release)

    # ---- 2. actors ------------------------------------------------------
    actors = [[DOMAIN, ONTOLOGY_VERSION, r[2], r[3], r[4], r[5], r[6] or None,
               r[7] or None, r[8]] for r in rows_of(text, "actors")]
    chunks.append(insert("actors",
        ["domain", "ontology_version", "actor", "ordinal", "display_name",
         "actor_kind", "members", "owns_steps_today", "responsibility"], actors))
    counts["actors"] = len(actors)
    record("departments", "table", "7 rows", "not restored",
           "departments is 1:1 with actors, which already carries actor_kind "
           "(department | joint_body | machine) and members. Restoring both "
           "would duplicate the authority registry.")

    # ---- 3. ontology_notes ---------------------------------------------
    notes_rows = []
    for r in rows_of(text, "ontology_notes"):
        _, _, note_id, ordinal, subject, question, blocks, owner, status = r
        notes_rows.append([DOMAIN, ONTOLOGY_VERSION, note_id, ordinal, subject,
                           question, blocks, owner, "OPEN"])
    chunks.append(insert("ontology_notes",
        ["domain", "ontology_version", "note_id", "ordinal", "subject",
         "question", "blocks", "owner", "status"], notes_rows))
    counts["ontology_notes"] = len(notes_rows)
    record("ontology_notes (all 7)", "authority", "not restored", "NULL",
           "2026.10 records a proposed owner, not a confirmed authority. "
           "Populating authority would pre-empt Q-012.")

    # ---- 4. enums / enum_values ----------------------------------------
    enums = [[DOMAIN, ONTOLOGY_VERSION, r[2], r[3], r[4]]
             for r in rows_of(text, "enums") if r[2] != PROMOTED_ENUM]
    chunks.append(insert("enums",
        ["domain", "ontology_version", "enum_name", "ordinal",
         "semantic_definition"], enums))
    counts["enums"] = len(enums)

    reason_rows, value_rows = [], []
    for r in rows_of(text, "enum_values"):
        _, _, enum_name, value, ordinal, definition = r
        if enum_name == PROMOTED_ENUM:
            decision = DECISION_SPECIFIC_REASONS.get(value)
            reason_rows.append([DOMAIN, ONTOLOGY_VERSION, value, ordinal,
                                "DECISION_SPECIFIC" if decision else "PLATFORM",
                                decision, definition, "PROPOSED"])
        else:
            value_rows.append([DOMAIN, ONTOLOGY_VERSION, enum_name, value,
                               ordinal, definition])
    chunks.append(insert("enum_values",
        ["domain", "ontology_version", "enum_name", "value", "ordinal",
         "semantic_definition"], value_rows))
    counts["enum_values"] = len(value_rows)
    record("enum decision_reason_code", "location",
           "enums + enum_values", "decision_reason_codes table",
           "enum_values carries no governance_state, authority or signature, "
           "so a reason code could not hold confirmation state as an enum row.")

    # ---- 5. configuration_dimensions -----------------------------------
    dimensions = []
    for r in rows_of(text, "configuration_dimensions"):
        (_, _, dimension, ordinal, label, data_type, identity_affecting,
         governance_state, blocks_ia, proposed_ia, pricing, entitlement,
         hierarchy, rationale, impact, authority, owner, status,
         eff_from, eff_to, confirmed_by, confirmed_on) = r

        signed = confirmed_by is not None and confirmed_on is not None
        if identity_affecting != "UNKNOWN" and not signed:
            record("configuration_dimensions.%s" % dimension,
                   "identity_affecting", identity_affecting, "UNKNOWN",
                   "Source marked it %s / %s but confirmed_by and confirmed_on "
                   "are NULL. An unsigned confirmation is not a confirmation."
                   % (identity_affecting, governance_state))
            record("configuration_dimensions.%s" % dimension,
                   "governance_state", governance_state, "PROPOSED",
                   "Follows the identity_affecting downgrade.")
            record("configuration_dimensions.%s" % dimension,
                   "status", status, "proposed", "Follows the downgrade.")
            identity_affecting = "UNKNOWN"
            governance_state = "PROPOSED"
            status = "proposed"

        new_blocks = identity_affecting == "UNKNOWN"
        if bool(blocks_ia) != new_blocks:
            record("configuration_dimensions.%s" % dimension,
                   "blocks_identity_assessment", blocks_ia, new_blocks,
                   "Derived: a dimension at UNKNOWN blocks IDENTITY_ASSESSMENT. "
                   "The change is in the conservative direction only.")

        if authority is not None:
            record("configuration_dimensions.%s" % dimension, "authority",
                   authority, "NULL",
                   "2026.10's authority value is a proposal on an unsigned row. "
                   "Restoring it would assert what Q-012 exists to confirm.")

        dimensions.append([DOMAIN, ONTOLOGY_VERSION, dimension, ordinal,
                           "AUTHORITATIVE", "AUTHORITATIVE", label,
                           data_type, identity_affecting, proposed_ia,
                           governance_state, new_blocks, pricing, entitlement,
                           hierarchy, rationale, impact, owner, None, status,
                           eff_from, eff_to])
    chunks.append(insert("configuration_dimensions",
        ["domain", "ontology_version", "dimension", "ordinal",
         "release_class", "governance_basis", "label",
         "data_type", "identity_affecting", "proposed_identity_affecting",
         "governance_state", "blocks_identity_assessment", "pricing_affecting",
         "entitlement_affecting", "hierarchy_affecting", "rationale",
         "impact_if_wrong", "owner", "authority", "status", "effective_from",
         "effective_to"], dimensions))
    counts["configuration_dimensions"] = len(dimensions)

    # ---- 6. identity_rules ---------------------------------------------
    rules = []
    for r in rows_of(text, "identity_rules"):
        (_, _, rule, ordinal, change_type, reads_dimension, condition,
         proposed_effect, observed, rationale, owner, status,
         confirmed_by, confirmed_on) = r
        signed = confirmed_by is not None and confirmed_on is not None
        if status == "confirmed" and not signed:
            record("identity_rules.%s" % rule, "status", "confirmed",
                   "proposed",
                   "Source marked it confirmed but confirmed_by and "
                   "confirmed_on are NULL.")
            status = "proposed"
        rules.append([DOMAIN, ONTOLOGY_VERSION, rule, ordinal,
                      "AUTHORITATIVE", "AUTHORITATIVE", change_type,
                      reads_dimension, condition, proposed_effect, None,
                      "PROPOSED", observed, rationale, owner, None, status])
    chunks.append(insert("identity_rules",
        ["domain", "ontology_version", "rule", "ordinal",
         "release_class", "governance_basis", "change_type",
         "reads_dimension", "condition_expression", "proposed_effect",
         "identity_effect", "governance_state", "observed_materials",
         "rationale", "owner", "authority", "status"], rules))
    counts["identity_rules"] = len(rules)
    record("identity_rules (all 9)", "identity_effect", "not present in source",
           "NULL",
           "Only proposed_effect exists at 2026.10. The confirmed effect stays "
           "NULL until an authority signs it.")

    # ---- 7. decisions ---------------------------------------------------
    decisions = []
    for r in rows_of(text, "decisions"):
        (_, _, decision, ordinal, subject_type, question, mode,
         accountable, phase, replaces, blocked_on) = r
        blocked_by = "Q-002" if decision == "IDENTITY_ASSESSMENT" else None
        if blocked_by:
            record("decisions.IDENTITY_ASSESSMENT", "blocked_by_note",
                   blocked_on, "Q-002",
                   "Normalized: the free-text blocker names exactly what Q-002 "
                   "asks, and Q-002.blocks names IDENTITY_ASSESSMENT. Both "
                   "sides of the link are in the source.")
        decisions.append([DOMAIN, ONTOLOGY_VERSION, decision, ordinal,
                          subject_type, question, mode, accountable, None,
                          "proposed", phase, replaces or None, blocked_on,
                          blocked_by])
    chunks.append(insert("decisions",
        ["domain", "ontology_version", "decision", "ordinal", "subject_type",
         "question", "mode", "accountable_actor", "authority", "status",
         "phase", "replaces_today", "blocked_on", "blocked_by_note"], decisions))
    counts["decisions"] = len(decisions)

    # ---- 8. decision_outputs -------------------------------------------
    outputs = [[DOMAIN, ONTOLOGY_VERSION, r[2], r[3], r[4],
                "AUTHORITATIVE", "AUTHORITATIVE", r[5], r[6],
                "PROPOSED"] for r in rows_of(text, "decision_outputs")]
    chunks.append(insert("decision_outputs",
        ["domain", "ontology_version", "decision", "outcome", "ordinal",
         "release_class", "governance_basis", "semantic_definition",
         "entitles_actions", "governance_state"], outputs))
    counts["decision_outputs"] = len(outputs)

    # ---- 9. decision_reason_codes --------------------------------------
    chunks.append(insert("decision_reason_codes",
        ["domain", "ontology_version", "reason_code", "ordinal", "scope",
         "decision_type", "semantic_definition", "governance_state"],
        reason_rows))
    counts["decision_reason_codes"] = len(reason_rows)

    # ---- 10. decision_dependencies -------------------------------------
    deps = [[DOMAIN, ONTOLOGY_VERSION, r[2], r[3], r[4], None, "HARD_GATE",
             r[5], r[6]] for r in rows_of(text, "decision_dependencies")]
    chunks.append(insert("decision_dependencies",
        ["domain", "ontology_version", "decision", "depends_on", "ordinal",
         "required_outcome", "dependency_type", "upstream_actor",
         "upstream_phase"], deps))
    counts["decision_dependencies"] = len(deps)
    record("decision_dependencies (all 4)", "required_outcome",
           "not present in source", "NULL",
           "2026.10 records the dependency but not which upstream outcome "
           "satisfies it. Inferring one would be inventing governance.")

    # ---- 11. projection_rules ------------------------------------------
    projections = []
    for r in rows_of(text, "projection_rules"):
        (_, _, rule, ordinal, source_object, target_system, proposed_action,
         requires_new, rationale, owner, status, confirmed_by,
         confirmed_on) = r
        projections.append([DOMAIN, ONTOLOGY_VERSION, rule, ordinal,
                            source_object, target_system, proposed_action,
                            None, requires_new, rationale, owner, None, status])
    chunks.append(insert("projection_rules",
        ["domain", "ontology_version", "rule", "ordinal", "source_object",
         "target_system", "proposed_action", "projection_reason",
         "requires_new_target_identity", "rationale", "owner", "authority",
         "status"], projections))
    counts["projection_rules"] = len(projections)
    record("projection_rules (all 4)", "projection_reason",
           "not present per rule", "NULL",
           "projection_reason is recorded per row in projection_matrix, which "
           "is a derived table and is not restored as authoring content.")

    # ---- 12. evidence_reference ----------------------------------------
    chunks.append("-- evidence_reference: 0 rows. No governance evidence "
                  "exists yet.\n")
    counts["evidence_reference"] = 0

    return chunks, counts, notes, digest


HEADER = """-- ============================================================================
-- Restoration of repository 2026.10 into ontology_authoring
-- ============================================================================
-- GENERATED by ontology_authoring/restore/build_restoration.py.
-- Do not edit by hand; regenerate.
--
-- Source : ontology/source/claris_ontology.sql
-- Digest : sha256 %s
--
-- NOT EXECUTED. Awaiting explicit authorization (D.4G.1G.5 section 8).
--
-- Every governance value restored here is UNKNOWN, PROPOSED, OPEN or NULL.
-- Nothing in this file confirms an identity semantic, closes a question,
-- names an authority, or makes any decision executable.
-- ============================================================================

SET search_path = ontology_authoring;

BEGIN;

"""

FOOTER = """
COMMIT;
"""


def main():
    chunks, counts, notes, digest = build()
    with io.open(OUT_SQL, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(HEADER % digest)
        handle.write("\n".join(chunks))
        handle.write(FOOTER)

    lines = ["# Restoration provenance -- repository 2026.10 to ontology_authoring",
             "", "Phase: STEP 5G.6 / D.4G.1G.5", "",
             "Source: `ontology/source/claris_ontology.sql`", "",
             "Source digest: `sha256 %s`" % digest, "",
             "Source ontology version: `%s`" % ONTOLOGY_VERSION, "",
             "Generated by `ontology_authoring/restore/build_restoration.py`. "
             "Not executed.", "",
             "## Restored row counts", "",
             "| Table | Rows |", "|---|---|"]
    for table in sorted(counts):
        lines.append("| `%s` | %d |" % (table, counts[table]))
    lines += ["| **total** | **%d** |" % sum(counts.values()), "",
              "## Transformations", "",
              "Every entry below lowers or withholds a governance claim. "
              "No entry raises one.", "",
              "| Subject | Field | Source | Restored | Why |", "|---|---|---|---|---|"]
    for subject, field, was, now, why in notes:
        lines.append("| `%s` | `%s` | %s | %s | %s |" % (
            subject, field, "`%s`" % was, "`%s`" % now, why))
    lines += ["", "## Not restored", "",
              "- `object_types`, `object_properties`, `links`, `phases`, "
              "`use_cases`, `evidence_types`, `inference_rules`, "
              "`contradiction_checks` -- deferred technical metadata.",
              "- `change_impact`, `projection_matrix` -- derived from identity "
              "rules and projection rules; recomputed as views, never authored.",
              "- `configuration_dimension_values` -- deferred.",
              "- `example_configuration_versions`, `example_configuration_values`, "
              "`example_projections` -- sample data, not governance.",
              "- `departments` -- collapsed into `actors`.",
              "", "## Sources deliberately NOT used", "",
              "- live `ontology` KB 1.0 -- frozen legacy, disjoint vocabulary",
              "- KB 1.0.1 -- verified comparison witness only, never an "
              "authoring source",
              "- KB 1.1 -- frozen forensic artifact, never imported",
              "- `claris_kb` projections -- projections are never a source", ""]
    with io.open(OUT_DOC, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))

    print("restored rows:", sum(counts.values()))
    for table in sorted(counts):
        print("   %-28s %d" % (table, counts[table]))
    print("transformations recorded:", len(notes))


if __name__ == "__main__":
    main()
