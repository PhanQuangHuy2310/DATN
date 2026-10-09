from __future__ import annotations

from urllib.parse import parse_qs, unquote


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
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "sslmode": sslmode,
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000 -c lock_timeout=5000",
            },
        }
    except (ValueError, TypeError) as exc:
        if isinstance(exc, DatabaseUrlError):
            raise
        raise DatabaseUrlError("DATABASE_URL is malformed") from None
