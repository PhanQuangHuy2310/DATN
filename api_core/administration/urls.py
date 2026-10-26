from django.urls import path

from .views import records

urlpatterns = [
    path("<str:kind>", records),
    path("<str:kind>/<uuid:record_id>", records),
]
