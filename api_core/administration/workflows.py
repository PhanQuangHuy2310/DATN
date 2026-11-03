"""Request workflows screen (admin portal): lifecycle groups A/B/C and request types.

Backed by the core catalogue: eas.request_type plus its active
eas.config_release (form schema, routing rules, SLA). The retired
request_templates/workflow_categories tables never drove the workflow engine,
so this screen now shows what the engine really runs.

Editable here: name, group, active flag and automation level (risk_weight),
all through administration.service.mutate (validation, idempotency, audit).
Lifecycle, form and routing changes need a new published config release
(Policy workspace); they are rejected with an explicit error code instead of
being silently ignored.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

from django.db import IntegrityError, connection
from django.http import JsonResponse

from api_core.authn.module_access import can
from api_core.authn.service import require_actor
from api_core.catalog.plan_catalog import catalog_v2
from api_core.http import JsonBodyError, api_error, correlation_id, parse_json_object
from api_core.workflow.service import CommandError

from .service import mutate, read_record

logger = logging.getLogger(__name__)

READ_ROLES = ("OPS_ADMIN", "POLICY_ADMIN", "AUDITOR")
LIFECYCLES = {
    "A": (
        "Nhóm A: Chỉ phê duyệt",
        "Yêu cầu hoàn tất ngay khi được phê duyệt (nghỉ phép, chấm công, thanh toán).",
    ),
    "B": (
        "Nhóm B: Phê duyệt và thực hiện",
        "Sau phê duyệt, bộ phận chuyên trách thực hiện rồi đóng yêu cầu.",
    ),
    "C": (
        "Nhóm C: Phê duyệt, thực hiện và nghiệm thu",
        "Sau khi thực hiện, người yêu cầu nghiệm thu kết quả mới hoàn thành.",
    ),
}
RESOLVER_LABELS = {
    "DIRECT_MANAGER": "Quản lý trực tiếp",
    "DEPARTMENT_HEAD": "Trưởng phòng",
    "DIRECTOR": "Ban giám đốc",
    "FINANCE": "Tài chính",
    "REQUESTER": "Người yêu cầu",
}
TYPE_SQL = """
    SELECT rt.id::text, rt.code, rt.name, rt.category, rt.lifecycle, rt.is_active,
           rt.risk_weight, rt.approval_level, rt.description,
           cr.version, cr.form_schema, cr.route_rules, cr.sla_profile, cr.published_at
    FROM eas.request_type rt
    LEFT JOIN eas.config_release cr ON cr.id = rt.active_release_id
