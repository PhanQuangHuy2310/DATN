"""AI regulation learning: rule compiler, announcement builder, AI verification."""

import json
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase

from api_core.workflow import ai_learning
from api_core.workflow.ai_learning import (
    RequestTypeName,
    TransientLearningError,
    build_announcement,
    compile_regulations,
    steps_detail,
)

REG_002 = {
    "code": "REG-002",
    "title": "Quy định phân loại và hạn mức phê duyệt yêu cầu A, B, C",
    "content": (
        "Các yêu cầu thuộc Phân loại A được AI đối chiếu tự động theo trọng số. "
        "Phân loại B yêu cầu Trưởng bộ phận phê duyệt trong 24h. Phân loại C áp dụng "
        "cho ngân sách từ 50.000.000 VNĐ trở lên và bắt buộc qua Ban Giám Đốc phê duyệt."
    ),
}
TYPES = [RequestTypeName("LEAVE", "Nghỉ phép"), RequestTypeName("PURCHASE", "Mua sắm")]


class CompilerTests(SimpleTestCase):
    def test_real_regulation_yields_board_rule(self):
        rules = compile_regulations([REG_002], TYPES)
        self.assertEqual(len(rules), 1)
        rule = rules[0]
        self.assertEqual(rule["id"], "REG-002-3")
        self.assertEqual(rule["amount_gt"], 49_999_999)
        self.assertEqual(rule["min_risk"], 5)
        self.assertIs(rule["auto_approve"], False)
        self.assertNotIn("request_type", {k for k, v in rule.items() if v})

    def test_units_bounds_days_and_type_scope(self):
        reg = {
            "code": "REG-9",
            "title": "t",
            "content": (
                "Yêu cầu Mua sắm trên 5 triệu bắt buộc duyệt thủ công. "
                "Nghỉ phép quá 3 ngày phải được phê duyệt. "
                "Chi phí dưới 2 triệu không được tự động duyệt nếu thiếu chứng từ. "
                "Mọi yêu cầu được AI đối chiếu tự động."
            ),
        }
        rules = {r["id"]: r for r in compile_regulations([reg], TYPES)}
        self.assertEqual(rules["REG-9-1-PURCHASE"]["amount_gt"], 5_000_000)
        self.assertEqual(rules["REG-9-1-PURCHASE"]["min_risk"], 4)
        self.assertEqual(rules["REG-9-2-LEAVE"]["days_gt"], 3)
        self.assertNotIn("REG-9-3", rules)  # upper bound only: nothing to enforce
        self.assertIs(rules["REG-9-4"]["auto_approve"], True)
        for rule in rules.values():
            self.assertLessEqual(len(rule["id"]), 50)

    def test_sentences_without_signal_are_ignored(self):
        reg = {
            "code": "REG-001",
            "title": "t",
            "content": "Làm việc từ 08:00 đến 17:30.",
        }
        self.assertEqual(compile_regulations([reg], TYPES), [])


class AnnouncementTests(SimpleTestCase):
    def test_new_manual_rule_produces_process_guidance(self):
        rules = compile_regulations([REG_002], TYPES)
        out = build_announcement(
            version="2.1",
            previous_regulations=[],
            regulations=[REG_002],
            previous_rules=[],
            rules=rules,
            type_names={t.code: t.name for t in TYPES},
        )
        self.assertEqual(out["title"], "Hệ thống đã cập nhật quy định v2.1")
        kinds = [c["kind"] for c in out["changes"]]
        self.assertEqual(kinds, ["REGULATION_ADDED", "RULE_ADDED"])
        self.assertEqual(len(out["guidance"]), 1)
        self.assertIn("50.000.000 đ", out["guidance"][0]["title"])
        self.assertIn("Tạo yêu cầu", out["guidance"][0]["steps"][0])

    def test_unchanged_rules_say_process_is_unchanged(self):
        rules = compile_regulations([REG_002], TYPES)
        edited = {**REG_002, "title": "Tên mới"}
        out = build_announcement(
            version="2.2",
            previous_regulations=[REG_002],
            regulations=[edited],
            previous_rules=rules,
            rules=rules,
            type_names={},
        )
        self.assertEqual([c["kind"] for c in out["changes"]], ["REGULATION_UPDATED"])
        self.assertEqual(out["guidance"], [])
        self.assertIn("không thay đổi", out["summary"])

    def test_removed_manual_rule_tells_users_auto_approval_is_possible(self):
        rules = compile_regulations([REG_002], TYPES)
        out = build_announcement(
            version="3.0",
            previous_regulations=[REG_002],
            regulations=[],
            previous_rules=rules,
            rules=[],
            type_names={},
        )
        self.assertIn("REGULATION_REMOVED", [c["kind"] for c in out["changes"]])
        self.assertIn("Không còn bắt buộc", out["guidance"][0]["title"])

    def test_steps_detail_marks_failure(self):
        self.assertEqual(
            [s["status"] for s in steps_detail(3, failed=True)],
            ["DONE", "DONE", "FAILED", "WAITING"],
        )
        self.assertTrue(all(s["status"] == "DONE" for s in steps_detail(4)))


def _fake_ai(*, enforce=True, loaded_version=None):
    state = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/ai/policy/rules":
            state["policy"] = json.loads(request.content)
            return httpx.Response(200, json=state["policy"])
        if request.method == "GET" and request.url.path == "/ai/policy/rules":
            policy = dict(state["policy"])
            if loaded_version:
                policy["version"] = loaded_version
            return httpx.Response(200, json=policy)
        if request.url.path == "/ai/auto-approve/evaluate":
            ids = (
                ", ".join(r["id"] for r in state["policy"]["rules"]) if enforce else ""
            )
            return httpx.Response(
                200,
                json={
                    "decision": "escalate_to_human" if enforce else "auto_approve",
                    "detail_reasons": [f"Quy định áp dụng luật: {ids}"],
                    "policy_version": state["policy"]["version"],
                },
            )
        return httpx.Response(404)

    return lambda: httpx.Client(
        base_url="http://ai", transport=httpx.MockTransport(handler)
    )


class ApplyToAiTests(SimpleTestCase):
    def setUp(self):
        self.policy = {
            "version": "v2.1",
            "rules": compile_regulations([REG_002], TYPES),
        }

    def test_verified_when_engine_enforces_rule(self):
        with patch.object(ai_learning, "_ai_http", _fake_ai()):
            result = ai_learning.apply_to_ai(self.policy)
        self.assertEqual(result, {"rules_loaded": 1, "enforcement_checks": 1})

    def test_rejected_when_engine_ignores_rule(self):
        with (
            patch.object(ai_learning, "_ai_http", _fake_ai(enforce=False)),
            self.assertRaises(RuntimeError),
        ):
            ai_learning.apply_to_ai(self.policy)

    def test_rejected_when_engine_kept_old_version(self):
        with (
            patch.object(ai_learning, "_ai_http", _fake_ai(loaded_version="v1.0")),
            self.assertRaises(RuntimeError),
        ):
            ai_learning.apply_to_ai(self.policy)

    def test_unreachable_service_is_retryable(self):
        def down():
            def handler(request):
                raise httpx.ConnectError("refused", request=request)

            return httpx.Client(
                base_url="http://ai", transport=httpx.MockTransport(handler)
            )

        with (
            patch.object(ai_learning, "_ai_http", down),
            self.assertRaises(TransientLearningError),
        ):
            ai_learning.apply_to_ai(self.policy)
