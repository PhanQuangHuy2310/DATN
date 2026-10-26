from django.urls import path
from .views import request_types, request_type_forms
urlpatterns = [
    path("request-types", request_types, name="request-types"),
    path("request-type-forms", request_type_forms, name="request-type-forms"),
]
