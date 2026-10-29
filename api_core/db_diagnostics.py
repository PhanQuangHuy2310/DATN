"""Sanitized database failure classification, independent of driver internals.

Never include exception messages, SQL statements, DSNs or parameters in logs.
A PostgreSQL error's SQLSTATE and Python exception class are sufficient to
separate a connectivity failure from a permission/schema problem.
"""

from __future__ import annotations

TRANSIENT_STATES = frozenset(
    {
        "53300",  # too_many_connections
        "53400",  # configuration_limit_exceeded
        "55P03",  # lock_not_available (including lock_timeout)
        "57014",  # query_canceled / statement_timeout
        "57P01",  # admin_shutdown
        "57P02",  # crash_shutdown
        "57P03",  # cannot_connect_now
    }
)


def sqlstate(exc: BaseException) -> str:
    """Extract PostgreSQL SQLSTATE through Django/psycopg exception chaining."""
    current = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        value = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        if isinstance(value, str) and len(value) == 5 and value.isalnum():
            return value.upper()
        current = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )
    return "unknown"


def failure_category(exc: BaseException) -> str:
    """Return a short non-sensitive problem class suitable for server logs."""
    state = sqlstate(exc)
    if state == "55P03":
        return "lock_timeout"
    if state == "57014":
        return "statement_timeout"
    if state in {"53300", "53400"}:
        return "capacity"
    if state.startswith(("08", "57P")):
        return "connection"
    if state == "42501":
        return "permission"
    if state in {"42P01", "42703", "42883"}:
        return "schema"
    if state != "unknown":
        return "query"
    types = []
    current = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        types.append(type(current).__name__)
        current = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )
    if any(
        t
        in {
            "OperationalError",
            "InterfaceError",
            "ConnectionError",
            "TimeoutError",
            "OSError",
        }
        for t in types
    ):
        return "connection"
    return "unknown"


def api_db_failure(exc: BaseException) -> tuple[str, int]:
    """Avoid misleading HTTP 500 for transient DB/network failures.

    Authorization never fails open: all failures remain errors. Only the
    status/code differ for presentation; no automatic retry of mutations.
    """
    kind = failure_category(exc)
    if kind in {"connection", "capacity", "lock_timeout", "statement_timeout"}:
        return "DATABASE_TEMPORARILY_UNAVAILABLE", 503
    return "DATABASE_QUERY_FAILED", 500
