"""Phân tích LÝ DO người duyệt thu hồi hồ sơ AI đã tự duyệt, để học bad case mới (yêu cầu trưởng nhóm 18/11).

Ba câu hỏi cho mỗi lý do:
  1. Lý do thuộc loại nào? (mô hình phân loại tự huấn luyện, chạy cục bộ, không gửi văn bản ra ngoài)
       - mã bad case có sẵn: AI đã biết kiểu này nhưng bỏ sót (chưa vượt ngưỡng / loại đơn chưa thuộc phạm vi);
       - NEW_PATTERN: kiểu rủi ro lặp lại được, chưa có trong danh mục;
       - ONE_OFF: chỉ đúng với riêng hồ sơ đó (nhập sai, thiếu chứng từ...), không nên thành bad case.
  2. Đo được bằng dữ liệu hệ thống không? Đầu phân loại thứ hai đoán đặc trưng (số giờ báo trước, ngày cuối
     tháng, thứ trong tuần, số ngày, số tiền...) rồi đặt ngưỡng từ chính giá trị của hồ sơ bị thu hồi.
  3. Giống ứng viên nào đã có? Độ tương đồng văn bản (cùng không gian TF-IDF) + cùng đặc trưng, cùng loại đơn.

Việc quyết định "đủ thường xuyên để thành bad case chưa" (đếm số ca, số người gửi, số người duyệt, độ phủ trên
lịch sử) cần CSDL nên nằm ở api_core/workflow/bad_case_learning.py. Điều kiện của bad case học được chỉ dùng
một tập đặc trưng đã khai báo (FEATURES) và phép so sánh cố định, nên kiểm tra được và không thực thi mã lạ.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

try:
    from nlp_text import extract_amount_vnd, normalize_text, strip_diacritics
except ImportError:  # chạy từ gốc repo
    from ai_service.nlp_text import extract_amount_vnd, normalize_text, strip_diacritics

ENGINE_VERSION = "bad-case-reason-1"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "bad_case_reason.joblib"
NEW = "NEW_PATTERN"
ONE_OFF = "ONE_OFF"
NO_FEATURE = "NONE"

# Đặc trưng được phép dùng trong điều kiện của bad case học được. request_level: tính từ chính hồ sơ
# (đầu phân loại đặc trưng chỉ đoán nhóm này); còn lại là tín hiệu ngữ cảnh đã có (bad_case_signals.py).
FEATURES: dict[str, dict[str, Any]] = {
    "notice_hours": {"label": "số giờ báo trước (từ lúc gửi đơn tới lúc bắt đầu)", "unit": "giờ",
                     "request_level": True, "title": "Báo trước quá sát giờ"},
    "start_day_of_month": {"label": "ngày trong tháng của ngày bắt đầu", "unit": "",
                           "request_level": True, "title": "Rơi vào giai đoạn cuối tháng"},
    "start_weekday": {"label": "thứ của ngày bắt đầu (1 = Thứ Hai … 7 = Chủ nhật)", "unit": "",
                      "request_level": True, "title": "Lặp lại vào cùng thứ trong tuần"},
    "submit_hour": {"label": "giờ gửi đơn (0–23, giờ Việt Nam)", "unit": "giờ",
                    "request_level": True, "title": "Gửi đơn vào giờ bất thường"},
    "days_requested": {"label": "số ngày của đơn", "unit": "ngày",
                       "request_level": True, "title": "Đơn dài ngày"},
    "amount": {"label": "số tiền của hồ sơ", "unit": "VNĐ",
               "request_level": True, "title": "Số tiền cao bất thường"},
    "requester_rejected_30d": {"label": "số hồ sơ của người gửi bị từ chối trong 30 ngày", "unit": "hồ sơ",
                               "request_level": True, "title": "Người gửi vừa bị từ chối nhiều hồ sơ"},
    "same_type_count_7d": {"label": "số hồ sơ cùng loại của người gửi trong 7 ngày", "unit": "hồ sơ"},
    "same_type_count_30d": {"label": "số hồ sơ cùng loại của người gửi trong 30 ngày", "unit": "hồ sơ"},
    "same_type_count_month": {"label": "số hồ sơ cùng loại của người gửi trong tháng", "unit": "hồ sơ"},
    "team_absence_ratio": {"label": "tỉ lệ đồng nghiệp cùng phòng vắng trùng ngày", "unit": ""},
    "work_due_in_absence": {"label": "số việc đến hạn trong thời gian vắng", "unit": "việc"},
    "requester_finance_count_7d": {"label": "số hồ sơ tài chính của người gửi trong 7 ngày", "unit": "hồ sơ"},
    "requester_amount_7d": {"label": "tổng tiền hồ sơ tài chính của người gửi trong 7 ngày", "unit": "VNĐ"},
    "off_hours_count_7d": {"label": "số hồ sơ gửi ngoài giờ trong 7 ngày", "unit": "hồ sơ"},
    "ai_revoked_90d": {"label": "số lần tự duyệt của AI cho người gửi bị thu hồi trong 90 ngày", "unit": "lần"},
    "duplicate_invoice_count": {"label": "số hồ sơ khác dùng cùng số hóa đơn", "unit": "hồ sơ"},
    "same_customer_count_7d": {"label": "số hồ sơ chiết khấu khác cho cùng khách trong 7 ngày", "unit": "hồ sơ"},
}
OPS = ("<=", ">=", "==", "in")
MAX_TERMS = 4
WEEKDAYS = {1: "Thứ Hai", 2: "Thứ Ba", 3: "Thứ Tư", 4: "Thứ Năm", 5: "Thứ Sáu", 6: "Thứ Bảy", 7: "Chủ nhật"}
NIGHT_HOURS = [22, 23, 0, 1, 2, 3, 4, 5]


# --------------------------------------------------------------------------- điều kiện
def validate_condition(cond: Any) -> dict[str, Any]:
    """Chuẩn hóa {"all": [{"feature", "op", "value"}]}; sai thì ValueError (thông điệp tiếng Việt)."""
    if not isinstance(cond, dict) or set(cond) != {"all"} or not isinstance(cond["all"], list):
        raise ValueError('Điều kiện phải có dạng {"all": [{"feature": ..., "op": ..., "value": ...}]}')
    terms = cond["all"]
    if not 1 <= len(terms) <= MAX_TERMS:
        raise ValueError(f"Điều kiện cần 1–{MAX_TERMS} vế")
    out = []
    for term in terms:
        if not isinstance(term, dict) or set(term) != {"feature", "op", "value"}:
            raise ValueError("Mỗi vế chỉ gồm feature, op, value")
        feature, op, value = term["feature"], term["op"], term["value"]
        if feature not in FEATURES:
            raise ValueError(f"Đặc trưng không hỗ trợ: {feature}")
        if op not in OPS:
            raise ValueError(f"Phép so sánh không hỗ trợ: {op}")
        if op == "in":
            if not isinstance(value, list) or not 1 <= len(value) <= 24:
                raise ValueError("Phép 'in' cần danh sách 1–24 giá trị")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
                raise ValueError("Giá trị phải là số")
            value = sorted({float(v) if isinstance(v, float) and not v.is_integer() else int(v) for v in value})
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Giá trị phải là số")
            value = int(value) if float(value).is_integer() else float(value)
        if feature == "start_weekday" and any(not 1 <= v <= 7 for v in (value if op == "in" else [value])):
            raise ValueError("Thứ trong tuần là 1–7")
        out.append({"feature": feature, "op": op, "value": value})
    return {"all": out}


def condition_matches(cond: dict[str, Any] | None, values: dict[str, Any]) -> bool:
    """Mọi vế đều đúng; thiếu giá trị (None) thì KHÔNG khớp, để không chặn nhầm khi thiếu dữ liệu."""
    if not cond or not cond.get("all"):
        return False
    for term in cond["all"]:
        v = values.get(term["feature"])
        if v is None or isinstance(v, (list, dict)):
            return False
        v = float(v)
        op, ref = term["op"], term["value"]
        if op == "<=" and not v <= ref:
            return False
        if op == ">=" and not v >= ref:
            return False
        if op == "==" and v != ref:
            return False
        if op == "in" and v not in [float(x) for x in ref]:
            return False
    return True


def _fmt(feature: str, value: Any) -> str:
    if feature == "start_weekday":
        return ", ".join(WEEKDAYS.get(int(v), str(v)) for v in (value if isinstance(value, list) else [value]))
    if feature in ("amount", "requester_amount_7d"):
        return f"{float(value):,.0f}".replace(",", ".") + " VNĐ"
    if feature == "team_absence_ratio":
        return f"{float(value):.0%}"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    unit = FEATURES[feature].get("unit") or ""
    return f"{value} {unit}".strip()


def describe_condition(cond: dict[str, Any] | None) -> str:
    if not cond or not cond.get("all"):
        return "chưa có điều kiện đo được"
    words = {"<=": "≤", ">=": "≥", "==": "=", "in": "thuộc"}
    return " và ".join(
        f"{FEATURES[t['feature']]['label']} {words[t['op']]} {_fmt(t['feature'], t['value'])}" for t in cond["all"]
    )


# --------------------------------------------------------------------------- văn bản
def fold(text: str) -> str:
    return strip_diacritics(normalize_text(text))


def _word_view(text: str) -> str:
    return normalize_text(text)


_DAYS = re.compile(r"(\d{1,2})\s*(?:ngày|ngay)\b")
_WEEKDAY_WORDS = [
    (7, r"chu nhat|cn\b"), (1, r"thu hai|thu 2|\bt2\b"), (2, r"thu ba|thu 3|\bt3\b"),
    (3, r"thu tu|thu 4|\bt4\b"), (4, r"thu nam|thu 5|\bt5\b"), (5, r"thu sau|thu 6|\bt6\b"),
    (6, r"thu bay|thu 7|\bt7\b"),
]
_NIGHT = re.compile(r"nua dem|dem khuya|\bkhuya\b|\b(?:1[01]|[0-5])\s*(?:gio|h)\s*(?:dem|sang)\b|rang sang")


def _ceil_to(value: float, steps: list[float]) -> float:
    for s in steps:
        if value <= s:
            return s
    return steps[-1]


def propose_condition(feature: str | None, reason: str, values: dict[str, Any]) -> dict[str, Any] | None:
    """Ngưỡng lấy từ chính hồ sơ bị thu hồi (và con số trong lý do nếu có); None nếu không đặt được."""
    if not feature or feature not in FEATURES:
        return None
    text = fold(reason)
    v = values.get(feature)
    term: dict[str, Any] | None = None
    if feature == "notice_hours":
        hours = 24.0 if v is None else _ceil_to(max(float(v), 0.0), [4, 8, 12, 24, 48])
        term = {"op": "<=", "value": int(hours)}
    elif feature == "start_day_of_month":
        day = 25 if v is None or float(v) >= 25 or float(v) < 20 else int(v)
        term = {"op": ">=", "value": day}
    elif feature == "start_weekday":
        # Quy luật theo thứ phải được nêu trong lý do; một quan sát đơn lẻ không đủ suy ra "luôn vào thứ X".
        days = [d for d, pattern in _WEEKDAY_WORDS if re.search(pattern, text)]
        term = {"op": "in", "value": days} if days else None
    elif feature == "submit_hour":
        if _NIGHT.search(text) or (v is not None and int(v) in NIGHT_HOURS):
            term = {"op": "in", "value": NIGHT_HOURS}
        elif v is not None:
            term = {"op": "in", "value": [int(v)]}
    elif feature == "days_requested":
        m = _DAYS.search(text)
        days = int(m.group(1)) if m else (int(v) if v else None)
        term = {"op": ">=", "value": max(days, 3)} if days else None
    elif feature == "amount":
        amount = extract_amount_vnd(reason) or (float(v) if v else None)
        if amount and amount >= 1_000_000:
            term = {"op": ">=", "value": int(amount // 1_000_000 * 1_000_000)}
    elif feature == "requester_rejected_30d":
        term = {"op": ">=", "value": max(2, int(v or 0))}
    elif v is not None and isinstance(v, (int, float)) and not isinstance(v, bool):
        term = {"op": ">=", "value": v}
    if term is None:
        return None
    try:
        cond = validate_condition({"all": [{"feature": feature, **term}]})
    except ValueError:
        return None
    # Điều kiện phải bắt được chính hồ sơ bị thu hồi (nếu biết giá trị), nếu không là đoán sai đặc trưng.
    if v is not None and not condition_matches(cond, values):
        return None
    return cond


# --------------------------------------------------------------------------- mô hình
# Dấu hiệu ngôn ngữ (đã bỏ dấu) phân biệt KIỂU RỦI RO CHUNG (lặp lại, bất thường, thói quen) với LÝ DO RIÊNG
# của một hồ sơ (nhập sai, thiếu giấy tờ, đổi ý...). Soạn từ định nghĩa hai nhãn, không từ bộ kiểm tra.
GENERAL_CUES = (
    "lan nao", "hay xin", "hay nop", "hay gui", "thuong xuyen", "thuong ", "luon ", "lien tuc", "lien tiep",
    "nhieu lan", "bat thuong", "qua sat", "sat gio", "dot xuat", "khong bao truoc", "don dap", "toi tap", "dip ",
    "moi khi", "tuan nao", "thang nao", "ngay nao", "thoi quen", "lap lai", "qua dai", "qua lon", "qua cao",
    "qua nhieu", "vuot muc", "danh sach", "rui ro", "tien su", "dang ngo", "cu xin", "cu nop", "toan ",
    "hang tuan", "hang thang", "cuoi thang", "dau tuan", "cuoi tuan", "nua dem", "khuya", "khong nen tu dong",
    "may tu duyet", "tu duyet", "tu dong",
)
INSTANCE_CUES = (
    "nham", "sai ", "ghi sai", "viet sai", "thieu", "bo sung", "dinh kem", "chu ky", "ban sao", "gui lai",
    "sua lai", "kiem tra lai", "huy", "doi y", "da doi", "doi lich", "doi sang", "chuyen sang", "da xu ly",
    "da duyet", "don giay", "trao doi truc tiep", "chua ro", "bi mo", "bi cat", "don nay", "lan nay", "hom do",
    "khong can", "khong nghi nua", "trung don", "hach toan", "chot gia", "online", "giay to",
)


class CueFeatures:
    """Đếm dấu hiệu 'chung' / 'riêng' và có con số hay không; transformer kiểu sklearn, không phụ thuộc sklearn."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        from scipy.sparse import csr_matrix

        rows = []
        for text in X:
            t = " " + fold(text) + " "
            g = sum(cue in t for cue in GENERAL_CUES)
            i = sum(cue in t for cue in INSTANCE_CUES)
            rows.append([min(g, 3) / 3, min(i, 3) / 3, float(g > i), float(i > g),
                         float(bool(re.search(r"\d", t))), min(len(t.split()), 40) / 40])
        return csr_matrix(rows)

    def get_params(self, deep=True):
        return {}

    def set_params(self, **params):
        return self


