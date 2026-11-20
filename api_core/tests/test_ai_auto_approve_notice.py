"""AI tự duyệt thì báo cho 2 cấp quản lý phía trên người gửi (20/11, theo trưởng nhóm: con người phải nắm được
đầu ra của AI). Luồng giữ nguyên: hồ sơ vẫn hoàn tất, quản lý có 24 giờ để thu hồi."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase

from api_core import worker
from api_core.workflow import auto_approval as aa

REQUESTER, MANAGER, DIRECTOR, CEO = (
    f"00000000-0000-4000-8000-00000000000{i}" for i in range(1, 5)
)
CONTEXT = {
    "requester_id": REQUESTER,
    "requester_name": "Lê Phương Khoa",
    "assignee_id": MANAGER,
    "step_id": "step-1",
}


def _cursor(chain):
    """chain: {user_id: (manager_id, manager_is_active)}; other queries return the request code/type."""
    cur = MagicMock()
    state = {}

    def execute(sql, params=None):
        state["sql"], state["params"] = sql, params

    def fetchone():
        if "manager_id" in state["sql"]:
            return chain.get(state["params"][0])
        if "FROM eas.request r" in state["sql"]:
            return ("EAS-2026-000601", "Làm việc từ xa (WFH)")
        return None

    cur.execute.side_effect = execute
    cur.fetchone.side_effect = fetchone
    return cur


class SupervisorChainTests(SimpleTestCase):
    def test_two_levels_above_the_requester(self):
        cur = _cursor(
            {
                REQUESTER: (MANAGER, True),
                MANAGER: (DIRECTOR, True),
                DIRECTOR: (CEO, True),
            }
        )
        self.assertEqual(aa._supervisors(cur, REQUESTER), [MANAGER, DIRECTOR])

    def test_inactive_manager_is_skipped_but_the_chain_continues(self):
        cur = _cursor({REQUESTER: (MANAGER, False), MANAGER: (DIRECTOR, True)})
        self.assertEqual(aa._supervisors(cur, REQUESTER), [DIRECTOR])

    def test_no_manager_and_cycles_stop_safely(self):
        self.assertEqual(aa._supervisors(_cursor({}), REQUESTER), [])
        cur = _cursor({REQUESTER: (MANAGER, True), MANAGER: (REQUESTER, True)})
        self.assertEqual(aa._supervisors(cur, REQUESTER), [MANAGER])


class NoticeTests(SimpleTestCase):
    def _run(self, chain):
        cur = _cursor(chain)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        with patch.object(aa, "connection", conn), patch.object(aa, "transaction"):
            aa._notify_supervisors("req-1", CONTEXT, "cid")
        return cur

    def test_outbox_event_names_both_supervisors_and_grants_read_access(self):
        cur = self._run({REQUESTER: (MANAGER, True), MANAGER: (DIRECTOR, True)})
        calls = [c.args for c in cur.execute.call_args_list]
        participants = [p for sql, p in calls if "request_participant" in sql]
        self.assertEqual([p[1] for p in participants], [MANAGER, DIRECTOR])
        outbox = next(p for sql, p in calls if "outbox_event" in sql)
        self.assertEqual(outbox[1], "AI_AUTO_APPROVED")
        payload = outbox[2].obj
        self.assertEqual(payload["recipient_ids"], [MANAGER, DIRECTOR])
        self.assertIn("EAS-2026-000601", payload["label"])
        self.assertIn("Lê Phương Khoa", payload["label"])
        self.assertIn("thu hồi", payload["label"])

    def test_without_a_manager_chain_the_original_approver_is_told(self):
        cur = self._run({})
        outbox = next(
            c.args[1] for c in cur.execute.call_args_list if "outbox_event" in c.args[0]
        )
        self.assertEqual(outbox[2].obj["recipient_ids"], [MANAGER])

    def test_a_failing_notice_never_breaks_the_approval(self):
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError("db down")
        with patch.object(aa, "connection", conn), patch.object(aa, "transaction"):
            aa._notify_supervisors("req-1", CONTEXT, "cid")  # không ném lỗi


class WorkerRecipientsTests(SimpleTestCase):
    def test_ai_auto_approved_goes_to_the_named_supervisors(self):
        item = SimpleNamespace(
            event_type="AI_AUTO_APPROVED",
            request_id="req-1",
            payload={"recipient_ids": [MANAGER, DIRECTOR], "label": "AI đã tự duyệt X"},
        )
        self.assertEqual(
            worker._recipients(MagicMock(), item),
            [(MANAGER, "AI đã tự duyệt X"), (DIRECTOR, "AI đã tự duyệt X")],
        )

    def test_ai_account_is_never_a_recipient_downstream(self):
        self.assertTrue(settings.EAS_AI_SYSTEM_USER_ID)


REVOKE_CHAIN = {
    REQUESTER: (MANAGER, True),
    MANAGER: (DIRECTOR, True),
    DIRECTOR: (CEO, True),
}


class RevokeRightTests(SimpleTestCase):
    """Cấp trên hoặc cấp trên nữa của người gửi được thu hồi trong 24 giờ (20/11)."""

    def _may(self, actor, approver=False):
        with patch.object(aa, "_is_actor_valid_for_role", return_value=approver):
            return aa.may_revoke(
                _cursor(REVOKE_CHAIN),
                actor_id=actor,
                requester_id=REQUESTER,
                department_id="d",
                type_id="t",
            )

    def test_direct_manager_and_the_next_level_may_revoke(self):
        self.assertTrue(self._may(MANAGER))
        self.assertTrue(self._may(DIRECTOR))

    def test_three_levels_up_only_as_a_valid_approver(self):
        self.assertFalse(self._may(CEO))
        self.assertTrue(self._may(CEO, approver=True))

    def test_requester_never_revokes_own_request(self):
        self.assertFalse(self._may(REQUESTER, approver=True))
