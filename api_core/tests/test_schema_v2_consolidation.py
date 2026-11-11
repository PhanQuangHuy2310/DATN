"""Schema v2 consolidation (migration 15): one admin change log, no duplicate names."""

import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.management import call_command
from django.test import SimpleTestCase

from api_core.management.commands import import_legacy_changelog as cmd
from api_core.workflow import service

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/migrations/15_schema_v2_consolidate.sql"


class RecordSystemChangeTests(SimpleTestCase):
    def test_human_change_goes_to_admin_event_with_changelog_fields(self):
        actor = str(uuid4())
        with patch.object(service, "_append_admin_audit", return_value="e1") as audit:
            service.record_system_change(
                MagicMock(),
                actor_id=actor,
                change_type="WORKFLOW",
                system_version="v2.0",
                title="Chuyển nhóm A",
                description="mô tả",
                old_value={"category_code": "A"},
                new_value={"category_code": "B"},
                correlation_id=str(uuid4()),
            )
        kwargs = audit.call_args.kwargs
        self.assertEqual(kwargs["actor_kind"], "HUMAN")
        self.assertEqual(kwargs["action"], "SYSTEM_CHANGE_WORKFLOW")
        self.assertEqual(kwargs["details"]["change_type"], "WORKFLOW")
        self.assertEqual(kwargs["details"]["new_value"], {"category_code": "B"})
        self.assertGreaterEqual(len(kwargs["reason"]), 10)

    def test_system_change_without_actor_and_short_title(self):
        with patch.object(service, "_append_admin_audit") as audit:
            service.record_system_change(
                MagicMock(),
                actor_id=None,
                change_type="REGULATION",
                system_version="v1.2",
                title="v1.2",
                description="",
                correlation_id=str(uuid4()),
            )
        kwargs = audit.call_args.kwargs
        self.assertEqual(kwargs["actor_kind"], "SYSTEM")
        self.assertIsNone(kwargs["actor_id"])
        self.assertTrue(kwargs["reason"].startswith("Thay đổi hệ thống"))


class ImportLegacyChangelogTests(SimpleTestCase):
    def _run(self, *args, rows):
        cursor = MagicMock()
        cursor.fetchone.return_value = (True,)
        cursor.fetchall.return_value = rows
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        out = StringIO()
        with (
            patch.object(cmd, "connection", connection),
            patch.object(cmd, "transaction", MagicMock()),
            patch.object(cmd, "record_system_change") as record,
        ):
            call_command("import_legacy_changelog", *args, stdout=out)
        return record, out.getvalue()

    def _row(self, actor_id):
        return (
            str(uuid4()),
            "v2.0",
            "API_STATUS",
            "PATCH",
            "Bật kết nối API: HR",
            "mô tả",
            {"is_enabled": False},
            {"is_enabled": True},
            "admin@eas.com",
            datetime(2026, 11, 3, tzinfo=timezone.utc),
            actor_id,
        )

    def test_dry_run_writes_nothing(self):
        record, out = self._run(rows=[self._row(None)])
        record.assert_not_called()
        self.assertIn("1 row(s) pending", out)

    def test_apply_keeps_legacy_id_time_and_actor(self):
        actor = str(uuid4())
        row = self._row(actor)
        record, _ = self._run("--apply", rows=[row])
        kwargs = record.call_args.kwargs
        self.assertEqual(kwargs["actor_id"], actor)
        self.assertEqual(kwargs["extra_details"]["legacy_changelog_id"], row[0])
        self.assertEqual(
            kwargs["extra_details"]["original_created_at"], row[9].isoformat()
        )
        self.assertEqual(kwargs["new_value"], {"is_enabled": True})


class NoDuplicateNamesTests(SimpleTestCase):
    REMOVED = (
        r"INSERT INTO eas\.system_versions_changelog",
        r"FROM eas\.system_versions_changelog",
        r"eas\.work_handover",
        r"eas\.workflow_categories",
        r"\br\.risk_weight\b",
        r"\br\.approval_level\b",
        r"\bu\.username\b",
        r"eas\.(roles|requests|departments|admins|user_roles|role_permissions|request_templates)\b",
    )

    def test_code_no_longer_uses_removed_names(self):
        offenders = []
        for path in (ROOT / "api_core").rglob("*.py"):
            if (
                "tests" in path.parts
                or "management" in path.parts
                and path.name.startswith("import_legacy")
            ):
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in self.REMOVED:
                for match in re.finditer(pattern, text):
                    line = text.count("\n", 0, match.start()) + 1
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{line} {match.group(0)}"
                    )
        self.assertEqual(offenders, [])

    def test_migration_archives_instead_of_deleting(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertNotRegex(sql, r"DROP\s+SCHEMA")
        self.assertNotRegex(sql, r"DROP\s+TABLE")
        self.assertIn("eas_archive.dropped_column_value", sql)
        self.assertIn("import_legacy_changelog --apply", sql)
        # Column values are saved before each column is dropped.
        self.assertLess(
            sql.index("INSERT INTO eas_archive.dropped_column_value"),
            sql.index("DROP COLUMN %I"),
        )


class TableReadableGuardTests(SimpleTestCase):
    def test_checks_schema_usage_before_to_regclass(self):
        # to_regclass() raises "permission denied for schema" for a role without
        # USAGE (worker on mock_hr) and aborts the transaction.
        cursor = MagicMock()
        cursor.fetchone.return_value = (False,)
        self.assertFalse(service._table_readable(cursor, "mock_hr.attendance"))
        sql = cursor.execute.call_args.args[0]
        self.assertLess(sql.index("has_schema_privilege"), sql.index("to_regclass"))
        self.assertIn("CASE", sql)
