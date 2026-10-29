from django.urls import path

from .views import access_matrix_view, api_catalog_view, records

urlpatterns = [
    path("api-catalog", api_catalog_view, name="admin-api-catalog"),
    path("access-matrix", access_matrix_view, name="admin-access-matrix"),
    path("<str:kind>", records),
    path("<str:kind>/<uuid:record_id>", records),
]
