r"""Kiểm thử trực tiếp vòng phản hồi 'sai tối đa 1 lần' theo ai_service/training/data/feedback_learning_episodes.json.

Chạy trên BẢN SAO CSDL local (đã chạy migration 23 + 24), cùng biến môi trường với test_report_scenarios.py:
  set EAS_LIVE_ORACLE_DSN=postgresql://supabase_admin:postgres@127.0.0.1:55322/postgres
  set EAS_LIVE_PASSWORD=Password@123456
  .venv\Scripts\python.exe tests\live\test_ai_feedback_learning.py [--json out.json]

Mỗi tập in: lần sai (1) đã được người sửa, ca tương tự (2) có lặp lại lỗi không, ca đối chứng (3) có đổi hành vi
không. Chỉ số: repeat_mistakes (mục tiêu 0) và over_generalization (mục tiêu 0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ai_escalation as esc
import test_report_scenarios as t

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ai_service" / "training" / "data"
TODAY = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def verify_episodes() -> list[dict]:
    raw = (DATA / "feedback_learning_episodes.json").read_bytes()
    want = (DATA / "feedback_learning_episodes.sha256").read_text(encoding="ascii").split()[0]
    check(hashlib.sha256(raw).hexdigest() == want, "SHA-256 bộ tập đã đổi; từ chối chạy")
    return json.loads(raw)["episodes"]


def wfh(day_offset: int) -> dict:
    return {"title": "Làm việc từ xa kiểm thử phản hồi", "date": (TODAY + timedelta(days=day_offset)).isoformat(),
            "task_list": "Hoàn thiện tài liệu", "communication_channel": "Microsoft Teams"}


def staff(o: t.Oracle, *, max_wfh: int | None = None, min_wfh: int | None = None, exclude=()) -> str:
    rows = o.all(
        """
        SELECT u.email, (SELECT count(*) FROM eas.request q JOIN eas.request_type qt ON qt.id=q.type_id
                         WHERE q.requester_id=u.id AND qt.code='WFH_REQ'
                           AND q.created_at > date_trunc('month', now())) AS wfh
        FROM eas.app_user u JOIN eas.app_user m ON m.id=u.manager_id AND m.is_active
        WHERE u.is_active AND NOT u.is_system_account AND u.email NOT LIKE 'admin%%'
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='REQUESTER' AND r.revoked_at IS NULL)
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.role='STAFF' AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id=u.id AND r.revoked_at IS NULL
                          AND r.role IN ('OPS_ADMIN','POLICY_ADMIN','DIRECTOR','VICE_DIRECTOR','APPROVER'))
          AND NOT EXISTS (SELECT 1 FROM eas.ai_feedback f WHERE f.subject_id=u.id)
        ORDER BY md5(u.email || now()::text)
        """
    )
    for email, count in rows:
        if email in exclude:
            continue
        if max_wfh is not None and count > max_wfh:
            continue
        if min_wfh is not None and count < min_wfh:
            continue
        return email
    raise AssertionError("không tìm được nhân viên phù hợp trong bản sao")


def lifecycle(o, rid):
    row = o.one("""SELECT i.lifecycle FROM eas.workflow_instance i JOIN eas.request r ON r.current_revision_id=i.revision_id
                   WHERE r.id=%s ORDER BY i.created_at DESC LIMIT 1""", rid)
    return row[0] if row else None


def settle(o, rid, timeout=40):
    """Chờ worker xử lý xong lượt AI cho hồ sơ (tự duyệt, nâng luồng, hoặc để người duyệt)."""
    return o.wait(
        """SELECT r.status FROM eas.request r WHERE r.id=%s AND (r.status <> 'PENDING_APPROVAL' OR EXISTS (
             SELECT 1 FROM eas.outbox_event e WHERE e.request_id=r.id AND e.event_type='APPROVAL_REQUESTED'
             AND e.state IN ('SENT','DEAD')))""", rid, timeout=timeout)


def ai_completed(o, rid) -> bool:
    return bool(o.one("""SELECT 1 FROM eas.approval_decision d WHERE d.request_id=%s
                         AND d.actor_id='00000002-0000-4000-8000-0000000000a1'""", rid))


def escalated(o, rid) -> dict | None:
    row = o.one("SELECT details FROM eas.audit_event WHERE request_id=%s AND action='AI_ESCALATED' "
                "ORDER BY seq DESC LIMIT 1", rid)
    return row[0] if row else None


def fb_01(o: t.Oracle) -> dict:
    x = staff(o, max_wfh=2)
    rid, _, _ = t.submit(o, "WFH_REQ", x, wfh(30))
    o.wait("SELECT 1 FROM eas.approval_decision WHERE request_id=%s", rid, timeout=40)
    check(ai_completed(o, rid), f"(1) AI không tự duyệt đơn đầu của {x}; không dựng được lần sai")
    manager = o.email(o.one("SELECT manager_id::text FROM eas.app_user WHERE email=%s", x)[0])
    m = t.login(manager)
    st, body = m.call("POST", f"/api/v1/requests/{rid}/ai-approval/revoke",
                      {"reason": "Đơn WFH trùng ngày họp bắt buộc tại văn phòng", "expected_version": o.req(rid)["version"]},
                      idem=str(uuid.uuid4()))
    check(st == 200, f"(1) quản lý thu hồi thất bại: HTTP {st} {body}")
    rid2, _, _ = t.submit(o, "WFH_REQ", x, wfh(31))
    settle(o, rid2)
    d = escalated(o, rid2)
    repeat = ai_completed(o, rid2)
    learned = o.one("SELECT details FROM eas.audit_event WHERE request_id=%s AND action='AI_LEARNED_FROM_FEEDBACK'", rid2)
    z = staff(o, max_wfh=2, exclude=(x,))
    rid3, _, _ = t.submit(o, "WFH_REQ", z, wfh(32))
    o.wait("SELECT 1 FROM eas.approval_decision WHERE request_id=%s", rid3, timeout=40)
    control_changed = not ai_completed(o, rid3)
    return {"repeat_mistake": repeat, "over_generalization": control_changed,
            "evidence": (f"(1) {o.req(rid)['code']} AI tự duyệt, {manager} thu hồi; (2) {o.req(rid2)['code']} "
                         f"AI tự duyệt lại: {repeat}, nâng luồng: {d and d['to_lifecycle']} "
                         f"({', '.join(c['code'] for c in (d or {}).get('causes', []))}), học: {bool(learned)}; "
                         f"(3) {o.req(rid3)['code']} của {z} vẫn tự duyệt: {not control_changed}")}


def top_up_wfh(o: t.Oracle, email: str, target: int = 7, start: int = 60) -> None:
    """Đưa số đơn WFH trong tháng của một người lên target (ngưỡng BC_WFH_FREQUENT là quá 7)."""
    count = o.one("""SELECT count(*) FROM eas.request q JOIN eas.request_type qt ON qt.id=q.type_id
                     JOIN eas.app_user u ON u.id=q.requester_id
                     WHERE u.email=%s AND qt.code='WFH_REQ' AND q.created_at > date_trunc('month', now())""", email)[0]
    for i in range(max(target - count, 0)):
        t.submit(o, "WFH_REQ", email, wfh(start + i))


def fb_02(o: t.Oracle) -> dict:
    x = staff(o, max_wfh=6)
    top_up_wfh(o, x)
    rid, _, _ = t.submit(o, "WFH_REQ", x, wfh(33))
    check(esc.wait_escalated(o, rid) is not None, f"(1) đơn WFH của {x} (≥8 đơn/tháng) không bị nâng luồng")
    approver = o.email(o.active_step(rid)[2])
    m = t.login(approver)
    st, body = m.call("POST", f"/api/v1/requests/{rid}/ai-feedback/escalation",
                      {"reason": "Nhân viên làm dự án tại khách hàng, WFH theo thỏa thuận"})
    check(st == 200, f"(1) đánh dấu chuyển nhầm thất bại: HTTP {st} {body}")
    rid2, _, _ = t.submit(o, "WFH_REQ", x, wfh(34))
    settle(o, rid2)
    time.sleep(3)
    repeat = escalated(o, rid2) is not None
    w = staff(o, max_wfh=6, exclude=(x,))
    top_up_wfh(o, w, start=80)
    rid3, _, _ = t.submit(o, "WFH_REQ", w, wfh(35))
    control_changed = esc.wait_escalated(o, rid3) is None
    return {"repeat_mistake": repeat, "over_generalization": control_changed,
            "evidence": (f"(1) {o.req(rid)['code']} của {x} bị chuyển B, {approver} đánh dấu nhầm; (2) "
                         f"{o.req(rid2)['code']} bị chuyển lại: {repeat}, luồng {lifecycle(o, rid2)}; (3) "
                         f"{o.req(rid3)['code']} của {w} vẫn chuyển B: {not control_changed}")}


def _plan_after_leave(o, x_email, y_id, y_email, m_email, day):
    held, _, _ = t.submit(o, "EXPENSE_CLAIM", y_email, esc.expense(1_100_000))
    o.wait("""SELECT 1 FROM eas.approval_step s JOIN eas.workflow_instance i ON i.id=s.instance_id
              WHERE s.request_id=%s AND s.state='ACTIVE' AND i.state='ACTIVE'""", held)
    esc.reset_leave_balance(o, x_email)
    rid, _, _ = t.submit(o, "LEAVE", x_email, esc.leave(TODAY + timedelta(days=day), y_id))
    check(esc.wait_escalated(o, rid) is not None, "đơn nghỉ không được nâng luồng")
    st, body = t.decide(o, rid, "APPROVE")
    check(st == 200, f"cấp trên duyệt thất bại: HTTP {st} {body}")
    m = t.login(m_email)
    st, body = m.call("GET", f"/api/v1/requests/{rid}/ai-remediation")
    check(st == 200, f"lấy đề xuất thất bại: HTTP {st} {body}")
    item = next(i for i in body["plan"]["items"] if i["item_request_id"] == held)
    prop = next(p for p in body["plan"]["proposals"] if p["case_code"] == "BC_DEADLINE_CONFLICT")
    return m, rid, item, prop


def fb_03(o: t.Oracle) -> dict:
    x_id, x_email, y_id, y_email, _m_id, m_email = esc.manager_with_team(o)
    m, rid, item, prop = _plan_after_leave(o, x_email, y_id, y_email, m_email, 2)
    check(len(item["candidates"]) >= 2, "cần ít nhất 2 ứng viên để quản lý chọn khác AI")
    top, chosen = item["candidates"][0], item["candidates"][1]
    st, body = m.call("POST", f"/api/v1/requests/{rid}/ai-remediation/confirm",
                      {"proposal_id": prop["id"], "actions": [{"action": "DELEGATE_APPROVALS", "stage_id": item["stage_id"],
                                                               "candidate_id": chosen["user_id"]}]},
                      idem=str(uuid.uuid4()))
    check(st == 200, f"(1) xác nhận chọn ứng viên khác thất bại: HTTP {st} {body}")
    _m2, _rid2, item2, _p2 = _plan_after_leave(o, x_email, y_id, y_email, m_email, 4)
    first = item2["candidates"][0] if item2["candidates"] else {}
    repeat = first.get("user_id") != chosen["user_id"]
    # Đối chứng: một người xin nghỉ khác (quản lý khác có cấp dưới).
    other = o.one("""
        SELECT x.id::text, x.email, y.id::text, y.email, m.email FROM eas.app_user x
        JOIN eas.app_user y ON y.manager_id = x.id AND y.is_active
        JOIN eas.app_user m ON m.id = x.manager_id AND m.is_active
        WHERE x.is_active AND x.id <> %s AND NOT x.is_system_account AND x.email NOT LIKE 'admin%%'
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = x.id AND r.role = 'APPROVER' AND r.revoked_at IS NULL)
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = x.id AND r.role = 'REQUESTER' AND r.revoked_at IS NULL)
          AND EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = y.id AND r.role = 'REQUESTER' AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id IN (x.id, y.id)
                          AND r.role IN ('OPS_ADMIN','POLICY_ADMIN','DIRECTOR','VICE_DIRECTOR') AND r.revoked_at IS NULL)
          AND NOT EXISTS (SELECT 1 FROM eas.role_membership r WHERE r.user_id = y.id AND r.role = 'APPROVER' AND r.revoked_at IS NULL)
        ORDER BY x.email LIMIT 1""", x_id)
    control_changed = False
    control_note = "không có người xin nghỉ khác phù hợp"
    if other:
        _m3, _rid3, item3, _p3 = _plan_after_leave(o, other[1], other[2], other[3], other[4], 6)
        control_changed = any(c.get("learned") for c in item3["candidates"])
        control_note = f"{other[1]}: có ứng viên gắn 'learned': {control_changed}"
    return {"repeat_mistake": repeat, "over_generalization": control_changed,
            "evidence": (f"(1) AI xếp {top.get('display_name')} đầu, quản lý chọn {chosen.get('display_name')}; "
                         f"(2) lần sau đứng đầu: {first.get('display_name')} (learned={first.get('learned')}); "
                         f"(3) {control_note}")}


def fb_04(o: t.Oracle) -> dict:
    admin = t.login("admin@eas.com", portal="admin")
    code = "QC-FB-" + uuid.uuid4().hex[:5].upper()
    unparsed = "Phê duyệt chiết khấu thương mại đặc biệt từ 20% trở lên phải qua Ban Giám đốc."
    supported = "Thanh toán chi phí từ 40 triệu đồng trở lên bắt buộc duyệt thủ công."
    st, body = admin.call("POST", "/api/v1/admin/regulations",
                          {"code": code, "title": "Quy định kiểm thử phản hồi", "category": "Quy định chung",
                           "content": f"{unparsed} {supported}"})
    check(st in (200, 201), f"ban hành thất bại: HTTP {st} {body}")
    review = o.wait("SELECT id::text, suggestion FROM eas.regulation_clause_review WHERE regulation_code=%s AND state='PENDING'",
                    code, timeout=120)
    check(review is not None, "(1) câu chưa hiểu không vào hàng chờ của admin")
    supported_in_queue = o.one("SELECT count(*) FROM eas.regulation_clause_review WHERE regulation_code=%s "
                               "AND sentence LIKE 'Thanh toán chi phí%%'", code)[0]
    suggestion = review[1].get("rules") or []
    rules = [r for r in suggestion if r.get("request_type") == "SPECIAL_DISCOUNT" and r.get("auto_approve") is False]
    rules = [{k: v for k, v in r.items() if k in ("request_type", "auto_approve", "min_risk", "approvers", "escalate_to")}
             for r in rules] or [{"request_type": "SPECIAL_DISCOUNT", "auto_approve": False, "min_risk": 5,
                                  "approvers": ["DIRECTOR"]}]
    st, body = admin.call("POST", f"/api/v1/admin/regulations/clause-reviews/{review[0]}/approve",
                          {"rules": rules, "note": "Duyệt theo đề xuất của AI"})
    check(st == 200, f"(1) admin duyệt thất bại: HTTP {st} {body}")
    applied = o.wait("SELECT applied_policy FROM eas.ai_system_state WHERE id=1", timeout=120,
                     want=lambda v: v and any(str(r.get("id", "")).startswith(f"REV-{code}") for r in v[0].get("rules", [])))
    learned = bool(applied)
    compiled = applied and any(str(r.get("id", "")).startswith(f"{code}-2") for r in applied[0]["rules"])
    return {"repeat_mistake": not learned, "over_generalization": bool(supported_in_queue) or not compiled,
            "evidence": (f"(1) câu % vào hàng chờ, Gemini gợi ý {len(suggestion)} luật; admin duyệt {len(rules)} luật; "
                         f"(2) luật REV-{code} có trong bộ luật đang áp dụng: {learned}; "
                         f"(3) câu ngưỡng tiền tự biên dịch: {bool(compiled)}, vào hàng chờ: {bool(supported_in_queue)}")}


def fb_05(o: t.Oracle) -> dict:
    admin = t.login("admin@eas.com", portal="admin")
    before = json.loads((ROOT / "ai_service" / "models" / "remediation_ranker_meta.json").read_text(encoding="utf-8"))
    st, body = admin.call("POST", "/api/v1/admin/ai-engine/feedback/learn", {})
    check(st == 202, f"không khởi chạy được học dồn: HTTP {st} {body}")
    end = time.time() + 300
    while time.time() < end:
        st, state = admin.call("GET", "/api/v1/admin/ai-engine/feedback")
        if st == 200 and (state.get("learning") or {}).get("state") == "DONE":
            body = state["learning"]["result"]
            break
        time.sleep(5)
    else:
        raise AssertionError("học dồn chưa xong sau 5 phút")
    status = body.get("status")
    ok_gate = True
    if status == "ACCEPTED":
        ok_gate = (body["after"]["test_top1"] >= (body["before"]["test_top1"] or 0) - 0.01
                   and body["after"]["real_top1"] >= (body["before"]["real_top1"] or 0))
    elif status == "REJECTED_BY_GATE":
        ok_gate = bool(body.get("reasons"))
    else:
        ok_gate = False
    empty = subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-c",
         ("import httpx,os;r=httpx.post(os.environ['EAS_AI_SERVICE_URL']+'/ai/remediation/retrain',json={'groups':[]},"
          "headers={'X-Internal-Secret':os.environ['EAS_AI_INTERNAL_SECRET']},timeout=60);print(r.json()['status'])")],
        capture_output=True, text=True, cwd=ROOT, timeout=120, check=False).stdout.strip()
    return {"repeat_mistake": not ok_gate, "over_generalization": empty != "NOT_ENOUGH_FEEDBACK",
            "evidence": (f"(2) học dồn: {status}, trước {body.get('before')}, sau {body.get('after')}, "
                         f"lý do {body.get('reasons')}, phiên bản {body.get('version') or before.get('model_version')}; "
                         f"(3) không có phản hồi: {empty}")}


CASES = {"FB-01": fb_01, "FB-02": fb_02, "FB-03": fb_03, "FB-04": fb_04, "FB-05": fb_05}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    t._guard()
    verify_episodes()
    o = t.Oracle()
    only = set(filter(None, a.only.split(",")))
    results = []
    for code, fn in CASES.items():
        if only and code not in only:
            continue
        start = time.time()
        try:
            r = fn(o)
            ok = not r["repeat_mistake"] and not r["over_generalization"]
        except Exception as exc:  # noqa: BLE001
            r = {"repeat_mistake": None, "over_generalization": None,
                 "evidence": str(exc) if isinstance(exc, AssertionError) else traceback.format_exc()}
            ok = False
        results.append({"code": code, "pass": ok, "seconds": round(time.time() - start, 1), **r})
        print(f"{'PASS' if ok else 'FAIL'}  {code}  ({time.time() - start:5.1f}s)  {r['evidence']}", flush=True)
    repeats = sum(1 for r in results if r["repeat_mistake"])
    over = sum(1 for r in results if r["over_generalization"])
    print(f"\nKẾT QUẢ: {sum(r['pass'] for r in results)}/{len(results)} PASS | lặp lại lỗi: {repeats} | học tràn: {over}")
    if a.json:
        Path(a.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
