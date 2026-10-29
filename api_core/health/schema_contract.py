"""Runtime EAS schema contract.

Do not use ``count(*) = 30`` as a readiness requirement. PostgreSQL has
supporting lookup tables and future additive schema changes may introduce
more tables. The required 30 workflow tables must all exist by name.
"""

REQUIRED_EAS_TABLES = frozenset(
    (
        "security_epoch",
        "department",
        "app_user",
        "request_type",
        "role_membership",
        "config_release",
        "request",
        "request_revision",
        "workflow_instance",
        "request_participant",
        "approval_step",
        "approval_decision",
        "execution_attempt",
        "acceptance_decision",
        "execution_issue",
        "attachment",
        "draft_attachment",
        "revision_attachment",
        "execution_attachment",
        "sla_stage",
        "sla_alert",
        "audit_head",
        "audit_event",
        "admin_event",
        "audit_checkpoint",
        "outbox_event",
        "notification",
        "idempotency_record",
        "privacy_case",
        "retention_hold",
    )
)


def has_required_eas_tables(present_names):
    """Return True when every required table is present; extra tables are valid."""
    return REQUIRED_EAS_TABLES.issubset(set(present_names))


def missing_required_eas_tables(present_names):
    return sorted(REQUIRED_EAS_TABLES - set(present_names))