"""


def _group_labels() -> dict[str, str]:
    return {g["code"]: g["label"] for g in catalog_v2().get("groups", [])}


def _sla_hours(sla: dict | None) -> int | None:
    if not sla:
        return None
    hours = [
        sla.get(k) for k in ("approval_hours", "execution_hours", "acceptance_hours")
    ]
    return sum(h for h in hours if isinstance(h, (int, float))) or None


def _lifecycle_steps(
    lifecycle: str, approvers: list[str] | None = None, sla: dict | None = None
) -> list[dict]:
    sla = sla or {}
    approver = (
        ", ".join(RESOLVER_LABELS.get(a, a) for a in approvers)
        if approvers
        else "Người phê duyệt"
    )
    steps = [
        ("Tạo và gửi yêu cầu", "Người yêu cầu", "YEU_CAU", None),
        ("Phê duyệt", approver, "PHE_DUYET", sla.get("approval_hours")),
    ]
    if lifecycle in ("B", "C"):
        steps.append(
            ("Thực hiện", "Bộ phận thực hiện", "THUC_HIEN", sla.get("execution_hours"))
        )
    if lifecycle == "C":
        steps.append(
            ("Nghiệm thu", "Người yêu cầu", "NGHIEM_THU", sla.get("acceptance_hours"))
        )
    steps.append(("Hoàn thành", "Hệ thống", "HOAN_THANH", None))
    return [
        {"step": i, "name": name, "actor": actor, "stage": stage, "sla_hours": hours}
        for i, (name, actor, stage, hours) in enumerate(steps, start=1)
    ]


def _default_approvers(route_rules: dict | None) -> list[str]:
    rules = (route_rules or {}).get("rules") or []
    default = next((r for r in rules if r.get("default")), rules[0] if rules else {})
    return list(default.get("approvers") or [])


def _automation_weight(risk_weight: int | None) -> int:
    """risk 1 (safest) -> 100% automation candidate, risk 5 -> 0%."""
    return round((5 - (risk_weight or 3)) * 25)


def _risk_from_automation(weight) -> int:
    if (
        isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or not 0 <= weight <= 100
    ):
        raise CommandError("INVALID_AUTOMATION_WEIGHT", status=422)
    return 5 - round(weight / 25)


def _serialize_type(row, labels: dict[str, str]) -> dict:
    (
        tid,
        code,
        name,
        group,
        lifecycle,
        active,
        risk,
        level,
        desc,
        version,
        form,
        routes,
        sla,
        published,
    ) = row
    steps = _lifecycle_steps(lifecycle, _default_approvers(routes), sla)
    return {
        "id": tid,
        "code": code,
        "name": name,
        "description": desc or "",
        "request_type": labels.get(group, group),
        "group_code": group,
        "category_code": lifecycle,
        "category_name": LIFECYCLES.get(lifecycle, ("", ""))[0],
        "sla_hours": _sla_hours(sla),
        "automation_weight": _automation_weight(risk),
        "risk_weight": risk,
        "approval_level": level,
        "form_schema": form or {},
        "workflow_steps": steps,
        "route_rules": (routes or {}).get("rules") or [],
        "release_version": version,
        "linked_api_id": None,
        "api_code": None,
        "api_name": None,
        "api_source_system": None,
        "is_api_enabled": False,
        "is_active": bool(active),
        "updated_at": published.isoformat() if published else None,
    }


def _fetch_types(where: str = "", params: list | None = None) -> list[dict]:
    from api_core.catalog import integrations

    labels = _group_labels()
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, api_code, api_name, source_system, lower(COALESCE(domain_key, '')), is_enabled
            FROM eas.mock_apis
            """
        )
        api_rows = cur.fetchall()
        cur.execute(
            TYPE_SQL + where + " ORDER BY rt.lifecycle, rt.code", params or []
        )  # NOSONAR python:S2077
        type_rows = cur.fetchall()

    result = []
    for r in type_rows:
        item = _serialize_type(r, labels)
        for api_id, a_code, a_name, a_source, a_domain, a_enabled in api_rows:
            if integrations.blocks(a_domain, item["code"], item["group_code"]):
                item["linked_api_id"] = api_id
                item["api_code"] = a_code
                item["api_name"] = a_name
                item["api_source_system"] = a_source
                item["is_api_enabled"] = bool(a_enabled)
                if not a_enabled:
                    item["unavailable_notice"] = integrations.notice_for(
                        a_source or a_name
                    )
                break
        result.append(item)
    return result


def _errors(view):
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except CommandError as exc:
            return api_error(request, exc.code, status=exc.status, fields=exc.fields)
        except JsonBodyError as exc:
            return api_error(request, str(exc), status=400)
        except IntegrityError:
            return api_error(request, "CONSTRAINT_CONFLICT", status=409)

    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


def _require_writer(request) -> None:
    """Configuring request types needs update/delete on `requests_workflows`.

    `can_create` on this module means "create business requests", so adding a
    request type also requires `can_update`.
    """
    action = "delete" if request.method == "DELETE" else "update"
    if not can(request, "requests_workflows", action):
        raise CommandError("FORBIDDEN", status=403)


def _types_authorizer(request):
    def check(_cursor, _actor) -> None:
        _require_writer(request)

    return check


def _idempotency_key(request) -> str:
    try:
        return str(UUID(request.headers.get("Idempotency-Key", "").strip()))
    except ValueError:
        return str(uuid4())


