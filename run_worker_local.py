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

from connect_database import ConfigurationError, load_environment

ROOT = Path(__file__).resolve().parent


def main() -> int:
    try:
        load_environment(ROOT / ".env.database")
        load_environment(ROOT / ".env.worker")
    except ConfigurationError as exc:
        print("CONFIG:", exc)
        return 2
    worker_url = os.environ.get("EAS_WORKER_DATABASE_URL", "")
    try:
        parsed = urlsplit(worker_url)
        if parsed.scheme not in ("postgres", "postgresql") or not (
            parsed.hostname and parsed.username and parsed.password and parsed.path
        ):
            raise ValueError()
        user = unquote(parsed.username)
        if user != "eas_worker_login" and not user.startswith("eas_worker_login."):
            raise ValueError()
    except ValueError:
        print(
            "CONFIG: .env.worker must contain EAS_WORKER_DATABASE_URL using eas_worker_login or eas_worker_login.PROJECT_REF"
        )
        return 2
    os.environ["DATABASE_URL"] = worker_url
    os.environ.setdefault("EAS_ENV", "development")
    sys.argv = [str(ROOT / "manage.py"), "run_outbox_worker", *sys.argv[1:]]
    runpy.run_path(str(ROOT / "manage.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
