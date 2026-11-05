from django.urls import path

from .views import database_connection, live, ready

urlpatterns = [
    path("live", live, name="health-live"),
    path("db", database_connection, name="health-db"),
    path("ready", ready, name="health-ready"),
]