def model_input(reason: str, type_code: str | None, type_token: bool) -> str:
    """Phiên bản 2 thêm mã loại đơn vào đầu câu (loại đơn giới hạn các bad case có thể gặp)."""
    return f"loaidon_{(type_code or 'x').lower()} {reason}" if type_token else reason


def build_pipeline(c: float = 4.0, cues: bool = False, cue_weight: float = 1.0):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    parts = [
        ("word", TfidfVectorizer(preprocessor=_word_view, ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("char", TfidfVectorizer(preprocessor=fold, analyzer="char_wb", ngram_range=(2, 5), min_df=2,
                                 sublinear_tf=True)),
    ]
    weights = {"word": 1.0, "char": 1.0}
    if cues:
        parts.append(("cues", CueFeatures()))
        weights["cues"] = cue_weight
    features = FeatureUnion(parts, transformer_weights=weights)
    return Pipeline([("tfidf", features),
                     ("clf", LogisticRegression(C=c, max_iter=4000, class_weight="balanced"))])


_MODEL: dict[str, Any] | None = None
_MODEL_MTIME: float | None = None


def load_model(path: Path = MODEL_PATH) -> dict[str, Any] | None:
    """{'label': Pipeline, 'feature': Pipeline, 'meta': {...}} hoặc None khi chưa huấn luyện."""
    global _MODEL, _MODEL_MTIME
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    if _MODEL is None or _MODEL_MTIME != mtime:
        import joblib

        # Chỉ nạp tệp mô hình trong repo/ảnh, không bao giờ từ dữ liệu người dùng (AGENTS.md).
        _MODEL = joblib.load(path)
        _MODEL_MTIME = mtime
    return _MODEL


def _cosine_max(pipeline, text: str, others: list[str]) -> float:
    if not others:
        return 0.0
    vec = pipeline.named_steps["tfidf"]
    a = vec.transform([text])
    b = vec.transform(others)
    num = (b @ a.T).toarray().ravel()
    na = math.sqrt(a.multiply(a).sum()) or 1.0
    nb = [math.sqrt(b[i].multiply(b[i]).sum()) or 1.0 for i in range(b.shape[0])]
    return float(max(n / (na * d) for n, d in zip(num, nb)))


def classify(reason: str, model: dict[str, Any] | None = None, type_code: str | None = None) -> dict[str, Any]:
    model = model or load_model()
    if model is None:
        return {"label": ONE_OFF, "confidence": 0.0, "top": [], "feature": None, "engine": "untrained"}
    pipe = model["label"]
    text = model_input(reason, type_code, bool(model.get("meta", {}).get("type_token")))
    probs = pipe.predict_proba([text])[0]
    order = probs.argsort()[::-1]
    classes = pipe.classes_
    label, conf = str(classes[order[0]]), float(probs[order[0]])
    feature = None
    # Đoán đặc trưng cho cả lý do bị xếp là "riêng": phân biệt chung/riêng từ MỘT câu không chắc (cả mô hình
    # lẫn Gemini đều yếu ở ranh giới này), tần suất ở nhiều người duyệt mới là bằng chứng quyết định.
    if label in (NEW, ONE_OFF) and model.get("feature") is not None:
        feature_text = model_input(reason, type_code, bool(model.get("meta", {}).get("feature_type_token")))
        fp = model["feature"].predict_proba([feature_text])[0]
        best = model["feature"].classes_[fp.argmax()]
        feature = None if best == NO_FEATURE else str(best)
    # Độ chắc rằng lý do KHÔNG thuộc bad case có sẵn (tổng hai nhãn ngoài danh mục), dùng cho ứng viên mới.
    outside = float(sum(p for c, p in zip(classes, probs) if c in (NEW, ONE_OFF)))
    return {
        "label": label,
        "confidence": round(conf, 3),
        "confidence_outside": round(outside, 3),
        "top": [{"label": str(classes[i]), "p": round(float(probs[i]), 3)} for i in order[:3]],
        "feature": feature,
        "engine": model.get("meta", {}).get("version", ENGINE_VERSION),
    }


def analyze(
    *,
    reason: str,
    type_code: str,
    values: dict[str, Any],
    cases: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phân loại một lý do, đề xuất điều kiện và ghép vào ứng viên giống nhất.

    cases: bad case đang có hiệu lực [{code, title, request_types}] (để biết loại đơn đã thuộc phạm vi chưa).
    candidates: ứng viên đang chờ [{code, verdict, feature, type_codes, reasons}].
    """
    model = model or load_model()
    result = classify(reason, model, type_code)
    label = result["label"]
    by_code = {c["code"]: c for c in cases}
    out: dict[str, Any] = {**result, "verdict": label, "code": None, "condition": None, "match": None,
                           "similarity": 0.0}

    if label not in (NEW, ONE_OFF):
        case = by_code.get(label)
        types = (case or {}).get("request_types") or []
        covered = case is not None and ("*" in types or type_code in types)
        out.update(verdict="EXISTING" if covered else "EXISTING_SCOPE", code=label,
                   title=(case or {}).get("title") or label)
        if covered:
            out["explanation"] = (f"Lý do khớp bad case đã có {label} ({out['title']}); AI đã biết kiểu này nhưng "
                                  "hồ sơ chưa vượt ngưỡng nên bị bỏ sót.")
        else:
            out["explanation"] = (f"Lý do khớp bad case {label} ({out['title']}) nhưng bad case này chưa áp dụng cho "
                                  f"loại {type_code}; ứng viên: mở rộng phạm vi sang {type_code}.")
    elif label == NEW:
        out["condition"] = propose_condition(result["feature"], reason, values)
        feature = result["feature"]
        title = FEATURES[feature]["title"] if feature else "Rủi ro mới do người duyệt nêu"
        out["title"] = f"{title} ({type_code})"
        out["explanation"] = (
            "Lý do mô tả một kiểu rủi ro lặp lại được, chưa có trong danh mục"
            + (f"; đo được bằng {FEATURES[feature]['label']}: {describe_condition(out['condition'])}"
               if out["condition"] else "; chưa đo được bằng dữ liệu hệ thống")
            + "."
        )
    else:
        feature = result["feature"]
        out["condition"] = propose_condition(feature, reason, values)
        out["title"] = (f"{FEATURES[feature]['title']} ({type_code})" if feature else "Lý do riêng của hồ sơ")
        out["explanation"] = ("Lý do có vẻ chỉ đúng với riêng hồ sơ này (nhập sai, thiếu chứng từ, cần trao đổi, sự "
                              "cố riêng...), chưa phải kiểu rủi ro chung"
                              + (f"; nếu lặp lại ở nhiều người thì đo được bằng {FEATURES[feature]['label']}"
                                 if out["condition"] else "") + ".")

    # Ghép vào ứng viên giống nhất: cùng kết luận; cùng mã (bad case có sẵn) hoặc cùng đặc trưng + loại đơn,
    # hoặc văn bản đủ giống.
    best, best_sim = None, 0.0
    for cand in candidates:
        # Kiểu mới và lý do "riêng" cùng đặc trưng có thể là một kiểu (ranh giới một câu không chắc).
        compatible = {NEW, ONE_OFF}
        if cand.get("verdict") != out["verdict"] and not (
            cand.get("verdict") in compatible and out["verdict"] in compatible
        ):
            continue
        if out["code"] and cand.get("base_code") == out["code"] and type_code in (cand.get("type_codes") or []):
            best, best_sim = cand, 1.0
            break
        if out["verdict"] == "EXISTING":
            continue
        same_type = type_code in (cand.get("type_codes") or [])
        cond = cand.get("condition")
        # Ràng buộc nhất quán: ứng viên đã có điều kiện đo được thì chỉ nhận lý do của hồ sơ mà điều kiện đó bắt
        # được (cùng cơ chế rủi ro). Tránh gom nhầm một lý do không liên quan làm ứng viên đủ ngưỡng.
        cond_hit = False
        if cond and same_type:
            try:
                cond_hit = condition_matches(validate_condition(cond), values)
            except ValueError:
                cond_hit = False
            if not cond_hit:
                continue
        sim = _cosine_max(model["label"], reason, list(cand.get("reasons") or [])[:20]) if model else 0.0
        same_feature = bool(result["feature"]) and cand.get("feature") == result["feature"]
        score = sim + (0.5 if same_feature and same_type else 0.0) + (0.3 if cond_hit else 0.0)
        # Lý do không có điều kiện đo được riêng (không có cơ chế cạnh tranh) mà điều kiện của ứng viên bắt được
        # hồ sơ này: chỉ cần câu chữ gần ở mức thấp hơn (đặt sau lần chạy thật thứ hai, ghi trong báo cáo).
        weak_join = cond_hit and out.get("condition") is None and sim >= SIMILAR_WITH_CONDITION
        if score > best_sim and (score >= 0.5 or sim >= SIMILAR or weak_join):
            best, best_sim = cand, score
    if best is not None:
        out["match"] = best["code"]
        out["similarity"] = round(min(best_sim, 1.0), 3)
    return out


SIMILAR = 0.35
SIMILAR_WITH_CONDITION = 0.15
