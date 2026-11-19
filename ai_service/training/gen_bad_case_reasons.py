"""Sinh dữ liệu HUẤN LUYỆN cho bộ phân loại lý do thu hồi tự duyệt (ai_service/bad_case_reason.py).

Nguồn duy nhất là mô tả trong danh mục bad case (data/bad_case_catalog.json) và mô tả các đặc trưng đo
được; Gemini KHÔNG thấy bộ kiểm tra (training/data/bad_case_reasons_test.json, băm trước). Không gửi dữ
liệu cá nhân hay hồ sơ thật.

  ai_service\\.venv-ai\\Scripts\\python -I ai_service\\training\\gen_bad_case_reasons.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from bad_case_reason import FEATURES
from regulation_llm import call_gemini

OUT = Path(__file__).resolve().parent / "data" / "bad_case_reasons_train.json"
OUT_V2 = Path(__file__).resolve().parent / "data" / "bad_case_reasons_train2.json"
OUT_V3 = Path(__file__).resolve().parent / "data" / "bad_case_reasons_train3.json"
A_TYPES = [
    "LEAVE", "LEAVE_SPECIAL", "ATTENDANCE_ADJUSTMENT", "WFH_REQ", "EXPENSE_CLAIM",
    "REFUND_COMPENSATION", "SPECIAL_DISCOUNT", "ROOM_BOOKING", "VISITOR_SECURITY_PASS",
]

COMMON = """Bối cảnh: hệ thống phê duyệt nội bộ EAS cho phép AI tự duyệt một số đơn đơn giản (nghỉ phép, WFH, điều chỉnh
chấm công, thanh toán chi phí, hoàn tiền, chiết khấu, đặt phòng họp, thẻ khách). Trong 24 giờ, người quản lý có thể
THU HỒI quyết định tự duyệt và phải ghi LÝ DO (1-2 câu, văn nói của quản lý Việt Nam, đa dạng cách viết, có câu ngắn,
có câu dài, có câu gõ tắt). Không dùng tên người thật đầy đủ (chỉ tên gọi ngắn như "Lan", "anh Tú" nếu cần).
"""

PROMPT_CASE = COMMON + """
Hãy viết {n} lý do thu hồi KHÁC NHAU mà người quản lý viết khi phát hiện đúng tình huống sau:
Tình huống: {title}
Tác hại: {harm}
Điều kiện nhận biết: {condition}
Áp dụng cho loại đơn: {types}
Chỉ trả JSON: {{"reasons": [{{"type": "MÃ LOẠI", "reason": "..."}}]}}"""

PROMPT_NEW = COMMON + """
Hãy viết {n} lý do thu hồi KHÁC NHAU cho các KIỂU RỦI RO LẶP LẠI ĐƯỢC (sẽ còn gặp ở người khác, nên thành quy tắc chung)
nhưng KHÔNG thuộc các tình huống đã có sau đây:
{known}
Mỗi lý do gắn một đặc trưng đo được nếu có (chọn đúng một khóa) hoặc null nếu không đo được bằng dữ liệu hệ thống:
{features}
Trải đều các đặc trưng; khoảng 1/4 số lý do là null (ví dụ khách là đối thủ, mùa cao điểm nội bộ, khách hàng nợ xấu...).
Chỉ trả JSON: {{"reasons": [{{"type": "MÃ LOẠI", "reason": "...", "feature": "khóa hoặc null"}}]}}"""

PROMPT_ONE_OFF = COMMON + """
Hãy viết {n} lý do thu hồi KHÁC NHAU chỉ đúng với RIÊNG hồ sơ đó, KHÔNG phải kiểu rủi ro chung: nhập sai thông tin, thiếu
hoặc sai chứng từ/đính kèm, cần trao đổi trực tiếp, người gửi muốn hủy/sửa, sự cố riêng (phòng hỏng, lịch dời, lãnh đạo
cần dùng), đã xử lý ngoài hệ thống, quản lý duyệt nhầm... Đa dạng loại đơn: {types}.
Chỉ trả JSON: {{"reasons": [{{"type": "MÃ LOẠI", "reason": "..."}}]}}"""


STYLE_V2 = """
Văn phong (lượt 2): câu NGẮN 6-25 từ như người duyệt gõ nhanh vào ô lý do; trộn câu trang trọng và câu nói; khoảng 1/5
số câu gõ không dấu, viết thường. Không mở đầu bằng "Thu hồi", không xưng hô dài dòng."""

PROMPT_PAIRS = COMMON + STYLE_V2 + """
Viết {n} CẶP lý do thu hồi. Mỗi cặp cùng chủ đề, cùng loại đơn nhưng khác bản chất:
- "pattern": KIỂU RỦI RO CHUNG, sẽ lặp lại ở người khác hoặc lần sau (thói quen, thời điểm bất thường, quy mô bất thường,
  lịch sử xấu của người gửi, nhóm khách/đối tác rủi ro...). Dấu hiệu: "lần nào cũng", "hay", "thường", "cứ", "bất thường",
  "quá sát", "dồn dập", "vào dịp"...; KHÔNG thuộc các tình huống đã có sau:
{known}
  Gắn đặc trưng đo được (một khóa) hoặc null:
{features}
- "one_off": CHỈ ĐÚNG VỚI RIÊNG HỒ SƠ NÀY: nhập sai, thiếu/sai chứng từ, cần bổ sung, người gửi đổi ý/hủy, lịch dời, sự cố
  riêng, đã xử lý ngoài hệ thống, quản lý muốn trao đổi trực tiếp.
