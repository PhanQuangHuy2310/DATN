"""Move a file-based AI policy (ai_service/data/active_enterprise_policy.json)
into eas.ai_policy_version, the database source of truth (migration 08)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from api_core.authn.models import Actor
from api_core.workflow import ai_policy
from api_core.workflow.service import CommandError as WorkflowCommandError


class Command(BaseCommand):
    help = "Import a file-based AI policy into eas.ai_policy_version and activate it."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Policy JSON file with version and rules.")
        parser.add_argument(
            "--operator", required=True, help="POLICY_ADMIN email recording the import."
        )
        parser.add_argument(
            "--no-activate",
            action="store_true",
            help="Store the version without activating it.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.is_file():
            raise CommandError(f"Policy file not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id::text FROM eas.app_user WHERE email=%s AND is_active",
                [options["operator"].strip().lower()],
            )
            row = cursor.fetchone()
        if not row:
            raise CommandError("Operator account not found or inactive.")
        operator = Actor(
            id=row[0],
            email=options["operator"],
            display_name="",
            department_id="",
            auth_version=0,
            roles=frozenset({"POLICY_ADMIN"}),
            must_change_password=False,
        )
        body = {
            "version": raw.get("version"),
            "rules": raw.get("rules"),
            "activate": not options["no_activate"],
        }
        try:
            stored = ai_policy.publish_version(
                actor=operator, body=body, correlation_id=str(uuid4())
            )
        except WorkflowCommandError as exc:
            raise CommandError(exc.code) from exc
        self.stdout.write(
            f"Imported AI policy {stored['version']} ({len(stored['rules'])} rules), "
            f"active={stored['activated']}."
        )
