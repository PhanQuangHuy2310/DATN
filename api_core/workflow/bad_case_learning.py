"""Học bad case mới từ lý do người duyệt thu hồi hồ sơ AI đã tự duyệt (migration 25, yêu cầu trưởng nhóm 18/11).

Luồng:
  1. Người duyệt thu hồi hồ sơ AI đã tự duyệt và PHẢI nêu lý do (workflow/auto_approval.py). Lý do + tín hiệu
     của hồ sơ lúc AI duyệt được ghi vào eas.ai_feedback (bộ nhớ ca, dùng ngay cho cùng người + cùng loại).
  2. Sau khi lưu, AI phân tích lý do (POST /ai/bad-case/analyze-reason, mô hình chạy cục bộ):
       EXISTING        khớp bad case có sẵn, AI bỏ sót vì hồ sơ chưa vượt ngưỡng -> ghi bằng chứng cho bad case đó;
       EXISTING_SCOPE  khớp bad case có sẵn nhưng loại đơn chưa thuộc phạm vi -> ứng viên mở rộng phạm vi;
       NEW_PATTERN     kiểu rủi ro mới, lặp lại được -> ứng viên bad case mới (kèm điều kiện đo được nếu có);
       ONE_OFF         lý do riêng của hồ sơ -> ứng viên để admin quyết (mặc định không tạo).
     Lý do giống nhau được gom vào cùng một ứng viên (eas.bad_case, state CANDIDATE); mỗi lý do là một dòng
     eas.bad_case_evidence.
  3. AI tự đánh giá ứng viên "có thường xảy ra đủ để thành bad case không" theo các tiêu chí ở CRITERIA. Đủ thì
     tự kích hoạt (ACTIVE, activated_by = AI) và dùng ngay ở hồ sơ kế tiếp của MỌI người; chưa đủ thì ghi rõ thiếu
     tiêu chí nào và hỏi admin có tạo không (trang Quy định -> AI học từ phản hồi).

Bad case học được chỉ làm AI CHẶT hơn (không tự duyệt, chuyển A -> B/C), không bao giờ nới quyền tự duyệt.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.workflow import bad_case_conditions as bcc

logger = logging.getLogger(__name__)

WINDOW_DAYS = 90
MIN_EVIDENCE = 3  # số lần thu hồi khác nhau vì cùng kiểu lý do
MIN_REQUESTERS = (
    2  # không phải thói quen của riêng một người (đã có bộ nhớ ca theo người)
)
MIN_APPROVERS = 2  # không phải tiêu chuẩn riêng của một người duyệt
MIN_CONFIDENCE = 0.5  # độ chắc trung bình của mô hình khi hiểu các lý do
MAX_COVERAGE = 0.30  # điều kiện không được bắt quá 30% hồ sơ cùng loại trong 90 ngày (chặn tràn lan)
REOPEN_EXTRA = 3  # ứng viên bị admin từ chối được hỏi lại khi có thêm từng này ca mới
LOCAL_TZ = "Asia/Ho_Chi_Minh"

SQL_REQUEST_FEATURES = """
    WITH f AS (
      SELECT
        CASE WHEN coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date') ~ '^\\d{4}-\\d{2}-\\d{2}'
             THEN left(coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date'), 10)::date END AS d_start,
        CASE WHEN coalesce(v.payload->>'end_date', coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date')) ~ '^\\d{4}-\\d{2}-\\d{2}'
             THEN left(coalesce(v.payload->>'end_date', coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date')), 10)::date END AS d_end,
        CASE WHEN v.payload->>'start_time' ~ '^\\d{1,2}:\\d{2}' THEN (v.payload->>'start_time')::time
             ELSE time '08:00' END AS t_start,
        v.submitted_at, v.amount_vnd, r.requester_id
      FROM eas.request r JOIN eas.request_revision v ON v.id = r.current_revision_id
      WHERE r.id = %(request_id)s
    )
    SELECT
        round((extract(epoch FROM ((d_start + t_start) AT TIME ZONE %(tz)s - submitted_at)) / 3600)::numeric, 1),
        extract(day FROM d_start)::int,
        extract(isodow FROM d_start)::int,
        extract(hour FROM submitted_at AT TIME ZONE %(tz)s)::int,
        CASE WHEN d_start IS NOT NULL THEN greatest(coalesce(d_end, d_start) - d_start + 1, 0) END,
        amount_vnd,
        (SELECT count(*) FROM eas.request x
         WHERE x.requester_id = f.requester_id AND x.status = 'REJECTED'
           AND x.updated_at > f.submitted_at - interval '30 days' AND x.updated_at <= f.submitted_at)
    FROM f
"""
SQL_HISTORY_FEATURES = """
    WITH f AS (
      SELECT
        CASE WHEN coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date') ~ '^\\d{4}-\\d{2}-\\d{2}'
             THEN left(coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date'), 10)::date END AS d_start,
        CASE WHEN coalesce(v.payload->>'end_date', coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date')) ~ '^\\d{4}-\\d{2}-\\d{2}'
             THEN left(coalesce(v.payload->>'end_date', coalesce(v.payload->>'start_date', v.payload->>'date', v.payload->>'booking_date', v.payload->>'work_date', v.payload->>'visit_date', v.payload->>'event_date')), 10)::date END AS d_end,
        CASE WHEN v.payload->>'start_time' ~ '^\\d{1,2}:\\d{2}' THEN (v.payload->>'start_time')::time
             ELSE time '08:00' END AS t_start,
        v.submitted_at, v.amount_vnd, r.requester_id
      FROM eas.request r
      JOIN eas.request_type rt ON rt.id = r.type_id
      JOIN eas.request_revision v ON v.request_id = r.id AND v.revision_no = 1
      WHERE rt.code = %(type_code)s AND v.submitted_at > now() - make_interval(days => %(days)s)
        AND r.status <> 'DRAFT'
    )
    SELECT
        round((extract(epoch FROM ((d_start + t_start) AT TIME ZONE %(tz)s - submitted_at)) / 3600)::numeric, 1),
        extract(day FROM d_start)::int,
        extract(isodow FROM d_start)::int,
        extract(hour FROM submitted_at AT TIME ZONE %(tz)s)::int,
        CASE WHEN d_start IS NOT NULL THEN greatest(coalesce(d_end, d_start) - d_start + 1, 0) END,
        amount_vnd,
        (SELECT count(*) FROM eas.request x
         WHERE x.requester_id = f.requester_id AND x.status = 'REJECTED'
           AND x.updated_at > f.submitted_at - interval '30 days' AND x.updated_at <= f.submitted_at)
    FROM f
"""
FEATURE_KEYS = (
    "notice_hours",
    "start_day_of_month",
    "start_weekday",
    "submit_hour",
    "days_requested",
    "amount",
    "requester_rejected_30d",
)


def available(cursor) -> bool:
    cursor.execute("SELECT to_regclass('eas.bad_case') IS NOT NULL")
    return bool(cursor.fetchone()[0])


def _row_features(row) -> dict[str, Any]:
    out = {}
    for key, value in zip(FEATURE_KEYS, row, strict=True):
        out[key] = (
            None
            if value is None
            else (float(value) if key in ("notice_hours", "amount") else int(value))
        )
    return out


def request_features(cursor, request_id: str) -> dict[str, Any]:
    """Đặc trưng của bản đang hiệu lực của hồ sơ (số giờ báo trước, ngày/thứ bắt đầu, giờ gửi, số ngày, số tiền)."""
    cursor.execute(  # NOSONAR python:S2077 - static parameterized SQL query
        SQL_REQUEST_FEATURES,
        {"request_id": request_id, "tz": LOCAL_TZ},
    )
    row = cursor.fetchone()
    return _row_features(row) if row else dict.fromkeys(FEATURE_KEYS)


def history_features(
    cursor, type_code: str, days: int = WINDOW_DAYS
) -> list[dict[str, Any]]:
    """Đặc trưng của mọi hồ sơ cùng loại đã gửi trong N ngày (bản gửi đầu tiên), để đo độ phủ của điều kiện."""
    cursor.execute(  # NOSONAR python:S2077 - static parameterized SQL query
        SQL_HISTORY_FEATURES,
        {"type_code": type_code, "days": days, "tz": LOCAL_TZ},
    )
    return [_row_features(r) for r in cursor.fetchall()]


# --------------------------------------------------------------------------- cấu hình cho bộ phát hiện
def detector_config(cursor) -> dict[str, Any]:
    """Bad case học được đang ACTIVE + điều chỉnh danh mục có sẵn (ngưng / mở rộng loại đơn) gửi kèm đánh giá."""
    if not available(cursor):
        return {"learned_bad_cases": [], "bad_case_overrides": {}}
    cursor.execute(
        """
        SELECT code, title, rationale, request_types, condition, condition_text, risk, escalate_to, detector,
               base_code, state
        FROM eas.bad_case
        WHERE (detector = 'RULE' AND state = 'ACTIVE') OR (detector = 'SCOPE' AND state = 'ACTIVE')
           OR (detector = 'BUILTIN' AND state = 'RETIRED')
        """
    )
    learned, overrides = [], {}
    for (
        code,
        title,
        rationale,
        types,
        cond,
        cond_text,
        risk,
        esc,
        detector,
        base,
        state,
    ) in cursor.fetchall():
        if detector == "RULE":
            learned.append(
                {
                    "code": code,
                    "title": title,
                    "rationale": rationale,
                    "request_types": list(types),
                    "condition": cond,
                    "condition_text": cond_text,
                    "risk": risk,
                    "escalate_to": esc,
                }
            )
        elif detector == "SCOPE":
            overrides.setdefault(base, {}).setdefault("extra_types", []).extend(types)
        else:
            overrides.setdefault(code, {})["disabled"] = True
    return {"learned_bad_cases": learned, "bad_case_overrides": overrides}


def safe_detector_config() -> dict[str, Any]:
    try:
        with connection.cursor() as cursor:
            return detector_config(cursor)
    except Exception:
        logger.warning("bad-case config unavailable", exc_info=True)
        return {"learned_bad_cases": [], "bad_case_overrides": {}}


# --------------------------------------------------------------------------- đánh giá đủ / chưa đủ
def _type_names(cursor, codes: list[str]) -> dict[str, str]:
    cursor.execute(
        "SELECT code, name FROM eas.request_type WHERE code = ANY(%s)", [codes]
    )
    return dict(cursor.fetchall())


def evaluate_case(cursor, case: dict[str, Any]) -> dict[str, Any]:
    """Tiêu chí 'đủ thường xuyên để thành bad case' cho một ứng viên, kèm lý do thiếu và câu hỏi cho admin."""
    cursor.execute(
        """
        SELECT count(DISTINCT request_id), count(DISTINCT requester_id), count(DISTINCT approver_id),
               coalesce(avg(confidence), 0), count(*) FILTER (WHERE verdict <> 'ONE_OFF'), count(*)
        FROM eas.bad_case_evidence
        WHERE bad_case_id = %s AND created_at > now() - make_interval(days => %s)
        """,
        [case["id"], WINDOW_DAYS],
    )
    n, requesters, approvers, confidence, general, total = cursor.fetchone()
    mostly_general = (
        total > 0 and general * 2 >= total if total else case["verdict"] != "ONE_OFF"
    )
    confidence = round(float(confidence), 3)
    criteria = [
        # Một câu đơn lẻ khó phân biệt chung/riêng; nhiều người duyệt độc lập nêu cùng kiểu là bằng chứng lặp lại.
        {
            "key": "pattern",
            "ok": mostly_general
            or (
                n >= MIN_EVIDENCE
                and requesters >= MIN_REQUESTERS
                and approvers >= MIN_APPROVERS
            ),
            "text": (
                "Là kiểu rủi ro chung, lặp lại được"
                if mostly_general
                else "AI hiểu lý do là riêng của từng hồ sơ; chỉ coi là kiểu chung khi lặp lại ở nhiều người "
                "gửi và nhiều người duyệt"
            ),
        },
        {
            "key": "evidence",
            "ok": n >= MIN_EVIDENCE,
            "value": n,
            "need": MIN_EVIDENCE,
            "text": f"Đã xảy ra {n}/{MIN_EVIDENCE} lần trong {WINDOW_DAYS} ngày",
        },
        {
            "key": "requesters",
            "ok": requesters >= MIN_REQUESTERS,
            "value": requesters,
            "need": MIN_REQUESTERS,
            "text": f"Gặp ở {requesters}/{MIN_REQUESTERS} người gửi khác nhau",
        },
        {
            "key": "approvers",
            "ok": approvers >= MIN_APPROVERS,
            "value": approvers,
            "need": MIN_APPROVERS,
            "text": f"Được {approvers}/{MIN_APPROVERS} người duyệt độc lập nêu ra",
        },
        {
            "key": "confidence",
            "ok": confidence >= MIN_CONFIDENCE,
            "value": confidence,
            "need": MIN_CONFIDENCE,
            "text": (
                f"AI chắc trung bình {confidence:.0%} rằng các lý do không thuộc bad case có sẵn "
                f"(cần ≥ {MIN_CONFIDENCE:.0%})"
            ),
        },
    ]
    cond = case.get("condition")
    if case["detector"] == "SCOPE":
        criteria.append(
            {
                "key": "measurable",
                "ok": True,
                "text": f"Đo được bằng bộ phát hiện có sẵn {case.get('base_code')}",
            }
        )
        criteria.append(
            {
                "key": "coverage",
                "ok": True,
                "text": "Bộ phát hiện có sẵn đã có ngưỡng riêng, không chặn cả loại đơn",
            }
        )
    else:
        criteria.append(
            {
                "key": "measurable",
                "ok": bool(cond),
                "text": ("Đo được bằng dữ liệu hệ thống: " + bcc.describe(cond))
                if cond
                else "Chưa đo được bằng dữ liệu hệ thống (AI không tự nhận ra lần sau nếu không có điều kiện)",
            }
        )
        if cond and bcc.history_computable(cond):
            rows = [
                r for t in case["request_types"] for r in history_features(cursor, t)
            ]
            hit = sum(bcc.matches(cond, r) for r in rows)
            share = hit / len(rows) if rows else 0.0
            criteria.append(
                {
                    "key": "coverage",
                    "ok": share <= MAX_COVERAGE,
                    "value": round(share, 3),
                    "need": MAX_COVERAGE,
                    "text": (
                        f"Điều kiện bắt {hit}/{len(rows)} hồ sơ cùng loại trong {WINDOW_DAYS} ngày "
                        f"({share:.0%}, tối đa {MAX_COVERAGE:.0%}) nên không chặn tràn lan"
                    ),
                }
            )
        else:
            criteria.append(
                {
                    "key": "coverage",
                    "ok": False,
                    "text": "Chưa kiểm chứng được độ phủ trên lịch sử (điều kiện dùng tín hiệu ngữ cảnh "
                    "hoặc chưa có điều kiện)",
                }
            )
    enough = all(c["ok"] for c in criteria)
    missing = [c["text"] for c in criteria if not c["ok"]]
    names = _type_names(cursor, list(case["request_types"]))
    types = ", ".join(names.get(t, t) for t in case["request_types"])
    if enough:
        summary = (
            f"Đủ để thành bad case: {n} lần thu hồi từ {requesters} người gửi, {approvers} người duyệt, "
            "điều kiện đo được và không chặn tràn lan. AI tự thêm vào danh mục và dùng từ hồ sơ kế tiếp."
        )
        question = None
    else:
        summary = "Chưa đủ để AI tự tạo bad case vì: " + "; ".join(missing) + "."
        question = (
            f"Có tạo bad case “{case['title']}” để AI không tự duyệt và chuyển sang quy trình "
            f"{case.get('escalate_to') or 'B'} các hồ sơ {types}"
            + (f" khi {bcc.describe(cond)}" if cond else "")
            + " không?"
        )
    return {
        "enough": enough,
        "criteria": criteria,
        "missing": missing,
        "summary": summary,
        "question": question,
        "stats": {
            "evidence": n,
            "requesters": requesters,
            "approvers": approvers,
            "confidence": confidence,
        },
        "thresholds": {
            "window_days": WINDOW_DAYS,
            "min_evidence": MIN_EVIDENCE,
            "min_requesters": MIN_REQUESTERS,
            "min_approvers": MIN_APPROVERS,
            "min_confidence": MIN_CONFIDENCE,
            "max_coverage": MAX_COVERAGE,
        },
    }


def compose_rationale(cursor, case_id: str, base: str | None = None) -> str:
    """Vì sao là bad case: tác hại (bad case có sẵn) hoặc tổng hợp lý do của các người duyệt."""
    cursor.execute(
        "SELECT reason FROM eas.bad_case_evidence WHERE bad_case_id = %s ORDER BY created_at DESC LIMIT 3",
        [case_id],
    )
    quotes = "; ".join(f"“{r[0][:160]}”" for r in cursor.fetchall())
    head = f"{base} " if base else ""
    return (
        head + f"Người duyệt đã thu hồi quyết định tự duyệt của AI vì: {quotes}."
    ).strip()[:2000]


# --------------------------------------------------------------------------- phân tích một lý do
def _audit(cursor, request_id, action, target_id, details, correlation_id=None) -> None:
    from api_core.workflow.service import _append_request_audit

    _append_request_audit(
        cursor,
        request_id=request_id,
        actor_id=None,
        actor_kind="SYSTEM",
        action=action,
        target_type="bad_case",
        target_id=target_id,
        details=details,
        correlation_id=correlation_id
        or str(uuid5(NAMESPACE_URL, f"eas:bad-case:{target_id}")),
    )


def _call_ai(body: dict[str, Any]) -> dict[str, Any]:
    import httpx
    from django.conf import settings

    with httpx.Client(
        base_url=settings.EAS_AI_SERVICE_URL,
        timeout=httpx.Timeout(30.0, connect=5.0),
        headers={"X-Internal-Secret": settings.EAS_AI_INTERNAL_SECRET},
    ) as client:
        resp = client.post("/ai/bad-case/analyze-reason", json=body)
        resp.raise_for_status()
        return resp.json()


def _cases_and_candidates(cursor) -> tuple[list[dict], list[dict], dict[str, dict]]:
    cursor.execute(
        """
        SELECT b.id::text, b.code, b.title, b.request_types, b.detector, b.state, b.verdict, b.feature, b.base_code,
               b.rationale, b.risk, b.escalate_to, b.condition,
               (SELECT array_agg(e.reason ORDER BY e.created_at DESC) FROM (
                  SELECT reason, created_at FROM eas.bad_case_evidence WHERE bad_case_id = b.id
                  ORDER BY created_at DESC LIMIT 20) e)
        FROM eas.bad_case b
        """
    )
    cases, candidates, by_code = [], [], {}
    for (
        cid,
        code,
        title,
        types,
        detector,
        state,
        verdict,
        feature,
        base,
        rationale,
        risk,
        esc,
        cond,
        reasons,
    ) in cursor.fetchall():
        row = {
            "id": cid,
            "code": code,
            "title": title,
            "request_types": list(types),
            "detector": detector,
            "state": state,
            "verdict": verdict,
            "feature": feature,
            "base_code": base,
            "rationale": rationale,
            "risk": risk,
            "escalate_to": esc,
        }
        by_code[code] = row
        if detector == "BUILTIN" and state == "ACTIVE":
            cases.append({"code": code, "title": title, "request_types": list(types)})
        if detector != "BUILTIN" and state != "RETIRED":
            candidates.append(
                {
                    "code": code,
                    "verdict": verdict,
                    "feature": feature,
                    "base_code": base,
                    "type_codes": list(types),
                    "reasons": list(reasons or []),
                    "condition": cond,
                }
            )
    return cases, candidates, by_code


def _new_code(
    cursor,
    verdict: str,
    feature: str | None,
    type_code: str,
    base: str | None,
    seed: str,
) -> str:
    if verdict == "EXISTING_SCOPE" and base:
        code = f"{base}_{type_code}"
    elif verdict in ("NEW_PATTERN", "ONE_OFF") and feature:
        code = f"BC_{feature.upper()}_{type_code}"
    else:
        code = ("BC_NEW_" if verdict == "NEW_PATTERN" else "BC_REVIEW_") + hashlib.sha1(
            seed.encode()
        ).hexdigest()[:8]
    code = re.sub(r"[^A-Z0-9_]", "_", code.upper())[:56]
    candidate, k = code, 2
    while True:
        cursor.execute("SELECT 1 FROM eas.bad_case WHERE code = %s", [candidate])
        if not cursor.fetchone():
            return candidate
        candidate, k = f"{code[:54]}_{k}", k + 1


def analyze_feedback(feedback_id: str) -> dict[str, Any] | None:
    """Phân tích một lý do thu hồi (idempotent: mỗi phản hồi một bằng chứng). None nếu không áp dụng."""
    with connection.cursor() as cursor:
        if not available(cursor):
            return None
        cursor.execute(
            """
            SELECT f.request_id::text, f.type_code, f.subject_id::text, f.actor_id::text, f.reason, f.signals,
                   (SELECT e.details->>'reason' FROM eas.audit_event e
                    WHERE e.request_id = f.request_id AND e.action = 'AI_AUTO_APPROVE_REVOKED'
                    ORDER BY e.seq DESC LIMIT 1),
                   EXISTS (SELECT 1 FROM eas.bad_case_evidence x WHERE x.feedback_id = f.id)
            FROM eas.ai_feedback f
            WHERE f.id = %s AND f.kind = 'AUTO_APPROVE_REVOKED'
            """,
            [feedback_id],
        )
        row = cursor.fetchone()
        if not row or row[7]:
            return None
        (
            request_id,
            type_code,
            requester_id,
            approver_id,
            short_reason,
            signals,
            full_reason,
            _,
        ) = row
        reason = (full_reason or short_reason or "").strip()
        if len(reason) < 5:
            return None
        # Mọi tín hiệu số/đúng-sai (để AI chạy lại bộ phát hiện có sẵn); bằng chứng chỉ lưu đặc trưng điều kiện.
        scalars = {
            k: v
            for k, v in (signals or {}).items()
            if v is None or isinstance(v, (bool, int, float))
        }
        values = {k: v for k, v in scalars.items() if k in bcc.FEATURES}
        cases, candidates, by_code = _cases_and_candidates(cursor)

    analysis = _call_ai(
        {
            "reason": reason,
            "type_code": type_code,
            "values": scalars,
            "cases": cases,
            "candidates": candidates,
        }
    )
    verdict = analysis.get("verdict")
    if verdict not in ("EXISTING", "EXISTING_SCOPE", "NEW_PATTERN", "ONE_OFF"):
        raise ValueError(f"unexpected verdict {verdict!r}")

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM eas.bad_case_evidence WHERE feedback_id = %s", [feedback_id]
        )
        if cursor.fetchone():
            return None
        target = None
        if verdict == "EXISTING":
            target = by_code.get(analysis.get("code"))
        elif analysis.get("match") and analysis["match"] in by_code:
            target = by_code[analysis["match"]]
        created = False
        if target is None:
            base = (
                by_code.get(analysis.get("code"))
                if verdict == "EXISTING_SCOPE"
                else None
            )
            if verdict == "EXISTING_SCOPE" and base is None:
                verdict = "NEW_PATTERN"
            detector = "SCOPE" if verdict == "EXISTING_SCOPE" else "RULE"
            cond = None
            if analysis.get("condition"):
                try:
                    cond = bcc.validate(analysis["condition"])
                except ValueError:
                    cond = None
            code = _new_code(
                cursor,
                verdict,
                analysis.get("feature"),
                type_code,
                base["code"] if base else None,
                feedback_id,
            )
            title = (
                f"{base['title']} (mở rộng sang {type_code})"
                if base
                else (analysis.get("title") or "Rủi ro mới")
                if verdict == "NEW_PATTERN" or cond
                else f"Lý do riêng: {reason[:120]}"
            )
            cursor.execute(
                """
                INSERT INTO eas.bad_case(code, title, rationale, condition_text, request_types, detector, base_code,
                                         condition, verdict, feature, risk, escalate_to, source, state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'AI', 'CANDIDATE')
                RETURNING id::text
                """,
                [
                    code,
                    title[:200],
                    (base["rationale"] if base else reason)[:2000],
                    bcc.describe(cond)
                    if cond
                    else (f"Như {base['code']}" if base else None),
                    [type_code],
                    detector,
                    base["code"] if base else None,
                    Jsonb(cond) if cond else None,
                    verdict,
                    analysis.get("feature"),
                    base["risk"] if base else 3,
                    base["escalate_to"] if base else "B",
                ],
            )
            target = {
                "id": cursor.fetchone()[0],
                "code": code,
                "title": title,
                "detector": detector,
                "state": "CANDIDATE",
                "verdict": verdict,
                "request_types": [type_code],
                "base_code": base["code"] if base else None,
                "escalate_to": base["escalate_to"] if base else "B",
                "condition": cond,
            }
            created = True
        cursor.execute(
            """
            INSERT INTO eas.bad_case_evidence(feedback_id, request_id, bad_case_id, type_code, requester_id,
                                              approver_id, reason, verdict, confidence, feature, feature_values,
                                              analysis)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            [
                feedback_id,
                request_id,
                target["id"] if target else None,
                type_code,
                requester_id,
                approver_id,
                reason[:2000],
                verdict,
                # Ứng viên mới: độ chắc rằng lý do không thuộc danh mục có sẵn; khớp bad case có sẵn: độ chắc của mã đó.
                analysis.get("confidence")
                if verdict.startswith("EXISTING")
                else analysis.get("confidence_outside", analysis.get("confidence")),
                analysis.get("feature"),
                Jsonb(values),
                Jsonb(
                    {
                        k: analysis.get(k)
                        for k in (
                            "engine",
                            "top",
                            "explanation",
                            "why_missed",
                            "match",
                            "similarity",
                            "condition",
                            "condition_text",
                            "title",
                        )
                    }
                ),
            ],
        )
        evidence_id = cursor.fetchone()[0]
        result: dict[str, Any] = {
            "evidence_id": evidence_id,
            "verdict": verdict,
            "analysis": analysis,
            "bad_case": target and target["code"],
            "created": created,
        }
        if target is None or target["detector"] == "BUILTIN":
            _audit(
                cursor,
                request_id,
                "AI_BAD_CASE_EVIDENCE",
                evidence_id,
                {
                    "verdict": verdict,
                    "code": target and target["code"],
                    "explanation": analysis.get("explanation"),
                    "why_missed": analysis.get("why_missed"),
                },
            )
            return result
        result.update(_reevaluate(cursor, target["id"], request_id=request_id))
        return result


def _reevaluate(
    cursor, case_id: str, *, request_id: str | None = None
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id::text, code, title, request_types, detector, state, verdict, condition, base_code, escalate_to,
               decided_at, rationale
        FROM eas.bad_case WHERE id = %s FOR UPDATE
        """,
        [case_id],
    )
    (
        cid,
        code,
        title,
        types,
        detector,
        state,
        verdict,
        cond,
        base,
        esc,
        decided_at,
        rationale,
    ) = cursor.fetchone()
    case = {
        "id": cid,
        "code": code,
        "title": title,
        "request_types": list(types),
        "detector": detector,
        "state": state,
        "verdict": verdict,
        "condition": cond,
        "base_code": base,
        "escalate_to": esc,
    }
    evaluation = evaluate_case(cursor, case)
    new_state = state
    if state == "CANDIDATE" and evaluation["enough"]:
        new_state = "ACTIVE"
    elif state == "REJECTED" and decided_at is not None:
        cursor.execute(
            "SELECT count(*) FROM eas.bad_case_evidence WHERE bad_case_id = %s AND created_at > %s",
            [cid, decided_at],
        )
        if cursor.fetchone()[0] >= REOPEN_EXTRA:
            new_state = "CANDIDATE"
            evaluation["summary"] = (
                f"Admin đã từ chối trước đây nhưng có thêm {REOPEN_EXTRA}+ lần thu hồi cùng "
                "kiểu lý do. " + evaluation["summary"]
            )
    new_rationale = rationale
    if detector == "RULE":
        new_rationale = compose_rationale(cursor, cid)
    cursor.execute(
        """
        UPDATE eas.bad_case
        SET evaluation = %s, state = %s, rationale = %s,
            activated_by = CASE WHEN %s = 'ACTIVE' AND state = 'CANDIDATE' THEN 'AI' ELSE activated_by END,
            activated_at = CASE WHEN %s = 'ACTIVE' AND state = 'CANDIDATE' THEN statement_timestamp()
                                ELSE activated_at END
        WHERE id = %s
        """,
        [Jsonb(evaluation), new_state, new_rationale, new_state, new_state, cid],
    )
    if state == "CANDIDATE" and new_state == "ACTIVE":
        action = "AI_BAD_CASE_LEARNED"
    elif new_state == "CANDIDATE":
        action = "AI_BAD_CASE_CANDIDATE"
    else:
        action = "AI_BAD_CASE_EVIDENCE"
    if request_id:
        _audit(
            cursor,
            request_id,
            action,
            cid,
            {
                "code": code,
                "state": new_state,
                "enough": evaluation["enough"],
                "summary": evaluation["summary"],
                "question": evaluation["question"],
            },
        )
    return {"state": new_state, "evaluation": evaluation}


def sweep(limit: int = 20) -> int:
    """Phân tích các lý do thu hồi chưa có bằng chứng (lỡ lúc AI service tắt); worker gọi định kỳ."""
    with connection.cursor() as cursor:
        if not available(cursor):
            return 0
        cursor.execute(
            """
            SELECT f.id::text FROM eas.ai_feedback f
            WHERE f.kind = 'AUTO_APPROVE_REVOKED' AND f.retired_at IS NULL
              AND f.created_at > now() - interval '30 days'
              AND NOT EXISTS (SELECT 1 FROM eas.bad_case_evidence e WHERE e.feedback_id = f.id)
            ORDER BY f.created_at LIMIT %s
            """,
            [limit],
        )
        ids = [r[0] for r in cursor.fetchall()]
    done = 0
    for fid in ids:
        try:
            if analyze_feedback(fid):
                done += 1
        except Exception:
            logger.warning("bad-case analysis failed: feedback=%s", fid, exc_info=True)
            break  # AI service chưa sẵn sàng: thử lại ở lượt sau
    return done


def analyze_in_background(feedback_id: str) -> None:
    """Gọi sau khi giao dịch thu hồi đã lưu; lỗi thì worker quét lại sau (sweep)."""
    import threading

    from django.db import close_old_connections

    def job():
        close_old_connections()
        try:
            analyze_feedback(feedback_id)
        except Exception:
            logger.warning(
                "bad-case analysis deferred to worker: feedback=%s",
                feedback_id,
                exc_info=True,
            )
        finally:
            close_old_connections()

    threading.Thread(target=job, name="bad-case-analysis", daemon=True).start()


# --------------------------------------------------------------------------- admin quyết
def admin_decide(
    cursor, *, case_id: str, actor_id: str, decision: str, body: dict[str, Any]
) -> dict[str, Any]:
    """approve (CANDIDATE -> ACTIVE, có thể sửa tên/lý do/điều kiện/loại đơn/mức chuyển), reject, retire, enable."""
    cursor.execute(
        """
        SELECT code, state, detector, condition, request_types, title, rationale, escalate_to, risk
        FROM eas.bad_case WHERE id = %s FOR UPDATE
        """,
        [case_id],
    )
    row = cursor.fetchone()
    if not row:
        raise LookupError("NOT_FOUND")
    code, state, detector, cond, types, title, rationale, esc, risk = row
    note = str(body.get("note") or "").strip()[:500] or None
    allowed = {
        "approve": ("CANDIDATE",),
        "reject": ("CANDIDATE",),
        "retire": ("ACTIVE",),
        "enable": ("RETIRED",),
    }
    if state not in allowed[decision]:
        raise PermissionError("STATE_CONFLICT")
    if decision in ("reject", "retire") and not note:
        raise ValueError("note: Cần lý do")
    if decision == "approve":
        if "condition" in body and detector == "RULE":
            cond = (
                bcc.validate(body["condition"])
                if body["condition"] is not None
                else None
            )
        if detector == "RULE" and not cond:
            raise ValueError(
                "condition: Bad case cần điều kiện đo được để AI tự nhận ra lần sau"
            )
        if "request_types" in body:
            new_types = body["request_types"]
            if not isinstance(new_types, list) or not 1 <= len(new_types) <= 60:
                raise ValueError("request_types: 1–60 mã loại")
            cursor.execute(
                "SELECT count(*) FROM eas.request_type WHERE code = ANY(%s)",
                [new_types],
            )
            if cursor.fetchone()[0] != len(set(new_types)):
                raise ValueError("request_types: Có mã loại không tồn tại")
            types = sorted(set(new_types))
        title = str(body.get("title") or title).strip()[:200]
        rationale = str(body.get("rationale") or rationale).strip()[:2000]
        esc = body.get("escalate_to", esc)
        if esc not in ("B", "C"):
            raise ValueError("escalate_to: B hoặc C")
        risk = body.get("risk", risk)
        if isinstance(risk, bool) or not isinstance(risk, int) or not 1 <= risk <= 5:
            raise ValueError("risk: 1–5")
        if len(title) < 3 or len(rationale) < 5:
            raise ValueError("title: Cần tên và lý do vì sao là bad case")
    new_state = {
        "approve": "ACTIVE",
        "reject": "REJECTED",
        "retire": "RETIRED",
        "enable": "ACTIVE",
    }[decision]
    if detector == "BUILTIN":
        cursor.execute(
            "UPDATE eas.bad_case SET state = %s, note = %s, decided_by = %s, decided_at = statement_timestamp() "
            "WHERE id = %s",
            [new_state, note, actor_id, case_id],
        )
    else:
        cursor.execute(
            """
            UPDATE eas.bad_case
            SET state = %s, note = %s, decided_by = %s, decided_at = statement_timestamp(),
                condition = CASE WHEN %s THEN %s ELSE condition END,
                condition_text = CASE WHEN %s AND detector = 'RULE' THEN %s ELSE condition_text END,
                request_types = %s, title = %s, rationale = %s, escalate_to = %s, risk = %s,
                activated_by = CASE WHEN %s = 'approve' THEN 'ADMIN' ELSE activated_by END,
                activated_at = CASE WHEN %s = 'approve' THEN statement_timestamp() ELSE activated_at END
            WHERE id = %s
            """,
            [
                new_state,
                note,
                actor_id,
                decision == "approve",
                Jsonb(cond) if cond else None,
                decision == "approve",
                bcc.describe(cond) if cond else None,
                list(types),
                title,
                rationale,
                esc,
                risk,
                decision,
                decision,
                case_id,
            ],
        )
    return {"id": case_id, "code": code, "state": new_state}
