r"""Kiểm thử trực tiếp: AI học bad case mới từ lý do người duyệt thu hồi hồ sơ AI đã tự duyệt (migration 25).

Chạy trên BẢN SAO CSDL local (đã chạy migration 23 + 24 + 25), cùng biến môi trường với test_report_scenarios.py:
  set EAS_LIVE_ORACLE_DSN=postgresql://supabase_admin:postgres@127.0.0.1:55322/postgres
  set EAS_LIVE_PASSWORD=Password@123456
  .venv\Scripts\python.exe tests\live\test_bad_case_learning.py [--json out.json]

BL-01  3 người duyệt (≥ 2 người khác nhau) thu hồi vì cùng một KIỂU lý do mới ở 3 người gửi khác nhau
       -> lần 1, 2: ứng viên + AI nói chưa đủ và hỏi admin; lần 3: AI tự thêm bad case vào CSDL;
       -> người thứ tư (chưa từng bị thu hồi) gửi hồ sơ cùng kiểu: AI chuyển sang B, nêu vì sao là bad case;
       -> hồ sơ bình thường của người khác vẫn được tự duyệt (không chặn tràn lan).
BL-02  lý do riêng của một hồ sơ -> AI kết luận không phải kiểu chung, nêu lý do, hỏi admin; admin từ chối.
BL-03  lý do khớp bad case có sẵn -> ghi bằng chứng cho bad case đó, nói vì sao AI bỏ sót, không tạo bad case mới.
BL-04  ứng viên chưa đủ -> admin bấm tạo (kèm điều kiện) -> AI dùng ngay cho người khác.
Bad case + bằng chứng sinh từ hồ sơ kiểm thử được xóa ở đầu và cuối (chỉ trên bản sao local) để lần chạy sau
và các kiểm thử khác không bị ảnh hưởng.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ai_feedback_learning as fb
import test_report_scenarios as t


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


_BAD_LOGIN: set[str] = set()


def can_login(email: str) -> bool:
    """Bản sao CSDL có vài tài khoản đã đổi mật khẩu (kiểm thử khác): bỏ qua, không phải lỗi của AI."""
    if email in _BAD_LOGIN:
        return False
    try:
        t.login(email)
        return True
    except AssertionError:
        _BAD_LOGIN.add(email)
        return False


def staff(o, exclude=()) -> str:
    excl = list(exclude)
    for _ in range(40):
        email = fb.staff(o, max_wfh=2, exclude=tuple(excl) + tuple(_BAD_LOGIN))
        if can_login(email) and can_login(manager_of(o, email)):
            return email
        excl.append(email)
    raise AssertionError("không tìm được nhân viên đăng nhập được")


def manager_of(o, email: str) -> str:
    return o.email(o.one("SELECT manager_id::text FROM eas.app_user WHERE email=%s", email)[0])


def ai_approved_wfh(o, email: str, day: int) -> str:
    rid, _, _ = t.submit(o, "WFH_REQ", email, fb.wfh(day))
    o.wait("SELECT 1 FROM eas.approval_decision WHERE request_id=%s", rid, timeout=40)
    check(fb.ai_completed(o, rid), f"AI không tự duyệt đơn WFH của {email} ({o.req(rid)['code']})")
    return rid


def revoke(o, rid: str, email: str, reason: str) -> dict:
    m = t.login(manager_of(o, email))
    st, body = m.call("POST", f"/api/v1/requests/{rid}/ai-approval/revoke",
                      {"reason": reason, "expected_version": o.req(rid)["version"]}, idem=str(uuid.uuid4()))
    check(st == 200, f"thu hồi thất bại: HTTP {st} {body}")
    row = o.wait(
        """SELECT e.verdict, e.confidence, e.feature, b.id::text, b.code, b.state, b.evaluation, b.activated_by,
                  e.analysis
           FROM eas.bad_case_evidence e LEFT JOIN eas.bad_case b ON b.id = e.bad_case_id
           WHERE e.request_id = %s ORDER BY e.created_at DESC LIMIT 1""", rid, timeout=60)
    check(row, f"AI chưa phân tích lý do thu hồi của {o.req(rid)['code']} sau 60 giây")
    keys = ("verdict", "confidence", "feature", "case_id", "code", "state", "evaluation", "activated_by", "analysis")
    return dict(zip(keys, row, strict=True))


def pick_staff(o, n: int, exclude=(), distinct_managers: int = 1) -> list[str]:
    chosen, managers, seen = [], set(), list(exclude)
    for _ in range(60):
        email = staff(o, exclude=tuple(seen))
        seen.append(email)
        mgr = manager_of(o, email)
        # Còn ít chỗ hơn số quản lý còn thiếu thì chỉ nhận người có quản lý mới.
        if mgr in managers and n - len(chosen) <= distinct_managers - len(managers):
            continue
        chosen.append(email)
        managers.add(mgr)
        if len(chosen) == n:
            return chosen
    raise AssertionError("không chọn được đủ nhân viên với số quản lý khác nhau cần thiết")


def escalation_causes(o, rid) -> list[dict]:
    d = fb.escalated(o, rid)
    return (d or {}).get("causes") or []


def bl_01(o: t.Oracle) -> dict:
    people = pick_staff(o, 3, distinct_managers=2)
    reasons = [
        "Báo WFH quá sát giờ, gửi tối hôm trước cho sáng hôm sau, phòng không kịp sắp xếp.",
        "Xin làm từ xa sát ngày như vậy thì không kịp bố trí người họp thay.",
        "Cứ báo WFH đột xuất, không báo trước đủ thời gian để sắp xếp công việc.",
    ]
    steps = []
    for i, (email, reason) in enumerate(zip(people, reasons, strict=True)):
        rid = ai_approved_wfh(o, email, 1)
        r = revoke(o, rid, email, reason)
        steps.append(r)
        if i < 2:
            check(r["state"] == "CANDIDATE",
                  f"lần {i + 1}: mong ứng viên chờ admin, được {r['state']} ({r['verdict']}, {r['code']})")
            check(bool((r["evaluation"] or {}).get("question")), f"lần {i + 1}: AI không hỏi admin")
    codes = {s["code"] for s in steps}
    check(len(codes) == 1, f"3 lý do cùng kiểu bị tách thành nhiều ứng viên: {codes} "
                           f"({[(s['verdict'], s['feature']) for s in steps]})")
    last = steps[-1]
    check(last["state"] == "ACTIVE" and last["activated_by"] == "AI",
          f"lần 3: AI chưa tự tạo bad case, trạng thái {last['state']}; đánh giá: "
          f"{(last['evaluation'] or {}).get('summary')}")
    code = last["code"]
    z = staff(o, exclude=tuple(people))
    rid_z, _, _ = t.submit(o, "WFH_REQ", z, fb.wfh(1))
    fb.settle(o, rid_z)
    causes = escalation_causes(o, rid_z)
    hit = next((c for c in causes if c.get("code") == code), None)
    check(hit is not None, f"người thứ tư {z}: AI không áp bad case mới {code} (nguyên nhân: {causes})")
    check(bool(hit.get("why")), "nguyên nhân chuyển luồng thiếu 'vì sao là bad case'")
    w = staff(o, exclude=tuple(people) + (z,))
    rid_w = ai_approved_wfh(o, w, 20)
    return {"pass": True, "evidence": (
        f"3 lý do -> {[(s['verdict'], s['feature'], s['state']) for s in steps]}; bad case {code} "
        f"({(last['evaluation'] or {}).get('summary')}); người thứ tư {o.req(rid_z)['code']} chuyển "
        f"{fb.lifecycle(o, rid_z)} vì {code}: “{hit.get('why')[:80]}…”; đối chứng {o.req(rid_w)['code']} vẫn tự duyệt")}


def bl_02(o: t.Oracle) -> dict:
    x = staff(o)
    rid = ai_approved_wfh(o, x, 26)
    r = revoke(o, rid, x, "Em ghi thiếu danh sách công việc trong ngày, bổ sung rồi gửi lại nhé.")
    ev = r["evaluation"] or {}
    check(r["verdict"] == "ONE_OFF", f"mong lý do riêng (ONE_OFF), được {r['verdict']}")
    check(r["state"] == "CANDIDATE" and not ev.get("enough"), f"không được tự tạo: {r['state']}")
    check(ev.get("missing") and ev.get("question"), "AI không nêu lý do chưa đủ hoặc không hỏi admin")
    admin = t.login("admin@eas.com", portal="admin")
    st, body = admin.call("POST", f"/api/v1/admin/ai-engine/bad-cases/{r['case_id']}/reject",
                          {"note": "Lý do riêng của hồ sơ, không phải kiểu rủi ro chung"})
    check(st == 200 and body.get("state") == "REJECTED", f"admin từ chối thất bại: HTTP {st} {body}")
    return {"pass": True, "evidence": (f"{o.req(rid)['code']}: {r['verdict']} (chắc {r['confidence']}); AI: "
                                       f"{ev.get('summary')[:140]}…; hỏi: {ev.get('question')[:90]}…; admin từ chối")}


def bl_03(o: t.Oracle) -> dict:
    x = staff(o)
    rid = ai_approved_wfh(o, x, 27)
    before = o.one("SELECT count(*) FROM eas.bad_case")[0]
    r = revoke(o, rid, x, "Tháng này bạn ấy làm từ xa quá nhiều buổi rồi, cần lên văn phòng.")
    after = o.one("SELECT count(*) FROM eas.bad_case")[0]
    why = (r["analysis"] or {}).get("why_missed")
    check(r["verdict"] == "EXISTING" and r["code"] == "BC_WFH_FREQUENT",
          f"mong khớp BC_WFH_FREQUENT, được {r['verdict']} {r['code']}")
    check(after == before, "tạo thêm bad case mới cho lý do đã có trong danh mục")
    check(bool(why), "không giải thích vì sao AI bỏ sót")
    return {"pass": True, "evidence": f"{o.req(rid)['code']}: khớp {r['code']}; vì sao bỏ sót: {why[:140]}"}


def next_weekday(day: int, weekday: int) -> int:
    """Số ngày từ hôm nay tới ngày có isoweekday = weekday, không sớm hơn day."""
    d = fb.TODAY + timedelta(days=day)
    while d.isoweekday() != weekday:
        d += timedelta(days=1)
    return (d - fb.TODAY).days


def bl_04(o: t.Oracle) -> dict:
    x = staff(o)
    friday = next_weekday(40, 5)
    rid = ai_approved_wfh(o, x, friday)
    r = revoke(o, rid, x, "Tuần nào cũng xin làm từ xa vào thứ Sáu, thành nghỉ cuối tuần dài.")
    check(r["verdict"] == "NEW_PATTERN" and r["state"] == "CANDIDATE",
          f"mong ứng viên kiểu mới chờ admin, được {r['verdict']} {r['state']}")
    proposed = o.one("SELECT condition FROM eas.bad_case WHERE id=%s", r["case_id"])[0]
    condition = proposed or {"all": [{"feature": "start_weekday", "op": "in", "value": [5]}]}
    admin = t.login("admin@eas.com", portal="admin")
    st, body = admin.call("POST", f"/api/v1/admin/ai-engine/bad-cases/{r['case_id']}/approve",
                          {"condition": condition, "note": "Admin xác nhận tạo bad case"})
    check(st == 200 and body.get("state") == "ACTIVE", f"admin tạo bad case thất bại: HTTP {st} {body}")
    z = staff(o, exclude=(x,))
    rid_z, _, _ = t.submit(o, "WFH_REQ", z, fb.wfh(next_weekday(45, 5)))
    fb.settle(o, rid_z)
    hit = any(c.get("code") == r["code"] for c in escalation_causes(o, rid_z))
    check(hit, f"{z}: AI không áp bad case admin vừa tạo ({r['code']}, điều kiện {condition})")
    rid_w = ai_approved_wfh(o, staff(o, exclude=(x, z)), next_weekday(45, 3))
    return {"pass": True, "evidence": (f"{o.req(rid)['code']}: ứng viên {r['code']} (AI đề xuất điều kiện "
                                       f"{proposed}); admin tạo -> {o.req(rid_z)['code']} thứ Sáu chuyển "
                                       f"{fb.lifecycle(o, rid_z)}; {o.req(rid_w)['code']} thứ Tư vẫn tự duyệt")}


def close_test_requests(o) -> int:
    """Hồ sơ kiểm thử còn chờ duyệt (bị thu hồi hoặc bị chuyển B/C) được người duyệt TỪ CHỐI kèm lý do, đúng luồng
    thật; nếu để treo, việc đang giữ của quản lý phình ra và làm lệch kiểm thử đề xuất xử lý (giới hạn 30 việc)."""
    rows = o.all(
        """
        SELECT r.id::text FROM eas.request r JOIN eas.request_revision v ON v.request_id = r.id AND v.revision_no = 1
        WHERE v.payload->>'title' = 'Làm việc từ xa kiểm thử phản hồi' AND r.status = 'PENDING_APPROVAL'
        """
    )
    closed = 0
    for (rid,) in rows:
        try:
            st, _ = t.decide(o, rid, "REJECT", "Dọn dữ liệu kiểm thử trực tiếp: từ chối hồ sơ kiểm thử còn treo.")
            closed += st == 200
        except AssertionError:
            continue  # tài khoản người duyệt không đăng nhập được trên bản sao
    return closed


def purge_test_cases(o) -> int:
    """Xóa bad case + bằng chứng sinh từ hồ sơ kiểm thử (tiêu đề cố định) trên BẢN SAO local.

    Trigger bảo vệ cấm xóa (đúng cho hệ thống thật); ở bản sao kiểm thử, phiên supabase_admin tắt trigger bằng
    session_replication_role để các lần chạy lặp lại không ảnh hưởng nhau (ứng viên bị từ chối vẫn 'hút' lý do mới).
    """
    with o.conn.transaction(), o.conn.cursor() as c:
        c.execute("SET LOCAL session_replication_role = replica")
        # Phản hồi thu hồi của hồ sơ kiểm thử: ngưng dùng, nếu không worker (quét 5 phút) phân tích lại và tạo lại.
        c.execute(
            """
            UPDATE eas.ai_feedback f SET retired_at = now()
            FROM eas.request_revision v
            WHERE v.request_id = f.request_id AND v.revision_no = 1
              AND v.payload->>'title' = 'Làm việc từ xa kiểm thử phản hồi'
              AND f.kind = 'AUTO_APPROVE_REVOKED' AND f.retired_at IS NULL
            """
        )
        c.execute(
            """
            WITH test_req AS (
              SELECT r.id FROM eas.request r JOIN eas.request_revision v ON v.request_id = r.id AND v.revision_no = 1
              WHERE v.payload->>'title' = 'Làm việc từ xa kiểm thử phản hồi'),
            cases AS (
              SELECT DISTINCT e.bad_case_id AS id FROM eas.bad_case_evidence e
              JOIN eas.bad_case b ON b.id = e.bad_case_id AND b.detector <> 'BUILTIN'
              WHERE e.request_id IN (SELECT id FROM test_req)),
            gone AS (
              DELETE FROM eas.bad_case_evidence
              WHERE request_id IN (SELECT id FROM test_req) OR bad_case_id IN (SELECT id FROM cases) RETURNING 1)
            DELETE FROM eas.bad_case WHERE id IN (SELECT id FROM cases) RETURNING 1
            """
        )
        return c.rowcount


CASES = {"BL-01": bl_01, "BL-02": bl_02, "BL-03": bl_03, "BL-04": bl_04}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    t._guard()
    o = t.Oracle()
    only = set(filter(None, a.only.split(",")))
    results = []
    close_test_requests(o)
    purge_test_cases(o)
    try:
        for code, fn in CASES.items():
            if only and code not in only:
                continue
            start = time.time()
            try:
                r = fn(o)
            except Exception as exc:  # noqa: BLE001
                r = {"pass": False,
                     "evidence": str(exc) if isinstance(exc, AssertionError) else traceback.format_exc()}
            results.append({"code": code, "seconds": round(time.time() - start, 1), **r})
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {code}  ({time.time() - start:5.1f}s)  {r['evidence']}",
                  flush=True)
    finally:
        close_test_requests(o)
        purge_test_cases(o)
    print(f"\nKẾT QUẢ: {sum(r['pass'] for r in results)}/{len(results)} PASS")
    if a.json:
        Path(a.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
