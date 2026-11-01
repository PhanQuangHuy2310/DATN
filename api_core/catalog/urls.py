from django.urls import path

from .views import (
    colleague_choices,
    plan_request_type_blueprints,
    request_type_forms,
    request_types,
)

urlpatterns = [
    path("request-types", request_types, name="request-types"),
    path("request-type-forms", request_type_forms, name="request-type-forms"),
    path("colleagues", colleague_choices, name="colleagues"),
    path("plan-request-types", plan_request_type_blueprints, name="plan-request-types"),
]
