"""EAS PostgreSQL connection/check/launcher. Copy into DATN beside manage.py."""

from __future__ import annotations

import argparse
import os
import re
import runpy
import sys
from pathlib import Path
from urllib.parse import quote

EXPECTED_TABLES = ["security_epoch", "department", "app_user", "request_type", "role_membership", "config_release", "request", "request_revision", "workflow_instance", "request_participant", "approval_step", "approval_decision", "execution_attempt", "acceptance_decision", "execution_issue", "attachment", "draft_attachment", "revision_attachment", "execution_attachment", "sla_stage", "sla_alert", "audit_head", "audit_event", "admin_event", "audit_checkpoint", "outbox_event", "notification", "idempotency_record", "privacy_case", "retention_hold"]


class ConfigurationError(ValueError):
    pass


def load_environment(path: Path, environ=None):
    """Simple KEY=VALUE file; existing process environment has priority.

    No shell execution, escape expansion, interpolation or multiline values.
    Surrounding matching quotes are stripped; # inside a value is preserved.
    """
    env = os.environ if environ is None else environ
    if not path.is_file():
        return
    pending = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigurationError(
                f"Dong {number} trong file moi truong khong hop le."
            )
        if value[:1] in ('"', "'"):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigurationError(f"Dau nhay khong hop le tai dong {number}.")
            value = value[1:-1]
        pending[key] = value
    for key, value in pending.items():
        env.setdefault(key, value)


def database_url(environ=None):
    env = os.environ if environ is None else environ
    # Exact URLs supplied by the deployment take precedence over separate fields.
    value = env.get("DATABASE_URL") or env.get("EAS_API_DATABASE_URL")
    if value:
        if not value.startswith(("postgresql://", "postgres://")):
            raise ConfigurationError("DATABASE_URL phai la URL PostgreSQL.")
        return value
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ConfigurationError("Thieu cau hinh: " + ", ".join(missing))
    host = env["DB_HOST"].strip()
    if any(char in host for char in "/@?# \t\n"):
        raise ConfigurationError("DB_HOST chi chua hostname hoac dia chi IP.")
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    try:
        port = int(env.get("DB_PORT", "5432"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ConfigurationError("DB_PORT phai nam trong 1..65535.") from None
    sslmode = env.get("DB_SSLMODE", "require")
    if sslmode not in {"require", "verify-ca", "verify-full", "disable"}:
        raise ConfigurationError("DB_SSLMODE khong hop le.")
    return (
        f"postgresql://{quote(env['DB_USER'], safe='')}:{quote(env['DB_PASSWORD'], safe='')}"
        f"@{host}:{port}/{quote(env['DB_NAME'], safe='')}?sslmode={sslmode}"
    )


def check_database(url):
    try:
        import psycopg
    except ImportError:
        print("Chua cai psycopg. Chay: python -m pip install -r requirements-db.txt")
        return 2
    try:
        # prepare_threshold=None supports connections through transaction pooling.
        with psycopg.connect(
            url,
            connect_timeout=10,
            prepare_threshold=None,
            options="-c statement_timeout=10000 -c lock_timeout=3000",
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SELECT 1")
                assert cursor.fetchone()[0] == 1
                print("OK: ket noi PostgreSQL thanh cong.")
                cursor.execute(
                    "SELECT has_schema_privilege(current_user, oid, 'USAGE') "
                    "FROM pg_namespace WHERE nspname = 'eas'"
                )
                row = cursor.fetchone()
                if not row or not row[0]:
                    print(
                        "FAIL: schema eas chua ton tai hoac tai khoan thieu quyen USAGE."
                    )
                    return 3
                missing, unreadable = [], []
                for name in EXPECTED_TABLES:
                    cursor.execute("SELECT to_regclass(%s)", ("eas." + name,))
                    table = cursor.fetchone()[0]
                    if table is None:
                        missing.append(name)
                        continue
                    cursor.execute(
                        "SELECT has_table_privilege(current_user, %s, 'SELECT')",
                        (table,),
                    )
                    if not cursor.fetchone()[0]:
                        unreadable.append(name)
                if missing:
                    print("FAIL: thieu bang eas: " + ", ".join(missing))
                else:
                    print("OK: tim thay du 30 bang eas theo dtb.txt.")
                if unreadable:
                    print(
                        "NOTE: khong co quyen SELECT truc tiep: "
                        + ", ".join(unreadable)
                    )
                print(
                    "Chi kiem tra ket noi/cau truc/quyen doc. Chua kiem tra RLS, ghi du lieu, trigger hay luong E2E."
                )
                return 3 if missing else 0
    except psycopg.Error as exc:
        code = getattr(exc, "sqlstate", None)
        # Do not print raw exception or DSN: they can contain credentials/host data.
        messages = {
            "28P01": "Sai thong tin xac thuc database.",
            "3D000": "Database khong ton tai.",
            "42501": "Tai khoan thieu quyen truy cap.",
            "57014": "Truy van vuot qua thoi gian cho.",
        }
        print(
            "FAIL: "
            + messages.get(
                code,
                "Khong the ket noi/kiem tra. Kiem tra host, port, mang, SSL va thong tin dang nhap.",
            )
        )
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ket noi PostgreSQL/Supabase cho EAS; khong in mat khau."
    )
    parser.add_argument(
        "--env-file", type=Path, default=Path(__file__).with_name(".env.database")
    )
    parser.add_argument(
        "--runserver",
        action="store_true",
        help="Khoi dong Django voi ket noi da cau hinh",
    )
    parser.add_argument("--bind", default="127.0.0.1:8000")
    args = parser.parse_args(argv)
    try:
        load_environment(args.env_file)
        url = database_url()
        if args.runserver:
            if os.environ.get("EAS_ENV", "").lower() == "test":
                raise ConfigurationError(
                    "EAS_ENV=test su dung SQLite. Hay chon development de ket noi PostgreSQL."
                )
            manage = Path(__file__).with_name("manage.py")
            if not manage.is_file():
                raise ConfigurationError(
                    "Dat connect_database.py cung thu muc voi manage.py cua DATN."
                )
            # Reuse Django's existing validation and connection backend.
            from api_core.config.database import parse_database_url

            parse_database_url(url)
            os.environ["DATABASE_URL"] = url
            sys.argv = [str(manage), "runserver", args.bind]
            runpy.run_path(str(manage), run_name="__main__")
            return 0
        return check_database(url)
    except (ConfigurationError, ValueError) as exc:
        # Local errors above contain field names, never secret values.
        print("CONFIG: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
