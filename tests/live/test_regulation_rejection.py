r"""Kiểm thử trực tiếp: AI đọc văn bản quy định, trả lỗi từng câu, trả lại bản lỗi và quay hiệu lực về bản cũ (migration 26).

Chạy trên BẢN SAO CSDL local (đã chạy migration 26), cùng biến môi trường với test_report_scenarios.py:
  set EAS_LIVE_ORACLE_DSN=postgresql://supabase_admin:postgres@127.0.0.1:55322/postgres
  set EAS_LIVE_PASSWORD=Password@123456
  .venv\Scripts\python.exe tests\live\test_regulation_rejection.py [--json out.json] [--skip-technical]

RV-01  Ban hành văn bản tự mâu thuẫn -> 422, AI chỉ rõ Điều nào chồng Điều nào; không lưu, không khoá hệ thống.
RV-02  "AI kiểm tra trước": văn bản hỏng mã hóa -> lỗi ký tự; văn bản đúng -> không lỗi, đếm số luật hiểu được.
RV-03  Văn bản lỗi lọt vào lượt học (nạp thẳng vào CSDL, không qua API) -> AI đọc, trả lại: gỡ khỏi hiệu lực, lưu bản
       bị trả lại + lỗi, báo admin, mở khoá; bộ luật AI giữ nguyên.
RV-04  Admin "Sửa và nạp lại" đúng mã đó -> bản bị trả lại chuyển RESOLVED, AI học và áp dụng.
RV-05  Lỗi kỹ thuật (tạm dừng ai-service khi AI đang học bản sửa) -> sau mọi lần thử: nội dung quay về bản đã áp
       dụng, bản bị trả lại (TECHNICAL) giữ nguyên nội dung để nạp lại, admin được báo. Mất khoảng 2-3 phút.
Quy định do kiểm thử tạo được bãi bỏ ở cuối.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_report_scenarios as t

ROOT = Path(__file__).resolve().parents[2]
CODE = "QD-KT-" + uuid.uuid4().hex[:5].upper()
GOOD = ("Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 7 triệu đồng không được tự động duyệt, bắt buộc Kế "
        "toán phê duyệt thủ công kèm nghiệm thu độc lập.")
GOOD_EDIT = ("Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 9 triệu đồng không được tự động duyệt, bắt buộc "
             "Kế toán phê duyệt thủ công kèm nghiệm thu độc lập.")
CONTRADICTION = ("Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 5 triệu đồng được phép tự động duyệt. "
                 "Điều 2: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 3 triệu đồng không được tự động duyệt.")
MOJIBAKE = "Äiá»u 1: YÃªu cáº§u Nghá»‰ phÃ©p tá»« 5 ngÃ y báº¯t buá»™c duyá»‡t thá»§ cÃ´ng."


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def admin():
    return t.login("admin@eas.com", portal="admin")


def wait_learning(o, timeout=420) -> tuple:
    end = time.time() + timeout
    while time.time() < end:
        busy = o.one("SELECT count(*) FROM eas.ai_learning_job WHERE status IN ('QUEUED','RUNNING')")[0]
        if not busy:
            return o.one("SELECT status, error FROM eas.ai_learning_job ORDER BY created_at DESC LIMIT 1")
        time.sleep(3)
    raise AssertionError("AI chưa học xong sau thời gian chờ")


def rv_01(o) -> dict:
    jobs = o.one("SELECT count(*) FROM eas.ai_learning_job")[0]
    st, body = admin().call("POST", "/api/v1/admin/regulations",
                            {"code": CODE, "title": "Quy định kiểm thử mâu thuẫn", "category": "Quy định chung",
                             "content": CONTRADICTION})
    check(st == 422 and body["error"]["code"] == "REGULATION_INVALID", f"mong 422 REGULATION_INVALID, được {st} {body}")
    errors = body["validation"]["errors"]
    check(errors and errors[0]["kind"] == "CONTRADICTION", f"không thấy lỗi mâu thuẫn: {errors}")
    check("Điều 1" in errors[0]["message"] and "Điều 2" in errors[0]["message"], "lỗi không chỉ rõ hai điều")
    saved = o.one("SELECT count(*) FROM eas.company_regulations WHERE code=%s", CODE)[0]
    check(saved == 0, "văn bản lỗi vẫn bị lưu")
    check(o.one("SELECT count(*) FROM eas.ai_learning_job")[0] == jobs, "vẫn tạo lượt học / khoá hệ thống")
    return {"pass": True, "evidence": f"422, AI: {errors[0]['message'][:160]}…; không lưu, không khoá"}


def rv_02(o) -> dict:
    a = admin()
    st, bad = a.call("POST", "/api/v1/admin/regulations/validate",
                     {"code": CODE, "title": "Quy định lỗi mã hóa", "content": MOJIBAKE})
    check(st == 200 and not bad["validation"]["ok"], f"văn bản hỏng mã hóa không bị bắt: {st} {bad}")
    check(bad["validation"]["errors"][0]["kind"] == "GARBLED", "sai loại lỗi")
    st, good = a.call("POST", "/api/v1/admin/regulations/validate",
                      {"code": CODE, "title": "Quy định hoàn tiền", "content": GOOD})
    check(st == 200 and good["validation"]["ok"] and good["validation"]["rules"] >= 1, f"văn bản đúng bị chặn: {good}")
    check(o.one("SELECT count(*) FROM eas.company_regulations WHERE code=%s", CODE)[0] == 0, "kiểm tra trước lại lưu")
    return {"pass": True, "evidence": (f"hỏng mã hóa -> {bad['validation']['errors'][0]['message'][:90]}…; "
                                       f"văn bản đúng -> ok, hiểu {good['validation']['rules']} luật")}


def rv_03(o) -> dict:
    before_rules = o.one("SELECT applied_policy FROM eas.ai_system_state WHERE id=1")[0]
    # Lọt qua kênh khác API (nhập thẳng CSDL): lượt học vẫn phải đọc và trả lại.
    o.one("INSERT INTO eas.company_regulations(code, title, category, content, updated_by) "
          "VALUES (%s, 'Quy định kiểm thử lọt lỗi', 'Quy định chung', %s, 'Nhập thẳng CSDL') RETURNING 1",
          CODE, CONTRADICTION)
    st, body = admin().call("POST", "/api/v1/admin/ai-engine/retrain", {})
    check(st == 200, f"không xếp được lượt học: {st} {body}")
    wait_learning(o)
    active = o.one("SELECT count(*) FROM eas.company_regulations WHERE code=%s AND NOT is_deleted", CODE)[0]
    check(active == 0, "văn bản lỗi vẫn còn hiệu lực")
    rej = o.one("SELECT state, cause, action, errors, message FROM eas.regulation_rejection WHERE regulation_code=%s "
                "ORDER BY created_at DESC LIMIT 1", CODE)
    check(rej and rej[0] == "OPEN" and rej[1] == "VALIDATION", f"không có bản bị trả lại OPEN: {rej}")
    check(any(e.get("kind") == "CONTRADICTION" for e in rej[3]), "bản bị trả lại thiếu danh sách lỗi")
    ann = o.one("SELECT title, summary FROM eas.system_announcement WHERE audience='ADMIN' AND kind='REGULATION_REJECTED' "
                "ORDER BY created_at DESC LIMIT 1")
    check(ann and CODE in ann[0], f"admin không được báo: {ann}")
    state = o.one("SELECT client_maintenance_lock, applied_policy FROM eas.ai_system_state WHERE id=1")
    check(state[0] is False, "hệ thống vẫn khoá bảo trì")
    check(state[1] == before_rules, "bộ luật AI bị thay đổi")
    hist = o.one("SELECT change_summary FROM eas.regulation_versions v JOIN eas.company_regulations r ON r.id=v.regulation_id "
                 "WHERE r.code=%s ORDER BY v.created_at DESC LIMIT 1", CODE)
    return {"pass": True, "evidence": (f"lượt học trả lại {CODE} ({rej[2]}): {rej[4][:120]}…; báo admin “{ann[0]}”; "
                                       f"mở khoá, bộ luật giữ nguyên; lịch sử: “{hist and hist[0]}”")}


def rv_04(o) -> dict:
    st, body = admin().call("POST", "/api/v1/admin/regulations",
                            {"code": CODE, "title": "Quy định kiểm thử hoàn tiền", "category": "Quy định chung",
                             "content": GOOD})
    check(st == 201, f"nạp lại bản đã sửa thất bại: {st} {body}")
    status = wait_learning(o)
    check(status[0] == "APPLIED", f"AI không áp dụng bản đã sửa: {status}")
    open_left = o.one("SELECT count(*) FROM eas.regulation_rejection WHERE regulation_code=%s AND state='OPEN'", CODE)[0]
    check(open_left == 0, "bản bị trả lại chưa chuyển RESOLVED sau khi nạp lại")
    rules = o.one("SELECT applied_policy FROM eas.ai_system_state WHERE id=1")[0]["rules"]
    check(any(str(r.get("id", "")).startswith(CODE) for r in rules), "luật của bản sửa không có trong bộ luật AI")
    return {"pass": True, "evidence": f"nạp lại {CODE} -> {status[0]}, bản bị trả lại RESOLVED, luật có hiệu lực"}


def rv_05(o) -> dict:
    reg_id = o.one("SELECT id::text FROM eas.company_regulations WHERE code=%s AND NOT is_deleted", CODE)[0]
    subprocess.run(["docker", "compose", "stop", "ai-service"], cwd=ROOT, check=True, capture_output=True)
    try:
        st, body = admin().call("PATCH", f"/api/v1/admin/regulations/{reg_id}",
                                {"title": "Quy định kiểm thử hoàn tiền", "content": GOOD_EDIT,
                                 "change_summary": "Kiểm thử: nâng ngưỡng hoàn tiền"})
        check(st == 200, f"sửa quy định thất bại: {st} {body}")
        status = wait_learning(o, timeout=480)
    finally:
        subprocess.run(["docker", "compose", "start", "ai-service"], cwd=ROOT, check=True, capture_output=True)
    check(status[0] == "FAILED", f"mong lượt học thất bại khi AI tắt, được {status}")
    content = o.one("SELECT content FROM eas.company_regulations WHERE code=%s AND NOT is_deleted", CODE)[0]
    check(content == GOOD, "nội dung không quay về bản đã áp dụng")
    rej = o.one("SELECT cause, rejected_content, state FROM eas.regulation_rejection WHERE regulation_code=%s "
                "ORDER BY created_at DESC LIMIT 1", CODE)
    check(rej and rej[0] == "TECHNICAL" and rej[1] == GOOD_EDIT and rej[2] == "OPEN",
          f"bản bị trả lại (kỹ thuật) không giữ nội dung bản sửa: {rej}")
    lock = o.one("SELECT client_maintenance_lock FROM eas.ai_system_state WHERE id=1")[0]
    check(lock is False, "hệ thống vẫn khoá")
    return {"pass": True, "evidence": (f"AI tắt -> {status[0]} sau mọi lần thử; nội dung {CODE} quay về bản đã áp dụng; "
                                       "bản sửa được giữ (TECHNICAL, OPEN) để nạp lại; đã mở khoá")}


def cleanup(o) -> None:
    a = admin()
    for (rid,) in o.all("SELECT id::text FROM eas.regulation_rejection WHERE regulation_code=%s AND state='OPEN'", CODE):
        a.call("POST", f"/api/v1/admin/regulations/rejections/{rid}/dismiss", {"note": "Dọn sau kiểm thử trực tiếp"})
    row = o.one("SELECT id::text FROM eas.company_regulations WHERE code=%s AND NOT is_deleted", CODE)
    if row:
        a.call("DELETE", f"/api/v1/admin/regulations/{row[0]}", {})
        wait_learning(o)


CASES = {"RV-01": rv_01, "RV-02": rv_02, "RV-03": rv_03, "RV-04": rv_04, "RV-05": rv_05}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--skip-technical", action="store_true")
    a = ap.parse_args()
    t._guard()
    o = t.Oracle()
    wait_learning(o)
    results = []
    try:
        for code, fn in CASES.items():
            if a.skip_technical and code == "RV-05":
                continue
            start = time.time()
            try:
                r = fn(o)
            except Exception as exc:  # noqa: BLE001
                r = {"pass": False,
                     "evidence": str(exc) if isinstance(exc, AssertionError) else traceback.format_exc()}
            results.append({"code": code, "seconds": round(time.time() - start, 1), **r})
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {code}  ({time.time() - start:5.1f}s)  {r['evidence']}", flush=True)
    finally:
        cleanup(o)
    print(f"\nKẾT QUẢ: {sum(r['pass'] for r in results)}/{len(results)} PASS")
    if a.json:
        Path(a.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if all(r["pass"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
