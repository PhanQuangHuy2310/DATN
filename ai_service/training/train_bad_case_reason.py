"""Huấn luyện + chấm bộ phân loại lý do thu hồi tự duyệt (ai_service/bad_case_reason.py).

  ai_service\\.venv-ai\\Scripts\\python -I ai_service\\training\\train_bad_case_reason.py            # chỉ CV trên train
  ai_service\\.venv-ai\\Scripts\\python -I ai_service\\training\\train_bad_case_reason.py --final    # + chấm bộ test băm
  ... --final --gemini                                                                          # + Gemini zero-shot

Bộ test (data/bad_case_reasons_test.json) được viết tay và băm trước khi sinh dữ liệu huấn luyện và cài mô hình
(commit 0c6b7ad); mã băm được kiểm tra trước khi chấm. Mô hình chỉ được chọn tham số bằng kiểm định chéo trên tập
train, không nhìn bộ test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "data"
sys.path.insert(0, str(AI_DIR))

import bad_case_reason as bcr
from nlp_text import strip_diacritics

TEST_SHA256 = "eb01b749c90bfaf6acdabffb6a5cc336bdc99ed93dfffe7fd8fc6aa1bceddc52"
# Bộ thứ hai: viết sau khi bộ thứ nhất đã chấm phiên bản 1 (và đã xem lỗi), băm TRƯỚC khi làm phiên bản 2 (c9984d7).
TEST2_SHA256 = "16cd8f18210b5f0fbaabe039218dd6af63b05f2944f23c218d6c24bb91e7e433"
# Bộ thứ ba (ca oái oăm): viết và băm TRƯỚC phiên bản 3 (commit c61b10f).
TEST3_SHA256 = "58a946a7fdabb0e97f16507cd0e39a613e253b92b7a98f1275088ce88091c043"
TESTS = {"1": ("bad_case_reasons_test.json", TEST_SHA256), "2": ("bad_case_reasons_test2.json", TEST2_SHA256),
         "3": ("bad_case_reasons_test3.json", TEST3_SHA256)}
SEED = 20261118


def group(label: str) -> str:
    return label if label in (bcr.NEW, bcr.ONE_OFF) else "EXISTING"


def load_test(which: str = "1") -> list[dict]:
    name, expected = TESTS[which]
    raw = (DATA / name).read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected:
        raise SystemExit(f"Bộ test {name} đã bị sửa (sha256 {digest}), dừng chấm.")
    return json.loads(raw)["items"]


def load_train(version: str = "v2") -> list[dict]:
    files = ["bad_case_reasons_train.json"]
    if version in ("v2", "v3"):
        files.append("bad_case_reasons_train2.json")
    if version == "v3":
        # Lượt 3: phủ định đúng loại (nhắc tên loại đơn nhưng KHÔNG phải bad case của loại đó) + văn phong oái oăm.
        files.append("bad_case_reasons_train3.json")
    items = [i for f in files for i in json.loads((DATA / f).read_text(encoding="utf-8"))["items"]]
    rng = random.Random(SEED)
    out = list(items)
    # Người dùng hay gõ không dấu trên điện thoại: thêm bản không dấu cho 30% câu.
    for item in items:
        if rng.random() < 0.3:
            out.append({**item, "reason": strip_diacritics(item["reason"]).lower(), "source": "augment-nodiac"})
    return out


# --------------------------------------------------------------------------- baseline từ khóa
KEYWORDS = [
    ("BC_DUPLICATE_INVOICE", r"hoa don.*(trung|da (duoc )?thanh toan|lan hai|hai lan)|trung so hoa don|hoa don cu"),
    ("BC_SPLIT_AMOUNT_EVASION", r"chia nho|tach .*(ho so|khoan)|ne nguong|cong lai vuot"),
    ("BC_DEADLINE_CONFLICT", r"(han|deadline|het han).*(chua (ban )?giao|chua co nguoi)|chua ban giao"),
    ("BC_HANDOVER_OVERLOADED", r"(nguoi )?(nhan|duoc) ban giao.*(nghi|qua tai|om|vang)|qua tai"),
    ("BC_TEAM_ABSENCE_PEAK", r"(phong|team|bo phan|dong nghiep).*(nghi|vang|cong tac).*(trung|nhieu|nua|khong du)|khong du nguoi"),
    ("BC_REPEATED_EXEMPTION", r"(cham cong|gio cong|sua gio).*(nhieu lan|lan thu|lien tuc)|quen cham cong"),
    ("BC_WFH_FREQUENT", r"(wfh|lam tu xa).*(nhieu|qua|lien tuc|ngay nao)"),
    ("BC_REFUND_FREQUENT", r"hoan tien.*(nhieu|don dap|lan thu|lien)"),
    ("BC_DISCOUNT_REPEAT_CUSTOMER", r"(chiet khau|giam gia).*(cung (mot )?khach|lien tiep|lap lai|tuan truoc)"),
    ("BC_REQUESTER_ABSENT_ON_EVENT", r"(nguoi dat|nguoi dang ky|chu tri|don khach).*(nghi|vang|cong tac)"),
    ("BC_AI_REVOKED_HISTORY", r"thu hoi.*(nhieu lan|lan nao|hai lan|2 lan)|(nhieu lan|lan nao).*thu hoi"),
    ("BC_OFF_HOURS_BULK", r"(nua dem|ngoai gio|2 gio sang|khuya).*(hang loat|nhieu|mot loat)|(hang loat|nhieu|mot loat).*(nua dem|ngoai gio|khuya)"),
    (bcr.NEW, r"sat gio|dot xuat|khong bao truoc|cuoi thang|chot so|khoa so|thu hai|thu sau|qua dai|bat thuong|bi tu choi|lien tiep"),
]


def keyword_predict(reason: str) -> str:
    text = bcr.fold(reason)
    for label, pattern in KEYWORDS:
        if re.search(pattern, text):
            return label
    return bcr.ONE_OFF


# --------------------------------------------------------------------------- Gemini zero-shot
GEMINI_PROMPT = """Phân loại LÝ DO người quản lý thu hồi một hồ sơ mà AI đã tự duyệt trong hệ thống phê duyệt nội bộ.
Nhãn:
{cases}
- NEW_PATTERN: kiểu rủi ro lặp lại được (sẽ gặp lại ở người khác) nhưng KHÔNG thuộc các mã trên.
- ONE_OFF: chỉ đúng với riêng hồ sơ đó (nhập sai, thiếu chứng từ, cần trao đổi, sự cố riêng...).
Loại đơn: {type}
Lý do: <<<{reason}>>>
Chỉ trả JSON: {{"label": "MÃ hoặc NEW_PATTERN hoặc ONE_OFF"}}"""


def gemini_predict(items: list[dict]) -> list[str]:
    from regulation_llm import call_gemini

    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    catalog = json.loads((AI_DIR / "data" / "bad_case_catalog.json").read_text(encoding="utf-8"))
    cases = "\n".join(f"- {c['code']}: {c['title']}" for c in catalog["cases"])
    out = []
    for item in items:
        label = "ERROR"
        for attempt in range(3):
            try:
                raw = json.loads(call_gemini(GEMINI_PROMPT.format(cases=cases, type=item["type"],
                                                                  reason=item["reason"]), key, model, 40)["text"])
                label = str(raw.get("label", "")).strip().upper() if isinstance(raw, dict) else "ERROR"
                break
            except Exception:  # noqa: BLE001
                time.sleep(5 * (attempt + 1))
        out.append(label)
    return out


# --------------------------------------------------------------------------- chấm điểm
def score(items: list[dict], preds: list[str], feats: list[str | None] | None = None) -> dict:
    n = len(items)
    exact = sum(p == i["label"] for p, i in zip(preds, items))
    grp = sum(group(p) == group(i["label"]) for p, i in zip(preds, items))
    groups = ("EXISTING", bcr.NEW, bcr.ONE_OFF)
    f1s = {}
    for g in groups:
        tp = sum(group(p) == g and group(i["label"]) == g for p, i in zip(preds, items))
        fp = sum(group(p) == g and group(i["label"]) != g for p, i in zip(preds, items))
        fn = sum(group(p) != g and group(i["label"]) == g for p, i in zip(preds, items))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s[g] = round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0
    existing = [(p, i) for p, i in zip(preds, items) if group(i["label"]) == "EXISTING"]
    out = {
        "n": n,
        "accuracy_exact": round(exact / n, 3),
        "accuracy_group": round(grp / n, 3),
        "macro_f1_group": round(sum(f1s.values()) / 3, 3),
        "f1_by_group": f1s,
        "existing_code_accuracy": round(sum(p == i["label"] for p, i in existing) / len(existing), 3),
        "one_off_called_pattern": sum(group(i["label"]) == bcr.ONE_OFF and group(p) != bcr.ONE_OFF
                                      for p, i in zip(preds, items)),
        "pattern_called_one_off": sum(group(i["label"]) != bcr.ONE_OFF and group(p) == bcr.ONE_OFF
                                      for p, i in zip(preds, items)),
        "errors": [{"id": i["id"], "gold": i["label"], "pred": p} for p, i in zip(preds, items) if p != i["label"]],
    }
    if feats is not None:
        new = [(f, i) for f, i, p in zip(feats, items, preds) if i["label"] == bcr.NEW]
        ok = sum((f or None) == i.get("feature") for f, i in new)
        out["feature_accuracy_on_new"] = round(ok / len(new), 3) if new else None
        out["feature_errors"] = [{"id": i["id"], "gold": i.get("feature"), "pred": f}
                                 for f, i in new if (f or None) != i.get("feature")]
    return out


def texts_of(items: list[dict], cfg: dict) -> list[str]:
    return [bcr.model_input(i["reason"], i.get("type"), cfg["type_token"]) for i in items]


def cross_validate(train: list[dict], cfg: dict, folds: int = 5) -> float:
    from sklearn.model_selection import StratifiedKFold

    texts = texts_of(train, cfg)
    labels = [i["label"] for i in train]
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=SEED)
    correct = 0
    for tr, te in skf.split(texts, labels):
        pipe = bcr.build_pipeline(cfg["C"], cues=cfg["cues"]).fit([texts[k] for k in tr], [labels[k] for k in tr])
        pred = pipe.predict([texts[k] for k in te])
        correct += sum(p == labels[k] for p, k in zip(pred, te))
    return correct / len(texts)


def cross_validate_feature(train: list[dict], cfg: dict, folds: int = 5) -> float:
    """Đầu đoán đặc trưng đo được: chọn cấu hình riêng bằng kiểm định chéo trên các câu NEW_PATTERN của tập train."""
    from sklearn.model_selection import StratifiedKFold

    new = [i for i in train if i["label"] == bcr.NEW]
    texts = texts_of(new, cfg)
    labels = [i.get("feature") or bcr.NO_FEATURE for i in new]
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=SEED)
    correct = 0
    for tr, te in skf.split(texts, labels):
        pipe = bcr.build_pipeline(cfg["C"]).fit([texts[k] for k in tr], [labels[k] for k in tr])
        correct += sum(p == labels[k] for p, k in zip(pipe.predict([texts[k] for k in te]), te))
    return correct / len(texts)


def fit(train: list[dict], cfg: dict, feature_cfg: dict | None = None) -> dict:
    feature_cfg = feature_cfg or {"C": cfg["C"], "type_token": cfg["type_token"]}
    label_pipe = bcr.build_pipeline(cfg["C"], cues=cfg["cues"]).fit(texts_of(train, cfg),
                                                                    [i["label"] for i in train])
    new = [i for i in train if i["label"] == bcr.NEW]
    feature_pipe = bcr.build_pipeline(feature_cfg["C"]).fit(
        texts_of(new, feature_cfg), [i.get("feature") or bcr.NO_FEATURE for i in new])
    return {"label": label_pipe, "feature": feature_pipe}


def feature_head_accuracy(model: dict, items: list[dict]) -> dict:
    """Đầu đoán đặc trưng chạy thẳng trên MỌI câu NEW_PATTERN (không phụ thuộc nhãn mô hình đoán)."""
    new = [i for i in items if i["label"] == bcr.NEW]
    tt = bool(model.get("meta", {}).get("feature_type_token", model.get("meta", {}).get("type_token")))
    preds = model["feature"].predict([bcr.model_input(i["reason"], i.get("type"), tt) for i in new])
    ok = sum((None if p == bcr.NO_FEATURE else p) == i.get("feature") for p, i in zip(preds, new))
    return {"n": len(new), "accuracy": round(ok / len(new), 3) if new else None}


def predict(model: dict, items: list[dict]) -> tuple[list[str], list[str | None]]:
    preds, feats = [], []
    for item in items:
        r = bcr.classify(item["reason"], model, item.get("type"))
        preds.append(r["label"])
        feats.append(r["feature"])
    return preds, feats


def main() -> None:
    import joblib

    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["v1", "v2", "v3"], default="v3")
    ap.add_argument("--final", action="store_true", help="chấm các bộ test đã băm")
    ap.add_argument("--tests", default="1,2", help="bộ test để chấm, vd. 1,2")
    ap.add_argument("--compare", help="tệp mô hình phiên bản trước để chấm cùng bộ test")
    ap.add_argument("--gemini", action="store_true", help="chấm thêm Gemini zero-shot")
    ap.add_argument("--json", default="")
    ap.add_argument("--score-only", help="chỉ chấm một tệp mô hình có sẵn trên --tests, không huấn luyện")
    args = ap.parse_args()

    if args.score_only:
        model = joblib.load(args.score_only)
        out = {}
        for which in args.tests.split(","):
            test = load_test(which)
            preds, feats = predict(model, test)
            sc = score(test, preds, feats)
            sc["feature_head"] = feature_head_accuracy(model, test)
            out[which] = sc
            print(f"test{which} {model.get('meta', {}).get('version')}: exact={sc['accuracy_exact']} "
                  f"group={sc['accuracy_group']} macroF1={sc['macro_f1_group']} feat_head={sc['feature_head']}")
        if args.json:
            Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return

    train = load_train(args.version)
    print("train:", len(train), Counter(group(i["label"]) for i in train))
    if args.version == "v1":
        grid = [{"C": c, "type_token": False, "cues": False} for c in (1.0, 4.0, 16.0)]
    else:
        grid = [{"C": c, "type_token": t, "cues": q} for t in (False, True) for q in (False, True)
                for c in (4.0, 16.0)]
    cv = []
    for cfg in grid:
        acc = round(cross_validate(train, cfg), 3)
        cv.append({**cfg, "cv_accuracy": acc})
        print(f"  CV {cfg}: {acc}", flush=True)
    best = max(cv, key=lambda r: r["cv_accuracy"])
    cfg = {k: best[k] for k in ("C", "type_token", "cues")}
    # Đầu đoán đặc trưng học từ dữ liệu lượt 1: nhãn đặc trưng của lượt 2 (cặp tương phản) nhiễu hơn. Kiểm định
    # chéo trên các fold của lượt 1 (thêm/không thêm toàn bộ lượt 2 vào phần học): 0.738 / 0.688 (type_token),
    # 0.688 / 0.662 (không). Quyết định này đưa ra SAU khi đã thấy kết quả bộ test 2 (ghi trong báo cáo).
    feature_train = load_train("v1") if args.version in ("v2", "v3") else train
    feature_cv = []
    for fcfg in [{"C": c, "type_token": t} for t in (False, True) for c in (4.0, 16.0)]:
        acc = round(cross_validate_feature(feature_train, fcfg), 3)
        feature_cv.append({**fcfg, "cv_accuracy": acc})
        print(f"  CV đặc trưng {fcfg}: {acc}", flush=True)
    fbest = max(feature_cv, key=lambda r: r["cv_accuracy"])
    feature_cfg = {"C": fbest["C"], "type_token": fbest["type_token"]}
    meta = {"version": {"v1": "bad-case-reason-1", "v2": "bad-case-reason-2", "v3": "bad-case-reason-3"}[args.version],
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_train": len(train), **cfg, "cv_accuracy": best["cv_accuracy"],
            "feature_C": feature_cfg["C"], "feature_type_token": feature_cfg["type_token"],
            "feature_cv_accuracy": fbest["cv_accuracy"],
            "test_sha256": {k: v[1] for k, v in TESTS.items()}}
    model = fit(train, cfg, feature_cfg)
    if args.version in ("v2", "v3"):
        model["feature"] = fit(feature_train, cfg, feature_cfg)["feature"]
        meta["feature_data"] = "train1 (lượt 1)"
    model = {**model, "meta": meta}
    results: dict = {"meta": meta, "cv": cv, "feature_cv": feature_cv, "test": {}}
    results_path = DATA / "bad_case_reason_results.json"
    if results_path.exists():
        old = json.loads(results_path.read_text(encoding="utf-8"))
        results["history"] = old.get("history", []) + [{"meta": old.get("meta"), "cv": old.get("cv"),
                                                         "test": old.get("test")}]

    if args.final:
        compare = joblib.load(args.compare) if args.compare else None
        for which in args.tests.split(","):
            test = load_test(which)
            preds, feats = predict(model, test)
            block = {"model": score(test, preds, feats),
                     "keyword_baseline": score(test, [keyword_predict(i["reason"]) for i in test])}
            block["model"]["feature_head"] = feature_head_accuracy(model, test)
            if compare is not None:
                cp, cf = predict(compare, test)
                block["previous_model"] = score(test, cp, cf)
                block["previous_model"]["feature_head"] = feature_head_accuracy(compare, test)
            if args.gemini:
                block["gemini_zero_shot"] = score(test, gemini_predict(test))
            results["test"][which] = block
            for name, sc in block.items():
                print(f"test{which} {name:16s} exact={sc['accuracy_exact']} group={sc['accuracy_group']} "
                      f"macroF1={sc['macro_f1_group']} feat={sc.get('feature_accuracy_on_new')} "
                      f"feat_head={sc.get('feature_head')}")
        meta["test"] = {w: {k: b["model"][k] for k in ("accuracy_exact", "accuracy_group", "macro_f1_group",
                                                       "feature_accuracy_on_new")}
                        for w, b in results["test"].items()}
        results_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    joblib.dump(model, bcr.MODEL_PATH)
    print("lưu", bcr.MODEL_PATH, cfg)


if __name__ == "__main__":
    main()
