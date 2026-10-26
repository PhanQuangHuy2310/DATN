from django.urls import path
from .views import request_types, request_type_forms, plan_request_type_blueprints, colleague_choices
urlpatterns = [
    path("request-types", request_types, name="request-types"),
    path("request-type-forms", request_type_forms, name="request-type-forms"),
    path("colleagues", colleague_choices, name="colleagues"),
    path("plan-request-types", plan_request_type_blueprints, name="plan-request-types"),
]
