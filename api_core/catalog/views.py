"""Read-only request catalogue sourced from published, scoped policy releases.

The request form is *not* a security boundary: create/submit still rechecks
role membership, request type, published release and state under DB locks.
"""

import json
from functools import lru_cache
from pathlib import Path

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from api_core.authn.service import require_actor
from api_core.catalog.availability import request_option_blocker
from api_core.catalog.plan_catalog import (
    enterprise_item,
    enterprise_items,
    enterprise_options,
    five_level_framework,
    plan_item,
    plan_items,
    resolve_five_level_metadata,
)


@lru_cache(maxsize=1)
def approval_menu_blueprint():
    """The 20 display rows supplied by the plan, mapped to 18 distinct codes."""
    data = json.loads(
        Path(__file__).with_name("approval_menu.json").read_text(encoding="utf-8")
    )
    if (
        data.get("display_rows") != 20
        or data.get("unique_types") != 18
        or len(data["options"]) != 20
        or len({row["code"] for row in data["options"]}) != 18
    ):
        raise RuntimeError("INVALID_APPROVAL_MENU")
    return data


CORE_TYPE_NAMES = {
    "LEAVE": "Nghỉ phép thường niên",
    "LEAVE_SPECIAL": "Nghỉ phép đặc biệt",
    "ROOM_BOOKING": "Đặt phòng họp",
    "EXPENSE_CLAIM": "Thanh toán chi phí",
    "ACCESS": "Cấp quyền truy cập hệ thống",
    "ACCESS_FACILITY": "Cấp quyền ra vào",
    "BUSINESS_TRIP": "Công tác",
    "IT_SUPPORT": "Yêu cầu hỗ trợ IT",
    "EQUIPMENT": "Mua sắm thiết bị",
    "EQUIPMENT_BORROW": "Mượn thiết bị",
}

CORE_FIELD_LABELS = {
    "title": "Tiêu đề yêu cầu",
    "reason": "Lý do / Diễn giải chi tiết",
    "start_date": "Ngày bắt đầu",
    "end_date": "Ngày kết thúc",
    "handover_user_id": "Người nhận bàn giao công việc",
    "special_leave_type": "Loại chế độ nghỉ đặc biệt",
    "room_name": "Phòng họp / Không gian",
    "booking_date": "Ngày sử dụng",
    "start_time": "Giờ bắt đầu (HH:MM)",
    "end_time": "Giờ kết thúc (HH:MM)",
    "attendees_count": "Số người tham dự",
    "purpose": "Mục đích sử dụng",
    "expense_category": "Hạng mục chi phí",
    "amount_vnd": "Số tiền / Dự toán (VNĐ)",
    "amount": "Số tiền (VNĐ)",
    "invoice_number": "Số hóa đơn / Chứng từ",
    "beneficiary_account": "Tài khoản thụ hưởng",
    "app_code": "Hệ thống / Ứng dụng",
    "requested_role": "Quyền hạn đề nghị",
    "duration_days": "Thời hạn cấp quyền (ngày)",
    "leave_type": "Loại nghỉ phép",
    "access_level": "Mức quyền truy cập",
    "justification": "Lý do đề nghị cấp quyền",
    "facility_zone": "Khu vực cần ra vào",
    "access_window": "Khung giờ đăng ký",
    "destination": "Địa điểm công tác",
    "transportation": "Phương tiện di chuyển",
    "support_category": "Nhóm hỗ trợ kỹ thuật",
    "urgency": "Mức độ ưu tiên",
    "device_asset_tag": "Mã tài sản / Tên thiết bị",
    "item_name": "Tên thiết bị / Vật tư",
    "quantity": "Số lượng",
    "specification": "Cấu hình / Thông số kỹ thuật",
    "specs": "Cấu hình / Thông số kỹ thuật",
    "location": "Địa điểm sử dụng",
}


def resolve_field_labels(code: str) -> dict[str, str]:
    specific = (
        plan_item(code)
        or enterprise_item(code)
        or next(
            (x for x in approval_menu_blueprint()["types"] if x["code"] == code), {}
        )
    ).get("field_labels", {})
    return {**CORE_FIELD_LABELS, **specific}


