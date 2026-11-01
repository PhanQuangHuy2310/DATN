from django.urls import path

from . import views

urlpatterns = [
    path("csrf", views.csrf, name="auth-csrf"),
    path("login", views.login, name="auth-login"),
    path("logout", views.logout, name="auth-logout"),
    path("me", views.me, name="auth-me"),
    path("password", views.password, name="auth-password"),
    path("change-password", views.password, name="auth-change-password"),
    path(
        "password-reset/request",
        views.password_reset_request,
        name="password-reset-request",
    ),
    path(
        "password-reset/requests",
        views.password_reset_requests,
        name="password-reset-requests",
    ),
    path(
        "password-reset/requests/<uuid:request_id>/approve",
        views.password_reset_approve,
        name="password-reset-approve",
    ),
]
