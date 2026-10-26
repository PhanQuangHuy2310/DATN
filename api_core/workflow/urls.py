from django.urls import path

from . import history_views, views

urlpatterns = [
    path("requests/<uuid:request_id>/history", history_views.history),
    path(
        "request-drafts/<uuid:request_id>/attachments/<uuid:attachment_id>",
        history_views.remove_draft_attachment,
    ),
    # Draft & Submit
    path("request-drafts", views.draft, name="request-draft-create"),
    path("requests", views.request_list_or_create, name="request-list"),
    path("requests/submit", views.submit, name="request-submit"),
    path(
        "requests/<uuid:request_id>/submit", views.submit, name="request-submit-with-id"
    ),
    path(
        "requests/<uuid:request_id>",
        views.request_detail_or_patch,
        name="request-detail",
    ),
    path(
        "request-drafts/<uuid:request_id>",
        views.update_draft_view,
        name="request-draft-update",
    ),
    # Revisions
    path(
        "requests/<uuid:request_id>/revisions",
        views.revisions_list,
        name="request-revisions-list",
    ),
    path(
        "requests/<uuid:request_id>/revisions/<uuid:revision_id>",
        views.revision_detail,
        name="request-revision-detail",
    ),
    # Attachments
    path(
        "request-drafts/<uuid:request_id>/attachments",
        views.attachment,
        name="request-attachment-upload",
    ),
    path(
        "requests/<uuid:request_id>/attachments",
        views.attachment,
        name="request-attachment-upload-alias",
    ),
    path(
        "requests/<uuid:request_id>/execution/attachments",
        views.execution_attachment,
        name="execution-attachment-upload",
    ),
    path(
        "attachments/<uuid:attachment_id>",
        views.attachment_metadata,
        name="attachment-metadata",
    ),
    path(
        "attachments/<uuid:attachment_id>/download",
        views.attachment_download,
        name="attachment-download",
    ),
    # Decisions & Cancellation
    path(
        "requests/<uuid:request_id>/approval-decisions",
        views.approval_decision,
        name="approval-decision",
    ),
    path(
        "requests/<uuid:request_id>/decisions",
        views.approval_decision,
        name="approval-decision-alias",
    ),
    path(
        "requests/<uuid:request_id>/cancel", views.cancellation, name="request-cancel"
    ),
    path(
        "requests/<uuid:request_id>/withdraw",
        views.cancellation,
        name="request-withdraw-alias",
    ),
    # Execution & Acceptance
    path(
        "requests/<uuid:request_id>/execution/start",
        views.execution_start,
        name="execution-start",
    ),
    path(
        "requests/<uuid:request_id>/claim",
        views.execution_start,
        name="execution-claim-alias",
    ),
    path(
        "requests/<uuid:request_id>/execution/submit",
        views.execution_submit,
        name="execution-submit",
    ),
    path(
        "requests/<uuid:request_id>/execution",
        views.execution_submit,
        name="execution-submit-alias",
    ),
    path(
        "requests/<uuid:request_id>/issues",
        views.report_issue_view,
        name="request-issue",
    ),
    path(
        "requests/<uuid:request_id>/execution/issues",
        views.report_issue_view,
        name="execution-issue-alias",
    ),
    path(
        "requests/<uuid:request_id>/acceptance-decisions",
        views.acceptance_decision,
        name="acceptance-decision",
    ),
    path(
        "requests/<uuid:request_id>/acceptance",
        views.acceptance_decision,
        name="acceptance-decision-alias",
    ),
    # OPS Admin
    path("ops/requests", views.ops_requests_view, name="ops-requests"),
    path(
        "requests/<uuid:request_id>/reassign",
        views.reassign_view,
        name="request-reassign",
    ),
    path(
        "ops/outbox/<uuid:event_id>/replay",
        views.outbox_replay_view,
        name="ops-outbox-replay",
    ),
    # Policy & Config Release
    path("config-releases", views.config_releases_view, name="config-releases"),
    path(
        "config-releases/<uuid:release_id>",
        views.config_release_detail_view,
        name="config-release-detail",
    ),
    path(
        "config-releases/<uuid:release_id>/validate",
        views.config_release_validate_view,
        name="config-release-validate",
    ),
    path(
        "config-releases/<uuid:release_id>/publish",
        views.config_release_publish_view,
        name="config-release-publish",
    ),
    # Notifications, Reports & Audit
    path("notifications", views.notifications_view, name="notifications-list"),
    path(
        "notifications/<uuid:notification_id>",
        views.notification_mark_read_view,
        name="notification-mark-read",
    ),
    path(
        "notifications/<uuid:notification_id>/read",
        views.notification_mark_read_view,
        name="notification-mark-read-alias",
    ),
    path("reports/requests", views.reports_requests_view, name="reports-requests"),
    path(
        "requests/<uuid:request_id>/audit",
        views.request_audit_view,
        name="request-audit",
    ),
    path(
        "requests/<uuid:request_id>/audit/verify",
        views.request_audit_verify_view,
        name="request-audit-verify",
    ),
    path("admin-events", views.admin_events_view, name="admin-events"),
    # System Maintenance
    path(
        "system/maintenance",
        views.system_maintenance_view,
        name="system-maintenance",
    ),
    path(
        "system/maintenance/start",
        views.system_maintenance_start_view,
        name="system-maintenance-start",
    ),
    path(
        "system/maintenance/complete",
        views.system_maintenance_complete_view,
        name="system-maintenance-complete",
    ),
    # AI Assistance Proxy
    path("ai/classify", views.ai_classify_view, name="ai-classify"),
    path("ai/risk-score", views.ai_risk_score_view, name="ai-risk-score"),
    path("ai/summarize", views.ai_summarize_view, name="ai-summarize"),
]
