r"""Huấn luyện TOÀN BỘ mô hình AI của EAS bằng một lệnh duy nhất.

    ai_service\.venv-ai\Scripts\python.exe ai_service\training\train.py
    ... train.py --only nlp      # chỉ bộ phân loại văn bản
    ... train.py --only risk     # chỉ bộ chấm điểm rủi ro
    ... train.py --check         # chỉ nạp model hiện có và chạy thử vài câu

Nguồn dữ liệu (đều nằm trong repo, không cần file sinh tạm):
  * api_core/catalog/catalog_v2.json           danh mục 58 loại yêu cầu đang dùng
  * training/data/request_corpus.json          tệp huấn luyện văn bản (mẫu câu)
  * training/data/request_eval_realistic.json  câu viết tay để đánh giá, không train
  * training/data/request_eval_short.json      câu rất ngắn viết tay ("bố mất"), không train
  * training/data/request_public_train.json    câu yêu cầu THẬT từ bộ dữ liệu công khai (phiếu IT,
                                               CLINC150, BANKING77), đã dịch và gán nhãn; có train
  * training/data/request_eval_public.json     phần test của các bộ công khai + câu ngoài phạm vi
                                               (MASSIVE vi-VN), không train

Cùng --seed thì cùng dữ liệu, cùng model, cùng tên file. Model chỉ được thay
khi mọi bước train xong (ghi vào thư mục tạm rồi mới chuyển sang models/).
Kết quả: models/*.pkl|json và training/data/training_report.md (ghi đè).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

AI_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_DIR.parent
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from nlp_text import (  # noqa: E402
    ADVANCE_TIERS,
    LEGACY_TYPE_ALIASES,
    normalize_text,
    refine_advance_tier,
    strip_diacritics,
)

DATA_DIR = AI_DIR / "training" / "data"
MODELS_DIR = AI_DIR / "models"
CATALOG_PATH = REPO_ROOT / "api_core" / "catalog" / "catalog_v2.json"
CORPUS_PATH = DATA_DIR / "request_corpus.json"
EVAL_PATH = DATA_DIR / "request_eval_realistic.json"
EVAL_SHORT_PATH = DATA_DIR / "request_eval_short.json"
PUBLIC_TRAIN_PATH = DATA_DIR / "request_public_train.json"
EVAL_PUBLIC_PATH = DATA_DIR / "request_eval_public.json"
REPORT_PATH = DATA_DIR / "training_report.md"

PIPELINE_VERSION = "catalog-v2-public-2-context"
# Số bản sao của mỗi câu thật khi ghép với ~38.000 câu tổng hợp (luân phiên có dấu /
# không dấu). 0 = không dùng dữ liệu thật; giá trị được chọn trên tập dev.
PUBLIC_WEIGHTS = (0, 3, 6)
OUT_OF_SCOPE = "__OUT_OF_SCOPE__"
LOW_CONFIDENCE = 0.35  # cùng ngưỡng với routers/classify.py
OTHER_TYPE = "__OTHER__"

NLP_ARTIFACTS = ["nlp_classifier.pkl", "nlp_labels.json"]
RISK_DOMAINS = ("finance", "hr", "it")
RISK_ARTIFACTS = [
    "risk_model.pkl",
    "feature_columns.json",
    "encoders.json",
    *(f"risk_model_{d}.pkl" for d in RISK_DOMAINS),
    *(f"feature_cols_{d}.json" for d in RISK_DOMAINS),
    "domain_model_registry.json",
]
# Files written by the pipelines this script replaced.
OBSOLETE_ARTIFACTS = [
    "nlp_vectorizer.pkl",
    "nlp_request_type_model.pkl",
    "nlp_department_model.pkl",
    "nlp_template_model.pkl",
]

EXECUTOR_DEPARTMENT = {
    "EXECUTOR_FINANCE": "FINANCE",
    "EXECUTOR_HR": "HR",
    "EXECUTOR_IT": "IT",
    "EXECUTOR_TECH": "TECH",
    "EXECUTOR_ADMIN": "ADMIN",
    "EXECUTOR_ASSET": "ASSET",
    "EXECUTOR_PROCUREMENT": "PROCUREMENT",
    "EXECUTOR_FACILITY": "FACILITY",
    "EXECUTOR_LEGAL": "LEGAL",
    "EXECUTOR_MARKETING": "MARKETING",
    "EXECUTOR_WAREHOUSE": "WAREHOUSE",
}
# Types without an executor are closed by their approvers.
CATEGORY_DEPARTMENT = {
    "ABSENCE": "HR",
    "WORKTIME": "HR",
    "PEOPLE": "HR",
    "PAYMENT": "FINANCE",
    "PROCUREMENT": "PROCUREMENT",
    "BORROW": "ADMIN",
    "PROVISION": "ADMIN",
    "SALES": "SALES",
    "LEGAL": "LEGAL",
    "SUPPORT": "IT",
    "WORK": "ADMIN",
    "ASSET": "ASSET",
}

# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def load_catalog() -> dict[str, Any]:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    groups = {g["code"]: g["label"] for g in raw["groups"]}
    types: dict[str, dict[str, Any]] = {}
    for item in raw["items"]:
        if item.get("status") != "ACTIVE":
            continue
        executor = (item.get("route_rules") or {}).get("executor")
        department = EXECUTOR_DEPARTMENT.get(executor) or CATEGORY_DEPARTMENT.get(
            item["category"], "ADMIN"
        )
        types[item["code"]] = {
            "name": item["name"],
            "category": item["category"],
            "category_label": groups.get(item["category"], item["category"]),
            "department": department,
            "lifecycle": item["lifecycle"],
            "risk_weight": int(item["risk_weight"]),
            "approval_level": int(item.get("approval_level") or 1),
            "approval_route": item.get("approval_route") or "",
        }
    if not types:
        raise ValueError(f"No ACTIVE request types in {CATALOG_PATH}")
    return {"groups": groups, "types": types}


# ---------------------------------------------------------------------------
# NLP dataset (deterministic expansion of request_corpus.json)
# ---------------------------------------------------------------------------

_SLOT = re.compile(r"\{(\w+)\}")


def _fill(template: str, slots: dict[str, list[str]], rng: random.Random) -> str:
    return _SLOT.sub(lambda m: rng.choice(slots[m.group(1)]), template)


def validate_corpus(corpus: dict[str, Any], catalog: dict[str, Any]) -> None:
    active = set(catalog["types"])
    types = corpus["types"]
    unknown = sorted(set(types) - active)
    missing = sorted(active - set(types))
    if unknown:
        raise ValueError(f"Corpus has codes that are not ACTIVE in the catalog: {unknown}")
    if missing:
        raise ValueError(f"Corpus has no examples for catalog codes: {missing}")
    for code, spec in types.items():
        slots = {**corpus["slots"], **spec.get("slots", {})}
        if len(spec.get("titles", [])) < 3 or not spec.get("details"):
            raise ValueError(f"{code}: needs at least 3 titles and 1 detail")
        for template in [*spec["titles"], *spec["details"], *spec.get("short", [])]:
            for name in _SLOT.findall(template):
                if name not in slots:
                    raise ValueError(f"{code}: unknown slot {{{name}}} in {template!r}")


def build_nlp_dataset(
    corpus: dict[str, Any], per_type: int, seed: int, short_per_type: int = 200
) -> pd.DataFrame:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for code in sorted(corpus["types"]):
        spec = corpus["types"][code]
        slots = {**corpus["slots"], **spec.get("slots", {})}
        seen: set[str] = set()
        attempts = 0
        while len(seen) < per_type and attempts < per_type * 6:
            attempts += 1
            title_index = rng.randrange(len(spec["titles"]))
            title = _fill(spec["titles"][title_index], slots, rng)
            roll = rng.random()
            if roll < 0.15:
                description = ""
            elif roll < 0.85:
                description = _fill(rng.choice(spec["details"]), slots, rng)
            else:
                picks = rng.sample(spec["details"], min(2, len(spec["details"])))
                description = " ".join(_fill(p, slots, rng) for p in picks)
            title = f"{rng.choice(corpus['prefixes'])}{title}"
            description = f"{description}{rng.choice(corpus['suffixes'])}".strip()
            text = f"{title}. {description}" if description else title
            augment = rng.random()
            if augment < 0.25:
                text = strip_diacritics(text)
            elif augment < 0.40:
                text = text.lower()
            if rng.random() < 0.05:
                words = text.split()
                if len(words) > 4:
                    del words[rng.randrange(len(words))]
                    text = " ".join(words)
            key = normalize_text(text)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "text": key,
                    "request_type": code,
                    "template_group": f"{code}#{title_index}",
                }
            )
        # Very short inputs ("bố mất", "quên chấm công"): no prefix, suffix or
        # detail, so a 2-3 word title is learnt as a request on its own.
        short = spec.get("short", [])
        target = min(short_per_type, len(short) * 25) if short else 0
        short_seen: set[str] = set()
        attempts = 0
        while len(short_seen) < target and attempts < target * 8:
            attempts += 1
            index = rng.randrange(len(short))
            text = _fill(short[index], slots, rng)
            if rng.random() < 0.35:
                text = strip_diacritics(text)
            key = normalize_text(text)
            if key in short_seen or key in seen:
                continue
            short_seen.add(key)
            rows.append(
                {"text": key, "request_type": code, "template_group": f"{code}#s{index}"}
            )
    return pd.DataFrame(rows)


def heldout_template_split(
    frame: pd.DataFrame, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Hold out ~20% of each type's TITLE templates: the test rows use phrasings
    the model never saw, which a random row split would hide."""
    rng = random.Random(seed + 7)
    test_groups: set[str] = set()
    for code, groups in frame.groupby("request_type")["template_group"]:
        unique = sorted(set(groups))
        k = max(1, round(len(unique) * 0.2))
        test_groups.update(rng.sample(unique, k))
    is_test = frame["template_group"].isin(test_groups).to_numpy()
    return np.where(~is_test)[0], np.where(is_test)[0]


