"""Read-only request catalogue sourced from published, scoped policy releases.

The request form is *not* a security boundary: create/submit still rechecks
role membership, request type, published release and state under DB locks.
"""
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from api_core.authn.service import require_actor


@require_GET
def request_types(request):
    """Public list of active type codes; does not reveal policy internals."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT rt.code, rt.lifecycle,
              (cr.id IS NOT NULL AND cr.state = 'PUBLISHED'
               AND cr.type_id = rt.id AND cr.lifecycle = rt.lifecycle) AS configured
            FROM eas.request_type rt
            LEFT JOIN eas.config_release cr ON cr.id=rt.active_release_id
            WHERE rt.is_active ORDER BY rt.code
        """)
        items = [{"code": code, "lifecycle": lifecycle, "configured": configured}
                 for code, lifecycle, configured in cursor.fetchall()]
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
            SELECT rt.code, rt.lifecycle, cr.id::text, cr.form_schema
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
        items = [{"code":code, "lifecycle":lifecycle, "release_id":release_id,
                  "form_schema":form_schema}
                 for code,lifecycle,release_id,form_schema in cursor.fetchall()]
    return JsonResponse({"items": items})
