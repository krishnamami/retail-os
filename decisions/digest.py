"""Deterministic input_digest, implementing the D.4B section K contract exactly.

INCLUDED
    decision_type, subject_type, subject_id, resolved decision_horizon,
    ontology_version, kb_version, policy_version, rule_set_digest,
    fold_state_id, fold properties sorted by property_name (name, fold_state,
    resolved_value, property_value_type, effective_at, latest_known_arrival_at,
    sorted basis_assertion_ids), domain facts sorted by fact_name,
    digest_scheme_version.

EXCLUDED
    requested_at, correlation_id, requested_by, evaluated_at, decided_at,
    executor build metadata. These vary between identical executions and would
    destroy replay.

CANONICALIZATION
    UTF-8; object keys sorted by Unicode code point; no insignificant
    whitespace; set-valued arrays (basis_assertion_ids) sorted; sequence-valued
    arrays keep order; timestamps RFC 3339 UTC with microseconds and a Z
    suffix; null distinct from absent; integers decimal with no exponent and no
    trailing '.0'; booleans true/false.

ALGORITHM
    SHA-256 over the canonical UTF-8 bytes, lowercase hex, tagged:

        v1:sha256:<hex>

    The tag is not decoration. Without it a future canonicalization change
    silently invalidates every stored digest and replay comparison.

Python's built-in hash() is never used: it is salted per process and is not
stable across runs.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .contracts import DecisionContext, Known, Unavailable
from .errors import DigestSerializationError

__all__ = ["DIGEST_SCHEME_VERSION", "canonical_json", "compute_input_digest"]

DIGEST_SCHEME_VERSION = "v1"
_HASH_NAME = "sha256"


def _ts(value: datetime) -> str:
    """RFC 3339, UTC, microsecond precision, Z suffix."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise DigestSerializationError(
            "naive datetime cannot be canonically serialized; timezone required"
        )
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _escape(text: str) -> str:
    out = []
    for ch in text:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def canonical_json(value: Any) -> str:
    """Canonical JSON text for a restricted, fully-determined value space."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, float):
        raise DigestSerializationError(
            "float is not canonically serializable (binary rounding is not "
            "reproducible across platforms); use int, str or Decimal"
        )
    if isinstance(value, str):
        return f'"{_escape(value)}"'
    if isinstance(value, datetime):
        return f'"{_ts(value)}"'
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: kv[0])
        return "{" + ",".join(
            f'"{_escape(str(k))}":{canonical_json(v)}' for k, v in items
        ) + "}"
    raise DigestSerializationError(
        f"unsupported type for canonical serialization: {type(value).__name__}"
    )


def digest_payload(context: DecisionContext) -> dict:
    """The exact structure that gets hashed. Exposed for auditability."""
    fold = context.fold
    gov = context.governance

    properties = []
    for name in sorted(fold.properties):
        prop = fold.properties[name]
        properties.append(
            {
                "property_name": prop.property_name,
                "fold_state": prop.fold_state.value,
                "resolved_value": prop.resolved_value,
                "property_value_type": prop.property_value_type,
                "effective_at": prop.effective_at,
                "latest_known_arrival_at": prop.latest_known_arrival_at,
                # set-valued: sorted so storage order cannot alter the digest
                "basis_assertion_ids": sorted(prop.basis_assertion_ids),
            }
        )

    facts = []
    for name in sorted(context.facts.facts):
        fact = context.facts.facts[name]
        if isinstance(fact, Known):
            facts.append({"fact_name": name, "status": "KNOWN", "value": fact.value})
        elif isinstance(fact, Unavailable):
            facts.append(
                {"fact_name": name, "status": "UNAVAILABLE", "reason": fact.reason}
            )
        else:  # pragma: no cover - guarded at construction
            raise DigestSerializationError(f"unknown fact type for {name!r}")

    return {
        "digest_scheme_version": DIGEST_SCHEME_VERSION,
        "decision_type": context.request.decision_type,
        "subject_type": context.request.subject_type,
        "subject_id": context.request.subject_id,
        "decision_horizon": context.request.decision_horizon,
        "ontology_version": gov.ontology_version,
        "kb_version": gov.kb_version,
        "policy_version": gov.policy_version,
        "rule_set_digest": gov.rule_set_digest,
        "fold_state_id": fold.fold_state_id,
        "fold_status": fold.fold_status.value,
        "folded_properties": properties,
        "domain_facts": facts,
    }


def compute_input_digest(context: DecisionContext) -> str:
    """Tagged SHA-256 over the canonical payload.

    Replay property: identical governed inputs plus identical
    (ontology_version, kb_version, policy_version, rule_set_digest,
    digest_scheme_version) produce an identical digest.
    """
    canonical = canonical_json(digest_payload(context))
    hexdigest = hashlib.new(_HASH_NAME, canonical.encode("utf-8")).hexdigest()
    return f"{DIGEST_SCHEME_VERSION}:{_HASH_NAME}:{hexdigest}"
