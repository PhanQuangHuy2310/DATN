"""Vòng phản hồi: bộ nhớ ca sửa quyết định của AI đúng phạm vi, luật admin duyệt được kiểm tra."""

from datetime import datetime, timezone
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from api_core.authn.models import Actor
from api_core.workflow import ai_feedback
from api_core.workflow.ai_learning import validate_review_rules
from api_core.workflow.regulation_compiler import RequestTypeName, skip_reason
from api_core.workflow.remediation import (
    can_mark_escalation_unnecessary,
    mark_escalation_unnecessary,
)
from api_core.workflow.service import CommandError
from api_core.workflow.views import _ai_escalation_info

REVOKED = [
    {
        "id": "f1",
        "request_id": "req-1",
        "request_code": "EAS-1",
        "case_codes": [],
        "reason": "Trùng họp",
        "human_decision": {},
        "actor_name": "Quản lý A",
        "created_at": "2026-11-18T00:00:00",
    }
]
OVERRULED = [
    {
        "id": "f2",
        "request_id": "req-2",
        "request_code": "EAS-2",
        "case_codes": ["BC_WFH_FREQUENT"],
        "reason": "Làm tại khách hàng",
        "human_decision": {},
        "actor_name": "Quản lý B",
        "created_at": "2026-11-18T00:00:00",
    }
]


def fake_memory(revoked=(), overruled=()):
    def memory(cursor, *, kind, type_code, subject_id):
        return {
            "AUTO_APPROVE_REVOKED": list(revoked),
            "ESCALATION_UNNECESSARY": list(overruled),
        }.get(kind, [])

    return memory


class MemoryTests(SimpleTestCase):
    def apply(
        self, verdict, revoked=(), overruled=(), lifecycle="A", exclude_request_id=None
    ):
        with patch.object(
            ai_feedback, "memory", side_effect=fake_memory(revoked, overruled)
        ):
            return ai_feedback.apply_to_verdict(
                None,
                verdict=verdict,
                type_code="WFH_REQ",
                requester_id="u1",
                lifecycle=lifecycle,
                exclude_request_id=exclude_request_id,
            )

    def test_no_memory_keeps_the_decision(self):
        out = self.apply({"decision": "auto_approve"})
        self.assertEqual(out["decision"], "auto_approve")
        self.assertEqual(out["learned"], [])

    def test_revoked_before_means_no_auto_approval_and_escalation(self):
        out = self.apply({"decision": "auto_approve"}, revoked=REVOKED)
        self.assertEqual(out["decision"], "escalate_to_human")
        self.assertEqual(out["escalate_to"], "B")
        self.assertEqual(out["escalation_causes"][-1]["code"], "LEARNED_REVOKE")
        self.assertIn("EAS-1", out["learned"][0]["text"])

    def test_revoked_request_does_not_self_escalate_from_its_own_feedback(self):
        same = self.apply(
            {"decision": "auto_approve"}, revoked=REVOKED, exclude_request_id="req-1"
        )
        self.assertIsNone(same.get("escalate_to"))
        self.assertEqual(same["learned"], [])
        nxt = self.apply(
            {"decision": "auto_approve"}, revoked=REVOKED, exclude_request_id="req-99"
        )
        self.assertEqual(nxt["escalate_to"], "B")
        self.assertEqual(nxt["escalation_causes"][-1]["code"], "LEARNED_REVOKE")

    def test_overruled_bad_case_is_not_escalated_again(self):
        verdict = {
            "decision": "escalate_to_human",
            "escalate_to": "B",
            "escalation_causes": [
                {"source": "BAD_CASE", "code": "BC_WFH_FREQUENT", "escalate_to": "B"}
            ],
        }
        out = self.apply(verdict, overruled=OVERRULED)
        self.assertIsNone(out["escalate_to"])
        self.assertEqual(out["decision"], "escalate_to_human")  # vẫn có người duyệt
        self.assertEqual(out["learned"][0]["suppressed"], ["BC_WFH_FREQUENT"])

    def test_other_bad_case_still_escalates(self):
        verdict = {
            "escalate_to": "B",
            "escalation_causes": [
                {
                    "source": "BAD_CASE",
                    "code": "BC_DEADLINE_CONFLICT",
                    "escalate_to": "B",
                }
            ],
        }
        self.assertEqual(self.apply(verdict, overruled=OVERRULED)["escalate_to"], "B")

    def test_regulation_cause_is_never_suppressed_by_memory(self):
        verdict = {
            "escalate_to": "C",
            "escalation_causes": [
                {"source": "BAD_CASE", "code": "BC_WFH_FREQUENT", "escalate_to": "B"},
                {"source": "REGULATION", "code": "QC05-4", "escalate_to": "C"},
            ],
        }
        self.assertEqual(self.apply(verdict, overruled=OVERRULED)["escalate_to"], "C")


CODES = frozenset({"SPECIAL_DISCOUNT", "LEAVE"})
TYPES = (
    RequestTypeName(
        "SPECIAL_DISCOUNT", "Phê duyệt chiết khấu thương mại đặc biệt", "A"
    ),
    RequestTypeName("EXPENSE_CLAIM", "Thanh toán chi phí", "A"),
)


