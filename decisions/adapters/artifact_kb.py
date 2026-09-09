"""Read-only governance resolver over the COMPILED ARTIFACT STORE.

WHAT THIS IS, AND WHY IT IS NOT A SECOND RESOLVER ARCHITECTURE
---------------------------------------------------------------
`decisions/governance_resolver.py` defines the prototype/production selection
contract and says, in its own docstring, that "loading candidates from a live
artifact store is D.4G.2 work and is deliberately absent". This module is that
loader and nothing more. It does not re-decide which release a mode may use --
it hands candidates to `select_release()` and accepts the answer, including the
refusal.

It also does not replace `kb_postgres.PostgresKBResolver`. That one reads the
legacy executable table `claris_kb.decision_rules`, which is where
CHANGE_CLASSIFICATION's governed rules live and where production continues to
read from. This one reads `claris_kb.kb_artifact.kb_json` -- the deterministic
artifact the D.4G.4 compiler produced -- because that is the only place the
prototype release's executable bindings exist. Two stores, two adapters, one
selection contract; no fallback between them.

WHAT THE ARTIFACT OWNS, AND WHAT THE DOMAIN PACK STILL OWNS
------------------------------------------------------------
The authoring model promoted `rule_class` into governed metadata at D.4G.1G.4:
`ontology_authoring.decision_rule_bindings` carries decision, rule_id,
predicate_name, rule_class, precedence and expected_outcome, and the compiler
carries all of it into the artifact. So unlike the legacy path, rule_class here
is READ, never assigned -- which resolves open decision V-1 in the direction
D.4C anticipated.

What the artifact deliberately does NOT carry is executable code. A binding
names a predicate; it does not contain one. The domain pack supplies the
name -> callable mapping, and a name the domain pack does not export fails
resolution outright rather than being skipped: a governed binding pointing at
code that does not exist is a deployment defect.

The artifact also carries no reason_code on a binding. That column does not
exist in the authoring model, and adding it would change every compiled
artifact's digest -- including releases already published and verified. So
reason codes stay where D.4E put them, in the domain pack, and travel in
through the same `predicate_name` key as the callables. This is recorded as a
known gap rather than papered over.

GENERIC
    Nothing here mentions Claris, IDENTITY_ASSESSMENT, a dimension name or an
    identity tuple. Mappings arrive from the caller.

SAFETY
    Read-only. Every statement is a parameterized SELECT through
    ReadOnlyDatabase, which refuses anything that is not SELECT/WITH.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from ..contracts import GOVERNANCE_BASES
from ..digest import canonical_json
from ..governance_resolver import (
    ExecutionMode,
    NoEligibleGovernance,
    ReleaseCandidate,
    select_release,
)
from ..ports import ActiveKB, GovernedRuleMetadata, ResolvedRuleSet, RuleClassBinding
from ..registry import PredicateRegistry
from ..rules import RuleClass
from .errors import NoActiveKB, NoExecutableRuleSet

__all__ = [
    "ARTIFACT_SQL",
    "ArtifactRelease",
    "ArtifactGovernanceResolver",
    "build_registry",
    "load_releases",
]

#: Every artifact the store currently marks ACTIVE, in either class. The
#: selection between them is `select_release()`'s job, not this query's.
ARTIFACT_SQL = """
SELECT kb_version, ontology_version, status, release_class, governance_basis,
       validation_status, content_digest, kb_json
