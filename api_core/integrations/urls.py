from django.urls import path

from .views import form_options

urlpatterns = [path("options", form_options)]
