"""Single configuration source for local processes: <repository>/.env.

Process environment wins over file values (Docker/CI secrets take precedence).
Only the API/worker/AI processes load secrets; Vite exposes VITE_* values only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")
ALIASES = {
    "DATABASE_URL": "EAS_API_DATABASE_URL",
    "DJANGO_SECRET_KEY": "EAS_DJANGO_SECRET_KEY",
    "DJANGO_DEBUG": "EAS_DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS": "EAS_DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "EAS_CSRF_TRUSTED_ORIGINS",
    "SUPABASE_URL": "EAS_SUPABASE_URL",
    "SUPABASE_SECRET_KEY": "EAS_SUPABASE_SECRET_KEY",
    "EAS_AI_INTERNAL_SECRET": "INTERNAL_API_SECRET",
    "LOG_LEVEL": "EAS_LOG_LEVEL",
}


def load_project_env(path: Path | None = None) -> None:
    env_file = path or (ROOT / ".env")
    if env_file.is_file():
        for line_no, raw in enumerate(env_file.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, value = line.partition("=")
            name, value = name.strip(), value.strip()
            if not sep or not KEY.fullmatch(name):
                raise ValueError(f"Invalid environment file, line {line_no}")
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError(f"Invalid quoted value on line {line_no}")
                value = value[1:-1]
            os.environ.setdefault(name, value)
    for destination, source in ALIASES.items():
        if os.environ.get(source):
            os.environ.setdefault(destination, os.environ[source])