FROM   claris_kb.kb_artifact
WHERE  status = 'ACTIVE'
ORDER  BY release_class, kb_version
"""


@dataclass(frozen=True)
class ArtifactRelease:
    """One ACTIVE compiled artifact, with its payload parsed."""

    kb_version: str
    ontology_version: str
    release_class: str
    governance_basis: str
    validation_status: Optional[str]
    content_digest: str
    payload: Mapping[str, Any]

    @property
    def sections(self) -> Mapping[str, Any]:
        return self.payload.get("sections", {})

    def rows(self, section: str) -> tuple:
        value = self.sections.get(section)
        return tuple(value) if isinstance(value, (list, tuple)) else ()

    @property
    def candidate(self) -> ReleaseCandidate:
        """The selection-contract view of this artifact.

        `artifact_status` is lowercased on the way in. The artifact store spells
        the lifecycle in upper case ('ACTIVE') and the selection contract in
        lower ('active'); normalising here keeps one spelling per layer rather
        than loosening the comparison in the locked resolver.
        """
        return ReleaseCandidate(
            ontology_version=self.ontology_version,
            release_class=self.release_class,
            governance_basis=self.governance_basis,
            artifact_status="active",
            validation_status=self.validation_status,
        )


def load_releases(db) -> tuple[ArtifactRelease, ...]:
    """Every ACTIVE artifact the store holds, payload parsed.

    An artifact whose payload has no `sections` key is not silently treated as
    empty: it is a differently-shaped artifact (KB 1.1 predates the compiler)
    and it simply contributes no executable bindings. The candidate is still
    offered to the selection contract, so production selecting it and then
    finding no rules fails as NoExecutableRuleSet -- a named system failure --
    rather than as a business CANNOT_DECIDE.
    """
    import json

    releases = []
    for row in db.query(ARTIFACT_SQL):
        payload = row["kb_json"]
        if isinstance(payload, (str, bytes)):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            payload = {}
        if row["governance_basis"] not in GOVERNANCE_BASES:
            raise NoActiveKB(
                f"artifact {row['kb_version']!r} carries governance_basis "
                f"{row['governance_basis']!r}, which is not a governed basis"
            )
        releases.append(ArtifactRelease(
            kb_version=row["kb_version"],
            ontology_version=row["ontology_version"],
            release_class=row["release_class"],
            governance_basis=row["governance_basis"],
            validation_status=row["validation_status"],
            content_digest=row["content_digest"],
            payload=payload,
        ))
    return tuple(releases)


class ArtifactGovernanceResolver:
    """GovernanceResolverPort over the artifact store, scoped to one mode.

    Construction selects the release. There is no later opportunity to widen
    the selection, and no method that reaches past it: a resolver built for
    PROTOTYPE cannot answer a production question and vice versa.
    """

    __slots__ = ("_release", "_mode", "_reason_codes")

    def __init__(self, db, mode: ExecutionMode = ExecutionMode.PRODUCTION,
                 releases: Optional[Sequence[ArtifactRelease]] = None,
                 reason_codes: Optional[Mapping[str, str]] = None) -> None:
        available = tuple(releases) if releases is not None else load_releases(db)
        if not available:
            raise NoActiveKB(
                "the artifact store holds no ACTIVE artifact in any class"
            )
        chosen = select_release([r.candidate for r in available], mode)
        for release in available:
            if (release.ontology_version == chosen.ontology_version
                    and release.release_class == chosen.release_class):
                self._release = release
                break
        else:  # pragma: no cover - select_release returned a candidate we lack
            raise NoEligibleGovernance(
                "the selected release is not among the loaded artifacts"
            )
        self._mode = mode
        #: predicate_name -> reason_code, supplied by the domain pack.
        #:
        #: The authoring model has no reason_code on an executable binding, and
        #: adding one would change the digest of every release compiled
        #: afterwards -- including releases already published and verified. So
        #: the reason travels in through the same key as the callable, and the
        #: gap is recorded rather than papered over. A predicate with no entry
        #: here yields reason_code None, which is truthful: no reason was
        #: governed for it.
        self._reason_codes = dict(reason_codes or {})

    # -- what was selected ----------------------------------------------

    @property
    def release(self) -> ArtifactRelease:
        return self._release

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @property
    def governance_basis(self) -> str:
        return self._release.governance_basis

    # -- GovernanceResolverPort -----------------------------------------

    def active_kb(self) -> ActiveKB:
        return ActiveKB(kb_version=self._release.kb_version,
                        raw={"content_digest": self._release.content_digest,
                             "release_class": self._release.release_class,
                             "governance_basis": self._release.governance_basis,
                             "validation_status": self._release.validation_status})

    def bindings_for(self, decision_type: str) -> tuple:
        """The artifact's executable binding rows for one decision type."""
        return tuple(
            row for row in self._release.rows("decision_rule_bindings")
            if row.get("decision") == decision_type
        )

    def resolve_rules(self, decision_type: str,
                      kb_version: Optional[str] = None) -> ResolvedRuleSet:
        """Governed rule metadata for one decision type, from the artifact.

        `kb_version` is honoured as an assertion, not as a selector: a caller
        asking for a version other than the selected release's is refused
        rather than quietly served the selected one.
        """
        if kb_version is not None and kb_version != self._release.kb_version:
            raise NoExecutableRuleSet(
                f"this resolver is bound to kb_version "
                f"{self._release.kb_version!r}; {kb_version!r} was requested"
            )
        rows = self.bindings_for(decision_type)
        if not rows:
            raise NoExecutableRuleSet(
                f"{self._release.kb_version} declares no executable bindings for "
                f"decision_type={decision_type!r}; a missing rule set is a "
                "platform misconfiguration, not a business CANNOT_DECIDE"
            )
        metadata = tuple(
            GovernedRuleMetadata(
                decision_type=decision_type,
                rule_id=row["rule_id"],
                kb_version=self._release.kb_version,
                ontology_version=self._release.ontology_version,
                policy_version="",          # derived-or-absent; normalized to None
                precedence=int(row["precedence"]),
                outcome_code=row["expected_outcome"],
                rule_name=row.get("description"),
                reason_code=self._reason_codes.get(row["predicate_name"]),
                condition_text=None,        # no prose condition exists to carry
                status=row.get("status"),
            )
            for row in sorted(rows, key=lambda r: (int(r["precedence"]),
                                                   r["rule_id"]))
        )
        return ResolvedRuleSet(
            decision_type=decision_type,
            kb_version=self._release.kb_version,
            ontology_version=self._release.ontology_version,
            policy_version="",
            rules=metadata,
            excluded_rules=(),
            rule_set_digest=self._digest(rows),
        )

    # -- what the domain pack needs to bind executable code --------------

    def class_bindings(
        self,
        decision_type: str,
        predicate_names: Optional[Mapping[str, Callable]] = None,
    ) -> Mapping[str, RuleClassBinding]:
        """rule_class + predicate_ref per rule_id, READ from the artifact.

        The legacy path takes these from a domain pack because
        `claris_kb.decision_rules` has no rule_class column. The authoring model
        does have one, so here the governed binding supplies it and the domain
        pack supplies only the code it names.

        When `predicate_names` is given, a binding naming a predicate the domain
        pack does not export raises immediately, with every unknown name listed.
        """
        rows = self.bindings_for(decision_type)
        if predicate_names is not None:
            unknown = sorted(
                {row["predicate_name"] for row in rows
                 if row["predicate_name"] not in predicate_names}
            )
            if unknown:
                raise NoExecutableRuleSet(
                    f"{self._release.kb_version} binds predicates the domain pack "
                    "does not export: " + ", ".join(unknown)
                )
        bindings = {}
        for row in rows:
            try:
                rule_class = RuleClass(row["rule_class"])
            except ValueError as exc:
                raise NoExecutableRuleSet(
                    f"binding {row['rule_id']!r} declares rule_class "
                    f"{row['rule_class']!r}, which is not GUARD, MATCH or FALLBACK"
                ) from exc
            bindings[row["rule_id"]] = RuleClassBinding(
                rule_id=row["rule_id"],
                rule_class=rule_class,
                predicate_ref=row["predicate_name"],
                precedence_override=int(row["precedence"]),
            )
        return bindings

    def outcomes_for(self, decision_type: str) -> frozenset:
        """The outcome vocabulary this release declares for one decision type."""
        return frozenset(
            row["outcome"] for row in self._release.rows("decision_outputs")
            if row.get("decision") == decision_type and row.get("outcome")
        )

    def projection_rules(self) -> tuple:
        """The release's projection rules, in declared order. May be empty."""
        return tuple(sorted(
            self._release.rows("projection_rules"),
            key=lambda r: (r.get("ordinal") if r.get("ordinal") is not None
                           else 0, r.get("rule", "")),
        ))

    # -- internals -------------------------------------------------------

    def _digest(self, rows) -> str:
        import hashlib

        semantic = [
            {k: row[k] for k in ("rule_id", "rule_class", "precedence",
                                 "predicate_name", "expected_outcome")}
            for row in sorted(rows, key=lambda r: r["rule_id"])
        ]
        return hashlib.sha256(
            canonical_json(semantic).encode("utf-8")
        ).hexdigest()


def build_registry(
    resolver: ArtifactGovernanceResolver,
    decision_type: str,
    predicates_by_name: Mapping[str, Callable],
    registry: Optional[PredicateRegistry] = None,
) -> PredicateRegistry:
    """Register the artifact's bound predicates under the release's kb_version.

    The registry key is (decision_type, rule_id, kb_version), and kb_version is
    the SELECTED release's -- so a prototype registry and a production registry
    cannot collide even when they bind the same rule_id, and a stale registry
    built for an earlier release cannot satisfy a newer one.
    """
    registry = registry if registry is not None else PredicateRegistry()
    kb_version = resolver.release.kb_version
    for row in sorted(resolver.bindings_for(decision_type),
                      key=lambda r: (int(r["precedence"]), r["rule_id"])):
        name = row["predicate_name"]
        try:
            predicate = predicates_by_name[name]
        except KeyError:
            raise NoExecutableRuleSet(
                f"binding {row['rule_id']!r} names predicate {name!r}, which the "
                "domain pack does not export"
            ) from None
        registry.register(decision_type, row["rule_id"], kb_version, predicate)
    return registry
