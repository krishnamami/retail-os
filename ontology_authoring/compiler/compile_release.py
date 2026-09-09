"""Deterministic compiler: one authoring release -> one immutable KB artifact.

CONTRACT (D.4G.1G.3 section W, locked at D.4G.1G.4)

    input   exactly ONE ontology_authoring release, status 'published'
    output  exactly ONE artifact payload + its semantic digest

    fail closed on every validation. A release that cannot be proven valid
    produces no artifact at all, rather than an artifact with a warning.

WHAT THIS COMPILER IS NOT
    It is not the KB 1.1 compiler. That one declared a projection as its own
    source, dropped governance fields, and turned open questions into
    assertions. Nothing here reads claris_kb, the legacy ontology schema, KB
    1.1's kb_json, or a hard-coded rule dictionary. The ONLY source is the
    deployed ontology_authoring rows for the named release.

DETERMINISM
    The semantic payload excludes every wall-clock value. generated_at lives
    in envelope metadata and is NOT digested, so recompiling an unchanged
    release reproduces the digest exactly. Rows are sorted by primary key and
    JSON keys are sorted, so row order in the database cannot change the
    digest either.

PROTOTYPE SAFETY
    A PROTOTYPE_ASSUMPTION never becomes AUTHORITATIVE or CONFIRMED here. The
    compiler copies classification through; it has no code path that raises it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

__all__ = [
    "CompilationError",
    "CompiledArtifact",
    "SECTIONS",
    "SECTION_KEYS",
    "COMPILER_VERSION",
    "DIGEST_ALGORITHM",
    "canonical_json",
    "compile_release",
    "semantic_digest",
]

COMPILER_VERSION = "claris_authoring_compiler/1.0"
DIGEST_ALGORITHM = "sha256"

#: The 14 authoring tables, and the primary key each is sorted by. Order here
#: is the order they appear in the payload; both are part of the digest.
SECTIONS: tuple = (
    ("ontology_release", ("domain", "ontology_version")),
    ("ontology_notes", ("note_id",)),
    ("enums", ("enum_name",)),
    ("enum_values", ("enum_name", "value")),
    ("actors", ("actor",)),
    ("configuration_dimensions", ("dimension",)),
    ("identity_rules", ("rule",)),
    ("decisions", ("decision",)),
    ("decision_outputs", ("decision", "outcome")),
    ("decision_dependencies", ("decision", "depends_on")),
    ("projection_rules", ("rule",)),
    ("decision_reason_codes", ("reason_code",)),
    ("decision_rule_bindings", ("decision", "rule_id")),
    ("evidence_reference", ("evidence_reference_id",)),
)
SECTION_KEYS = tuple(name for name, _ in SECTIONS)

#: evidence_reference is not version-scoped: it is an append-only pointer store
#: shared across releases.
UNVERSIONED = frozenset({"evidence_reference"})

LOCKED_PROTOTYPE_TUPLE = ("product_reference", "geography", "term_months",
                          "customer_segment")


class CompilationError(Exception):
    """Compilation failed a validation. No artifact is produced."""


@dataclass(frozen=True)
class CompiledArtifact:
    domain: str
    ontology_version: str
    release_class: str
    governance_basis: str
    validation_status: str | None
    parent_ontology_version: str | None
    payload: dict
    semantic_digest: str
    census: dict = field(default_factory=dict)

    @property
    def kb_version(self) -> str:
        """Derived, never invented: one release compiles to one artifact."""
        return self.ontology_version


# ----------------------------------------------------------------------
# canonicalisation
# ----------------------------------------------------------------------

def _scalar(value):
    """Render one column deterministically, without inventing a value."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_scalar(v) for v in value]
    return str(value)          # dates, decimals, uuids -> stable text


