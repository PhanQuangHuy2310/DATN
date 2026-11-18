r"""Kiểm thử trực tiếp: quy định mới thay thế quy định cũ tương tự (ví dụ 40 tr -> 50 tr của người dùng, 18/11).

Chạy trên BẢN SAO CSDL local, cùng biến môi trường với test_report_scenarios.py:
  set EAS_LIVE_ORACLE_DSN=postgresql://supabase_admin:postgres@127.0.0.1:55322/postgres
  set EAS_LIVE_PASSWORD=Password@123456
  .venv\Scripts\python.exe tests\live\test_regulation_supersede.py

SP-01  Ban hành QD cũ "Hoàn tiền trên 4 triệu -> nghiệm thu độc lập": đơn hoàn tiền 5 triệu bị AI chuyển sang C.
SP-02  "AI kiểm tra trước" QD mới "trên 6 triệu": không lỗi, báo SẼ THAY THẾ đúng điều của QD cũ.
SP-03  Ban hành QD mới: luật 4 triệu rời khỏi bộ luật AI, trang Quy định ghi "đã bị thay thế"; đơn 5 triệu KHÔNG còn
       bị chuyển C; đơn 7 triệu vẫn chuyển C theo QD mới; người dùng được báo "QD mới thay thế QD cũ".
SP-04  Văn bản mới tự mâu thuẫn trong chính nó vẫn bị chặn (không thay thế gì).
Quy định do kiểm thử tạo được bãi bỏ ở cuối.
"""

from __future__ import annotations

import sys
import time
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_regulation_rejection as rej
import test_report_scenarios as t

SUFFIX = uuid.uuid4().hex[:4].upper()
OLD, NEW = f"QD-CU-{SUFFIX}", f"QD-MOI-{SUFFIX}"
OLD_TEXT = ("Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 4 triệu đồng không được tự động duyệt, bắt buộc Kế "
            "toán phê duyệt thủ công kèm nghiệm thu độc lập.")
NEW_TEXT = ("Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 6 triệu đồng không được tự động duyệt, bắt buộc Kế "
            "toán phê duyệt thủ công kèm nghiệm thu độc lập.")


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


REQUESTS: list[str] = []


def refund(o, amount: int) -> str:
    rid, _, _ = t.submit(o, "REFUND_COMPENSATION", None, {
        "title": "Hoàn tiền kiểm thử thay thế quy định", "order_code": f"DH-{uuid.uuid4().hex[:6].upper()}",
        "amount_vnd": amount, "reason": "Kiểm thử quy định mới thay thế quy định cũ",
        "customer_reference": "KH-KIEM-THU"})
    o.wait("""SELECT 1 FROM eas.request r WHERE r.id=%s AND (r.status <> 'PENDING_APPROVAL' OR EXISTS (
                SELECT 1 FROM eas.outbox_event e WHERE e.request_id=r.id AND e.event_type='APPROVAL_REQUESTED'
                AND e.state IN ('SENT','DEAD')))""", rid, timeout=40)
    REQUESTS.append(rid)
    return rid


def escalated_to(o, rid) -> str | None:
    row = o.one("SELECT details->>'to_lifecycle' FROM eas.audit_event WHERE request_id=%s AND action='AI_ESCALATED' "
                "ORDER BY seq DESC LIMIT 1", rid)
    return row[0] if row else None


def publish(code, title, content):
    st, body = rej.admin().call("POST", "/api/v1/admin/regulations",
                                {"code": code, "title": title, "category": "Quy định chung", "content": content})
    check(st == 201, f"ban hành {code} thất bại: {st} {body}")
    return body


def rules_of(o, code):
    policy = o.one("SELECT applied_policy FROM eas.ai_system_state WHERE id=1")[0]
    return [r for r in policy["rules"] if r.get("source_code") == code or r["id"].startswith(f"{code}-")]


def sp_01(o) -> dict:
    publish(OLD, "Quy định hoàn tiền (cũ)", OLD_TEXT)
    status = rej.wait_learning(o)
    check(status[0] == "APPLIED", f"AI không áp dụng QD cũ: {status}")
    rid = refund(o, 5_000_000)
    check(escalated_to(o, rid) == "C", f"đơn 5 triệu không bị chuyển C theo QD cũ: {escalated_to(o, rid)}")
    return {"pass": True, "evidence": f"{OLD} áp dụng; {o.req(rid)['code']} hoàn 5 tr -> chuyển C"}


