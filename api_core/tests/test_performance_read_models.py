"""Read model regression checks for Supabase round-trip reductions.

No network/database access is required; tests use mocked SQL cursors.
"""

import json
from datetime import datetime, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

from api_core.authn.models import Actor
from api_core.catalog.views import department_options
from api_core.workflow.reporting import list_notifications


class EfficientReadModelsTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.actor = Actor(
            id=str(uuid4()),
            email="reader@eas.com",
            display_name="Reader",
            department_id=str(uuid4()),
            auth_version=1,
            roles=frozenset({"REQUESTER"}),
            must_change_password=False,
        )

    @patch("api_core.workflow.reporting.connection.cursor")
    def test_notification_list_returns_count_and_page_in_one_statement(
        self, cursor_context
    ):
        cursor = MagicMock()
        cursor_context.return_value.__enter__.return_value = cursor
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        cursor.fetchall.return_value = [
            (
                3,
                "notification-1",
                "event-1",
                "request-1",
                "REQUEST_SUBMITTED",
                None,
                now,
            ),
            (3, "notification-2", "event-2", "request-2", "APPROVAL_APPROVE", now, now),
        ]
        result = list_notifications(self.actor, {"limit": "1", "offset": "0"})
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertEqual(result["unread_count"], 3)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["next_offset"], 1)
        self.assertEqual(result["items"][0]["label"], "REQUEST_SUBMITTED")

    @patch("api_core.workflow.reporting.connection.cursor")
    def test_empty_notification_page_preserves_unread_count(self, cursor_context):
        cursor = MagicMock()
        cursor_context.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = [(9, None, None, None, None, None, None)]
        result = list_notifications(self.actor, {"offset": "300"})
        self.assertEqual(result["items"], [])
        self.assertEqual(result["unread_count"], 9)
        self.assertIsNone(result["next_offset"])

    @patch("api_core.catalog.views.connection.cursor")
    def test_department_options_returns_only_small_picker_fields(self, cursor_context):
        cursor = MagicMock()
        cursor_context.return_value.__enter__.return_value = cursor
        cursor.fetchall.return_value = [("d1", "Kế toán"), ("d2", "IT")]
        # @require_GET -> @require_actor -> original view. Authentication is
        # independently verified in existing security / actor tests.
        view = department_options.__wrapped__.__wrapped__
        response = view(RequestFactory().get("/api/v1/meta/departments"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)["items"],
            [{"id": "d1", "name": "Kế toán"}, {"id": "d2", "name": "IT"}],
        )
        self.assertEqual(cursor.execute.call_count, 1)