ACCENT_CHARS = False


def make_text_pipeline(c_value: float, seed: int, accent_chars: bool = ACCENT_CHARS) -> Pipeline:
    accented = [
        (
            # Ký tự GIỮ DẤU: không dấu thì "muộn" (đi muộn), "mượn" (mượn đồ), "muốn" cùng là "muon".
            # Đứng sau "word" để type_memory vẫn đọc từ vựng ở transformer_list[0].
            "char_accent",
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=5, sublinear_tf=True,
                            max_features=30000),
        )
    ] if accent_chars else []
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=60000
                ),
            ),
            (
                # Accent-free character n-grams: robust to typos and to users
                # typing Vietnamese without diacritics.
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=3,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    max_features=150000,
                ),
            ),
            *accented,
        ]
    )
    classifier = LogisticRegression(C=c_value, max_iter=3000, random_state=seed)
    return Pipeline([("features", features), ("classifier", classifier)])


def predict_codes(
    model: Pipeline, texts: list[str], top_k: int = 3
) -> tuple[list[str], list[list[str]]]:
    normalized = [normalize_text(t) for t in texts]
    probabilities = model.predict_proba(normalized)
    classes = model.classes_
    top1: list[str] = []
    topk: list[list[str]] = []
    for text, row in zip(texts, probabilities):
        order = np.argsort(row)[::-1][:top_k]
        ranked = [str(classes[i]) for i in order]
        ranked[0] = refine_advance_tier(ranked[0], text)
        top1.append(ranked[0])
        topk.append(ranked)
    return top1, topk


def load_eval_items(path: Path = EVAL_PATH) -> list[dict[str, str]]:
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    for item in items:
        item["text"] = f"{item['title']}. {item.get('description') or ''}".strip(" .")
    return items


def load_public_train(catalog: dict[str, Any]) -> list[dict[str, str]]:
    """Real requests from public datasets (translated, relabelled); [] if absent."""
    if not PUBLIC_TRAIN_PATH.is_file():
        return []
    items = load_eval_items(PUBLIC_TRAIN_PATH)
    unknown = {i["label"] for i in items} - set(catalog["types"])
    if unknown:
        raise ValueError(f"Public train labels not in catalog: {sorted(unknown)}")
    return items


def public_rows(items: list[dict[str, str]], weight: int) -> tuple[list[str], list[str]]:
    """`weight` copies per real sentence, alternating accented / accent-free text."""
    texts: list[str] = []
    labels: list[str] = []
    for item in items:
        for copy in range(weight):
            text = item["text"] if copy % 2 == 0 else strip_diacritics(item["text"])
            texts.append(normalize_text(text))
            labels.append(item["label"])
    return texts, labels


