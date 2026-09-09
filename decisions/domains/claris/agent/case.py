"""Case context assembly for the Claris coordination agent.

WHAT THIS IS
------------
The Workbench does not start a launch. Claris's existing tools and processes do
that. This layer OBSERVES what those systems left behind -- evidence,
assertions, folded state, governed decisions, canonical objects -- and
reconstructs one coherent picture of a change that is already in flight.

So there is no "create launch" here, no workflow engine, and no state machine.
There is a reader.

WHAT IT MAY AND MAY NOT DO
--------------------------
It reads. It never writes, never executes a decision, and never concludes one.
Every field it returns is traceable to a row: a decision, an evidence record, a
fold property, a canonical object, or the active governance artifact. Where the
data does not say something, the field is None and the absence is reported --
never filled in from a plausible guess.

Two absences matter enough to name here, because they are the ones a demo would
be tempted to paper over:

    ACTORS. Every actor id in this corpus is a simulation marker
    ('SIMULATED/product-manager', 'config_governance_system'). Those are not
    people. The assembler returns the ROLE, which is real governed metadata, and
    returns the actor as None with the raw marker preserved separately for
    audit. Inventing "Daniel Park" from a mock would put a fabricated human into
    a business record.

    DIMENSION OWNERSHIP. The prototype release carries owner=NULL and
    authority=NULL on every configuration dimension, because the restoration
    deliberately withheld unsigned claims. 2026.10 proposes owners, but Q-002 --
    who owns the identity dimensions -- is OPEN. So when a customer_segment is
    missing, this layer reports that the owning role is NOT ESTABLISHED and
    names Q-002, rather than routing the request to a team nobody confirmed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from ..identity import (
    IDENTITY_PROPERTIES,
    encode_identity_values,
    render_term_months,
)

__all__ = [
    "SIMULATION_MARKERS",
    "CaseContext",
    "CaseContextAssembler",
    "is_simulated_actor",
]

#: Prefixes and literals that mark an actor id as a simulation artefact rather
#: than a person. An id matching one of these is never presented as a human.
SIMULATION_MARKERS = ("SIMULATED/", "SIMULATED:", "config_governance_system",
                      "product_definition", "configuration_governance",
                      "SYSTEM", "vertical-slice")


def is_simulated_actor(actor_id: Optional[str]) -> bool:
    if not actor_id:
        return True
    return any(actor_id.startswith(marker) or actor_id == marker
               for marker in SIMULATION_MARKERS)


@dataclass(frozen=True)
class CaseContext:
    """Everything observable about one change, from persisted state alone."""

    subject_id: str
    subject_type: str
    decision_horizon: Any
    fold_status: Optional[str]

    identity_tuple: Mapping[str, Any] = field(default_factory=dict)
    identity_states: Mapping[str, str] = field(default_factory=dict)
    canonical_identity: Optional[str] = None

    launch: Optional[Mapping[str, Any]] = None
    product: Optional[Mapping[str, Any]] = None
    configuration: Optional[Mapping[str, Any]] = None
    version: Optional[Mapping[str, Any]] = None

    decisions: tuple = ()
    evidence: tuple = ()
    projections: tuple = ()
    actors: tuple = ()
    dimension_governance: tuple = ()
    governance: Mapping[str, Any] = field(default_factory=dict)
    open_questions: tuple = ()

    # -- convenience the analyser and the drafter both need ---------------

    @property
    def current_decisions(self) -> Mapping[str, tuple]:
        """decision_type -> every decision currently claiming to be current.

        A tuple rather than a single value, deliberately. Until every subject
        has been re-evaluated under the supersession fix, a subject can carry
        more than one current decision, and an agent that returned the first one
        would be choosing an answer it has no authority to choose.
        """
        grouped: dict = {}
        for decision in self.decisions:
            if decision.get("state") == "current":
                grouped.setdefault(decision["decision_type"], []).append(decision)
        return {k: tuple(v) for k, v in grouped.items()}

    @property
    def superseded_decisions(self) -> tuple:
        return tuple(d for d in self.decisions if d.get("state") == "superseded")

    @property
    def missing_identity_properties(self) -> tuple:
        return tuple(sorted(
            name for name, state in self.identity_states.items()
            if state != "ESTABLISHED"))

    @property
    def contradicted_identity_properties(self) -> tuple:
        return tuple(sorted(
            name for name, state in self.identity_states.items()
            if state == "CONTRADICTED"))


class CaseContextAssembler:
    """Reads one case out of the database. Read-only, no execution."""

    __slots__ = ("_db", "_release", "_identity_properties")

    def __init__(self, db, release, identity_properties) -> None:
        self._db = db
        self._release = release
        self._identity_properties = tuple(identity_properties)

    # ------------------------------------------------------------------

    def subjects(self, subject_type: str) -> tuple:
        return tuple(row["subject_id"] for row in self._db.query("""
            SELECT DISTINCT subject_id FROM state.fold_state_snapshot
            WHERE subject_type = %s ORDER BY subject_id""", (subject_type,)))

    def assemble(self, subject_id: str, subject_type: str) -> CaseContext:
        snapshot = self._snapshot(subject_id, subject_type)
        if snapshot is None:
            raise LookupError(
                f"no fold snapshot for {subject_type}/{subject_id}; the agent "
                "observes governed state and there is none for this subject")

        properties = _properties(snapshot["folded_properties"])
        identity_tuple = {
            name: properties.get(name, {}).get("resolved_value")
            for name in self._identity_properties
        }
        identity_states = {
            name: properties.get(name, {}).get("fold_state", "ABSENT")
            for name in self._identity_properties
        }
        product_reference = identity_tuple.get("product_reference")

        decisions = self._decisions(subject_id)
        configuration = self._configuration(
            decisions, product_reference, identity_tuple, identity_states)
        version = self._version(decisions)
        product = self._product(product_reference)

        return CaseContext(
            subject_id=subject_id,
            subject_type=subject_type,
            decision_horizon=snapshot["decision_horizon"],
            fold_status=snapshot["fold_status"],
            identity_tuple=identity_tuple,
            identity_states=identity_states,
            canonical_identity=(configuration or {}).get("canonical_identity"),
            launch=self._launch(properties),
            product=product,
            configuration=configuration,
            version=version,
            decisions=decisions,
            evidence=self._evidence(subject_id, properties),
            projections=(),          # supplied by the caller; see the agent
            actors=self._actors(),
            dimension_governance=self._dimension_governance(),
            governance={
                "ontology_version": self._release.ontology_version,
                "kb_version": self._release.kb_version,
                "release_class": self._release.release_class,
                "governance_basis": self._release.governance_basis,
                "validation_status": self._release.validation_status,
                "content_digest": self._release.content_digest,
                # Which decision types this release actually binds a predicate
                # for. The coordination layer uses it to say "nothing else is
                # executable here" truthfully rather than by assumption.
                "bound_decision_types": tuple(
                    {"decision": row.get("decision")}
                    for row in self._release.rows("decision_rule_bindings")),
            },
            open_questions=self._open_questions(),
        )

    # -- readers ---------------------------------------------------------

    def _snapshot(self, subject_id: str, subject_type: str):
        rows = self._db.query("""
            SELECT subject_id, subject_type, decision_horizon, fold_status,
                   folded_properties
            FROM state.fold_state_snapshot
            WHERE subject_type = %s AND subject_id = %s
            ORDER BY decision_horizon DESC LIMIT 1""",
            (subject_type, subject_id))
        return rows[0] if rows else None

    def _launch(self, properties: Mapping[str, Any]):
        reference = (properties.get("launch_reference") or {}).get(
            "resolved_value")
        if not reference:
            return None
        rows = self._db.query("""
            SELECT subject_id, fold_status, folded_properties
            FROM state.fold_state_snapshot
            WHERE subject_type = 'launch' AND subject_id = %s
            ORDER BY decision_horizon DESC LIMIT 1""", (reference,))
        if not rows:
            return {"launch_id": reference, "observed": False}
        launch_properties = _properties(rows[0]["folded_properties"])
        requester_role = (launch_properties.get("change_requester_role") or {}
                          ).get("resolved_value")
        requester_actor = (launch_properties.get("change_requested_by") or {}
                           ).get("resolved_value")
        return {
            "launch_id": reference,
            "observed": True,
            "fold_status": rows[0]["fold_status"],
            "intent_classification": (
                launch_properties.get("intent_classification") or {}
            ).get("resolved_value"),
            "requested_by_role": requester_role,
            # a simulation marker is never presented as a person
            "requested_by_actor": (None if is_simulated_actor(requester_actor)
                                   else requester_actor),
            "requested_by_actor_raw": requester_actor,
        }

    def _product(self, product_reference: Optional[str]):
        if not product_reference:
            return None
        rows = self._db.query("""
            SELECT product_id, product_name, created_at
            FROM claris.product WHERE product_id = %s""", (product_reference,))
        return rows[0] if rows else None

    def _configuration(self, decisions, product_reference,
                       identity_tuple=None, identity_states=None):
        """The configuration this subject's decisions actually touched.

        TWO RESOLUTION PATHS, IN PRECEDENCE ORDER

        1. Through the version a decision created. Authoritative: the decision
           materialized that configuration, so the link is a fact.

        2. Through canonical identity, when no version exists. A
           NO_BUSINESS_CHANGE decision deliberately creates nothing -- that is
           what makes it a duplicate -- so path 1 returns nothing and the case
           context used to report `configuration: None` for exactly the
           scenario the prototype exists to demonstrate. The request WAS
           resolved to a configuration; the absence of a version is the
           evidence of it, not a reason to disclaim it.

        Path 2 is a lookup, not a guess. It re-derives the same canonical
        identity string the materializer used and matches it exactly, so it can
        only find the configuration this request's identity actually denotes.
        The original caution still holds and is why it is not weakened to a
        product lookup: a product may carry several configurations, and
        choosing one by product alone would attribute a canonical object to a
        request that never resolved to it.

        Path 2 refuses to run unless every identity property is ESTABLISHED.
        An incomplete tuple is the CANNOT_DECIDE case, and inventing a
        configuration for it would manufacture the certainty the fold declined
        to supply.

        The returned row carries `resolved_via` so a caller can tell a
        configuration this decision CREATED from one it was ABSORBED INTO.
        Those are different business facts and must not read alike.
        """
        for decision in decisions:
            rows = self._db.query("""
                SELECT c.configuration_id, c.product_id, c.canonical_identity,
                       c.identity_digest, c.status, c.governed_identity,
                       c.created_at, c.created_by, c.archived_at
                FROM claris.configuration_version v
                JOIN claris.configuration c
                  ON c.configuration_id = v.configuration_id
                WHERE v.identity_assessment_id = %s""",
                (decision["decision_id"],))
            if rows:
                row = dict(rows[0])
                row["resolved_via"] = "version"
                return row

        canonical = self._canonical_identity(identity_tuple, identity_states)
        if not canonical or not product_reference:
            return None
        rows = self._db.query("""
            SELECT c.configuration_id, c.product_id, c.canonical_identity,
                   c.identity_digest, c.status, c.governed_identity,
                   c.created_at, c.created_by, c.archived_at
            FROM claris.configuration c
            WHERE c.canonical_identity = %s
              AND c.product_id = %s
            ORDER BY c.configuration_id""",
            (canonical, product_reference))
        if not rows:
            return None
        row = dict(rows[0])
        row["resolved_via"] = "canonical_identity"
        return row

    @staticmethod
    def _canonical_identity(identity_tuple, identity_states):
        """The canonical identity of a complete tuple, or None.

        Uses the governed encoder rather than a local join, so a duplicate is
        matched by the same length-prefixed string the materializer wrote. A
        second implementation here would be a second definition of business
        identity, and the two would eventually disagree.

        None -- never a partial string -- whenever a property is missing, not
        ESTABLISHED, or cannot be rendered. Rendering failures are treated as
        "cannot resolve", not as an alternative identity.
        """
        if not identity_tuple or not identity_states:
            return None
        rendered = []
        for name in IDENTITY_PROPERTIES:
            if identity_states.get(name) != "ESTABLISHED":
                return None
            value = identity_tuple.get(name)
            if value is None:
                return None
            if name == "term_months":
                try:
                    rendered.append(render_term_months(value))
                except Exception:  # noqa: BLE001 -- unrenderable, not an identity
                    return None
            elif isinstance(value, bool) or not isinstance(value, str):
                return None
            else:
                rendered.append(value)
        return encode_identity_values(rendered)

    def _version(self, decisions):
        for decision in decisions:
            rows = self._db.query("""
                SELECT version_id, configuration_id, status,
                       identity_assessment_outcome, identity_assessment_id,
                       created_at
                FROM claris.configuration_version
                WHERE identity_assessment_id = %s""",
                (decision["decision_id"],))
            if rows:
                return rows[0]
        return None

    def _decisions(self, subject_id: str) -> tuple:
        return tuple(self._db.query("""
            SELECT decision_id::text AS decision_id, decision_type, subject_type,
                   subject_id, outcome_code, reason_code, matched_rule_id,
                   matched_rule_class, matched_rule_kb_version,
                   confidence_level, missing_evidence, blocking_evidence,
                   ontology_version, kb_version, policy_version,
                   governance_basis, execution_mode, input_digest,
                   fold_state_id, state, superseded_by::text AS superseded_by,
                   superseded_at, decided_at, decided_by, horizon_as_of
            FROM claris.decision
            WHERE subject_id = %s
            ORDER BY decided_at, decision_type""", (subject_id,)))

    def _evidence(self, subject_id: str, properties: Mapping[str, Any]) -> tuple:
        """Evidence for this subject, with its role and its basis assertions.

        Only evidence the Fold actually used is reported as contributing: the
        basis_assertion_ids on each folded property are the audit trail, and
        anything else about the same subject is context, not basis.
        """
        rows = self._db.query("""
            SELECT e.evidence_id::text AS evidence_id, e.evidence_type,
                   e.property_name, e.asserted_value, e.value_type,
                   e.source_system, e.source_actor_id, e.source_actor_role,
                   e.occurred_at, e.recorded_at, e.arrival_at,
                   e.simulator_classification
            FROM runtime.evidence e
            WHERE e.subject_id = %s
            ORDER BY e.occurred_at, e.property_name""", (subject_id,))
        used = {name: set(item.get("basis_assertion_ids") or ())
                for name, item in properties.items()}
        enriched = []
        for row in rows:
            actor = row["source_actor_id"]
            enriched.append({
                **row,
                "role": row["source_actor_role"],
                "actor": None if is_simulated_actor(actor) else actor,
                "actor_raw": actor,
                "contributed_to_fold": row["property_name"] in used,
            })
        return tuple(enriched)

    def _actors(self) -> tuple:
        """The governed actor/role model, from the active release."""
        return tuple(sorted(
            (dict(row) for row in self._release.rows("actors")),
            key=lambda r: r.get("ordinal") or 0))

    def _dimension_governance(self) -> tuple:
        """Per-dimension ownership as the ACTIVE release states it.

        On a prototype release owner and authority are NULL by construction --
        the restoration withheld every unsigned claim -- so this is what makes
        "nobody owns this yet" reportable rather than invisible.
        """
        return tuple(
            {
                "dimension": row.get("dimension"),
                "label": row.get("label"),
                "identity_affecting": row.get("identity_affecting"),
                "governance_state": row.get("governance_state"),
                "blocks_identity_assessment":
                    row.get("blocks_identity_assessment"),
                "owner": row.get("owner"),
                "authority": row.get("authority"),
                "status": row.get("status"),
            }
            for row in self._release.rows("configuration_dimensions"))

    def _open_questions(self) -> tuple:
        return tuple(
            {"note_id": row.get("note_id"), "topic": row.get("topic"),
             "question": row.get("question"), "owner": row.get("owner"),
             "status": row.get("status")}
            for row in self._release.rows("ontology_notes"))


def _properties(folded) -> dict:
    if isinstance(folded, str):
        folded = json.loads(folded)
    return {item["property_name"]: item for item in (folded or ())}