Đa dạng loại đơn: {types}.
Chỉ trả JSON: {{"pairs": [{{"type": "MÃ LOẠI", "pattern": "...", "feature": "khóa hoặc null", "one_off": "..."}}]}}"""


def ask_pairs(prompt: str, key: str, model: str) -> list[dict]:
    for attempt in range(3):
        try:
            raw = json.loads(call_gemini(prompt, key, model, timeout=120)["text"])
            items = raw if isinstance(raw, list) else raw.get("pairs") or []
            return [i for i in items if isinstance(i, dict) and i.get("pattern") and i.get("one_off")]
        except Exception as exc:  # noqa: BLE001
            print(f"  lỗi lần {attempt + 1}: {type(exc).__name__}: {str(exc)[:120]}")
            time.sleep(8 * (attempt + 1))
    return []


def generate_v2(key: str, model: str, catalog: dict, per_case: int, rounds: int) -> None:
    """Lượt 2 (sau khi phiên bản 1 trượt bộ test 1): câu ngắn, cặp tương phản pattern / one_off."""
    items: list[dict] = []
    for case in catalog["cases"]:
        types = [t for t in case["request_types"] if t in A_TYPES] or A_TYPES
        got = ask(PROMPT_CASE.format(n=per_case, title=case["title"], harm=case.get("harm", ""),
                                     condition=case.get("condition", ""), types=", ".join(types)) + STYLE_V2,
                  key, model)
        print(f"{case['code']}: {len(got)}")
        items += [{"type": str(i.get("type") or types[0]), "reason": i["reason"].strip(), "label": case["code"],
                   "source": "gemini-v2"} for i in got]
    known = "\n".join(f"  * {c['title']}" for c in catalog["cases"])
    features = "\n".join(f"  * {k}: {v['label']}" for k, v in FEATURES.items() if v.get("request_level"))
    for r in range(rounds):
        got = ask_pairs(PROMPT_PAIRS.format(n=30, known=known, features=features, types=", ".join(A_TYPES)),
                        key, model)
        print(f"cặp lượt {r + 1}: {len(got)}")
        for i in got:
            feat = i.get("feature") if i.get("feature") in FEATURES else None
            items.append({"type": str(i.get("type") or "LEAVE"), "reason": str(i["pattern"]).strip(),
                          "label": "NEW_PATTERN", "feature": feat, "source": "gemini-v2-pair"})
            items.append({"type": str(i.get("type") or "LEAVE"), "reason": str(i["one_off"]).strip(),
                          "label": "ONE_OFF", "source": "gemini-v2-pair"})
    seen, unique = set(), []
    for item in items:
        k = " ".join(item["reason"].lower().split())
        if k not in seen:
            seen.add(k)
            unique.append(item)
    OUT_V2.write_text(json.dumps({"about": "Lượt 2 của gen_bad_case_reasons.py (--v2); không thấy bộ kiểm tra.",
                                  "model": model, "items": unique}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ghi {len(unique)} câu -> {OUT_V2}")


def ask(prompt: str, key: str, model: str, tries: int = 3, timeout: int = 90) -> list[dict]:
    for attempt in range(tries):
        try:
            raw = json.loads(call_gemini(prompt, key, model, timeout=timeout)["text"])
            items = raw if isinstance(raw, list) else raw.get("reasons") or []
            return [i for i in items if isinstance(i, dict) and str(i.get("reason", "")).strip()]
        except Exception as exc:  # noqa: BLE001
            print(f"  lỗi lần {attempt + 1}: {type(exc).__name__}: {str(exc)[:120]}")
            time.sleep(8 * (attempt + 1))
    return []


STYLE_V3 = """
Văn phong (lượt 3, ca OÁI OĂM): trộn đều các kiểu sau, mỗi kiểu vài câu:
- gõ không dấu, viết thường; viết tắt (ko, k, dc, j, nv, sếp); sai chính tả nhẹ;
- trộn tiếng Anh (deadline, task, book, refund, WFH, sale, OT);
- câu cực ngắn (2-5 từ) và câu dài vòng vo, lịch sự;
- PHỦ ĐỊNH: "không phải vì X mà vì Y" (nhãn theo Y);
- câu hỏi tu từ, giọng mỉa nhẹ."""

PROMPT_TYPE_CONTRAST = COMMON + STYLE_V3 + """
Loại đơn: {type_name} ({type_code}). Bad case ĐÃ CÓ của loại này: {known}.
Viết {n} lý do thu hồi cho loại đơn này mà KHÔNG thuộc các bad case đã có ở trên, dù có thể nhắc tới tên loại đơn
(ví dụ đơn WFH nhưng lý do là báo sát giờ, hoặc thiếu kế hoạch làm việc, chứ không phải WFH quá nhiều). Chia đều:
- "pattern": kiểu rủi ro CHUNG lặp lại được (thói quen, thời điểm, quy mô bất thường, lịch sử xấu, đối tác rủi ro...),
  kèm đặc trưng đo được (một khóa) hoặc null:
{features}
- "one_off": chỉ đúng với RIÊNG hồ sơ này (nhập sai, thiếu giấy tờ, đổi ý, lịch dời, sự cố riêng, đã xử lý ngoài).
Chỉ trả JSON: {{"reasons": [{{"kind": "pattern|one_off", "reason": "...", "feature": "khóa hoặc null"}}]}}"""

PROMPT_CASE_V3 = COMMON + STYLE_V3 + """
Viết {n} lý do thu hồi KHÁC NHAU mà người quản lý viết khi phát hiện đúng tình huống sau (dù diễn đạt oái oăm):
Tình huống: {title}
Tác hại: {harm}
Điều kiện nhận biết: {condition}
Áp dụng cho loại đơn: {types}
Chỉ trả JSON: {{"reasons": [{{"type": "MÃ LOẠI", "reason": "..."}}]}}"""

TYPE_NAMES = {
    "LEAVE": "Nghỉ phép", "LEAVE_SPECIAL": "Nghỉ phép đặc biệt", "ATTENDANCE_ADJUSTMENT": "Điều chỉnh chấm công",
    "WFH_REQ": "Làm việc từ xa (WFH)", "EXPENSE_CLAIM": "Thanh toán chi phí", "REFUND_COMPENSATION": "Hoàn tiền / Đền bù",
    "SPECIAL_DISCOUNT": "Chiết khấu thương mại đặc biệt", "ROOM_BOOKING": "Đặt phòng họp",
    "VISITOR_SECURITY_PASS": "Thẻ an ninh khách ra vào",
}


V3_BATCH = 20  # 40 câu/lần mất ~66 giây với flash-lite, sát ngưỡng timeout: chia lô nhỏ
V3_TIMEOUT = 180


def generate_v3(key: str, model: str, catalog: dict, per_case: int, per_type: int) -> None:
    """Lượt 3: phủ định đúng loại (lý do nhắc tới loại đơn nhưng không phải bad case của loại đó) + văn phong oái oăm.

    Mỗi lô ghi ngay vào tệp .partial.json; chạy lại thì bỏ qua lô đã xong.
    """
    partial_path = OUT_V3.with_suffix(".partial.json")
    done: dict[str, list[dict]] = (
        json.loads(partial_path.read_text(encoding="utf-8")) if partial_path.exists() else {}
    )
    features = "\n".join(f"  * {k}: {v['label']}" for k, v in FEATURES.items() if v.get("request_level"))
    jobs: list[tuple[str, str, str, list[str]]] = []  # (id, prompt, nguồn, loại đơn)
    for code in A_TYPES:
        known = "; ".join(c["title"] for c in catalog["cases"] if code in c["request_types"] or "*" in c["request_types"])
        for b in range(0, per_type, V3_BATCH):
            prompt = PROMPT_TYPE_CONTRAST.format(type_name=TYPE_NAMES[code], type_code=code,
                                                 known=known or "(không có)", n=min(V3_BATCH, per_type - b),
                                                 features=features)
            jobs.append((f"contrast:{code}:{b}", prompt, "contrast", [code]))
    for case in catalog["cases"]:
        types = [t for t in case["request_types"] if t in A_TYPES] or A_TYPES
        for b in range(0, per_case, V3_BATCH):
            prompt = PROMPT_CASE_V3.format(n=min(V3_BATCH, per_case - b), title=case["title"],
                                           harm=case.get("harm", ""), condition=case.get("condition", ""),
                                           types=", ".join(types))
            jobs.append((f"case:{case['code']}:{b}", prompt, "case", types))
    for n, (job_id, prompt, _kind, _types) in enumerate(jobs, 1):
        if job_id in done:
            continue
        started = time.monotonic()
        got = ask(prompt, key, model, timeout=V3_TIMEOUT)
        if got:
            done[job_id] = got
            partial_path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
        print(f"[{n}/{len(jobs)}] {job_id}: {len(got)} câu, {time.monotonic() - started:.0f}s", flush=True)

    items: list[dict] = []
    for job_id, _prompt, kind, types in jobs:
        for i in done.get(job_id, []):
            if kind == "contrast":
                label = str(i.get("kind") or "").lower()
                if label not in ("pattern", "one_off"):
                    continue
                feat = i.get("feature") if i.get("feature") in FEATURES else None
                items.append({"type": types[0], "reason": i["reason"].strip(), "source": "gemini-v3-contrast",
                              "label": "NEW_PATTERN" if label == "pattern" else "ONE_OFF",
                              **({"feature": feat} if label == "pattern" else {})})
            else:
                items.append({"type": str(i.get("type") or types[0]), "reason": i["reason"].strip(),
                              "label": job_id.split(":")[1], "source": "gemini-v3-tricky"})
    seen, unique = set(), []
    for item in items:
        k = " ".join(item["reason"].lower().split())
        if k not in seen:
            seen.add(k)
            unique.append(item)
    missing = [j[0] for j in jobs if j[0] not in done]
    OUT_V3.write_text(json.dumps({"about": "Lượt 3 của gen_bad_case_reasons.py (--v3): phủ định đúng loại + văn phong oái "
                                           "oăm; không thấy bộ kiểm tra.", "model": model, "missing_batches": missing,
                                  "items": unique}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ghi {len(unique)} câu -> {OUT_V3} (thiếu {len(missing)} lô)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"))
    ap.add_argument("--per-case", type=int, default=30)
    ap.add_argument("--rounds", type=int, default=4, help="số lượt cho NEW_PATTERN / ONE_OFF (mỗi lượt 40 câu)")
    ap.add_argument("--v2", action="store_true", help="lượt 2: câu ngắn + cặp tương phản")
    ap.add_argument("--v3", action="store_true", help="lượt 3: phủ định đúng loại + văn phong oái oăm")
    args = ap.parse_args()
    key = os.environ["GEMINI_API_KEY"]
    catalog = json.loads((AI_DIR / "data" / "bad_case_catalog.json").read_text(encoding="utf-8"))
    if args.v3:
        generate_v3(key, args.model, catalog, args.per_case, 40)
        return
    if args.v2:
        generate_v2(key, args.model, catalog, args.per_case, args.rounds)
        return
    items: list[dict] = []

    for case in catalog["cases"]:
        types = [t for t in case["request_types"] if t in A_TYPES] or A_TYPES
        got = ask(PROMPT_CASE.format(n=args.per_case, title=case["title"], harm=case.get("harm", ""),
                                     condition=case.get("condition", ""), types=", ".join(types)), key, args.model)
        print(f"{case['code']}: {len(got)}")
        items += [{"type": str(i.get("type") or types[0]), "reason": i["reason"].strip(), "label": case["code"],
                   "source": "gemini"} for i in got]

    known = "\n".join(f"- {c['title']}" for c in catalog["cases"])
    features = "\n".join(f"- {k}: {v['label']}" for k, v in FEATURES.items() if v.get("request_level"))
    for r in range(args.rounds):
        got = ask(PROMPT_NEW.format(n=40, known=known, features=features), key, args.model)
        print(f"NEW_PATTERN lượt {r + 1}: {len(got)}")
        for i in got:
            feat = i.get("feature")
            feat = feat if feat in FEATURES else None
            items.append({"type": str(i.get("type") or "LEAVE"), "reason": i["reason"].strip(),
                          "label": "NEW_PATTERN", "feature": feat, "source": "gemini"})
        got = ask(PROMPT_ONE_OFF.format(n=40, types=", ".join(A_TYPES)), key, args.model)
        print(f"ONE_OFF lượt {r + 1}: {len(got)}")
        items += [{"type": str(i.get("type") or "LEAVE"), "reason": i["reason"].strip(), "label": "ONE_OFF",
                   "source": "gemini"} for i in got]

    seen, unique = set(), []
    for item in items:
        k = " ".join(item["reason"].lower().split())
        if k not in seen:
            seen.add(k)
            unique.append(item)
    OUT.write_text(json.dumps({"about": "Sinh bởi gen_bad_case_reasons.py từ mô tả danh mục; không thấy bộ kiểm tra.",
                               "model": args.model, "items": unique}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ghi {len(unique)} câu -> {OUT}")


if __name__ == "__main__":
    main()
