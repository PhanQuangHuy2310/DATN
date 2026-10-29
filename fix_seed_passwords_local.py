r"""Utility script to update placeholder passwords in eas.app_user to standard PBKDF2 hash of Admin@123456.

Usage: python fix_seed_passwords_local.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from connect_database import database_url, load_environment

TARGET_HASH = (
    "pbkdf2_sha256$600000$eas_seed_2026$/yIu1DHt5Xd+/BX6FW+U9GwEEuZjgxwk1613D9BohoU="
)
PLACEHOLDERS = (
    "pbkdf2_sha256$600000$seed$TempHashForDevOnly00000000000000000000000000000=",
    "pbkdf2_sha256$600000$admin_salt$dummy_hash_for_bootstrap_change_on_first_login",
)


def main():
    env_file = Path(__file__).with_name(".env.database")
    if not env_file.is_file():
        env_file = Path(__file__).with_name(".env")
    load_environment(env_file)
    os.environ["DATABASE_URL"] = database_url()

    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install: pip install psycopg")
        return 2

    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE eas.app_user
                SET password_hash = %s
                WHERE password_hash = ANY(%s) OR password_hash LIKE '!UNUSABLE_DEMO_%'
                RETURNING username
                """,
                [TARGET_HASH, list(PLACEHOLDERS)],
            )
            updated = [r[0] for r in cur.fetchall()]
            conn.commit()
            print(
                f"Updated {len(updated)} user(s) to Admin@123456 hash: {', '.join(updated) if updated else 'none'}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
