"""Claris domain system/configuration failures.

D.4E section 25 draws a line the platform already draws (D.4B section O) and
the domain pack must not blur:

    BUSINESS outcome   IR-011 / IR-012 -> CANNOT_DECIDE. A governed statement
                       about the subject. Persistable, not retryable.
    SYSTEM failure     everything in this module. Nothing was decided, nothing
                       may be persisted, and the condition is retryable once
                       the defect is fixed.

Every class here subclasses the platform's DecisionExecutionError, so a caller
that catches system failures catches these too and never mistakes one for a
business CANNOT_DECIDE.

`IdentityNotSerializable` is the deliberate exception to the rule that
everything here is a system failure: see its docstring. It exists so that
"this identity cannot be serialized" is representable as a value, and it is
raised only by the STRICT serializer, whose caller has already asserted the
inputs are usable.
"""

from __future__ import annotations

from ...errors import DecisionExecutionError

__all__ = [
    "ClarisDomainError",
    "IdentityNotSerializable",
    "InvalidIdentityState",
    "InvalidIdentityValue",
    "CanonicalLookupError",
    "ConfigurationEligibilityUnknown",
    "InvalidDomainFact",
]


class ClarisDomainError(DecisionExecutionError):
    """Base for Claris domain-pack failures."""


class IdentityNotSerializable(ClarisDomainError):
    """A required identity property is absent, UNREPORTED, EXPLICITLY_UNDEFINED
    or CONTRADICTED, so the canonical identity tuple cannot be formed.

    D.4E section 3: such an identity MUST NOT serialize.

    This condition is ALSO the business situation IR-011 and IR-012 exist to
    report. It is therefore never allowed to reach the executor as an
    exception on the ordinary path: `try_serialize_canonical_identity` returns
    None for it, the lookup adapter turns it into an `Unavailable` domain fact,
    and the GUARD predicates convert it into a governed CANNOT_DECIDE. It is
    raised only by the strict `serialize_canonical_identity`, which a caller
    invokes after establishing that the inputs are usable -- so reaching it is
    a caller defect, not a governed condition.
    """


class InvalidIdentityState(ClarisDomainError):
    """A required identity property carries FoldState.INVALID.

    D.4E section 3: an invalid state MUST fail as a system/configuration error.
    INVALID is not one of the states IR-011 (section 6) or IR-012 (section 7)
    enumerate, so no governed rule claims it and the domain pack must not
    invent one.
    """


class InvalidIdentityValue(ClarisDomainError):
    """An ESTABLISHED identity property carries a value the domain cannot render.

    A malformed term_months, or an ESTABLISHED property whose resolved_value is
    None. D.4E section 25 classifies both as system/configuration failures, not
    as a business CANNOT_DECIDE.
    """


class CanonicalLookupError(ClarisDomainError):
    """The read-only canonical lookup could not be performed.

    A database failure is a system failure (section 25). It is never converted
    into `product_exists = FALSE`, which would be an assertion about the
    business rather than a report about the platform.
    """


class ConfigurationEligibilityUnknown(CanonicalLookupError):
    """A configuration row carries a status outside the governed vocabulary,
    so whether it is currently eligible cannot be determined.

    claris.configuration constrains status to exactly ('active', 'archived'),
    but the column is nullable and the CHECK passes for NULL. A row that is
    neither, and carries no archived_at either, cannot be classified.

    Classifying it as eligible would let an ungoverned row satisfy IR-010 and
    conclude NO_BUSINESS_CHANGE. Classifying it as ineligible would assert the
    identity is free when nobody knows. Both invent governance, so neither is
    done: this is reported as a system/configuration failure.
    """


class InvalidDomainFact(ClarisDomainError):
    """A domain fact carries a type the predicate contract does not permit.

    Section 25 lists 'invalid domain fact type' as a system failure. A
    predicate that silently treated a string 'FALSE' as truthy would fabricate
    a governed outcome.
    """
