"""Xếp hạng người nhận việc thay khi một hồ sơ dính tình huống xấu được duyệt (hướng xử lý gốc rễ).

Bài toán: người xin nghỉ đang giữ việc đến hạn (bước duyệt, lượt thực hiện). Sau khi quản lý vẫn cho
nghỉ, AI đề xuất CHUYỂN từng việc cho ai, hoặc LÙI HẠN nếu không có người phù hợp. Quản lý xác nhận.

Phân vai:
  - Ràng buộc cứng do LUẬT ở API core lo (không giao cho học máy): ứng viên phải có đúng vai trò cho việc
    (APPROVER/EXECUTOR/ACCEPTOR đúng phạm vi phòng và loại), không vắng trong thời gian nghỉ, không phải
    người gửi việc đó, không phải tài khoản quản trị/hệ thống.
  - Học máy (XGBoost rank:pairwise) chỉ XẾP HẠNG các ứng viên hợp lệ theo đặc trưng tải việc, kinh
    nghiệm, quan hệ tổ chức. Nhãn huấn luyện mô phỏng lựa chọn của quản lý theo bộ tiêu chí ghi rõ ở
    ``expert_utility`` (không có lịch sử bàn giao thật để học) nên mô hình được gọi đúng tên là
    "mô phỏng chuyên gia"; giá trị nằm ở giải thích được từng điểm và chạy trên dữ liệu thật của hệ thống.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

FEATURES = (
    "same_department",  # cùng phòng với việc cần làm thay
    "same_team",  # cùng quản lý trực tiếp với người xin nghỉ (đồng nghiệp ngang cấp)
    "open_items",  # số việc đang mở của ứng viên
    "due_in_window",  # số việc của ứng viên đến hạn trong thời gian người kia vắng
    "type_experience",  # số lần ứng viên đã duyệt/xử lý cùng loại yêu cầu trong 180 ngày
    "is_superior",  # ứng viên là cấp trên của người xin nghỉ
)
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "remediation_ranker.json"
)
META_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "remediation_ranker_meta.json"
)
MODEL_VERSION = "remediation-ranker-2"
# Ràng buộc đơn điệu (theo thứ tự FEATURES): thêm việc đến hạn / việc đang mở / là cấp trên không bao giờ làm
# điểm TĂNG; cùng phòng / cùng nhóm / thêm kinh nghiệm không bao giờ làm điểm GIẢM. Bản 1 (không ràng buộc) có
# 7/8.112 cặp vi phạm, ví dụ thêm 1 việc đến hạn mà điểm lại tăng; xem training/data/remediation_report.md.
MONOTONE = "(1,1,-1,-1,1,-1)"


def vector(c: dict[str, Any]) -> list[float]:
    return [float(c.get(f) or 0) for f in FEATURES]


def expert_utility(c: dict[str, Any]) -> float:
    """Bộ tiêu chí chuyên gia dùng để GÁN NHÃN mô phỏng (không dùng khi suy luận).

    Ưu tiên người cùng phòng, cùng nhóm, có kinh nghiệm cùng loại; tránh người đang có nhiều việc,
    nhất là việc đến hạn trong cùng thời gian; cấp trên chỉ nên nhận khi không còn ai (tránh dồn việc lên).
    Lợi ích giảm dần theo kinh nghiệm (log) và phạt tăng nhanh theo việc đến hạn.
    """
    return (
        2.0 * c["same_department"]
        + 1.2 * c["same_team"]
        + 1.1 * math.log1p(c["type_experience"])
        - 0.22 * c["open_items"]
        - 0.9 * c["due_in_window"] ** 1.3
        - 1.4 * c["is_superior"]
    )


def explain(c: dict[str, Any]) -> list[str]:
    out = []
    if c.get("same_department"):
        out.append("cùng phòng với việc cần làm thay")
    if c.get("same_team"):
        out.append("cùng nhóm với người xin nghỉ")
    if c.get("type_experience"):
        out.append(
            f"đã xử lý {int(c['type_experience'])} hồ sơ cùng loại trong 180 ngày"
        )
    out.append(f"đang mở {int(c.get('open_items') or 0)} việc")
    if c.get("due_in_window"):
        out.append(f"có {int(c['due_in_window'])} việc đến hạn trong cùng thời gian")
    if c.get("is_superior"):
        out.append("là cấp trên (chỉ nên nhận khi không còn ai)")
    return out


_model: dict[str, Any] = {"booster": None, "mtime": None}


def _booster():
    try:
        mtime = os.stat(MODEL_PATH).st_mtime_ns
    except FileNotFoundError:
        return None
    if _model["mtime"] != mtime:
        try:
            import xgboost as xgb
        except ImportError:  # môi trường không có xgboost: dùng mốc dự phòng
            return None

        booster = xgb.Booster()
        booster.load_model(MODEL_PATH)
        _model.update(booster=booster, mtime=mtime)
    return _model["booster"]


def heuristic_score(c: dict[str, Any]) -> float:
    """Mốc dự phòng khi chưa có mô hình: ít việc nhất, tránh việc trùng thời gian."""
    return -(float(c.get("open_items") or 0) + 3 * float(c.get("due_in_window") or 0))


def rank(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Sắp xếp ứng viên (đã qua ràng buộc cứng), trả điểm + giải thích."""
    if not candidates:
        return {"model_version": MODEL_VERSION, "engine": "none", "ranked": []}
    booster = _booster()
    if booster is not None:
        import numpy as np
        import xgboost as xgb

        scores = booster.predict(
            xgb.DMatrix(
                np.array([vector(c) for c in candidates]), feature_names=list(FEATURES)
            )
        )
        engine = "xgboost-ranker"
    else:
        scores = [heuristic_score(c) for c in candidates]
        engine = "heuristic-fallback"
    ranked = sorted(
        (
            {**c, "score": round(float(s), 4), "why": explain(c)}
            for c, s in zip(candidates, scores, strict=True)
        ),
        key=lambda c: -c["score"],
    )
    return {"model_version": MODEL_VERSION, "engine": engine, "ranked": ranked}