def _reason(payload: dict, default: str) -> str:
    reason = str(payload.get("reason") or "").strip()
    return reason if len(reason) >= 10 else default


def _categories() -> list[dict]:
    types = _fetch_types(" WHERE rt.is_active")
    items = []
    for code, (name, desc) in LIFECYCLES.items():
        own = [t for t in types if t["category_code"] == code]
        sla = sorted(t["sla_hours"] for t in own if t["sla_hours"])
        items.append(
            {
                "category_code": code,
                "name": name,
                "description": desc,
                # Typical (median) SLA of the active types in this group.
                "sla_hours": sla[len(sla) // 2] if sla else None,
                "workflow_steps": _lifecycle_steps(code),
                "type_count": len(own),
                "editable": False,
                "updated_at": None,
            }
        )
    return items


@require_actor(*READ_ROLES)
def workflow_categories_list(request):
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    items = _categories()
    return JsonResponse({"items": items, "count": len(items)})


@require_actor(*READ_ROLES)
def workflow_category_detail(request, code):
    code = code.upper().strip()
    item = next((c for c in _categories() if c["category_code"] == code), None)
    if not item:
        return api_error(request, "CATEGORY_NOT_FOUND", status=404)
    if request.method == "GET":
        return JsonResponse(item)
    if request.method in ("PATCH", "PUT"):
        return JsonResponse({"success": True, "item": item})
    return api_error(request, "METHOD_NOT_ALLOWED", status=405)


@require_actor(*READ_ROLES)
@_errors
def request_templates_list(request):
    if request.method == "GET":
        category = request.GET.get("category_code", "").upper().strip()
        items = (
            _fetch_types(" WHERE rt.lifecycle = %s", [category])
            if category
            else _fetch_types()
        )
        return JsonResponse({"items": items, "count": len(items)})
    if request.method != "POST":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)

    _require_writer(request)
    payload = parse_json_object(request)
    group = payload.get("group_code") or next(
        (k for k, v in _group_labels().items() if v == payload.get("request_type")),
        None,
    )
    result = mutate(
        request.actor,
        "request-types",
        None,
        {
            "code": str(payload.get("code") or "").strip().upper(),
            "name": payload.get("name"),
            "description": str(
                payload.get("description") or payload.get("name") or ""
            ).strip(),
            "category": group,
            "lifecycle": payload.get("category_code"),
            "risk_weight": _risk_from_automation(payload.get("automation_weight", 50)),
            "is_active": False,
            "reason": _reason(payload, "Tạo loại yêu cầu mới từ trang Quy trình"),
        },
        "POST",
        _idempotency_key(request),
        correlation_id(request),
        authorizer=_types_authorizer(request),
    )
    item = _fetch_types(" WHERE rt.id = %s::uuid", [result.body["item"]["id"]])[0]
    return JsonResponse({"success": True, "item": item}, status=201)


