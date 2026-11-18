r"""Huấn luyện + đánh giá mô hình xếp hạng người nhận việc thay (ai_service/remediation_ranker.py).

Hai bước, tách rời để tập test có trước mô hình:
  ai_service\.venv-ai\Scripts\python ai_service\training\train_remediation.py --make-test   # sinh + băm tập test
  ai_service\.venv-ai\Scripts\python ai_service\training\train_remediation.py               # huấn luyện, chấm test

Dữ liệu là MÔ PHỎNG (không có lịch sử bàn giao thật): mỗi nhóm là một việc cần người làm thay với 2-16
ứng viên hợp lệ; nhãn là lựa chọn của "quản lý" = bộ tiêu chí chuyên gia (expert_utility) cộng nhiễu
(mô phỏng các quản lý không chọn giống hệt nhau). Train/dev/test dùng seed khác nhau; test lệch phân
phối có chủ đích (phòng lớn hơn, nhiều việc hơn) để đo khả năng khái quát.
Chỉ số: top-1 (chọn đúng người quản lý chọn), NDCG@3; so với mốc ngẫu nhiên, ít việc nhất, nhiều kinh
nghiệm nhất.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "ai_service" / "training" / "data"
sys.path.insert(0, str(ROOT / "ai_service"))

import remediation_ranker as rr

TEST_PATH = DATA / "remediation_test.json"
HASH_PATH = DATA / "remediation_test.sha256"
REPORT_PATH = DATA / "remediation_report.md"
NOISE = 0.35


def candidate(rng: random.Random, heavy: bool) -> dict:
    same_dept = int(rng.random() < 0.6)
    open_items = min(int(rng.expovariate(1 / (6 if heavy else 4))), 20)
    return {
        "same_department": same_dept,
        "same_team": int(same_dept and rng.random() < 0.45),
        "open_items": open_items,
        "due_in_window": min(
            open_items, sum(rng.random() < (0.3 if heavy else 0.2) for _ in range(6))
        ),
        "type_experience": 0
        if rng.random() < 0.35
        else min(int(rng.lognormvariate(1.4, 0.9)), 60),
        "is_superior": 0,
    }


def group(rng: random.Random, heavy: bool) -> list[dict]:
    n = rng.randint(6, 16) if heavy else rng.randint(2, 10)
    cands = [candidate(rng, heavy) for _ in range(n)]
    if rng.random() < 0.2:
        rng.choice(cands)["is_superior"] = 1
    utilities = [rr.expert_utility(c) + rng.gauss(0, NOISE) for c in cands]
    order = sorted(range(n), key=lambda i: -utilities[i])
    for rank_pos, i in enumerate(order):
        cands[i]["relevance"] = max(3 - rank_pos, 0)
    return cands


def make_groups(seed: int, count: int, heavy: bool) -> list[list[dict]]:
    rng = random.Random(seed)
    return [group(rng, heavy) for _ in range(count)]


def ndcg_at(scores: list[float], rel: list[int], k: int = 3) -> float:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
    dcg = sum((2 ** rel[i] - 1) / math.log2(p + 2) for p, i in enumerate(order))
    ideal = sorted(rel, reverse=True)[:k]
    idcg = sum((2**r - 1) / math.log2(p + 2) for p, r in enumerate(ideal))
    return dcg / idcg if idcg else 1.0


def evaluate(groups: list[list[dict]], scorer) -> dict:
    top1 = ndcg = 0.0
    for g in groups:
        scores = scorer(g)
        rel = [c["relevance"] for c in g]
        best = max(range(len(g)), key=lambda i: scores[i])
        top1 += rel[best] == 3
        ndcg += ndcg_at(scores, rel)
    return {
        "top1": round(top1 / len(groups), 4),
        "ndcg@3": round(ndcg / len(groups), 4),
        "groups": len(groups),
    }


def make_test() -> int:
    if TEST_PATH.exists():
        sys.exit("Tập test đã có; không sinh lại (sẽ làm mất ý nghĩa băm trước).")
    groups = make_groups(seed=2026, count=1000, heavy=True)
    raw = json.dumps(
        {
            "about": "Tập TEST xếp hạng người nhận việc thay, sinh và băm 18/11/2026 TRƯỚC khi huấn luyện; "
            "lệch phân phối (phòng 6-16 ứng viên, tải nặng). Không sửa.",
            "noise": NOISE,
            "groups": groups,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    TEST_PATH.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    HASH_PATH.write_text(
        f"{digest}  {TEST_PATH.name}\n", encoding="ascii", newline="\n"
    )
    print("đã sinh và băm tập test:", digest)
    return 0


def load_test() -> list[list[dict]]:
    raw = TEST_PATH.read_bytes()
    want = HASH_PATH.read_text(encoding="ascii").split()[0]
    if hashlib.sha256(raw).hexdigest() != want:
        sys.exit("SHA-256 tập test đã đổi; từ chối chấm.")
    return json.loads(raw)["groups"]


def to_matrix(groups):
    import numpy as np

    x, y, qid = [], [], []
    for gi, g in enumerate(groups):
        for c in g:
            x.append(rr.vector(c))
            y.append(c["relevance"])
            qid.append(gi)
    return np.array(x), np.array(y), np.array(qid)


def train() -> int:
    import xgboost as xgb

    test = load_test()
    train_groups = make_groups(seed=42, count=4000, heavy=False)
    dev_groups = make_groups(seed=7, count=800, heavy=False)
    xtr, ytr, qtr = to_matrix(train_groups)
    xdv, ydv, qdv = to_matrix(dev_groups)
    params = {
        "objective": "rank:pairwise",
        "eta": 0.1,
        "max_depth": 4,
        "min_child_weight": 2,
        "subsample": 0.9,
        "colsample_bytree": 1.0,
        "eval_metric": "ndcg@3",
        "seed": 42,
    }
    dtr = xgb.DMatrix(xtr, label=ytr, qid=qtr, feature_names=list(rr.FEATURES))
    ddv = xgb.DMatrix(xdv, label=ydv, qid=qdv, feature_names=list(rr.FEATURES))
    started = time.perf_counter()
    booster = xgb.train(
        params,
        dtr,
        num_boost_round=600,
        evals=[(ddv, "dev")],
        early_stopping_rounds=40,
        verbose_eval=False,
    )
    seconds = round(time.perf_counter() - started, 1)
    booster.save_model(str(rr.MODEL_PATH))
    rr._model.update(booster=None, mtime=None)

    def model_scorer(g):
        import numpy as np

        return list(
            booster.predict(
                xgb.DMatrix(
                    np.array([rr.vector(c) for c in g]), feature_names=list(rr.FEATURES)
                ),
                iteration_range=(0, booster.best_iteration + 1),
            )
        )

    rng = random.Random(99)
    scorers = {
        "xgboost_ranker": model_scorer,
        "baseline_random": lambda g: [rng.random() for _ in g],
        "baseline_least_loaded": lambda g: [rr.heuristic_score(c) for c in g],
        "baseline_most_experienced": lambda g: [c["type_experience"] for c in g],
        "expert_rule_noise_free": lambda g: [rr.expert_utility(c) for c in g],
    }
    metrics = {
        split: {name: evaluate(gs, fn) for name, fn in scorers.items()}
        for split, gs in (("dev", dev_groups), ("test", test))
    }
    importance = booster.get_score(importance_type="gain")
    meta = {
        "model_version": rr.MODEL_VERSION,
        "status": "READY_FOR_INFERENCE",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training_seconds": seconds,
        "best_iteration": booster.best_iteration,
        "params": params,
        "features": list(rr.FEATURES),
        "label_policy": (
            f"expert_utility (ai_service/remediation_ranker.py) + nhiễu Gauss sd={NOISE:.2f}; "
            "relevance 3/2/1/0 theo thứ hạng"
        ),
        "data": {
            "train_groups": len(train_groups),
            "dev_groups": len(dev_groups),
            "test_groups": len(test),
            "test_sha256": HASH_PATH.read_text(encoding="ascii").split()[0],
        },
        "metrics": metrics,
        "feature_gain": {k: round(v, 3) for k, v in importance.items()},
    }
    Path(rr.META_PATH).write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    lines = [
        "# Báo cáo: mô hình xếp hạng người nhận việc thay (" + rr.MODEL_VERSION + ")",
        "",
        f"Huấn luyện {meta['trained_at']}, {seconds} giây, vòng tốt nhất {booster.best_iteration}.",
        "Dữ liệu MÔ PHỎNG (không có lịch sử bàn giao thật); nhãn = bộ tiêu chí chuyên gia + nhiễu (xem docstring).",
        "Tập test băm trước khi huấn luyện, lệch phân phối (phòng lớn hơn, nhiều việc hơn).",
        "",
        "| Bộ chấm | dev top-1 | dev NDCG@3 | test top-1 | test NDCG@3 |",
        "|---|---|---|---|---|",
    ]
    for name in scorers:
        d, t = metrics["dev"][name], metrics["test"][name]
        lines.append(
            f"| {name} | {d['top1']:.3f} | {d['ndcg@3']:.3f} | {t['top1']:.3f} | {t['ndcg@3']:.3f} |"
        )
    lines += [
        "",
        "`expert_rule_noise_free` là trần tham chiếu: chính bộ tiêu chí gán nhãn khi không có nhiễu.",
        "Mô hình chỉ học lại bộ tiêu chí đó; giá trị ở việc chạy trên tín hiệu thật và giải thích từng điểm.",
        "",
        "Độ quan trọng (gain): "
        + ", ".join(
            f"{k} {v:.2f}"
            for k, v in sorted(meta["feature_gain"].items(), key=lambda x: -x[1])
        ),
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-test", action="store_true")
    a = ap.parse_args()
    return make_test() if a.make_test else train()


if __name__ == "__main__":
    raise SystemExit(main())
