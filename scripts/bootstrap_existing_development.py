"""Install the validated EAS demo identities/config into a non-empty dev directory.

The canonical fixture SQL refuses every non-empty EAS domain. This wrapper permits
pre-existing departments/users only, while preserving its validated statements,
hashes and transaction. It never deletes or rewrites existing records.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api_core.config.database import parse_database_url

SEED = ROOT / "database" / "EAS_Supabase_SQL" / "01_demo_seed_DEV_ONLY.sql"


def _remove_empty_domain_guard(sql_text: str) -> str:
    marker = "DO $$ BEGIN\n IF EXISTS(SELECT 1 FROM eas.app_user)"
    start = sql_text.find(marker)
    if start < 0:
        raise RuntimeError("Canonical seed empty-domain guard was not found")
    end = sql_text.find("END $$;", start)
    if end < 0:
        raise RuntimeError("Canonical seed guard terminator was not found")
    return sql_text[:start] + sql_text[end + len("END $$;") :]


def main() -> None:
    config = parse_database_url(os.environ.get("DATABASE_URL", ""))
    project_ref = config["HOST"].split(".")[1]
    if os.environ.get("EAS_CONFIRM_DEVELOPMENT_PROJECT") != project_ref:
        raise RuntimeError("Exact EAS_CONFIRM_DEVELOPMENT_PROJECT is required")
    kwargs = {
        "dbname": config["NAME"],
        "user": config["USER"],
        "password": config["PASSWORD"],
        "host": config["HOST"],
        "port": config["PORT"],
        "sslmode": config["OPTIONS"]["sslmode"],
        "connect_timeout": 10,
    }
    with psycopg.connect(**kwargs) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT (SELECT count(*) FROM eas.config_release),
                       (SELECT count(*) FROM eas.request),
                       (SELECT count(*) FROM eas.admin_event),
                       (SELECT count(*) FROM eas.request_type WHERE active_release_id IS NOT NULL)
                """
        )
        if cursor.fetchone() != (0, 0, 0, 0):
            raise RuntimeError(
                "Development bootstrap requires empty config/request/audit state"
            )
        cursor.execute(
            """
                SELECT id::text FROM eas.department WHERE id::text LIKE '00000001-%'
                UNION ALL
                SELECT id::text FROM eas.app_user WHERE id::text LIKE '00000002-%'
                UNION ALL
                SELECT id::text FROM eas.role_membership WHERE id::text LIKE '00000004-%'
                """
        )
        collisions = cursor.fetchall()
        if collisions:
            raise RuntimeError("Demo identifier collision detected")
        seed = _remove_empty_domain_guard(SEED.read_text(encoding="utf-8"))
        cursor.execute(seed)
        connection.commit()

    with psycopg.connect(**kwargs) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT (SELECT count(*) FROM eas.app_user),
                       (SELECT count(*) FROM eas.config_release),
                       (SELECT count(*) FROM eas.admin_event),
                       (SELECT count(*) FROM eas.request_type WHERE active_release_id IS NOT NULL)
                """
        )
        users, releases, events, active_types = cursor.fetchone()
    if (releases, events, active_types) != (3, 4, 3):
        raise RuntimeError("Bootstrap postcondition failed")
    print(
        {
            "result": "PASS",
            "users": users,
            "config_releases": releases,
            "admin_events": events,
            "active_request_types": active_types,
        }
    )


if __name__ == "__main__":
    main()