def suggest_action(
    kind: str, hours_to_due: float, absence_hours: float, best: dict[str, Any] | None
) -> dict[str, str]:
    """Chọn hướng xử lý cho một việc (luật, giải thích được).

    - Có ứng viên phù hợp: chuyển việc (bước duyệt thì giao lại bước, lượt thực hiện thì đổi người làm).
    - Không có ai, hoặc người tốt nhất cũng đang kín việc đến hạn: lùi hạn tới sau khi người xin nghỉ
      đi làm lại, nếu việc đến hạn trong thời gian vắng.
    - Còn lại: đề nghị người gửi đổi ngày nghỉ.
    """
    if best is not None and int(best.get("due_in_window") or 0) <= 2:
        action = "DELEGATE_APPROVALS" if kind == "APPROVAL" else "REASSIGN_WORK"
        return {
            "action": action,
            "why": f"giao cho {best.get('display_name') or 'ứng viên đứng đầu'}",
        }
    if hours_to_due <= absence_hours + 24:
        return {
            "action": "POSTPONE_DEADLINE",
            "why": "không có người phù hợp làm thay; lùi hạn tới sau ngày đi làm lại",
        }
    return {
        "action": "RESCHEDULE_REQUEST",
        "why": "việc chưa đến hạn gấp; đề nghị đổi ngày nghỉ",
    }


