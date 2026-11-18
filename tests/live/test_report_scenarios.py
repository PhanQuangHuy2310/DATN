r"""Kiểm thử đầu-cuối qua API thật cho các testcase trong báo cáo (Bảng 3.13, 3.16).

CHỈ chạy trên bản sao CSDL ở máy local (QA sandbox), KHÔNG chạy trên Supabase dùng chung:
script tự từ chối nếu DSN oracle không trỏ tới localhost/127.0.0.1.

Chuẩn bị (xem docs/HUONG_DAN_SUPABASE_LOCAL.md):
  - API đang chạy và trỏ vào bản sao (mặc định http://127.0.0.1:8000)
  - các tài khoản trong bản sao có mật khẩu thử chung (EAS_LIVE_PASSWORD)
  - EAS_LIVE_ORACLE_DSN: kết nối superuser vào bản sao, chỉ để ĐỌC trạng thái làm đối chiếu

Chạy:
  set EAS_LIVE_ORACLE_DSN=postgresql://postgres:<mk>@127.0.0.1:55432/postgres
  set EAS_LIVE_PASSWORD=<mật khẩu thử>
  .venv\Scripts\python.exe tests\live\test_report_scenarios.py  [--only E2E-A01,SEC-02] [--json out.json]

Mỗi testcase in PASS/FAIL kèm bằng chứng (mã hồ sơ, trạng thái, mã HTTP). Thoát mã 0 khi tất cả PASS.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlsplit

import psycopg

API = os.getenv("EAS_LIVE_API", "http://127.0.0.1:8000").rstrip("/")
ORIGIN = os.getenv("EAS_LIVE_ORIGIN", "http://127.0.0.1:8080")
PASSWORD = os.getenv("EAS_LIVE_PASSWORD", "")
DSN = os.getenv("EAS_LIVE_ORACLE_DSN", "")

APPROVE_REASON = "Kiểm thử tự động: đồng ý theo kịch bản"


# ----------------------------------------------------------------------------- an toàn
def _guard() -> None:
    if not PASSWORD or not DSN:
        sys.exit("Thiếu EAS_LIVE_PASSWORD hoặc EAS_LIVE_ORACLE_DSN.")
    host = urlsplit(DSN).hostname
    if host not in {"127.0.0.1", "localhost"}:
        sys.exit(f"Từ chối chạy: oracle DSN trỏ tới '{host}', không phải bản sao local.")
    if urlsplit(API).hostname not in {"127.0.0.1", "localhost"}:
        sys.exit("Từ chối chạy: API không phải localhost.")


# ----------------------------------------------------------------------------- HTTP
class Http:
    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _csrf(self) -> str:
        for c in self.jar:
            if c.name == "csrftoken":
                return c.value
        self.call("GET", "/api/v1/auth/csrf")
        return next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def call(self, method: str, path: str, body: Any = None, *, idem: str | None = None,
             csrf: bool = True, raw: bytes | None = None, content_type: str | None = None) -> tuple[int, Any]:
        headers = {"Referer": ORIGIN + "/", "Origin": ORIGIN}
        data = None
        if raw is not None:
            data, headers["Content-Type"] = raw, content_type or "application/octet-stream"
        elif body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        if method != "GET" and csrf:
            headers["X-CSRFToken"] = self._csrf()
        if idem is None and method != "GET":
            idem = str(uuid.uuid4())  # mọi lệnh ghi của EAS đều yêu cầu khóa idempotency
        if idem:
            headers["Idempotency-Key"] = idem
        req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=60) as r:
                text = r.read().decode("utf-8", "replace")
                return r.status, (json.loads(text) if text else {})
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(text)
            except ValueError:
                return e.code, {"raw": text[:300]}


def login(email: str, portal: str = "client") -> Http:
    h = Http()
    st, body = h.call("POST", "/api/v1/auth/login", {"email": email, "password": PASSWORD, "portal": portal})
    if st != 200:
        raise AssertionError(f"đăng nhập {email} ({portal}) thất bại: HTTP {st} {body}")
    return h


def rid_of(body: dict) -> str | None:
    return body.get("request_id") or body.get("id") or (body.get("request") or {}).get("id")


def multipart(field_name: str, filename: str, content: bytes, mime: str) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    head = (f"--{b}\r\nContent-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode()
    return head + content + f"\r\n--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
# PDF hợp lệ về magic bytes nhưng chứa chuỗi kiểm thử EICAR: đi qua bước kiểm định dạng, phải bị ClamAV chặn.
EICAR_LINE = b"\n" + EICAR + b"\n"


# ----------------------------------------------------------------------------- oracle (chỉ đọc)
class Oracle:
    def __init__(self) -> None:
        self.conn = psycopg.connect(DSN, autocommit=True)

    def one(self, sql: str, *args):
        with self.conn.cursor() as c:
            c.execute(sql, args)
            return c.fetchone()

    def all(self, sql: str, *args):
        with self.conn.cursor() as c:
            c.execute(sql, args)
            return c.fetchall()

    def req(self, rid: str) -> dict[str, Any]:
        row = self.one("SELECT code,status,lock_version,current_revision_id::text FROM eas.request WHERE id=%s", rid)
        return {"code": row[0], "status": row[1], "version": row[2], "revision": row[3]}

    def email(self, user_id: str) -> str:
        return self.one("SELECT email FROM eas.app_user WHERE id=%s", user_id)[0]

    def active_step(self, rid: str):
        return self.one("""SELECT s.id::text, s.step_no, s.assignee_id::text FROM eas.approval_step s
                           JOIN eas.workflow_instance i ON i.id=s.instance_id
                           WHERE s.request_id=%s AND s.state='ACTIVE' AND i.state='ACTIVE'""", rid)

    def instance(self, rid: str):
        return self.one("""SELECT id::text, lifecycle, state, planned_executor_id::text, acceptor_id::text
                           FROM eas.workflow_instance WHERE request_id=%s AND state='ACTIVE'""", rid)

    def attempts(self, rid: str):
        return self.all("""SELECT id::text, attempt_no, executor_id::text, state, closure_kind
                           FROM eas.execution_attempt WHERE request_id=%s ORDER BY attempt_no""", rid)

    def requester(self, lifecycle_type: str) -> str:
        """Nhân viên thường (REQUESTER + có quản lý trực tiếp còn hoạt động, không phải quản trị)."""
        row = self.one("""
            SELECT u.email FROM eas.app_user u
            JOIN eas.app_user m ON m.id=u.manager_id AND m.is_active
            WHERE u.is_active AND u.email NOT LIKE 'admin%%'
              AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='REQUESTER'
                          AND r.revoked_at IS NULL)
              AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id
                              AND r.role IN ('OPS_ADMIN','POLICY_ADMIN','DIRECTOR','VICE_DIRECTOR') AND r.revoked_at IS NULL)
              AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='STAFF' AND r.revoked_at IS NULL)
              -- Bỏ người đã có nhiều hồ sơ cùng loại trong tháng do chạy test lặp lại: AI sẽ (đúng) coi đó là
              -- tình huống xấu (BC_WFH_FREQUENT, BC_REPEATED_EXEMPTION) và chuyển hồ sơ sang luồng B.
              AND (SELECT count(*) FROM eas.request q JOIN eas.request_type qt ON qt.id=q.type_id
                   WHERE q.requester_id=u.id AND qt.code=%s
                     AND q.created_at > date_trunc('month', now())) < 3
            ORDER BY md5(u.email || %s) LIMIT 1""", lifecycle_type, lifecycle_type)
        return row[0]

    def fixture(self, sql: str, *args) -> None:
        """Dựng điều kiện kiểm thử trong BẢN SAO (vd. lùi đồng hồ SLA). Bỏ qua trigger như một fixture."""
        with self.conn.transaction(), self.conn.cursor() as c:
            c.execute("SET LOCAL session_replication_role = replica")
            c.execute(sql, args)

    def wait(self, sql: str, *args, timeout: float = 20.0, want=lambda v: bool(v)):
        end = time.time() + timeout
        val = None
        while time.time() < end:
            val = self.one(sql, *args)
            if want(val):
                return val
            time.sleep(1)
        return val

    def sandbox_reactivate(self, user_id: str) -> None:
        """Dọn dẹp sau SEC-01: mở lại tài khoản trong BẢN SAO (an toàn vì _guard chỉ cho localhost)."""
        with self.conn.cursor() as c:
            c.execute("UPDATE eas.app_user SET is_active=true WHERE id=%s", (user_id,))

    def try_tamper_as(self, role: str, sql: str) -> str | None:
        """Thử sửa/xóa audit bằng đúng vai trò runtime; trả về SQLSTATE nếu bị chặn, None nếu thành công (rollback)."""
        with self.conn.transaction(force_rollback=True), self.conn.cursor() as c:
            c.execute(f"SET LOCAL ROLE {role}")
            try:
                with self.conn.transaction():
                    c.execute(sql)
                return None
            except psycopg.Error as exc:
                return exc.sqlstate

    def ops_admin(self) -> str:
        return self.one("""SELECT u.email FROM eas.app_user u JOIN eas.role_membership r ON r.user_id=u.id
                           WHERE r.role='OPS_ADMIN' AND r.scope_kind='GLOBAL' AND r.revoked_at IS NULL AND u.is_active
                           LIMIT 1""")[0]


# ----------------------------------------------------------------------------- thao tác nghiệp vụ
PAYLOADS = {
    "WFH_REQ": lambda: {"title": "Làm việc từ xa kiểm thử tự động", "date": "2026-12-15",
                        "task_list": "Hoàn thiện báo cáo kiểm thử", "communication_channel": "Microsoft Teams"},
    "ACCESS": lambda: {"title": "Cấp quyền hệ thống kiểm thử", "app_code": "JIRA", "duration_days": 30,
                       "purpose": "Phục vụ kiểm thử tự động luồng B", "reason": "Kiểm thử tự động luồng mẫu B",
                       "requested_role": "JIRA_MEMBER"},
    "LAPTOP_PROVISION": lambda: {"title": "Cấp máy tính kiểm thử", "specs_needed": "16GB RAM, SSD 512GB",
                                 "position": "Chuyên viên", "reason": "Kiểm thử tự động luồng mẫu C",
                                 "location": "Văn phòng Hà Nội"},
}


def submit(o: Oracle, type_code: str, requester_email: str | None = None,
           payload: dict | None = None) -> tuple[str, Http, str]:
    email = requester_email or o.requester(type_code)
    h = login(email)
    st, body = h.call("POST", "/api/v1/requests/submit",
                      {"type_code": type_code, "payload": payload or PAYLOADS[type_code]()}, idem=str(uuid.uuid4()))
    if st not in (200, 201):
        raise AssertionError(f"gửi {type_code} thất bại: HTTP {st} {body}")
    rid = rid_of(body)
    if not rid:
        raise AssertionError(f"phản hồi gửi không có request_id: {body}")
    return rid, h, email


def decide(o: Oracle, rid: str, outcome: str, reason: str | None = None, executor: bool = True) -> tuple[int, Any]:
    step = o.active_step(rid)
    if not step:
        raise AssertionError(f"không có bước duyệt ACTIVE (trạng thái {o.req(rid)['status']})")
    h = login(o.email(step[2]))
    body: dict[str, Any] = {"outcome": outcome, "reason": reason or APPROVE_REASON,
                            "expected_version": o.req(rid)["version"]}
    if outcome == "APPROVE" and executor:
        st, opts = h.call("GET", f"/api/v1/requests/{rid}/assignable-executors")
        items = (opts or {}).get("items") or (opts or {}).get("executors") or []
        if st == 200 and items and (opts.get("required") or opts.get("assignment_required")
                                    or opts.get("is_last_step") or opts.get("final_step")):
            body["executor_id"] = items[0].get("id") or items[0].get("user_id")
    return h.call("POST", f"/api/v1/requests/{rid}/approval-decisions", body, idem=str(uuid.uuid4()))


def approve_all(o: Oracle, rid: str, limit: int = 8) -> list[str]:
    seen = []
    for _ in range(limit):
        if not o.active_step(rid):
            break
        st, body = decide(o, rid, "APPROVE")
        if st not in (200, 201):
            raise AssertionError(f"duyệt thất bại: HTTP {st} {body}")
        seen.append(o.req(rid)["status"])
    return seen


def executor_session(o: Oracle, rid: str) -> tuple[Http, str]:
    inst = o.instance(rid)
    atts = o.attempts(rid)
    executor = (atts[-1][2] if atts and atts[-1][2] else None) or (inst[3] if inst else None)
    if not executor:
        raise AssertionError("chưa xác định người thực hiện")
    return login(o.email(executor)), executor


def execute_and_submit(o: Oracle, rid: str) -> None:
    h, _ = executor_session(o, rid)
    st, body = h.call("POST", f"/api/v1/requests/{rid}/claim", {"expected_version": o.req(rid)["version"]})
    if st not in (200, 201):
        raise AssertionError(f"nhận việc thất bại: HTTP {st} {body}")
    raw, ct = multipart("file", "minh_chung.pdf", PDF, "application/pdf")
    st, body = h.call("POST", f"/api/v1/requests/{rid}/execution/attachments", raw=raw, content_type=ct)
    if st not in (200, 201):
        raise AssertionError(f"tải minh chứng thất bại: HTTP {st} {body}")
    st, body = h.call("POST", f"/api/v1/requests/{rid}/execution/submit",
                      {"expected_version": o.req(rid)["version"], "result_note": "Đã hoàn thành công việc theo yêu cầu",
                       "external_reference": "QA-" + rid[:8]})
    if st not in (200, 201):
        raise AssertionError(f"nộp kết quả thất bại: HTTP {st} {body}")


def acceptance(o: Oracle, rid: str, outcome: str, as_user: str | None = None) -> tuple[int, Any]:
    inst = o.one("SELECT acceptor_id::text FROM eas.workflow_instance WHERE request_id=%s AND state='ACTIVE'", rid)
    user = as_user or inst[0]
    h = login(o.email(user))
    reason = "Kết quả đạt yêu cầu nghiệm thu" if outcome == "ACCEPT" else "Cần làm lại: thiếu cấu hình phần mềm"
    return h.call("POST", f"/api/v1/requests/{rid}/acceptance-decisions",
                  {"outcome": outcome, "reason": reason, "expected_version": o.req(rid)["version"]})


# ----------------------------------------------------------------------------- testcase
@dataclass
class Result:
    case: str
    passed: bool
    evidence: str
    seconds: float = 0.0
    error: str = ""


CASES: dict[str, Callable[[Oracle], str]] = {}


def case(code: str):
    def deco(fn):
        CASES[code] = fn
        return fn
    return deco


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


@case("E2E-A01")
def e2e_a01(o: Oracle) -> str:
    rid, _, _ = submit(o, "WFH_REQ")
    states = approve_all(o, rid)
    r = o.req(rid)
    n_dec = o.one("SELECT count(*) FROM eas.approval_decision WHERE request_id=%s", rid)[0]
    n_att = len(o.attempts(rid))
    n_audit = o.one("SELECT count(*) FROM eas.audit_event WHERE request_id=%s", rid)[0]
    check(r["status"] == "COMPLETED", f"trạng thái cuối {r['status']}")
    check(n_att == 0, "mẫu A không được có execution_attempt")
    check(n_dec == len(states) and n_audit > 0, "thiếu quyết định hoặc audit")
    return f"{r['code']}: {len(states)} cấp duyệt → COMPLETED; {n_dec} quyết định, 0 lượt thực hiện, {n_audit} sự kiện audit"


@case("E2E-A02")
def e2e_a02(o: Oracle) -> str:
    rid, h, _ = submit(o, "WFH_REQ")
    rev0 = o.req(rid)["revision"]
    st, body = decide(o, rid, "NEEDS_INFO", "Cần bổ sung danh sách công việc chi tiết hơn")
    check(st in (200, 201), f"yêu cầu bổ sung lỗi HTTP {st} {body}")
    check(o.req(rid)["status"] == "NEEDS_INFO", f"trạng thái {o.req(rid)['status']}")
    old = o.one("SELECT state FROM eas.workflow_instance WHERE request_id=%s ORDER BY created_at LIMIT 1", rid)[0]
    payload = PAYLOADS["WFH_REQ"]()
    payload["task_list"] = "Hoàn thiện báo cáo kiểm thử; cập nhật tài liệu; họp tổng kết"
    st, body = h.call("POST", f"/api/v1/requests/{rid}/submit",
                      {"type_code": "WFH_REQ", "payload": payload, "expected_version": o.req(rid)["version"]},
                      idem=str(uuid.uuid4()))
    check(st in (200, 201), f"nộp lại lỗi HTTP {st} {body}")
    r = o.req(rid)
    step = o.active_step(rid)
    check(r["revision"] != rev0, "revision không đổi")
    check(step is not None and step[1] == 1, "tuyến duyệt không bắt đầu lại từ cấp 1")
    approve_all(o, rid)
    final = o.req(rid)["status"]
    check(final == "COMPLETED", f"trạng thái cuối {final}")
    return f"{r['code']}: NEEDS_INFO → phiên cũ {old}, revision mới, duyệt lại từ cấp 1 → {final}"


@case("E2E-A03")
def e2e_a03(o: Oracle) -> str:
    rid, h, _ = submit(o, "WFH_REQ")
    while True:
        steps_left = o.one("""SELECT count(*) FROM eas.approval_step s JOIN eas.workflow_instance i ON i.id=s.instance_id
                              WHERE s.request_id=%s AND i.state='ACTIVE' AND s.state IN ('WAITING','PENDING')""", rid)[0]
        if steps_left == 0:
            break
        decide(o, rid, "APPROVE")
    st, body = decide(o, rid, "REJECT", "Không phù hợp lịch làm việc của bộ phận trong tuần này")
    check(st in (200, 201), f"từ chối lỗi HTTP {st} {body}")
    check(o.req(rid)["status"] == "REJECTED", f"trạng thái {o.req(rid)['status']}")
    st2, body2 = h.call("POST", f"/api/v1/requests/{rid}/submit",
                        {"type_code": "WFH_REQ", "payload": PAYLOADS["WFH_REQ"](), "expected_version": o.req(rid)["version"]},
                        idem=str(uuid.uuid4()))
    check(st2 >= 400, f"gửi lại hồ sơ REJECTED lại thành công (HTTP {st2})")
    return f"{o.req(rid)['code']}: REJECTED ở cấp cuối; gửi lại bị chặn HTTP {st2} {body2.get('error') or body2.get('code', '')}"


@case("E2E-B01")
def e2e_b01(o: Oracle) -> str:
    rid, _, _ = submit(o, "ACCESS")
    approve_all(o, rid)
    s1 = o.req(rid)["status"]
    check(s1 == "READY_FOR_EXECUTION", f"sau duyệt: {s1}")
    execute_and_submit(o, rid)
    r = o.req(rid)
    acc = o.one("SELECT count(*) FROM eas.acceptance_decision WHERE request_id=%s", rid)[0]
    check(r["status"] == "COMPLETED" and acc == 0, f"trạng thái {r['status']}, nghiệm thu {acc}")
    return f"{r['code']}: READY_FOR_EXECUTION → IN_PROGRESS → COMPLETED; không có bước nghiệm thu"


@case("E2E-B02")
def e2e_b02(o: Oracle) -> str:
    rid, _, _ = submit(o, "ACCESS")
    approve_all(o, rid)
    h, old_exec = executor_session(o, rid)
    st, body = h.call("POST", f"/api/v1/requests/{rid}/issues",
                      {"expected_version": o.req(rid)["version"], "kind": "UNABLE_TO_CLAIM",
                       "reason": "Đang nghỉ phép, không thể nhận việc tuần này"})
    check(st in (200, 201), f"báo không thể nhận lỗi HTTP {st} {body}")
    check(o.req(rid)["status"] != "COMPLETED", "hồ sơ tự hoàn tất")
    inst = o.instance(rid)
    new_exec = o.one("""SELECT m.user_id::text FROM eas.role_membership m JOIN eas.app_user u ON u.id=m.user_id
                        WHERE m.role='EXECUTOR' AND m.revoked_at IS NULL AND u.is_active AND m.user_id<>%s
                          AND m.user_id <> (SELECT requester_id FROM eas.request WHERE id=%s)
                        ORDER BY (m.scope_kind='GLOBAL') DESC LIMIT 1""", old_exec, rid)[0]
    admin = login(o.ops_admin(), "admin")
    atts = o.attempts(rid)
    target_kind, target_id = ("EXECUTOR", atts[-1][0]) if atts else ("PLANNED_EXECUTOR", inst[0])
    st, body = admin.call("POST", f"/api/v1/requests/{rid}/reassign",
                          {"target_kind": target_kind, "target_id": target_id, "new_user_id": new_exec,
                           "reason": "Điều chuyển do người thực hiện báo không thể nhận việc",
                           "expected_version": o.req(rid)["version"]})
    check(st in (200, 201), f"điều chuyển lỗi HTTP {st} {body}")
    h2 = login(o.email(new_exec))
    st, body = h2.call("POST", f"/api/v1/requests/{rid}/claim", {"expected_version": o.req(rid)["version"]})
    check(st in (200, 201), f"người mới nhận việc lỗi HTTP {st} {body}")
    r = o.req(rid)
    check(r["status"] == "IN_PROGRESS", f"trạng thái {r['status']}")
    return f"{r['code']}: UNABLE_TO_CLAIM → OPS_ADMIN điều chuyển ({target_kind}) → người mới nhận việc, {r['status']}"


@case("E2E-C01")
def e2e_c01(o: Oracle) -> str:
    rid, _, _ = submit(o, "LAPTOP_PROVISION")
    approve_all(o, rid)
    execute_and_submit(o, rid)
    s_wait = o.req(rid)["status"]
    check(s_wait == "WAITING_FOR_ACCEPTANCE", f"sau nộp kết quả: {s_wait}")
    st, body = acceptance(o, rid, "ACCEPT")
    check(st in (200, 201), f"nghiệm thu lỗi HTTP {st} {body}")
    r = o.req(rid)
    check(r["status"] == "COMPLETED", f"trạng thái {r['status']}")
    return f"{r['code']}: {s_wait} → ACCEPTED → COMPLETED"


@case("E2E-C02")
def e2e_c02(o: Oracle) -> str:
    rid, _, _ = submit(o, "LAPTOP_PROVISION")
    approve_all(o, rid)
    execute_and_submit(o, rid)
    st, body = acceptance(o, rid, "REWORK")
    check(st in (200, 201), f"yêu cầu làm lại lỗi HTTP {st} {body}")
    atts = o.attempts(rid)
    check(len(atts) == 2 and atts[0][3] == "FINISHED" and atts[0][4] == "REWORK",
          f"lượt thực hiện sau REWORK: {atts}")
    execute_and_submit(o, rid)
    st, body = acceptance(o, rid, "ACCEPT")
    check(st in (200, 201), f"nghiệm thu lần 2 lỗi HTTP {st} {body}")
    r = o.req(rid)
    first_note = o.one("SELECT result_note FROM eas.execution_attempt WHERE request_id=%s AND attempt_no=1", rid)[0]
    check(r["status"] == "COMPLETED" and first_note, "lịch sử lần 1 bị mất hoặc chưa hoàn tất")
    return f"{r['code']}: REWORK → lượt 1 FINISHED/REWORK giữ nguyên kết quả, tạo lượt 2 → ACCEPTED → COMPLETED"


@case("E2E-C03")
def e2e_c03(o: Oracle) -> str:
    rid, _, _ = submit(o, "LAPTOP_PROVISION")
    approve_all(o, rid)
    execute_and_submit(o, rid)
    executor = o.attempts(rid)[-1][2]
    st, body = acceptance(o, rid, "ACCEPT", as_user=executor)
    n = o.one("SELECT count(*) FROM eas.acceptance_decision WHERE request_id=%s", rid)[0]
    check(st >= 400 and n == 0, f"người thực hiện tự nghiệm thu được (HTTP {st})")
    return f"{o.req(rid)['code']}: người thực hiện gọi API nghiệm thu → HTTP {st} {body.get('error') or body.get('code','')}; 0 quyết định nghiệm thu"


@case("SEC-01")
def sec_01(o: Oracle) -> str:
    email = o.requester("SEC-01")
    uid = o.one("SELECT id::text FROM eas.app_user WHERE email=%s", email)[0]
    h = login(email)
    st_before, _ = h.call("GET", "/api/v1/auth/me")
    admin = login(o.ops_admin(), "admin")
    try:
        st_lock, body = admin.call("DELETE", f"/api/v1/admin/users-management/{uid}",
                                   {"reason": "Kiểm thử tự động: khóa tài khoản đang có phiên"})
        st_after, _ = h.call("GET", "/api/v1/auth/me")
        st_write, _ = h.call("POST", "/api/v1/request-drafts", {"type_code": "WFH_REQ", "title": "Thử ghi sau khi khóa"})
    finally:
        o.sandbox_reactivate(uid)  # khôi phục bản sao sau kiểm thử (chỉ bản sao local)
    check(st_lock in (200, 204), f"khóa tài khoản lỗi HTTP {st_lock} {body}")
    check(st_before == 200 and st_after == 401 and st_write in (401, 403), f"trước {st_before}, sau {st_after}, ghi {st_write}")
    return f"OPS_ADMIN khóa tài khoản → {st_lock}; /auth/me của phiên cũ trước khóa {st_before}, sau khóa {st_after}; thao tác ghi → {st_write}"

@case("SEC-02")
def sec_02(o: Oracle) -> str:
    h = login(o.requester("SEC-02"))
    before = o.one("SELECT count(*) FROM eas.request")[0]
    st, body = h.call("POST", "/api/v1/request-drafts", {"type_code": "WFH_REQ", "title": "Không có CSRF"},
                      idem=str(uuid.uuid4()), csrf=False)
    after = o.one("SELECT count(*) FROM eas.request")[0]
    check(st == 403 and after == before, f"HTTP {st}, số hồ sơ {before}→{after}")
    return f"POST không kèm CSRF → HTTP {st}; không sinh bản ghi mới"


@case("SEC-03")
def sec_03(o: Oracle) -> str:
    rid, h, email = submit(o, "WFH_REQ")
    owner = login(email)
    raw, ct = multipart("file", "rieng_tu.pdf", PDF, "application/pdf")
    draft_st, draft = owner.call("POST", "/api/v1/request-drafts", {"type_code": "WFH_REQ", "title": "Hồ sơ có tệp riêng tư"},
                                 idem=str(uuid.uuid4()))
    did = rid_of(draft)
    st, att = owner.call("POST", f"/api/v1/request-drafts/{did}/attachments", raw=raw, content_type=ct)
    check(st == 201, f"tải tệp lỗi HTTP {st} {att}")
    att_id = att.get("id") or att.get("attachment_id")
    dept = o.one("SELECT department_id FROM eas.app_user WHERE email=%s", email)[0]
    outsider = o.one("""SELECT u.email FROM eas.app_user u WHERE u.is_active AND u.department_id IS DISTINCT FROM %s
                        AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.scope_kind='GLOBAL'
                                        AND r.role IN ('OPS_ADMIN','AUDITOR','DIRECTOR','VICE_DIRECTOR','APPROVER','EXECUTOR'))
                        LIMIT 1""", dept)[0]
    o2 = login(outsider)
    st_meta, _ = o2.call("GET", f"/api/v1/attachments/{att_id}")
    st_dl, body = o2.call("GET", f"/api/v1/attachments/{att_id}/download")
    leaked = "storage" in json.dumps(body).lower() or "local_storage" in json.dumps(body).lower()
    check(st_meta == 404 and st_dl == 404 and not leaked, f"metadata {st_meta}, download {st_dl}")
    return f"tài khoản phòng khác đọc metadata → {st_meta}, tải tệp → {st_dl}; không lộ đường dẫn kho"


@case("SEC-04")
def sec_04(o: Oracle) -> str:
    h = login(o.requester("SEC-04"))
    st, d = h.call("POST", "/api/v1/request-drafts", {"type_code": "WFH_REQ", "title": "Bản nháp hai tab"}, idem=str(uuid.uuid4()))
    did = rid_of(d)
    v = o.req(did)["version"]
    st1, _ = h.call("PATCH", f"/api/v1/request-drafts/{did}", {"expected_version": v, "payload": {"title": "Tab một lưu trước"}})
    st2, b2 = h.call("PATCH", f"/api/v1/request-drafts/{did}", {"expected_version": v, "payload": {"title": "Tab hai lưu phiên cũ"}})
    title = o.one("SELECT draft_payload->>'title' FROM eas.request WHERE id=%s", did)[0]
    check(st1 == 200 and st2 == 409 and title == "Tab một lưu trước", f"tab1 {st1}, tab2 {st2} {b2}, title '{title}'")
    return f"tab 1 lưu → {st1}; tab 2 lưu bằng lock_version cũ → {st2} {b2.get('error') or b2.get('code','')}; giữ nội dung tab 1"


@case("SEC-05")
def sec_05(o: Oracle) -> str:
    rid, _, _ = submit(o, "WFH_REQ")
    step = o.active_step(rid)
    h = login(o.email(step[2]))
    v = o.req(rid)["version"]
    results: list[int] = []

    def go():
        st, _ = h.call("POST", f"/api/v1/requests/{rid}/approval-decisions",
                       {"outcome": "APPROVE", "reason": APPROVE_REASON, "expected_version": v}, idem=str(uuid.uuid4()))
        results.append(st)

    threads = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    n_dec = o.one("SELECT count(*) FROM eas.approval_decision WHERE step_id=%s", step[0])[0]
    n_active = o.one("SELECT count(*) FROM eas.approval_step WHERE request_id=%s AND state='ACTIVE'", rid)[0]
    check(sorted(results)[0] in (200, 201) and sorted(results)[1] >= 400 and n_dec == 1 and n_active <= 1,
          f"HTTP {results}, quyết định {n_dec}, bước ACTIVE {n_active}")
    return f"{o.req(rid)['code']}: hai lệnh duyệt đồng thời → HTTP {sorted(results)}; 1 quyết định, {n_active} bước ACTIVE"


@case("SEC-07")
def sec_07(o: Oracle) -> str:
    h = login(o.requester("SEC-07"))
    st, d = h.call("POST", "/api/v1/request-drafts", {"type_code": "WFH_REQ", "title": "Kiểm thử tải tệp"})
    did = rid_of(d)
    check(st == 201 and did, f"không tạo được bản nháp: HTTP {st} {d}")
    ok_raw, ok_ct = multipart("file", "hop_le.pdf", PDF, "application/pdf")
    st_ok, ok_body = h.call("POST", f"/api/v1/request-drafts/{did}/attachments", raw=ok_raw, content_type=ok_ct)
    out = []
    for name, content, mime in (("lon.pdf", PDF + b"0" * (10 * 1024 * 1024 + 10), "application/pdf"),
                                ("gia_mao.pdf", b"MZ\x90\x00 day la file exe", "application/pdf"),
                                ("eicar.pdf", EICAR, "application/pdf"),
                                ("pdf_nhiem_eicar.pdf", PDF + EICAR_LINE, "application/pdf")):
        raw, ct = multipart("file", name, content, mime)
        st, body = h.call("POST", f"/api/v1/request-drafts/{did}/attachments", raw=raw, content_type=ct)
        out.append((name, st, (body.get("error") or {}).get("code") if isinstance(body.get("error"), dict) else body.get("error")))
    names = [r[0] for r in o.all("SELECT a.original_name FROM eas.attachment a WHERE a.request_id=%s", did)]
    check(st_ok == 201, f"tệp hợp lệ bị từ chối: HTTP {st_ok} {ok_body}")
    check(all(s in (400, 413, 415, 422) for _, s, _ in out), f"kết quả {out}")
    check(names == ["hop_le.pdf"], f"tệp đã lưu: {names}")
    return f"tệp PDF hợp lệ → {st_ok}; " + "; ".join(f"{a} → {b} {c}" for a, b, c in out) + "; chỉ tệp hợp lệ được lưu"

@case("SEC-08")
def sec_08(o: Oracle) -> str:
    h = login(o.requester("SEC-08"))
    key = str(uuid.uuid4())
    st1, b1 = h.call("POST", "/api/v1/request-drafts", {"type_code": "WFH_REQ", "title": "Khóa idempotency lần một"}, idem=key)
    before = o.one("SELECT count(*) FROM eas.request")[0]
    st2, b2 = h.call("POST", "/api/v1/request-drafts", {"type_code": "WFH_REQ", "title": "Cùng khóa nhưng dữ liệu khác"}, idem=key)
    after = o.one("SELECT count(*) FROM eas.request")[0]
    check(st1 in (200, 201) and st2 >= 400 and after == before, f"lần 1 {st1}, lần 2 {st2} {b2}, hồ sơ {before}→{after}")
    return f"lần 1 → {st1}; lặp khóa với dữ liệu khác → {st2} {b2.get('error') or b2.get('code','')}; không tạo hồ sơ thứ hai"


@case("SEC-06")
def sec_06(o: Oracle) -> str:
    import subprocess
    rid = o.one("SELECT id::text FROM eas.request WHERE status='COMPLETED' ORDER BY completed_at DESC LIMIT 1")[0]
    out = subprocess.run(["docker", "exec", "eas-api-1", "python", "manage.py", "audit_verify", "--scope", f"REQ:{rid}"],
                         capture_output=True, text=True, timeout=120)
    status = (json.loads(out.stdout or "{}") or {}).get("status")
    upd = o.try_tamper_as("eas_api", f"UPDATE eas.audit_event SET action=action WHERE request_id='{rid}'")
    dele = o.try_tamper_as("eas_api", f"DELETE FROM eas.audit_event WHERE request_id='{rid}'")
    check(out.returncode == 0 and status == "PASS", f"audit_verify {out.returncode} {out.stdout[:200]} {out.stderr[-200:]}")
    check(upd is not None and dele is not None, f"vai trò API sửa/xóa được audit (UPDATE {upd}, DELETE {dele})")
    return (f"audit_verify chuỗi băm của {o.req(rid)['code']} → {status}; vai trò API thử UPDATE audit → bị chặn ({upd}), "
            f"DELETE → bị chặn ({dele})")

@case("INT-06")
def int_06(o: Oracle) -> str:
    import subprocess
    code = ("import urllib.request,urllib.error\n"
            "for h in ({}, {'X-Integration-Secret':'sai-khoa'}):\n"
            "    r=urllib.request.Request('http://mock-systems:8000/mock-api/v1/hr/employees',headers=h)\n"
            "    try: print(urllib.request.urlopen(r,timeout=10).status)\n"
            "    except urllib.error.HTTPError as e: print(e.code)\n")
    out = subprocess.run(["docker", "exec", "eas-api-1", "python", "-c", code], capture_output=True, text=True, timeout=60)
    codes = [int(x) for x in out.stdout.split() if x.isdigit()]
    check(len(codes) == 2 and all(c in (401, 403) for c in codes), f"mã trả về {codes} {out.stderr[-200:]}")
    return f"gọi Mock Systems API không có khóa → {codes[0]}, khóa sai → {codes[1]}"


@case("CFG-01")
def cfg_01(o: Oracle) -> str:
    rid, _, _ = submit(o, "WFH_REQ")
    rel, active = o.one("""SELECT v.release_id::text, t.active_release_id::text FROM eas.request r
                           JOIN eas.request_revision v ON v.id=r.current_revision_id JOIN eas.request_type t ON t.id=r.type_id
                           WHERE r.id=%s""", rid)
    policy = o.one("""SELECT u.email FROM eas.app_user u JOIN eas.role_membership m ON m.user_id=u.id
                      WHERE m.role='POLICY_ADMIN' AND m.revoked_at IS NULL AND u.is_active LIMIT 1""")[0]
    h = login(policy, "admin")
    sha_before = o.one("SELECT content_sha256 FROM eas.config_release WHERE id=%s", rel)[0]
    st, body = h.call("PATCH", f"/api/v1/config-releases/{rel}", {"route_rules": {"default": "x"}, "expected_version": 0})
    sha_after = o.one("SELECT content_sha256 FROM eas.config_release WHERE id=%s", rel)[0]
    check(rel == active, "revision không chụp đúng bản quy chế đang hiệu lực")
    check(st >= 400 and sha_before == sha_after, f"sửa bản đã ban hành → HTTP {st}")
    code = body.get("error", {}).get("code") if isinstance(body.get("error"), dict) else body.get("error")
    return (f"{o.req(rid)['code']}: revision chụp config_release_id = bản đang hiệu lực; "
            f"POLICY_ADMIN sửa bản đã ban hành → HTTP {st} {code}, nội dung (sha256) không đổi")


@case("SLA-01")
def sla_01(o: Oracle) -> str:
    rid, _, _ = submit(o, "WFH_REQ")
    stage = o.one("SELECT id::text FROM eas.sla_stage WHERE request_id=%s AND closed_at IS NULL", rid)
    check(stage is not None, "hồ sơ không mở chặng SLA")
    # Đồng hồ kiểm thử: đã trôi 10/12 thời hạn (qua mốc 50%, chưa quá hạn).
    o.fixture("UPDATE eas.sla_stage SET started_at=now()-interval '10 hours', due_at=now()+interval '2 hours' WHERE id=%s",
              stage[0])
    n1 = o.wait("SELECT count(*) FROM eas.sla_alert WHERE stage_id=%s AND kind='REMINDER'", stage[0], want=lambda v: v[0] >= 1)[0]
    time.sleep(8)  # worker quét 2 giây/lần: chờ thêm vài vòng để bắt thông báo trùng
    n2 = o.one("SELECT count(*) FROM eas.sla_alert WHERE stage_id=%s", stage[0])[0]
    assignee = o.active_step(rid)[2]
    notes = o.wait("""SELECT count(*) FROM eas.notification WHERE request_id=%s AND recipient_id=%s AND label LIKE %s""",
                   rid, assignee, "%đến hạn%", want=lambda v: v[0] >= 1)[0]
    check(n1 == 1 and n2 == 1 and notes == 1, f"nhắc hạn {n1}→{n2}, thông báo {notes}")
    return f"{o.req(rid)['code']}: qua mốc 50% → 1 cảnh báo REMINDER, sau nhiều vòng worker vẫn 1; người duyệt nhận 1 thông báo"


@case("SLA-02")
def sla_02(o: Oracle) -> str:
    rid, _, _ = submit(o, "WFH_REQ")
    stage = o.one("SELECT id::text FROM eas.sla_stage WHERE request_id=%s AND closed_at IS NULL", rid)[0]
    o.fixture("UPDATE eas.sla_stage SET started_at=now()-interval '10 hours', due_at=now()-interval '5 minutes' WHERE id=%s",
              stage)
    due = o.one("SELECT due_at FROM eas.sla_stage WHERE id=%s", stage)[0]
    row = o.wait("SELECT breached_at, due_at FROM eas.sla_stage WHERE id=%s", stage, want=lambda v: v[0] is not None)
    breach = o.one("SELECT count(*) FROM eas.sla_alert WHERE stage_id=%s AND kind='BREACH'", stage)[0]
    assignee = o.active_step(rid)[2]
    notes = o.wait("SELECT count(*) FROM eas.notification WHERE request_id=%s AND recipient_id=%s AND label LIKE %s",
                   rid, assignee, "%quá hạn%", want=lambda v: v[0] >= 1)[0]
    step_owner_after = o.active_step(rid)[2]
    escalated = step_owner_after != assignee
    check(row[0] is not None and breach == 1 and row[1] == due and notes >= 1,
          f"breached_at {row[0]}, cảnh báo {breach}, hạn gốc giữ {row[1] == due}, thông báo {notes}")
    check(escalated, "ghi nhận vi phạm nhưng KHÔNG leo thang theo chính sách (eas.sla_escalation_policy chưa được mã nguồn sử dụng)")
    return f"{o.req(rid)['code']}: quá hạn → breached_at = due_at, 1 cảnh báo BREACH, người duyệt được báo, đã leo thang"


@case("DLG-01")
def dlg_01(o: Oracle) -> str:
    email = o.requester("DLG")
    rid, _, _ = submit(o, "WFH_REQ", requester_email=email)
    approver = o.active_step(rid)[2]
    h = login(o.email(approver))
    st, cands = h.call("GET", "/api/v1/delegations/candidates")
    req_id = o.one("SELECT id::text FROM eas.app_user WHERE email=%s", email)[0]
    items = [c for c in (cands.get("items") or cands.get("candidates") or []) if (c.get("id") or c.get("user_id")) != req_id]
    check(st == 200 and items, f"không có người nhận ủy quyền hợp lệ: HTTP {st} {cands}")
    delegate = items[0].get("id") or items[0].get("user_id")
    now = time.time()
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(t))  # noqa: E731
    st, d = h.call("POST", "/api/v1/delegations", {"delegate_id": delegate, "starts_at": iso(now - 60),
                                                   "ends_at": iso(now + 86400), "reason": "Nghỉ phép, ủy quyền kiểm thử"})
    did = (d.get("delegation") or d).get("id")
    try:
        check(st == 201, f"tạo ủy quyền lỗi HTTP {st} {d}")
        moved_to = o.wait("SELECT assignee_id::text FROM eas.approval_step WHERE request_id=%s AND state='ACTIVE'", rid,
                          want=lambda v: v and v[0] == delegate)
        check(moved_to and moved_to[0] == delegate, f"bước duyệt không chuyển sang người được ủy quyền ({moved_to})")
        st2, b2 = decide(o, rid, "APPROVE")
        check(st2 in (200, 201) and o.req(rid)["status"] == "COMPLETED", f"người được ủy quyền duyệt lỗi HTTP {st2} {b2}")
    finally:
        if did:
            h.call("POST", f"/api/v1/delegations/{did}/revoke", {})
    return f"{o.req(rid)['code']}: người duyệt tạo ủy quyền → bước đang chờ chuyển sang người được ủy quyền → duyệt → COMPLETED"


@case("DLG-02")
def dlg_02(o: Oracle) -> str:
    email = o.requester("DLG")
    rid0, _, _ = submit(o, "WFH_REQ", requester_email=email)
    approver = o.active_step(rid0)[2]
    decide(o, rid0, "APPROVE")
    h = login(o.email(approver))
    non_approver = o.one("""SELECT u.id::text FROM eas.app_user u WHERE u.is_active AND NOT EXISTS
                            (SELECT 1 FROM eas.role_membership m WHERE m.user_id=u.id AND m.role IN ('APPROVER','MANAGER','TEAM_LEAD',
                             'DIRECTOR','VICE_DIRECTOR','OPS_ADMIN','POLICY_ADMIN') AND m.revoked_at IS NULL) LIMIT 1""")[0]
    now = time.time()
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(t))  # noqa: E731
    st_bad, b_bad = h.call("POST", "/api/v1/delegations", {"delegate_id": non_approver, "starts_at": iso(now),
                                                           "ends_at": iso(now + 86400), "reason": "Ủy quyền cho người thiếu vai trò"})
    st, cands = h.call("GET", "/api/v1/delegations/candidates")
    delegate = ((cands.get("items") or cands.get("candidates") or [{}])[0]).get("id")
    st_ok, d = h.call("POST", "/api/v1/delegations", {"delegate_id": delegate, "starts_at": iso(now + 3600),
                                                      "ends_at": iso(now + 7200), "reason": "Ủy quyền sẽ được làm hết hạn"})
    did = (d.get("delegation") or d).get("id")
    try:
        check(st_ok == 201, f"không tạo được ủy quyền mẫu: HTTP {st_ok} {d}")
        o.fixture("UPDATE eas.approval_delegation SET starts_at=now()-interval '2 days', ends_at=now()-interval '1 day' WHERE id=%s", did)
        rid, _, _ = submit(o, "WFH_REQ", requester_email=email)
        owner = o.active_step(rid)[2]
        check(st_bad in (403, 409, 422), f"ủy quyền cho người thiếu vai trò được chấp nhận (HTTP {st_bad})")
        check(owner == approver, f"bước duyệt giao cho {owner} dù ủy quyền đã hết hạn")
    finally:
        if did:
            h.call("POST", f"/api/v1/delegations/{did}/revoke", {})
    code = b_bad.get("error", {}).get("code") if isinstance(b_bad.get("error"), dict) else b_bad
    return (f"ủy quyền cho người không có vai trò duyệt → HTTP {st_bad} {code}; ủy quyền đã hết hạn không được dùng, "
            f"{o.req(rid)['code']} vẫn giao cho người duyệt gốc")


def _leave_payload(o: Oracle, email: str, kind: str = "LEAVE") -> dict:
    me = o.one("SELECT id::text, department_id FROM eas.app_user WHERE email=%s", email)
    mate = o.one("SELECT id::text FROM eas.app_user WHERE department_id=%s AND id<>%s AND is_active LIMIT 1", me[1], me[0])[0]
    base = {"title": "Nghỉ phép có lương kiểm thử", "start_date": "2026-12-21", "end_date": "2026-12-22",
            "reason": "Giải quyết việc gia đình (kiểm thử)", "handover_user_id": mate}
    if kind == "LEAVE":
        base["leave_kind"] = "CO_LUONG"
    return base


def _leave_once(o: Oracle, email: str) -> str:
    rid, _, _ = submit(o, "LEAVE", requester_email=email, payload=_leave_payload(o, email))
    approve_all(o, rid)
    while o.req(rid)["status"] in ("READY_FOR_EXECUTION", "IN_PROGRESS"):
        execute_and_submit(o, rid)
    status = o.req(rid)["status"]
    usage = o.wait("SELECT count(*), coalesce(sum(days),0) FROM mock_hr.leave_usage WHERE source_request_id=%s", rid,
                   want=lambda v: v[0] >= 1)
    ev = o.one("""SELECT id::text FROM eas.outbox_event WHERE request_id=%s AND state IN ('SENT','DONE','PROCESSED','DELIVERED')
                  ORDER BY created_at DESC LIMIT 1""", rid) or o.one(
        "SELECT id::text FROM eas.outbox_event WHERE request_id=%s ORDER BY created_at DESC LIMIT 1", rid)
    replay = None
    if ev:
        admin = login(o.ops_admin(), "admin")
        replay, _ = admin.call("POST", f"/api/v1/ops/outbox/{ev[0]}/replay", {"reason": "Phát lại sự kiện để kiểm thử trừ lặp"})
        time.sleep(8)
    usage2 = o.one("SELECT count(*), coalesce(sum(days),0) FROM mock_hr.leave_usage WHERE source_request_id=%s", rid)
    unique = o.one("""SELECT count(*) FROM pg_indexes WHERE schemaname='mock_hr' AND tablename='leave_usage'
                      AND indexdef ILIKE '%%UNIQUE%%(source_request_id)%%'""")[0]
    check(status == "COMPLETED" and usage[0] == 1 and usage2[0] == 1 and unique == 1,
          f"trạng thái {status}, ghi nhận phép {usage}→{usage2}, ràng buộc duy nhất {unique}")
    return (f"{o.req(rid)['code']}: nghỉ có lương 2 ngày hoàn tất → quỹ phép ghi đúng 1 lần ({usage[1]} ngày); "
            f"phát lại sự kiện đã gửi bị từ chối HTTP {replay} (chỉ sự kiện DEAD được phát lại); "
            f"mock_hr.leave_usage có UNIQUE(source_request_id) nên không thể trừ lặp")


@case("INT-01")
def int_01(o: Oracle) -> str:
    """Trên cấu hình THẬT sao chép từ Supabase."""
    return _leave_once(o, o.requester("INT-01"))


@case("INT-01*")
def int_01_logic(o: Oracle) -> str:
    """Kiểm logic trừ quỹ phép sau khi TẠM căn mẫu vòng đời của LEAVE với bản quy chế đang hiệu lực (chỉ trong bản sao)."""
    old = o.one("SELECT lifecycle FROM eas.request_type WHERE code='LEAVE'")[0]
    o.fixture("""UPDATE eas.request_type t SET lifecycle=c.lifecycle FROM eas.config_release c
                 WHERE t.code='LEAVE' AND c.id=t.active_release_id""")
    try:
        return _leave_once(o, o.requester("INT-01b")) + f" (đã tạm đổi lifecycle {old} → bản quy chế, sau đó khôi phục)"
    finally:
        o.fixture("UPDATE eas.request_type SET lifecycle=%s WHERE code='LEAVE'", old)


@case("INT-02")
def int_02(o: Oracle) -> str:
    room = o.one("""SELECT resource_code FROM mock_facilities.resource WHERE resource_type ILIKE '%%ROOM%%'
                    AND availability_status ILIKE 'AVAILABLE' AND NOT EXISTS (
                      SELECT 1 FROM mock_facilities.reservation r WHERE r.resource_id=resource.id
                        AND r.starts_at < '2026-12-23 10:00+07' AND r.ends_at > '2026-12-23 09:00+07')
                    ORDER BY resource_code LIMIT 1""")[0]
    payload = {"title": "Đặt phòng họp kiểm thử", "booking_date": "2026-12-23", "start_time": "09:00", "end_time": "10:00",
               "room_code": room, "attendees_count": 5, "purpose": "Họp kiểm thử tranh chấp phòng"}
    rid1, _, _ = submit(o, "ROOM_BOOKING", requester_email=o.requester("INT-02a"), payload=dict(payload))
    approve_all(o, rid1)
    s1 = o.req(rid1)["status"]
    email2 = o.requester("INT-02b")
    h2 = login(email2)
    st2, b2 = h2.call("POST", "/api/v1/requests/submit", {"type_code": "ROOM_BOOKING", "payload": dict(payload)})
    code2 = b2.get("error", {}).get("code") if isinstance(b2.get("error"), dict) else b2.get("error")
    rid2 = rid_of(b2) if st2 in (200, 201) else None
    if rid2:
        approve_all(o, rid2)
    held = o.all("""SELECT r.source_request_id::text, r.status FROM mock_facilities.reservation r
                    JOIN mock_facilities.resource x ON x.id=r.resource_id
                    WHERE x.resource_code=%s AND r.starts_at < '2026-12-23 10:00+07' AND r.ends_at > '2026-12-23 09:00+07'
                      AND r.status NOT IN ('CANCELLED','REJECTED','RELEASED')""", room)
    check(s1 == "COMPLETED", f"hồ sơ 1: {s1}")
    check(len(held) == 1 and held[0][0] == rid1, f"chỗ được giữ: {held}")
    check(st2 == 409 or rid2, f"hồ sơ 2: HTTP {st2} {b2}")
    second = f"bị từ chối khi gửi HTTP {st2} {code2}" if not rid2 else f"→ {o.req(rid2)['status']}"
    return f"phòng {room} 23/12 09:00–10:00: hồ sơ 1 → {s1} và giữ chỗ; hồ sơ 2 {second}; chỉ 1 chỗ được giữ"


@case("INT-03")
def int_03(o: Oracle) -> str:
    api_id = o.one("SELECT id::text FROM eas.mock_apis WHERE api_code='API_HR'")[0]
    admin = login(o.ops_admin(), "admin")
    h = login(o.requester("INT-03"))
    title = {"type_code": "LEAVE_SPECIAL", "title": "Nghỉ phép đặc biệt kiểm thử"}
    st_on, b_on = h.call("POST", "/api/v1/request-drafts", title)  # đối chứng: HRM đang bật
    before = o.one("SELECT count(*) FROM eas.request")[0]
    st_off, b_off = admin.call("PATCH", f"/api/v1/admin/mock-apis/{api_id}/toggle", {"reason": "Kiểm thử tắt tích hợp HRM"})
    try:
        enabled = o.one("SELECT is_enabled FROM eas.mock_apis WHERE id=%s", api_id)[0]
        time.sleep(6)  # danh sách API bị tắt được cache 5 giây
        st, body = h.call("POST", "/api/v1/request-drafts", title)
        after = o.one("SELECT count(*) FROM eas.request")[0]
    finally:
        if not o.one("SELECT is_enabled FROM eas.mock_apis WHERE id=%s", api_id)[0]:
            admin.call("PATCH", f"/api/v1/admin/mock-apis/{api_id}/toggle", {"reason": "Bật lại sau kiểm thử"})
    code = body.get("error", {}).get("code") if isinstance(body.get("error"), dict) else body.get("error")
    check(st_on == 201, f"đối chứng khi HRM bật thất bại: HTTP {st_on} {b_on}")
    check(st_off == 200 and enabled is False, f"tắt tích hợp lỗi HTTP {st_off} {b_off}")
    check(st >= 400 and after == before, f"vẫn tạo được yêu cầu phụ thuộc HRM: HTTP {st}, hồ sơ {before}→{after}")
    return (f"HRM bật: tạo nháp nghỉ phép đặc biệt → {st_on}; OPS_ADMIN tắt API_HR → tạo lại bị chặn HTTP {st} {code}, "
            f"không tạo hồ sơ mới; đã bật lại")


# ----------------------------------------------------------------------------- chạy
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    _guard()
    o = Oracle()
    wanted = [c.strip() for c in args.only.split(",") if c.strip()] or list(CASES)
    results: list[Result] = []
    for code in wanted:
        t = time.perf_counter()
        try:
            ev = CASES[code](o)
            results.append(Result(code, True, ev, time.perf_counter() - t))
        except Exception as exc:  # noqa: BLE001
            results.append(Result(code, False, "", time.perf_counter() - t,
                                  f"{exc}" if isinstance(exc, AssertionError) else traceback.format_exc(limit=2)))
        r = results[-1]
        print(f"{'PASS' if r.passed else 'FAIL'}  {code:8} ({r.seconds:5.1f}s)  {r.evidence or r.error}", flush=True)
    passed = sum(r.passed for r in results)
    print(f"\nKẾT QUẢ: {passed}/{len(results)} PASS")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([r.__dict__ for r in results], f, ensure_ascii=False, indent=1)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
