"""Safe diagnostic for DATN/connect_database.py. Does not print database passwords or URLs.

Place beside connect_database.py and .env.database, then run:
    .\\.venv\\Scripts\\python.exe diagnose_supabase.py
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


def main() -> int:
    root = Path(__file__).resolve().parent
    if not (root / "connect_database.py").is_file():
        print(
            "ERROR: Dat file diagnose_supabase.py cung thu muc voi connect_database.py"
        )
        return 2
    if not (root / ".env.database").is_file():
        print("ERROR: Thieu .env.database tai thu muc DATN")
        return 2

    import connect_database as eas

    overrides = [
        k
        for k in (
            "DATABASE_URL",
            "EAS_API_DATABASE_URL",
            "DB_USER",
            "DB_PASSWORD",
            "DB_HOST",
        )
        if k in os.environ
    ]
    print("ENV_OVERRIDES:", ", ".join(overrides) if overrides else "none")
    try:
        eas.load_environment(root / ".env.database")
        uri = eas.database_url()
        parsed = urlsplit(uri)
    except (ValueError, eas.ConfigurationError) as exc:
        # Field-oriented errors from the project, not a raw DSN.
        print("CONFIG_ERROR:", type(exc).__name__)
        return 2

    source = (
        "DATABASE_URL"
        if os.getenv("DATABASE_URL")
        else "EAS_API_DATABASE_URL"
        if os.getenv("EAS_API_DATABASE_URL")
        else "DB_*"
    )
    password = unquote(parsed.password or "")
    print("SOURCE:", source)
    print("HOST:", parsed.hostname or "<empty>")
    print("PORT:", parsed.port or "<unspecified>")
    print("DB_NAME:", parsed.path.lstrip("/") or "<empty>")
    print("USER:", unquote(parsed.username or "") or "<empty>")
    print("PASSWORD_PROVIDED:", bool(password))
    print(
        "PASSWORD_IS_PLACEHOLDER:",
        "replace-with" in password.lower() or "mat_khau" in password.lower(),
    )
    print("SSL_MODE:", parse_qs(parsed.query).get("sslmode", ["not set"])[0])
    try:
        import psycopg
    except ImportError:
        print("ERROR: Chua cai psycopg")
        return 2
    try:
        with psycopg.connect(uri, connect_timeout=10, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                user = cur.fetchone()[0]
        print("RESULT: AUTH_SUCCESS")
        print("POSTGRES_ROLE:", user)
        print(
            "NEXT: Chay .\\.venv\\Scripts\\python.exe connect_database.py de kiem tra bang/quyen"
        )
        return 0
    except psycopg.Error as exc:
        code = getattr(exc, "sqlstate", None)
        details = str(exc).lower()
        print("RESULT: CONNECTION_FAILED")
        print("ERROR_CLASS:", type(exc).__name__)
        print("SQLSTATE:", code or "none")
        if "password authentication failed" in details or code == "28P01":
            print(
                "REASON: AUTH_FAILED (kiem tra user va mat khau PostgreSQL; neu vua reset, pooler co the cache)"
            )
        elif "tenant or user not found" in details or "tenant/user" in details:
            print(
                "REASON: TENANT_OR_USER_NOT_FOUND (kiem tra host va user cua Session pooler)"
            )
        elif "timeout" in details or "timed out" in details:
            print("REASON: TIMEOUT (kiem tra mang, firewall, endpoint)")
        elif "ssl" in details:
            print("REASON: SSL_ISSUE (kiem tra sslmode va certificate)")
        elif (
            "name or service not known" in details or "nodename nor servname" in details
        ):
            print("REASON: DNS_FAILED (kiem tra host)")
        else:
            print(
                "REASON: OTHER (kiem tra cau hinh host/user/password va log Supabase)"
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
