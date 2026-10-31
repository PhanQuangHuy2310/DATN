"""Read-only check of current PostgreSQL schema against 2026-10-26 EAS contract.

Windows: python check_schema_contract.py
Uses .env; never prints a URL or credential.
"""
from __future__ import annotations
import sys
from pathlib import Path
from connect_database import load_environment, database_url

REQUIRED = {
    "request_type": {"id", "code", "lifecycle", "is_active", "active_release_id", "name", "description", "category"},
    "config_release": {"id", "type_id", "version", "state", "form_schema", "route_rules", "actor_bindings", "sla_profile"},
    "request": {"id", "code", "type_id", "requester_id", "draft_payload", "status"},
    "app_user": {"id", "username", "display_name", "department_id", "is_active"},
}
ALLOWED_CATEGORIES = {"HR", "IT", "FACILITY", "PROCUREMENT", "ASSET", "FINANCE", "GENERAL"}


def _verify_tables(cur) -> bool:
    cur.execute("SET TRANSACTION READ ONLY")
    cur.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='eas'")
    rows = cur.fetchall()
    names = {}
    for table, col in rows:
        names.setdefault(table, set()).add(col)
    ok = True
    for table, required in REQUIRED.items():
        missing = required - names.get(table, set())
        print(f"[{ 'PASS' if not missing else 'FAIL' }] eas.{table}: " +
              ("các cột cần thiết tồn tại" if not missing else "thiếu " + ', '.join(sorted(missing))))
        ok &= not missing
    return ok


def _verify_categories(cur) -> bool:
    cur.execute("SELECT category, COUNT(*) FROM eas.request_type GROUP BY category ORDER BY category")
    ok = True
    for category, count in cur.fetchall():
        if category not in ALLOWED_CATEGORIES:
            ok = False
            print("[FAIL] category không hợp lệ")
        else:
            print(f"[PASS] category '{category}' có {count} loại yêu cầu")
    return ok

def main():
    load_environment(Path(__file__).with_name(".env"))
    import psycopg
    try:
        with psycopg.connect(database_url(), connect_timeout=8, prepare_threshold=None,
                             options="-c statement_timeout=8000 -c lock_timeout=2500") as conn, conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='eas'")
                rows = cur.fetchall()
                names = {}
                for table, col in rows:
                    names.setdefault(table, set()).add(col)
                ok = True
                for table, required in REQUIRED.items():
                    missing = required - names.get(table, set())
                    print(f"[{ 'PASS' if not missing else 'FAIL' }] eas.{table}: " +
                          ("các cột cần thiết tồn tại" if not missing else "thiếu " + ', '.join(sorted(missing))))
                    ok &= not missing
                if ok:
                    cur.execute("SELECT category, COUNT(*) FROM eas.request_type GROUP BY category ORDER BY category")
                    for category, count in cur.fetchall():
                        if category not in ALLOWED_CATEGORIES:
                            ok = False
                            print("[FAIL] category không hợp lệ")
                        else:
                            print(f"[INFO] category={category}: {count} loại")
                print("Chỉ đọc schema và thống kê; không migrate/seed hay sửa release.")
                return 0 if ok else 1
    except psycopg.Error as exc:
        print("[FAIL] PostgreSQL:", exc.sqlstate or type(exc).__name__)
        return 2

if __name__ == "__main__":
    sys.exit(main())
