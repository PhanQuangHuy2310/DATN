from __future__ import annotations

import contextlib
import sys
from uuid import UUID, uuid4

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api_core.workflow.service import _append_admin_audit


class Command(BaseCommand):
    help = "Execute or inspect data privacy rights and erasure cases with legal hold protection."

    def add_arguments(self, parser):
        parser.add_argument("--case", required=True, help="Privacy case UUID.")
        parser.add_argument(
            "--action",
            required=True,
            choices=("dry-run", "approve", "reject", "execute-erase"),
            help="Privacy case action.",
        )
        parser.add_argument(
            "--approval", required=True, help="Legal/compliance approval reference."
        )

    def handle(self, *args, **options):
        case_id = options["case"].strip()
        try:
            norm_case_id = str(UUID(case_id))
        except ValueError:
            self.stderr.write(f"ERROR: Invalid case UUID: {case_id}")
            sys.exit(2)

        action = options["action"]
        approval = options["approval"].strip()

        if not approval:
            self.stderr.write("ERROR: --approval reference must be non-empty.")
            sys.exit(2)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id::text, p.subject_user_id::text, p.case_type, p.status,
                       u.username, u.email
                FROM eas.privacy_case p
                JOIN eas.app_user u ON u.id = p.subject_user_id
                WHERE p.id = %s
                """,
                [norm_case_id],
            )
            row = cursor.fetchone()
            if not row:
                self.stderr.write(f"ERROR: Privacy case '{norm_case_id}' not found.")
                sys.exit(2)

            p_id, subject_user_id, case_type, current_status, username, _email = row

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM eas.retention_hold h
                JOIN eas.request r ON r.id = h.request_id
                WHERE r.requester_id = %s AND h.released_at IS NULL
                """,
                [subject_user_id],
            )
            hold_count = cursor.fetchone()[0]

        if action == "dry-run":
            self.stdout.write(f"Privacy Case: {p_id}")
            self.stdout.write(f"Subject User: {username} ({subject_user_id})")
            self.stdout.write(f"Case Type: {case_type}")
            self.stdout.write(f"Current Status: {current_status}")
            self.stdout.write(f"Active Retention Holds: {hold_count}")
            if hold_count > 0:
                self.stdout.write(
                    "WARNING: Erasure will be blocked by active legal retention holds."
                )
            else:
                self.stdout.write("Status: Eligible for processing.")
            sys.exit(0)

        elif action == "approve":
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE eas.privacy_case
                    SET status = 'APPROVED', decision_reference = %s
                    WHERE id = %s
                    """,
                    [approval, norm_case_id],
                )
            self.stdout.write(
                f"Privacy case '{norm_case_id}' approved with reference '{approval}'."
            )
            sys.exit(0)

        elif action == "reject":
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE eas.privacy_case
                    SET status = 'REJECTED', decision_reference = %s, completed_at = statement_timestamp()
                    WHERE id = %s
                    """,
                    [approval, norm_case_id],
                )
            self.stdout.write(
                f"Privacy case '{norm_case_id}' rejected with reference '{approval}'."
            )
            sys.exit(0)

        elif action == "execute-erase":
            if hold_count > 0:
                self.stderr.write(
                    "BLOCKED_BY_HOLD: Active legal retention hold blocks erasure."
                )
                sys.exit(2)

            if current_status != "APPROVED":
                self.stderr.write(
                    f"ERROR: Case must be in APPROVED state to execute erasure (current: {current_status})."
                )
                sys.exit(2)

            if case_type != "ERASE":
                self.stderr.write(
                    f"ERROR: Only ERASE cases can execute erasure (current: {case_type})."
                )
                sys.exit(2)

            correlation_id = str(uuid4())

            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SELECT eas.lock_security(true)")

                cursor.execute(
                    """
                    UPDATE eas.app_user
                    SET display_name = 'REDACTED',
                        is_active = FALSE,
                        password_hash = '!PRIVACY_ERASED',
                        email = %s,
                        auth_version = auth_version + 1
                    WHERE id = %s
                    """,
                    [f"erased_{subject_user_id[:8]}@privacy.local", subject_user_id],
                )

                cursor.execute(
                    """
                    UPDATE eas.privacy_case
                    SET status = 'DONE',
                        completed_at = statement_timestamp()
                    WHERE id = %s
                    """,
                    [norm_case_id],
                )

                cursor.execute(
                    "UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1"
                )

                _append_admin_audit(
                    cursor,
                    actor_id=None,
                    actor_kind="SYSTEM",
                    action="PRIVACY_ERASE_EXECUTED",
                    target_type="privacy_case",
                    target_id=norm_case_id,
                    reason=approval,
                    details={
                        "subject_user_id": subject_user_id,
                        "case_id": norm_case_id,
                        "decision_reference": approval,
                    },
                    correlation_id=correlation_id,
                )

            with contextlib.suppress(Exception):
                cache.delete(f"eas:session:{subject_user_id}")

            self.stdout.write(f"Privacy erasure executed for case '{norm_case_id}'.")
            sys.exit(0)
