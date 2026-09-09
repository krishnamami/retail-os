r"""Live read-only integration tests against the accord database.

SKIPPED BY DEFAULT. `pytest tests/decisions` never needs AWS or PostgreSQL.

To run:

    $env:RETAIL_OS_LIVE_DB = "1"
    .\venv\Scripts\python.exe -m pytest tests\decisions\integration -q -s

Connection follows the established repository pattern exactly: ambient AWS
credential chain -> Secrets Manager (us-west-2) -> retail_os/rds/postgres.
No credential is requested, printed or stored.

EVERY statement in this suite is a read. The session is pinned READ ONLY
server-side and the adapter refuses anything that is not SELECT/WITH.
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TESTS_DECISIONS = os.path.abspath(os.path.join(_HERE, ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _path in (_REPO_ROOT, _TESTS_DECISIONS):
    if _path not in sys.path:
        sys.path.insert(0, _path)

if os.environ.get("RETAIL_OS_LIVE_DB") != "1":
    pytest.skip(
        "live database tests are opt-in; set RETAIL_OS_LIVE_DB=1 to run",
        allow_module_level=True,
    )

from decisions.adapters.connection import read_only_connection  # noqa: E402
from decisions.adapters.fold_postgres import PostgresFoldLoader  # noqa: E402
from decisions.adapters.kb_postgres import PostgresKBResolver  # noqa: E402

from live_support import row_counts  # noqa: E402,F401  (re-exported for tests)


@pytest.fixture(scope="session")
def db():
    with read_only_connection() as database:
        yield database


@pytest.fixture(scope="session")
def fold_loader(db):
    return PostgresFoldLoader(db)


@pytest.fixture(scope="session")
def kb_resolver(db):
    return PostgresKBResolver(db)


@pytest.fixture(scope="session")
def identity_subjects(db):
    """Discover subjects from the database rather than hard-coding ids."""
    from live_support import IDENTITY_PROPERTIES, SUBJECT_TYPE

    rows = db.query(
        """
        SELECT f.subject_id,
               f.decision_horizon,
               count(*) FILTER (WHERE e->>'fold_state' = 'ESTABLISHED') AS established,
               count(*) FILTER (WHERE e->>'fold_state' = 'UNREPORTED')  AS unreported,
               count(*)                                                  AS total
        FROM state.fold_state_snapshot f,
             jsonb_array_elements(f.folded_properties) e
        WHERE f.subject_type = %s
          AND e->>'property_name' = ANY(%s)
        GROUP BY 1, 2
        ORDER BY 1
        """,
        (SUBJECT_TYPE, list(IDENTITY_PROPERTIES)),
    )
    complete = [r for r in rows if r["established"] == len(IDENTITY_PROPERTIES)]
    partial = [r for r in rows if r["unreported"] > 0]
    return {"all": rows, "complete": complete, "with_unreported": partial}
