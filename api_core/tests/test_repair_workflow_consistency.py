from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.management import call_command
from django.test import SimpleTestCase

from api_core.management.commands import repair_workflow_consistency as cmd

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def _sql(cursor) -> str:
    return " ".join(c.args[0] for c in cursor.execute.call_args_list)


class RepairWorkflowConsistencyTests(SimpleTestCase):
    def test_stuck_request_activates_lowest_waiting_step_with_audit(self):
        cursor = MagicMock()
        step = str(uuid4())
        cursor.fetchone.return_value = (step, 2)
        row = (
            str(uuid4()),
            "REQ-2026-0009",
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
            {"approval_hours": 24},
        )
        with (
            patch.object(cmd, "_substitute_approver") as substitute,
            patch.object(cmd, "_append_request_audit") as audit,
        ):
            result = cmd.repair_stuck(cursor, row, NOW)
        sql = _sql(cursor)
        self.assertIn("SET state='ACTIVE', activated_at=%s", sql)
        self.assertIn("INSERT INTO eas.sla_stage", sql)
        substitute.assert_called_once()
        self.assertEqual(audit.call_args.kwargs["action"], "DATA_REPAIR_STEP_ACTIVATED")
        self.assertEqual(audit.call_args.kwargs["actor_kind"], "SYSTEM")
        self.assertEqual(result["step_no"], 2)

    def test_orphan_terminal_request_is_closed(self):
        cursor = MagicMock()
        cursor.rowcount = 1
        with patch.object(cmd, "_append_request_audit") as audit:
            result = cmd.repair_orphan(
                cursor, (str(uuid4()), "REQ-2026-0011", "CANCELLED"), NOW
            )
        sql = _sql(cursor)
        self.assertIn("SET state='SKIPPED'", sql)
        self.assertIn("UPDATE eas.workflow_instance SET state=%s", sql)
        self.assertIn("UPDATE eas.sla_stage SET closed_at=%s", sql)
        self.assertEqual(
            audit.call_args.kwargs["action"], "DATA_REPAIR_TERMINAL_CLOSED"
        )
        self.assertEqual(result["action"], "TERMINAL_CLOSED")

    def test_dry_run_reports_without_writing(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [(None, "REQ-2026-0002")],
            [(None, "REQ-2026-0011", "CANCELLED")],
        ]
        out = StringIO()
        with (
            patch.object(cmd, "transaction"),
            patch.object(cmd, "connection") as conn,
            patch.object(cmd, "repair_stuck") as stuck,
            patch.object(cmd, "repair_orphan") as orphan,
        ):
            conn.cursor.return_value.__enter__.return_value = cursor
            call_command("repair_workflow_consistency", stdout=out)
        stuck.assert_not_called()
        orphan.assert_not_called()
        self.assertIn("dry-run: 1 stuck, 1 orphan", out.getvalue())
