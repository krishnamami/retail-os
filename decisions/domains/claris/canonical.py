"""Canonical materialization and legacy projection preview for Claris.

WHAT THIS MODULE IS FOR
-----------------------
A predicate concludes; it does not act. This module is the separate, later act:
it turns a PERSISTED governed decision into canonical rows, and it computes what
each target system would need for the versions that resulted.

    CREATE_PRODUCT       Product + initial Configuration + ConfigurationVersion
    CREATE_CONFIGURATION reuse Product; new Configuration + first Version
    NEW_VERSION          reuse Product and Configuration; next Version
    NO_BUSINESS_CHANGE   nothing is created; the existing identity is returned
    USE_EXISTING         nothing is created; the existing identity is returned
    CANNOT_DECIDE        NOTHING. Not a version, not a placeholder, not a
                         "pending" row. The request is retained for human review
                         and the canonical layer is left exactly as it was.

IDEMPOTENCE IS STRUCTURAL, NOT PROCEDURAL
-----------------------------------------
Identifiers are DERIVED from the canonical identity rather than allocated from a
sequence:

    configuration_id = CFG-<product_reference>-<first 8 hex of sha256(identity)>
    version_id       = <configuration_id>-V<n>

so re-running against the same identity computes the same id and the write is a
guarded INSERT that finds it already there. Nothing depends on remembering what
a previous run allocated, which is what makes replay safe across processes and
across sessions.

WHAT REPLAY ACTUALLY DOES, STATED PLAINLY
------------------------------------------
Re-running the slice does NOT reproduce the first run's outcomes, and that is
correct rather than a defect. The canonical lookup is CURRENT_STATE (carried-open
item V-4: claris.product has no validity interval, so an as-of read is not
answerable from this schema). After the first run the products and configurations
exist, so a request that first concluded CREATE_CONFIGURATION now concludes
NO_BUSINESS_CHANGE against the configuration it itself created. The invariant
that matters -- and that is asserted -- is that replay creates NO new canonical
row.

PROJECTION PREVIEWS ARE PREVIEWS
--------------------------------
Nothing here writes to all_skus, SAP, ww_pricing or Salesforce, and nothing here
writes to claris.projection either: that table carries five columns
(projection_id, created_at, source_decision_id, projection_reason_code,
previous_projection_id) and has no target_system, target_key, projection_action
or projection_status, so a preview cannot be stored in it without inventing a
schema. The previews are computed and reported.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from .errors import ClarisDomainError

__all__ = [
    "CanonicalMaterializationError",
    "CREATE_PRODUCT",
    "CREATE_CONFIGURATION",
    "NEW_VERSION",
    "NO_BUSINESS_CHANGE",
    "USE_EXISTING",
    "CANNOT_DECIDE",
    "MATERIALIZING_OUTCOMES",
    "configuration_id_for",
    "identity_digest_for",
    "version_id_for",
    "MaterializationResult",
    "CanonicalMaterializer",
    "ProjectionPreview",
    "preview_projections",
]


class CanonicalMaterializationError(ClarisDomainError):
    """Materialization could not proceed. Never converted into a business
    outcome: a canonical write that cannot be made safely is a system failure."""


CREATE_PRODUCT = "CREATE_PRODUCT"
CREATE_CONFIGURATION = "CREATE_CONFIGURATION"
NEW_VERSION = "NEW_VERSION"
NO_BUSINESS_CHANGE = "NO_BUSINESS_CHANGE"
USE_EXISTING = "USE_EXISTING"
CANNOT_DECIDE = "CANNOT_DECIDE"

#: The only outcomes that may create a canonical row.
MATERIALIZING_OUTCOMES = frozenset({CREATE_PRODUCT, CREATE_CONFIGURATION,
                                    NEW_VERSION})


def configuration_id_for(product_reference: str, canonical_identity: str) -> str:
    """A stable configuration id derived from the identity it represents.

    Derived, not allocated. Two runs of the slice, two processes, or a rerun
    after a crash all compute the same id for the same business identity, so
    the guarded INSERT is a no-op rather than a duplicate.

    The product reference is kept in the clear because a human reading
    claris.configuration should be able to see which product a row belongs to
    without joining; the hash disambiguates the rest of the tuple.
    """
    digest = hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()
    return f"CFG-{product_reference}-{digest[:8]}"


def identity_digest_for(canonical_identity: str) -> str:
    """A digest OF THE BUSINESS IDENTITY, and of nothing else.

    Deliberately not the decision's input_digest. input_digest fingerprints one
    evaluation's inputs so a decision can be replayed; this fingerprints the
    identity a configuration carries. Storing the former in
    claris.configuration.identity_digest would tie a stable business identity to
    the particular decision that happened to create it, and two configurations
    with the same identity would then be distinguishable by digest -- which is
    the exact conflation this codebase has kept apart throughout.
    """
    return "v1:sha256:" + hashlib.sha256(
        canonical_identity.encode("utf-8")).hexdigest()


def version_id_for(configuration_id: str, sequence: int) -> str:
    if sequence < 1:
        raise CanonicalMaterializationError(
            f"version sequence must start at 1, got {sequence}")
    return f"{configuration_id}-V{sequence}"


@dataclass
class MaterializationResult:
    """What one decision actually caused in the canonical layer."""

    subject_id: str
    outcome_code: str
    decision_id: Optional[str] = None
    product_id: Optional[str] = None
    configuration_id: Optional[str] = None
    version_id: Optional[str] = None
    version_sequence: Optional[int] = None
    canonical_identity: Optional[str] = None
    identity_digest: Optional[str] = None
    created: tuple = ()
    reused: tuple = ()
    human_review_required: bool = False
    note: str = ""

    @property
    def canonical_action(self) -> str:
        if self.created:
            return "CREATED " + ", ".join(self.created)
        if self.reused:
            return "REUSED " + ", ".join(self.reused)
        return "NONE"


class CanonicalMaterializer:
    """Turns a persisted governed decision into canonical rows.

    Constructed with a write-capable database. Every write is a guarded INSERT
    or a SELECT; there is no UPDATE and no DELETE in this class, because the
    canonical layer is append-only under the prototype and nothing here has the
    authority to retire an identity.
    """

    __slots__ = ("_db", "_created_by", "_digest_width")

    #: Characters a governed digest needs: "v1:sha256:" + 64 hex.
    DIGEST_WIDTH_REQUIRED = 74

    def __init__(self, db, created_by: str = "vertical-slice") -> None:
        self._db = db
        self._created_by = created_by
        self._digest_width = self._identity_digest_width()

    def _identity_digest_width(self):
        """How wide claris.configuration.identity_digest actually is.

        Read from the catalogue rather than assumed. A column's width is part
        of its type, and writing a value that does not fit is a truncation
        error halfway through a materialization run.
        """
        return self._db.scalar("""
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_schema='claris' AND table_name='configuration'
              AND column_name='identity_digest'""")

    @property
    def writes_identity_digest(self) -> bool:
        """Whether the deployed column can hold a governed digest at all."""
        return (self._digest_width is not None
                and self._digest_width >= self.DIGEST_WIDTH_REQUIRED)

    def _identity_digest(self, canonical_identity: str):
        """The governed digest, or None when the column cannot hold one.

        DELIBERATELY NOT TRUNCATED. claris.configuration.identity_digest is
        varchar(32) on this deployment, sized for a 32-character hash before the
        D.4G.2 digest contract existed, and it cannot be widened without
        dropping and recreating the nine claris.v_workbench_* views that read it
        -- none of which has a repository source yet.

        Shortening the digest to fit would put a value in the canonical layer
        that follows no governed contract, differs silently from every other
        digest in this database, and can be verified against nothing. NULL says
        truthfully that no digest was recorded.

        Nothing is lost functionally: canonical_identity carries the full
        identity in varchar(256), it is the authoritative key, and every lookup
        resolves a configuration by it. No code path resolves one by digest.

        This is width-aware rather than hardcoded so that widening the column is
        the ONLY thing needed to start recording digests -- no code change, and
        no stale assumption left behind to find later.
        """
        if not self.writes_identity_digest:
            return None
        return identity_digest_for(canonical_identity)

    # -- reads ----------------------------------------------------------

    def product_exists(self, product_id: str) -> bool:
        return bool(self._db.scalar(
            "SELECT count(*) FROM claris.product WHERE product_id = %s",
            (product_id,)))

    def configuration_by_identity(self, canonical_identity: str) -> Optional[dict]:
        rows = self._db.query("""
            SELECT configuration_id, product_id, status, archived_at
            FROM claris.configuration
            WHERE canonical_identity = %s
            ORDER BY configuration_id""", (canonical_identity,))
        return rows[0] if rows else None

    def version_count(self, configuration_id: str) -> int:
        return int(self._db.scalar(
            "SELECT count(*) FROM claris.configuration_version "
            "WHERE configuration_id = %s", (configuration_id,)) or 0)

    # -- writes, each guarded -------------------------------------------

    def _ensure_product(self, product_id: str, product_name: str) -> bool:
        """True when this call created the product."""
        if self.product_exists(product_id):
            return False
        self._db.execute("""
            INSERT INTO claris.product (product_id, product_name)
            SELECT %s, %s
            WHERE NOT EXISTS (SELECT 1 FROM claris.product WHERE product_id = %s)
            """, (product_id, product_name, product_id))
        return self.product_exists(product_id)

    def _ensure_configuration(self, configuration_id: str, product_id: str,
                              canonical_identity: str,
                              identity_digest: str) -> bool:
        existing = self._db.query(
            "SELECT configuration_id FROM claris.configuration "
            "WHERE configuration_id = %s", (configuration_id,))
        if existing:
            return False
        self._db.execute("""
            INSERT INTO claris.configuration
                (configuration_id, product_id, canonical_identity,
                 identity_digest, status, governed_identity, created_by)
            SELECT %s, %s, %s, %s, 'active', true, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM claris.configuration WHERE configuration_id = %s)
            """, (configuration_id, product_id, canonical_identity,
                  identity_digest, self._created_by, configuration_id))
        return True

    def _ensure_version(self, version_id: str, configuration_id: str,
                        outcome_code: str, decision_id: Optional[str]) -> bool:
        existing = self._db.query(
            "SELECT version_id FROM claris.configuration_version "
            "WHERE version_id = %s", (version_id,))
        if existing:
            return False
        self._db.execute("""
            INSERT INTO claris.configuration_version
                (version_id, configuration_id, status,
                 identity_assessment_outcome, identity_assessment_id)
            SELECT %s, %s, 'established', %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM claris.configuration_version
                WHERE version_id = %s)
            """, (version_id, configuration_id, outcome_code, decision_id,
                  version_id))
        return True

    # -- the one public entry point --------------------------------------

    def materialize(
        self,
        *,
        subject_id: str,
        outcome_code: str,
        product_reference: Optional[str],
        canonical_identity: Optional[str],
        product_name: Optional[str] = None,
        decision_id: Optional[str] = None,
    ) -> MaterializationResult:
        """Apply one governed outcome. Creates nothing it is not entitled to."""
        result = MaterializationResult(subject_id=subject_id,
                                       outcome_code=outcome_code,
                                       decision_id=decision_id,
                                       canonical_identity=canonical_identity)

        if outcome_code == CANNOT_DECIDE:
            result.human_review_required = True
            result.note = ("no canonical identity change; the platform named "
                           "the gap rather than defaulting")
            return result

        if outcome_code not in MATERIALIZING_OUTCOMES | {NO_BUSINESS_CHANGE,
                                                        USE_EXISTING}:
            raise CanonicalMaterializationError(
                f"{outcome_code!r} is not an outcome this materializer knows how "
                "to apply; refusing to guess")

        if not canonical_identity or not product_reference:
            raise CanonicalMaterializationError(
                f"{outcome_code} requires a canonical identity and a product "
                "reference; a materializing outcome cannot have reached here "
                "without them")

        configuration_id = configuration_id_for(product_reference,
                                                canonical_identity)
        result.product_id = product_reference
        result.configuration_id = configuration_id

        created: list = []
        reused: list = []

        if outcome_code in (NO_BUSINESS_CHANGE, USE_EXISTING):
            existing = self.configuration_by_identity(canonical_identity)
            if existing is None:
                raise CanonicalMaterializationError(
                    f"{outcome_code} on an identity no configuration carries; "
                    "the decision and the canonical layer disagree")
            result.configuration_id = existing["configuration_id"]
            result.version_sequence = self.version_count(
                existing["configuration_id"])
            result.note = ("the requested identity already exists; no "
                           "configuration and no version were created")
            result.reused = ("product", "configuration")
            return result

        # -- CREATE_PRODUCT ----------------------------------------------
        if outcome_code == CREATE_PRODUCT:
            if not product_name:
                raise CanonicalMaterializationError(
                    f"CREATE_PRODUCT for {product_reference!r} has no governed "
                    "product_name; claris.product.product_name is NOT NULL and "
                    "inventing one would put an ungoverned value in the "
                    "canonical layer")
            if self._ensure_product(product_reference, product_name):
                created.append("product")
            else:
                reused.append("product")
        else:
            if not self.product_exists(product_reference):
                raise CanonicalMaterializationError(
                    f"{outcome_code} under product {product_reference!r}, which "
                    "does not exist canonically; the decision assumed a product "
                    "the canonical layer does not have")
            reused.append("product")

        # -- the configuration -------------------------------------------
        if outcome_code == NEW_VERSION:
            existing = self.configuration_by_identity(canonical_identity)
            if existing is None:
                raise CanonicalMaterializationError(
                    "NEW_VERSION on an identity no configuration carries")
            configuration_id = existing["configuration_id"]
            result.configuration_id = configuration_id
            reused.append("configuration")
        else:
            digest = self._identity_digest(canonical_identity)
            result.identity_digest = digest
            if self._ensure_configuration(configuration_id, product_reference,
                                          canonical_identity, digest):
                created.append("configuration")
            else:
                reused.append("configuration")

        # -- the version --------------------------------------------------
        sequence = self.version_count(configuration_id) + 1
        version_id = version_id_for(configuration_id, sequence)
        if self._ensure_version(version_id, configuration_id, outcome_code,
                                decision_id):
            created.append("configuration_version")
        else:
            reused.append("configuration_version")
        result.version_id = version_id
        result.version_sequence = sequence
        result.created = tuple(created)
        result.reused = tuple(reused)
        return result


# ======================================================================
# legacy projection preview
# ======================================================================

#: How a governed outcome is read against a projection rule.
#:
#: DERIVED, NOT GOVERNED -- stated so it cannot be mistaken for policy.
#: ontology_authoring.projection_rules carries target_system, proposed_action
#: and requires_new_target_identity, and leaves projection_reason NULL, exactly
#: as the 2026.10 source does. The reason a target row exists is therefore
#: computed here, from the governed `projection_reason` vocabulary, following
#: the worked example the source itself supplies in
#: claris.retail_ontology.example_projections:
#:
#:   an initial configuration       -> CONFIGURATION_REQUIRED,  not proliferation
#:   a genuinely new product        -> BUSINESS_IDENTITY_REQUIRED, not proliferation
#:   a new version, in all_skus     -> LEGACY_SYSTEM_CONSTRAINT, proliferation
#:   a new version, elsewhere       -> TARGET_SYSTEM_REQUIREMENT, proliferation
#:
#: Q-003 (legacy_update_in_place) is open against PR-001 and PR-002 and would
#: settle whether an all_skus row is genuinely unavoidable. Until it is, PR-001's
#: own status is 'confirm_with_claris' and this mapping inherits that.
_REASON_BY_OUTCOME = {
    CREATE_PRODUCT: ("BUSINESS_IDENTITY_REQUIRED", False),
    CREATE_CONFIGURATION: ("CONFIGURATION_REQUIRED", False),
}
_LEGACY_CONSTRAINT_SYSTEM = "all_skus"


@dataclass(frozen=True)
class ProjectionPreview:
    """What one target system would need for one canonical version."""

    subject_id: str
    configuration_id: str
    version_id: Optional[str]
    rule: str
    target_system: str
    target_object_type: Optional[str]
    target_key: Optional[str]
    projection_action: str
    projection_reason: str
    requires_new_target_identity: bool
    counts_as_proliferation: bool
    projection_status: str
    rule_status: str
    previous_projection_id: Optional[str] = None

    def as_row(self) -> dict:
        return {k: getattr(self, k) for k in (
            "subject_id", "configuration_id", "version_id", "rule",
            "target_system", "target_object_type", "target_key",
            "projection_action", "projection_reason",
            "requires_new_target_identity", "counts_as_proliferation",
            "projection_status", "rule_status", "previous_projection_id")}


def preview_projections(
    result: MaterializationResult,
    projection_rules: Sequence[Mapping[str, Any]],
) -> tuple:
    """What each target system would need for this outcome. Writes nothing.

    An outcome that created no version needs no projection: NO_BUSINESS_CHANGE
    and USE_EXISTING return the existing identity, and CANNOT_DECIDE returns
    nothing at all. Emitting a NO_ACTION row for them would put a projection
    record against a version that does not exist.

    `target_key` is deliberately None everywhere. A material number, SKU row id
    or pricebook entry id is minted BY the target system; predicting one here
    would be fabricating a legacy identifier, and the preview's whole point is
    to say a row is REQUIRED, not to pretend it already exists.
    """
    if result.outcome_code not in MATERIALIZING_OUTCOMES:
        return ()
    if not result.version_id:
        return ()

    previews = []
    for rule in projection_rules:
        if rule.get("source_object") not in (None, "configuration", "price"):
            continue
        target = rule["target_system"]
        action = rule.get("proposed_action") or "CREATE"
        requires_new = bool(rule.get("requires_new_target_identity"))

        if result.outcome_code == NEW_VERSION:
            if target == _LEGACY_CONSTRAINT_SYSTEM:
                reason, proliferation = "LEGACY_SYSTEM_CONSTRAINT", True
            else:
                reason, proliferation = "TARGET_SYSTEM_REQUIREMENT", True
        else:
            reason, proliferation = _REASON_BY_OUTCOME[result.outcome_code]

        previews.append(ProjectionPreview(
            subject_id=result.subject_id,
            configuration_id=result.configuration_id,
            version_id=result.version_id,
            rule=rule["rule"],
            target_system=target,
            target_object_type=rule.get("target_object_type"),
            target_key=None,
            projection_action=action,
            projection_reason=reason,
            requires_new_target_identity=requires_new,
            counts_as_proliferation=proliferation,
            projection_status="REQUIRED",
            rule_status=rule.get("status") or "proposed",
            previous_projection_id=None,
        ))
    return tuple(previews)