class ReviewRuleValidationTests(SimpleTestCase):
    def test_valid_rule_gets_default_risk(self):
        rules = validate_review_rules(
            [{"request_type": "SPECIAL_DISCOUNT", "auto_approve": False}], CODES
        )
        self.assertEqual(rules[0]["min_risk"], 4)

    def test_rejects_unknown_type_field_and_widening(self):
        for bad in (
            [{"request_type": "NOPE", "auto_approve": False}],
            [{"request_type": "LEAVE", "auto_approve": False, "drop_table": 1}],
            [{"request_type": "LEAVE", "auto_approve": True, "due_within_hours": 24}],
            [{"request_type": "LEAVE", "auto_approve": False, "escalate_to": "D"}],
            [],
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_review_rules(bad, CODES)


class SkipReasonTests(SimpleTestCase):
    def test_reports_only_controlled_sentences_that_could_not_compile(self):
        # v3 hiểu phần trăm; câu có điều kiện định tính (nhóm khách hàng) vẫn phải lên hàng chờ của admin.
        self.assertIsNotNone(
            skip_reason(
                "Phê duyệt chiết khấu thương mại đặc biệt cho khách hàng thân thiết bắt "
                "buộc duyệt thủ công.",
                list(TYPES),
            )
        )
        self.assertIsNone(
            skip_reason(
                "Phê duyệt chiết khấu thương mại đặc biệt từ 25% trở lên bắt buộc "
                "duyệt thủ công.",
                list(TYPES),
            )
        )
        self.assertIsNone(
            skip_reason(
                "Thanh toán chi phí từ 40 triệu đồng trở lên bắt buộc duyệt thủ công.",
                list(TYPES),
            )
        )
        self.assertIsNone(skip_reason("Phòng họp giao ban sáng thứ Hai.", list(TYPES)))


def _actor(user_id: str, roles=("REQUESTER", "APPROVER")) -> Actor:
    return Actor(
        id=user_id,
        email="user@eas.com",
        display_name="Nhân sự 1",
        department_id=str(uuid4()),
        auth_version=1,
        roles=frozenset(roles),
        must_change_password=False,
    )


class _DummyCursorContext:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self._cursor

    def __exit__(self, *_exc):
        return False


class EscalationFeedbackPermissionTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def test_can_mark_escalation_unnecessary_checks_non_requester_and_non_superseded_step(
        self,
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = (True,)
        actor_id = str(uuid4())
        request_id = str(uuid4())

        self.assertFalse(can_mark_escalation_unnecessary(cursor, "", request_id))
        cursor.execute.assert_not_called()

        self.assertTrue(can_mark_escalation_unnecessary(cursor, actor_id, request_id))
        sql, params = cursor.execute.call_args[0]
        self.assertIn("i.state <> 'SUPERSEDED'", sql)
        self.assertIn("r.requester_id <> %s", sql)
        self.assertIn("s.assignee_id = %s", sql)
        self.assertEqual(params, [request_id, actor_id, actor_id])

    def test_ai_escalation_info_is_per_request_for_same_user_across_two_lifecycles(
        self,
    ):
        user_1 = str(uuid4())
        user_2 = str(uuid4())
        req_1 = str(uuid4())
        req_2 = str(uuid4())
        occurred = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
        details = {"from_lifecycle": "A", "to_lifecycle": "B", "causes": []}

        def run_info(
            req_id, actor_id, requester_id, reviewer_allowed, already_marked=False
        ):
            cursor = MagicMock()
            cursor.fetchone.side_effect = [
                (details, occurred),
                (True,),
                (1,),
                (already_marked,),
            ]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = _DummyCursorContext(cursor)
            with (
                patch("api_core.workflow.views.connection", mock_conn),
                patch("api_core.workflow.ai_feedback.available", return_value=True),
                patch(
                    "api_core.workflow.remediation.can_mark_escalation_unnecessary",
                    return_value=reviewer_allowed,
                ) as checker,
            ):
                info = _ai_escalation_info(
                    req_id, actor_id=actor_id, requester_id=requester_id
                )
            return info, checker

        # Vòng đời 1: user_1 là người gửi yêu cầu -> không bao giờ hiện nút, kể cả giữ quyền APPROVER
        info1, checker1 = run_info(req_1, user_1, user_1, reviewer_allowed=True)
        self.assertFalse(info1["can_mark_unnecessary"])
        checker1.assert_not_called()

        # Vòng đời 2: cùng user_1 nhưng ở hồ sơ khác (requester=user_2) nơi user_1 là người kiểm duyệt -> hiện nút
        info2, checker2 = run_info(req_2, user_1, user_2, reviewer_allowed=True)
        self.assertTrue(info2["can_mark_unnecessary"])
        checker2.assert_called_once()

        # Cùng user_1 ở hồ sơ khác nhưng đã đánh dấu rồi -> ẩn nút
        info3, checker3 = run_info(
            req_2, user_1, user_2, reviewer_allowed=True, already_marked=True
        )
        self.assertFalse(info3["can_mark_unnecessary"])
        checker3.assert_not_called()

        # Người không phải người kiểm duyệt -> ẩn nút
        info4, _ = run_info(req_2, str(uuid4()), user_2, reviewer_allowed=False)
        self.assertFalse(info4["can_mark_unnecessary"])

    def test_mark_escalation_unnecessary_forbids_requester_even_with_ops_admin_role(
        self,
    ):
        user_1 = str(uuid4())
        req_1 = str(uuid4())
        cursor = MagicMock()
        cursor.fetchone.return_value = (False,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = _DummyCursorContext(cursor)

        with (
            patch("django.db.transaction.atomic"),
            patch("api_core.workflow.remediation.connection", mock_conn),
            self.assertRaises(CommandError) as raised,
        ):
            mark_escalation_unnecessary(
                actor=_actor(user_1, roles=("REQUESTER", "APPROVER", "OPS_ADMIN")),
                request_id=req_1,
                reason="Lý do hợp lệ ít nhất 5 ký tự",
                correlation_id="corr-1",
            )

        self.assertEqual(raised.exception.status, 403)
        self.assertEqual(raised.exception.code, "FORBIDDEN")
