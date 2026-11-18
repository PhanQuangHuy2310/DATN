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
ESC-04  Sau khi cấp trên duyệt: AI xếp hạng người nhận việc thay; quản lý xác nhận -> bước duyệt được chuyển,
        đề xuất CONFIRMED, audit "AI đề xuất - quản lý xác nhận" trên hồ sơ được chuyển.
ESC-05  Hướng lùi hạn: quản lý xác nhận -> hạn SLA lùi tới sau ngày đi làm lại, người gửi việc được báo;
        sửa hạn không qua cờ vẫn bị trigger chặn.
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


def reset_leave_balance(o: t.Oracle, email: str) -> None:
    """Chỉ trong BẢN SAO: trả lại quỹ phép năm (các lần chạy test lặp lại tiêu hết phép của cùng một người)."""
    o.fixture(
        """UPDATE mock_hr.leave_balance lb SET used_days = 0
           FROM mock_hr.employee e JOIN eas.app_user u
             ON u.employee_code = e.employee_code OR lower(u.email) = lower(e.work_email)
           WHERE lb.employee_id = e.id AND lb.leave_type = 'ANNUAL' AND u.email = %s""",
        email,
    )


def leave(day: date, handover_id: str) -> dict:
    return {
        "title": "Xin nghỉ phép ngày mai",
        "reason": "Việc gia đình đột xuất, kiểm thử tự động",
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "leave_kind": "CO_LUONG",
        "handover_user_id": handover_id,
    }


QC05_TEXT = 'Điều 1 (Chặn duyệt tự động Nghỉ phép khi vướng hạn chót công việc): Đối với yêu cầu Nghỉ phép hoặc Nghỉ phép đặc biệt kéo dài từ 1 ngày trở lên trong giai đoạn nhân sự đang giữ tác vụ có hạn chót gấp trong 24 giờ chưa bàn giao, hệ thống không được tự động duyệt mà bắt buộc phải qua Trưởng bộ phận và Nhân sự phê duyệt thủ công. Điều 2 (Chặn lạm dụng Điều chỉnh chấm công lặp lại có hệ thống): Đối với yêu cầu Điều chỉnh chấm công khi nhân sự giải trình quên chấm công, đi muộn hoặc về sớm lặp lại từ lần thứ 4 trong tháng, hệ thống không tự động duyệt và bắt buộc Trưởng bộ phận phê duyệt thủ công. Điều 3 (Kiểm soát hạn mức Thanh toán chi phí và Quyết toán tạm ứng): Đối với yêu cầu Thanh toán chi phí hoặc Quyết toán tạm ứng có giá trị từ 20 triệu đồng trở lên, hệ thống không được tự động phê duyệt mà phải qua Kế toán kiểm soát và trình Ban Giám đốc phê duyệt. Điều 4 (Chống chia nhỏ chứng từ Tạm ứng và Thanh toán để lách hạn mức): Đối với đề xuất Thanh toán chi phí, Tạm ứng chi phí (<10tr) và Tạm ứng chi phí (10-50tr) có giá trị từ 15 triệu đồng trở lên hoặc có dấu hiệu chia nhỏ hóa đơn liên tiếp, hệ thống bắt buộc trình Kế toán và Ban Giám đốc phê duyệt thủ công kèm nghiệm thu độc lập. Điều 5 (Kiểm soát Hoàn tiền và Làm việc từ xa rủi ro cao): Đối với yêu cầu Hoàn tiền / Đền bù có giá trị trên 2 triệu đồng, hệ thống không được tự động duyệt mà bắt buộc phải được phê duyệt thủ công. Đối với yêu cầu Làm việc từ xa (WFH) kéo dài trên 2 ngày, hệ thống bắt buộc phải qua Trưởng bộ phận phê duyệt thủ công.'