def score_public(model: Pipeline, items: list[dict[str, Any]]) -> dict[str, Any]:
    """In-scope accuracy per source/mapping, and how often out-of-scope text is flagged."""
    normalized = [normalize_text(i["text"]) for i in items]
    probabilities = model.predict_proba(normalized)
    top1, topk = predict_codes(model, [i["text"] for i in items])
    groups: dict[str, list[tuple[bool, bool, bool]]] = {}
    oos_flagged: list[bool] = []
    for item, p1, ranked, row in zip(items, top1, topk, probabilities):
        low = float(row.max()) < LOW_CONFIDENCE
        if item["label"] == OUT_OF_SCOPE:
            oos_flagged.append(low)
            continue
        hit = (p1 == item["label"], item["label"] in ranked, low)
        groups.setdefault(f"{item['source']}:{item['mapping']}", []).append(hit)
        groups.setdefault("ALL_IN_SCOPE", []).append(hit)
    out: dict[str, Any] = {
        name: {
            "rows": len(hits),
            "accuracy": float(np.mean([h[0] for h in hits])),
            "top3_accuracy": float(np.mean([h[1] for h in hits])),
            "low_confidence_rate": float(np.mean([h[2] for h in hits])),
        }
        for name, hits in sorted(groups.items())
    }
    if oos_flagged:
        out["OUT_OF_SCOPE"] = {"rows": len(oos_flagged), "flagged_rate": float(np.mean(oos_flagged))}
    return out


