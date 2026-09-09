"""Read-only Claris canonical lookup, and the domain facts it produces.

BOUNDARY (D.4E sections 4 and 14)
---------------------------------
This module is the ONLY place that knows the names claris.product and
claris.configuration. The generic executor never sees a table name, a SQL
string, a cursor or a row; predicates never see one either. What crosses the
boundary is three named domain facts and nothing else:

    product_exists                 bool
    existing_configuration_count   int
    exact_identity_match_exists    bool

EXACT IDENTITY MATCH ELIGIBILITY -- D.4E correction
---------------------------------------------------
`exact_identity_match_exists` is TRUE only when a matching configuration is
CURRENTLY ELIGIBLE: `status = 'active' AND archived_at IS NULL`.

An archived-only match returns FALSE. Treating an archived configuration as an
exact identity match would let IR-010 conclude NO_BUSINESS_CHANGE against a
configuration that is no longer live, and that governance semantic has never
been established. No reactivation semantic is invented in its place, and this
module does not decide what an archived-only match SHOULD mean -- IR-010
simply does not fire.

`existing_configuration_count` is deliberately UNCHANGED and still counts
archived configurations. The two facts answer different questions: "has this
product ever had a configuration" (which governs IR-013's initial-configuration
condition) versus "is this exact identity live right now".

A fact that could not be computed crosses as `Unavailable(reason=...)` rather
than as a fabricated False or 0. The difference matters twice over: a governed
record must not claim the business has no product when the truth is that the
platform could not look, and `input_digest` must distinguish the two.

AS-OF vs CURRENT STATE -- carried-open item V-4 (section 5)
-----------------------------------------------------------
What the canonical schema actually provides:

    claris.product        product_id, product_name, created_at
    claris.configuration  configuration_id, product_id, canonical_identity,
                          identity_digest, status, governed_identity,
                          created_at, created_by, archived_at

claris.product records when a product appeared and NOTHING about when it
ceased to exist -- no archived_at, no status, no validity interval. A product
deleted from the table leaves no trace, so "did this product exist at horizon
T" is not answerable from this schema at all.

claris.configuration is better but still not sufficient: created_at plus
archived_at bound a rough interval, yet canonical_identity itself is mutable
in place with no version history, so the identity a configuration had at
horizon T is unrecoverable once it changes.

Therefore this adapter implements CURRENT-STATE DOMAIN LOOKUP and says so.
It does not filter on decision_horizon, because a filter would dress a
current-state read as historical replay. `LookupSemantics.CURRENT_STATE` and
`REPLAY_SAFETY` travel on every result so no caller has to guess.

    REPLAY-SAFE AS-OF DOMAIN LOOKUP: NOT IMPLEMENTED -- schema insufficient.
    Canonical lookup replay status: PARTIAL / NOT YET REPLAY-SAFE.

SAFETY
    Read-only. Every statement is a parameterized SELECT submitted through
    decisions.adapters.connection.ReadOnlyDatabase, which refuses anything that
    is not SELECT/WITH before it reaches the server, on a session pinned READ
    ONLY. No INSERT, UPDATE, DELETE or DDL appears in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ...contracts import (
    DecisionRequest,
    DomainFacts,
    FoldSnapshotView,
    FoldState,
    Known,
    Unavailable,
)
from .errors import (
    CanonicalLookupError,
    ConfigurationEligibilityUnknown,
    InvalidIdentityState,
)
from .identity import identity_inputs, serialize_canonical_identity

__all__ = [
    "PRODUCT_EXISTS",
    "EXISTING_CONFIGURATION_COUNT",
    "EXACT_IDENTITY_MATCH_EXISTS",
    "DOMAIN_FACT_NAMES",
    "LookupSemantics",
    "REPLAY_SAFETY",
    "ACTIVE_STATUS",
    "ARCHIVED_STATUS",
    "CONFIGURATION_STATUS_VOCABULARY",
    "UNAVAILABLE_PRODUCT_REFERENCE_NOT_ESTABLISHED",
    "UNAVAILABLE_IDENTITY_NOT_SERIALIZABLE",
    "CanonicalLookupResult",
    "CanonicalIdentityLookup",
    "ClarisIdentityFactProvider",
    "facts_from",
]

# -- domain fact names (the entire vocabulary crossing the boundary) -----
PRODUCT_EXISTS = "product_exists"
EXISTING_CONFIGURATION_COUNT = "existing_configuration_count"
EXACT_IDENTITY_MATCH_EXISTS = "exact_identity_match_exists"

DOMAIN_FACT_NAMES: tuple[str, ...] = (
    PRODUCT_EXISTS,
    EXISTING_CONFIGURATION_COUNT,
    EXACT_IDENTITY_MATCH_EXISTS,
)

# -- fixed Unavailable reasons -------------------------------------------
# Fixed strings, not formatted messages: an Unavailable reason enters
# input_digest, so a message carrying a subject id or a timestamp would make
# two identical governed situations produce two different digests.
UNAVAILABLE_PRODUCT_REFERENCE_NOT_ESTABLISHED = "PRODUCT_REFERENCE_NOT_ESTABLISHED"
UNAVAILABLE_IDENTITY_NOT_SERIALIZABLE = "IDENTITY_NOT_SERIALIZABLE"


class LookupSemantics(Enum):
    """Which question a lookup result actually answers."""

    CURRENT_STATE = "CURRENT_STATE"
    AS_OF_HORIZON = "AS_OF_HORIZON"


#: Carried-open item V-4. See the module docstring.
REPLAY_SAFETY = "PARTIAL / NOT YET REPLAY-SAFE"

PRODUCT_SCHEMA = "claris"
PRODUCT_TABLE = "product"
CONFIGURATION_TABLE = "configuration"

PRODUCT_EXISTS_SQL = f"""
SELECT EXISTS (
    SELECT 1 FROM {PRODUCT_SCHEMA}.{PRODUCT_TABLE} WHERE product_id = %s
) AS product_exists
"""

CONFIGURATION_COUNT_SQL = f"""
SELECT count(*) AS n
FROM {PRODUCT_SCHEMA}.{CONFIGURATION_TABLE}
WHERE product_id = %s
"""

#: The governed lifecycle vocabulary of claris.configuration.status. Closed by
#: CONSTRAINT check_configuration_status CHECK (status IN ('active','archived')).
ACTIVE_STATUS = "active"
ARCHIVED_STATUS = "archived"
CONFIGURATION_STATUS_VOCABULARY: tuple[str, ...] = (ACTIVE_STATUS, ARCHIVED_STATUS)

#: An exact identity match is resolved by CLASSIFYING the matching rows, not by
#: EXISTS. The three buckets are deliberately not symmetric:
#:
#:   eligible       currently active AND not archived. Only this returns TRUE.
#:   ineligible     archived by status OR by archived_at. Includes the
#:                  contradictory status='active' + archived_at IS NOT NULL row,
#:                  which is treated as archived because the conservative
#:                  reading never invents reactivation.
#:   unclassifiable status outside the governed vocabulary AND no archived_at,
#:                  so the row cannot be placed either way -> system failure.
EXACT_IDENTITY_SQL = f"""
SELECT
    count(*) FILTER (
        WHERE status = %s AND archived_at IS NULL
    ) AS eligible_matches,
    count(*) FILTER (
        WHERE status = %s OR archived_at IS NOT NULL
    ) AS ineligible_matches,
    count(*) FILTER (
        WHERE (status IS NULL OR status NOT IN (%s, %s))
          AND archived_at IS NULL
    ) AS unclassifiable_matches,
    count(*) AS total_matches
