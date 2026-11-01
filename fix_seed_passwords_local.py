r"""Replace seed placeholder password hashes in eas.app_user (local/dev only).

The password is read from EAS_SEED_PASSWORD (never stored in the repo), hashed
with Argon2, and every updated account must change it at first sign-in.

Usage: set EAS_SEED_PASSWORD in .env, then python fix_seed_passwords_local.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from connect_database import database_url, load_environment

PLACEHOLDERS = (
    "pbkdf2_sha256$600000$seed$TempHashForDevOnly00000000000000000000000000000=",
    "pbkdf2_sha256$600000$admin_salt$dummy_hash_for_bootstrap_change_on_first_login",
)


def seed_password_hash() -> str:
    password = os.getenv("EAS_SEED_PASSWORD", "")
    if len(password) < 15:
        raise SystemExit("Set EAS_SEED_PASSWORD (>=15 characters) before running.")
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"]
        )
    from django.contrib.auth.hashers import make_password

    return make_password(password, hasher="argon2")


def main():
    load_environment(Path(__file__).with_name(".env"))
    os.environ["DATABASE_URL"] = database_url()
    target_hash = seed_password_hash()

    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install: pip install psycopg")
        return 2

    with psycopg.connect(
        os.environ["DATABASE_URL"], connect_timeout=10, prepare_threshold=None
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE eas.app_user
                SET password_hash = %s, must_change_password = TRUE,
                    auth_version = auth_version + 1
                WHERE password_hash = ANY(%s) OR password_hash LIKE '!UNUSABLE_DEMO_%%'
                RETURNING email
                """,
                [target_hash, list(PLACEHOLDERS)],
            )
            updated = [r[0] for r in cur.fetchall()]
            conn.commit()
            print(
                f"Updated {len(updated)} user(s); each must change the password at first sign-in."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
