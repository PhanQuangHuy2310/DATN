from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from psycopg.types.json import Jsonb

from api_core.audit import canonical_sha256

DEMO_USERNAME = "demo_requester"
DISABLED_HASH = "!UNUSABLE_DEMO_REQUESTER"


class Command(BaseCommand):
    help = "Temporarily enable/disable the fixed development E2E account with audited changes."

    def add_arguments(self, parser):
        parser.add_argument("mode", choices=("enable", "disable"))
        parser.add_argument("--confirm-project", required=True)

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != "development":
            raise CommandError("This command is restricted to EAS_ENV=development.")
        project_ref = urlparse(os.getenv("SUPABASE_URL", "")).hostname
        project_ref = project_ref.split(".")[0] if project_ref else ""
        if not project_ref or options["confirm_project"] != project_ref:
            raise CommandError("Project confirmation does not match SUPABASE_URL.")

        mode = options["mode"]
        password = os.getenv("EAS_E2E_PASSWORD", "")
        if mode == "enable" and len(password) < 24:
            raise CommandError("EAS_E2E_PASSWORD must contain at least 24 characters.")

        now = datetime.now(timezone.utc)
        correlation_id = str(uuid4())
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT eas.lock_security(true)")
            cursor.execute(
                """
                SELECT id::text,department_id::text,password_hash,auth_version,must_change_password
                FROM eas.app_user WHERE username=%s AND is_active FOR UPDATE
                """,
                [DEMO_USERNAME],
            )
            row = cursor.fetchone()
            if not row:
                raise CommandError(
                    "The fixed demo requester does not exist or is inactive."
                )
            user_id, department_id, current_hash, auth_version, must_change = row
            if mode == "enable" and (current_hash != DISABLED_HASH or not must_change):
                raise CommandError(
                    "Fixture account is not in its disabled baseline state."
                )

            new_version = auth_version + 1
            password_hash = (
                make_password(password, hasher="argon2")
                if mode == "enable"
                else DISABLED_HASH
            )
            cursor.execute(
                """
                UPDATE eas.app_user
                SET password_hash=%s,auth_version=%s,must_change_password=%s
                WHERE id=%s
                """,
                [password_hash, new_version, mode == "disable", user_id],
            )
            cursor.execute(
                "UPDATE eas.security_epoch SET version=version+1,updated_at=%s WHERE id=1",
                [now],
            )
            cursor.execute("SELECT seq,last_hash FROM eas.lock_audit_head('ADMIN')")
            head = cursor.fetchone()
            if not head:
                raise CommandError("ADMIN audit head is missing.")

            event_id = str(uuid4())
            sequence = head[0] + 1
            previous_hash = head[1]
            action = (
                "E2E_PASSWORD_ENABLED" if mode == "enable" else "E2E_PASSWORD_DISABLED"
            )
            reason = "Temporary browser-test credential lifecycle operation."
            details = {
                "auth_version": new_version,
                "fixture": DEMO_USERNAME,
                "mode": mode,
            }
            occurred_at = now.isoformat(timespec="microseconds").replace("+00:00", "Z")
            event = {
                "action": action,
                "actor_id": None,
                "actor_kind": "SYSTEM",
                "correlation_id": correlation_id,
                "department_id": department_id,
                "details": details,
                "hash_version": 1,
                "id": event_id,
                "occurred_at": occurred_at,
                "prev_hash": previous_hash,
                "reason": reason,
                "scope_key": "ADMIN",
                "seq": str(sequence),
                "target_id": user_id,
                "target_type": "app_user",
                "type_id": None,
            }
            cursor.execute(
                """
                INSERT INTO eas.admin_event(
                  id,seq,actor_id,actor_kind,action,target_type,target_id,department_id,
                  type_id,details,reason,correlation_id,occurred_at,hash_version,prev_hash,hash
                ) VALUES (%s,%s,NULL,'SYSTEM',%s,'app_user',%s,%s,NULL,%s,%s,%s,%s,1,%s,%s)
                """,
                [
                    event_id,
                    sequence,
                    action,
                    user_id,
                    department_id,
                    Jsonb(details),
                    reason,
                    correlation_id,
                    now,
                    previous_hash,
                    canonical_sha256(event),
                ],
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"E2E account {mode} completed; no credential was printed."
            )
        )
