"""Regression tests: DB07 JSONB NOT NULL and per-action transactional outbox."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase
from psycopg.types.json import Jsonb

from api_core.authn.models import Actor
from api_core.workflow.service import create_draft, _append_request_audit
from api_core.worker import OutboxItem, _recipients


class CreationAndNotificationTests(SimpleTestCase):
    def setUp(self):
        self.actor = Actor(
            id=str(uuid4()), username="requester", display_name="Requester",
            department_id=str(uuid4()), auth_version=1,
            roles=frozenset({"REQUESTER"}), must_change_password=False,
        )

    @patch("api_core.workflow.service._append_request_audit")
    @patch("api_core.workflow.service._authorize")
    @patch("api_core.workflow.service._execute_idempotent")
    def test_creating_without_title_never_inserts_null_jsonb(self, execute, authorize, audit):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            (str(uuid4()), str(uuid4())),
            ("EAS-2026-0001",),
        ]
        execute.side_effect = lambda **kwargs: kwargs["operation"](cursor)
        response = create_draft(
            actor=self.actor, body={"type_code": "LEAVE"},
            idempotency_key=str(uuid4()), correlation_id=str(uuid4()),
        )
        self.assertEqual(response[1], 201)
        insert = next(call for call in cursor.execute.call_args_list
                      if "INSERT INTO eas.request(" in call.args[0])
        self.assertIsInstance(insert.args[1][4], Jsonb)
        self.assertEqual(insert.args[1][4].obj, {})
        audit.assert_called_once()

    def test_audit_enqueues_one_activity_in_same_transaction(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (0, "0" * 64)
        _append_request_audit(
            cursor, request_id=str(uuid4()), actor_id=self.actor.id,
            action="REQUEST_SUBMITTED", target_type="request", target_id=str(uuid4()),
            details={}, correlation_id=str(uuid4()),
            occurred_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        )
        outbox = [c for c in cursor.execute.call_args_list
                  if "INSERT INTO eas.outbox_event" in c.args[0]]
        self.assertEqual(len(outbox), 1)
        self.assertIn("REQUEST_ACTIVITY", outbox[0].args[0])
        self.assertTrue(outbox[0].args[1][2].startswith("request-activity:"))

    def test_read_only_attachment_download_does_not_spam_inbox(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (0, "0" * 64)
        _append_request_audit(
            cursor, request_id=str(uuid4()), actor_id=self.actor.id,
            action="ATTACHMENT_DOWNLOADED", target_type="attachment", target_id=str(uuid4()),
            details={}, correlation_id=str(uuid4()),
        )
        self.assertFalse(any("INSERT INTO eas.outbox_event" in c.args[0]
                             for c in cursor.execute.call_args_list))

    def test_worker_targets_owner_and_nonrevoked_participants(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(self.actor.id,), (str(uuid4()),)]
        item = OutboxItem(id=str(uuid4()), request_id=str(uuid4()),
                          event_type="REQUEST_ACTIVITY", payload={"action": "REQUEST_SUBMITTED"},
                          attempts=1, lease_token=str(uuid4()))
        recipients = _recipients(cursor, item)
        self.assertEqual(len(recipients), 2)
        self.assertTrue(all("được gửi" in label for _, label in recipients))
        self.assertIn("read_revoked_at IS NULL", cursor.execute.call_args.args[0])
