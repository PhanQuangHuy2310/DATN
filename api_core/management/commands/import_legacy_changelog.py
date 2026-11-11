"""Copy eas.system_versions_changelog rows into the hash-chained eas.admin_event.

Schema v2 keeps one admin change log (admin_event). Rows are appended through
the normal audit writer so the hash chain stays valid; each copy carries
``details.legacy_changelog_id`` so the command is idempotent and migration 15
can verify every row was copied before it archives the old table.

    python manage.py import_legacy_changelog            # dry-run
    python manage.py import_legacy_changelog --apply
"""

from __future__ import annotations

import uuid

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from api_core.workflow.service import record_system_change

SQL_PENDING = """
    SELECT c.id::text, c.system_version, c.change_type, c.change_scope, c.title,
           c.description, c.old_value, c.new_value, c.changed_by, c.created_at,
           (SELECT u.id::text FROM eas.app_user u
             WHERE u.id::text = c.changed_by OR lower(u.email) = lower(c.changed_by)
             LIMIT 1)
    FROM eas.system_versions_changelog c
    WHERE NOT EXISTS (
      SELECT 1 FROM eas.admin_event e
      WHERE e.details->>'legacy_changelog_id' = c.id::text
    )
    ORDER BY c.created_at, c.id
"""


def _text(value, fallback: str) -> str:
    value = (value or "").strip()
    return value or fallback


class Command(BaseCommand):
    help = "Copy legacy system_versions_changelog rows into admin_event (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the rows.")

    def handle(self, *args, **options):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('eas.system_versions_changelog') IS NOT NULL"
            )
            if not cursor.fetchone()[0]:
                self.stdout.write(
                    "eas.system_versions_changelog không còn: không có gì để chép."
                )
                return
            cursor.execute(SQL_PENDING)
            rows = cursor.fetchall()
            for row in rows:
                legacy_id, version, change_type, scope, title, desc = row[:6]
                old_value, new_value, changed_by, created_at, actor_id = row[6:]
                self.stdout.write(
                    f"{created_at:%Y-%m-%d %H:%M} {change_type:<10} {title}"
                )
                if not options["apply"]:
                    continue
                record_system_change(
                    cursor,
                    actor_id=actor_id,
                    change_type=_text(change_type, "SYSTEM"),
                    change_scope=_text(scope, "PATCH"),
                    system_version=_text(version, "v?"),
                    title=_text(title, "Thay đổi hệ thống (bản ghi cũ)"),
                    description=desc or "",
                    old_value=old_value,
                    new_value=new_value,
                    target_type="legacy_changelog",
                    target_id=legacy_id,
                    extra_details={
                        "legacy_changelog_id": legacy_id,
                        "original_created_at": created_at.isoformat(),
                        "changed_by": changed_by,
                    },
                    correlation_id=str(uuid.uuid4()),
                )
            verb = (
                "copied"
                if options["apply"]
                else "pending (dry-run, re-run with --apply)"
            )
            self.stdout.write(f"{len(rows)} row(s) {verb}.")
