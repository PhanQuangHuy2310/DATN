"""Gemini hết hạn mức (HTTP 429) hoặc lỗi giữa chừng: mọi chức năng vẫn chạy bằng phần nội bộ (19/11).

Gemini chỉ là phần phụ: phân tích quy định (RAG), gợi ý luật cho câu AI chưa hiểu, tóm tắt hồ sơ, đọc ảnh khi
PaddleOCR hỏng. Phân loại, chấm rủi ro, bad case, chuyển luồng và lượt học quy định là mô hình nội bộ.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (REPO, os.path.join(REPO, "ai_service")):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import regulation_llm
    from google.api_core.exceptions import TooManyRequests
    from routers import regulation_analysis, summarize

    HAS_AI_DEPS = True
except (
    ImportError
):  # venv gốc không cài fastapi / google: chạy bằng ai_service/.venv-ai
    HAS_AI_DEPS = False


def quota(*_args, **_kwargs):
    raise TooManyRequests("429 Resource has been exhausted (e.g. check quota).")


@unittest.skipUnless(
    HAS_AI_DEPS, "cần fastapi + google-generativeai (ai_service/.venv-ai)"
)
class GeminiOutageTests(unittest.TestCase):
    def test_regulation_analysis_falls_back_to_the_in_house_engine(self):
        calls = []

        def fail(*args, **kwargs):
            calls.append(1)
            quota()

        fallback = lambda text, types: {
            "version": "noi-bo",
            "proposals": [{"rule": "x"}],
        }
        with (
            patch.object(regulation_llm, "call_gemini", side_effect=fail),
            patch.object(regulation_llm.time, "sleep"),
        ):
            out = regulation_llm.analyze(
                "Nghỉ phép trên 3 ngày bắt buộc duyệt thủ công.",
                [],
                [],
                api_key="k",
                model_name="gemini-x",
                fallback=fallback,
                retries=2,
                retry_wait=0,
            )
        self.assertTrue(out["fallback_used"])
        self.assertEqual(out["error"], "TooManyRequests")
        self.assertEqual(out["proposals"], [{"rule": "x"}])
        self.assertEqual(
            len(calls), 3
        )  # thử lại 2 lần khi bị giới hạn tần suất rồi mới dùng phần nội bộ
        self.assertTrue(out["requires_admin_approval"])

    def test_rule_suggestion_for_unparsed_clause_returns_empty_not_an_error_page(self):
        body = regulation_analysis.ClauseIn(
            clause="Nhân viên mới chỉ được nghỉ sau 2 tháng.",
            types=[{"code": "LEAVE", "name": "Nghỉ phép"}],
        )
        settings = type("S", (), {"gemini_api_key": "k", "gemini_model": "gemini-x"})()
        with (
            patch.object(regulation_analysis, "get_settings", return_value=settings),
            patch("regulation_rules_llm.extract", side_effect=quota),
        ):
            out = asyncio.run(regulation_analysis.clause_rules(body))
        self.assertEqual(out["rules"], [])
        self.assertEqual(out["error"], "TooManyRequests")

    def test_summary_falls_back_to_local_extraction(self):
        body = summarize.SummarizeRequest(
            title="Xin nghỉ phép 2 ngày",
            request_type="LEAVE",
            requester_name="NV",
            description="Về quê có việc gia đình, đã bàn giao công việc cho đồng nghiệp.",
        )
        with (
            patch.object(summarize.settings, "gemini_api_key", "k"),
            patch(
                "google.generativeai.GenerativeModel.generate_content",
                side_effect=quota,
            ),
        ):
            out = summarize.summarize_request(body)
        self.assertEqual(
            out.tokens_used, 0
        )  # không token nào của Gemini: bản trích xuất cục bộ
        self.assertTrue(out.summary)


class GeminiKeyPoolRotationTests(unittest.TestCase):
    def test_rotates_on_quota_and_invalid_key_and_sticks_to_healthy_key(self):
        import gemini_key_pool

        pool = gemini_key_pool.GeminiKeyPool(quota_cooldown_sec=60.0)
        keys_str = "key1,key2,key3"
        attempted: list[str] = []

        def fake_call(k: str) -> str:
            attempted.append(k)
            if k == "key1":
                raise RuntimeError("403 API_KEY_INVALID: API key not valid")
            if k == "key2":
                raise RuntimeError("429 ResourceExhausted: Quota exceeded")
            return f"ok:{k}"

        res1 = pool.execute(fake_call, api_key=keys_str)
        self.assertEqual(res1, "ok:key3")
        self.assertEqual(attempted, ["key1", "key2", "key3"])

        # Lần gọi kế tiếp phải dùng ngay key3 đang khỏe mạnh, không thử lại key1 (invalid) hay key2 (cooldown)
        attempted.clear()
        res2 = pool.execute(fake_call, api_key=keys_str)
        self.assertEqual(res2, "ok:key3")
        self.assertEqual(attempted, ["key3"])

        st = pool.status(api_key=keys_str)
        self.assertEqual(st["total_keys"], 3)
        self.assertEqual(st["ready_keys"], 1)
        self.assertEqual(
            [item["status"] for item in st["keys"]], ["invalid", "cooldown", "ready"]
        )


if __name__ == "__main__":
    unittest.main()