def sp_02(o) -> dict:
    st, body = rej.admin().call("POST", "/api/v1/admin/regulations/validate",
                                {"code": NEW, "title": "Quy định hoàn tiền (mới)", "content": NEW_TEXT})
    v = body["validation"]
    check(st == 200 and v["ok"], f"văn bản mới bị chặn: {v}")
    hit = [x for x in v["supersedes"] if x["related"]["code"] == OLD]
    check(hit, f"AI không báo sẽ thay thế {OLD}: {v['supersedes']}")
    return {"pass": True, "evidence": f"không lỗi; {hit[0]['message'][:150]}…"}


def sp_03(o) -> dict:
    publish(NEW, "Quy định hoàn tiền (mới)", NEW_TEXT)
    status = rej.wait_learning(o)
    check(status[0] == "APPLIED", f"AI không áp dụng QD mới: {status}")
    check(not rules_of(o, OLD), f"luật của {OLD} vẫn trong bộ luật AI: {rules_of(o, OLD)}")
    check(rules_of(o, NEW), f"luật của {NEW} không có trong bộ luật AI")
    _st, body = rej.admin().call("GET", "/api/v1/admin/regulations")
    old_item = next(r for r in body["regulations"] if r["code"] == OLD)
    check(old_item["superseded_by"] and old_item["superseded_by"][0]["new_code"] == NEW,
          f"trang Quy định không ghi {OLD} đã bị thay thế: {old_item.get('superseded_by')}")
    r5 = refund(o, 5_000_000)
    check(escalated_to(o, r5) is None, f"đơn 5 triệu vẫn bị chuyển {escalated_to(o, r5)} (luật cũ còn hiệu lực)")
    r7 = refund(o, 7_000_000)
    check(escalated_to(o, r7) == "C", f"đơn 7 triệu không bị chuyển C theo QD mới: {escalated_to(o, r7)}")
    ann = o.one("SELECT changes FROM eas.system_announcement WHERE audience='ALL' ORDER BY created_at DESC LIMIT 1")
    titles = [c.get("title", "") for c in (ann[0] if ann else [])]
    check(any(NEW in x and OLD in x and "thay thế" in x for x in titles), f"thông báo thiếu dòng thay thế: {titles}")
    return {"pass": True, "evidence": (f"{NEW} áp dụng, luật {OLD} rời bộ luật; {o.req(r5)['code']} 5 tr không chuyển; "
                                       f"{o.req(r7)['code']} 7 tr chuyển C; thông báo: “{titles[0][:120]}…”")}


def sp_04(o) -> dict:
    st, body = rej.admin().call("POST", "/api/v1/admin/regulations",
                                {"code": f"QD-TU-{SUFFIX}", "title": "Tự mâu thuẫn", "category": "Quy định chung",
                                 "content": rej.CONTRADICTION})
    check(st == 422 and body["validation"]["errors"][0]["kind"] == "CONTRADICTION",
          f"văn bản tự mâu thuẫn không bị chặn: {st} {body}")
    return {"pass": True, "evidence": "văn bản tự mâu thuẫn vẫn bị chặn 422"}


def cleanup(o) -> None:
    a = rej.admin()
    for code in (NEW, OLD):
        row = o.one("SELECT id::text FROM eas.company_regulations WHERE code=%s AND NOT is_deleted", code)
        if row:
            a.call("DELETE", f"/api/v1/admin/regulations/{row[0]}", {})
            rej.wait_learning(o)
    for rid in REQUESTS:  # hồ sơ kiểm thử còn chờ duyệt: người duyệt từ chối, không để treo
        if o.req(rid)["status"] == "PENDING_APPROVAL":
            try:
                t.decide(o, rid, "REJECT", "Dọn dữ liệu kiểm thử trực tiếp: từ chối hồ sơ kiểm thử còn treo.")
            except AssertionError:
                pass


def main() -> int:
    t._guard()
    o = t.Oracle()
    rej.wait_learning(o)
    results = []
    try:
        for code, fn in {"SP-01": sp_01, "SP-02": sp_02, "SP-03": sp_03, "SP-04": sp_04}.items():
            start = time.time()
            try:
                r = fn(o)
            except Exception as exc:  # noqa: BLE001
                r = {"pass": False,
                     "evidence": str(exc) if isinstance(exc, AssertionError) else traceback.format_exc()}
            results.append(r)
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {code}  ({time.time() - start:5.1f}s)  {r['evidence']}", flush=True)
    finally:
        cleanup(o)
    print(f"\nKẾT QUẢ: {sum(r['pass'] for r in results)}/{len(results)} PASS")
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
