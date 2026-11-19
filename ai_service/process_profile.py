"""Hồ sơ quy trình: học máy nội bộ đánh giá MẪU VÒNG ĐỜI (A/B/C) và TRỌNG SỐ RỦI RO (1-5) của một loại yêu cầu,
và đánh giá tác động của một quy định mới lên các loại yêu cầu hiện có.

- Đầu vào chỉ là NỘI DUNG quy trình: tên, mô tả, nhóm nghiệp vụ, các trường của biểu mẫu (và văn bản quy định
  khi đánh giá tác động). Không dùng executor/acceptor/approval_level vì đó là cấu hình suy ra từ nhãn.
- Mô hình chốt trước khi đánh giá: Logistic Regression (C=1, class_weight='balanced') cho A/B/C;
  Ridge (alpha=1) cho trọng số, làm tròn và kẹp vào 1..5.
- Mỗi dự đoán kèm lý do: các đặc trưng đóng góp lớn nhất (mô hình tuyến tính nên đóng góp = hệ số x giá trị).
- Đề xuất theo quy định mới = phần CHÊNH giữa dự đoán có quy định và không có quy định, cộng vào cấu hình hiện
  tại; nhờ vậy sai số sẵn có của mô hình không biến thành đề xuất. Đề xuất chỉ để quản trị viên duyệt.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics.pairwise import cosine_similarity

try:
    from nlp_text import normalize_text, strip_diacritics
except ImportError:  # chạy từ gốc repo
    from ai_service.nlp_text import normalize_text, strip_diacritics

PROFILE_VERSION = "process-profile-3"
# Phiên bản 1 (chốt trước): cosine TF-IDF từ >= 0.15, tối đa 5 loại -> bỏ sót 3/9 kịch bản vì mô tả loại rất ngắn.
# Phiên bản 2 (chỉnh trên tập phát triển QD-01..QD-10, chấm trên tập giữ lại QD-11..QD-20):
#   TF-IDF ký tự không dấu 3-5 gram + từ; lấy loại đứng đầu nếu >= RELATED_MIN, thêm loại khác nếu
#   >= RELATED_RATIO x điểm đầu; lớp chênh lệch dự đoán phía sau mới quyết định có đề xuất hay không.
# Phiên bản 3 (bản cuối; chấm trên tập giữ lại thứ hai QD-21..QD-30): phần chênh tính trên TÍN HIỆU NGHIỆP VỤ quy định
#   bổ sung, định giá bằng hệ số không âm học từ 58 loại, thay vì ghép cả câu quy định vào mô hình từ ngữ.
RELATED_MIN = 0.08
RELATED_RATIO = 0.75
RELATED_TOP_K = 3
WEIGHT_STEP = 0.5          # phần chênh trọng số (mô hình hồi quy) tối thiểu để đề xuất đổi 1 bậc
LIFECYCLE_ORDER = {"A": 0, "B": 1, "C": 2}
# Mô tả giữ chỗ và tóm tắt tuyến duyệt ("QL trực tiếp → HR ⇒ thực hiện: HR") nói thẳng người thực hiện/nghiệm thu,
# tức là lộ nhãn -> bỏ khỏi đầu vào.
PLACEHOLDER_RE = re.compile(r"Loại yêu cầu [^;]*; yêu cầu công bố quy chế hợp lệ trước khi sử dụng\.?", re.IGNORECASE)
ROUTE_MARKS = ("→", "⇒", "thực hiện:", "nghiệm thu:")

# Nhóm tín hiệu nghiệp vụ (so khớp trên văn bản không dấu, chữ thường). Tên nhóm dùng làm lý do hiển thị.
CUES: dict[str, tuple[str, list[str]]] = {
    "money": ("có giá trị tiền / ngân sách", ["tien", "amount", "ngan sach", "tam ung", "thanh toan", "chi phi", "hoa don",
                                            "chiet khau", "voucher", "gia tri", "trieu", "ty dong", "vnd", "budget", "price",
                                            "khuyen mai", "giam gia"]),
    "execution": ("cần người thực hiện", ["cap ", "cai dat", "lap dat", "sua chua", "thuc hien", "trien khai", "phat hanh",
                                         "xuat ", "luan chuyen", "tuyen ", "thu hoi", "dong dau", "trich xuat", "mua sam",
                                         "xu ly", "dieu chuyen", "ban hanh", "tiep nhan"]),
    "acceptance": ("cần bàn giao / nghiệm thu", ["ban giao", "nghiem thu", "danh gia hieu qua", "bien ban", "thiet bi",
                                                "tai san", "du an", "release", "hoi dong"]),
    "sensitive": ("liên quan dữ liệu nhạy cảm / hạ tầng", ["du lieu", "ca nhan", "pii", "bao mat", "quyen truy cap",
                                                          "server", "production", "firewall", "mat khau", "nhay cam",
                                                          "khan cap", "su co"]),
    "legal": ("ràng buộc pháp lý", ["hop dong", "phap che", "con dau", "quy che", "nda", "ky luat", "nghi dinh", "luat",
                                   "tham dinh"]),
    "hr": ("tác động nhân sự", ["luong", "thang chuc", "ky luat", "tuyen dung", "thoi viec", "dieu chuyen", "khen thuong",
                               "tru phep", "tru nua ngay"]),
    "external": ("liên quan bên ngoài", ["khach", "doi tac", "nha cung cap", "vendor", "ben ngoai"]),
    "irreversible": ("khó đảo ngược", ["thanh ly", "huy ", "xoa ", "sa thai", "thoi viec"]),
    "authority": ("đòi hỏi cấp có thẩm quyền cao", ["ban giam doc", "giam doc", "hoi dong", "truong bo phan",
                                                   "phe duyet", "xac nhan"]),
    "high_risk": ("được xếp rủi ro cao", ["rui ro cao", "khan cap", "bat buoc", "nghiem trong"]),
    "routine": ("tác vụ thường nhật, tự phục vụ", ["nghi phep", "phong hop", "cham cong", "lam viec tu xa", "wfh",
                                                  "van phong pham", "the ra vao", "di muon", "ve som"]),
}
AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(trieu|ty)")


def _plain(text: str) -> str:
    return " " + strip_diacritics(normalize_text(text or "")).lower() + " "


def clean_description(text: str) -> str:
    text = PLACEHOLDER_RE.sub("", text or "").strip()
    return "" if any(m in text for m in ROUTE_MARKS) else text


def type_text(item: dict[str, Any]) -> str:
    fields = " ".join(str(f).replace("_", " ") for f in item.get("fields") or [])
    return f"{item.get('name', '')}. {clean_description(item.get('description', ''))}. {fields}"


def cue_features(text: str) -> dict[str, float]:
    plain = _plain(text)
    feats = {f"cue:{k}": float(min(3, sum(plain.count(w) for w in words))) for k, (_, words) in CUES.items()}
    amounts = [float(a.replace(",", ".")) * (1000 if unit == "ty" else 1) for a, unit in AMOUNT_RE.findall(plain)]
    feats["amount_log_million"] = math.log1p(max(amounts)) if amounts else 0.0
    return feats


def struct_features(item: dict[str, Any]) -> dict[str, float]:
    fields = [str(f) for f in item.get("fields") or []]
    joined = " ".join(fields)
    return {
        "n_fields": float(len(fields)),
        "field:amount": float(any(k in joined for k in ("amount", "price", "value", "budget", "total"))),
        "field:date_range": float("start_date" in fields and "end_date" in fields),
        "field:person": float(any(f.endswith(("user_id", "employee_id")) for f in fields)),
        f"category:{item.get('category', '')}": 1.0,
    }


def item_features(item: dict[str, Any], extra_text: str = "") -> tuple[dict[str, float], str]:
    text = type_text(item) + (" " + extra_text if extra_text else "")
    feats = {**struct_features(item), **cue_features(text)}
    return feats, _plain(text)


def readable(feature: str) -> str:
    if feature.startswith("cue:"):
        return CUES[feature[4:]][0]
    if feature.startswith("category:"):
        return f"thuộc nhóm {feature.split(':', 1)[1]}"
    if feature.startswith("word:"):
        return f"có cụm từ \"{feature[5:]}\""
    return {"n_fields": "số trường biểu mẫu", "field:amount": "biểu mẫu có trường số tiền",
            "field:date_range": "biểu mẫu có khoảng thời gian", "field:person": "biểu mẫu chỉ định người khác",
            "amount_log_million": "mức tiền được nêu"}.get(feature, feature)


@dataclass
class ProcessProfiler:
    lc_c: float = 1.0          # C của Logistic Regression (vòng đời)
    use_words: bool = True     # có dùng TF-IDF từ ngữ bên cạnh tín hiệu nghiệp vụ hay không
    corpus: list[dict[str, Any]] = field(default_factory=list)
    version: str = PROFILE_VERSION

    def __post_init__(self) -> None:
        self.dict_vec = DictVectorizer(sparse=True)
        self.tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=3000)
        self.lifecycle_model = LogisticRegression(C=self.lc_c, class_weight="balanced", max_iter=5000, random_state=42)
        self.weight_model = Ridge(alpha=1.0)
        # Phiên bản 3: mô hình phụ chỉ trên tín hiệu nghiệp vụ, dùng để định giá phần nghĩa vụ quy định mới bổ sung.
        self.cue_vec = DictVectorizer(sparse=True)
        self.cue_weight = Ridge(alpha=1.0, positive=True)
        self.cue_lifecycle = LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000, random_state=42)

    # ------------------------------------------------------------------ matrix
    def _matrix(self, rows: list[tuple[dict[str, float], str]], fit: bool = False):
        dicts = [r[0] for r in rows]
        a = self.dict_vec.fit_transform(dicts) if fit else self.dict_vec.transform(dicts)
        if not self.use_words:
            return csr_matrix(a)
        texts = [r[1] for r in rows]
        b = self.tfidf.fit_transform(texts) if fit else self.tfidf.transform(texts)
        return csr_matrix(hstack([a, b]))

    def feature_names(self) -> list[str]:
        names = list(self.dict_vec.get_feature_names_out())
        return names + ([f"word:{w}" for w in self.tfidf.get_feature_names_out()] if self.use_words else [])

    def fit(self, items: list[dict[str, Any]]) -> ProcessProfiler:
        X = self._matrix([item_features(i) for i in items], fit=True)
        self.lifecycle_model.fit(X, [i["lifecycle"] for i in items])
        self.weight_model.fit(X, [float(i["risk_weight"]) for i in items])
        Xc = self._cue_matrix([item_features(i)[0] for i in items], fit=True)
        self.cue_weight.fit(Xc, [float(i["risk_weight"]) for i in items])
        self.cue_lifecycle.fit(Xc, [i["lifecycle"] for i in items])
        self.corpus = [{k: i[k] for k in ("code", "name", "category", "description", "fields", "lifecycle", "risk_weight")}
                       for i in items]
        return self

    # ------------------------------------------------------------------ dự đoán + lý do
    def _explain(self, x, coef: np.ndarray, top: int = 3, positive: bool = True) -> list[str]:
        contrib = x.multiply(coef).toarray().ravel() if hasattr(x, "multiply") else x * coef
        names = self.feature_names()
        order = np.argsort(contrib)[::-1] if positive else np.argsort(contrib)
        out = []
        for idx in order:
            if (contrib[idx] <= 0 if positive else contrib[idx] >= 0) or len(out) >= top:
                break
            out.append(readable(names[idx]))
        return out

    def predict_one(self, item: dict[str, Any], extra_text: str = "") -> dict[str, Any]:
        x = self._matrix([item_features(item, extra_text)])
        probs = self.lifecycle_model.predict_proba(x)[0]
        classes = list(self.lifecycle_model.classes_)
        lc = classes[int(np.argmax(probs))]
        raw_w = float(self.weight_model.predict(x)[0])
        return {
            "lifecycle": lc,
            "lifecycle_confidence": round(float(np.max(probs)), 3),
            "risk_weight": int(min(5, max(1, round(raw_w)))),
            "risk_weight_raw": round(raw_w, 3),
            "reasons_lifecycle": self._explain(x, self.lifecycle_model.coef_[classes.index(lc)]
                                               if len(classes) > 2 else self.lifecycle_model.coef_[0]),
            "reasons_weight_up": self._explain(x, self.weight_model.coef_),
            "reasons_weight_down": self._explain(x, self.weight_model.coef_, positive=False),
        }

    # ------------------------------------------------------------------ tác động của quy định mới
    def related_types(self, regulation: str, items: list[dict[str, Any]] | None = None) -> list[tuple[dict, float]]:
        items = items or self.corpus
        docs = [_plain(type_text(i)) for i in items] + [_plain(regulation)]
        word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit_transform(docs)
        char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(docs)
        sims = 0.5 * cosine_similarity(word[-1], word[:-1]).ravel() + 0.5 * cosine_similarity(char[-1], char[:-1]).ravel()
        ranked = sorted(zip(items, sims), key=lambda t: -t[1])
        if not ranked or ranked[0][1] < RELATED_MIN:
            return []
        top = ranked[0][1]
        return [(i, float(s)) for i, s in ranked[:RELATED_TOP_K] if s >= max(RELATED_MIN, RELATED_RATIO * top)]

    def _cue_matrix(self, feats: list[dict[str, float]], fit: bool = False):
        rows = [{k: v for k, v in f.items() if k.startswith("cue:") or k == "amount_log_million"} for f in feats]
        return self.cue_vec.fit_transform(rows) if fit else self.cue_vec.transform(rows)

    def cue_prices(self) -> dict[str, float]:
        """Mức tăng trọng số mô hình học được cho mỗi tín hiệu nghiệp vụ (ràng buộc không âm)."""
        return {n: round(float(c), 3) for n, c in zip(self.cue_vec.get_feature_names_out(), self.cue_weight.coef_)}

    def regulation_impact(self, regulation: str, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Phiên bản 3: chỉ định giá PHẦN NGHĨA VỤ quy định bổ sung. Với mỗi loại liên quan, lấy các tín hiệu nghiệp vụ
        tăng thêm khi ghép quy định vào nội dung loại; mức tăng trọng số = tổng (giá học được x mức tăng tín hiệu),
        giá được ràng buộc không âm nên thêm nghĩa vụ không bao giờ làm giảm rủi ro. Mẫu vòng đời: mô hình chỉ dùng
        tín hiệu nghiệp vụ dự đoán trước/sau; chỉ đề xuất nâng."""
        items = items or self.corpus
        proposals, related = [], []
        for item, sim in self.related_types(regulation, items):
            before = item_features(item)[0]
            after = item_features(item, regulation)[0]
            added = {k: after[k] - before.get(k, 0.0) for k in after
                     if (k.startswith("cue:") or k == "amount_log_million") and after[k] > before.get(k, 0.0)}
            prices = self.cue_prices()
            delta_w = sum(prices.get(k, 0.0) * v for k, v in added.items())
            current_lc, current_w = item["lifecycle"], int(item["risk_weight"])
            proposed_w = min(5, current_w + max(1, round(delta_w))) if delta_w >= WEIGHT_STEP else current_w
            xb, xa = self._cue_matrix([before]), self._cue_matrix([after])
            lc_b, lc_a = self.cue_lifecycle.predict(xb)[0], self.cue_lifecycle.predict(xa)[0]
            proposed_lc = current_lc
            if lc_a != lc_b and LIFECYCLE_ORDER[lc_a] > max(LIFECYCLE_ORDER[lc_b], LIFECYCLE_ORDER[current_lc]):
                proposed_lc = lc_a
            triggered = [CUES[k[4:]][0] if k.startswith("cue:") else readable(k) for k in added]
            entry = {"code": item["code"], "name": item.get("name", ""), "similarity": round(sim, 3),
                     "current": {"lifecycle": current_lc, "risk_weight": current_w},
                     "proposed": {"lifecycle": proposed_lc, "risk_weight": proposed_w},
                     "weight_delta_raw": round(delta_w, 3), "triggered_by": triggered}
            related.append(entry)
            if proposed_w != current_w or proposed_lc != current_lc:
                proposals.append({**entry, "reasons": triggered})
        return {"version": self.version, "related": related, "proposals": proposals,
                "requires_admin_approval": True}
