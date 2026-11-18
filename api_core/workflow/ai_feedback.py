"""Vòng phản hồi của AI: ghi nhận khi con người sửa quyết định của AI và dùng lại ngay (bộ nhớ ca).

Mục tiêu (18/11/2026): AI được phép sai một lần do chưa biết, nhưng KHÔNG sai cùng một kiểu lần thứ hai.

Bốn loại phản hồi (bảng eas.ai_feedback, migration 24):
  AUTO_APPROVE_REVOKED     AI tự duyệt, quản lý thu hồi
  ESCALATION_UNNECESSARY   AI chuyển hồ sơ sang B/C, quản lý xác nhận là chuyển nhầm
  RANKING_OVERRIDDEN       quản lý chọn người nhận việc khác ứng viên AI xếp đầu
  REMEDIATION_DISMISSED    quản lý bỏ qua đề xuất xử lý

Bộ nhớ ca dùng ngay ở quyết định kế tiếp, không cần huấn luyện lại. Phạm vi so khớp được chọn để KHÔNG
học tràn: ngoại lệ thu hồi / chuyển nhầm gắn với hoàn cảnh của một người, nên chỉ áp cho cùng người gửi +
cùng loại yêu cầu (chuyển nhầm còn phải cùng mã tình huống xấu); lựa chọn người nhận việc áp cho cùng người
xin nghỉ + cùng loại việc. Ca cũ hơn MEMORY_DAYS hoặc đã bị admin ngưng dùng (retired_at) không còn hiệu lực.
Học dồn (huấn luyện lại mô hình xếp hạng, đề xuất chỉnh ngưỡng) ở api_core/management/commands/ai_learn_from_feedback.py.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

MEMORY_DAYS = 180
KINDS = (
    "AUTO_APPROVE_REVOKED",
    "ESCALATION_UNNECESSARY",
    "RANKING_OVERRIDDEN",
    "REMEDIATION_DISMISSED",
)


def available(cursor) -> bool:
    cursor.execute("SELECT to_regclass('eas.ai_feedback') IS NOT NULL")
    return bool(cursor.fetchone()[0])


def _clean_signals(signals: dict[str, Any] | None) -> dict[str, Any]:
    out = {}
    for key, value in (signals or {}).items():
        if isinstance(value, float):
            out[key] = round(value, 3)
        elif isinstance(value, (int, bool, str)) or value is None:
            out[key] = value
        elif isinstance(value, list):
            out[key] = [round(v, 1) if isinstance(v, float) else v for v in value[:20]]
    return out


def record(
    cursor,
    *,
    kind: str,
    request_id: str,
    type_code: str,
    subject_id: str | None,
    actor_id: str,
    ai_decision: dict[str, Any],
    human_decision: dict[str, Any],
    reason: str | None = None,
    case_codes: list[str] | None = None,
    signals: dict[str, Any] | None = None,
) -> str | None:
    """Thêm một phản hồi; không có bảng (chưa chạy migration 24) thì bỏ qua."""
    if kind not in KINDS or not available(cursor):
        return None
    cursor.execute(
        """
        INSERT INTO eas.ai_feedback(kind, request_id, type_code, subject_id, actor_id, case_codes,
                                    ai_decision, human_decision, reason, signals)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id::text
        """,
        [
            kind,
            request_id,
            type_code,
            subject_id,
            actor_id,
            sorted({str(c) for c in case_codes or []})[:20],
            Jsonb(ai_decision),
            Jsonb(human_decision),
            (reason or "")[:500] or None,
            Jsonb(_clean_signals(signals)),
        ],
    )
    return cursor.fetchone()[0]


def memory(
    cursor, *, kind: str, type_code: str, subject_id: str | None
) -> list[dict[str, Any]]:
    """Các ca còn hiệu lực cùng loại phản hồi, cùng loại yêu cầu, cùng người (mới nhất trước)."""
    if not subject_id or not available(cursor):
        return []
    cursor.execute(
        """
        SELECT f.id::text, r.code, f.case_codes, f.reason, f.human_decision, u.display_name, f.created_at
        FROM eas.ai_feedback f
        JOIN eas.request r ON r.id = f.request_id
        LEFT JOIN eas.app_user u ON u.id = f.actor_id
        WHERE f.kind = %s AND f.type_code = %s AND f.subject_id = %s AND f.retired_at IS NULL
          AND f.created_at > now() - make_interval(days => %s)
        ORDER BY f.created_at DESC
        LIMIT 20
        """,
        [kind, type_code, subject_id, MEMORY_DAYS],
    )
    keys = (
        "id",
        "request_code",
        "case_codes",
        "reason",
        "human_decision",
        "actor_name",
        "created_at",
    )
    rows = [dict(zip(keys, row, strict=True)) for row in cursor.fetchall()]
    for row in rows:
        row["created_at"] = row["created_at"].isoformat()
    return rows


def explain(row: dict[str, Any]) -> str:
    who = row.get("actor_name") or "quản lý"
    why = f": “{row['reason']}”" if row.get("reason") else ""
    return f"giống ca {row['request_code']} đã được {who} sửa{why}"


def apply_to_verdict(
    cursor,
    *,
    verdict: dict[str, Any],
    type_code: str,
    requester_id: str | None,
    lifecycle: str,
) -> dict[str, Any]:
    """Điều chỉnh quyết định của AI theo bộ nhớ ca. Trả về verdict mới + 'learned' (mô tả điều chỉnh).

    - Đã từng bị thu hồi tự duyệt (cùng người, cùng loại): không tự duyệt nữa; với luồng A thì chuyển sang
      B như một tình huống xấu đã học (LEARNED_REVOKE).
    - Quản lý đã xác nhận chuyển luồng nhầm cho đúng các tình huống xấu này (cùng người, cùng loại) và không
      có điều khoản quy định nào yêu cầu: bỏ chuyển luồng, giữ luồng hiện tại với người duyệt thủ công.
    """
    out = dict(verdict)
    learned: list[dict[str, Any]] = []
    revoked = memory(
        cursor,
        kind="AUTO_APPROVE_REVOKED",
        type_code=type_code,
        subject_id=requester_id,
    )
    if revoked and (
        out.get("decision") == "auto_approve" or not out.get("escalate_to")
    ):
        case = revoked[0]
        text = f"Không tự duyệt: {explain(case)}"
        out["decision"] = "escalate_to_human"
        if lifecycle == "A" and not out.get("escalate_to"):
            out["escalate_to"] = "B"
            out["escalation_causes"] = [
                *(out.get("escalation_causes") or []),
                {
                    "source": "LEARNED",
                    "code": "LEARNED_REVOKE",
                    "escalate_to": "B",
                    "text": text,
                },
            ]
        learned.append(
            {"kind": "AUTO_APPROVE_REVOKED", "feedback_id": case["id"], "text": text}
        )

    if out.get("escalate_to"):
        causes = out.get("escalation_causes") or []
        bad = {c.get("code") for c in causes if c.get("source") == "BAD_CASE"}
        regulation = [c for c in causes if c.get("source") in ("REGULATION", "LEARNED")]
        if bad and not regulation:
            overruled = memory(
                cursor,
                kind="ESCALATION_UNNECESSARY",
                type_code=type_code,
                subject_id=requester_id,
            )
            covered = (
                set().union(*(set(r["case_codes"] or []) for r in overruled))
                if overruled
                else set()
            )
            if bad <= covered:
                case = next(r for r in overruled if set(r["case_codes"] or []) & bad)
                text = f"Không chuyển luồng: {explain(case)}"
                out["escalate_to"] = None
                out["decision"] = (
                    "escalate_to_human"  # vẫn có người duyệt, chỉ không đổi quy trình
                )
                learned.append(
                    {
                        "kind": "ESCALATION_UNNECESSARY",
                        "feedback_id": case["id"],
                        "text": text,
                        "suppressed": sorted(bad),
                    }
                )
    out["learned"] = learned
    return out


def ranking_preferences(
    cursor, *, holder_id: str, item_type_code: str
) -> list[dict[str, Any]]:
    """Người quản lý đã chọn (khác AI) cho việc cùng loại của cùng người xin nghỉ, mới nhất trước."""
    rows = memory(
        cursor,
        kind="RANKING_OVERRIDDEN",
        type_code=item_type_code,
        subject_id=holder_id,
    )
    out = []
    for row in rows:
        chosen = (row.get("human_decision") or {}).get("candidate_id")
        if chosen and chosen not in {o["candidate_id"] for o in out}:
            out.append(
                {"candidate_id": chosen, "feedback_id": row["id"], "text": explain(row)}
            )
    return out


# --------------------------------------------------------------------------- học dồn định kỳ
FALSE_POSITIVE_ALERT = 0.3
MIN_ESCALATIONS = 3


def feedback_summary(cursor) -> dict[str, Any]:
    """Số phản hồi theo loại + tỉ lệ chuyển luồng nhầm theo tình huống xấu (90 ngày) và đề xuất chỉnh ngưỡng."""
    if not available(cursor):
        return {"installed": False}
    cursor.execute(
        "SELECT kind, count(*), count(*) FILTER (WHERE retired_at IS NULL) FROM eas.ai_feedback GROUP BY 1"
    )
    kinds = {r[0]: {"total": r[1], "active": r[2]} for r in cursor.fetchall()}
    cursor.execute(
        """
        WITH esc AS (
          SELECT c->>'code' AS code, count(*) AS n
          FROM eas.audit_event e, jsonb_array_elements(e.details->'causes') c
          WHERE e.action = 'AI_ESCALATED' AND c->>'source' = 'BAD_CASE'
            AND e.occurred_at > now() - interval '90 days'
          GROUP BY 1
        ), fp AS (
          SELECT unnest(case_codes) AS code, count(*) AS n FROM eas.ai_feedback
          WHERE kind = 'ESCALATION_UNNECESSARY' AND created_at > now() - interval '90 days'
          GROUP BY 1
        )
        SELECT esc.code, esc.n, coalesce(fp.n, 0) FROM esc LEFT JOIN fp USING (code) ORDER BY esc.n DESC
        """
    )
    per_case, suggestions = [], []
    for code, n, wrong in cursor.fetchall():
        rate = round(wrong / n, 3) if n else 0.0
        per_case.append(
            {
                "code": code,
                "escalations": n,
                "marked_unnecessary": wrong,
                "false_positive_rate": rate,
            }
        )
        if n >= MIN_ESCALATIONS and rate >= FALSE_POSITIVE_ALERT:
            suggestions.append(
                {
                    "code": code,
                    "text": (
                        f"{wrong}/{n} lần chuyển luồng vì {code} bị quản lý đánh dấu nhầm ({rate:.0%}): "
                        "cân nhắc nâng ngưỡng trong data/bad_case_catalog.json"
                    ),
                }
            )
    return {
        "installed": True,
        "kinds": kinds,
        "per_case": per_case,
        "threshold_suggestions": suggestions,
    }


def ranking_groups(cursor) -> tuple[list[str], list[list[dict[str, Any]]]]:
    cursor.execute(
        """
        SELECT id::text, signals->'group' FROM eas.ai_feedback
        WHERE kind = 'RANKING_OVERRIDDEN' AND retired_at IS NULL AND jsonb_typeof(signals->'group') = 'array'
        ORDER BY created_at
        """
    )
    ids, groups = [], []
    for fid, group in cursor.fetchall():
        rows = [
            {**c, "user_id": str(i)}
            for i, c in enumerate(group or [])
            if isinstance(c, dict)
        ]
        if len(rows) >= 2:
            ids.append(fid)
            groups.append(rows)
    return ids, groups


def learn_from_feedback() -> dict[str, Any]:
    """Học dồn: huấn luyện lại mô hình xếp hạng bằng lựa chọn thật của quản lý (cổng kiểm tra ở AI service)."""
    import httpx
    from django.conf import settings
    from django.db import connection

    with connection.cursor() as cursor:
        if not available(cursor):
            return {"status": "NOT_INSTALLED"}
        ids, groups = ranking_groups(cursor)
        summary = feedback_summary(cursor)
    if not groups:
        return {
            "status": "NOT_ENOUGH_FEEDBACK",
            "message": "Chưa có lựa chọn nào của quản lý khác đề xuất của AI.",
            "summary": summary,
        }
    with httpx.Client(
        base_url=settings.EAS_AI_SERVICE_URL,
        timeout=httpx.Timeout(300.0, connect=5.0),
        headers={"X-Internal-Secret": settings.EAS_AI_INTERNAL_SECRET},
    ) as client:
        resp = client.post("/ai/remediation/retrain", json={"groups": groups})
        resp.raise_for_status()
        result = resp.json()
    if result.get("status") == "ACCEPTED":
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE eas.ai_feedback SET used_in_training = %s WHERE id = ANY(%s::uuid[]) AND used_in_training IS NULL",
                [result.get("version") or "retrained", ids],
            )
    return {**result, "feedback_rows": len(ids), "summary": summary}


def new_ranking_feedback_count(cursor) -> int:
    if not available(cursor):
        return 0
    cursor.execute(
        "SELECT count(*) FROM eas.ai_feedback WHERE kind='RANKING_OVERRIDDEN' AND used_in_training IS NULL "
        "AND retired_at IS NULL"
    )
    return int(cursor.fetchone()[0])
