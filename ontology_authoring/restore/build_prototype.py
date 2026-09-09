"""Build the PROTOTYPE governance release (D.4G.1G.5P.1).

Emits:
    ontology_authoring/restore/003_prototype_2026_10_P1.sql
    ontology_authoring/restore/prototype_assumptions.md

NOT EXECUTED. Nothing here connects to a database.

WHAT THIS RELEASE IS
    A demonstration release. Every governed value in it is a PROTOTYPE
    ASSUMPTION made by engineering, labelled as such, and awaiting validation
    with Claris. It is not Claris-approved and it cannot become so by being
    deployed, compiled or executed.

WHAT IT STRUCTURALLY CANNOT DO
    * occupy configuration_dimensions.identity_affecting  (CHECK)
    * occupy identity_rules.identity_effect               (CHECK)
    * carry governance_state = CONFIRMED                  (CHECK)
    * exist outside a release_class = PROTOTYPE release   (composite FK)
    * be selected by the production resolver              (candidate filter)

    No authority, confirmed_by or confirmed_on is written by this module, and
    none of those columns appears in any INSERT it emits.
"""

from __future__ import annotations

import io
import os

from build_restoration import (  # noqa: E402  -- same directory, by design
    DOMAIN,
    ONTOLOGY_VERSION as PARENT_VERSION,
    insert,
    rows_of,
    read_source,
    source_digest,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_SQL = os.path.join(HERE, "003_prototype_2026_10_P1.sql")
OUT_DOC = os.path.join(HERE, "prototype_assumptions.md")

PROTOTYPE_VERSION = "2026.10-prototype.1"
RELEASE_CLASS = "PROTOTYPE"
BASIS = "PROTOTYPE_ASSUMPTION"
VALIDATION_STATUS = "TO_BE_VALIDATED_WITH_CLARIS"
BUILT_BY = "engineering:D.4G.1G.5P.1"

DESCRIPTION = (
    "PROTOTYPE. NOT CLARIS APPROVED. FOR DEMONSTRATION ONLY. "
    "Every governed value in this release is an engineering assumption "
    "awaiting validation with Claris. Q-001 through Q-007 remain open."
)

# --------------------------------------------------------------------------
# the locked prototype identity tuple -- D.4E, unchanged at G.5P and here
# --------------------------------------------------------------------------
IDENTITY_TUPLE = ("product_reference", "geography", "term_months",
                  "customer_segment")

# dimension, ordinal, label, in_tuple, prototype_assumption, note
PROTOTYPE_DIMENSIONS = [
    ("product_reference", 0, "Product reference", True, True,
     "PROTOTYPE ASSUMPTION. Prototype-only: 2026.10 has no counterpart. "
     "Q-007 asks whether any identifier spans the process, or identity starts "
     "at the material number."),
    ("geography", 1, "Geography", True, True,
     "PROTOTYPE ASSUMPTION. The prototype's name for the 2026.10 'geo' "
     "dimension, which is UNKNOWN and unsigned there. 63 materials from geo "
     "additions, none replacing an existing material."),
    ("term_months", 2, "Contract term (months)", True, True,
     "PROTOTYPE ASSUMPTION. The prototype's name for the 2026.10 'term' "
     "dimension, which is UNKNOWN and unsigned there. Q-009 asks whether term "
     "months and contract length months are the same business concept."),
    ("customer_segment", 3, "Customer segment", True, True,
     "PROTOTYPE ASSUMPTION. The prototype's name for the 2026.10 'segment' "
     "dimension, which is UNKNOWN and unsigned there."),
    ("user_tier", 4, "User tier", False, False,
     "PROTOTYPE ASSUMPTION -- THE MOST CONSEQUENTIAL ONE IN THIS RELEASE. "
     "Assumed NOT identity-bearing, which is what makes IR-005 conclude "
     "NEW_VERSION and what avoids 78 of the 92 replacement materials in the "
     "corpus. If Claris says user tier IS identity-bearing, IR-005 becomes "
     "CREATE_CONFIGURATION and that saving does not exist. Unvalidated."),
    ("package_format", 5, "Package format", False, False,
     "PROTOTYPE ASSUMPTION WITH A RECORDED CONFLICT. 2026.10 proposes this "
     "dimension IS identity-bearing (IR-006 -> CREATE_CONFIGURATION), but the "
     "locked prototype identity tuple excludes it, so this release assumes "
     "NOT identity-bearing in order to keep the tuple at four properties. "
     "The two assumptions disagree: under this release a repackage yields an "
     "identical canonical identity and the exact-match predicate concludes "
     "NO_BUSINESS_CHANGE, so the CREATE_CONFIGURATION that IR-006 proposes is "
     "unreachable. Recorded, not resolved: resolving it means changing tuple "
     "membership, which G.5P locked."),
    ("description", 6, "Description", False, False,
     "PROTOTYPE ASSUMPTION. Assumed not identity-bearing, matching 2026.10's "
     "own proposal. 2026.10 marks it CONFIRMED but with no confirmed_by or "
     "confirmed_on, so it is unsigned there and unconfirmed here."),
]

# rule, change_type, reads_dimension, proposed_effect, classification, note
PROTOTYPE_RULES = [
    ("IR-001", "new_product_family", None, "CREATE_PRODUCT",
     "SAFE FOR PROTOTYPE",
     "Tautological in the source: a new family is a new commercial product by "
     "definition. Reads no dimension.", None),
    ("IR-002", "geo_add", "geography", "CREATE_CONFIGURATION",
     "ASSUMPTION -- LABEL",
     "63 materials in the corpus came from geo additions and none replaced an "
     "existing material.", None),
    ("IR-003", "term_add", "term_months", "CREATE_CONFIGURATION",
     "ASSUMPTION -- LABEL",
     "33 materials, none replacing an existing one.", None),
    ("IR-004", "segment_add", "customer_segment", "CREATE_CONFIGURATION",
     "ASSUMPTION -- LABEL",
     "19 materials, none replacing an existing one.", None),
    ("IR-005", "tier_restructure", "user_tier", "NEW_VERSION",
     "ASSUMPTION -- PROMINENT LABEL",
     "78 of the 92 materials that replaced an existing material came from "
     "tier restructures. This assumption is what turns them into versions.",
     "PROMINENT LABEL REQUIRED. This is the single most consequential "
     "assumption in the release and the one most expensive to get wrong. Any "
     "figure derived from it must be shown alongside the fact that it is "
     "unvalidated."),
    ("IR-006", "repackage", "package_format", None,
     "BLOCKED EVEN FOR PROTOTYPE",
     "12 materials from repackaging, all replacing an existing one.",
     "NOT EXECUTABLE IN THIS PROTOTYPE (D.4G.2 section 1). 2026.10 proposes "
     "repackage -> CREATE_CONFIGURATION, but package_format is not one of the "
     "four locked identity properties, so the two assumptions cannot both "
     "execute coherently. The rule is retained for provenance with "
     "proposed_effect NULL and status undefined, so no executable derivation "
     "can reach it. A repackage must conclude CANNOT_DECIDE / "
     "IDENTITY_POLICY_NOT_DEFINED, exactly as reclassify/SLP does. Resolving "
     "it means changing tuple membership, which G.5P locked."),
    ("IR-008", "price_change", None, "NEW_VERSION",
     "SAFE FOR PROTOTYPE",
     "Verified against the corpus: three price changes minted nothing. Reads "
     "no dimension.", None),
    ("IR-009", "rename", "description", "NO_BUSINESS_CHANGE",
     "SAFE FOR PROTOTYPE",
     "Verified against the corpus: two renames minted nothing.", None),
]

# EXCLUDED, deliberately. See prototype_assumptions.md.
EXCLUDED_RULES = [
    ("IR-007", "reclassify", "slp_code", "NEW_VERSION",
     "BLOCKED EVEN FOR PROTOTYPE",
     "2026.10 states: NO PROPOSAL POSSIBLE. No definition of SLP exists "
     "anywhere in the process documentation. Its proposed effect rests on an "
     "inference from position in the process, not on knowledge. Executing it "
     "would demonstrate a conclusion about a term we cannot define. A "
     "reclassify change must reach CANNOT_DECIDE / IDENTITY_POLICY_NOT_DEFINED "
     "instead."),
]

PROTOTYPE_OUTCOMES = [
    ("CREATE_PRODUCT", 0, "New product family or business concept."),
    ("CREATE_CONFIGURATION", 1,
     "New sellable identity under an existing product."),
    ("USE_EXISTING", 2,
     "The requested sellable configuration already exists; its identity is "
     "returned rather than a second one created."),
    ("NEW_VERSION", 3,
     "Existing identity, changed business state. No new configuration."),
    ("NO_BUSINESS_CHANGE", 4, "No canonical mutation."),
    ("CANNOT_DECIDE", 5,
     "Required evidence or governing policy is missing. The platform names "
     "the gap rather than defaulting."),
]

# rule_id, predicate_name, rule_class, precedence, expected_outcome, text
PROTOTYPE_BINDINGS = [
    ("IA-PRED-001", "ir_011_missing_required_input", "GUARD", 1,
     "CANNOT_DECIDE", "Missing required identity input."),
    ("IA-PRED-002", "ir_012_contradicted_required_input", "GUARD", 2,
     "CANNOT_DECIDE", "Contradicted required identity input."),
    ("IA-PRED-003", "ir_013_initial_configuration", "MATCH", 5,
     "CREATE_CONFIGURATION", "No configuration exists for this product yet."),
    ("IA-PRED-004", "ir_010_exact_identity_match", "MATCH", 6,
     "NO_BUSINESS_CHANGE", "An active configuration already carries this "
     "canonical identity."),
]
# No FALLBACK. D.4B locked none and inventing one would give the decision a
# terminal outcome no authority sanctioned -- least of all in a demonstration.

DECISION = "IDENTITY_ASSESSMENT"


def build():
    text = read_source()
    digest = source_digest(text)
    chunks, counts = [], {}

    chunks.append(insert("ontology_release",
        ["domain", "ontology_version", "description", "status",
         "release_class", "validation_status", "parent_ontology_version",
         "parent_release_class", "source_namespace", "source_sha256",
         "content_digest", "created_by"],
        [[DOMAIN, PROTOTYPE_VERSION, DESCRIPTION, "draft", RELEASE_CLASS,
          VALIDATION_STATUS, PARENT_VERSION, "AUTHORITATIVE",
          "repository:ontology/source/claris_ontology.sql", None, digest,
          BUILT_BY]]))
    counts["ontology_release"] = 1

    actors = [[DOMAIN, PROTOTYPE_VERSION, r[2], r[3], r[4], r[5],
               r[6] or None, r[7] or None, r[8]]
              for r in rows_of(text, "actors")]
    chunks.append(insert("actors",
        ["domain", "ontology_version", "actor", "ordinal", "display_name",
         "actor_kind", "members", "owns_steps_today", "responsibility"],
        actors))
    counts["actors"] = len(actors)

    src_decision = [r for r in rows_of(text, "decisions") if r[2] == DECISION][0]
    chunks.append(insert("decisions",
        ["domain", "ontology_version", "decision", "ordinal", "subject_type",
         "question", "mode", "accountable_actor", "authority", "status",
         "phase", "blocked_on", "blocked_by_note"],
        [[DOMAIN, PROTOTYPE_VERSION, DECISION, 0, src_decision[4],
          src_decision[5], src_decision[6], src_decision[7], None, "proposed",
          src_decision[8],
          "PROTOTYPE RELEASE. Q-002 remains open in the authoritative release; "
          "this release executes an engineering assumption instead of a "
          "Claris confirmation.", None]]))
    counts["decisions"] = 1

    chunks.append(insert("decision_outputs",
        ["domain", "ontology_version", "decision", "outcome", "ordinal",
         "release_class", "governance_basis", "semantic_definition",
         "governance_state"],
        [[DOMAIN, PROTOTYPE_VERSION, DECISION, code, ordinal, RELEASE_CLASS,
          BASIS, definition, "PROPOSED"]
         for code, ordinal, definition in PROTOTYPE_OUTCOMES]))
    counts["decision_outputs"] = len(PROTOTYPE_OUTCOMES)

    chunks.append(insert("configuration_dimensions",
        ["domain", "ontology_version", "dimension", "ordinal",
         "release_class", "governance_basis", "label", "data_type",
         "identity_affecting", "proposed_identity_affecting",
         "governance_state", "blocks_identity_assessment", "rationale",
         "owner", "authority", "status"],
        [[DOMAIN, PROTOTYPE_VERSION, dimension, ordinal, RELEASE_CLASS, BASIS,
          label, "string", "UNKNOWN", assumption, "PROPOSED", True, note,
          None, None, "proposed"]
         for dimension, ordinal, label, _in_tuple, assumption, note
         in PROTOTYPE_DIMENSIONS]))
    counts["configuration_dimensions"] = len(PROTOTYPE_DIMENSIONS)

    chunks.append(insert("identity_rules",
        ["domain", "ontology_version", "rule", "ordinal", "release_class",
         "governance_basis", "change_type", "reads_dimension",
         "proposed_effect", "identity_effect", "governance_state",
         "rationale", "blocking_note", "owner", "authority", "status"],
        [[DOMAIN, PROTOTYPE_VERSION, rule, index, RELEASE_CLASS, BASIS,
          change_type, reads, effect, None,
          "PROPOSED" if effect else "UNPROPOSED", rationale, note,
          None, None, "proposed" if effect else "undefined"]
         for index, (rule, change_type, reads, effect, _cls, rationale, note)
         in enumerate(PROTOTYPE_RULES)]))
    counts["identity_rules"] = len(PROTOTYPE_RULES)

    chunks.append(insert("decision_rule_bindings",
        ["domain", "ontology_version", "release_class", "governance_basis",
         "decision", "rule_id", "predicate_name", "rule_class", "precedence",
         "expected_outcome", "description", "status"],
        [[DOMAIN, PROTOTYPE_VERSION, RELEASE_CLASS, BASIS, DECISION, rule_id,
          predicate, rule_class, precedence, outcome, description, "proposed"]
         for rule_id, predicate, rule_class, precedence, outcome, description
         in PROTOTYPE_BINDINGS]))
    counts["decision_rule_bindings"] = len(PROTOTYPE_BINDINGS)

    return chunks, counts, digest


HEADER = """-- ============================================================================
-- PROTOTYPE GOVERNANCE RELEASE  %s
-- ============================================================================
--            *** PROTOTYPE -- NOT CLARIS APPROVED ***
--            *** FOR DEMONSTRATION ONLY ***
--            *** TO BE VALIDATED WITH CLARIS ***
--
-- GENERATED by ontology_authoring/restore/build_prototype.py. Do not edit.
-- Parent authoritative release: %s
-- Source digest: sha256 %s
--
-- NOT EXECUTED. Awaiting explicit authorization.
--
-- Every governed value here is an engineering assumption. Nothing in this
-- file is confirmed governance: no row carries an authority, a confirmed_by
-- or a confirmed_on, identity_affecting is UNKNOWN throughout, and
-- identity_effect is NULL throughout. Q-001 through Q-007 remain open in the
-- authoritative release and this release does not close any of them.
--
-- IR-007 (reclassify / SLP) is deliberately ABSENT. See
-- prototype_assumptions.md.
-- ============================================================================

SET search_path = ontology_authoring;

BEGIN;

"""


def main():
    chunks, counts, digest = build()
    with io.open(OUT_SQL, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(HEADER % (PROTOTYPE_VERSION, PARENT_VERSION, digest))
        handle.write("\n".join(chunks))
        handle.write("\nCOMMIT;\n")

    lines = [
        "# Prototype governance assumptions -- %s" % PROTOTYPE_VERSION, "",
        "**PROTOTYPE. NOT CLARIS APPROVED. FOR DEMONSTRATION ONLY.**", "",
        "Validation status: `%s`" % VALIDATION_STATUS, "",
        "Parent authoritative release: `%s`" % PARENT_VERSION, "",
        "Every value below is an engineering assumption. None is confirmed "
        "governance. No authority, signature or evidence is claimed for any "
        "of them, and none may be presented to anyone as a Claris decision.",
        "", "## Locked identity tuple", "",
        "```", " | ".join(IDENTITY_TUPLE), "```", "",
        "Serialization order is the order above. Membership is a **prototype "
        "assumption**, not Claris-confirmed canonical identity.", "",
        "## Dimensions", "",
        "| Dimension | In tuple | Assumed identity-bearing | Note |",
        "|---|---|---|---|"]
    for dimension, _o, _l, in_tuple, assumption, note in PROTOTYPE_DIMENSIONS:
        lines.append("| `%s` | %s | %s | %s |" % (
            dimension, "yes" if in_tuple else "no",
            "yes" if assumption else "no", note))
    lines += ["", "## Change assumptions", "",
              "| Rule | Change | Reads | Assumed effect | Classification |",
              "|---|---|---|---|---|"]
    for rule, change_type, reads, effect, cls, _r, _n in PROTOTYPE_RULES:
        lines.append("| `%s` | `%s` | `%s` | `%s` | **%s** |" % (
            rule, change_type, reads or "-", effect, cls))
    lines += ["", "## Excluded", "",
              "| Rule | Change | Classification | Why |", "|---|---|---|---|"]
    for rule, change_type, _reads, _effect, cls, why in EXCLUDED_RULES:
        lines.append("| `%s` | `%s` | **%s** | %s |" % (
            rule, change_type, cls, why))
    lines += ["", "## Executable predicates", "",
              "| ID | Predicate | Class | Precedence | Concludes |",
              "|---|---|---|---|---|"]
    for rule_id, predicate, rule_class, precedence, outcome, _d in PROTOTYPE_BINDINGS:
        lines.append("| `%s` | `%s` | %s | %d | `%s` |" % (
            rule_id, predicate, rule_class, precedence, outcome))
    lines += ["",
              "No FALLBACK is declared. D.4B locked none, and inventing one "
              "would give the decision a terminal outcome no authority "
              "sanctioned.", "",
              "## Recorded conflicts -- not resolved here", "",
              "- **`IR-006` repackage is not reachable under the locked "
              "tuple.** `package_format` is excluded from the four identity "
              "properties, so a repackage produces an identical canonical "
              "identity and `IA-PRED-004` concludes `NO_BUSINESS_CHANGE` "
              "before `IR-006` is considered. Resolving this means changing "
              "tuple membership, which G.5P locked. Escalated.",
              "- **`IR-005` tier_restructure carries the release's largest "
              "unvalidated claim.** 78 of 92 replacement materials turn on it.",
              "", "## Row counts", "", "| Table | Rows |", "|---|---|"]
    for table in sorted(counts):
        lines.append("| `%s` | %d |" % (table, counts[table]))
    lines += ["| **total** | **%d** |" % sum(counts.values()), ""]

    with io.open(OUT_DOC, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))

    print("prototype rows:", sum(counts.values()))
    for table in sorted(counts):
        print("   %-28s %d" % (table, counts[table]))


if __name__ == "__main__":
    main()
