"""Lượt học quy định khi Gemini hết hạn mức / lỗi: câu AI chưa hiểu vẫn vào hàng chờ admin, chỉ thiếu gợi ý (19/11)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from api_core.workflow import ai_learning
from api_core.workflow.regulation_compiler import RequestTypeName

TYPES = [RequestTypeName("LEAVE", "Nghỉ phép", "A")]
CLAUSE = "Nhân viên mới chỉ được nghỉ phép sau 2 tháng làm việc."


def _http(response=None, error=None):
    client = MagicMock()
    if error:
        client.post.side_effect = error
    else:
        client.post.return_value = response
    ctx = MagicMock()
    ctx.__enter__.return_value = client
    return ctx


class SuggestRulesOutageTests(SimpleTestCase):
    def test_ai_service_unreachable(self):
        with patch(
            "api_core.workflow.ai_learning._ai_http",
            return_value=_http(error=TimeoutError()),
        ):
            self.assertEqual(
                ai_learning._suggest_rules(CLAUSE, TYPES), {"error": "TimeoutError"}
            )

    def test_gemini_quota_reported_by_the_ai_service(self):
        body = {"rules": [], "rejected": [], "error": "TooManyRequests"}
        resp = SimpleNamespace(status_code=200, json=lambda: body)
        with patch("api_core.workflow.ai_learning._ai_http", return_value=_http(resp)):
            self.assertEqual(
                ai_learning._suggest_rules(CLAUSE, TYPES),
                {"rules": [], "rejected": [], "error": "TooManyRequests"},
            )

    def test_ai_service_error_status(self):
        resp = SimpleNamespace(status_code=429, json=dict)
        with patch("api_core.workflow.ai_learning._ai_http", return_value=_http(resp)):
            self.assertEqual(
                ai_learning._suggest_rules(CLAUSE, TYPES), {"error": "HTTP 429"}
            )
