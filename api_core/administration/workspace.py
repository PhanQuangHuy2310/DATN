"""Employee portal APIs (/api/v1/workspace/*), opened by module rights.

Each route reuses the administration view logic; instead of an admin role it
requires the module right the administrator granted in the permission matrix
(view for GET, create/update/delete for writes). Writes are re-checked inside
the shared views, so both portals enforce exactly the same rules.
"""

from __future__ import annotations

from django.db import connection
from django.http import JsonResponse
from django.urls import path

from api_core.authn.module_access import can, require_module
from api_core.authn.service import require_actor
from api_core.catalog import integrations
from api_core.http import api_error
from api_core.read_cache import cached

from . import analytics, org_users_rbac, regulations_ai, workflows


def _employee(view, module: str, actions: dict[str, str] | None = None):
    inner = getattr(view, "__wrapped__", view)
    return require_actor()(require_module(module, actions)(inner))


@require_actor()
def departments_view(request):
    """Active departments for pickers (people with users or org chart access)."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    if not (can(request, "users") or can(request, "org_chart")):
        return api_error(request, "MODULE_FORBIDDEN", status=403)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id::text, code, name, parent_id::text FROM eas.department WHERE is_active ORDER BY code"
        )
        keys = ("id", "code", "name", "parent_id")
        items = [dict(zip(keys, r)) for r in cur.fetchall()]
    return JsonResponse({"items": items, "count": len(items)})


@require_actor()
@require_module("requests_workflows")
def request_catalog_view(request):
    """Active request types with linked integrations and availability."""
    if request.method != "GET":
        return api_error(request, "METHOD_NOT_ALLOWED", status=405)
    items = cached("request-catalog", _catalog_items)
    return JsonResponse(
        {
            "items": items,
            "count": len(items),
            "can_configure": can(request, "requests_workflows", "update")
            or can(request, "requests_workflows", "delete"),
        }
    )


def _catalog_items() -> list[dict]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT api_code, api_name, COALESCE(source_system, api_name), lower(COALESCE(domain_key, '')), is_enabled "
            "FROM eas.mock_apis ORDER BY api_code"
        )
        apis = cur.fetchall()
    items = []
    for item in workflows._fetch_types(" WHERE rt.is_active"):
        linked = [
            {
                "api_code": code,
                "api_name": name,
                "source_system": source,
                "is_enabled": bool(enabled),
            }
            for code, name, source, domain, enabled in apis
            if integrations.blocks(domain, item["code"], item["group_code"])
        ]
        down = next((a for a in linked if not a["is_enabled"]), None)
        items.append(
            {
                **item,
                "linked_apis": linked,
                "is_api_enabled": down is None,
                "unavailable_notice": (
                    f"Yêu cầu này hiện không thể sử dụng do kết nối API của hệ thống "
                    f"[{down['source_system']}] đang bị tắt."
                    if down
                    else None
                ),
            }
        )
    return items


_requests_detail = getattr(
    org_users_rbac.user_requests_detail_view,
    "__wrapped__",
    org_users_rbac.user_requests_detail_view,
)


@require_actor()
@require_module("requests_workflows")
def my_requests_view(request):
    """Requests the current user takes part in, grouped into the 5 stages."""
    return _requests_detail(request, request.actor.id)


# Users: PATCH/DELETE pick update vs delete inside the shared view.
USERS_DETAIL_ACTIONS = {"PATCH": "view", "PUT": "view", "DELETE": "view"}
# For request types, POST configures a new type (needs update, not create).
TYPES_ACTIONS = {"POST": "update"}

urlpatterns = [
    path("analytics", _employee(analytics.admin_analytics_view, "dashboard")),
    path("org-chart-tree", _employee(org_users_rbac.org_chart_tree_view, "org_chart")),
    path("departments", departments_view),
    path("rbac/roles", _employee(org_users_rbac.rbac_roles_list, "users")),
    path("users-management", _employee(org_users_rbac.users_management_list, "users")),
    path(
        "users-management/<uuid:user_id>",
        _employee(org_users_rbac.user_management_detail, "users", USERS_DETAIL_ACTIONS),
    ),
    path(
        "users-management/<uuid:user_id>/requests-detail",
        _employee(org_users_rbac.user_requests_detail_view, "users"),
    ),
    path(
        "users-management/<uuid:user_id>/leave-trip",
        _employee(org_users_rbac.user_leave_trip_manage, "users", {"POST": "update"}),
    ),
    path(
        "regulations", _employee(regulations_ai.regulations_list_create, "regulations")
    ),
    path(
        "regulations/<uuid:reg_id>",
        _employee(regulations_ai.regulation_detail_update_delete, "regulations"),
    ),
    path("request-catalog", request_catalog_view),
    path("my-requests", my_requests_view),
    path(
        "request-templates",
        _employee(
            workflows.request_templates_list, "requests_workflows", TYPES_ACTIONS
        ),
    ),
    path(
        "request-templates/<uuid:template_id>",
        _employee(workflows.request_template_detail, "requests_workflows"),
    ),
    path(
        "workflow-categories",
        _employee(workflows.workflow_categories_list, "requests_workflows"),
    ),
    path(
        "workflow-categories/<str:code>",
        _employee(workflows.workflow_category_detail, "requests_workflows"),
    ),
    path("mock-apis", _employee(workflows.mock_apis_list, "requests_workflows")),
]
