"""Module permissions (Xem/Thêm/Sửa/Xoá) granted by the administrator.

Employees reach a feature only through the module rights the admin grants in
the permission matrix (eas.role_module_permission + eas.user_permissions).
Admin accounts (OPS_ADMIN/POLICY_ADMIN) keep full access. Four system modules
are never available to employees, whatever the matrix says.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponse

from api_core.http import api_error

ADMIN_ROLES = frozenset({"OPS_ADMIN", "POLICY_ADMIN"})
# Configuration/system modules stay with the administrator only.
NEVER_FOR_EMPLOYEES = frozenset(
    {"permissions", "ai_engine", "api_management", "system_versions"}
)
ACTION_BY_METHOD = {
    "GET": "view",
    "HEAD": "view",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


def module_rights(request: HttpRequest) -> dict[str, dict[str, bool]]:
    """Effective rights of request.actor, loaded once per request."""
    cached = getattr(request, "_module_rights", None)
    if cached is None:
        from api_core.authn.views import _get_actor_permissions

        cached = _get_actor_permissions(request.actor).get("by_module", {})
        request._module_rights = cached
    return cached


def can(request: HttpRequest, module: str, action: str = "view") -> bool:
    actor = request.actor
    if actor.roles & ADMIN_ROLES:
        return True
    if module in NEVER_FOR_EMPLOYEES:
        return False
    return bool((module_rights(request).get(module) or {}).get(f"can_{action}"))


def require_module(module: str, actions: dict[str, str] | None = None) -> Callable:
    """Use under @require_actor(): 403 unless the actor holds the module right.

    `actions` overrides the method → action map (e.g. {"POST": "update"} when a
    POST configures something instead of creating a business record).
    """
    mapping = {**ACTION_BY_METHOD, **(actions or {})}

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            action = mapping.get(request.method, "view")
            if not can(request, module, action):
                return api_error(request, "MODULE_FORBIDDEN", status=403)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