def score_realistic(
    model: Pipeline, items: list[dict[str, str]], catalog: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split in ("dev", "test"):
        subset = [i for i in items if i["split"] == split]
        if not subset:
            continue
        top1, topk = predict_codes(model, [i["text"] for i in subset])
        labels = [i["label"] for i in subset]
        category = catalog["types"]
        result[split] = {
            "rows": len(subset),
            "accuracy": float(np.mean([p == y for p, y in zip(top1, labels)])),
            "top3_accuracy": float(
                np.mean([y in ranked for ranked, y in zip(topk, labels)])
            ),
            "category_accuracy": float(
                np.mean(
                    [
                        category[p]["category"] == category[y]["category"]
                        for p, y in zip(top1, labels)
                    ]
                )
            ),
            "errors": [
                {"text": i["text"], "expected": y, "predicted": p, "top3": r}
                for i, y, p, r in zip(subset, labels, top1, topk)
                if p != y
            ],
        }
    return result


def train_nlp(
    staging: Path,
    catalog: dict[str, Any],
    per_type: int,
    seed: int,
    short_per_type: int = 200,
    # C=5 cố định (19/11): với C>=10 mô hình tự tin quá mức, câu ngoài danh mục được nhận ra 87% -> 74%
    # (xem data/request_everyday_report.md). Muốn dò lại: --nlp-c 2 5 10 20.
    c_values: tuple[float, ...] = (5.0,),
    accent_chars: bool | None = None,
) -> dict[str, Any]:
    accent_chars = ACCENT_CHARS if accent_chars is None else accent_chars
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    validate_corpus(corpus, catalog)
    frame = build_nlp_dataset(corpus, per_type, seed, short_per_type)
    train_idx, test_idx = heldout_template_split(frame, seed)
    texts = frame["text"].tolist()
    labels = frame["request_type"].to_numpy()
    eval_items = load_eval_items()
    short_items = load_eval_items(EVAL_SHORT_PATH)
    unknown_labels = {i["label"] for i in [*eval_items, *short_items]} - set(catalog["types"])
    if unknown_labels:
        raise ValueError(f"Evaluation labels not in catalog: {sorted(unknown_labels)}")
    dev_items = [i for i in [*eval_items, *short_items] if i["split"] == "dev"]
    public_items = load_public_train(catalog)
    public_train = [i for i in public_items if i["split"] == "train"]
    public_dev = [i for i in public_items if i["split"] == "dev"]
    public_eval = load_eval_items(EVAL_PUBLIC_PATH) if EVAL_PUBLIC_PATH.is_file() else []
    weights = PUBLIC_WEIGHTS if public_items else (0,)
    print(
        f"NLP: {len(frame):,} câu tổng hợp cho {frame['request_type'].nunique()} loại "
        f"| train {len(train_idx):,} / held-out mẫu câu {len(test_idx):,} "
        f"| đánh giá viết tay {len(eval_items)} + câu ngắn {len(short_items)} "
        f"| câu thật công khai train {len(public_train)} / dev {len(public_dev)} / test {len(public_eval)}"
    )

    def accuracy_on(model: Pipeline, items: list[dict[str, str]]) -> float:
        if not items:
            return 0.0
        pred, _ = predict_codes(model, [i["text"] for i in items])
        return float(np.mean([p == i["label"] for p, i in zip(pred, items)]))

    # Choose C and the weight of real sentences on held-out templates, the
    # hand-written dev split and the public dev split (never on any test split).
    candidates: list[tuple[float, int, float, float, float, float]] = []
    for weight in weights:
        extra_texts, extra_labels = public_rows(public_train, weight)
        for c_value in c_values:
            started = time.monotonic()
            model = make_text_pipeline(c_value, seed, accent_chars)
            model.fit(
                [texts[i] for i in train_idx] + extra_texts,
                np.concatenate([labels[train_idx], np.array(extra_labels, dtype=labels.dtype)]),
            )
            heldout_pred, _ = predict_codes(model, [texts[i] for i in test_idx])
            heldout_acc = accuracy_score(labels[test_idx], heldout_pred)
            dev_acc = accuracy_on(model, dev_items)
            public_dev_acc = accuracy_on(model, public_dev)
            candidates.append(
                (c_value, weight, heldout_acc, dev_acc, public_dev_acc, time.monotonic() - started)
            )
            print(
                f"  w={weight} C={c_value:<5} held-out={heldout_acc:.4f} dev viết tay={dev_acc:.4f} "
                f"dev công khai={public_dev_acc:.4f} ({time.monotonic() - started:.0f}s)"
            )
    # Both dev splits count equally (hand-written phrasing and real tickets);
    # held-out templates break ties, then the simpler model wins.
    best = max(
        candidates,
        key=lambda c: (round((c[3] + c[4]) / 2 if public_dev else c[3], 4), round(c[2], 4), -c[0]),
    )
    best_c, best_weight = best[0], best[1]

    # Metrics for the chosen settings, measured before the final refit.
    extra_texts, extra_labels = public_rows(public_train, best_weight)
    model = make_text_pipeline(best_c, seed, accent_chars)
    model.fit(
        [texts[i] for i in train_idx] + extra_texts,
        np.concatenate([labels[train_idx], np.array(extra_labels, dtype=labels.dtype)]),
    )
    heldout_pred, heldout_top = predict_codes(model, [texts[i] for i in test_idx])
    order = sorted(catalog["types"])
    heldout = {
        "rows": int(len(test_idx)),
        "accuracy": float(accuracy_score(labels[test_idx], heldout_pred)),
        "top3_accuracy": float(
            np.mean([y in r for r, y in zip(heldout_top, labels[test_idx])])
        ),
        "f1_macro": float(
            f1_score(labels[test_idx], heldout_pred, labels=order, average="macro")
        ),
    }
    worst = sorted(
        (
            (code, float(np.mean(np.array(heldout_pred)[labels[test_idx] == code] == code)))
            for code in order
        ),
        key=lambda item: item[1],
    )[:8]
    heldout["weakest_types"] = [{"type": c, "accuracy": a} for c, a in worst]

    # Final model: every synthetic sentence plus every public train+dev sentence
    # (hand-written eval and the public test set stay unseen).
    all_texts, all_labels = public_rows(public_items, best_weight)
    final = make_text_pipeline(best_c, seed, accent_chars)
    final.fit(texts + all_texts, np.concatenate([labels, np.array(all_labels, dtype=labels.dtype)]))
    realistic = score_realistic(final, eval_items, catalog)
    short_scores = score_realistic(final, short_items, catalog)
    public_scores = score_public(final, public_eval) if public_eval else {}
    joblib.dump(final, staging / "nlp_classifier.pkl", compress=3)

    labels_payload = {
        "schema_version": 2,
        "pipeline_version": PIPELINE_VERSION,
        "request_type": order,
        "department": sorted({t["department"] for t in catalog["types"].values()}),
        "lifecycle_template": sorted({t["lifecycle"] for t in catalog["types"].values()}),
        "categories": catalog["groups"],
        "catalog": catalog["types"],
        "aliases": LEGACY_TYPE_ALIASES,
        "advance_tiers": list(ADVANCE_TIERS),
    }
    (staging / "nlp_labels.json").write_text(
        json.dumps(labels_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if public_scores:
        print(
            f"  → dữ liệu công khai TEST: trong phạm vi {public_scores['ALL_IN_SCOPE']['accuracy']:.4f}, "
            f"ngoài phạm vi bị gắn cờ {public_scores.get('OUT_OF_SCOPE', {}).get('flagged_rate', 0):.4f}"
        )
    print(
        f"  → chọn C={best_c}, trọng số câu thật={best_weight}: held-out mẫu câu {heldout['accuracy']:.4f}, "
        f"viết tay dev {realistic['dev']['accuracy']:.4f}, "
        f"viết tay TEST {realistic['test']['accuracy']:.4f} "
        f"(top-3 {realistic['test']['top3_accuracy']:.4f}), "
        f"câu ngắn TEST {short_scores['test']['accuracy']:.4f}"
    )
    return {
        "corpus": str(CORPUS_PATH.relative_to(AI_DIR)),
        "evaluation_set": str(EVAL_PATH.relative_to(AI_DIR)),
        "short_evaluation_set": str(EVAL_SHORT_PATH.relative_to(AI_DIR)),
        "types": len(order),
        "synthetic_rows": int(len(frame)),
        "rows_per_type": per_type,
        "corpus_templates": {
            "titles": sum(len(s["titles"]) for s in corpus["types"].values()),
            "details": sum(len(s["details"]) for s in corpus["types"].values()),
            "short": sum(len(s.get("short", [])) for s in corpus["types"].values()),
        },
        "model": "TF-IDF từ (1-2 gram) + ký tự không dấu (2-5 gram) → Logistic Regression",
        "public_train_set": str(PUBLIC_TRAIN_PATH.relative_to(AI_DIR)) if public_items else None,
        "public_evaluation_set": str(EVAL_PUBLIC_PATH.relative_to(AI_DIR)) if public_eval else None,
        "public_rows": {"train": len(public_train), "dev": len(public_dev), "test": len(public_eval)},
        "c_search": [
            {"C": c, "public_weight": w, "heldout_accuracy": h, "dev_accuracy": d,
             "public_dev_accuracy": pd_}
            for c, w, h, d, pd_, _ in candidates
        ],
        "chosen_c": best_c,
        "chosen_public_weight": best_weight,
        "heldout_templates": heldout,
        "realistic": realistic,
        "short_inputs": short_scores,
        "public_test": public_scores,
    }


# ---------------------------------------------------------------------------
# Risk dataset (deterministic simulation of catalog requests)
# ---------------------------------------------------------------------------

M = 1_000_000
# (typical low, typical high) VND for types that carry an amount; editable assumptions.
AMOUNT_PROFILE = {
    "ADVANCE_SMALL": (0.5 * M, 10 * M),
    "ADVANCE_MEDIUM": (10 * M, 50 * M),
    "ADVANCE_LARGE": (50 * M, 1000 * M),
    "EXPENSE_CLAIM": (0.2 * M, 20 * M),
    "REFUND_COMPENSATION": (0.1 * M, 10 * M),
    "REIMBURSEMENT": (0.5 * M, 50 * M),
    "SALARY_ADVANCE": (1 * M, 20 * M),
    "TAX_INVOICE_ISSUE": (1 * M, 500 * M),
    "VENDOR_PAYMENT": (20 * M, 2000 * M),
    "BUDGET_REALLOCATION": (20 * M, 1000 * M),
    "EQUIPMENT": (5 * M, 200 * M),
    "PURCHASE_REQUEST": (1 * M, 100 * M),
    "SAAS_LICENSE_BUY": (2 * M, 200 * M),
    "OFFICE_SUPPLIES": (0.1 * M, 5 * M),
    "BUSINESS_TRIP": (1 * M, 50 * M),
    "REWARD_REQ": (0.5 * M, 20 * M),
    "SALARY_ADJUSTMENT": (1 * M, 15 * M),
    "TRAINING_COURSE": (1 * M, 50 * M),
    "PROJECT_INITIATION": (50 * M, 2000 * M),
    "CONTRACT_APPROVAL": (20 * M, 5000 * M),
    "MARKETING_CAMPAIGN": (10 * M, 1000 * M),
    "FLASH_SALE_VOUCHER": (5 * M, 300 * M),
    "SPECIAL_DISCOUNT": (5 * M, 500 * M),
    "ASSET_DISPOSAL": (1 * M, 200 * M),
    "FACILITY_REPAIR": (0.5 * M, 50 * M),
}
IT_RISK_TYPES = {
    "ACCESS",
    "PROD_DATA_ACCESS",
    "SERVER_FIREWALL",
    "LAPTOP_PROVISION",
    "RESOURCE_REVOKE",
    "IT_SUPPORT",
    "SECURITY_INCIDENT_HOTFIX",
    "DATA_UAT_EXPORT",
    "FEATURE_RELEASE",
}
FINANCE_CATEGORIES = {"PAYMENT", "PROCUREMENT", "SALES"}
HR_CATEGORIES = {"ABSENCE", "WORKTIME", "PEOPLE"}

ROLES = ["intern", "junior", "senior", "lead", "manager", "director"]
ROLE_WEIGHTS = [0.08, 0.35, 0.27, 0.15, 0.10, 0.05]
URGENCIES = ["low", "medium", "high", "urgent"]
URGENCY_WEIGHTS = [0.2, 0.5, 0.22, 0.08]
REQUESTER_DEPARTMENTS = ["finance", "hr", "it", "legal", "marketing", "operations", "sales"]

RISK_FEATURES = [
    "request_type_enc",
    "risk_weight",
    "department_enc",
    "user_role_enc",
    "priority_level_enc",
    "amount_log",
    "amount_millions",
    "budget_log",
    "amount_to_budget_ratio",
    "is_over_budget",
    "is_split_amount_suspect",
    "has_receipt",
    "num_attachments",
    "no_receipt_has_amount",
    "user_tenure_months",
    "past_requests_count",
    "past_rejection_rate",
    "high_rejection_rate",
    "is_off_hours",
    "is_template_matched",
    # Ngữ cảnh vận hành (18/11/2026, HUONG_DAN_TRAIN_AI.md mục 4.2): tính từ CSDL ở
    # api_core/workflow/bad_case_signals.py, cùng nghĩa ở routers/risk.py.
    "pending_work_due_24h",
    "work_due_in_absence",
    "handover_uncovered",
    "team_absence_ratio",
    "same_type_count_30d",
]
CONTEXT_CATEGORIES = {"ABSENCE"}
# Lần 2 (19/11): bộ 1 cho thấy mô hình gần như bỏ qua ngữ cảnh ở công tác/WFH vì mẫu có ngữ cảnh quá hiếm
# (~11% dòng nhóm vắng mặt chạm luật). Nhóm vắng mặt: gấp đôi số dòng, ngữ cảnh dày hơn, lấy mẫu sát ngưỡng
# (vắng 30-50%, lần 2-6). Các nhóm khác giữ phân phối cũ.
RISK_DATA_VERSION = "context-2"
CONTEXT_ROWS_FACTOR = 2


def risk_domain(code: str, catalog: dict[str, Any]) -> str:
    if code in IT_RISK_TYPES:
        return "it"
    category = catalog["types"].get(code, {}).get("category")
    if category in FINANCE_CATEGORIES or code in {"CONTRACT_APPROVAL", "ASSET_DISPOSAL"}:
        return "finance"
    if category in HR_CATEGORIES:
        return "hr"
    return "master"


def _risk_label(row: dict[str, Any], typical_high: float, rng: random.Random) -> int:
    """Simulated reviewer policy (editable assumption, not company data)."""
    amount = row["amount_vnd"]
    if amount > 0 and amount > row["budget_remaining_vnd"]:
        return 5  # hard rule: over the remaining budget
    score = row["risk_weight"]
    flags = 0
    if amount > 0 and typical_high:
        if amount > typical_high:
            score += 1
            flags += 1
        if amount > 2 * typical_high:
            score += 1
    if row["is_split_amount_suspect"]:
        score = max(score + 2, 4)
        flags += 1
    if amount > 0 and not row["has_receipt"] and row["category"] == "PAYMENT":
        score += 1
        flags += 1
    if row["past_rejection_rate"] > 0.3:
        score += 1
        flags += 1
    if row["is_off_hours"] and (amount > 0 or row["domain"] == "it"):
        score += 1
        flags += 1
    if not row["is_template_matched"]:
        score += 1
        flags += 1
    if row["user_tenure_months"] < 3 and row["risk_weight"] >= 3:
        score += 1
        flags += 1
    if row["category"] in CONTEXT_CATEGORIES:
        # Ví dụ của thầy: xin nghỉ khi đang giữ việc sắp hết hạn mà không ai làm thay được.
        if row["pending_work_due_24h"] > 0 and row["handover_uncovered"]:
            score = max(score + 2, 4)
            flags += 1
        elif row["work_due_in_absence"] > 0 and row["handover_uncovered"]:
            score += 1
            flags += 1
        if row["team_absence_ratio"] >= 0.4:
            score += 1
            flags += 1
        if row["same_type_count_30d"] >= 4:
            score += 1
            flags += 1
    if row["user_role"] in ("manager", "director") and flags == 0:
        score -= 1
    if rng.random() < 0.03:  # reviewers disagree on a few borderline cases
        score += rng.choice((-1, 1))
    return int(min(5, max(1, score)))


def _team_ratio(rng: random.Random, dense: bool) -> float:
    roll = rng.random()
    if dense and roll < 0.2:
        return rng.uniform(0.3, 0.5)  # sát ngưỡng 40%
    if roll < (0.3 if dense else 0.1):
        return rng.uniform(0.35, 0.8)
    return rng.betavariate(1.3, 7)


def _same_type_count(rng: random.Random, dense: bool) -> int:
    roll = rng.random()
    if dense and roll < 0.2:
        return rng.randint(2, 6)  # sát ngưỡng lần thứ 4
    if roll < (0.3 if dense else 0.08):
        return rng.randint(4, 10)
    return min(3, int(rng.expovariate(1 / 1.2)))


def build_risk_dataset(
    catalog: dict[str, Any], per_type: int, seed: int
) -> pd.DataFrame:
    rng = random.Random(seed + 101)
    rows: list[dict[str, Any]] = []
    codes = sorted(catalog["types"])
    plan = [
        (code, per_type * (CONTEXT_ROWS_FACTOR if catalog["types"][code]["category"] in CONTEXT_CATEGORIES else 1))
        for code in codes
    ] + [(OTHER_TYPE, per_type * 3)]
    for code, count in plan:
        spec = catalog["types"].get(code)
        for _ in range(count):
            if spec is None:
                weight = rng.randint(1, 5)
                category = rng.choice(["PAYMENT", "WORK", "SUPPORT", "PEOPLE"])
                profile = (
                    (1 * M, rng.choice([10, 50, 200]) * M) if rng.random() < 0.5 else None
                )
            else:
                weight = spec["risk_weight"]
                category = spec["category"]
                profile = AMOUNT_PROFILE.get(code)
            role = rng.choices(ROLES, ROLE_WEIGHTS)[0]
            tenure_max = {"intern": 6, "junior": 36, "senior": 96, "lead": 120, "manager": 180, "director": 240}[role]
            amount = 0.0
            if profile:
                low, high = profile
                roll = rng.random()
                if roll < 0.85:
                    amount = float(np.exp(rng.uniform(np.log(low), np.log(high))))
                elif roll < 0.97:
                    amount = high * rng.uniform(1.0, 3.0)
                else:
                    amount = 0.0
                amount = round(amount, -3)
            if amount > 0:
                budget = amount * float(np.exp(rng.gauss(1.2, 0.8)))
                if rng.random() < 0.07:
                    budget = amount * rng.uniform(0.1, 0.95)
            else:
                budget = rng.uniform(50, 1000) * M
            has_receipt = 1 if (amount == 0 or rng.random() < 0.85) else 0
            rejection = (
                rng.uniform(0.3, 0.8) if rng.random() < 0.08 else min(0.3, rng.betavariate(1, 9))
            )
            dense = category in CONTEXT_CATEGORIES
            row = {
                "request_type": code,
                "category": category,
                "domain": risk_domain(code, catalog) if spec else "master",
                "risk_weight": weight,
                "department": rng.choice(REQUESTER_DEPARTMENTS),
                "user_role": role,
                "priority_level": rng.choices(URGENCIES, URGENCY_WEIGHTS)[0],
                "amount_vnd": amount,
                "budget_remaining_vnd": round(budget, -3),
                "has_receipt": has_receipt,
                "num_attachments": max(has_receipt if amount else 0, min(6, int(rng.expovariate(0.7)))),
                "user_tenure_months": rng.randint(0, tenure_max),
                "past_requests_count": min(40, int(rng.expovariate(1 / 6))),
                "past_rejection_rate": round(rejection, 3),
                "is_off_hours": int(rng.random() < 0.12),
                "is_split_amount_suspect": int(amount > 0 and rng.random() < 0.03),
                "is_template_matched": int(rng.random() < 0.92),
                # Ngữ cảnh vận hành, sinh cho MỌI loại để mô hình học được nó chỉ có tác dụng
                # với nhóm vắng mặt (ABSENCE).
                "pending_work_due_24h": 0 if rng.random() < (0.5 if dense else 0.75) else rng.randint(1, 4),
                "work_due_in_absence": 0 if rng.random() < (0.55 if dense else 0.8) else rng.randint(1, 3),
                "team_absence_ratio": round(_team_ratio(rng, dense), 3),
                "same_type_count_30d": _same_type_count(rng, dense),
            }
            row["handover_uncovered"] = int(
                (row["pending_work_due_24h"] > 0 or row["work_due_in_absence"] > 0)
                and rng.random() < (0.5 if dense else 0.45)
            )
            row["risk_score"] = _risk_label(row, profile[1] if profile else 0.0, rng)
            rows.append(row)
    return pd.DataFrame(rows)


def make_encoders(catalog: dict[str, Any]) -> dict[str, dict[str, int]]:
    def index(values: list[str]) -> dict[str, int]:
        return {value: i for i, value in enumerate(values)}

    return {
        "request_type": index([*sorted(catalog["types"]), OTHER_TYPE]),
        "department": index(sorted(REQUESTER_DEPARTMENTS)),
        "user_role": index(sorted(ROLES)),
        "priority_level": index(sorted(URGENCIES)),
    }


def risk_features(frame: pd.DataFrame, encoders: dict[str, dict[str, int]]) -> pd.DataFrame:
    """Must match routers/risk.py::build_feature_vector."""
    amount = frame["amount_vnd"].astype(float)
    budget = frame["budget_remaining_vnd"].astype(float)
    out = pd.DataFrame(index=frame.index)
    out["request_type_enc"] = frame["request_type"].map(encoders["request_type"])
    out["risk_weight"] = frame["risk_weight"]
    out["department_enc"] = frame["department"].map(encoders["department"])
    out["user_role_enc"] = frame["user_role"].map(encoders["user_role"])
    out["priority_level_enc"] = frame["priority_level"].map(encoders["priority_level"])
    out["amount_log"] = np.log1p(amount)
    out["amount_millions"] = amount / 1e6
    out["budget_log"] = np.log1p(budget)
    out["amount_to_budget_ratio"] = amount / (budget + 1.0)
    out["is_over_budget"] = (amount > budget).astype(int)
    for column in (
        "is_split_amount_suspect",
        "has_receipt",
        "num_attachments",
        "user_tenure_months",
        "past_requests_count",
        "past_rejection_rate",
        "is_off_hours",
        "is_template_matched",
        "pending_work_due_24h",
        "work_due_in_absence",
        "handover_uncovered",
        "team_absence_ratio",
        "same_type_count_30d",
    ):
        out[column] = frame[column]
    out["no_receipt_has_amount"] = ((amount > 0) & (frame["has_receipt"] == 0)).astype(int)
    out["high_rejection_rate"] = (frame["past_rejection_rate"] > 0.25).astype(int)
    features = out[RISK_FEATURES].astype(np.float32)
    if features.isna().any().any():
        raise ValueError("Risk features contain values missing from the encoders.")
    return features


def _fit_risk_model(
    name: str, features: pd.DataFrame, scores: np.ndarray, threads: int, seed: int
) -> tuple[xgb.XGBClassifier, dict[str, Any], dict[int, int]]:
    classes = sorted(set(scores.tolist()))
    to_index = {value: i for i, value in enumerate(classes)}
    y = np.array([to_index[s] for s in scores])
    x = features.to_numpy()
    x_rest, x_test, y_rest, y_test = train_test_split(
        x, y, test_size=0.15, random_state=seed, stratify=y
    )
    x_train, x_val, y_train, y_val = train_test_split(
        x_rest, y_rest, test_size=0.15, random_state=seed + 1, stratify=y_rest
    )
    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=2,
        objective="multi:softprob",
        num_class=len(classes),
        eval_metric="mlogloss",
        tree_method="hist",
        early_stopping_rounds=30,
        random_state=seed,
        n_jobs=threads,
        verbosity=0,
    )
    started = time.monotonic()
    model.fit(x_train, y_train, eval_set=[(x_val, y_val)], verbose=False)
    predicted = np.array([classes[i] for i in model.predict(x_test)])
    expected = np.array([classes[i] for i in y_test])
    metrics = {
        "rows": int(len(x)),
        "accuracy": float(accuracy_score(expected, predicted)),
        "within_one": float(np.mean(np.abs(expected - predicted) <= 1)),
        "f1_macro": float(f1_score(expected, predicted, average="macro")),
        "classes": classes,
        "confusion_matrix": confusion_matrix(expected, predicted, labels=classes).tolist(),
        "best_iteration": int(model.best_iteration),
        "seconds": round(time.monotonic() - started, 1),
        "top_features": [
            [f, round(float(v), 4)]
            for f, v in sorted(
                zip(RISK_FEATURES, model.feature_importances_), key=lambda p: -p[1]
            )[:6]
        ],
    }
    print(
        f"  {name}: {len(x):,} dòng, accuracy={metrics['accuracy']:.4f}, "
        f"lệch ≤1 bậc={metrics['within_one']:.4f}, macro-F1={metrics['f1_macro']:.4f} "
        f"({metrics['seconds']}s)"
    )
    return model, metrics, {i: v for v, i in to_index.items()}


def train_risk(
    staging: Path, catalog: dict[str, Any], per_type: int, threads: int, seed: int
) -> dict[str, Any]:
    frame = build_risk_dataset(catalog, per_type, seed)
    encoders = make_encoders(catalog)
    features = risk_features(frame, encoders)
    scores = frame["risk_score"].to_numpy()
    print(
        f"Risk: {len(frame):,} yêu cầu mô phỏng | phân bố điểm "
        f"{dict(sorted(Counter(scores.tolist()).items()))}"
    )
    results: dict[str, Any] = {}
    model, metrics, reverse = _fit_risk_model("Master", features, scores, threads, seed)
    joblib.dump(model, staging / "risk_model.pkl", compress=3)
    _write_json(staging / "feature_columns.json", RISK_FEATURES)
    _write_json(staging / "encoders.json", encoders)
    results["master"] = metrics

    type_domains = {
        code: risk_domain(code, catalog) for code in sorted(catalog["types"])
    }
    registry: dict[str, Any] = {
        "pipeline_version": PIPELINE_VERSION,
        "type_domains": type_domains,
        "aliases": LEGACY_TYPE_ALIASES,
        "other_type": OTHER_TYPE,
    }
    for domain in RISK_DOMAINS:
        mask = frame["domain"].eq(domain).to_numpy()
        model, metrics, reverse = _fit_risk_model(
            domain.title(), features[mask], scores[mask], threads, seed
        )
        joblib.dump(model, staging / f"risk_model_{domain}.pkl", compress=3)
        _write_json(
            staging / f"feature_cols_{domain}.json",
            {
                "feature_cols": RISK_FEATURES,
                "label_remap": {str(v): i for i, v in reverse.items()},
                "reverse_remap": {str(i): int(v) for i, v in reverse.items()},
            },
        )
        registry[domain] = {
            "model_file": f"risk_model_{domain}.pkl",
            "features_file": f"feature_cols_{domain}.json",
            "accuracy": round(metrics["accuracy"], 4),
            "f1_macro": round(metrics["f1_macro"], 4),
            "rows": metrics["rows"],
            "request_types": sorted(c for c, d in type_domains.items() if d == domain),
        }
        results[domain] = metrics
    _write_json(staging / "domain_model_registry.json", registry)
    results["rows"] = int(len(frame))
    results["data_version"] = RISK_DATA_VERSION
    results["rows_per_type"] = per_type
    results["label_policy"] = (
        "Mô phỏng: điểm gốc = risk_weight của loại; vượt ngân sách còn lại = 5; "
        "nghi chia nhỏ +2 (tối thiểu 4); vượt mức thông thường +1/+2; thiếu chứng từ "
        "thanh toán +1; tỷ lệ bị từ chối >30% +1; ngoài giờ (có tiền hoặc IT) +1; sai "
        "biểu mẫu +1; thâm niên <3 tháng với loại rủi ro ≥3 +1; ngữ cảnh (chỉ nhóm vắng mặt "
        "ABSENCE): giữ việc đến hạn ≤24h mà bàn giao không làm thay được -> tối thiểu 4 (+2), "
        "có việc đến hạn trong thời gian vắng mà bàn giao không làm thay được +1, đồng nghiệp "
        "vắng trùng ngày ≥40% +1, lần thứ ≥4 cùng loại trong 30 ngày +1; quản lý không có cờ "
        "-1; 3% nhiễu ±1."
    )
    return results


# ---------------------------------------------------------------------------
# Artifacts, report, check
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def commit_artifacts(staging: Path, names: list[str]) -> None:
    """Move every new file into models/ at the end; restore all on any failure."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".backup-", dir=MODELS_DIR) as backup_name:
        backup = Path(backup_name)
        touched = [*names, *OBSOLETE_ARTIFACTS]
        for name in touched:
            if (MODELS_DIR / name).is_file():
                shutil.copy2(MODELS_DIR / name, backup / name)
        try:
            for name in names:
                os.replace(staging / name, MODELS_DIR / name)
            for name in OBSOLETE_ARTIFACTS:
                (MODELS_DIR / name).unlink(missing_ok=True)
        except Exception:
            for name in touched:
                if (backup / name).is_file():
                    os.replace(backup / name, MODELS_DIR / name)
            raise


def write_report(metadata: dict[str, Any]) -> None:
    nlp = metadata.get("nlp_metrics")
    risk = metadata.get("risk_metrics")
    lines = [
        "# Báo cáo huấn luyện AI — EAS",
        "",
        f"- Phiên bản pipeline: `{metadata['pipeline_version']}`",
        f"- Thời điểm: {metadata['trained_at']} (seed {metadata['random_state']}, "
        f"{metadata['training_duration_seconds']} giây)",
        "- Lệnh: `ai_service\\.venv-ai\\Scripts\\python.exe ai_service\\training\\train.py`",
        "",
        "> Dữ liệu huấn luyện gồm câu tổng hợp từ mẫu câu và câu yêu cầu thật từ bộ dữ liệu "
        "công khai (đã dịch, gán nhãn). Con số đáng tin nhất là độ chính xác trên các tập "
        "**test** (viết tay và công khai), vì các câu này không được dùng để train.",
        "",
    ]
    if nlp:
        real = nlp["realistic"]
        lines += [
            "## 1. Phân loại yêu cầu từ văn bản",
            "",
            f"- {nlp['types']} loại yêu cầu ACTIVE của catalog v2; "
            f"{nlp['synthetic_rows']:,} câu sinh từ {nlp['corpus_templates']['titles']} mẫu tiêu đề "
            f"và {nlp['corpus_templates']['details']} mẫu mô tả, "
            f"{nlp['corpus_templates'].get('short', 0)} mẫu câu rất ngắn.",
            f"- Câu thật từ bộ dữ liệu công khai: {nlp.get('public_rows', {}).get('train', 0)} train + "
            f"{nlp.get('public_rows', {}).get('dev', 0)} dev (`{nlp.get('public_train_set')}`), "
            f"mỗi câu nhân {nlp.get('chosen_public_weight', 0)} bản (có dấu / không dấu).",
            f"- Mô hình: {nlp['model']}, C={nlp['chosen_c']}.",
            "",
            "| Tập đánh giá | Số câu | Đúng loại (top-1) | Đúng trong top-3 | Đúng nhóm |",
            "|---|---:|---:|---:|---:|",
            f"| Mẫu câu bị giữ lại (chưa từng thấy) | {nlp['heldout_templates']['rows']:,} | "
            f"{nlp['heldout_templates']['accuracy']:.1%} | {nlp['heldout_templates']['top3_accuracy']:.1%} | — |",
        ]
        short = nlp.get("short_inputs", {})
        for scores, prefix in ((real, "Viết tay"), (short, "Câu rất ngắn")):
            for split in ("dev", "test"):
                if split in scores:
                    r = scores[split]
                    label = f"{prefix} — dev" if split == "dev" else f"**{prefix} — test**"
                    lines.append(
                        f"| {label} | {r['rows']} | {r['accuracy']:.1%} | "
                        f"{r['top3_accuracy']:.1%} | {r['category_accuracy']:.1%} |"
                    )
        public = nlp.get("public_test") or {}
        names = {
            "ALL_IN_SCOPE": "**Công khai — tất cả câu trong phạm vi (test)**",
            "it_tickets:manual": "Công khai — phiếu IT thật (test)",
            "clinc:direct": "Công khai — CLINC150, ánh xạ trực tiếp (test)",
            "clinc:approx": "Công khai — CLINC150, ánh xạ gần đúng (test)",
            "banking77:direct": "Công khai — BANKING77, ánh xạ trực tiếp (test)",
            "banking77:approx": "Công khai — BANKING77, ánh xạ gần đúng (test)",
        }
        for key, label in names.items():
            if key in public:
                r = public[key]
                lines.append(
                    f"| {label} | {r['rows']} | {r['accuracy']:.1%} | {r['top3_accuracy']:.1%} | — |"
                )
        if "OUT_OF_SCOPE" in public:
            r = public["OUT_OF_SCOPE"]
            lines += [
                "",
                f"Câu ngoài phạm vi (MASSIVE vi-VN, {r['rows']} câu): {r['flagged_rate']:.1%} bị gắn cờ "
                f"độ tin cậy thấp (< {LOW_CONFIDENCE}), đúng kỳ vọng.",
            ]
        for scores, title in ((real, "Câu viết tay (test)"), (short, "Câu rất ngắn (test)")):
            errors = scores.get("test", {}).get("errors", [])
            lines += ["", f"{title} còn phân loại sai:", ""]
            if not errors:
                lines.append("- (không có)")
            for error in errors:
                lines.append(
                    f"- \"{error['text']}\" → dự đoán `{error['predicted']}`, đúng là "
                    f"`{error['expected']}` (top-3: {', '.join(error['top3'])})"
                )
        lines.append("")
    if risk:
        lines += [
            "## 2. Chấm điểm rủi ro (XGBoost, 1 master + 3 theo lĩnh vực)",
            "",
            f"- {risk['rows']:,} yêu cầu mô phỏng ({risk['rows_per_type']} mỗi loại + loại lạ `__OTHER__`).",
            f"- Quy tắc gán nhãn: {risk['label_policy']}",
            "",
            "| Model | Số dòng | Accuracy | Lệch ≤ 1 bậc | Macro-F1 |",
            "|---|---:|---:|---:|---:|",
        ]
        for name in ("master", *RISK_DOMAINS):
            m = risk[name]
            lines.append(
                f"| {name} | {m['rows']:,} | {m['accuracy']:.1%} | {m['within_one']:.1%} | {m['f1_macro']:.3f} |"
            )
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_check() -> int:
    model = joblib.load(MODELS_DIR / "nlp_classifier.pkl")
    labels = json.loads((MODELS_DIR / "nlp_labels.json").read_text(encoding="utf-8"))
    samples = [
        "bố mất",
        "Xin nghỉ phép 2 ngày về quê",
        "Điều hòa phòng họp tầng 3 bị hỏng",
        "Tổ chức year end party cho 80 người",
        "Tam ung 25 trieu dat coc hoi thao",
        "Mua bản quyền Figma cho team design",
        "Phát hiện email lừa đảo giả mạo giám đốc",
    ]
    top1, top3 = predict_codes(model, samples)
    for text, code, ranked in zip(samples, top1, top3):
        print(f"{text!r:50} → {code:<24} ({labels['catalog'][code]['name']}) top3={ranked}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", choices=("nlp", "risk"))
    parser.add_argument("--check", action="store_true", help="chỉ chạy thử model hiện có")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--nlp-per-type", type=int, default=600)
    parser.add_argument("--nlp-short-per-type", type=int, default=200)
    parser.add_argument("--nlp-accent-chars", choices=("on", "off"),
                        help="thêm n-gram ký tự giữ dấu (mặc định theo ACCENT_CHARS)")
    parser.add_argument("--nlp-c", type=float, nargs="+",
                        help="giá trị C của Logistic Regression được thử (mặc định 5)")
    parser.add_argument("--risk-per-type", type=int, default=1500)
    args = parser.parse_args(argv)
    if args.check:
        return run_check()

    catalog = load_catalog()
    started_at = datetime.now(UTC)
    start = time.monotonic()
    previous = {}
    metadata_path = MODELS_DIR / "model_metadata.json"
    if metadata_path.is_file():
        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
        if previous.get("pipeline_version") != PIPELINE_VERSION and args.only:
            parser.error("Model cũ thuộc pipeline khác: hãy train đầy đủ (bỏ --only) một lần.")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=MODELS_DIR) as staging_name:
        staging = Path(staging_name)
        names: list[str] = []
        nlp_metrics = previous.get("nlp_metrics")
        risk_metrics = previous.get("risk_metrics")
        if args.only in (None, "nlp"):
            print("== 1. Bộ phân loại văn bản ==")
            nlp_metrics = train_nlp(
                staging, catalog, args.nlp_per_type, args.seed, args.nlp_short_per_type,
                **({"c_values": tuple(args.nlp_c)} if args.nlp_c else {}),
                **({"accent_chars": args.nlp_accent_chars == "on"} if args.nlp_accent_chars else {}),
            )
            names += NLP_ARTIFACTS
        if args.only in (None, "risk"):
            print("== 2. Bộ chấm điểm rủi ro ==")
            risk_metrics = train_risk(
                staging, catalog, args.risk_per_type, args.threads, args.seed
            )
            names += RISK_ARTIFACTS
        metadata = {
            "pipeline_version": PIPELINE_VERSION,
            "trained_at": started_at.isoformat(timespec="seconds"),
            "training_duration_seconds": round(time.monotonic() - start, 1),
            "status": "READY_FOR_INFERENCE",
            "random_state": args.seed,
            "catalog": str(CATALOG_PATH.relative_to(REPO_ROOT)),
            "evaluation_scope": (
                "Synthetic data generated from request_corpus.json plus translated real requests "
                "from public datasets (request_public_train.json); the hand-written test splits "
                "and request_eval_public.json are never used for training."
            ),
            "nlp_metrics": nlp_metrics,
            "risk_metrics": risk_metrics,
        }
        _write_json(staging / "model_metadata.json", metadata)
        commit_artifacts(staging, [*names, "model_metadata.json"])
    write_report(metadata)
    print(f"\nXong. Model: {MODELS_DIR}\nBáo cáo: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