def esc_00(o: t.Oracle) -> str:
    """Bước 1 kịch bản demo: ban hành Quy chế 05/2026 -> AI học -> luật có điều kiện ngữ cảnh được nạp."""
    admin = t.login("admin@eas.com", portal="admin")
    code = "QC05-" + uuid.uuid4().hex[:6].upper()
    st, body = admin.call("POST", "/api/v1/admin/regulations", {
        "code": code, "title": "Quy chế 05/2026 về nghỉ phép, chấm công và hạn mức tài chính",
        "category": "Quy định chung", "content": QC05_TEXT})
    check(st in (200, 201), f"ban hành quy chế thất bại: HTTP {st} {body}")
    state = o.wait("SELECT sync_status, applied_policy FROM eas.ai_system_state WHERE id=1", timeout=90,
                   want=lambda v: v and v[0] in ("COMPLETED", "FAILED") and v[1]
                   and any(str(r.get("id", "")).startswith(code) for r in v[1].get("rules", [])))
    check(state and state[0] == "COMPLETED", f"AI chưa học xong quy chế: {state and state[0]}")
    rules = [r for r in state[1]["rules"] if str(r.get("id", "")).startswith(code)]
    by = {(r.get("request_type"), tuple(k for k in ("due_within_hours", "repeat_count_gte", "split_suspect",
                                                    "amount_gt", "days_gt") if r.get(k) is not None)) for r in rules}
    check(("LEAVE", ("due_within_hours", "days_gt")) in by, f"thiếu luật nghỉ phép có điều kiện deadline: {by}")
    check(("ATTENDANCE_ADJUSTMENT", ("repeat_count_gte",)) in by, f"thiếu luật chấm công lần thứ 4: {by}")
    check(("EXPENSE_CLAIM", ("split_suspect",)) in by, f"thiếu luật chia nhỏ: {by}")
    blanket = [r for r in rules if r.get("request_type") in ("LEAVE", "ATTENDANCE_ADJUSTMENT")
               and not any(r.get(k) for k in ("due_within_hours", "repeat_count_gte"))]
    check(not blanket, f"có luật chặn tràn cả loại: {[r['id'] for r in blanket]}")
    esc = sorted({r["request_type"] + "->" + r["escalate_to"] for r in rules if r.get("escalate_to")})
    return f"{code}: AI học xong ({len(rules)} luật), không luật chặn tràn; nâng luồng: {', '.join(esc)}"


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
    reset_leave_balance(o, x_email)
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
    # Người chưa có hồ sơ tài chính nào trong 7 ngày (chạy lại nhiều lần vẫn đúng).
    email = o.one(
        """
        SELECT u.email FROM eas.app_user u
        JOIN eas.app_user m ON m.id = u.manager_id AND m.is_active
        WHERE u.is_active AND u.email NOT LIKE 'admin%%' AND NOT u.is_system_account
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='REQUESTER'
                      AND r.revoked_at IS NULL)
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='STAFF'
                      AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id
                          AND r.role IN ('OPS_ADMIN','POLICY_ADMIN','DIRECTOR','VICE_DIRECTOR','APPROVER')
                          AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.request r JOIN eas.request_type t ON t.id=r.type_id
                          WHERE r.requester_id=u.id AND t.code IN ('EXPENSE_CLAIM','REIMBURSEMENT',
                            'ADVANCE_SMALL','ADVANCE_MEDIUM','ADVANCE_LARGE','REFUND_COMPENSATION',
                            'SALARY_ADVANCE')
                            AND r.created_at > now() - interval '7 days')
        ORDER BY md5(u.email || now()::text) LIMIT 1"""
    )[0]
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
    first = lifecycle_of(o, rids[0])
    check(first and first[0] == "A", f"hồ sơ đầu tiên lẽ ra giữ luồng A: {first}")
    # Hồ sơ thứ hai (tổng 19 triệu) lên C khi Quy chế 05/2026 Điều 4 (ngưỡng 15 triệu) đang hiệu lực.
    second = lifecycle_of(o, rids[1])
    return (
        f"{email}: 3 đề nghị 9,5 triệu; hồ sơ đầu giữ A; hồ sơ thứ hai "
        f"{second[0] if second else '?'}; hồ sơ thứ ba {o.req(rids[2])['code']} -> A→C "
        f"(người xử lý {o.email(lc[1])}, nghiệm thu {o.email(lc[2])})"
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


def _deadline_case(o: t.Oracle):
    """Dựng tình huống ESC-01 rồi để cấp trên duyệt: trả (rid, x_id, m_email, held_rid)."""
    x_id, x_email, y_id, y_email, _m_id, m_email = manager_with_team(o)
    held, _, _ = t.submit(o, "EXPENSE_CLAIM", y_email, expense(1_300_000))
    o.wait("""SELECT 1 FROM eas.approval_step s JOIN eas.workflow_instance i ON i.id=s.instance_id
              WHERE s.request_id=%s AND s.state='ACTIVE' AND i.state='ACTIVE'""", held)
    reset_leave_balance(o, x_email)
    rid, _, _ = t.submit(o, "LEAVE", x_email, leave(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
                                                     + timedelta(days=1), y_id))
    check(wait_escalated(o, rid) is not None, "hồ sơ nghỉ không được nâng luồng")
    st, body = t.decide(o, rid, "APPROVE")
    check(st == 200, f"cấp trên duyệt thất bại: HTTP {st} {body}")
    return rid, x_id, m_email, held


def esc_04(o: t.Oracle) -> str:
    rid, _x_id, m_email, held = _deadline_case(o)
    m = t.login(m_email)
    st, body = m.call("GET", f"/api/v1/requests/{rid}/ai-remediation")
    check(st == 200, f"lấy đề xuất xử lý thất bại: HTTP {st} {body}")
    plan = body["plan"]
    item = next((i for i in plan["items"] if i["item_request_id"] == held), None)
    check(item is not None, f"kế hoạch không có việc đang giữ của X: {[i['item_code'] for i in plan['items']]}")
    check(item["candidates"], "không có ứng viên nhận việc thay")
    best = item["candidates"][0]
    prop = next(p for p in plan["proposals"] if p["case_code"] == "BC_DEADLINE_CONFLICT")
    st, body = m.call("POST", f"/api/v1/requests/{rid}/ai-remediation/confirm",
                      {"proposal_id": prop["id"], "actions": [
                          {"action": "DELEGATE_APPROVALS", "stage_id": item["stage_id"],
                           "candidate_id": best["user_id"]}]}, idem=str(uuid.uuid4()))
    check(st == 200, f"xác nhận chuyển việc thất bại: HTTP {st} {body}")
    step = o.active_step(held)
    check(step and step[2] == best["user_id"], f"bước duyệt chưa chuyển cho ứng viên: {step}")
    state = o.one("SELECT state FROM eas.ai_remediation WHERE id=%s", prop["id"])[0]
    check(state == "CONFIRMED", f"đề xuất không ở CONFIRMED: {state}")
    audit = o.one("SELECT details FROM eas.audit_event WHERE request_id=%s AND action='AI_REMEDIATION_REASSIGNED'",
                  held)
    check(audit and audit[0]["proposed_by"] == "AI", "thiếu audit AI_REMEDIATION_REASSIGNED trên hồ sơ được chuyển")
    return (f"{o.req(rid)['code']}: quản lý {m_email} xem đề xuất ({item['engine']}, gợi ý "
            f"{item['suggestion']['action']}), xác nhận giao bước duyệt {item['item_code']} cho "
            f"{best.get('display_name')} (điểm {best['score']}: {'; '.join(best['why'][:3])}) -> đã chuyển, audit đủ")


def esc_05(o: t.Oracle) -> str:
    rid, _x_id, m_email, held = _deadline_case(o)
    m = t.login(m_email)
    st, body = m.call("GET", f"/api/v1/requests/{rid}/ai-remediation")
    check(st == 200, f"lấy đề xuất xử lý thất bại: HTTP {st} {body}")
    plan = body["plan"]
    item = next(i for i in plan["items"] if i["item_request_id"] == held)
    check(item["postpone_to"], "không có hạn mới để lùi")
    before = o.one("SELECT due_at FROM eas.sla_stage WHERE id=%s", item["stage_id"])[0]
    prop = next(p for p in plan["proposals"] if p["case_code"] == "BC_DEADLINE_CONFLICT")
    st, body = m.call("POST", f"/api/v1/requests/{rid}/ai-remediation/confirm",
                      {"proposal_id": prop["id"], "actions": [
                          {"action": "POSTPONE_DEADLINE", "stage_id": item["stage_id"]}]}, idem=str(uuid.uuid4()))
    check(st == 200, f"xác nhận lùi hạn thất bại: HTTP {st} {body}")
    after = o.one("SELECT due_at FROM eas.sla_stage WHERE id=%s", item["stage_id"])[0]
    check(after > before, f"hạn SLA không được lùi: {before} -> {after}")
    note = o.wait("SELECT count(*) FROM eas.notification n JOIN eas.request r ON r.id=n.request_id "
                  "WHERE n.request_id=%s AND n.recipient_id=r.requester_id AND n.label LIKE 'Hạn xử lý%%'",
                  held, want=lambda v: v and v[0] > 0)
    check(note and note[0] > 0, "người gửi việc không nhận được thông báo lùi hạn")
    # Không có cờ thì không ai sửa được hạn (trigger CSDL).
    blocked = o.try_tamper_as("eas_api", f"UPDATE eas.sla_stage SET due_at=due_at+interval '1 day' "
                                         f"WHERE id='{item['stage_id']}'")
    check(blocked == "23514", f"sửa hạn không cờ lẽ ra bị chặn, nhận {blocked}")
    return (f"{o.req(rid)['code']}: lùi hạn bước duyệt {item['item_code']} {before:%d/%m %H:%M} -> "
            f"{after:%d/%m %H:%M} (sau ngày đi làm lại), người gửi được báo; sửa hạn không cờ bị chặn (23514)")


CASES = {"ESC-00": esc_00, "ESC-01": esc_01, "ESC-02": esc_02, "ESC-03": esc_03, "ESC-04": esc_04, "ESC-05": esc_05}


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