def model_info() -> dict[str, Any]:
    try:
        with open(META_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {"model_version": MODEL_VERSION, "status": "NOT_TRAINED"}


# --------------------------------------------------------------------------- học dồn từ phản hồi
MIN_REAL_GROUPS = 1
REAL_WEIGHT = 20          # mỗi lựa chọn thật của quản lý được nhân bản để có trọng lượng so với dữ liệu mô phỏng
GATE_TOLERANCE = 0.01     # top-1 trên tập test đã băm không được giảm quá mức này


def _top1(booster, groups) -> float:
    """Tỉ lệ nhóm mà ứng viên điểm cao nhất là người được chọn (dự đoán một lần cho cả tập)."""
    import numpy as np
    import xgboost as xgb

    if not groups:
        return 0.0
    rows = [vector(c) for g in groups for c in g]
    scores = booster.predict(xgb.DMatrix(np.array(rows), feature_names=list(FEATURES)))
    hit, pos = 0, 0
    for g in groups:
        part = scores[pos : pos + len(g)]
        pos += len(g)
        best = g[int(np.argmax(part))]
        hit += bool(best.get("chosen") or best.get("relevance") == 3)
    return round(hit / len(groups), 4)


def retrain_with_feedback(real_groups: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Huấn luyện lại với các lần quản lý chọn khác AI; chỉ thay mô hình khi qua cổng kiểm tra.

    Cổng: (1) top-1 trên tập test mô phỏng ĐÃ BĂM (remediation_test.json) không giảm quá GATE_TOLERANCE;
    (2) độ đúng trên chính các lựa chọn thật của quản lý không giảm. Không đạt thì giữ mô hình cũ.
    """
    import tempfile

    import xgboost as xgb

    real = [g for g in real_groups if len(g) >= 2 and sum(bool(c.get("chosen")) for c in g) == 1]
    if len(real) < MIN_REAL_GROUPS:
        return {"status": "NOT_ENOUGH_FEEDBACK", "real_groups": len(real)}
    try:
        from training import train_remediation as tr
    except ImportError:
        from ai_service.training import train_remediation as tr
    test = tr.load_test()  # dừng nếu SHA-256 tập test đã đổi
    old = _booster()
    before = {"test_top1": _top1(old, test) if old else None, "real_top1": _top1(old, real) if old else None}

    sim_train = tr.make_groups(seed=42, count=4000, heavy=False)
    sim_dev = tr.make_groups(seed=7, count=800, heavy=False)
    real_rel = [[{**c, "relevance": 3 if c.get("chosen") else 0} for c in g] for g in real]
    xtr, ytr, qtr = tr.to_matrix(sim_train + real_rel * REAL_WEIGHT)
    xdv, ydv, qdv = tr.to_matrix(sim_dev)
    params = {"objective": "rank:pairwise", "eta": 0.1, "max_depth": 4, "min_child_weight": 2,
              "subsample": 0.9, "eval_metric": "ndcg@3", "seed": 42, "monotone_constraints": MONOTONE}
    booster = xgb.train(
        params,
        xgb.DMatrix(xtr, label=ytr, qid=qtr, feature_names=list(FEATURES)),
        num_boost_round=600,
        evals=[(xgb.DMatrix(xdv, label=ydv, qid=qdv, feature_names=list(FEATURES)), "dev")],
        early_stopping_rounds=40,
        verbose_eval=False,
    )
    trimmed = booster[: booster.best_iteration + 1]
    after = {"test_top1": _top1(trimmed, test), "real_top1": _top1(trimmed, real)}
    reasons = []
    if before["test_top1"] is not None and after["test_top1"] < before["test_top1"] - GATE_TOLERANCE:
        reasons.append(f"top-1 tập test giảm {before['test_top1']} -> {after['test_top1']}")
    if before["real_top1"] is not None and after["real_top1"] < before["real_top1"]:
        reasons.append(f"độ đúng trên lựa chọn thật giảm {before['real_top1']} -> {after['real_top1']}")
    meta = model_info()
    history = meta.get("feedback_history", [])
    entry = {"real_groups": len(real), "before": before, "after": after,
             "accepted": not reasons, "reasons": reasons}
    if not reasons:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MODEL_PATH), suffix=".json")
        os.close(fd)
        trimmed.save_model(tmp)
        os.replace(tmp, MODEL_PATH)
        _model.update(booster=None, mtime=None)
        version = f"{MODEL_VERSION}+fb{len([h for h in history if h.get('accepted')]) + 1}"
        entry["version"] = version
        meta["model_version"] = version
    meta["feedback_history"] = [*history, entry][-50:]
    with open(META_PATH, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=1)
    return {"status": "ACCEPTED" if not reasons else "REJECTED_BY_GATE", **entry}
