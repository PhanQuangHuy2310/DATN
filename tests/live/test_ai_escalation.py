r"""Kiểm thử trực tiếp: AI phát hiện tình huống xấu và chuyển CHÍNH hồ sơ A sang luồng B/C (migration 23).

Chạy trên BẢN SAO CSDL local (Supabase local), cùng biến môi trường với test_report_scenarios.py:
  set EAS_LIVE_ORACLE_DSN=postgresql://supabase_admin:postgres@127.0.0.1:55322/postgres
  set EAS_LIVE_PASSWORD=Password@123456
  .venv\Scripts\python.exe tests\live\test_ai_escalation.py [--json out.json]

ESC-01  Quản lý đang giữ bước duyệt hết hạn trong 24h xin nghỉ ngày mai, người nhận bàn giao không đủ
        thẩm quyền -> BC_DEADLINE_CONFLICT -> hồ sơ sang luồng B (quản lý cấp trên duyệt -> HR xử lý),
        có đề xuất xử lý PROPOSED; cấp trên duyệt -> READY_FOR_EXECUTION.
ESC-02  Ba đề nghị thanh toán 9,5 triệu trong 7 ngày -> hồ sơ thứ ba BC_SPLIT_AMOUNT_EVASION -> luồng C
        (có người nghiệm thu).
ESC-03  Đối chứng: đơn nghỉ khi không giữ việc đến hạn -> giữ luồng A.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_report_scenarios as t

RESULTS: list[dict] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def lifecycle_of(o: t.Oracle, rid: str):
    return o.one(
        """SELECT i.lifecycle, i.planned_executor_id::text, i.acceptor_id::text
           FROM eas.workflow_instance i JOIN eas.request r ON r.current_revision_id = i.revision_id
           WHERE r.id = %s AND i.state = 'ACTIVE'""",
        rid,
    )


def wait_escalated(o: t.Oracle, rid: str, timeout: float = 45.0):
    return o.wait(
        "SELECT details FROM eas.audit_event WHERE request_id=%s AND action='AI_ESCALATED' "
        "ORDER BY seq DESC LIMIT 1",
        rid,
        timeout=timeout,
    )


def manager_with_team(o: t.Oracle):
    """X: người duyệt có cấp dưới Y và có quản lý M; không phải quản trị."""
    return o.one(
        """
        SELECT x.id::text, x.email, y.id::text, y.email, m.id::text, m.email
        FROM eas.app_user x
        JOIN eas.app_user y ON y.manager_id = x.id AND y.is_active
        JOIN eas.app_user m ON m.id = x.manager_id AND m.is_active
        WHERE x.is_active AND x.email NOT LIKE 'admin%%' AND NOT x.is_system_account
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = x.id AND r.role = 'APPROVER'
                      AND r.revoked_at IS NULL)
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = x.id AND r.role = 'REQUESTER'
                      AND r.revoked_at IS NULL)
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = y.id AND r.role = 'REQUESTER'
                      AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id IN (x.id, y.id)
                          AND r.role IN ('OPS_ADMIN','POLICY_ADMIN','DIRECTOR','VICE_DIRECTOR')
                          AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = y.id AND r.role = 'APPROVER'
                          AND r.revoked_at IS NULL)
        ORDER BY x.email LIMIT 1
        """
    )


def expense(amount: int) -> dict:
    return {
        "title": "Thanh toán chi phí kiểm thử tự động",
        "reason": "Kiểm thử tự động tình huống xấu",
        "amount_vnd": amount,
        "invoice_number": f"KT-{uuid.uuid4().hex[:10].upper()}",
        "expense_category": "OFFICE",
        "beneficiary_account": "0123456789 - Ngân hàng kiểm thử",
    }


def leave(day: date, handover_id: str) -> dict:
    return {
        "title": "Xin nghỉ phép ngày mai",
        "reason": "Việc gia đình đột xuất, kiểm thử tự động",
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "leave_kind": "CO_LUONG",
        "handover_user_id": handover_id,
    }


def esc_01(o: t.Oracle) -> str:
    row = manager_with_team(o)
    check(
        row is not None,
        "không tìm được quản lý có cấp dưới và có cấp trên trong bản sao",
    )
    x_id, x_email, y_id, y_email, m_id, m_email = row
    # Y gửi một hồ sơ X phải duyệt (trọng số 3: AI không tự duyệt) -> X giữ việc hết hạn trong 24h.
    held, _, _ = t.submit(o, "EXPENSE_CLAIM", y_email, expense(1_200_000))
    step = o.wait(
        """SELECT s.assignee_id::text FROM eas.approval_step s JOIN eas.workflow_instance i
                     ON i.id=s.instance_id WHERE s.request_id=%s AND s.state='ACTIVE' AND i.state='ACTIVE'""",
        held,
    )
    check(
        step and step[0] == x_id,
        f"bước duyệt đầu của hồ sơ giữ việc không giao cho X: {step}",
    )
    # X xin nghỉ ngày mai, chọn Y (nhân viên, không có quyền duyệt) làm người nhận bàn giao.
    rid, _, _ = t.submit(
        o, "LEAVE", x_email, leave(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date() + timedelta(days=1), y_id)
    )
    details = wait_escalated(o, rid)
    check(details is not None, "không thấy audit AI_ESCALATED sau 45 giây")
    d = details[0]
    check(
        d["from_lifecycle"] == "A" and d["to_lifecycle"] == "B", f"luồng nâng sai: {d}"
    )
    codes = {c["code"] for c in d["causes"]}
    check(
        "BC_DEADLINE_CONFLICT" in codes,
        f"nguyên nhân thiếu BC_DEADLINE_CONFLICT: {codes}",
    )
    lc = lifecycle_of(o, rid)
    check(
        lc and lc[0] == "B" and lc[1],
        f"phiên duyệt mới không ở luồng B hoặc thiếu người xử lý: {lc}",
    )
    hr = o.email(lc[1])
    sup = o.one(
        "SELECT count(*) FROM eas.workflow_instance WHERE request_id=%s AND state='SUPERSEDED'",
        rid,
    )[0]
    check(sup == 1, "phiên duyệt A cũ không bị đóng SUPERSEDED")
    approver = o.active_step(rid)
    check(
        approver and approver[2] == m_id,
        f"người duyệt luồng B không phải cấp trên của X: {approver}",
    )
    prop = o.one(
        "SELECT state, proposal FROM eas.ai_remediation WHERE request_id=%s AND case_code='BC_DEADLINE_CONFLICT'",
        rid,
    )
    check(prop and prop[0] == "PROPOSED", f"không có đề xuất xử lý PROPOSED: {prop}")
    options = [opt["action"] for opt in prop[1]["options"]]
    # Cấp trên duyệt -> sang bộ phận chuyên môn (HR) xử lý.
    st, body = t.decide(o, rid, "APPROVE")
    check(st == 200, f"cấp trên duyệt thất bại: HTTP {st} {body}")
    status = o.req(rid)["status"]
    check(
        status == "READY_FOR_EXECUTION",
        f"sau khi duyệt hồ sơ ở {status}, không phải READY_FOR_EXECUTION",
    )
    return (
        f"{o.req(rid)['code']}: {x_email} giữ việc hết hạn <24h, bàn giao cho {y_email} (không đủ quyền) "
        f"-> AI_ESCALATED A→B ({', '.join(sorted(codes))}); duyệt bởi {m_email}; xử lý bởi {hr}; "
        f"đề xuất xử lý {options} -> READY_FOR_EXECUTION"
    )


def esc_02(o: t.Oracle) -> str:
    email = o.requester("EXPENSE_SPLIT")
    rids = []
    for _ in range(3):
        rid, _, _ = t.submit(o, "EXPENSE_CLAIM", email, expense(9_500_000))
        rids.append(rid)
        time.sleep(1)
    details = wait_escalated(o, rids[2])
    check(details is not None, "hồ sơ thứ ba không được nâng luồng sau 45 giây")
    d = details[0]
    codes = {c["code"] for c in d["causes"]}
    check(
        d["to_lifecycle"] == "C" and "BC_SPLIT_AMOUNT_EVASION" in codes,
        f"nâng luồng sai: {d}",
    )
    lc = lifecycle_of(o, rids[2])
    check(
        lc and lc[0] == "C" and lc[1] and lc[2],
        f"phiên duyệt luồng C thiếu người xử lý/nghiệm thu: {lc}",
    )
    first_two = [lifecycle_of(o, r) for r in rids[:2]]
    check(
        all(x and x[0] == "A" for x in first_two),
        f"hai hồ sơ đầu lẽ ra giữ luồng A: {first_two}",
    )
    return (
        f"{email}: 3 đề nghị 9,5 triệu; hồ sơ thứ ba {o.req(rids[2])['code']} -> A→C "
        f"(người xử lý {o.email(lc[1])}, nghiệm thu {o.email(lc[2])}); hai hồ sơ đầu giữ A"
    )


def esc_03(o: t.Oracle) -> str:
    email = o.requester("LEAVE_CONTROL")
    me = o.one(
        "SELECT id::text, manager_id::text FROM eas.app_user WHERE email=%s", email
    )
    # người nhận bàn giao: một đồng nghiệp cùng phòng
    peer = o.one(
        """SELECT u.id::text FROM eas.app_user u JOIN eas.app_user me ON me.id=%s
                    WHERE u.department_id=me.department_id AND u.id<>me.id AND u.is_active
                      AND NOT u.is_system_account LIMIT 1""",
        me[0],
    )
    rid, _, _ = t.submit(
        o, "LEAVE", email, leave(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date() + timedelta(days=20), peer[0])
    )
    time.sleep(12)
    esc = o.one(
        "SELECT count(*) FROM eas.audit_event WHERE request_id=%s AND action='AI_ESCALATED'",
        rid,
    )[0]
    check(esc == 0, "đơn nghỉ bình thường bị nâng luồng nhầm")
    lc = o.one(
        """SELECT i.lifecycle FROM eas.workflow_instance i JOIN eas.request r
                  ON r.current_revision_id=i.revision_id WHERE r.id=%s""",
        rid,
    )
    check(lc and lc[0] == "A", f"đơn nghỉ bình thường không ở luồng A: {lc}")
    return f"{o.req(rid)['code']}: không giữ việc đến hạn -> giữ luồng A, trạng thái {o.req(rid)['status']}"


CASES = {"ESC-01": esc_01, "ESC-02": esc_02, "ESC-03": esc_03}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    t._guard()
    o = t.Oracle()
    only = set(filter(None, a.only.split(",")))
    passed = 0
    for code, fn in CASES.items():
        if only and code not in only:
            continue
        start = time.time()
        try:
            evidence = fn(o)
            ok = True
        except Exception as exc:  # noqa: BLE001
            evidence = (
                str(exc) if isinstance(exc, AssertionError) else traceback.format_exc()
            )
            ok = False
        passed += ok
        RESULTS.append(
            {
                "code": code,
                "pass": ok,
                "seconds": round(time.time() - start, 1),
                "evidence": evidence,
            }
        )
        print(
            f"{'PASS' if ok else 'FAIL'}  {code}  ({time.time() - start:5.1f}s)  {evidence}",
            flush=True,
        )
    print(f"\nKẾT QUẢ: {passed}/{len(RESULTS)} PASS")
    if a.json:
        Path(a.json).write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
