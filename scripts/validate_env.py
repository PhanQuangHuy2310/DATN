#!/usr/bin/env python3
"""Validate EAS environment files without printing secret values."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

PROFILES = {
    "compose": {
        "EAS_API_DATABASE_URL",
        "EAS_WORKER_DATABASE_URL",
        "EAS_DJANGO_SECRET_KEY",
        "EAS_SUPABASE_URL",
        "EAS_REQUIRE_STORAGE",
    },
    "api": {"DATABASE_URL", "DJANGO_SECRET_KEY", "EAS_ENV", "EAS_REQUIRE_STORAGE"},
    "worker": {
        "DATABASE_URL",
        "DJANGO_SECRET_KEY",
        "EAS_ENV",
        "EAS_REQUIRE_STORAGE",
    },
    "web": {"VITE_API_BASE_URL"},
}

BOOLEAN_KEYS = {
    "DJANGO_DEBUG",
    "EAS_ALLOW_ADMIN_DB",
    "EAS_DJANGO_DEBUG",
    "EAS_HSTS_PRELOAD",
    "EAS_REQUIRE_ACTIVE_RELEASES",
    "EAS_REQUIRE_MOCK_SOURCES",
    "EAS_REQUIRE_STORAGE",
    "EAS_SSL_REDIRECT",
    "EAS_TRUST_PROXY_HEADERS",
}
INTEGER_KEYS = {
    "EAS_CLAMAV_PORT",
    "EAS_LOGIN_MAX_ATTEMPTS",
    "EAS_LOGIN_WINDOW_SECONDS",
    "EAS_SESSION_AGE_SECONDS",
    "EAS_WEB_PORT",
}
PLACEHOLDER_MARKERS = (
    "change-me",
    "example.invalid",
    "project-ref",
    "replace-me",
    "replace-through",
    "replace-with",
)
BANNED_DB_USERS = {"postgres", "supabase_admin"}


def parse_env(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    errors: list[str] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            errors.append(f"line {line_number}: expected KEY=VALUE")
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            errors.append(f"line {line_number}: invalid variable name")
            continue
        if key in values:
            errors.append(f"line {line_number}: duplicate variable {key}")
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values, errors


def is_true(value: str) -> bool:
    return value.strip().lower() == "true"


def validate_database_url(key: str, value: str, errors: list[str]) -> str | None:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or not parsed.hostname
        or not parsed.path
    ):
        errors.append(f"{key}: must be a complete PostgreSQL URL")
        return None
    username = (parsed.username or "").lower()
    if not username:
        errors.append(f"{key}: database username is required")
    elif username in BANNED_DB_USERS or "migration" in username or "owner" in username:
        errors.append(f"{key}: privileged database login is forbidden at runtime")
    if parsed.hostname not in {"localhost", "127.0.0.1", "db"}:
        query = parsed.query.lower()
        if "sslmode=require" not in query and "sslmode=verify-full" not in query:
            errors.append(f"{key}: remote PostgreSQL connections must require TLS")
    return username or None


def validate_supabase_secret(key: str, value: str, errors: list[str]) -> None:
    """Reject client-safe Supabase keys in the server-only secret slot."""
    if value.startswith("sb_publishable_"):
        errors.append(f"{key}: publishable keys cannot authorize private Storage")
        return
    if value.count(".") != 2:
        return
    try:
        payload = value.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return
    if claims.get("role") in {"anon", "authenticated"}:
        errors.append(f"{key}: anon/authenticated JWT cannot authorize private Storage")


def validate(
    values: dict[str, str], profile: str, allow_placeholders: bool
) -> list[str]:
    errors: list[str] = []
    for key in sorted(PROFILES[profile]):
        if key not in values:
            errors.append(f"missing required variable {key}")

    for key in BOOLEAN_KEYS & values.keys():
        if values[key].lower() not in {"true", "false"}:
            errors.append(f"{key}: use exactly true or false")
    for key in INTEGER_KEYS & values.keys():
        try:
            if int(values[key]) <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"{key}: must be a positive integer")

    storage_required = is_true(values.get("EAS_REQUIRE_STORAGE", "false"))
    storage_url_key = "EAS_SUPABASE_URL" if profile == "compose" else "SUPABASE_URL"
    storage_secret_key = (
        "EAS_SUPABASE_SECRET_KEY" if profile == "compose" else "SUPABASE_SECRET_KEY"
    )
    if storage_required:
        for key in (storage_url_key, storage_secret_key, "EAS_STORAGE_BUCKET"):
            if not values.get(key):
                errors.append(f"{key}: required when EAS_REQUIRE_STORAGE=true")
    if values.get(storage_secret_key):
        validate_supabase_secret(storage_secret_key, values[storage_secret_key], errors)

    for key in ("EAS_SUPABASE_URL", "SUPABASE_URL"):
        if values.get(key):
            parsed = urlparse(values[key])
            if parsed.scheme != "https" or not parsed.hostname:
                errors.append(f"{key}: must be an HTTPS origin")

    secret_key = (
        "EAS_DJANGO_SECRET_KEY" if profile == "compose" else "DJANGO_SECRET_KEY"
    )
    if (
        values.get(secret_key)
        and len(values[secret_key]) < 50
        and not allow_placeholders
    ):
        errors.append(f"{secret_key}: must contain at least 50 characters")

    database_keys = (
        ("EAS_API_DATABASE_URL", "EAS_WORKER_DATABASE_URL")
        if profile == "compose"
        else (("DATABASE_URL",) if profile in {"api", "worker"} else ())
    )
    usernames: list[str] = []
    for key in database_keys:
        if values.get(key):
            username = validate_database_url(key, values[key], errors)
            if username:
                usernames.append(username)
    if profile == "compose" and len(usernames) == 2 and usernames[0] == usernames[1]:
        errors.append("API and worker must use different database logins")

    if profile == "web":
        unexpected = sorted(key for key in values if not key.startswith("VITE_"))
        if unexpected:
            errors.append("web env may only contain VITE_* public variables")
        base_url = values.get("VITE_API_BASE_URL", "").rstrip("/")
        if base_url.endswith("/api") or "/api/v1" in base_url:
            errors.append("VITE_API_BASE_URL must be an origin without /api or /api/v1")

    environment = values.get("EAS_ENV", "development").lower()
    if environment not in {"development", "test", "staging", "production"}:
        errors.append("EAS_ENV: expected development, test, staging, or production")
    if environment == "production":
        if not storage_required:
            errors.append("production requires EAS_REQUIRE_STORAGE=true")
        if is_true(values.get("DJANGO_DEBUG", values.get("EAS_DJANGO_DEBUG", "false"))):
            errors.append("production cannot enable Django debug")
        if is_true(values.get("EAS_ALLOW_ADMIN_DB", "false")):
            errors.append("production cannot allow an admin database login")

    if not allow_placeholders:
        for key, value in values.items():
            if value and any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
                errors.append(f"{key}: placeholder value must be replaced")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="validate a committed template's structure without requiring real secrets",
    )
    args = parser.parse_args()
    if not args.file.is_file():
        print(f"ERROR: environment file not found: {args.file}", file=sys.stderr)
        return 2

    values, errors = parse_env(args.file)
    errors.extend(validate(values, args.profile, args.allow_placeholders))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            f"Environment validation failed with {len(errors)} error(s).",
            file=sys.stderr,
        )
        return 1
    print(
        f"Environment validation passed for profile '{args.profile}' ({len(values)} variables)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