FROM {PRODUCT_SCHEMA}.{CONFIGURATION_TABLE}
WHERE canonical_identity = %s
"""

#: Reports whether the deployed schema can answer "is this configuration
#: currently eligible" at all, so the D.4E STOP condition is re-evaluated
#: against the real database rather than assumed from the DDL file.
ELIGIBILITY_COLUMNS_SQL = """
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_schema = %s AND table_name = %s AND column_name = ANY(%s)
ORDER BY column_name
"""

ELIGIBILITY_CONSTRAINT_SQL = """
SELECT c.conname, pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = %s AND t.relname = %s AND c.contype = 'c'
ORDER BY c.conname
"""

#: Reports which temporal/version columns the deployment actually has, so the
#: as-of verdict is measured rather than asserted.
TEMPORAL_COLUMNS_SQL = """
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = %s AND table_name = ANY(%s)
ORDER BY table_name, ordinal_position
"""


@dataclass(frozen=True)
class CanonicalLookupResult:
    """Domain facts, plus the semantics under which they were obtained.

    `semantics` and `replay_safety` are attributes of the RESULT, not domain
    facts. They describe how the platform looked, not what the business is, so
    they stay out of DomainFacts and therefore out of input_digest.
    """

    product_exists: Optional[bool]
    existing_configuration_count: Optional[int]
    exact_identity_match_exists: Optional[bool]
    canonical_identity: Optional[str]
    product_reference: Optional[str]
    #: Breakdown behind exact_identity_match_exists. Reporting detail, NOT
    #: domain facts -- they stay out of DomainFacts and out of input_digest.
    eligible_identity_matches: Optional[int] = None
    ineligible_identity_matches: Optional[int] = None
    semantics: LookupSemantics = LookupSemantics.CURRENT_STATE
    replay_safety: str = REPLAY_SAFETY
    unavailable: tuple[tuple[str, str], ...] = ()

    def to_domain_facts(self) -> DomainFacts:
        """Exactly the three required facts. Never a row, never a handle."""
        reasons = dict(self.unavailable)
        facts = {}
        for name, value in (
            (PRODUCT_EXISTS, self.product_exists),
            (EXISTING_CONFIGURATION_COUNT, self.existing_configuration_count),
            (EXACT_IDENTITY_MATCH_EXISTS, self.exact_identity_match_exists),
        ):
            if value is None:
                facts[name] = Unavailable(reasons.get(name, "NOT_COMPUTED"))
            else:
                facts[name] = Known(value)
        return DomainFacts(facts)


def facts_from(result: CanonicalLookupResult) -> DomainFacts:
    """Section 14's minimal adapter, as a free function."""
    return result.to_domain_facts()


