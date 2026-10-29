r"""Local authorized account recovery for an EAS Django installation.

Runs the project's existing audited `account_reset` management command.
Requires local possession of valid .env.database credentials. Does not
write raw passwords to a command argument, config file, or audit event.

Usage:
  .\.venv\Scripts\python.exe recover_admin_password_interactive.py \
      --user admin --operator YOUR_ACCOUNT --approval LOCAL-RECOVERY-20261027
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Audited EAS local account password recovery")
    parser.add_argument("--user", default="admin", help="Existing username to reset")
    parser.add_argument("--operator", required=True, help="Existing account of the authorized operator")
    parser.add_argument("--approval", required=True, help="Recovery approval/ticket reference")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    if not (base / "manage.py").is_file():
        parser.error("Copy this script to the DATN project root, beside manage.py")
    if len(args.approval.strip()) < 10:
        parser.error("--approval must contain at least 10 characters for the audit event")

    try:
        from connect_database import database_url, load_environment

        load_environment(base / ".env.database")
        os.environ["DATABASE_URL"] = database_url()
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
        import django
        django.setup()
        from django.core.management import call_command
        from api_core.authn.service import PasswordChangeError, validate_new_password
    except Exception as exc:
        print("Cannot load EAS project/database settings:", type(exc).__name__, file=sys.stderr)
        return 2

    print(f"Target account: {args.user.strip().lower()}")
    print("Only proceed if you are authorized to administer this EAS database.")
    consent = input("Type RESET to proceed (anything else cancels): ").strip()
    if consent != "RESET":
        print("Cancelled without changes.")
        return 1

    password = getpass.getpass("New password (hidden): ")
    repeat = getpass.getpass("Repeat new password (hidden): ")
    if password != repeat:
        print("Passwords do not match. No changes made.", file=sys.stderr)
        return 2
    try:
        validate_new_password(password, args.user.strip().lower())
    except PasswordChangeError:
        print("Password policy failed (15-128 characters; uppercase, lowercase, digit, symbol; no username/common passwords).", file=sys.stderr)
        return 2
    del repeat

    # Management command writes through the existing security-lock, security-epoch,
    # admin-event hash chain, and argon2 password policy; transaction is atomic.
    os.environ["EAS_TEMP_PASSWORD"] = password
    del password
    try:
        call_command(
            "account_reset",
            user=args.user.strip().lower(),
            mode="reset-password",
            operator=args.operator.strip(),
            approval=args.approval.strip(),
        )
    except SystemExit as exc:
        # Existing project command calls sys.exit(0) even when successful.
        if exc.code not in (0, None):
            raise
        print("Password reset committed. Sign in with the new password and change it immediately.")
        return 0
    except Exception as exc:
        print("Reset could not be completed:", type(exc).__name__, file=sys.stderr)
        return 3
    finally:
        os.environ.pop("EAS_TEMP_PASSWORD", None)
    print("Password reset committed. Sign in with the new password and change it immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
