from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from api_core.authn.models import Actor
from api_core.workflow.history_views import history, unlink_attachment
from api_core.workflow.service import CommandError


class HistoryBoundaryTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.actor = Actor(
            str(uuid4()),
            "test",
            "Test",
            str(uuid4()),
            1,
            frozenset({"REQUESTER"}),
            False,
        )

    def test_history_reuses_detail_authorization(self):
        req = RequestFactory().get("/api/v1/requests/" + str(uuid4()) + "/history")
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=self.actor,
            ),
            patch(
                "api_core.workflow.history_views.request_detail",
                return_value=JsonResponse({"error": "not found"}, status=404),
            ),
            patch("api_core.workflow.history_views.connection.cursor"),
            patch("api_core.workflow.history_views.transaction.atomic"),
        ):
            self.assertEqual(history(req, str(uuid4())).status_code, 404)

    def run_unlink(self, status, owner=None, version=1, expected=1):
        c = MagicMock()
        c.fetchone.side_effect = [
            (
                owner or self.actor.id,
                status,
                version,
                str(uuid4()),
                self.actor.department_id,
            ),
            (str(uuid4()),),
        ]
        with (
            patch(
                "api_core.workflow.history_views._execute_idempotent",
                side_effect=lambda **kw: kw["operation"](c),
            ),
            patch("api_core.workflow.history_views._authorize"),
            patch("api_core.workflow.history_views._append_request_audit") as audit,
        ):
            result = unlink_attachment(
                actor=self.actor,
                request_id=str(uuid4()),
                attachment_id=str(uuid4()),
                body={"expected_version": expected},
                idempotency_key="key",
                correlation_id="corr",
            )
        return c, result, audit

    def test_cannot_remove_link_from_submitted_request(self):
        for state in ("PENDING_APPROVAL", "IN_PROGRESS", "COMPLETED", "CANCELLED"):
            with self.assertRaises(CommandError) as e:
                self.run_unlink(state)
            self.assertEqual(e.exception.code, "REQUEST_STATE_CONFLICT")

    def test_cannot_remove_other_users_attachment(self):
        with self.assertRaises(CommandError) as e:
            self.run_unlink("DRAFT", str(uuid4()))
        self.assertEqual(e.exception.code, "FORBIDDEN")

    def test_stale_unlink_rejected(self):
        with self.assertRaises(CommandError) as e:
            self.run_unlink("DRAFT", version=2, expected=1)
        self.assertEqual(e.exception.code, "VERSION_CONFLICT")

    def test_only_draft_link_deleted(self):
        c, result, audit = self.run_unlink("DRAFT")
        sql = " ".join(call.args[0] for call in c.execute.call_args_list)
        self.assertIn("DELETE FROM eas.draft_attachment", sql)
        self.assertNotIn("DELETE FROM eas.attachment ", sql)
        self.assertEqual(result[0]["lock_version"], 2)
        audit.assert_called_once()
