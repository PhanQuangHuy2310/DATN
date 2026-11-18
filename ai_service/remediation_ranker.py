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
MODEL_VERSION = "remediation-ranker-1"


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
        import xgboost as xgb

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
