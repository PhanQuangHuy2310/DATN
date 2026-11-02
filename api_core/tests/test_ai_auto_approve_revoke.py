"""Item 1.5: an approver can revoke an AI auto-approval within 24 hours."""

from datetime import datetime, timedelta, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from django.conf import settings
from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.workflow.auto_approval import (
    ai_approval_info,
    auto_approve_key,
    revoke_ai_auto_approval,
    try_auto_approve,
)
from api_core.workflow.service import CommandError


def _actor(roles, actor_id=None):
    return Actor(
        id=actor_id or str(uuid4()),
        email="approver@eas.com",
        display_name="Approver",
        department_id=str(uuid4()),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


class RevokeAiAutoApprovalTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def setUp(self):
        self.request_id = str(uuid4())
        self.requester = str(uuid4())
        self.human_approver = str(uuid4())
        self.approver = _actor({"APPROVER"})

    def request_row(self, status="COMPLETED", lifecycle="A", version=5):
        return (
            status,
            version,
            self.requester,
            str(uuid4()),
            str(uuid4()),
            1,
            str(uuid4()),
            str(uuid4()),
            {"title": "Đặt phòng họp"},
            None,
            "sha",
            1,
            1,
            str(uuid4()),
            lifecycle,
            "default",
            [
                {
                    "step_no": 1,
                    "assignee_id": self.human_approver,
                    "resolver": "DIRECT_MANAGER",
                }
            ],
            {"approval_hours": 8},
        )

    def revoke(self, fetches, actor=None, body=None):
        cursor = MagicMock()
        cursor.fetchone.side_effect = fetches
        with (
            patch(
                "api_core.workflow.auto_approval._execute_idempotent",
                side_effect=lambda **kw: kw["operation"](cursor),
            ),
            patch("api_core.workflow.auto_approval._append_request_audit") as audit,
        ):
            result = revoke_ai_auto_approval(
                actor=actor or self.approver,
                request_id=self.request_id,
                body=body or {"reason": "AI duyệt sai quy định", "expected_version": 5},
                idempotency_key=str(uuid4()),
                correlation_id="c",
            )
        return result, cursor, audit

    def ai_decision(self, hours_ago=1):
        return (
            settings.EAS_AI_SYSTEM_USER_ID,
            datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        )

    def test_revoke_within_24h_returns_request_to_manual_approval(self):
        result, cursor, audit = self.revoke(
            [
                self.request_row(),
                self.ai_decision(),
                (True,),  # actor is an approver in scope
                (str(uuid4()), self.human_approver),  # re-created first step
                (False,),  # delegation table not installed
                (False,),  # attendance feed not installed
            ]
        )
        self.assertEqual(result[0]["request"]["status"], "PENDING_APPROVAL")
        calls = [c.args for c in cursor.execute.call_args_list]
        sql = " ".join(c[0] for c in calls)
        self.assertIn("SET status='NEEDS_INFO'", sql)
        self.assertIn("INSERT INTO eas.request_revision", sql)
        self.assertIn("SET current_revision_id=%s, status='PENDING_APPROVAL'", sql)
        revision = next(c for c in calls if "INSERT INTO eas.request_revision" in c[0])
        self.assertEqual(revision[1][2], 2)  # next consecutive revision number
        self.assertEqual(revision[1][7], self.requester)
        step = next(c for c in calls if "INSERT INTO eas.approval_step" in c[0])
        self.assertEqual(step[1][4], self.human_approver)  # original human approver
        self.assertEqual(step[1][5], "ACTIVE")
        outbox = next(c for c in calls if "INSERT INTO eas.outbox_event" in c[0])
        self.assertEqual(outbox[1][1], "APPROVAL_REQUESTED")
        self.assertEqual(audit.call_args.kwargs["action"], "AI_AUTO_APPROVE_REVOKED")

    def test_after_24h_revoke_is_refused(self):
        with self.assertRaises(CommandError) as raised:
            self.revoke([self.request_row(), self.ai_decision(hours_ago=25)])
        self.assertEqual(raised.exception.code, "AI_APPROVAL_NOT_REVOCABLE")

    def test_human_decision_is_not_revocable(self):
        human = (self.human_approver, datetime.now(timezone.utc))
        with self.assertRaises(CommandError) as raised:
            self.revoke([self.request_row(), human])
        self.assertEqual(raised.exception.code, "AI_APPROVAL_NOT_REVOCABLE")

    def test_requester_cannot_revoke(self):
        requester = _actor({"APPROVER", "REQUESTER"}, actor_id=self.requester)
        with self.assertRaises(CommandError) as raised:
            self.revoke([self.request_row(), self.ai_decision()], actor=requester)
        self.assertEqual(raised.exception.code, "FORBIDDEN")

    def test_approver_out_of_scope_cannot_revoke(self):
        with self.assertRaises(CommandError) as raised:
            self.revoke([self.request_row(), self.ai_decision(), (False,)])
        self.assertEqual(raised.exception.code, "FORBIDDEN")

    def test_reason_is_required(self):
        with self.assertRaises(CommandError):
            self.revoke([], body={"reason": "ngắn", "expected_version": 5})

    def test_version_conflict(self):
        with self.assertRaises(CommandError) as raised:
            self.revoke([self.request_row(version=6)])
        self.assertEqual(raised.exception.code, "VERSION_CONFLICT")

    def test_request_detail_flags_revocable_window(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = self.ai_decision(hours_ago=2)
        info = ai_approval_info(cursor, self.request_id, "COMPLETED")
        self.assertTrue(info["revocable"])
        cursor.fetchone.return_value = self.ai_decision(hours_ago=30)
        self.assertFalse(
            ai_approval_info(cursor, self.request_id, "COMPLETED")["revocable"]
        )
        cursor.fetchone.return_value = (self.human_approver, datetime.now(timezone.utc))
        self.assertIsNone(ai_approval_info(cursor, self.request_id, "COMPLETED"))


class AutoApproveAfterRevokeTests(SimpleTestCase):
    def test_ai_does_not_re_approve_a_revoked_request(self):
        context = {
            "status": "PENDING_APPROVAL",
            "lock_version": 7,
            "risk_weight": 1,
            "type_code": "ROOM_BOOKING",
            "lifecycle": "A",
            "requester_name": "Staff",
            "department_code": "TECH",
            "step_id": str(uuid4()),
            "assignee_id": str(uuid4()),
            "amount_vnd": None,
            "ai_allowed": False,
        }
        with (
            patch(
                "api_core.workflow.auto_approval._load_context", return_value=context
            ),
            patch(
                "api_core.integrations.ai_service.ai_client_sync.evaluate_auto_approve"
            ) as ai,
        ):
            self.assertIsNone(try_auto_approve(str(uuid4()), "c"))
        ai.assert_not_called()

    def test_idempotency_key_is_a_stable_uuid_per_step(self):
        step = str(uuid4())
        key = auto_approve_key(step)
        self.assertEqual(str(UUID(key)), key)
        self.assertEqual(key, auto_approve_key(step))
        self.assertNotEqual(key, auto_approve_key(str(uuid4())))
