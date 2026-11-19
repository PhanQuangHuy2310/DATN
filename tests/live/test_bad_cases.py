r"""Kiểm thử trực tiếp suy luận tình huống xấu (bad cases) trên BẢN SAO CSDL local.

Cần cùng môi trường với test_report_scenarios.py (EAS_LIVE_ORACLE_DSN, EAS_LIVE_PASSWORD) và AI tự duyệt BẬT.
  .venv\Scripts\python.exe tests\live\test_bad_cases.py --json bad_cases.json

BC-01  Xin về sớm khi đang giữ việc đến hạn trong 24 giờ           → BC_DEADLINE_CONFLICT, không tự duyệt
BC-02  Ba đề nghị tạm ứng 9,5 triệu trong 7 ngày (tổng > 20 triệu) → BC_SPLIT_AMOUNT_EVASION ở hồ sơ thứ ba
BC-03  Điều chỉnh chấm công lần thứ 4 trong 30 ngày                → BC_REPEATED_EXEMPTION, không tự duyệt
BC-04  Người duyệt tự duyệt hồ sơ của chính mình                    → bị chặn (bất kiêm nhiệm, trigger CSDL)
BC-00  Đối chứng: một đề nghị tạm ứng 9,5 triệu đơn lẻ             → không gắn cờ
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_report_scenarios as t

TODAY = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def flags(o: t.Oracle, rid: str, timeout: float = 25.0) -> list[str]:
    """Các mã tình huống xấu AI đã ghi vào nhật ký kiểm toán của hồ sơ (chờ worker xử lý)."""
    row = o.wait("""SELECT details FROM eas.audit_event WHERE request_id=%s AND action='AI_BAD_CASE_FLAGGED'
                    ORDER BY seq DESC LIMIT 1""", rid, timeout=timeout)
    if not row:
        return []
    return [c["code"] for c in (row[0] or {}).get("cases", [])]


def decided_by_ai(o: t.Oracle, rid: str) -> int:
    return o.one("""SELECT count(*) FROM eas.approval_decision d JOIN eas.app_user u ON u.id=d.actor_id
                    WHERE d.request_id=%s AND u.email LIKE 'ai.%%'""", rid)[0]


def fresh_requester(o: t.Oracle, seed: str) -> str:
    """Nhân viên chưa có hồ sơ tài chính/chấm công trong 30 ngày, để tín hiệu không bị lịch sử cũ làm nhiễu."""
    row = o.one("""
        SELECT u.email FROM eas.app_user u JOIN eas.app_user m ON m.id=u.manager_id AND m.is_active
        WHERE u.is_active AND u.email NOT LIKE 'admin%%' AND u.email NOT LIKE 'ai.%%'
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='REQUESTER' AND r.revoked_at IS NULL)
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='STAFF' AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id
                          AND r.role IN ('OPS_ADMIN','POLICY_ADMIN','DIRECTOR','VICE_DIRECTOR') AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.request r JOIN eas.request_type rt ON rt.id=r.type_id
                          WHERE r.requester_id=u.id AND r.created_at > now() - interval '30 days'
                            AND rt.code IN ('ADVANCE_SMALL','ADVANCE_MEDIUM','ADVANCE_LARGE','EXPENSE_CLAIM',
                                            'REIMBURSEMENT','SALARY_ADVANCE','REFUND_COMPENSATION','ATTENDANCE_ADJUSTMENT'))
        ORDER BY md5(u.email || %s) LIMIT 1""", seed)
    if not row:
        raise AssertionError("không còn nhân viên sạch lịch sử để kiểm thử")
    return row[0]


def advance(amount: int) -> dict:
    return {"title": "Tạm ứng chi phí kiểm thử tình huống xấu", "amount": amount, "currency": "VND",
            "purpose": "Tạm ứng mua vật tư sự kiện", "expected_refund_date": str(TODAY + timedelta(days=20))}


def attendance(kind: str, day: date) -> dict:
    return {"title": f"Điều chỉnh chấm công {kind.lower()} kiểm thử", "work_date": str(day), "change_type": kind,
            "reason": "Kiểm thử suy luận tình huống xấu"}


def bc_00(o: t.Oracle) -> str:
    email = fresh_requester(o, "BC-00")
    rid, _, _ = t.submit(o, "ADVANCE_SMALL", email, advance(9_500_000))
    time.sleep(8)
    got = flags(o, rid, timeout=5)
    t.check(not got, f"đối chứng bị gắn cờ {got}")
    return f"{o.req(rid)['code']}: một đề nghị 9.500.000 VNĐ → không gắn cờ (trạng thái {o.req(rid)['status']})"


def bc_02(o: t.Oracle) -> str:
    email = fresh_requester(o, "BC-02")
    rids = [t.submit(o, "ADVANCE_SMALL", email, advance(9_500_000))[0] for _ in range(3)]
    first_two = [flags(o, r, timeout=8) for r in rids[:2]]
    third = flags(o, rids[2])
    t.check(not any(first_two), f"hồ sơ 1-2 bị gắn cờ sớm: {first_two}")
    t.check("BC_SPLIT_AMOUNT_EVASION" in third, f"hồ sơ thứ ba không bị gắn cờ: {third}")
    t.check(decided_by_ai(o, rids[2]) == 0, "AI vẫn tự duyệt hồ sơ bị gắn cờ")
    codes = [o.req(r)["code"] for r in rids]
    return (f"{', '.join(codes)}: 3 × 9.500.000 VNĐ trong 7 ngày (tổng 28.500.000 > 20.000.000) → hồ sơ thứ ba gắn "
            f"BC_SPLIT_AMOUNT_EVASION, chờ người duyệt; hai hồ sơ đầu không gắn cờ")


def bc_03(o: t.Oracle) -> str:
    email = fresh_requester(o, "BC-03")
    rids = []
    for i in range(4):
        rids.append(t.submit(o, "ATTENDANCE_ADJUSTMENT", email, attendance("Đi muộn", TODAY - timedelta(days=i + 1)))[0])
        time.sleep(1)
    fourth = flags(o, rids[3])
    t.check("BC_REPEATED_EXEMPTION" in fourth, f"lần thứ 4 không bị gắn cờ: {fourth}")
    t.check(decided_by_ai(o, rids[3]) == 0, "AI vẫn tự duyệt lần thứ 4")
    early = [o.req(r)["status"] for r in rids[:3]]
    return (f"{o.req(rids[3])['code']}: điều chỉnh chấm công lần 4 trong 30 ngày → BC_REPEATED_EXEMPTION, trạng thái "
            f"{o.req(rids[3])['status']}; ba lần đầu: {', '.join(early)}")


def bc_01(o: t.Oracle) -> str:
    # Dựng tình huống: người quản lý M đang giữ một bước duyệt có hạn SLA trong 3 giờ tới.
    holder_rid, _, _ = t.submit(o, "WFH_REQ")
    step = o.active_step(holder_rid)
    t.check(step is not None, "không có bước duyệt để làm việc đang giữ")
    manager_email = o.email(step[2])
    can_request = o.one("""SELECT EXISTS (SELECT 1 FROM eas.role_membership r JOIN eas.app_user u ON u.id=r.user_id
                           WHERE u.email=%s AND r.role='REQUESTER' AND r.revoked_at IS NULL)
                           AND EXISTS (SELECT 1 FROM eas.app_user u JOIN eas.app_user m ON m.id=u.manager_id
                           WHERE u.email=%s AND m.is_active)""", manager_email, manager_email)[0]
    t.check(bool(can_request), f"{manager_email} không gửi được hồ sơ (thiếu REQUESTER hoặc quản lý)")
    o.fixture("""UPDATE eas.sla_stage SET due_at = now() + interval '3 hours'
                 WHERE request_id=%s AND closed_at IS NULL""", holder_rid)
    rid, _, _ = t.submit(o, "ATTENDANCE_ADJUSTMENT", manager_email, attendance("Về sớm", TODAY))
    got = flags(o, rid)
    t.check("BC_DEADLINE_CONFLICT" in got, f"không phát hiện xung đột hạn chót: {got}")
    t.check(decided_by_ai(o, rid) == 0, "AI vẫn tự duyệt đơn xin về sớm")
    return (f"{o.req(rid)['code']}: người gửi đang giữ bước duyệt của {o.req(holder_rid)['code']} hạn trong 3 giờ, xin về "
            f"sớm → BC_DEADLINE_CONFLICT, trạng thái {o.req(rid)['status']}, chờ quản lý xác nhận")


def bc_04(o: t.Oracle) -> str:
    rid, _h, _email = t.submit(o, "WFH_REQ")
    step = o.active_step(rid)
    approver = o.email(step[2])
    sqlstate = o.try_tamper_as("eas_api", f"""UPDATE eas.approval_step SET assignee_id=
        (SELECT requester_id FROM eas.request WHERE id='{rid}') WHERE id='{step[0]}'""")
    t.check(sqlstate is not None, "CSDL cho phép giao bước duyệt cho chính người gửi")
    return (f"{o.req(rid)['code']}: giao bước duyệt cho chính người gửi bị CSDL từ chối (SQLSTATE {sqlstate}); "
            f"người duyệt hợp lệ là {approver}")


CASES = {"BC-00": bc_00, "BC-01": bc_01, "BC-02": bc_02, "BC-03": bc_03, "BC-04": bc_04}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    t._guard()
    o = t.Oracle()
    wanted = [c for c in a.only.split(",") if c] or list(CASES)
    results = []
    for code in wanted:
        start = time.perf_counter()
        try:
            ev = CASES[code](o)
            results.append({"case": code, "passed": True, "evidence": ev, "error": ""})
        except Exception as exc:  # noqa: BLE001
            results.append({"case": code, "passed": False, "evidence": "", "error": str(exc)[:500]})
        r = results[-1]
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {code}  ({time.perf_counter() - start:4.1f}s)  {r['evidence'] or r['error']}",
              flush=True)
    print(f"\nKẾT QUẢ: {sum(r['passed'] for r in results)}/{len(results)} PASS")
    if a.json:
        Path(a.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
