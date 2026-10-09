from django.urls import path

from .views import request_types

urlpatterns = [path("request-types", request_types, name="request-types")]
