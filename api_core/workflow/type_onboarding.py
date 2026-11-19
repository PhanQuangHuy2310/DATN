"""Cho loại yêu cầu mới (admin tạo hoặc AI tạo) dùng được ngay các cơ chế AI mà loại có sẵn đang có.

1. ``ensure_escalation_releases``: loại mẫu A có sẵn bản cấu hình nâng cấp B và C (như migration 23 làm cho 9 loại
   ban đầu), để khi hồ sơ dính tình huống xấu AI chuyển được luồng thay vì chỉ chặn tự duyệt.
2. ``extend_bad_cases``: các tình huống xấu có sẵn áp cho loại gần nhất được mở rộng sang loại mới (bad_case SCOPE,
   nguồn AI). Loại gần nhất do bộ phân loại chọn từ tên và mô tả của loại mới; chỉ mở rộng khi đủ giống.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.audit import canonical_sha256

logger = logging.getLogger(__name__)

# nhóm -> (bộ phận thực hiện, cấp duyệt thêm ở B, cấp duyệt thêm ở C); giống cách migration 23 nâng 9 loại ban đầu.
ESCALATION_PLAN: dict[str, tuple[str, list[str], list[str]]] = {
    "ABSENCE": ("EXECUTOR_HR", [], ["HR_MANAGER"]),
    "WORKTIME": ("EXECUTOR_HR", [], ["HR_MANAGER"]),
    "PEOPLE": ("EXECUTOR_HR", [], ["HR_MANAGER"]),
    "PAYMENT": ("EXECUTOR_FINANCE", ["FINANCE"], ["FINANCE", "DIRECTOR"]),
    "SALES": ("EXECUTOR_FINANCE", ["FINANCE"], ["FINANCE", "DIRECTOR"]),
    "PROCUREMENT": ("EXECUTOR_PROCUREMENT", ["FINANCE"], ["FINANCE", "DIRECTOR"]),
    "BORROW": ("EXECUTOR_FACILITY", [], []),
    "PROVISION": ("EXECUTOR_IT", [], ["IT_MANAGER"]),
    "SUPPORT": ("EXECUTOR_IT", [], ["IT_MANAGER"]),
    "LEGAL": ("EXECUTOR_LEGAL", [], ["LEGAL"]),
    "ASSET": ("EXECUTOR_ASSET", [], ["WAREHOUSE_MANAGER"]),
    "WORK": ("EXECUTOR_ADMIN", [], ["DIRECTOR"]),
}
DEFAULT_PLAN = ("EXECUTOR_ADMIN", [], ["DIRECTOR"])
SCOPE_MIN_CONFIDENCE = 0.5


def _escalated_route(
    route_rules: dict, lifecycle: str, plan: tuple[str, list[str], list[str]]
) -> dict:
    executor, extra_b, extra_c = plan
    extra = extra_b if lifecycle == "B" else extra_c
    rules = []
    for rule in route_rules.get("rules") or []:
        approvers = list(rule.get("approvers") or [])
        for a in extra:
            if a not in approvers and len(approvers) < 5:
                approvers.append(a)
        rules.append({**rule, "approvers": approvers})
    return {
        "schema_version": 1,
        "rules": rules,
        "executor": executor,
        "acceptor": "DIRECT_MANAGER" if lifecycle == "C" else None,
    }


def ensure_escalation_releases(cursor, *, type_id: str, actor_id: str) -> list[str]:
    """Tạo bản nâng cấp B/C còn thiếu cho loại mẫu A (trong giao dịch của người gọi). Trả về luồng đã tạo."""
    cursor.execute("SELECT to_regclass('eas.ai_remediation') IS NOT NULL")
    if not cursor.fetchone()[0]:
        return []  # migration 23 chưa chạy: chưa có cột escalation
    cursor.execute(
        """
        SELECT rt.lifecycle, rt.category, cr.form_schema, cr.route_rules, cr.actor_bindings, cr.sla_profile
        FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
        WHERE rt.id = %s::uuid AND cr.state = 'PUBLISHED'
        """,
        [type_id],
    )
    row = cursor.fetchone()
    if not row or row[0] != "A":
        return []
    _lc, category, form_schema, route_rules, actor_bindings, sla_profile = row
    plan = ESCALATION_PLAN.get(category or "", DEFAULT_PLAN)
    created = []
    for lifecycle in ("B", "C"):
        cursor.execute(
            "SELECT 1 FROM eas.config_release WHERE type_id = %s::uuid AND escalation AND lifecycle = %s "
            "AND state = 'PUBLISHED' LIMIT 1",
            [type_id, lifecycle],
        )
        if cursor.fetchone():
            continue
        route = _escalated_route(route_rules or {}, lifecycle, plan)
        sla = {
            **(sla_profile or {}),
            "execution_hours": 24,
            "acceptance_hours": 24 if lifecycle == "C" else None,
        }
        digest = canonical_sha256(
            {
                "actor_bindings": actor_bindings,
                "form_schema": form_schema,
                "lifecycle": lifecycle,
                "route_rules": route,
                "sla_profile": sla,
                "type_id": type_id,
                "escalation": True,
            }
        )
        cursor.execute(
            """
            INSERT INTO eas.config_release(
              type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings, sla_profile,
              created_by, published_by, published_at, content_sha256, escalation)
            VALUES (%s::uuid, (SELECT max(version) + 1 FROM eas.config_release WHERE type_id = %s::uuid), 'PUBLISHED',
                    %s, %s, %s, %s, %s, %s::uuid, %s::uuid, statement_timestamp(), %s, true)
            """,
            [
                type_id,
                type_id,
                lifecycle,
                Jsonb(form_schema),
                Jsonb(route),
                Jsonb(actor_bindings),
                Jsonb(sla),
                actor_id,
                actor_id,
                digest,
            ],
        )
        created.append(lifecycle)
    return created


def _scope_code(base: str, type_code: str) -> str | None:
    code = f"{base}_{type_code}"
    return code if re.fullmatch(r"BC_[A-Z0-9_]{2,57}", code) else None


def extend_bad_cases(
    cursor,
    *,
    type_code: str,
    nearest_code: str | None,
    confidence: float,
    nearest_name: str = "",
) -> list[str]:
    """Mở rộng tình huống xấu có sẵn của loại gần nhất sang loại mới (SCOPE, ACTIVE, nguồn AI)."""
    if (
        not nearest_code
        or confidence < SCOPE_MIN_CONFIDENCE
        or nearest_code == type_code
    ):
        return []
    cursor.execute("SELECT to_regclass('eas.bad_case') IS NOT NULL")
    if not cursor.fetchone()[0]:
        return []
    cursor.execute(
        """
        SELECT code, title, rationale, condition_text, risk, escalate_to
        FROM eas.bad_case
        WHERE detector = 'BUILTIN' AND state = 'ACTIVE' AND %s = ANY(request_types)
        """,
        [nearest_code],
    )
    created = []
    for base, title, rationale, condition_text, risk, escalate_to in cursor.fetchall():
        code = _scope_code(base, type_code)
        if not code:
            continue
        evaluation = {
            "summary": (
                f"Loại mới {type_code} giống loại {nearest_name or nearest_code} "
                f"(độ tin cậy {confidence:.0%}); tình huống xấu của loại đó được áp dụng ngay cho loại mới."
            ),
            "nearest_type": nearest_code,
            "confidence": round(confidence, 4),
        }
        cursor.execute(
            """
            INSERT INTO eas.bad_case(code, title, rationale, condition_text, request_types, detector, base_code,
                                     verdict, risk, escalate_to, source, state, evaluation, activated_by, activated_at)
            VALUES (%s, %s, %s, %s, %s, 'SCOPE', %s, 'EXISTING_SCOPE', %s, %s, 'AI', 'ACTIVE', %s, 'AI',
                    statement_timestamp())
            ON CONFLICT (code) DO NOTHING
            RETURNING code
            """,
            [
                code,
                title,
                rationale,
                condition_text,
                [type_code],
                base,
                risk,
                escalate_to,
                Jsonb(evaluation),
            ],
        )
        if cursor.fetchone():
            created.append(code)
    return created


def nearest_known_type(
    name: str, description: str = ""
) -> tuple[str | None, str, float]:
    """Loại có sẵn (mô hình đã học) gần nhất với tên + mô tả của loại mới; (None, "", 0) khi AI không phản hồi."""
    from api_core.workflow.ai_learning import _ai_http

    try:
        with _ai_http() as client:
            response = client.post(
                "/ai/classify/request",
                json={"title": name[:500], "description": description[:4000]},
            )
        data = response.json() if response.status_code == 200 else {}
    except Exception:
        logger.warning("nearest type lookup failed", exc_info=True)
        return None, "", 0.0
    if data.get("fallback_used") or data.get("unclear"):
        return None, "", 0.0
    return (
        data.get("predicted_request_type"),
        data.get("predicted_request_name") or "",
        float(data.get("confidence_request_type") or 0.0),
    )


def onboard_after_commit(type_code: str) -> None:
    """Sau khi admin ban hành bản đầu của một loại mới: mở rộng tình huống xấu (gọi AI ngoài giao dịch chính)."""
    from api_core.catalog.plan_catalog import catalog_v2_item
    from api_core.workflow import learned_types

    learned_types.invalidate()
    if catalog_v2_item(type_code):
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name, description FROM eas.request_type WHERE code = %s",
                [type_code],
            )
            row = cursor.fetchone()
        if not row:
            return
        nearest, nearest_name, confidence = nearest_known_type(row[0], row[1] or "")
        with transaction.atomic(), connection.cursor() as cursor:
            extend_bad_cases(
                cursor,
                type_code=type_code,
                nearest_code=nearest,
                confidence=confidence,
                nearest_name=nearest_name,
            )
    except Exception:
        logger.warning("type onboarding failed: %s", type_code, exc_info=True)


def summary(cursor, type_code: str) -> dict[str, Any]:
    """Tình trạng "đã học" của một loại: có trong mô hình gốc không, bản nâng luồng, tình huống xấu áp dụng."""
    from api_core.catalog.plan_catalog import catalog_v2_item

    cursor.execute(
        """
        SELECT rt.id::text, rt.lifecycle,
               (SELECT array_agg(cr.lifecycle ORDER BY cr.lifecycle) FROM eas.config_release cr
                 WHERE cr.type_id = rt.id AND cr.escalation AND cr.state = 'PUBLISHED')
        FROM eas.request_type rt WHERE rt.code = %s
        """,
        [type_code],
    )
    row = cursor.fetchone()
    if not row:
        return {}
    cursor.execute(
        "SELECT code FROM eas.bad_case WHERE state = 'ACTIVE' AND (%s = ANY(request_types) OR '*' = ANY(request_types))",
        [type_code],
    )
    return {
        "in_base_model": bool(catalog_v2_item(type_code)),
        "escalation_releases": list(row[2] or []),
        "bad_cases": [r[0] for r in cursor.fetchall()],
    }
