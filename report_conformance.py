#!/usr/bin/env python3
"""Read-only source audit against the supplied thesis (NOT an E2E test).

Usage: py -3.12 report_conformance.py [--json]
Never reads or prints .env secrets. Does not connect to Supabase or change files.
"""
from pathlib import Path
import argparse
import json


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "docs" / "REPORT_V1_SOURCE_MATRIX.json"


def check() -> dict:
    matrix = json.loads(SOURCE.read_text(encoding="utf-8"))
    def present(relative):
        return (ROOT / relative).is_file()
    def contains(relative, literal):
        try:
            return literal in (ROOT / relative).read_text(encoding="utf-8")
        except OSError:
            return False
    checks = [
        {"id": "UC01", "description": "Đăng nhập / session", "status": "CODE_PRESENT" if present("api_core/authn/views.py") else "GAP"},
        {"id": "UC02", "description": "Phát hành chính sách versioning", "status": "CODE_PRESENT" if present("api_core/workflow/config_service.py") else "GAP"},
        {"id": "UC03-UC12", "description": "Workflow A/B/C và thao tác theo role", "status": "CODE_PRESENT" if present("api_core/workflow/service.py") else "GAP"},
        {"id": "UC13-UC14", "description": "Notification / SLA worker", "status": "CODE_PRESENT" if present("api_core/worker.py") else "GAP"},
        {"id": "UC15", "description": "Chuỗi kiểm toán", "status": "CODE_PRESENT" if present("api_core/audit.py") else "GAP"},
        {"id": "UC17", "description": "User + role membership", "status": "CODE_PRESENT" if present("api_core/administration/service.py") else "GAP"},
        {"id": "CATALOG", "description": "Màn hình biểu mẫu sinh theo policy đã publish", "status": "CODE_PRESENT" if contains("web_client/src/components/RequestEditor.jsx", "request-type-forms") else "GAP"},
        {"id": "P0_CONSTRAINT", "description": "Bộ DDL gốc còn khóa danh mục 3 loại P0", "status": "MIGRATION_REQUIRED" if contains("database/EAS_Supabase_SQL/00_eas_supabase_schema.sql", "CONSTRAINT type_p0") else "REVIEW_REQUIRED"},
        {"id": "DB_16_TYPES", "description": "16 loại yêu cầu với mã / config / quyền chính thức", "status": "NOT_VERIFIED", "note":"Báo cáo nêu số lượng 16 nhưng không liệt kê danh mục mã đầy đủ; phải thống nhất và kiểm tra Database live."},
        {"id": "AI_5", "description": "5 router chức năng AI", "status": "CODE_PRESENT" if all(present("ai_service/routers/"+x+".py") for x in ["classify","risk","auto_approve","ocr","summarize"]) else "GAP", "note":"Router tồn tại không chứng minh đã tích hợp an toàn vào transaction Django."},
        {"id": "AI_AUTO_APPROVAL", "description": "Tự duyệt AI/SoD/audit/rollback", "status": "NOT_VERIFIED", "note":"Không bật auto-approve chỉ dựa vào Risk Score; phải có kiểm soát ngân sách, policy và audit."},
        {"id": "SLA_80", "description": "Cảnh báo 80% SLA theo báo cáo", "status": "MIGRATION_REQUIRED" if contains("database/EAS_Supabase_SQL/00_eas_supabase_schema.sql", "'0.5'::jsonb") else "REVIEW_REQUIRED"},
        {"id": "8_MOCK", "description": "8 schema mock tích hợp", "status": "CODE_PRESENT" if present("database/mock_enterprise_sql/00_mock_enterprise_schemas.sql") else "GAP", "note":"Chưa kiểm tra dữ liệu live và quyền SELECT."},
        {"id": "MOBILE", "description": "Mobile Flutter/FCM", "status": "NOT_VERIFIED", "note":"Không suy diễn chức năng Mobile đã hoàn tất từ mô tả báo cáo."},
        {"id": "GATEWAY", "description": "Nginx Rate Limit và Correlation ID", "status": "NOT_VERIFIED", "note":"Cần thử qua nginx reverse proxy trên môi trường triển khai."},
        {"id": "SECURITY", "description": "RBAC/SoD/IDOR/race/load", "status": "NOT_VERIFIED", "note":"Chỉ kiểm thử tích hợp đa vai trò trên Database thật mới xác nhận."},
    ]
    return {"source":matrix["source"],"scope":matrix["scope"],"checks":checks,
            "warning":"CODE_PRESENT chỉ xác nhận hiện diện code, KHÔNG phải PASS runtime/acceptance."}


def live_database_checks():
    """Opt-in read-only DB inspection. Never print DSN, passwords or SQL values."""
    try:
        import psycopg
        from connect_database import load_environment, database_url
        load_environment(ROOT / ".env")
        url = database_url()
    except Exception:
        # Do not stringify errors: some DB exception text contains DSN and host.
        return {"status":"SKIPPED", "reason":"Missing psycopg or database environment; install the project venv and configure .env."}
    try:
        with psycopg.connect(url,connect_timeout=8,prepare_threshold=None,
                             options="-c statement_timeout=8000 -c lock_timeout=2000") as conn:
            with conn.cursor() as c:
                c.execute("SET TRANSACTION READ ONLY")
                c.execute("""SELECT rt.code,rt.lifecycle,
                    (cr.id IS NOT NULL AND cr.state='PUBLISHED' AND cr.lifecycle=rt.lifecycle
                     AND cr.type_id=rt.id) AS configured
                    FROM eas.request_type rt
                    LEFT JOIN eas.config_release cr ON cr.id=rt.active_release_id
                    WHERE rt.is_active ORDER BY rt.code""")
                types=[{"code":code,"lifecycle":life,"configured":configured}
                       for code,life,configured in c.fetchall()]
                c.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='eas' AND table_type='BASE TABLE'")
                table_count=c.fetchone()[0]
                return {"status":"READ_ONLY_OK", "count_types":len(types),
                        "target_types":16,"all_types_configured":all(t['configured'] for t in types),
                        "types":types,"eas_table_count":table_count,
                        "report_16_types_met":len(types)==16 and all(t['configured'] for t in types)}
    except Exception as exc:
        return {"status":"CHECK_FAILED", "sqlstate":getattr(exc,"sqlstate",None),
                "reason":"Check safe role permissions, connectivity, schema version or statement timeout; details omitted to protect credentials."}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--json",action="store_true")
    parser.add_argument("--live-db",action="store_true",help="Connect to Supabase in READ ONLY mode using .env")
    args=parser.parse_args()
    result=check()
    if args.live_db:
        result['database']=live_database_checks()
    if args.json:
        print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print("EAS REPORT v1 - KIEM TRA KHOI MA NGUON (READ ONLY)")
        for item in result["checks"]:
            print(f"[{item['status']}] {item['id']}: {item['description']}")
        if args.live_db:
            db=result['database']
            print(f"DB READ-ONLY: {db['status']} | {db.get('count_types','?')}/16 types | tables={db.get('eas_table_count','?')}")
        print("KHONG TU DONG CAP NHAT DB; KHONG XAC NHAN PASS END-TO-END.")

if __name__ == "__main__":
    main()
