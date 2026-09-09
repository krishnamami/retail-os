"""Minimal read-only PostgreSQL boundary for the decision runtime.

Deliberately small. This is not a database framework.

Credentials follow the established repository pattern exactly, as used by
phase_d3_windows.py:

    ambient AWS credential chain
      -> AWS Secrets Manager, region us-west-2
      -> secret 'retail_os/rds/postgres'
      -> PostgreSQL 'accord'

Nothing here prints, logs, returns or stores a credential. The secret name and
region are the only configuration, and both are overridable.

SAFETY
    * every statement passes a gate permitting only SELECT / WITH
    * the session is pinned READ ONLY server-side
    * a statement timeout is set
    * the connection is rolled back and closed deterministically
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from typing import Any, Iterator, Optional, Sequence

from .errors import AdapterError, ReadOnlyViolation

__all__ = [
    "SECRET_ID",
    "REGION",
    "DATABASE",
    "DEPLOY_CONFIRM_ENV",
    "DEPLOY_CONFIRM_VALUE",
    "DeployDatabase",
    "ReadOnlyDatabase",
    "deploy_connection",
    "read_only_connection",
]

SECRET_ID = os.environ.get("RETAIL_OS_DB_SECRET", "retail_os/rds/postgres")
REGION = os.environ.get("AWS_REGION_RETAIL_OS", "us-west-2")
DATABASE = os.environ.get("RETAIL_OS_DB_NAME", "accord")
STATEMENT_TIMEOUT = os.environ.get("RETAIL_OS_STATEMENT_TIMEOUT", "60s")

_READ_ONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _credentials() -> dict:
    try:
        import boto3  # imported lazily so unit tests never need it
    except ImportError as exc:  # pragma: no cover
        raise AdapterError(
            "boto3 is required for live database access; unit tests must not "
            "reach this path"
        ) from exc
    client = boto3.client("secretsmanager", region_name=REGION)
    secret = client.get_secret_value(SecretId=SECRET_ID)["SecretString"]
    return json.loads(secret)


def _connect():
    try:
        import psycopg2  # imported lazily
    except ImportError as exc:  # pragma: no cover
        raise AdapterError("psycopg2 is required for live database access") from exc

    creds = _credentials()
    host = creds.get("host")
    user = creds.get("username") or creds.get("user")
    if not host or not user:
        # deliberately does not echo the secret contents
        raise AdapterError(
            f"secret {SECRET_ID!r} is missing required keys; present keys: "
            f"{sorted(creds)}"
        )
    return psycopg2.connect(
        host=host,
        port=int(creds.get("port", 5432)),
        user=user,
        password=creds.get("password"),
        dbname=creds.get("dbname") or creds.get("database") or DATABASE,
        connect_timeout=15,
    )


class ReadOnlyDatabase:
    """A thin read-only query surface over one connection."""

    __slots__ = ("_conn",)

    def __init__(self, connection) -> None:
        self._conn = connection

    def query(self, sql: str, params: Optional[Sequence[Any]] = None) -> list[dict]:
        """Run one read and return rows as dicts.

        Raises ReadOnlyViolation for anything that is not SELECT/WITH, before
        the statement reaches the database.
        """
        if not _READ_ONLY_SQL.match(sql):
            raise ReadOnlyViolation(
                f"only SELECT/WITH statements are permitted; refused: {sql.strip()[:120]!r}"
            )
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            columns = [c.name for c in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def scalar(self, sql: str, params: Optional[Sequence[Any]] = None) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    def session_is_read_only(self) -> bool:
        return self.scalar("SELECT current_setting('transaction_read_only')") == "on"

    def context(self) -> dict:
        return self.query(
            "SELECT current_database() AS database, current_user AS role, "
            "current_setting('transaction_read_only') AS read_only, "
            "version() AS server_version"
        )[0]


@contextmanager
def read_only_connection(connection=None) -> Iterator[ReadOnlyDatabase]:
    """Yield a read-only ReadOnlyDatabase, closing deterministically.

    Pass `connection` to reuse an existing one (tests); otherwise a connection
    is opened through the established Secrets Manager pattern.
    """
    owned = connection is None
    conn = connection or _connect()
    try:
        # psycopg2 opens a transaction on the first execute, and
        # SET SESSION CHARACTERISTICS applied inside an open transaction only
        # affects SUBSEQUENT transactions -- the current one stays read-write.
        # set_session() is the correct API: it pins read-only at the session
        # level before any transaction starts.
        #
        # autocommit is equally deliberate. Without it a single failed
        # statement aborts the transaction and every later read fails with
        # InFailedSqlTransaction, turning one real error into a cascade that
        # hides the rest of the evidence. Every statement here is a read, so
        # there is no transaction to preserve.
        if hasattr(conn, "set_session"):
            conn.set_session(readonly=True, autocommit=True)
        else:  # pragma: no cover - drivers without set_session
            with conn.cursor() as cur:
                cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")

        database = ReadOnlyDatabase(conn)
        if owned and not database.session_is_read_only():
            raise ReadOnlyViolation(
                "the session could not be pinned READ ONLY; refusing to proceed "
                "rather than running reads against a writable session"
            )
        yield database
    finally:
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        if owned:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass


# ======================================================================
# D.4G.3 -- deployment connection
# ======================================================================
#
# Deliberately separate from read_only_connection and deliberately awkward to
# reach. A writable session exists here for exactly one purpose: applying
# reviewed migration files. It is not a general write surface, it is never the
# default, and it refuses to open unless a human has set the confirmation
# environment variable for this run.
#
# autocommit is OFF, which is the opposite of the read-only path and for the
# opposite reason: DDL that fails halfway must roll back rather than leave the
# schema in a state nobody designed.

DEPLOY_CONFIRM_ENV = "RETAIL_OS_DEPLOY_CONFIRM"
DEPLOY_CONFIRM_VALUE = "D4G3"

#: Every confirmation this deployment surface accepts, one per piece of work
#: that has been reviewed and authorised to write. The set is explicit rather
#: than a single mutable constant so adding the vertical slice cannot silently
#: retire the D.4G.3 confirmation that existing scripts still pass.
DEPLOY_CONFIRM_VALUES = frozenset({
    DEPLOY_CONFIRM_VALUE,   # D.4G.3/.4 migrations
    "VSLICE",               # the vertical slice: canonical materialization
})


class DeployDatabase:
    """A write-capable surface for applying reviewed migration files."""

    __slots__ = ("_conn",)

    def __init__(self, connection) -> None:
        self._conn = connection

    @property
    def connection(self):
        return self._conn

    def query(self, sql: str, params: Optional[Sequence[Any]] = None) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            columns = [c[0] for c in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def scalar(self, sql: str, params: Optional[Sequence[Any]] = None) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def set_autocommit(self, value: bool) -> None:
        """ALTER TYPE ... ADD VALUE needs its own transaction on some versions."""
        self._conn.rollback()
        self._conn.autocommit = bool(value)


@contextmanager
def deploy_connection(connection=None) -> Iterator[DeployDatabase]:
    """Yield a write-capable DeployDatabase, or refuse.

    Refuses unless RETAIL_OS_DEPLOY_CONFIRM names one of the authorised pieces
    of work (DEPLOY_CONFIRM_VALUES), so a writable session can never be opened
    by an import, a stray test, or a script that meant to read.
    """
    confirmation = os.environ.get(DEPLOY_CONFIRM_ENV)
    if confirmation not in DEPLOY_CONFIRM_VALUES:
        raise AdapterError(
            f"a deployment connection requires {DEPLOY_CONFIRM_ENV} to be one "
            f"of {sorted(DEPLOY_CONFIRM_VALUES)} in the environment; refusing "
            f"to open a writable session with {confirmation!r}"
        )
    owned = connection is None
    conn = connection or _connect()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '300s'")
        conn.commit()
        yield DeployDatabase(conn)
    finally:
        try:
            if owned:
                conn.close()
        except Exception:  # noqa: BLE001  pragma: no cover
            pass
