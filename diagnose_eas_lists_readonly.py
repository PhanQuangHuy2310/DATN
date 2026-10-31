"""Read-only diagnostics for EAS requests, notifications, and reports.
Run from DATN root with the Python executable inside the .venv environment.
The checks use the backend runtime role, not the browser session. No secret output.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def classify(exc):
    current = exc
    seen = set()
    state = "unknown"
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        s = getattr(current, "sqlstate", None)
        if isinstance(s, str) and len(s) == 5:
            state = s
            break
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    reasons = {
        "42P10": "DISTINCT_ORDER_BY_ERROR",
        "42P18": "UNTYPED_SQL_PARAMETER",
        "42501": "PERMISSION_DENIED",
        "42P01": "TABLE_NOT_FOUND",
        "42703": "COLUMN_NOT_FOUND",
        "42883": "OPERATOR_OR_FUNCTION_NOT_FOUND",
        "22P02": "INVALID_TEXT_OR_UUID_FORMAT",
        "57014": "QUERY_TIMEOUT",
    }
    return type(exc).__name__, state, reasons.get(state, "CHECK_BACKEND_LOG")


def main():
    root = Path(__file__).resolve().parent
    os.chdir(root)
    if not (root / ".env").exists():
        print("ERROR: File .env chua co.")
        return 2
    import connect_database
    connect_database.load_environment(root / ".env")
    os.environ["DATABASE_URL"] = connect_database.database_url()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.config.settings")
    import django
    django.setup()
    from django.db import connection, transaction
    from django.test import RequestFactory
    from api_core.authn.models import Actor
    from api_core.workflow.reporting import list_notifications, get_request_metrics_report
    from api_core.workflow.views import request_list

    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SELECT current_user, id::text, username, display_name, department_id::text, auth_version, must_change_password FROM eas.app_user WHERE username = %s AND is_active", ["admin"])
            row = c.fetchone()
    if not row:
        print("ERROR: Khong tim thay tai khoan admin active de test pham vi du lieu.")
        return 2
    print("DATABASE_ROLE:", row[0], "| TEST_ACTOR:", row[2])
    actor = Actor(id=row[1],username=row[2],display_name=row[3], department_id=row[4],auth_version=row[5],roles=frozenset(),must_change_password=row[6])

    def execute(name,fn):
        try:
            with transaction.atomic():
                with connection.cursor() as c:
                    c.execute("SET TRANSACTION READ ONLY")
                result = fn()
            print("[PASS]",name,result)
            return True
        except Exception as e:
            print("[FAIL]",name,"EXCEPTION/SQLSTATE/REASON:",*classify(e))
            return False

    def requests():
        req=RequestFactory().get("/api/v1/requests?limit=20&offset=0&tab=mine")
        req.actor=actor
        resp=request_list.__wrapped__(req)
        return "http="+str(resp.status_code)
    def notifications():
        obj=list_notifications(actor, {"limit":"20", "offset":"0", "unread":"false"})
        return "items="+str(len(obj["items"]))
    def reports():
        now=datetime.now(timezone.utc)
        obj=get_request_metrics_report(actor,{"created_from":(now-timedelta(days=30)).isoformat(),"created_to":now.isoformat()})
        return "submitted="+str(obj["report"]["submitted"])
    a=execute("REQUESTS_MINE",requests)
    b=execute("NOTIFICATIONS",notifications)
    c=execute("REPORTS_REQUESTS",reports)
    print("SUMMARY:","ALL_PASS" if all((a,b,c)) else "FAILURES_PRESENT", "(read only)")
    return 0 if all((a,b,c)) else 1


if __name__ == "__main__":
    sys.exit(main())