def canonical_json(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def semantic_digest(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# read
# ----------------------------------------------------------------------

def _rows(db, table, domain, ontology_version, sort_key):
    if table in UNVERSIONED:
        raw = db.query(f"SELECT * FROM ontology_authoring.{table}")
    else:
        raw = db.query(
            f"SELECT * FROM ontology_authoring.{table} "
            "WHERE domain = %s AND ontology_version = %s",
            (domain, ontology_version))
    rows = [{k: _scalar(v) for k, v in row.items()} for row in raw]
    rows.sort(key=lambda r: tuple(str(r.get(k)) for k in sort_key))
    return rows


# ----------------------------------------------------------------------
# validation -- every one fails closed
# ----------------------------------------------------------------------

def _validate(payload, domain, ontology_version, failures):
    releases = payload["ontology_release"]
    if len(releases) != 1:
        failures.append(f"expected exactly one release row, found {len(releases)}")
        return
    release = releases[0]

    if release.get("status") != "published":
        failures.append(
            "a release must be status 'published' to compile; this one is "
            f"{release.get('status')!r}. Publication is a separate, deliberate "
            "act and a draft is not a release")

    release_class = release.get("release_class")
    basis_for_class = {"AUTHORITATIVE": "AUTHORITATIVE",
                       "PROTOTYPE": "PROTOTYPE_ASSUMPTION"}
    if release_class not in basis_for_class:
        failures.append(f"unknown release_class {release_class!r}")
        return
    expected_basis = basis_for_class[release_class]

    if release_class == "PROTOTYPE":
        if release.get("validation_status") != "TO_BE_VALIDATED_WITH_CLARIS":
            failures.append(
                "a prototype release must carry validation_status "
                "TO_BE_VALIDATED_WITH_CLARIS")
        if not release.get("parent_ontology_version"):
            failures.append("a prototype release must name its parent release")
        if release.get("parent_release_class") != "AUTHORITATIVE":
            failures.append(
                "a prototype release must descend from an AUTHORITATIVE one")
    elif release.get("validation_status") is not None:
        failures.append("an authoritative release carries no validation_status")

    # no classification contamination anywhere in the payload
    for section in ("configuration_dimensions", "identity_rules",
                    "decision_outputs", "decision_rule_bindings"):
        for row in payload.get(section, []):
            if "governance_basis" in row and row["governance_basis"] != expected_basis:
                failures.append(
                    f"{section}: {row.get('governance_basis')!r} in a "
                    f"{release_class} release")
            if "release_class" in row and row["release_class"] != release_class:
                failures.append(f"{section}: release_class disagrees with release")

    # a prototype assumption never occupies a confirmed field
    if release_class == "PROTOTYPE":
        for row in payload.get("configuration_dimensions", []):
            if row.get("identity_affecting") != "UNKNOWN":
                failures.append(
                    f"dimension {row.get('dimension')}: a prototype assumption "
                    "cannot occupy identity_affecting")
        for row in payload.get("identity_rules", []):
            if row.get("identity_effect") is not None:
                failures.append(
                    f"rule {row.get('rule')}: a prototype assumption cannot "
                    "occupy identity_effect")

    # referential integrity within the compiled set
    decisions = {r["decision"] for r in payload.get("decisions", [])}
    for row in payload.get("decision_outputs", []):
        if row["decision"] not in decisions:
            failures.append(
                f"decision_output {row['outcome']} references unknown decision "
                f"{row['decision']}")
    outcomes = {(r["decision"], r["outcome"]) for r in payload.get("decision_outputs", [])}

    seen_precedence = {}
    for row in payload.get("decision_rule_bindings", []):
        if row["decision"] not in decisions:
            failures.append(
                f"binding {row['rule_id']} references unknown decision "
                f"{row['decision']}")
        if not row.get("predicate_name"):
            failures.append(
                f"binding {row['rule_id']} names no predicate; an executable "
                "binding must be explicit")
        expected = row.get("expected_outcome")
        if expected and (row["decision"], expected) not in outcomes:
            failures.append(
                f"binding {row['rule_id']} expects outcome {expected!r}, which "
                f"{row['decision']} does not declare")
        slot = (row["decision"], row.get("precedence"))
        if slot in seen_precedence:
            failures.append(
                f"duplicate precedence {row.get('precedence')} on "
                f"{row['decision']}: {seen_precedence[slot]} and {row['rule_id']}")
        seen_precedence[slot] = row["rule_id"]
        if str(row["rule_id"]).startswith("IR-"):
            failures.append(
                f"{row['rule_id']} is a business identity rule id and must not "
                "be bound as an executable predicate")

    # an unresolved rule cannot silently become executable
    for row in payload.get("identity_rules", []):
        unresolved = row.get("proposed_effect") is None
        if unresolved and row.get("governance_state") != "UNPROPOSED":
            failures.append(
                f"rule {row.get('rule')} has no proposed effect but is not "
                "UNPROPOSED; an unresolved rule must be visibly unresolved")

    # the locked identity tuple, for a prototype release
    if release_class == "PROTOTYPE":
        tuple_members = [r["dimension"] for r in
                         sorted(payload.get("configuration_dimensions", []),
                                key=lambda r: r.get("ordinal") or 0)
                         if r.get("proposed_identity_affecting") is True]
        if tuple(tuple_members) != LOCKED_PROTOTYPE_TUPLE:
            failures.append(
                f"identity tuple is {tuple_members}, not the locked "
                f"{list(LOCKED_PROTOTYPE_TUPLE)}")


# ----------------------------------------------------------------------
# compile
# ----------------------------------------------------------------------

def compile_release(db, domain: str, ontology_version: str) -> CompiledArtifact:
    """Compile one deployed authoring release. Raises rather than warning."""
    payload: dict = {}
    census: dict = {}
    for table, sort_key in SECTIONS:
        rows = _rows(db, table, domain, ontology_version, sort_key)
        payload[table] = rows
        census[table] = len(rows)

    failures: list = []
    _validate(payload, domain, ontology_version, failures)
    if failures:
        raise CompilationError(
            "compilation failed %d validation(s); no artifact produced:\n  - %s"
            % (len(failures), "\n  - ".join(failures)))

    release = payload["ontology_release"][0]
    semantic = {
        "compiler_version": COMPILER_VERSION,
        "domain": domain,
        "ontology_version": ontology_version,
        "release_class": release["release_class"],
        "governance_basis": {"AUTHORITATIVE": "AUTHORITATIVE",
                             "PROTOTYPE": "PROTOTYPE_ASSUMPTION"}[
                                 release["release_class"]],
        "validation_status": release.get("validation_status"),
        "parent_ontology_version": release.get("parent_ontology_version"),
        "sections": payload,
    }
    return CompiledArtifact(
        domain=domain,
        ontology_version=ontology_version,
        release_class=release["release_class"],
        governance_basis=semantic["governance_basis"],
        validation_status=release.get("validation_status"),
        parent_ontology_version=release.get("parent_ontology_version"),
        payload=semantic,
        semantic_digest=semantic_digest(semantic),
        census=census,
    )
