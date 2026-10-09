from django.urls import path

from . import views

urlpatterns = [
    path("request-drafts", views.draft, name="request-draft-create"),
    path("requests", views.request_list, name="request-list"),
    path("requests/submit", views.submit, name="request-submit"),
    path("requests/<uuid:request_id>", views.request_detail, name="request-detail"),
    path(
        "requests/<uuid:request_id>/cancel",
        views.cancellation,
        name="request-cancel",
    ),
    path(
        "request-drafts/<uuid:request_id>/attachments",
        views.attachment,
        name="request-attachment-upload",
    ),
    path(
        "requests/<uuid:request_id>/approval-decisions",
        views.approval_decision,
        name="approval-decision",
    ),
    path(
        "requests/<uuid:request_id>/execution/start",
        views.execution_start,
        name="execution-start",
    ),
    path(
        "requests/<uuid:request_id>/execution/submit",
        views.execution_submit,
        name="execution-submit",
    ),
    path(
        "requests/<uuid:request_id>/execution/attachments",
        views.execution_attachment,
        name="execution-attachment-upload",
    ),
    path(
        "requests/<uuid:request_id>/acceptance-decisions",
        views.acceptance_decision,
        name="acceptance-decision",
    ),
]