def approval_type_name(code):
    matched = next(
        (item for item in approval_menu_blueprint()["types"] if item["code"] == code),
        None,
    )
    return (matched or plan_item(code) or enterprise_item(code) or {}).get(
        "name", CORE_TYPE_NAMES.get(code, code)
    )


@require_GET
def request_types(request):
    """Public list of active type codes; does not reveal policy internals."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT rt.code, rt.lifecycle, rt.name, rt.description, rt.category,
              (cr.id IS NOT NULL AND cr.state = 'PUBLISHED'
               AND cr.type_id = rt.id AND cr.lifecycle = rt.lifecycle) AS configured,
              rt.risk_weight, rt.approval_level
            FROM eas.request_type rt
            LEFT JOIN eas.config_release cr ON cr.id=rt.active_release_id
            WHERE rt.is_active ORDER BY rt.code
        """)
        items = []
        for row in cursor.fetchall():
            code, lifecycle, name, description, category, configured = row[:6]
            db_rw = row[6] if len(row) > 6 else None
            db_al = row[7] if len(row) > 7 else None
            risk_w, app_lvl = resolve_five_level_metadata(code, db_rw, db_al)
            items.append(
                {
                    "code": code,
                    "name": name.strip() or approval_type_name(code),
                    "description": description,
                    "category": category,
                    "lifecycle": lifecycle,
                    "configured": configured,
                    "risk_weight": risk_w,
                    "approval_level": app_lvl,
                }
            )
    return JsonResponse(
        {"items": items, "five_level_framework": five_level_framework()}
    )


def _fetch_requester_form_items(cursor, actor):
    cursor.execute(
        """
        SELECT rt.code, rt.lifecycle, cr.id::text, cr.form_schema,
               rt.name, rt.description, rt.category,
               rt.risk_weight, rt.approval_level
        FROM eas.request_type rt
        JOIN eas.config_release cr ON cr.id=rt.active_release_id
        WHERE rt.is_active AND cr.state='PUBLISHED'
          AND cr.type_id=rt.id AND cr.lifecycle=rt.lifecycle
          AND EXISTS (
            SELECT 1 FROM eas.role_membership m
            WHERE m.user_id=%s AND m.role='REQUESTER'
              AND m.revoked_at IS NULL
              AND m.valid_from<=statement_timestamp()
              AND (m.valid_to IS NULL OR m.valid_to>statement_timestamp())
              AND (m.scope_kind='GLOBAL' OR
                   (m.scope_kind='DEPARTMENT' AND m.department_id=%s))
              AND (m.type_scope='ALL' OR
                   (m.type_scope='ONE' AND m.type_id=rt.id))
          )
        ORDER BY rt.code
    """,
        [actor.id, actor.department_id],
    )
    items = []
    for row in cursor.fetchall():
        code, lifecycle, release_id, form_schema, name, description, category = row[:7]
        db_rw = row[7] if len(row) > 7 else None
        db_al = row[8] if len(row) > 8 else None
        risk_w, app_lvl = resolve_five_level_metadata(code, db_rw, db_al)
        items.append(
            {
                "code": code,
                "name": name.strip() or approval_type_name(code),
                "description": description,
                "category": category,
                "lifecycle": lifecycle,
                "release_id": release_id,
                "form_schema": form_schema,
                "field_labels": resolve_field_labels(code),
                "department_id": actor.department_id,
                "risk_weight": risk_w,
                "approval_level": app_lvl,
            }
        )
    return items


