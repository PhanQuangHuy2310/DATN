from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def request_types(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT code, lifecycle, active_release_id IS NOT NULL AS configured
            FROM eas.request_type
            WHERE is_active
            ORDER BY code
            """
        )
        items = [
            {"code": code, "lifecycle": lifecycle, "configured": configured}
            for code, lifecycle, configured in cursor.fetchall()
        ]
    return JsonResponse({"items": items})
