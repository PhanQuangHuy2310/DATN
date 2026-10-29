from __future__ import annotations

import io
import json
import os
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.management import call_command
from django.test import SimpleTestCase

from api_core.audit import canonical_sha256
from api_core.authn.models import Actor
from api_core.workflow.reporting import (
    get_request_metrics_report,
    verify_audit_chain,
)
from api_core.workflow.service import CommandError


class ReportingBoundaryAndLogicTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.actor = Actor(
            id=str(uuid4()),
            username="analyst",
            display_name="Analyst",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"AUDITOR"}),
            must_change_password=False,
        )

    def test_metrics_report_rejects_inverted_dates(self):
        # created_to <= created_from
        with self.assertRaises(CommandError) as raised:
            get_request_metrics_report(
                self.actor,
                {
                    "created_from": "2026-10-10T00:00:00Z",
                    "created_to": "2026-10-05T00:00:00Z",
                },
            )
        self.assertEqual(raised.exception.code, "PERIOD_INVALID")

    def test_metrics_report_rejects_exceeding_366_days(self):
        # Period > 366 days
        with self.assertRaises(CommandError) as raised:
            get_request_metrics_report(
                self.actor,
                {
                    "created_from": "2025-01-01T00:00:00Z",
                    "created_to": "2026-02-01T00:00:00Z",
                },
            )
        self.assertEqual(raised.exception.code, "PERIOD_INVALID")

    @patch("api_core.workflow.reporting.connection.cursor")
    def test_audit_verify_hash_chain_success(self, mock_cursor_ctx):
        from datetime import datetime, timezone

        from api_core.workflow.service import _utc_text

        mock_cursor = MagicMock()
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        dt1 = datetime(2026, 10, 22, 10, 0, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 10, 22, 10, 5, 0, 0, tzinfo=timezone.utc)

        scope_key = "ADMIN"
        e1_id = str(uuid4())
        e1_payload = {
            "action": "CONFIG_DRAFT_CREATED",
            "actor_id": self.actor.id,
            "actor_kind": "USER",
            "correlation_id": str(uuid4()),
            "department_id": None,
            "details": {},
            "hash_version": 1,
            "id": e1_id,
            "occurred_at": _utc_text(dt1),
            "prev_hash": "0" * 64,
            "reason": "Initial draft",
            "scope_key": "ADMIN",
            "seq": "1",
            "target_id": str(uuid4()),
            "target_type": "config_release",
            "type_id": None,
        }
        e1_hash = canonical_sha256(e1_payload)

        e2_id = str(uuid4())
        e2_payload = {
            "action": "CONFIG_RELEASE_PUBLISHED",
            "actor_id": self.actor.id,
            "actor_kind": "USER",
            "correlation_id": str(uuid4()),
            "department_id": None,
            "details": {},
            "hash_version": 1,
            "id": e2_id,
            "occurred_at": _utc_text(dt2),
            "prev_hash": e1_hash,
            "reason": "Published version 1",
            "scope_key": "ADMIN",
            "seq": "2",
            "target_id": str(uuid4()),
            "target_type": "config_release",
            "type_id": None,
        }
        e2_hash = canonical_sha256(e2_payload)

        # Mock audit_head and audit_events fetch
        mock_cursor.fetchone.side_effect = [
            (2, e2_hash),  # audit_head
            None,  # audit_checkpoint
        ]
        # Columns: id, seq, actor_id, actor_kind, action, target_type, target_id,
        #          department_id, type_id, details, reason, correlation_id, occurred_at, prev_hash, hash
        mock_cursor.fetchall.return_value = [
            (
                e1_id,
                1,
                self.actor.id,
                "USER",
                "CONFIG_DRAFT_CREATED",
                "config_release",
                e1_payload["target_id"],
                None,
                None,
                {},
                "Initial draft",
                e1_payload["correlation_id"],
                dt1,
                "0" * 64,
                e1_hash,
            ),
            (
                e2_id,
                2,
                self.actor.id,
                "USER",
                "CONFIG_RELEASE_PUBLISHED",
                "config_release",
                e2_payload["target_id"],
                None,
                None,
                {},
                "Published version 1",
                e2_payload["correlation_id"],
                dt2,
                e1_hash,
                e2_hash,
            ),
        ]

        result = verify_audit_chain(scope_key)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checked_seq"], 2)
        self.assertEqual(result["head_hash"], e2_hash)

    @patch("api_core.workflow.reporting.connection.cursor")
    def test_audit_verify_hash_chain_tamper_detected(self, mock_cursor_ctx):
        from datetime import datetime, timezone

        mock_cursor = MagicMock()
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        scope_key = "ADMIN"
        mock_cursor.fetchone.side_effect = [
            (1, "bad_head_hash"),  # audit_head
            None,  # audit_checkpoint
        ]
        mock_cursor.fetchall.return_value = [
            (
                str(uuid4()),
                1,
                self.actor.id,
                "USER",
                "CONFIG_DRAFT_CREATED",
                "config_release",
                str(uuid4()),
                None,
                None,
                {},
                "Initial",
                str(uuid4()),
                datetime(2026, 10, 22, 10, 0, 0, 0, tzinfo=timezone.utc),
                "bad_prev_hash",  # Should be 64 zeros!
                "tampered_hash",
            )
        ]

        result = verify_audit_chain(scope_key)
        self.assertEqual(result["status"], "FAIL")


class ReportingHttpContractTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.actor = Actor(
            id=str(uuid4()),
            username="user1",
            display_name="User One",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"REQUESTER", "AUDITOR"}),
            must_change_password=False,
        )

    @patch("api_core.workflow.views.list_notifications")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_notifications_endpoint(self, load_actor, list_notifs):
        load_actor.return_value = self.actor
        list_notifs.return_value = {
            "items": [
                {
                    "id": str(uuid4()),
                    "event_id": str(uuid4()),
                    "request_id": str(uuid4()),
                    "label": "REQUEST_SUBMITTED",
                    "read_at": None,
                    "created_at": "2026-10-22T10:00:00Z",
                }
            ],
            "unread_count": 1,
            "next_offset": None,
        }
        response = self.client.get("/api/v1/notifications?unread=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        self.assertEqual(response.json()["unread_count"], 1)

    @patch("api_core.workflow.reporting.connection.cursor")
    def test_list_notifications_direct_query(self, mock_cursor_ctx):
        mock_cursor = MagicMock()
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = []

        from api_core.workflow.reporting import list_notifications

        res_false = list_notifications(
            self.actor, {"limit": "20", "offset": "0", "unread": "false"}
        )
        self.assertIn("items", res_false)
        self.assertIn("unread_count", res_false)
        executed_sql = mock_cursor.execute.call_args[0][0]
        self.assertNotIn("%s IS FALSE", executed_sql)

        res_true = list_notifications(
            self.actor, {"limit": "20", "offset": "0", "unread": "true"}
        )
        self.assertIn("items", res_true)
        executed_sql_true = mock_cursor.execute.call_args[0][0]
        self.assertIn("read_at IS NULL", executed_sql_true)

    @patch("api_core.workflow.views.get_request_metrics_report")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_reports_requests_endpoint(self, load_actor, mock_report):
        load_actor.return_value = self.actor
        mock_report.return_value = {
            "submitted": 10,
            "approved": 8,
            "completed": 7,
            "by_status": {"COMPLETED": 7, "PENDING_APPROVAL": 2, "REJECTED": 1},
            "approved_rate": 0.8,
            "completed_rate": 0.7,
        }
        response = self.client.get("/api/v1/reports/requests")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["submitted"], 10)
        self.assertEqual(response.json()["approved_rate"], 0.8)

    @patch("api_core.workflow.views.get_request_audit_verify")
    @patch("api_core.authn.service.load_actor_from_session")
    def test_request_audit_verify_endpoint(self, load_actor, mock_verify):
        load_actor.return_value = self.actor
        req_id = str(uuid4())
        mock_verify.return_value = {
            "status": "PASS",
            "checked_seq": 5,
            "head_hash": "a" * 64,
        }
        response = self.client.get(f"/api/v1/requests/{req_id}/audit/verify")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "PASS")


class ManagementCommandsTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def test_account_reset_requires_temp_password_in_env_for_password_reset(self):
        old_env = os.environ.get("EAS_TEMP_PASSWORD")
        if "EAS_TEMP_PASSWORD" in os.environ:
            del os.environ["EAS_TEMP_PASSWORD"]
        try:
            with self.assertRaises(SystemExit) as cm:
                call_command(
                    "account_reset",
                    user="testuser",
                    mode="reset-password",
                    operator="admin",
                    approval="REF-1234",
                )
            self.assertEqual(cm.exception.code, 2)
        finally:
            if old_env is not None:
                os.environ["EAS_TEMP_PASSWORD"] = old_env

    @patch("api_core.management.commands.identity_import.connection.cursor")
    def test_identity_import_detects_cycles(self, mock_cursor_ctx):
        # TC008: Cycle detection in manifest
        import tempfile

        manifest_data = {
            "departments": [
                {"code": "D1", "name": "Dept 1", "parent_code": "D2"},
                {"code": "D2", "name": "Dept 2", "parent_code": "D1"},  # Cycle!
            ],
            "users": [],
            "roles": [],
        }
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tf:
            json.dump(manifest_data, tf)
            tf.flush()
            manifest_path = tf.name

        try:
            with self.assertRaises(SystemExit) as cm:
                call_command("identity_import", manifest=manifest_path, dry_run=True)
            self.assertEqual(cm.exception.code, 2)
        finally:
            if os.path.exists(manifest_path):
                os.remove(manifest_path)

    @patch("api_core.management.commands.audit_verify.verify_audit_chain")
    def test_audit_verify_command_exit_codes(self, mock_verify):
        # TC096 CLI exit codes: 0 on PASS, 2 on FAIL
        mock_verify.return_value = {
            "status": "PASS",
            "checked_seq": 10,
            "head_hash": "a" * 64,
        }
        out = io.StringIO()
        with self.assertRaises(SystemExit) as cm:
            call_command("audit_verify", scope="ADMIN", stdout=out)
        self.assertEqual(cm.exception.code, 0)
        self.assertIn('"status": "PASS"', out.getvalue())

        mock_verify.return_value = {"status": "FAIL", "reason": "Hash mismatch"}
        with self.assertRaises(SystemExit) as cm:
            call_command("audit_verify", scope="ADMIN")
        self.assertEqual(cm.exception.code, 2)

    @patch("api_core.management.commands.privacy_case.connection.cursor")
    def test_privacy_case_blocked_by_retention_hold(self, mock_cursor_ctx):
        # TC084: Privacy erasure blocked by active retention hold
        mock_cursor = MagicMock()
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        case_id = str(uuid4())
        target_uid = str(uuid4())
        mock_cursor.fetchone.side_effect = [
            (
                case_id,
                target_uid,
                "ERASURE",
                "APPROVED",
                "testuser",
                "testuser@example.com",
            ),
            (1,),  # active retention hold count > 0 -> BLOCKED!
        ]

        with self.assertRaises(SystemExit) as cm:
            call_command(
                "privacy_case",
                case=case_id,
                action="execute-erase",
                approval="REF-LEGAL-1",
            )
        self.assertEqual(cm.exception.code, 2)
