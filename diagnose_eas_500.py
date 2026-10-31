"""Safe read-only diagnostics for EAS-002 and EAS-003 HTTP 500 errors.

Tests PostgreSQL queries for /api/v1/notifications and /api/v1/requests
in a strictly READ ONLY transaction without writing data or altering schema.
Does not print database credentials or secrets.
"""

from __future__ import annotations

import os
import sys
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    with suppress(Exception):
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def mask_url(url: str) -> str:
    """Mask password and user in database URL."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or "unknown"
        port = f":{parts.port}" if parts.port else ""
        db = parts.path or ""
        return f"{parts.scheme}://***:***@{host}{port}{db}"
    except (ValueError, TypeError, AttributeError):
        return "<masked_url>"


def run_diagnostics() -> int:
    root = Path(__file__).resolve().parent
    env_file = root / ".env"

    print("=== CHẨN ĐOÁN LỖI EAS-002 & EAS-003 (READ ONLY) ===")

    if (
        not env_file.is_file()
        and not os.getenv("DATABASE_URL")
        and not os.getenv("EAS_API_DATABASE_URL")
    ):
        print(
            "[SKIP] Không tìm thấy file .env hoặc biến môi trường DATABASE_URL."
        )
        print("       Vui lòng cấu hình .env trước khi chạy chẩn đoán SQL.")
        return 0

    try:
        import connect_database as eas
    except ImportError:
        print("[FAIL] Không thể import connect_database.py")
        return 1

    try:
        if env_file.is_file():
            eas.load_environment(env_file)
        db_uri = eas.database_url()
    except (ValueError, KeyError, eas.ConfigurationError, OSError) as exc:
        print(f"[FAIL] Lỗi đọc cấu hình database: {type(exc).__name__}: {exc}")
        return 1

    try:
        import psycopg
    except ImportError:
        print(
            "[SKIP] Chưa cài đặt thư viện psycopg. Chạy: python -m pip install -r requirements-db.txt"
        )
        return 0

    masked = mask_url(db_uri)
    print(f"[*] Kết nối tới database: {masked}")

    sample_uuid = "00000002-0000-4000-8000-000000000008"

    try:
        with (
            psycopg.connect(
                db_uri,
                connect_timeout=10,
                prepare_threshold=None,
                options="-c statement_timeout=10000 -c lock_timeout=3000",
            ) as conn,
            conn.cursor() as cur,
        ):
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT current_user, current_database()")
            user, db = cur.fetchone()
            print(f"[*] Phiên làm việc: user={user}, database={db} (READ ONLY)")

            # -----------------------------------------------------------
            # Test 1: EAS-002 (/api/v1/notifications?limit=20&offset=0&unread=false)
            # -----------------------------------------------------------
            print("\n--- Kiểm tra EAS-002: Query notifications ---")
            try:
                # Check COUNT query
                cur.execute(
                    "SELECT COUNT(*) FROM eas.notification WHERE recipient_id = %s AND read_at IS NULL",
                    (sample_uuid,),
                )
                count = cur.fetchone()[0]

                # Check list query (unread=false -> evaluates %s::boolean IS FALSE)
                query_eas002 = """
                    SELECT id::text, event_id::text, request_id::text, label, read_at, created_at
                    FROM eas.notification
                    WHERE recipient_id = %s
                      AND (%s::boolean IS FALSE OR read_at IS NULL)
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(query_eas002, [sample_uuid, False, 21, 0])
                rows_eas002 = cur.fetchall()
                print(
                    f"[PASS] EAS-002: Query notifications (unread=false) thành công (count={count}, rows={len(rows_eas002)})."
                )

                # Also test unread=true
                cur.execute(query_eas002, [sample_uuid, True, 21, 0])
                rows_unread = cur.fetchall()
                print(
                    f"[PASS] EAS-002: Query notifications (unread=true) thành công (rows={len(rows_unread)})."
                )

            except psycopg.Error as exc:
                sqlstate = getattr(exc, "sqlstate", "unknown")
                print(f"[FAIL] EAS-002: Lỗi SQLSTATE={sqlstate}: {exc}")
                if sqlstate == "42P18":
                    print(
                        "       Nguyên nhân: Tham số không xác định kiểu dữ liệu (%s IS FALSE trong pooler)."
                    )
                return 1

            # -----------------------------------------------------------
            # Test 2: EAS-003 (/api/v1/requests?limit=20&offset=0&tab=mine&_revision=0)
            # -----------------------------------------------------------
            print("\n--- Kiểm tra EAS-003: Query requests ---")
            try:
                # Dynamic WHERE clauses matching fixed api_core/workflow/views.py
                for test_tab in ["mine", "approval", "execution", "acceptance", "all"]:
                    valid_tab = test_tab if test_tab in ("mine", "approval", "execution", "acceptance") else None
                    tab_params = [
                        None,  # status_filter
                        None,
                        None,  # search_filter
                        None,
                        None,  # type_code_filter
                        None,
                        None,  # dept_filter
                        None,
                        None,  # from_filter
                        None,
                        None,  # to_filter
                        None,
                        valid_tab,
                        sample_uuid,
                        valid_tab,
                        sample_uuid,
                        valid_tab,
                        sample_uuid,
                        valid_tab,
                        sample_uuid,
                        valid_tab,
                        sample_uuid,
                        sample_uuid,
                        sample_uuid,
                        21,
                        0,
                    ]
                    query_eas003 = """
                        SELECT r.id::text, r.code, rt.code, r.status, r.lock_version,
                               r.updated_at, r.created_at
                        FROM eas.request r
                        JOIN eas.request_type rt ON rt.id = r.type_id
                        LEFT JOIN eas.request_revision v ON v.id = r.current_revision_id
                        LEFT JOIN eas.app_user u ON u.id = r.requester_id
                        WHERE (%s::text IS NULL OR r.status = %s)
                          AND (%s::text IS NULL OR STRPOS(LOWER(r.code), LOWER(%s::text)) > 0)
                          AND (%s::text IS NULL OR rt.code = %s)
                          AND (%s::uuid IS NULL OR COALESCE(v.department_id, u.department_id) = %s::uuid)
                          AND (%s::timestamptz IS NULL OR r.created_at >= %s::timestamptz)
                          AND (%s::timestamptz IS NULL OR r.created_at <= %s::timestamptz)
                          AND (
                            (%s::text = 'mine' AND r.requester_id = %s)
                            OR (%s::text = 'approval' AND EXISTS (
                              SELECT 1 FROM eas.approval_step ast
                              WHERE ast.request_id = r.id AND ast.state = 'ACTIVE' AND ast.assignee_id = %s
                            ))
                            OR (%s::text = 'execution' AND EXISTS (
                              SELECT 1 FROM eas.workflow_instance wi
                              JOIN eas.execution_attempt ea ON ea.instance_id = wi.id
                              WHERE wi.request_id = r.id AND ea.state IN ('READY', 'RUNNING') AND ea.executor_id = %s
                            ))
                            OR (%s::text = 'acceptance' AND EXISTS (
                              SELECT 1 FROM eas.workflow_instance wi
                              JOIN eas.execution_attempt ea ON ea.instance_id = wi.id
                              WHERE wi.request_id = r.id AND wi.state = 'ACTIVE' AND wi.lifecycle = 'C'
                                AND wi.acceptor_id = %s AND ea.state = 'SUBMITTED'
                            ))
                            OR (%s::text IS NULL AND (
                                r.requester_id = %s
                                OR (
                                  r.status != 'DRAFT'
                                  AND EXISTS (
                                    SELECT 1 FROM eas.request_participant p
                                    WHERE p.request_id = r.id AND p.user_id = %s AND p.read_revoked_at IS NULL
                                  )
                                )
                                OR (
                                  r.status != 'DRAFT'
                                  AND EXISTS (
                                    SELECT 1 FROM eas.role_membership rm
                                    WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
                                      AND rm.revoked_at IS NULL
                                      AND rm.valid_from <= statement_timestamp()
                                      AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
                                      AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
                                      AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
                                  )
                                )
                            ))
                          )
                        ORDER BY r.updated_at DESC, r.id DESC
                        LIMIT %s OFFSET %s
                    """
                    cur.execute(query_eas003, tab_params)
                    rows_tab = cur.fetchall()
                    print(
                        f"[PASS] EAS-003: Query requests tab={test_tab} thành công (rows={len(rows_tab)})."
                    )

            except psycopg.Error as exc:
                sqlstate = getattr(exc, "sqlstate", "unknown")
                print(f"[FAIL] EAS-003: Lỗi SQLSTATE={sqlstate}: {exc}")
                if sqlstate == "42P18":
                    print(
                        "       Nguyên nhân: Tham số không xác định kiểu dữ liệu (%s IS NULL trong pooler)."
                    )
                return 1

            print(
                "\n=== KẾT QUẢ CHẨN ĐOÁN: TẤT CẢ TRUY VẤN EAS-002 & EAS-003 HOẠT ĐỘNG TỐT (PASS) ==="
            )
            return 0

    except psycopg.Error as exc:
        sqlstate = getattr(exc, "sqlstate", "unknown")
        print(f"[FAIL] Không thể kết nối database: SQLSTATE={sqlstate}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(run_diagnostics())
