#!/usr/bin/env python3
r"""Read-only local connectivity audit for EAS; never prints credentials.
Place this beside connect_database.py and run with the project's .venv Python.

Usage: .\.venv\Scripts\python.exe check_eas_connections_local.py
       .\.venv\Scripts\python.exe check_eas_connections_local.py --config-only
No database writes, migrations, login attempts, uploads or antivirus scan submissions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, status, name, detail):
        assert status in {"PASS", "WARN", "FAIL", "SKIP"}
        self.rows.append((status, name, detail))
        print(f"[{status}] {name}: {detail}")


def read_env(path):
    data = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        data[key] = val
    return data


def req(url, *, headers=None, timeout=3):
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=timeout) as res:
            payload = res.read(16384)
            return res.status, payload
    except HTTPError as exc:
        return exc.code, b""  # no response echo: avoid leaking data
    except (URLError, TimeoutError, ConnectionError, OSError):
        return None, b""


def jget(payload):
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}


def dbprobe(c, url, name, expected_membership):
    try:
        import psycopg
    except ImportError:
        c.add("WARN", name, "psycopg chưa được cài trong Python này")
        return
    try:
        with psycopg.connect(url, connect_timeout=5, prepare_threshold=None) as cn:
            with cn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    "SELECT current_user, pg_has_role(current_user,%s,%s)",
                    (expected_membership, "member"),
                )
                user, member = cur.fetchone()
                if not member:
                    c.add(
                        "FAIL",
                        name,
                        f"Đăng nhập được nhưng không thuộc nhóm {expected_membership}",
                    )
                else:
                    c.add(
                        "PASS",
                        name,
                        f"Đăng nhập được bằng role {user}; thuộc nhóm {expected_membership}",
                    )
                if expected_membership == "eas_api":
                    cur.execute(
                        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='eas' AND table_type='BASE TABLE'"
                    )
                    cnt = cur.fetchone()[0]
                    c.add(
                        "PASS" if cnt >= 30 else "FAIL",
                        "30 bảng EAS",
                        f"Tìm thấy {cnt} bảng (cần ít nhất 30)",
                    )
    except Exception as exc:
        state = getattr(exc, "sqlstate", None)
        if state == "28P01":
            reason = "Mật khẩu hoặc username không hợp lệ"
        elif state == "42501":
            reason = "Thiếu quyền PostgreSQL"
        elif state == "3D000":
            reason = "Database không tồn tại"
        else:
            reason = (
                f"Lỗi kết nối ({type(exc).__name__}, SQLSTATE={state or 'unknown'})"
            )
        c.add("FAIL", name, reason)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Kiểm tra các kết nối EAS (chỉ đọc, không in mật khẩu)"
    )
    p.add_argument(
        "--config-only",
        action="store_true",
        help="Chỉ kiểm tra cấu hình và mã nguồn, không gọi mạng/DB",
    )
    a = p.parse_args(argv)
    c = Checks()
    dbfile = ROOT / ".env"
    local = read_env(dbfile)
    root = read_env(ROOT / ".env")
    worker = read_env(ROOT / ".env")
    ai = read_env(ROOT / "ai_service" / ".env")
    effective = os.environ.copy()
    for k, v in local.items():
        effective.setdefault(k, v)
    print("=== EAS LOCAL CONNECTIVITY AUDIT (read-only; credentials hidden) ===")
    for f in [
        "connect_database.py",
        ".env",
        "web_client/vite.config.js",
        "ai_service/main.py",
        ".env",
    ]:
        c.add(
            "PASS" if (ROOT / f).is_file() else "FAIL",
            "File " + f,
            "Có" if (ROOT / f).is_file() else "Không tìm thấy",
        )
    if not local:
        c.add("FAIL", "Backend config", "Không đọc được .env")
    if local and (ROOT / "connect_database.py").exists():
        try:
            from connect_database import database_url

            dburl = database_url(effective)
            parsed = urlsplit(dburl)
            c.add(
                "PASS",
                "Backend DB URL",
                f"Kết nối theo {'DATABASE_URL/EAS_API_DATABASE_URL' if effective.get('DATABASE_URL') or effective.get('EAS_API_DATABASE_URL') else 'DB_*'}, user={unquote(parsed.username or '[missing]')}, port={parsed.port or '[missing]'}",
            )
        except Exception as exc:
            dburl = None
            c.add(
                "FAIL",
                "Backend DB URL",
                f"Lỗi cú pháp hoặc thiếu biến ({type(exc).__name__})",
            )
    else:
        dburl = None

    if local.get("EAS_REQUIRE_STORAGE", "true").lower() == "false":
        c.add(
            "WARN",
            "Storage local",
            "EAS_REQUIRE_STORAGE=false: readiness bỏ qua Storage/ClamAV, upload thật chưa được chứng minh",
        )
    if not effective.get("DJANGO_SECRET_KEY"):
        c.add(
            "WARN",
            "Django secret",
            "Thiếu DJANGO_SECRET_KEY trong môi trường Backend đang dùng; development sẽ dùng khóa mặc định",
        )
    if not effective.get("SUPABASE_URL") or not effective.get("SUPABASE_SECRET_KEY"):
        c.add(
            "WARN",
            "Supabase Storage",
            "Backend chưa được cấp đủ SUPABASE_URL và SUPABASE_SECRET_KEY (có thể đang tắt yêu cầu Storage)",
        )
    if not effective.get("REDIS_URL"):
        c.add(
            "WARN",
            "Redis/cache",
            "Chạy LocMem trong development; không thay thế Redis cho nhiều process",
        )

    dbsecret = (
        effective.get("EAS_AI_INTERNAL_SECRET")
        or effective.get("INTERNAL_API_SECRET")
        or (
            "eas-local-dev-shared-internal-secret-2026"
            if effective.get("ENVIRONMENT", "development") in {"development", "test"}
            else ""
        )
    )
    aisecret = (
        os.environ.get("INTERNAL_API_SECRET")
        or ai.get("INTERNAL_API_SECRET")
        or (
            "eas-local-dev-shared-internal-secret-2026"
            if effective.get("ENVIRONMENT", "development") in {"development", "test"}
            else ""
        )
    )
    if dbsecret and aisecret and dbsecret == aisecret:
        c.add(
            "PASS",
            "Django ↔ AI secret",
            "Hai phía sử dụng cùng secret (không hiển thị giá trị)",
        )
    else:
        c.add(
            "FAIL",
            "Django ↔ AI secret",
            "EAS_AI_INTERNAL_SECRET của Django khác INTERNAL_API_SECRET của AI",
        )
    if not ai.get("INTERNAL_API_SECRET"):
        c.add(
            "WARN",
            "AI secret missing",
            "Chưa cấu hình INTERNAL_API_SECRET trong .env (đang dùng fallback local)",
        )
    aiurl = effective.get("EAS_AI_SERVICE_URL", "http://ai-service:8001").rstrip("/")
    if aiurl == "http://127.0.0.1:8001" or aiurl == "http://localhost:8001":
        c.add("PASS", "AI địa chỉ local", aiurl)
    else:
        c.add(
            "WARN",
            "AI địa chỉ local",
            f"EAS_AI_SERVICE_URL={aiurl}; nếu chạy bằng Terminal cần http://127.0.0.1:8001",
        )
    clientfile = ROOT / "api_core" / "ai_client.py"
    routerfile = ROOT / "ai_service" / "routers" / "classify.py"
    if clientfile.is_file() and routerfile.is_file():
        client = clientfile.read_text(encoding="utf-8")
        router = routerfile.read_text(encoding="utf-8")
        has_post_request = bool(
            re.search(r'@router\.post\(\s*["\']/request["\']', router)
        )
        if "/ai/classify/request" in client and not has_post_request:
            c.add(
                "FAIL",
                "AI classify route",
                "Django gọi /ai/classify/request nhưng FastAPI định nghĩa /ai/classify/classify",
            )
        else:
            c.add(
                "PASS",
                "AI classify route",
                "Không thấy mismatch đường dẫn phân loại đã biết",
            )
        riskrouter = ROOT / "ai_service" / "routers" / "risk.py"
        if riskrouter.exists():
            rsrc = riskrouter.read_text(encoding="utf-8")
            if "amount_vnd: float" in rsrc and (
                '"amount_vnd"' not in client or '"num_attachments"' not in client
            ):
                c.add(
                    "WARN",
                    "AI risk payload",
                    "Django gửi amount/attachment_count, FastAPI đọc amount_vnd/num_attachments; AI có thể dùng mặc định",
                )
        use_client = []
        for mod in (ROOT / "api_core").rglob("*.py"):
            if "tests" in mod.parts or mod in {
                clientfile,
                ROOT / "api_core" / "integrations" / "ai_service.py",
            }:
                continue
            try:
                code = mod.read_text(encoding="utf-8")
            except OSError:
                continue
            if any(
                x in code
                for x in (
                    "ai_client_sync",
                    "AIServiceClient(",
                    "ai_client.score_",
                    "ai_client.classify_",
                    "ai_client.summarize_",
                    "ai_client.evaluate_",
                )
            ):
                use_client.append(str(mod.relative_to(ROOT)))
        if not use_client:
            c.add(
                "WARN",
                "AI tích hợp nghiệp vụ",
                "Không tìm thấy code gọi AI client từ các view/service Backend; các model có thể chưa được kích hoạt",
            )
    model_dir = ROOT / "ai_service" / "models"
    for model in [
        "risk_model.pkl",
        "nlp_vectorizer.pkl",
        "nlp_request_type_model.pkl",
        "nlp_department_model.pkl",
        "nlp_template_model.pkl",
    ]:
        c.add(
            "PASS" if (model_dir / model).is_file() else "WARN",
            "AI model " + model,
            "Có" if (model_dir / model).is_file() else "Thiếu",
        )
    if not ai.get("GEMINI_API_KEY"):
        c.add(
            "WARN",
            "Gemini",
            "Chưa cấu hình khóa; API tóm tắt dùng Gemini có thể không chạy",
        )
    raw_worker_url = worker.get("EAS_WORKER_DATABASE_URL") or root.get(
        "EAS_WORKER_DATABASE_URL", ""
    )
    placeholders = (
        "YOUR_PROJECT_REF",
        "YOUR_POOLER_HOST",
        "ENCODED_PASSWORD",
        "YOUR_PASSWORD",
    )
    has_placeholder = bool(
        raw_worker_url and any(ph in raw_worker_url for ph in placeholders)
    )

    w_user = worker.get("WORKER_DB_USER") or effective.get("WORKER_DB_USER", "")
    w_pass = worker.get("WORKER_DB_PASSWORD") or effective.get(
        "WORKER_DB_PASSWORD", ""
    )

    workerurl = None
    if (not raw_worker_url or has_placeholder) and w_user and w_pass:
        host = effective.get("DB_HOST", "127.0.0.1")
        port = effective.get("DB_PORT", "5432")
        dbname = effective.get("DB_NAME", "postgres")
        workerurl = f"postgresql://{quote(w_user, safe='.')}:{quote(w_pass, safe='')}@{host}:{port}/{dbname}"
        has_placeholder = False
    elif raw_worker_url and not has_placeholder:
        workerurl = raw_worker_url

    if not raw_worker_url and not workerurl:
        c.add(
            "WARN",
            "Worker DSN",
            "Không tìm thấy EAS_WORKER_DATABASE_URL trong .env (hoặc .env Docker)",
        )
    elif has_placeholder:
        c.add(
            "WARN",
            "Worker DSN",
            "EAS_WORKER_DATABASE_URL chứa chuỗi mẫu chưa cấu hình (YOUR_PROJECT_REF/YOUR_POOLER_HOST/ENCODED_PASSWORD)",
        )
        workerurl = None
    else:
        try:
            w = urlsplit(workerurl)
            if w.username and w.password:
                user = unquote(w.username)
                pwd = unquote(w.password)
                host_part = w.hostname
                if w.port:
                    host_part = f"{host_part}:{w.port}"
                workerurl = f"{w.scheme}://{quote(user, safe='.')}:{quote(pwd, safe='')}@{host_part}{w.path}"
                if w.query:
                    workerurl += f"?{w.query}"
                w = urlsplit(workerurl)
            if "worker" not in unquote(w.username or ""):
                c.add(
                    "WARN",
                    "Worker user",
                    "DSN không mang tên tài khoản Worker mong đợi",
                )
            else:
                c.add("PASS", "Worker config", "Có DSN riêng cho eas_worker_login")
            apiurl = root.get("EAS_API_DATABASE_URL")
            if apiurl and unquote(urlsplit(apiurl).password or "") == unquote(
                w.password or ""
            ):
                c.add(
                    "WARN",
                    "Mật khẩu worker",
                    "Backend và Worker đang dùng cùng mật khẩu; nên đặt riêng từng role",
                )
        except Exception:
            c.add("FAIL", "Worker config", "URL worker không hợp lệ")
            workerurl = None
    if a.config_only:
        c.add(
            "SKIP",
            "Network/DB",
            "--config-only: không gọi HTTP, PostgreSQL, Storage hay ClamAV",
        )
    else:
        if dburl:
            dbprobe(c, dburl, "PostgreSQL Backend", "eas_api")
        if workerurl:
            dbprobe(c, workerurl, "PostgreSQL Worker", "eas_worker")
        for name, url, valid in [
            ("Backend /health/live", "http://127.0.0.1:8000/health/live", {200}),
            ("Backend /health/ready", "http://127.0.0.1:8000/health/ready", {200}),
            ("Backend CSRF", "http://127.0.0.1:8000/api/v1/auth/csrf", {200}),
            ("Frontend Vite", "http://127.0.0.1:5173/", {200}),
            ("Frontend proxy CSRF", "http://127.0.0.1:5173/api/v1/auth/csrf", {200}),
            (
                "Chưa đăng nhập /auth/me",
                "http://127.0.0.1:8000/api/v1/auth/me",
                {401, 200},
            ),
            ("AI /health", "http://127.0.0.1:8001/health", {200}),
        ]:
            status, payload = req(url)
            isok = status in valid
            if (
                name == "Backend /health/ready"
                and status == 200
                and jget(payload).get("status") != "ready"
            ):
                isok = False
            c.add(
                "PASS" if isok else "FAIL",
                name,
                f"HTTP {status if status is not None else 'không kết nối được'}",
            )
        if dbsecret and dbsecret == aisecret:
            status, _ = req(
                "http://127.0.0.1:8001/ai/__connection_probe__",
                headers={"X-Internal-Secret": dbsecret},
            )
            c.add(
                "PASS" if status == 404 else "FAIL",
                "Django → AI xác thực nội bộ",
                f"HTTP {status}; 404 ở đường thử không tồn tại = secret được middleware chấp nhận",
            )
        else:
            c.add(
                "SKIP",
                "Django → AI xác thực nội bộ",
                "Bỏ qua vì hai secret đang không khớp",
            )
        if effective.get("EAS_REQUIRE_STORAGE", "true").lower() == "true":
            host = effective.get("EAS_CLAMAV_HOST", "clamav")
            try:
                with socket.create_connection(
                    (host, int(effective.get("EAS_CLAMAV_PORT", "3310"))), 3
                ) as s:
                    s.settimeout(3)
                    s.sendall(b"zPING\0")
                    reply = s.recv(20)
                c.add(
                    "PASS" if reply.startswith(b"PONG") else "FAIL",
                    "ClamAV ping",
                    "PONG" if reply.startswith(b"PONG") else "Chưa trả lời PONG",
                )
            except Exception:
                c.add("FAIL", "ClamAV ping", "Không kết nối được daemon")
            surl = effective.get("SUPABASE_URL", "").rstrip("/")
            skey = effective.get("SUPABASE_SECRET_KEY", "")
            bucket = effective.get("EAS_STORAGE_BUCKET", "eas-private")
            if surl and skey:
                headers = {"apikey": skey}
                if not skey.startswith("sb_secret_"):
                    headers["Authorization"] = "Bearer " + skey
                status, _ = req(
                    f"{surl}/storage/v1/bucket/{quote(bucket, safe='')}",
                    headers=headers,
                    timeout=5,
                )
                c.add(
                    "PASS" if status == 200 else "FAIL",
                    "Supabase bucket (read-only)",
                    f"HTTP {status if status else 'không kết nối được'}",
                )
            else:
                c.add("FAIL", "Supabase bucket", "Thiếu cấu hình trong .env")
        else:
            c.add(
                "SKIP",
                "Supabase bucket/ClamAV",
                "Đã tắt EAS_REQUIRE_STORAGE, không thử hai kết nối này",
            )
    counts = {
        x: sum(row[0] == x for row in c.rows) for x in ["PASS", "WARN", "FAIL", "SKIP"]
    }
    print("\n=== TỔNG KẾT ===")
    print(", ".join(f"{k}={v}" for k, v in counts.items()))
    print(
        "Không có thao tác ghi database, POST đăng nhập, migrate, upload hoặc thay đổi .env."
    )
    return 2 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
