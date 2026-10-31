"""Administrative command to enforce mandatory password rotation across accounts.

Required before commercial delivery or pilot deployment (ISO 27001 A.9.4.3 & SOC 2 CC6.1).
Sets must_change_password=True and increments auth_version so any active sessions are revoked.
"""

from __future__ import annotations

import contextlib
import sys
from uuid import uuid4

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api_core.workflow.service import _append_admin_audit


class Command(BaseCommand):
    help = (
        "Enforce mandatory password reset across seeded/existing accounts "
        "before commercial go-live (ISO 27001 / SOC 2)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--operator",
            required=True,
            help="Operator username or UUID authoring this compliance operation.",
        )
        parser.add_argument(
            "--approval",
            required=True,
            help="Change approval reference / ticket (e.g. CHG-GO-LIVE-HARDENING).",
        )
        parser.add_argument(
            "--exclude",
            default="admin",
            help="Comma-separated usernames to exclude (default: 'admin').",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report affected accounts without applying changes.",
        )

    def handle(self, *args, **options):
        operator = options["operator"].strip()
        approval = options["approval"].strip()
        exclude_list = [
            u.strip().casefold() for u in options["exclude"].split(",") if u.strip()
        ]
        dry_run = options["dry_run"]

        if not operator or not approval:
            self.stderr.write("ERROR: --operator and --approval must be non-empty.")
            sys.exit(2)

        correlation_id = str(uuid4())

        with transaction.atomic(), connection.cursor() as cursor:
            # If in postgres, acquire exclusive lock
            if connection.vendor == "postgresql":
                cursor.execute("SELECT eas.lock_security(true)")

            cursor.execute(
                """
                SELECT id::text, username, department_id::text, auth_version
                FROM eas.app_user
                WHERE is_active = TRUE AND must_change_password = FALSE
                """
            )
            rows = cursor.fetchall()
            candidates = [r for r in rows if r[1].casefold() not in exclude_list]

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] Found {len(candidates)} active accounts requiring password rotation."
                )
                for r in candidates:
                    self.stdout.write(f"  - {r[1]} (id: {r[0]})")
                sys.exit(0)

            if not candidates:
                self.stdout.write(
                    "All active accounts already require password change or were excluded."
                )
                sys.exit(0)

            cursor.execute(
                "SELECT id::text FROM eas.app_user WHERE username = %s OR id::text = %s",
                [operator, operator],
            )
            op_row = cursor.fetchone()
            operator_id = op_row[0] if op_row else None

            updated_count = 0
            for r in candidates:
                user_id, username, dept_id, auth_version = r
                new_version = auth_version + 1
                cursor.execute(
                    """
                    UPDATE eas.app_user
                    SET must_change_password = TRUE,
                        auth_version = %s
                    WHERE id = %s
                    """,
                    [new_version, user_id],
                )
                _append_admin_audit(
                    cursor,
                    actor_id=operator_id,
                    action="MASS_PASSWORD_ROTATION_ENFORCED",
                    target_type="app_user",
                    target_id=user_id,
                    department_id=dept_id,
                    reason=f"Mandatory commercial pre-delivery rotation: {approval}",
                    details={
                        "username": username,
                        "auth_version": new_version,
                        "change_ticket": approval,
                    },
                    correlation_id=correlation_id,
                )
                with contextlib.suppress(Exception):
                    cache.delete(f"eas:session:{user_id}")
                updated_count += 1

            if connection.vendor == "postgresql":
                cursor.execute(
                    "UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1"
                )

        self.stdout.write(
            f"Successfully enforced password rotation on {updated_count} accounts. "
            f"All previous sessions revoked."
        )
