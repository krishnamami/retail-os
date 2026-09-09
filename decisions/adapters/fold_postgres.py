"""Read-only Fold snapshot loader.

Generic infrastructure. This module knows nothing about IDENTITY_ASSESSMENT,
CHANGE_CLASSIFICATION, LAUNCH_READINESS, Claris identity rules or canonical
identity. It reads state.fold_state_snapshot and produces D.4C contracts.

HORIZON SEMANTICS -- established from the repository, not invented
------------------------------------------------------------------
Lookup is EXACT EQUALITY on decision_horizon:

    WHERE subject_type = %s AND subject_id = %s AND decision_horizon = %s

Evidence:
  * Every existing consumer selects snapshots this way -- tests/fold/
    test_fold_idempotency.sql, test_fold_lineage.sql, database/fold/*.
    There is no `decision_horizon <=` lookup anywhere in the repository.
    (The single `<` occurrence, execute_fold_extension.py:112, is a
    "which subjects are new since the prior horizon" analysis query.)
  * Snapshots are MATERIALIZED per horizon by
    runtime.fold_snapshot_at_horizon(p_decision_horizon). A snapshot exists
    only for a horizon that was actually folded, so "nearest earlier horizon"
    would silently answer a different question than the one asked.
  * fold_state_unique_horizon UNIQUE (decision_horizon, subject_type,
    subject_id) makes exact equality yield at most one row.

This preserves replay: the same horizon always resolves the same snapshot.

BUSINESS SEMANTICS ARE NOT APPLIED HERE
    UNREPORTED stays UNREPORTED. CONTRADICTED stays CONTRADICTED. Nothing is
    coerced to null, to ESTABLISHED, or to CANNOT_DECIDE. The loader
    represents governed state; predicates interpret it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from ..contracts import FoldProperty, FoldSnapshotView, FoldState
from ..ports import FoldLoadResult, FoldLoadStatus
from .errors import (
    DuplicateFoldSnapshot,
    InvalidFoldPropertyState,
    MalformedFoldSnapshot,
)

__all__ = [
    "REQUIRED_PROPERTY_KEYS",
    "FOLD_SNAPSHOT_SQL",
    "parse_timestamp",
    "_normalise_iso",
    "parse_assertion_ids",
    "parse_fold_property",
    "parse_folded_properties",
    "build_snapshot_view",
    "PostgresFoldLoader",
]

REQUIRED_PROPERTY_KEYS = (
    "property_name",
    "resolved_value",
    "property_value_type",
    "fold_state",
    "effective_at",
    "latest_known_arrival_at",
    "basis_assertion_ids",
)

FOLD_SNAPSHOT_SQL = """
SELECT fold_state_id,
       decision_horizon,
       subject_type,
       subject_id,
       fold_status,
       folded_properties,
       basis_assertion_ids,
       kb_version,
       policy_version,
       fold_computed_at
FROM state.fold_state_snapshot
WHERE subject_type = %s
  AND subject_id = %s
  AND decision_horizon = %s
