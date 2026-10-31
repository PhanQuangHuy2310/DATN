r"""Start worker using .env.database + .env.worker; does not print credentials.

CMD: .\.venv\Scripts\python.exe run_worker_local.py --once
     .\.venv\Scripts\python.exe run_worker_local.py
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from connect_database import ConfigurationError, load_environment, worker_database_url

ROOT = Path(__file__).resolve().parent


def main() -> int:
    try:
        from project_env import load_project_env
        load_project_env()
    except ConfigurationError as exc:
        print("CONFIG:", exc)
        return 2

    placeholders = (
        "YOUR_PROJECT_REF",
        "YOUR_POOLER_HOST",
        "ENCODED_PASSWORD",
        "YOUR_PASSWORD",
    )
    raw_worker_url = os.environ.get("EAS_WORKER_DATABASE_URL", "").strip()
    if any(ph in raw_worker_url for ph in placeholders) and not (
        os.environ.get("WORKER_DB_USER") and os.environ.get("WORKER_DB_PASSWORD")
    ):
        print(
            "WARN: EAS_WORKER_DATABASE_URL trong .env đang chứa chuỗi mẫu chưa cấu hình "
            "(YOUR_PROJECT_REF, YOUR_POOLER_HOST, hoặc ENCODED_PASSWORD). Worker không thể chạy."
        )
        return 2

    try:
        worker_url = worker_database_url()
        parsed = urlsplit(worker_url)
        if parsed.scheme not in ("postgres", "postgresql") or not (
            parsed.hostname and parsed.username and parsed.password and parsed.path
        ):
            raise ValueError()
        user = unquote(parsed.username)
        if (
            user not in ("eas_worker_login", "eas_worker")
            and not user.startswith("eas_worker_login.")
        ):
            raise ValueError()
    except (ValueError, ConfigurationError) as exc:
        msg = (
            str(exc)
            if isinstance(exc, ConfigurationError)
            else ".env must contain EAS_WORKER_DATABASE_URL using eas_worker_login or eas_worker_login.PROJECT_REF"
        )
        print(f"CONFIG: {msg}")
        return 2
    os.environ["DATABASE_URL"] = worker_url
    os.environ.setdefault("EAS_ENV", "development")
    sys.argv = [str(ROOT / "manage.py"), "run_outbox_worker", *sys.argv[1:]]
    runpy.run_path(str(ROOT / "manage.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
