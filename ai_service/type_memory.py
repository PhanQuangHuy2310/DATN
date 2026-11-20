"""Bộ nhớ loại yêu cầu mới và đánh giá "nhu cầu chưa có trong danh mục".

Bộ phân loại chính (TF-IDF + Logistic Regression) chỉ biết các loại có lúc huấn luyện. Loại tạo thêm sau đó (admin tạo
hoặc AI tạo từ nhu cầu của người dùng) được nhận biết ngay bằng bộ nhớ này, không cần huấn luyện lại:

* ``match_learned``: so khớp nội dung với tên, mô tả và tiêu đề các hồ sơ đã gửi của từng loại mới (n-gram ký tự,
  bỏ dấu, bỏ từ chức năng). Mỗi hồ sơ gửi thêm là một ví dụ mới, nên loại mới "học" dần theo cách người dùng viết.
* ``vocab_support``: tỉ lệ từ nội dung của câu nằm trong từ vựng mà mô hình đã gắn với các loại nó đoán. Độ tin cậy của
  mô hình không đủ để nhận ra nhu cầu mới ("Xin cấp chỗ đỗ ô tô" vẫn bị đoán "Cấp máy tính" 0,84) nhưng từ vựng thì
  không khớp; đó là dấu hiệu nhu cầu chưa có trong danh mục.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import numpy as np

try:
    from nlp_text import normalize_text
except ImportError:  # pragma: no cover - khi chạy từ gốc repo
    from ai_service.nlp_text import normalize_text

# Từ chức năng / động từ xin-cấp chung cho mọi loại: không mang nghĩa của loại yêu cầu.
_STOP_TEXT = """
xin cấp đăng ký đề nghị yêu cầu cho em tôi mình anh chị muốn cần được của và để các những một hai ba bốn năm
ngày mai hôm nay tại ở với công ty team nhóm bạn giúp vui lòng ạ nhé làm sao thế nào có không là thì đi vào ra
về lại này đó
"""
# Cùng phép chuẩn hóa với câu đầu vào (normalize_text đổi "đ" thành "d").
STOP = frozenset(re.findall(r"\w+", normalize_text(_STOP_TEXT)))
VOCAB_COEF = 0.5          # từ có hệ số dương > 0,5 với một loại được coi là từ vựng của loại đó
# Mô hình có thêm n-gram ký tự giữ dấu (train.py ACCENT_CHARS) chia trọng số với đặc trưng từ nên hệ số từ nhỏ hơn.
# Ngưỡng hiệu chỉnh trên 2 bộ dev (viết tay + câu ngắn, 234 câu, không dùng test) để tỉ lệ báo nhầm "nhu cầu
# mới" không cao hơn mô hình không dấu: 0,5 -> 10 câu, 0,4 -> 5, 0,35 -> 3 (tham chiếu 4). Xem
# training/data/request_everyday_report.md.
VOCAB_COEF_ACCENT = 0.35
NOVEL_SUPPORT = 0.34      # ≤ 1/3 từ nội dung khớp từ vựng của 3 loại được đoán -> nhu cầu mới
NOVEL_MAX_CONFIDENCE = 0.9
LEARNED_MIN = 0.2         # độ giống tối thiểu để đưa loại mới vào danh sách khả năng
LEARNED_SURE = 0.5        # từ ngưỡng này loại mới được chọn làm loại đề xuất
LEARNED_WHEN_NOVEL = 0.3  # mô hình gốc đã đánh giá là nhu cầu mới: loại mới khớp từ mức này thì chọn loại mới


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower().replace("đ", "d"))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


# Từ chức năng gõ không dấu ("xin dang ky"). Chỉ áp cho từ không dấu, để "tài khoản" không mất chữ "tài" (~ "tại").
STOP_FOLDED = frozenset(fold(w) for w in STOP)


def is_stop(word: str) -> bool:
    return word in STOP or (word == fold(word) and word in STOP_FOLDED)


def content_tokens(text: str) -> list[str]:
    words = re.findall(r"\w+", normalize_text(text or "").lower())
    return [w for w in words if len(w) > 1 and not w.isdigit() and not is_stop(w)]


class ModelVocab:
    """Từ vựng theo loại rút từ chính bộ phân loại (hệ số của đặc trưng từ)."""

    def __init__(self, pipeline):
        transformers = pipeline.named_steps["features"].transformer_list
        word = transformers[0][1]
        clf = pipeline.named_steps["classifier"]
        threshold = VOCAB_COEF_ACCENT if any(name == "char_accent" for name, _ in transformers) else VOCAB_COEF
        self.vocab = word.vocabulary_
        inverse = {i: t for t, i in self.vocab.items()}
        coef = clf.coef_[:, : len(self.vocab)]
        self.per_class = {
            str(code): {inverse[j] for j in np.nonzero(coef[i] > threshold)[0] if " " not in inverse[j]}
            for i, code in enumerate(clf.classes_)
        }

    def support(self, text: str, codes: list[str]) -> float | None:
        tokens = content_tokens(text)
        if not tokens:
            return None
        vocab = set().union(*(self.per_class.get(c, set()) for c in codes))
        return sum(t in vocab for t in tokens) / len(tokens)

    def known_words(self, text: str) -> int:
        """Số từ trong câu mà mô hình từng thấy (để nhận ra chuỗi vô nghĩa như "asdf qwer")."""
        return sum(w in self.vocab for w in re.findall(r"\w+", normalize_text(text or "").lower()))


_vocab_cache: dict[int, ModelVocab] = {}


def vocab_for(pipeline) -> ModelVocab:
    key = id(pipeline)
    if key not in _vocab_cache:
        _vocab_cache.clear()
        _vocab_cache[key] = ModelVocab(pipeline)
    return _vocab_cache[key]


def is_novel(confidence: float, support: float | None) -> bool:
    """Nhu cầu chưa có trong danh mục: từ vựng gần như không khớp, hoặc mô hình rất không chắc và khớp yếu."""
    if support is None:
        return False
    return (support <= NOVEL_SUPPORT and confidence < NOVEL_MAX_CONFIDENCE) or (confidence < 0.2 and support < 0.5)


def _doc(text: str) -> str:
    return " ".join(fold(t) for t in content_tokens(text))


@lru_cache(maxsize=1)
def _vectorizer_cls():
    from sklearn.feature_extraction.text import TfidfVectorizer

    return TfidfVectorizer


def match_learned(text: str, learned: list[dict]) -> list[tuple[dict, float]]:
    """[(loại, độ giống 0..1)] giảm dần. Độ giống = max cosine n-gram ký tự với hồ sơ loại và từng ví dụ."""
    query = _doc(text)
    if not query or not learned:
        return []
    docs, owner = [], []
    for k, item in enumerate(learned):
        profile = _doc(f"{item.get('name', '')} {item.get('description', '')}")
        for doc in [profile, *(_doc(e) for e in item.get("examples") or [])]:
            if doc:
                docs.append(doc)
                owner.append(k)
    if not docs:
        return []
    vec = _vectorizer_cls()(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
    matrix = vec.fit_transform([query, *docs])
    sims = (matrix[1:] @ matrix[0].T).toarray().ravel()
    best: dict[int, float] = {}
    for k, s in zip(owner, sims):
        best[k] = max(best.get(k, 0.0), float(s))
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    return [(learned[k], round(s, 4)) for k, s in ranked]


def learned_confidence(similarity: float) -> float:
    """Quy độ giống về thang độ tin cậy: 0,25 -> 0; 0,7 trở lên -> ~0,97."""
    return float(np.clip((similarity - 0.25) / 0.45, 0.0, 0.97))


_CONDITIONS = (
    (re.compile(r"days_gt\s*(\d+)"), "trên {} ngày"),
    (re.compile(r"amount_gte\s*(\d+)"), "từ {} đồng"),
    (re.compile(r"amount_gt\s*(\d+)"), "trên {} đồng"),
)
# Mã bộ phận thực hiện / người nghiệm thu trong tuyến duyệt của danh mục -> tên người dùng hiểu.
DEPARTMENT_NAMES = {
    "ADMIN": "Hành chính", "ASSET": "Quản lý tài sản", "FACILITY": "Cơ sở vật chất", "FINANCE": "Tài chính - Kế toán",
    "HR": "Nhân sự", "IT": "Công nghệ thông tin", "LEGAL": "Pháp chế", "MARKETING": "Marketing",
    "PROCUREMENT": "Mua hàng", "TECH": "Kỹ thuật phát triển", "WAREHOUSE": "Kho vận", "SALES": "Kinh doanh",
}
ROLE_NAMES = {"CTO": "Giám đốc công nghệ", "PM": "Quản lý dự án", "CISO": "Giám đốc an ninh thông tin"}
ROUTE_NAMES = {**DEPARTMENT_NAMES, **ROLE_NAMES}
# Mã đứng sau "thực hiện:", "nghiệm thu:" hoặc mũi tên. "QL trực tiếp", "TP Mua sắm" không nằm trong bảng nên giữ nguyên.
_ROUTE_CODE = re.compile(r"((?:thực hiện:|nghiệm thu:|→|⇒)\s*)([A-Z][A-Z_]+)\b")


def pretty_route(route: str) -> str:
    """"QL trực tiếp → HR (khi days_gt 3: …)" -> "QL trực tiếp → Nhân sự (khi trên 3 ngày: …)"; số tiền có dấu chấm
    ngăn cách; mã bộ phận và chức danh ("thực hiện: ADMIN", "→ CTO") thành tên người dùng hiểu."""
    out = route or ""
    for rx, template in _CONDITIONS:
        out = rx.sub(lambda m, t=template: t.format(f"{int(m.group(1)):,}".replace(",", ".")), out)
    return _ROUTE_CODE.sub(lambda m: m.group(1) + ROUTE_NAMES.get(m.group(2), m.group(2)), out)