"""

HORIZONS_SQL = """
SELECT decision_horizon
FROM state.fold_state_snapshot
WHERE subject_type = %s AND subject_id = %s
ORDER BY decision_horizon
"""

SUBJECTS_SQL = """
SELECT subject_type, subject_id, decision_horizon, fold_status
FROM state.fold_state_snapshot
WHERE subject_type = %s
ORDER BY subject_id, decision_horizon
"""


# ======================================================================
# pure parsing -- no I/O, fully unit-testable
# ======================================================================

def _normalise_iso(text: str) -> str:
    """Normalise a PostgreSQL timestamptz string for datetime.fromisoformat.

    Python 3.11 relaxed fromisoformat; 3.10 did not. PostgreSQL renders the UTC
    offset as '+00', which 3.10 rejects. Both forms are normalised to '+00:00'
    so the loader behaves identically on 3.10, 3.11 and 3.12.
    """
    text = text.strip().replace(" ", "T", 1)
    if text.endswith("Z"):
        return text[:-1] + "+00:00"
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)   # +0000 -> +00:00
    text = re.sub(r"([+-]\d{2})$", r"\1:00", text)          # +00   -> +00:00
    return text


def parse_timestamp(value: Any, *, field: str, property_name: str) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = _normalise_iso(value)
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise MalformedFoldSnapshot(
                f"property {property_name!r}: {field} is not a valid timestamp: {value!r}"
            ) from exc
    else:
        raise MalformedFoldSnapshot(
            f"property {property_name!r}: {field} has unsupported type "
            f"{type(value).__name__}"
        )
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        # governed timestamps are timestamptz; a naive value means the driver
        # or the data lost the zone, which must not be silently assumed UTC
        raise MalformedFoldSnapshot(
            f"property {property_name!r}: {field} is not timezone-aware: {value!r}"
        )
    return dt


def parse_assertion_ids(value: Any, *, property_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise MalformedFoldSnapshot(
                f"property {property_name!r}: basis_assertion_ids is not valid JSON"
            ) from exc
    if not isinstance(value, (list, tuple)):
        raise MalformedFoldSnapshot(
            f"property {property_name!r}: basis_assertion_ids must be an array, "
            f"got {type(value).__name__}"
        )
    ids = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise MalformedFoldSnapshot(
                f"property {property_name!r}: basis_assertion_ids contains a "
                f"non-string entry: {item!r}"
            )
        ids.append(item)
    return tuple(ids)


def parse_fold_property(element: Any) -> FoldProperty:
    if not isinstance(element, Mapping):
        raise MalformedFoldSnapshot(
            f"folded_properties element must be an object, got {type(element).__name__}"
        )
    name = element.get("property_name")
    if not isinstance(name, str) or not name.strip():
        raise MalformedFoldSnapshot(
            f"folded_properties element has missing/invalid property_name: {name!r}"
        )
    missing = [key for key in REQUIRED_PROPERTY_KEYS if key not in element]
    if missing:
        raise MalformedFoldSnapshot(
            f"property {name!r} is missing governed keys: {', '.join(missing)}"
        )

    raw_state = element.get("fold_state")
    if not isinstance(raw_state, str):
        raise InvalidFoldPropertyState(
            f"property {name!r}: fold_state must be a string, got {raw_state!r}"
        )
    try:
        state = FoldState(raw_state)
    except ValueError as exc:
        raise InvalidFoldPropertyState(
            f"property {name!r}: fold_state {raw_state!r} is outside the governed "
            f"vocabulary ({', '.join(m.value for m in FoldState)}). Note that the "
            "database CHECK constrains only the row-level fold_status column; the "
            "element-level fold_state is unconstrained, so this is validated here."
        ) from exc

    return FoldProperty(
        property_name=name,
        resolved_value=element.get("resolved_value"),
        property_value_type=element.get("property_value_type"),
        fold_state=state,
        effective_at=parse_timestamp(
            element.get("effective_at"), field="effective_at", property_name=name
        ),
        latest_known_arrival_at=parse_timestamp(
            element.get("latest_known_arrival_at"),
            field="latest_known_arrival_at",
            property_name=name,
        ),
        basis_assertion_ids=parse_assertion_ids(
            element.get("basis_assertion_ids"), property_name=name
        ),
    )


def parse_folded_properties(raw: Any) -> dict[str, FoldProperty]:
    """The live structure is a JSONB ARRAY of property objects."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MalformedFoldSnapshot("folded_properties is not valid JSON") from exc
    if raw is None:
        raise MalformedFoldSnapshot("folded_properties is null")
    if not isinstance(raw, (list, tuple)):
        raise MalformedFoldSnapshot(
            f"folded_properties must be a JSON array, got {type(raw).__name__}"
        )

    properties: dict[str, FoldProperty] = {}
    for element in raw:
        prop = parse_fold_property(element)
        if prop.property_name in properties:
            raise MalformedFoldSnapshot(
                f"duplicate property_name {prop.property_name!r} within one Fold "
                "snapshot; governed state cannot be silently deduplicated"
            )
        properties[prop.property_name] = prop
    return properties


