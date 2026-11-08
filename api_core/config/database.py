"""Connection settings read from the environment: PostgreSQL and Redis."""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import parse_qs, unquote

DEFAULT_LOCAL_REDIS_PORT = 6380


class DatabaseUrlError(ValueError):
    """Raised when DATABASE_URL cannot be converted safely."""


def parse_database_url(url: str) -> dict[str, object]:
    """Convert a PostgreSQL URL to Django settings without logging credentials.

    Splitting at the last ``@`` also supports a legacy local DSN whose password
    contains an unescaped at-sign. New credentials must still be percent-encoded.
    """

    if not url or "://" not in url:
        raise DatabaseUrlError("DATABASE_URL is missing or malformed")
    scheme, rest = url.split("://", 1)
    if scheme not in {"postgres", "postgresql"}:
        raise DatabaseUrlError("DATABASE_URL must use PostgreSQL")

    try:
        credentials, endpoint = rest.rsplit("@", 1)
        username, password = credentials.split(":", 1)
        host_port, database_query = endpoint.split("/", 1)
        database, _, query_string = database_query.partition("?")

        if host_port.startswith("["):
            host, separator, port_text = host_port[1:].partition("]:")
            if not separator:
                raise DatabaseUrlError("IPv6 DATABASE_URL must include a port")
        else:
            host, port_text = host_port.rsplit(":", 1)

        options = parse_qs(query_string, keep_blank_values=True)
        sslmode = options.get("sslmode", ["require"])[0]
        if sslmode not in {"require", "verify-ca", "verify-full", "disable"}:
            raise DatabaseUrlError("Unsupported sslmode")

        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(database),
            "USER": unquote(username),
            "PASSWORD": unquote(password),
            "HOST": host,
            "PORT": int(port_text),
            "CONN_MAX_AGE": int(os.getenv("EAS_DB_CONN_MAX_AGE", "60")),
            "DISABLE_SERVER_SIDE_CURSORS": True,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "sslmode": sslmode,
                "connect_timeout": int(
                    os.getenv("EAS_DB_CONNECT_TIMEOUT_SECONDS", "5")
                ),
                "prepare_threshold": None,
                "options": f"-c statement_timeout={int(os.getenv('EAS_DB_STATEMENT_TIMEOUT_MS', '20000'))} -c lock_timeout=5000",
            },
        }
    except (ValueError, TypeError) as exc:
        if isinstance(exc, DatabaseUrlError):
            raise
        raise DatabaseUrlError("DATABASE_URL is malformed") from None


def resolve_redis_url(environ: Mapping[str, str]) -> str:
    """Resolve the Redis URL, also for processes running outside Docker.

    REDIS_URL always wins (Docker sets redis://redis:6379/0). Outside Docker a
    host/port can be given instead; the port defaults to 6380 so the compose
    Redis (published on 127.0.0.1:6380) never collides with another Redis
    already listening on the machine's default 6379.
    """

    url = (environ.get("REDIS_URL") or "").strip()
    if url:
        return url
    host = (environ.get("EAS_REDIS_HOST") or "").strip()
    port = (environ.get("EAS_REDIS_PORT") or "").strip()
    if not host and not port:
        return ""  # no Redis configured: development uses the local-memory cache
    port_number = int(port or DEFAULT_LOCAL_REDIS_PORT)
    if not 1 <= port_number <= 65535:
        raise RuntimeError("EAS_REDIS_PORT must be a valid TCP port")
    db = (environ.get("EAS_REDIS_DB") or "0").strip()
    return f"redis://{host or '127.0.0.1'}:{port_number}/{db}"
