"""Claris domain pack.

STEP 5G.6 PHASE D.4E -- the IDENTITY_ASSESSMENT domain pack.

Every piece of Claris business semantics in the decision runtime lives under
this package. The generic platform (decisions/contracts.py, digest.py,
executor.py, registry.py, rules.py) does not import it and does not know it
exists; the dependency points one way only.

    errors.py       domain system/configuration failures
    identity.py     the locked identity tuple and its canonical serializer
    lookup.py       read-only claris.product / claris.configuration lookup
    registration.py rule-class mapping, precedence, registry binding
    predicates/     IR-011, IR-012, IR-013, IR-010

GOVERNANCE STATUS
    IR-010..IR-013 remain PROPOSED semantic candidates in
    claris_kb.identity_rules at kb_version 1.0.1. There are ZERO executable
    IDENTITY_ASSESSMENT rows in claris_kb.decision_rules and D.4E adds none.
    Governed IDENTITY_ASSESSMENT execution stays blocked until executable
    projection and activation are designed.

NOT IN THIS PHASE
    decision persistence, authorization, actions, projection, and any creation
    of Product / Configuration / ConfigurationVersion.
"""

from __future__ import annotations

from .errors import (
    CanonicalLookupError,
    ClarisDomainError,
    IdentityNotSerializable,
    InvalidDomainFact,
    InvalidIdentityState,
    InvalidIdentityValue,
)
from .identity import (
    DECISION_TYPE,
    IDENTITY_DELIMITER,
    IDENTITY_ENCODING_VERSION,
    encode_identity_values,
    parse_canonical_identity,
    IDENTITY_PROPERTIES,
    SUBJECT_TYPE,
    contradicted_identity_properties,
    identity_inputs,
    identity_inputs_established,
    missing_identity_properties,
    render_term_months,
    serialize_canonical_identity,
    try_serialize_canonical_identity,
)
from .lookup import (
    DOMAIN_FACT_NAMES,
    EXACT_IDENTITY_MATCH_EXISTS,
    EXISTING_CONFIGURATION_COUNT,
    PRODUCT_EXISTS,
    REPLAY_SAFETY,
    CanonicalIdentityLookup,
    CanonicalLookupResult,
    ClarisIdentityFactProvider,
    LookupSemantics,
)
from .registration import (
    IDENTITY_RULE_ORDER,
    SEMANTIC_RULE_ORDER,
    EXECUTABLE_RULE_IDS,
    executable_rule_id,
    IDENTITY_SEMANTIC_RULES,
    PROTOTYPE_ONTOLOGY_VERSION,
    PROTOTYPE_VALIDATION_STATUS,
    PROTOTYPE_LABEL,
    SEMANTIC_KB_VERSION,
    SEMANTIC_RULE_STATUS,
    build_prototype_registry,
    identity_class_bindings,
    prototype_governance_binding,
    prototype_rule_bindings,
    register_identity_assessment,
)

__all__ = [
    "DECISION_TYPE",
    "SUBJECT_TYPE",
    "IDENTITY_PROPERTIES",
    "IDENTITY_DELIMITER",
    "IDENTITY_ENCODING_VERSION",
    "encode_identity_values",
    "parse_canonical_identity",
    "identity_inputs",
    "identity_inputs_established",
    "missing_identity_properties",
    "contradicted_identity_properties",
    "render_term_months",
    "serialize_canonical_identity",
    "try_serialize_canonical_identity",
    "PRODUCT_EXISTS",
    "EXISTING_CONFIGURATION_COUNT",
    "EXACT_IDENTITY_MATCH_EXISTS",
    "DOMAIN_FACT_NAMES",
    "LookupSemantics",
    "REPLAY_SAFETY",
    "CanonicalIdentityLookup",
    "CanonicalLookupResult",
    "ClarisIdentityFactProvider",
    "SEMANTIC_KB_VERSION",
    "SEMANTIC_RULE_STATUS",
    "PROTOTYPE_ONTOLOGY_VERSION",
    "PROTOTYPE_VALIDATION_STATUS",
    "PROTOTYPE_LABEL",
    "IDENTITY_SEMANTIC_RULES",
    "IDENTITY_RULE_ORDER",
    "SEMANTIC_RULE_ORDER",
    "EXECUTABLE_RULE_IDS",
    "executable_rule_id",
    "identity_class_bindings",
    "register_identity_assessment",
    "prototype_rule_bindings",
    "prototype_governance_binding",
    "build_prototype_registry",
    "ClarisDomainError",
    "IdentityNotSerializable",
    "InvalidIdentityState",
    "InvalidIdentityValue",
    "CanonicalLookupError",
    "InvalidDomainFact",
]