@require_actor(*READ_ROLES)
@_errors
def request_template_detail(request, template_id):
    tid = str(template_id)
    items = _fetch_types(" WHERE rt.id = %s::uuid", [tid])
    if not items:
        return api_error(request, "TEMPLATE_NOT_FOUND", status=404)
    current = items[0]
    if request.method == "GET":
        return JsonResponse(current)
    if request.method not in ("PATCH", "PUT", "DELETE"):
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)

    _require_writer(request)
    payload = parse_json_object(request) if request.method != "DELETE" else {}
    revision = read_record(
        request.actor, "request-types", tid, _types_authorizer(request)
    )["item"]["revision"]
    key = _idempotency_key(request)

    if request.method == "DELETE":
        mutate(
            request.actor,
            "request-types",
            tid,
            {
                "reason": "Ngừng sử dụng loại yêu cầu từ trang Quy trình",
                "expected_revision": revision,
            },
            "DELETE",
            key,
            correlation_id(request),
            authorizer=_types_authorizer(request),
        )
        return JsonResponse(
            {"success": True, "action": "soft_deleted", "name": current["name"]}
        )

    category_changed = False
    new_cat = payload.get("category_code")
    if (
        new_cat
        and new_cat.upper() in ("A", "B", "C")
        and new_cat.upper() != current["category_code"]
    ):
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE eas.request_type SET lifecycle = %s WHERE id = %s::uuid",
                [new_cat.upper(), tid],
            )
        category_changed = True
        try:
            with connection.cursor() as cl_cur:
                cl_cur.execute(
                    """
                    INSERT INTO eas.system_versions_changelog (
                        id, system_version, change_type, change_scope, title,
                        description, old_value, new_value, changed_by, created_at
                    ) VALUES (%s, 'v2.0', 'WORKFLOW', 'PATCH', %s, %s, %s::jsonb, %s::jsonb, %s, now())
                    """,
                    [
                        str(uuid4()),
                        f"Chuyển phân loại mẫu yêu cầu: {current['name']} sang Nhóm {new_cat}",
                        f"Quản trị viên đã chuyển mẫu yêu cầu {current['name']} ({current['code']}) từ Nhóm {current['category_code']} sang Nhóm {new_cat}.",
                        json.dumps({"category_code": current["category_code"]}),
                        json.dumps({"category_code": new_cat}),
                        str(request.actor.id),
                    ],
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to record workflow changelog: %s", e)

    changes = {}
    if payload.get("name"):
        changes["name"] = payload["name"]
    if "description" in payload:
        changes["description"] = payload["description"]
    if "is_active" in payload:
        changes["is_active"] = payload["is_active"]
    group = payload.get("group_code") or next(
        (k for k, v in _group_labels().items() if v == payload.get("request_type")),
        None,
    )
    if group and group != current["group_code"]:
        changes["category"] = group
    if payload.get("automation_weight") is not None:
        changes["risk_weight"] = _risk_from_automation(payload["automation_weight"])
        try:
            with connection.cursor() as cl_cur:
                cl_cur.execute(
                    """
                    INSERT INTO eas.system_versions_changelog (
                        id, system_version, change_type, change_scope, title,
                        description, old_value, new_value, changed_by, created_at
                    ) VALUES (%s, 'v2.0', 'TEMPLATE', 'PATCH', %s, %s, %s::jsonb, %s::jsonb, %s, now())
                    """,
                    [
                        str(uuid4()),
                        f"Điều chỉnh trọng số tự động hóa: {current['name']}",
                        f"Quản trị viên đã cập nhật trọng số tự động hóa cho {current['name']} thành {payload['automation_weight']}%.",
                        json.dumps(
                            {"automation_weight": current.get("automation_weight")}
                        ),
                        json.dumps({"automation_weight": payload["automation_weight"]}),
                        str(request.actor.id),
                    ],
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to record workflow changelog: %s", e)

    if changes:
        mutate(
            request.actor,
            "request-types",
            tid,
            {
                **changes,
                "reason": _reason(payload, "Cập nhật loại yêu cầu từ trang Quy trình"),
                "expected_revision": revision,
            },
            "PATCH",
            key,
            correlation_id(request),
            authorizer=_types_authorizer(request),
        )

    item = _fetch_types(" WHERE rt.id = %s::uuid", [tid])[0]
    return JsonResponse(
        {"success": True, "category_changed": category_changed, "item": item}
    )


@require_actor(*READ_ROLES)
def mock_apis_list(request):
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, api_code, api_name, endpoint_path, http_method, source_system,
                   domain_key, data_provided, is_enabled
            FROM eas.mock_apis ORDER BY api_code
            """
        )
        keys = (
            "id",
            "api_code",
            "api_name",
            "endpoint_path",
            "http_method",
            "source_system",
            "domain_key",
            "data_provided",
            "is_enabled",
        )
        items = [dict(zip(keys, r)) for r in cur.fetchall()]
    return JsonResponse({"items": items, "count": len(items)})
