from django.http import HttpResponse
from django.urls import include, path

from api_core.administration.apis_and_versions import public_circuit_breaker_status
from api_core.administration.regulations_ai import public_ai_status_view
from api_core.authn import views as authn_views
from api_core.catalog import views as catalog_views
from api_core.health import views as health_views

urlpatterns = [
    path("", health_views.live, name="root-live"),
    path("favicon.ico", lambda _: HttpResponse(status=204), name="favicon"),
    path("api/v1/admin/", include("api_core.administration.urls")),
    path("health/", include("api_core.health.urls")),
    path("api/v1/system/ai-status", public_ai_status_view, name="public-ai-status"),
    path(
        "api/v1/system/api-circuit-breaker-status",
        public_circuit_breaker_status,
        name="public-api-circuit-breaker-status",
    ),
    path("api/v1/auth/", include("api_core.authn.urls")),
    path("api/v1/me", authn_views.me, name="me-alias"),
    path(
        "api/v1/permissions/me", authn_views.permissions_me, name="permissions-me-alias"
    ),
    path(
        "api/v1/request-types", catalog_views.request_types, name="request-types-alias"
    ),
    path("api/v1/", include("api_core.workflow.urls")),
    path("api/v1/meta/", include("api_core.catalog.urls")),
    path("api/v1/mock/", include("api_core.mock_sources.urls")),
]


def custom_404(request, exception=None):
    from api_core.http import api_error

    return api_error(request, "RESOURCE_NOT_FOUND", status=404)


def custom_500(request):
    from api_core.http import api_error

    return api_error(request, "INTERNAL_SERVER_ERROR", status=500)


handler404 = "api_core.config.urls.custom_404"
handler500 = "api_core.config.urls.custom_500"
