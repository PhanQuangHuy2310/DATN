from django.urls import include, path

from api_core.authn import views as authn_views
from api_core.catalog import views as catalog_views

urlpatterns = [
    path("health/", include("api_core.health.urls")),
    path("api/v1/auth/", include("api_core.authn.urls")),
    path("api/v1/me", authn_views.me, name="me-alias"),
    path(
        "api/v1/request-types", catalog_views.request_types, name="request-types-alias"
    ),
    path("api/v1/", include("api_core.workflow.urls")),
    path("api/v1/meta/", include("api_core.catalog.urls")),
    path("api/v1/mock/", include("api_core.mock_sources.urls")),
]
