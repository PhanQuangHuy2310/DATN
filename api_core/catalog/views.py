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
from api_core.catalog.plan_catalog import plan_items, plan_item, safe_display_name
from api_core.catalog.availability import request_option_blocker

@lru_cache(maxsize=1)
def approval_menu_blueprint():
    """The 20 display rows supplied by the plan, mapped to 18 distinct codes."""
    data = json.loads(Path(__file__).with_name("approval_menu.json").read_text(encoding="utf-8"))
    if (data.get("display_rows") != 20 or data.get("unique_types") != 18
        or len(data["options"]) != 20 or len({row["code"] for row in data["options"]}) != 18):
        raise RuntimeError("INVALID_APPROVAL_MENU")
    return data


def approval_type_name(code):
    matched = next((item for item in approval_menu_blueprint()["types"] if item["code"] == code), None)
    return (matched or plan_item(code) or {}).get("name", code)


@require_GET
def request_types(request):
    """Public list of active type codes; does not reveal policy internals."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT rt.code, rt.lifecycle, rt.name, rt.description, rt.category,
              (cr.id IS NOT NULL AND cr.state = 'PUBLISHED'
               AND cr.type_id = rt.id AND cr.lifecycle = rt.lifecycle) AS configured
            FROM eas.request_type rt
            LEFT JOIN eas.config_release cr ON cr.id=rt.active_release_id
            WHERE rt.is_active ORDER BY rt.code
        """)
        items = [{"code": code, "name": name.strip() or approval_type_name(code),
                  "description": description, "category": category, "lifecycle": lifecycle,
                  "configured": configured}
                 for code, lifecycle, name, description, category, configured in cursor.fetchall()]
    return JsonResponse({"items": items})


@require_GET
@require_actor("REQUESTER")
def request_type_forms(request):
    """Configured templates visible to a requester inside their effective scope.

    A published schema can be used to render a form; write services re-check all
    authorizations. Never expose actor_bindings, route_rules or secrets here.
    """
    actor = request.actor
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT rt.code, rt.lifecycle, cr.id::text, cr.form_schema,
                   rt.name, rt.description, rt.category
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
        """, [actor.id, actor.department_id])
        items = [{"code":code, "name":name.strip() or approval_type_name(code),
                  "description":description, "category":category,
                  "lifecycle":lifecycle, "release_id":release_id,
                  "form_schema":form_schema, "field_labels":(plan_item(code) or next((x for x in approval_menu_blueprint()["types"] if x["code"]==code), {})).get("field_labels", {}),
                  "department_id":actor.department_id}
                 for code,lifecycle,release_id,form_schema,name,description,category in cursor.fetchall()]
    # Distinguish real publication blockers from scoped REQUESTER permission
    # without returning private policy JSON, memberships or assignee identities.
    with connection.cursor() as cursor:
        cursor.execute("""
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
        """, [actor.id, actor.department_id])
        states = {code: (lc, active, published, scoped) for code, lc, active, published, scoped in cursor.fetchall()}

    available = {item["code"]: item for item in items}
    menu = []
    for row in approval_menu_blueprint()["options"]:
        code = row["code"]
        state = states.get(code)
        match = available.get(code)
        valid = bool(match and match["lifecycle"] == row["lifecycle"])
        blocker, reason = request_option_blocker(state, row["lifecycle"])
        menu.append({**row, "available": valid, "blocker_code": blocker if not valid else None,
                     "disabled_reason": reason if not valid else None})
    for item in items:
        if not any(row["code"] == item["code"] for row in menu):
            menu.append({"group": "Biểu mẫu hệ thống đang hoạt động", "label": item["name"],
                         "code": item["code"], "lifecycle": item["lifecycle"],
                         "risk_weight": None, "description": "Theo cấu hình hiện hành",
                         "available": True, "blocker_code": None, "disabled_reason": None})
    return JsonResponse({"items": items, "approval_menu": menu,
                         "request_code_generated_by_server": True})

@require_GET
@require_actor("POLICY_ADMIN", "OPS_ADMIN")
def plan_request_type_blueprints(request):
    """Read-only plan blueprints, not request types enabled for submission.

    Membership scope + SoD are independently rechecked by write services.
    """
    return JsonResponse({"source":"plan.docx", "count":len(plan_items()),
                         "deployment_state":"BLUEPRINT_ONLY", "items":plan_items(),
                         "approval_menu": approval_menu_blueprint()})

@require_GET
@require_actor("REQUESTER")
def colleague_choices(request):
    """For form UUID references: only active coworkers from the requester's department.

    No email, password, role grants or cross-department information is returned.
    This is only a convenience list, NOT authorization for approval assignment.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id::text, display_name FROM eas.app_user
            WHERE is_active AND department_id=%s AND id<>%s
            ORDER BY display_name, id LIMIT 300
        """, [request.actor.department_id, request.actor.id])
        choices = [{"id": x, "display_name": y} for x,y in cursor.fetchall()]
    return JsonResponse({"items": choices})
