from django.urls import path

from .views import access_matrix_view, api_catalog_view, records
from .overview import system_overview

urlpatterns = [
    path("overview", system_overview, name="admin-overview"),
    path("api-catalog", api_catalog_view, name="admin-api-catalog"),
    path("access-matrix", access_matrix_view, name="admin-access-matrix"),
    path("<str:kind>", records),
    path("<str:kind>/<uuid:record_id>", records),
]