class CanonicalIdentityLookup:
    """Read-only canonical lookup over claris.product and claris.configuration.

    Constructed with a ReadOnlyDatabase (or anything exposing the same
    `query`/`scalar` surface, which is what makes it unit-testable with no
    database at all).
    """

    __slots__ = ("_db",)

    def __init__(self, db) -> None:
        if db is None or not hasattr(db, "query"):
            raise CanonicalLookupError(
                "CanonicalIdentityLookup requires a read-only database with a "
                f"query() method, got {type(db).__name__}"
            )
        self._db = db

    # -- primitives ------------------------------------------------------

    def product_exists(self, product_reference: str) -> bool:
        rows = self._query(PRODUCT_EXISTS_SQL, (product_reference,))
        return bool(rows[0]["product_exists"]) if rows else False

    def configuration_count(self, product_reference: str) -> int:
        """Every configuration of this product, archived ones included.

        An archived configuration still means this product has had one, so
        IR-013's 'initial configuration' condition is not satisfied by it. The
        alternative -- counting only status='active' -- would let an archived
        configuration be silently recreated as if it were the first.
        """
        rows = self._query(CONFIGURATION_COUNT_SQL, (product_reference,))
        return int(rows[0]["n"]) if rows else 0

    def classify_identity_matches(self, canonical_identity: str) -> dict:
        """Split configurations carrying this identity into eligibility buckets.

        Returns eligible / ineligible / unclassifiable / total counts.
        """
        rows = self._query(
            EXACT_IDENTITY_SQL,
            (
                ACTIVE_STATUS,
                ARCHIVED_STATUS,
                ACTIVE_STATUS,
                ARCHIVED_STATUS,
                canonical_identity,
            ),
        )
        if not rows:
            return {
                "eligible_matches": 0,
                "ineligible_matches": 0,
                "unclassifiable_matches": 0,
                "total_matches": 0,
            }
        row = rows[0]
        return {key: int(row[key] or 0) for key in (
            "eligible_matches", "ineligible_matches",
            "unclassifiable_matches", "total_matches",
        )}

    def exact_identity_match_exists(self, canonical_identity: str) -> bool:
        """TRUE only for a CURRENTLY ELIGIBLE exact identity match.

        D.4E correction -- archived exact identity semantics.

        The earlier implementation asked EXISTS(canonical_identity = ?), which
        made an archived-only match return TRUE and let IR-010 conclude
        NO_BUSINESS_CHANGE against a configuration that is no longer live. That
        governance semantic was never established, so it is withdrawn.

        Eligible means, and only means, `status = 'active' AND archived_at IS
        NULL` -- the lifecycle claris.configuration itself defines. An
        archived-only match returns FALSE. Nothing here reactivates, revives or
        reuses an archived configuration, and nothing here decides what SHOULD
        happen when only an archived match exists: IR-010 simply does not fire,
        and the outcome falls to the rules that remain.

        A row whose status is outside the governed vocabulary and which carries
        no archived_at raises rather than being guessed either way.
        """
        counts = self.classify_identity_matches(canonical_identity)
        if counts["unclassifiable_matches"]:
            raise ConfigurationEligibilityUnknown(
                f"{counts['unclassifiable_matches']} configuration(s) carrying "
                f"canonical_identity {canonical_identity!r} have a status outside "
                f"the governed vocabulary {CONFIGURATION_STATUS_VOCABULARY} and no "
                "archived_at; current eligibility cannot be determined and must "
                "not be guessed"
            )
        return counts["eligible_matches"] > 0

    def eligibility_capability(self) -> dict:
        """Whether the deployed schema can determine current eligibility.

        Measured from information_schema and pg_constraint, so the D.4E STOP
        condition is re-checked against the real database.
        """
        columns = {
            row["column_name"]: row["is_nullable"]
            for row in self._query(
                ELIGIBILITY_COLUMNS_SQL,
                (PRODUCT_SCHEMA, CONFIGURATION_TABLE, ["status", "archived_at"]),
            )
        }
        constraints = {
            row["conname"]: row["definition"]
            for row in self._query(
                ELIGIBILITY_CONSTRAINT_SQL, (PRODUCT_SCHEMA, CONFIGURATION_TABLE)
            )
        }
        vocabulary_closed = any(
            ACTIVE_STATUS in definition and ARCHIVED_STATUS in definition
            for definition in constraints.values()
        )
        return {
            "columns": columns,
            "check_constraints": constraints,
            "has_status": "status" in columns,
            "has_archived_at": "archived_at" in columns,
            "vocabulary_closed_to_active_archived": vocabulary_closed,
            "eligibility_determinable": (
                "status" in columns and "archived_at" in columns and vocabulary_closed
            ),
            "governed_vocabulary": CONFIGURATION_STATUS_VOCABULARY,
        }

    def temporal_capability(self) -> dict:
        """What temporal/version columns exist, and the resulting V-4 verdict."""
        rows = self._query(
            TEMPORAL_COLUMNS_SQL,
            (PRODUCT_SCHEMA, [PRODUCT_TABLE, CONFIGURATION_TABLE]),
        )
        columns: dict[str, list] = {PRODUCT_TABLE: [], CONFIGURATION_TABLE: []}
        for row in rows:
            columns.setdefault(row["table_name"], []).append(row["column_name"])
        product = set(columns.get(PRODUCT_TABLE, ()))
        configuration = set(columns.get(CONFIGURATION_TABLE, ()))
        # An as-of read needs a validity interval on BOTH tables. product has
        # no end-of-life column at all, so the answer is settled there.
        product_as_of = bool(product & {"archived_at", "valid_to", "retired_at", "status"})
        configuration_as_of = bool(configuration & {"archived_at", "valid_to"})
        return {
            "columns": {k: tuple(v) for k, v in columns.items()},
            "product_supports_as_of": product_as_of,
            "configuration_supports_as_of": configuration_as_of,
            "as_of_supported": product_as_of and configuration_as_of,
            "semantics": LookupSemantics.CURRENT_STATE.value,
            "replay_safety": REPLAY_SAFETY,
        }

    # -- composition -----------------------------------------------------

    def lookup(
        self,
        product_reference: Optional[str],
        canonical_identity: Optional[str],
    ) -> CanonicalLookupResult:
        """One current-state lookup. Unavailable inputs stay Unavailable."""
        unavailable: list[tuple[str, str]] = []

        if product_reference is None:
            exists = None
            count = None
            unavailable.append(
                (PRODUCT_EXISTS, UNAVAILABLE_PRODUCT_REFERENCE_NOT_ESTABLISHED)
            )
            unavailable.append(
                (
                    EXISTING_CONFIGURATION_COUNT,
                    UNAVAILABLE_PRODUCT_REFERENCE_NOT_ESTABLISHED,
                )
            )
        else:
            exists = self.product_exists(product_reference)
            count = self.configuration_count(product_reference)

        eligible = ineligible = None
        if canonical_identity is None:
            match = None
            unavailable.append(
                (EXACT_IDENTITY_MATCH_EXISTS, UNAVAILABLE_IDENTITY_NOT_SERIALIZABLE)
            )
        else:
            counts = self.classify_identity_matches(canonical_identity)
            if counts["unclassifiable_matches"]:
                raise ConfigurationEligibilityUnknown(
                    f"{counts['unclassifiable_matches']} configuration(s) carrying "
                    f"canonical_identity {canonical_identity!r} have a status "
                    f"outside the governed vocabulary "
                    f"{CONFIGURATION_STATUS_VOCABULARY} and no archived_at; current "
                    "eligibility cannot be determined and must not be guessed"
                )
            eligible = counts["eligible_matches"]
            ineligible = counts["ineligible_matches"]
            match = eligible > 0

        return CanonicalLookupResult(
            product_exists=exists,
            existing_configuration_count=count,
            exact_identity_match_exists=match,
            canonical_identity=canonical_identity,
            product_reference=product_reference,
            eligible_identity_matches=eligible,
            ineligible_identity_matches=ineligible,
            unavailable=tuple(unavailable),
        )

    def lookup_for_fold(self, fold: FoldSnapshotView) -> CanonicalLookupResult:
        """Derive both lookup keys from the Fold, then look them up.

        Two governed states are handled deliberately differently.

        FoldState.INVALID on a required identity property raises immediately.
        Section 3 classifies an invalid state as a system/configuration error,
        and no governed rule claims it -- IR-011 enumerates UNREPORTED,
        EXPLICITLY_UNDEFINED and absent, IR-012 enumerates CONTRADICTED, and
        neither covers INVALID. Letting it fall through would produce a
        business CANNOT_DECIDE / NO_RULE_MATCHED, which is precisely the
        conversion section 25 forbids: a governed statement that the business
        could not decide, when the truth is that the platform holds unusable
        state.

        Every other non-ESTABLISHED state is a business condition. The
        canonical identity is serialized only when all four required
        properties are ESTABLISHED, so UNREPORTED / EXPLICITLY_UNDEFINED /
        CONTRADICTED reach the serializer never, and reach IR-011 and IR-012 as
        the governed conditions they are.
        """
        inputs = identity_inputs(fold)
        if inputs.invalid:
            raise InvalidIdentityState(
                "required identity properties carry FoldState.INVALID: "
                + ", ".join(sorted(inputs.invalid))
                + "; this is a system/configuration failure and must not be "
                "reported as a business CANNOT_DECIDE"
            )

        product_reference = None
        prop = fold.property_named("product_reference")
        if prop is not None and prop.fold_state is FoldState.ESTABLISHED:
            value = prop.resolved_value
            if isinstance(value, str) and not isinstance(value, bool):
                product_reference = value

        canonical_identity = (
            serialize_canonical_identity(fold) if inputs.all_established else None
        )
        return self.lookup(product_reference, canonical_identity)

    # -- internals -------------------------------------------------------

    def _query(self, sql: str, params) -> list:
        """Every read goes through here so failures classify identically.

        A database failure is a SYSTEM failure (section 25). It is re-raised as
        CanonicalLookupError and never degraded into product_exists = FALSE.
        """
        try:
            return self._db.query(sql, params)
        except Exception as exc:  # noqa: BLE001 - re-raised, never swallowed
            raise CanonicalLookupError(
                f"canonical lookup failed ({type(exc).__name__}: {exc}); this is "
                "a system failure and must not be reported as a business fact"
            ) from exc


class ClarisIdentityFactProvider:
    """DomainFactProviderPort implementation for IDENTITY_ASSESSMENT."""

    __slots__ = ("_lookup", "_last_result")

    def __init__(self, lookup: CanonicalIdentityLookup) -> None:
        if not isinstance(lookup, CanonicalIdentityLookup):
            raise CanonicalLookupError(
                "ClarisIdentityFactProvider requires a CanonicalIdentityLookup, "
                f"got {type(lookup).__name__}"
            )
        self._lookup = lookup
        self._last_result: Optional[CanonicalLookupResult] = None

    @property
    def last_result(self) -> Optional[CanonicalLookupResult]:
        """The most recent lookup, for reporting. Not part of any context."""
        return self._last_result

    def facts_for(
        self, request: DecisionRequest, fold: FoldSnapshotView
    ) -> DomainFacts:
        result = self._lookup.lookup_for_fold(fold)
        self._last_result = result
        return result.to_domain_facts()