def build_snapshot_view(row: Mapping[str, Any]) -> FoldSnapshotView:
    for column in ("fold_state_id", "decision_horizon", "subject_type", "subject_id",
                   "fold_status", "folded_properties", "kb_version", "policy_version"):
        if column not in row:
            raise MalformedFoldSnapshot(f"Fold row is missing column {column!r}")

    raw_status = row["fold_status"]
    try:
        fold_status = FoldState(raw_status)
    except (ValueError, TypeError) as exc:
        raise InvalidFoldPropertyState(
            f"fold_status {raw_status!r} is outside the governed vocabulary"
        ) from exc

    horizon = row["decision_horizon"]
    if isinstance(horizon, str):
        horizon = parse_timestamp(
            horizon, field="decision_horizon", property_name="<snapshot>"
        )
    if not isinstance(horizon, datetime) or horizon.tzinfo is None:
        raise MalformedFoldSnapshot(
            f"decision_horizon must be a timezone-aware timestamp, got {horizon!r}"
        )

    computed_at = row.get("fold_computed_at")
    if isinstance(computed_at, str):
        computed_at = parse_timestamp(
            computed_at, field="fold_computed_at", property_name="<snapshot>"
        )

    return FoldSnapshotView(
        fold_state_id=str(row["fold_state_id"]),
        subject_type=row["subject_type"],
        subject_id=row["subject_id"],
        decision_horizon=horizon,
        fold_status=fold_status,
        kb_version=row["kb_version"],
        policy_version=row["policy_version"],
        properties=parse_folded_properties(row["folded_properties"]),
        fold_computed_at=computed_at,
    )


# ======================================================================
# live loader
# ======================================================================

class PostgresFoldLoader:
    """Reads state.fold_state_snapshot. Read-only. Domain-agnostic."""

    __slots__ = ("_db",)

    def __init__(self, db) -> None:
        self._db = db

    def load(
        self, subject_type: str, subject_id: str, decision_horizon: datetime
    ) -> FoldLoadResult:
        if decision_horizon.tzinfo is None:
            raise MalformedFoldSnapshot(
                "decision_horizon must be timezone-aware; a naive value cannot "
                "identify a governed snapshot"
            )
        rows = self._db.query(
            FOLD_SNAPSHOT_SQL, (subject_type, subject_id, decision_horizon)
        )
        if not rows:
            return FoldLoadResult(
                status=FoldLoadStatus.NOT_FOUND,
                detail=(
                    f"no Fold snapshot for subject_type={subject_type!r} "
                    f"subject_id={subject_id!r} at decision_horizon="
                    f"{decision_horizon.isoformat()}"
                ),
            )
        if len(rows) > 1:
            raise DuplicateFoldSnapshot(
                f"{len(rows)} snapshots for ({decision_horizon.isoformat()}, "
                f"{subject_type}, {subject_id}); fold_state_unique_horizon should "
                "make this impossible"
            )
        return FoldLoadResult(
            status=FoldLoadStatus.FOUND, snapshot=build_snapshot_view(rows[0])
        )

    # -- read-only discovery helpers (tests and diagnostics) ------------

    def horizons_for(self, subject_type: str, subject_id: str) -> tuple[datetime, ...]:
        rows = self._db.query(HORIZONS_SQL, (subject_type, subject_id))
        return tuple(r["decision_horizon"] for r in rows)

    def subjects_of_type(self, subject_type: str) -> tuple[dict, ...]:
        return tuple(self._db.query(SUBJECTS_SQL, (subject_type,)))