def _fetch_requester_type_states(cursor, actor):
    cursor.execute(
        """
        SELECT rt.code, rt.lifecycle, rt.is_active,
               (cr.id IS NOT NULL AND cr.state='PUBLISHED'
                AND cr.type_id=rt.id AND cr.lifecycle=rt.lifecycle) AS has_release,
               EXISTS (
                 SELECT 1 FROM eas.role_membership m
                 WHERE m.user_id=%s AND m.role='REQUESTER'
                   AND m.revoked_at IS NULL AND m.valid_from<=statement_timestamp()
                   AND (m.valid_to IS NULL OR m.valid_to>statement_timestamp())
                   AND (m.scope_kind='GLOBAL' OR
                        (m.scope_kind='DEPARTMENT' AND m.department_id=%s))
                   AND (m.type_scope='ALL' OR
                        (m.type_scope='ONE' AND m.type_id=rt.id))
               ) AS scoped
        FROM eas.request_type rt
        LEFT JOIN eas.config_release cr ON cr.id=rt.active_release_id
    """,
        [actor.id, actor.department_id],
    )
    return {
        code: (lc, active, published, scoped)
        for code, lc, active, published, scoped in cursor.fetchall()
    }


def _build_requester_menu(items, states):
    available = {item["code"]: item for item in items}
    menu = []
    for row in approval_menu_blueprint()["options"] + enterprise_options():
        code = row["code"]
        state = states.get(code)
        match = available.get(code)
        valid = bool(match and match["lifecycle"] == row["lifecycle"])
        blocker, reason = request_option_blocker(state, row["lifecycle"])
        risk_w, app_lvl = resolve_five_level_metadata(
            code,
            match["risk_weight"] if match else row.get("risk_weight"),
            match["approval_level"] if match else row.get("approval_level"),
        )
        menu.append(
            {
                **row,
                "risk_weight": risk_w,
                "approval_level": app_lvl,
                "available": valid,
                "blocker_code": blocker if not valid else None,
                "disabled_reason": reason if not valid else None,
            }
        )
    for item in items:
        if not any(row["code"] == item["code"] for row in menu):
            menu.append(
                {
                    "group": "Biểu mẫu hệ thống đang hoạt động",
                    "label": item["name"],
                    "code": item["code"],
                    "lifecycle": item["lifecycle"],
                    "risk_weight": item["risk_weight"],
                    "approval_level": item["approval_level"],
                    "description": item["description"] or "Theo cấu hình hiện hành",
                    "available": True,
                    "blocker_code": None,
                    "disabled_reason": None,
                }
            )
    return menu


@require_GET
@require_actor("REQUESTER")
def request_type_forms(request):
    """Configured templates visible to a requester inside their effective scope.

    A published schema can be used to render a form; write services re-check all
    authorizations. Never expose actor_bindings, route_rules or secrets here.
    """
    actor = request.actor
    with connection.cursor() as cursor:
        items = _fetch_requester_form_items(cursor, actor)
        states = _fetch_requester_type_states(cursor, actor)
    menu = _build_requester_menu(items, states)
    return JsonResponse(
        {
            "items": items,
            "approval_menu": menu,
            "five_level_framework": five_level_framework(),
            "request_code_generated_by_server": True,
        }
    )


@require_GET
@require_actor("POLICY_ADMIN", "OPS_ADMIN")
def plan_request_type_blueprints(request):
    """Read-only plan blueprints, not request types enabled for submission.

    Membership scope + SoD are independently rechecked by write services.
    """
    return JsonResponse(
        {
            "source": "plan.docx",
            "count": len(plan_items()),
            "deployment_state": "BLUEPRINT_ONLY",
            "items": plan_items(),
            "enterprise_items": enterprise_items(),
            "five_level_framework": five_level_framework(),
            "approval_menu": approval_menu_blueprint(),
        }
    )


@require_GET
@require_actor("REQUESTER")
def colleague_choices(request):
    """For form UUID references: only active coworkers from the requester's department.

    No email, password, role grants or cross-department information is returned.
    This is only a convenience list, NOT authorization for approval assignment.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id::text, display_name FROM eas.app_user
            WHERE is_active AND department_id=%s AND id<>%s
            ORDER BY display_name, id LIMIT 300
        """,
            [request.actor.department_id, request.actor.id],
        )
        choices = [{"id": x, "display_name": y} for x, y in cursor.fetchall()]
    return JsonResponse({"items": choices})
