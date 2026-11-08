"""C1: <uuid:...> routes hand the view a uuid.UUID, not a str.

UUID(UUID(...)) raises AttributeError, which the views turned into 404, so
history, revisions and attachments were unreachable for their own owner.
These tests go through the real URL resolver (self.client) so the view gets
exactly what Django passes in production.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import SimpleTestCase

from api_core.authn.models import Actor

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


class FakeCursor:
    """Returns queued results in call order; records every executed SQL."""

    def __init__(self, fetchone=(), fetchall=()):
        self.one = list(fetchone)
        self.all = list(fetchall)
        self.params = []
        self.description = [("id",)]

    def execute(self, sql, params=None):
        self.params.append(params or [])

    def fetchone(self):
        return self.one.pop(0) if self.one else None

    def fetchall(self):
        return self.all.pop(0) if self.all else []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


@contextmanager
def _noop_atomic(*args, **kwargs):
    yield


class UuidRouteParamTests(SimpleTestCase):
    def setUp(self):
        self.actor = Actor(
            str(uuid4()),
            "owner@eas.com",
            "Owner",
            str(uuid4()),
            1,
            frozenset({"REQUESTER"}),
            False,
        )
        self.request_id = str(uuid4())
        self.revision_id = str(uuid4())
        self.attachment_id = str(uuid4())
        auth = patch(
            "api_core.authn.service.load_actor_from_session", return_value=self.actor
        )
        maintenance = patch(
            "api_core.maintenance.is_maintenance_active", return_value=False
        )
        for patcher in (auth, maintenance):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _with_cursor(self, module, cursor):
        patcher = patch(f"{module}.connection", FakeConnection(cursor))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_history_passes_a_string_id_to_request_detail(self):
        cursor = FakeCursor(fetchone=[(self.actor.id, "COMPLETED")])
        self._with_cursor("api_core.workflow.history_views", cursor)
        with (
            patch("api_core.workflow.history_views.transaction.atomic", _noop_atomic),
            patch(
                "api_core.workflow.history_views.request_detail",
                return_value=JsonResponse({"request": {}}),
            ) as detail,
        ):
            response = self.client.get(f"/api/v1/requests/{self.request_id}/history")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(detail.call_args.args[1], str)

    def test_revisions_list_is_200_for_the_owner(self):
        cursor = FakeCursor(
            fetchone=[(1,)],
            fetchall=[[(self.revision_id, 1, None, {"title": "x"}, None, NOW)], []],
        )
        self._with_cursor("api_core.workflow.views", cursor)
        response = self.client.get(f"/api/v1/requests/{self.request_id}/revisions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cursor.params[0][0], self.request_id)
        self.assertEqual(response.json()["revisions"][0]["id"], self.revision_id)

    def test_revision_detail_is_200_for_the_owner(self):
        cursor = FakeCursor(
            fetchone=[(1,), (self.revision_id, 1, None, {"title": "x"}, None, NOW)],
            fetchall=[[]],
        )
        self._with_cursor("api_core.workflow.views", cursor)
        response = self.client.get(
            f"/api/v1/requests/{self.request_id}/revisions/{self.revision_id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cursor.params[1], [self.revision_id, self.request_id])

    def test_attachment_metadata_is_200_for_the_owner(self):
        row = (
            self.attachment_id,
            self.request_id,
            "a.pdf",
            "application/pdf",
            10,
            "CLEAN",
            NOW,
            NOW,
        )
        cursor = FakeCursor(fetchone=[row + (None,) * 8])
        self._with_cursor("api_core.workflow.attachments", cursor)
        response = self.client.get(f"/api/v1/attachments/{self.attachment_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cursor.params[0][0], self.attachment_id)

    def test_attachment_download_is_200_for_the_owner(self):
        row = (
            self.attachment_id,
            self.request_id,
            "key",
            "a.pdf",
            "application/pdf",
            "CLEAN",
            "COMPLETED",
            self.actor.id,
            True,
            False,
            False,
        )
        cursor = FakeCursor(fetchone=[row])
        self._with_cursor("api_core.workflow.attachments", cursor)
        with (
            patch("api_core.workflow.attachments.transaction.atomic", _noop_atomic),
            patch(
                "api_core.workflow.attachments.get_private_object", return_value=b"%PDF"
            ),
            patch("api_core.workflow.attachments._append_request_audit"),
        ):
            response = self.client.get(
                f"/api/v1/attachments/{self.attachment_id}/download"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cursor.params[0][0], self.attachment_id)
