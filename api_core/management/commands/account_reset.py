from __future__ import annotations

import contextlib
import os
import sys
from uuid import uuid4

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api_core.workflow.service import _append_admin_audit


class Command(BaseCommand):
    help = "Audited administrative user account lifecycle management (disable, enable, reset-password)."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="Target username.")
        parser.add_argument(
            "--mode",
            required=True,
            choices=("disable", "enable", "reset-password"),
            help="Operation mode.",
        )
        parser.add_argument(
            "--operator", required=True, help="Operator username or UUID."
        )
        parser.add_argument(
            "--approval", required=True, help="Change approval reference/ticket."
        )

    def handle(self, *args, **options):
        username = options["user"].strip()
        mode = options["mode"]
        operator = options["operator"].strip()
        approval = options["approval"].strip()

        if not username or not operator or not approval:
            self.stderr.write(
                "ERROR: --user, --operator, and --approval must be non-empty."
            )
            sys.exit(2)

        temp_password = None
        if mode == "reset-password":
            temp_password = os.getenv("EAS_TEMP_PASSWORD", "")
            if len(temp_password) < 12:
                self.stderr.write(
                    "ERROR: EAS_TEMP_PASSWORD environment variable must have at least 12 characters."
                )
                sys.exit(2)

        correlation_id = str(uuid4())

        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(true)")

            cursor.execute(
                """
                SELECT id::text, department_id::text, is_active, auth_version
                FROM eas.app_user
                WHERE username = %s
                FOR UPDATE
                """,
                [username],
            )
            row = cursor.fetchone()
            if not row:
                self.stderr.write(f"ERROR: User '{username}' not found.")
                sys.exit(2)

            user_id, dept_id, _is_active, auth_version = row
            new_auth_version = auth_version + 1

            cursor.execute(
                "SELECT id::text FROM eas.app_user WHERE username = %s OR id::text = %s",
                [operator, operator],
            )
            op_row = cursor.fetchone()
            operator_id = op_row[0] if op_row else None

            if mode == "disable":
                cursor.execute(
                    """
                    UPDATE eas.app_user
                    SET is_active = FALSE, auth_version = %s
                    WHERE id = %s
                    """,
                    [new_auth_version, user_id],
                )
                action = "ACCOUNT_DISABLED"
            elif mode == "enable":
                cursor.execute(
                    """
                    UPDATE eas.app_user
                    SET is_active = TRUE, auth_version = %s
                    WHERE id = %s
                    """,
                    [new_auth_version, user_id],
                )
                action = "ACCOUNT_ENABLED"
            else:  # reset-password
                new_hash = make_password(temp_password, hasher="argon2")
                cursor.execute(
                    """
                    UPDATE eas.app_user
                    SET password_hash = %s,
                        auth_version = %s,
                        must_change_password = TRUE
                    WHERE id = %s
                    """,
                    [new_hash, new_auth_version, user_id],
                )
                action = "ACCOUNT_RESET_PASSWORD"

            cursor.execute(
                "UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1"
            )

            _append_admin_audit(
                cursor,
                actor_id=operator_id,
                action=action,
                target_type="app_user",
                target_id=user_id,
                department_id=dept_id,
                reason=approval,
                details={
                    "username": username,
                    "mode": mode,
                    "auth_version": new_auth_version,
                },
                correlation_id=correlation_id,
            )

        with contextlib.suppress(Exception):
            cache.delete(f"eas:session:{user_id}")

        self.stdout.write(f"User '{username}' successfully updated with mode '{mode}'.")
        sys.exit(0)
