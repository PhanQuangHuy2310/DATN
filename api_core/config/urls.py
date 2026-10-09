from django.urls import include, path

urlpatterns = [
    path("health/", include("api_core.health.urls")),
    path("api/v1/auth/", include("api_core.authn.urls")),
    path("api/v1/", include("api_core.workflow.urls")),
    path("api/v1/meta/", include("api_core.catalog.urls")),
    path("api/v1/mock/", include("api_core.mock_sources.urls")),
]
