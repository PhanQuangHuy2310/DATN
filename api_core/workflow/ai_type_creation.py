"""AI tạo loại yêu cầu mới khi người dùng cần một việc chưa có trong danh mục.

Luồng: người dùng gõ nhu cầu ở ô tìm kiếm → AI gợi ý "Có phải ý bạn là …" → không phải → "Tạo loại yêu cầu mới".
``propose`` (chỉ đọc) cho xem AI định tạo gì; ``create`` tạo thật. Người đầu tiên tạo ra loại; người thứ hai tìm là thấy
(bộ phân loại nhận loại mới ngay qua bộ nhớ loại mới, menu có mục mới).

An toàn:
* nội dung AI không hiểu (chuỗi vô nghĩa) bị từ chối; nội dung khớp rõ một loại đã có (kể cả loại AI vừa tạo cho người
  khác) thì trả về loại đó, không tạo trùng;
* loại AI tạo luôn từ mẫu B trở lên (quản lý trực tiếp duyệt, bộ phận chuyên môn thực hiện) nên không bao giờ được AI tự
  duyệt khi chưa có ai rà soát; mẫu và trọng số do mô hình hồ sơ quy trình đề xuất;
* tối đa ``MAX_PER_DAY`` loại mỗi người mỗi 24 giờ; mọi lần tạo ghi nhật ký kiểm toán và báo quản trị viên rà soát.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.audit import canonical_sha256
from api_core.authn.models import Actor
from api_core.workflow import learned_types, type_onboarding
from api_core.workflow.errors import CommandError
from api_core.workflow.learned_types import EXECUTOR_DEPARTMENT, route_summary
from api_core.workflow.service import _append_admin_audit

logger = logging.getLogger(__name__)

MAX_PER_DAY = 3
EXISTING_MIN_CONFIDENCE = 0.85  # mô hình gốc chắc chắn đến mức này (và không phải nhu cầu mới) thì dùng loại đã có
LEARNED_EXISTING = 0.5  # loại mới (bộ nhớ loại mới) khớp từ mức này thì dùng loại đó
FALLBACK_GROUP = "WORK"
DEPARTMENT_EXECUTOR = {dept: executor for executor, dept in EXECUTOR_DEPARTMENT.items()}
DEPARTMENT_EXECUTOR.setdefault("SALES", "EXECUTOR_MARKETING")
GENERIC_FORM = {
    "schema_version": 1,
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "reason"],
    "properties": {
        "title": {"type": "string", "minLength": 5, "maxLength": 150},
        "reason": {"type": "string", "minLength": 10, "maxLength": 4000},
        "due_date": {"type": "string", "format": "date"},
    },
}
# Cùng dạng hướng dẫn với các thông báo khác (SystemUpdates.jsx đọc {title, steps}).
ANNOUNCEMENT_GUIDANCE = [
    {
        "title": "Rà soát loại yêu cầu AI vừa tạo",
        "steps": [
            "Mở Yêu cầu & Quy trình, tìm loại mới theo mã trong thông báo.",
            "Kiểm tra tên, nhóm nghiệp vụ, biểu mẫu và tuyến duyệt; sửa nếu cần rồi ban hành lại.",
            "Nếu trùng một loại đã có, tắt loại mới để người dùng dùng loại cũ.",
        ],
    }
]
SLA = {
    "schema_version": 1,
    "clock": "CALENDAR_UTC",
    "reminder_fraction": 0.5,
    "approval_hours": 24,
}
_FILLER = re.compile(
    r"^(?:em|tôi|toi|mình|minh|cho em|cho tôi|cho mình|xin phép|em muốn|tôi muốn|mình muốn|muốn|em cần|tôi cần|cần|"
    r"làm sao để|làm thế nào để|cách)\s+",
    re.IGNORECASE,
)


def clean_name(text: str) -> str:
    name = " ".join(str(text or "").split()).strip(" .,;:!?-–")
    for _ in range(3):
        name = _FILLER.sub("", name)
    name = name[:80].rstrip(" .,;:!?-–")
    return name[:1].upper() + name[1:]


def _ai_post(path: str, body: dict) -> dict:
    from api_core.workflow.ai_learning import _ai_http

    try:
        with _ai_http() as client:
            response = client.post(path, json=body)
    except Exception as exc:
        raise CommandError("AI_SERVICE_UNAVAILABLE", status=503) from exc
    if response.status_code != 200:
        raise CommandError("AI_SERVICE_ERROR", status=502)
    return response.json()


def _classify(text: str) -> dict:
    return _ai_post(
        "/ai/classify/request",
        {
            "title": text[:500],
            "description": "",
            "learned_types": learned_types.current(),
        },
    )


def _assess(name: str, group: str) -> dict:
    try:
        return _ai_post(
            "/ai/process-profile/assess",
            {
                "name": name,
                "description": f"Nhu cầu do người dùng nêu: {name}",
                "category": group,
                "fields": list(GENERIC_FORM["properties"]),
            },
        )
    except CommandError:
        return {
            "lifecycle": "B",
            "risk_weight": 3,
            "reasons_lifecycle": ["dịch vụ AI chưa phản hồi: dùng mẫu B"],
        }


def _groups() -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT code, name FROM eas.request_group")
        return dict(cursor.fetchall())


def _existing(result: dict) -> dict | None:
    code = result.get("predicted_request_type")
    conf = float(result.get("confidence_request_type") or 0)
    learned = result.get("source") == "learned"
    if (learned and conf >= LEARNED_EXISTING) or (
        not result.get("novel") and conf >= EXISTING_MIN_CONFIDENCE
    ):
        return {
            "code": code,
            "name": result.get("predicted_request_name") or code,
            "confidence": round(conf, 4),
        }
    return None


def propose(text: str) -> dict[str, Any]:
    """Đề xuất của AI cho nhu cầu ``text`` (không ghi gì): loại đã có, hoặc cấu hình loại mới sẽ tạo."""
    text = " ".join(str(text or "").split())
    if not 6 <= len(text) <= 120:
        raise CommandError(
            "TEXT_LENGTH_INVALID",
            status=422,
            fields={
                "text": [
                    "Mô tả nhu cầu từ 6 đến 120 ký tự, ví dụ: Đăng ký suất ăn trưa."
                ]
            },
        )
    result = _classify(text)
    if result.get("fallback_used"):
        raise CommandError("AI_SERVICE_UNAVAILABLE", status=503)
    if result.get("unclear"):
        raise CommandError(
            "TEXT_UNCLEAR",
            status=422,
            fields={
                "text": [
                    "AI chưa hiểu nội dung này; hãy viết rõ nhu cầu, ví dụ: Đăng ký chỗ đỗ ô tô."
                ]
            },
        )
    existing = _existing(result)
    if existing:
        return {"existing": existing}
    name = clean_name(text)
    groups = _groups()
    group = (
        result.get("predicted_category")
        if result.get("predicted_category") in groups
        else FALLBACK_GROUP
    )
    profile = _assess(name, group)
    lifecycle = (
        "C" if profile.get("lifecycle") == "C" else "B"
    )  # không bao giờ A: chưa ai rà soát thì không tự duyệt
    executor = DEPARTMENT_EXECUTOR.get(
        result.get("predicted_department") or "", "EXECUTOR_ADMIN"
    )
    route = {
        "schema_version": 1,
        "rules": [
            {"id": "AI_DEFAULT", "default": True, "approvers": ["DIRECT_MANAGER"]}
        ],
        "executor": executor,
        "acceptor": "REQUESTER" if lifecycle == "C" else None,
    }
    nearest = (
        result.get("predicted_request_type")
        if result.get("source") != "learned"
        else None
    )
    return {
        "proposal": {
            "name": name,
            "group_code": group,
            "group_name": groups.get(group, group),
            "lifecycle": lifecycle,
            "risk_weight": int(min(5, max(1, int(profile.get("risk_weight") or 3)))),
            "route_rules": route,
            "route_summary": route_summary(route),
            "reasons": (profile.get("reasons_lifecycle") or [])[:3],
            "nearest_type": nearest,
            "nearest_name": result.get("predicted_request_name") or "",
            "nearest_confidence": round(
                float(result.get("confidence_request_type") or 0), 4
            ),
        }
    }


def create(actor: Actor, text: str, correlation_id: str) -> dict[str, Any]:
    plan = propose(text)
    if "existing" in plan:
        return {"created": False, "type": plan["existing"]}
    p = plan["proposal"]
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT eas.lock_security(true)")
        cursor.execute(
            "SELECT count(*) FROM eas.admin_event WHERE action = 'AI_REQUEST_TYPE_CREATED' AND actor_id = %s "
            "AND occurred_at > statement_timestamp() - interval '1 day'",
            [actor.id],
        )
        if cursor.fetchone()[0] >= MAX_PER_DAY:
            raise CommandError("AI_TYPE_CREATION_LIMIT", status=429)
        # Người khác vừa tạo đúng tên này (giữa lúc xem trước và tạo): dùng loại đó.
        cursor.execute(
            "SELECT code, name FROM eas.request_type WHERE lower(name) = lower(%s) AND is_active",
            [p["name"]],
        )
        same = cursor.fetchone()
        if same:
            return {
                "created": False,
                "type": {"code": same[0], "name": same[1], "confidence": 1.0},
            }
        cursor.execute(
            """
            SELECT cr.actor_bindings FROM eas.request_type rt JOIN eas.config_release cr ON cr.id = rt.active_release_id
            WHERE cr.state = 'PUBLISHED' ORDER BY (rt.code = %s) DESC, cr.published_at DESC LIMIT 1
            """,
            [p["nearest_type"] or ""],
        )
        bindings = cursor.fetchone()[0]
        type_id, code = str(uuid4()), f"AI_{uuid4().hex[:8].upper()}"
        description = (
            f"Do AI tạo từ nhu cầu của người dùng: «{' '.join(text.split())[:200]}»"
        )
        cursor.execute(
            """
            INSERT INTO eas.request_type(id, code, lifecycle, name, description, category, is_active, risk_weight,
                                         approval_level)
            VALUES (%s, %s, %s, %s, %s, %s, false, %s, 1)
            """,
            [
                type_id,
                code,
                p["lifecycle"],
                p["name"],
                description,
                p["group_code"],
                p["risk_weight"],
            ],
        )
        sla = {
            **SLA,
            "execution_hours": 48,
            "acceptance_hours": 24 if p["lifecycle"] == "C" else None,
        }
        digest = canonical_sha256(
            {
                "actor_bindings": bindings,
                "form_schema": GENERIC_FORM,
                "lifecycle": p["lifecycle"],
                "route_rules": p["route_rules"],
                "sla_profile": sla,
                "type_id": type_id,
            }
        )
        cursor.execute(
            """
            INSERT INTO eas.config_release(type_id, version, state, lifecycle, form_schema, route_rules, actor_bindings,
                                           sla_profile, created_by, published_by, published_at, content_sha256)
            VALUES (%s, 1, 'PUBLISHED', %s, %s, %s, %s, %s, %s, %s, statement_timestamp(), %s)
            RETURNING id::text
            """,
            [
                type_id,
                p["lifecycle"],
                Jsonb(GENERIC_FORM),
                Jsonb(p["route_rules"]),
                Jsonb(bindings),
                Jsonb(sla),
                actor.id,
                actor.id,
                digest,
            ],
        )
        release_id = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE eas.request_type SET active_release_id = %s, is_active = true WHERE id = %s",
            [release_id, type_id],
        )
        cursor.execute(
            """
            INSERT INTO eas.request_menu_item(code, group_code, type_code, label, preset, sort_order, is_active)
            VALUES (%s, %s, %s, %s, '{}'::jsonb, 900, true)
            """,
            [code, p["group_code"], code, p["name"]],
        )
        cursor.execute(
            "UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1"
        )
        scoped = type_onboarding.extend_bad_cases(
            cursor,
            type_code=code,
            nearest_code=p["nearest_type"],
            confidence=p["nearest_confidence"],
            nearest_name=p["nearest_name"],
        )
        details = {
            **p,
            "code": code,
            "release_id": release_id,
            "text": text[:200],
            "bad_cases_extended": scoped,
        }
        _append_admin_audit(
            cursor,
            actor_id=actor.id,
            action="AI_REQUEST_TYPE_CREATED",
            target_type="request_type",
            target_id=type_id,
            type_id=type_id,
            details=details,
            reason=f"AI tạo loại yêu cầu mới «{p['name']}» theo nhu cầu người dùng nêu",
            correlation_id=correlation_id,
        )
        cursor.execute(
            """
            INSERT INTO eas.system_announcement(audience, kind, version, title, summary, changes, guidance)
            VALUES ('ADMIN', 'REQUEST_TYPE_CREATED', %s, %s, %s, %s, %s)
            """,
            [
                code,
                f"AI đã tạo loại yêu cầu mới «{p['name']}»",
                (
                    f"Từ nhu cầu «{text[:120]}» của {actor.display_name or actor.email}. Quy trình mẫu {p['lifecycle']}: "
                    f"{p['route_summary']}."
                ),
                Jsonb(
                    [
                        {
                            "kind": "REQUEST_TYPE_CREATED",
                            "title": f"{p['name']} (nhóm {p['group_name']}, mã {code})",
                        }
                    ]
                ),
                Jsonb(ANNOUNCEMENT_GUIDANCE),
            ],
        )
    learned_types.invalidate()
    return {
        "created": True,
        "type": {
            "code": code,
            "name": p["name"],
            "lifecycle": p["lifecycle"],
            "group_code": p["group_code"],
            "route_summary": p["route_summary"],
        },
    }
