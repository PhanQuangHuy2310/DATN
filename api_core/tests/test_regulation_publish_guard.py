"""Nạp quy định (19/11, nhóm báo "không nạp được" và quy định lỗi vẫn được áp dụng).

* mã mặc định là mã REG còn trống, không theo số phiên bản (CSDL mới v1.0 từng gợi ý REG-002 đã có -> 409 mọi lần);
* "AI kiểm tra trước" của quy định mới báo trùng mã kèm mã còn trống;
* văn bản đang hiệu lực mà có lỗi (nạp trước khi có bước kiểm tra) được đánh dấu để admin sửa.
"""

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from api_core.administration import regulations_ai as ra
from api_core.workflow.regulation_compiler import RequestTypeName

TYPES = [
    RequestTypeName("REFUND_COMPENSATION", "Hoàn tiền / Đền bù", "A", 2),
    RequestTypeName("LEAVE", "Nghỉ phép", "A", 2),
]


def _actor(*roles):
    return SimpleNamespace(
        id="u-1",
        email="admin@eas.com",
        display_name="Admin",
        roles=frozenset(roles),
        must_change_password=False,
    )


class NextCodeTests(SimpleTestCase):
    def test_fresh_database_gets_the_first_free_code(self):
        self.assertEqual(
            ra.next_regulation_code(["REG-001", "REG-002", "REG-003"]), "REG-004"
        )
        self.assertEqual(
            ra.next_regulation_code(["REG-001", "QC05-6F1D23", "REG-014", "reg-020"]),
            "REG-021",
        )
        self.assertEqual(ra.next_regulation_code([]), "REG-001")


class LegacyIssueTests(SimpleTestCase):
    def test_regulations_published_before_the_check_are_flagged(self):
        contradiction = {
            "code": "REG-007",
            "title": "Quy định kiểm thử mâu thuẫn về hoàn tiền",
            "content": (
                "Điều 1: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 5 triệu đồng được phép tự động duyệt. "
                "Điều 2: Yêu cầu Hoàn tiền / Đền bù có giá trị trên 3 triệu đồng không được tự động duyệt."
            ),
        }
        question_marks = {
            "code": "REG-013",
            "title": "Quy định mâu thuẫn cũ",
            "content": "Di?u 1: Y?u c?u Ngh? ph?p b?t bu?c duy?t th? c?ng.",
        }
        mojibake = {
            "code": "REG-014",
            "title": "Quy định lỗi ký tự",
            "content": "Điều 1: YÃªu cáº§u Nghá»‰ phÃ©p bắt buộc duyệt thủ công.",
        }
        good = {
            "code": "REG-001",
            "title": "Giờ làm việc",
            "content": "Thời gian làm việc từ 8 giờ đến 17 giờ 30.",
        }
        self.assertEqual(
            [i["kind"] for i in ra.regulation_issues(contradiction, TYPES)],
            ["CONTRADICTION"],
        )
        self.assertEqual(
            [i["kind"] for i in ra.regulation_issues(question_marks, TYPES)],
            ["GARBLED"],
        )
        self.assertEqual(
            [i["kind"] for i in ra.regulation_issues(mojibake, TYPES)], ["GARBLED"]
        )
        self.assertEqual(ra.regulation_issues(good, TYPES), [])


class ValidateCodeTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    def _post(self, body, taken):
        cur = MagicMock()
        cur.fetchone.return_value = taken
        cur.fetchall.return_value = [("REG-001",), ("REG-002",), ("REG-003",)]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        ok = {"ok": True, "errors": [], "warnings": [], "supersedes": [], "rules": 1}
        with (
            patch(
                "api_core.authn.service.load_actor_from_session",
                return_value=_actor("OPS_ADMIN"),
            ),
            patch.object(ra, "connection", conn),
            patch.object(ra, "_content_check", return_value=ok),
        ):
            return self.client.post(
                "/api/v1/admin/regulations/validate",
                data=body,
                content_type="application/json",
            )

    def test_new_regulation_with_a_taken_code_is_reported_with_a_free_one(self):
        body = {
            "code": "REG-002",
            "title": "Quy định mới",
            "category": "Quy định chung",
            "content": "Nghỉ phép trên 3 ngày bắt buộc trưởng bộ phận phê duyệt thủ công.",
            "creating": True,
        }
        res = self._post(
            body, ("Quy định phân loại và hạn mức phê duyệt yêu cầu A, B, C",)
        )
        self.assertEqual(res.status_code, 200)
        validation = res.json()["validation"]
        self.assertFalse(validation["ok"])
        self.assertEqual(validation["errors"][0]["kind"], "CODE_EXISTS")
        self.assertEqual(validation["suggested_code"], "REG-004")

    def test_editing_an_existing_regulation_is_not_a_code_clash(self):
        body = {
            "code": "REG-002",
            "title": "Quy định cũ",
            "category": "Quy định chung",
            "content": "Nghỉ phép trên 3 ngày bắt buộc trưởng bộ phận phê duyệt thủ công.",
        }
        res = self._post(body, ("Quy định phân loại",))
        self.assertTrue(res.json()["validation"]["ok"])


class VersionAndKeepTests(SimpleTestCase):
    """Migration 27: chỉ "cập nhật lớn" mới tăng số đầu; quyết định giữ/bỏ điều cũ được lưu theo AI hoặc admin."""

    def test_big_update_sets_the_major_bump_for_the_transaction(self):
        cur = MagicMock()
        self.assertEqual(ra._version_mode(cur, {}), "MINOR")
        cur.execute.assert_not_called()
        self.assertEqual(ra._version_mode(cur, {"big_update": True}), "MAJOR")
        self.assertIn("eas.version_bump", cur.execute.call_args.args[0])

    def test_keep_decisions_follow_ai_unless_admin_overrides(self):
        cur = MagicMock()
        cur.fetchone.return_value = (True,)
        check = {
            "supersedes": [
                {
                    "key": "QD-CU|" + "a" * 64,
                    "recommendation": "KEEP",
                    "reason": "giữ chốt chia nhỏ",
                    "related": {"sentence": "câu cũ 1"},
                },
                {
                    "key": "QD-CU|" + "b" * 64,
                    "recommendation": "DROP",
                    "reason": "đổi ngưỡng",
                    "related": {},
                },
                {
                    "key": "QD-CU|" + "c" * 64,
                    "recommendation": "KEEP",
                    "reason": "x",
                    "related": {},
                },
            ]
        }
        request = SimpleNamespace(actor=_actor("POLICY_ADMIN"))
        decided = ra._store_keep_decisions(
            cur,
            request,
            "QD-MOI",
            check,
            {
                "supersede_decisions": {
                    "QD-CU|" + "b" * 64: "KEEP",
                    "QD-CU|" + "c" * 64: "DROP",
                }
            },
        )
        self.assertEqual(
            [(d["decision"], d["by"]) for d in decided],
            [("KEEP", "AI"), ("KEEP", "ADMIN"), ("DROP", "ADMIN")],
        )
        inserts = [
            c.args[1]
            for c in cur.execute.call_args_list
            if "INSERT INTO eas.regulation_keep_decision" in c.args[0]
        ]
        self.assertEqual(
            [(i[2], i[4]) for i in inserts], [("a" * 64, "AI"), ("b" * 64, "ADMIN")]
        )


class AnnouncementSinceLoginTests(SimpleTestCase):
    def test_unread_announcements_start_after_the_previous_login(self):
        from api_core.workflow import ai_learning

        cur = MagicMock()
        cur.fetchone.side_effect = [(True,), (True,)]
        cur.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        with patch.object(ai_learning, "connection", conn):
            ai_learning.list_announcements(_actor("REQUESTER"), unread_only=True)
        sql = cur.execute.call_args_list[-1].args[0]
        self.assertIn("previous_login_at", sql)
