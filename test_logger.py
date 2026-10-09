import json
import logging
import unittest

from api_core.logger import JsonFormatter, SensitiveDataFilter, redact


class LoggerSecurityTests(unittest.TestCase):
    def test_redacts_database_url_and_secret_key(self):
        message = "dsn=postgresql://user:pass@db:5432/postgres key=sb_secret_example"
        cleaned = redact(message)
        self.assertNotIn("user:pass", cleaned)
        self.assertNotIn("sb_secret_example", cleaned)
        self.assertGreaterEqual(cleaned.count("[REDACTED]"), 2)

    def test_redacts_password_and_log_injection(self):
        cleaned = redact("password=hunter2\nFAKE | CRITICAL")
        self.assertNotIn("hunter2", cleaned)
        self.assertNotIn("\n", cleaned)
        self.assertIn("\\n", cleaned)

    def test_filter_removes_sensitive_args(self):
        record = logging.LogRecord(
            "test", logging.INFO, __file__, 1, "token=%s", ("abc",), None
        )
        self.assertTrue(SensitiveDataFilter().filter(record))
        self.assertNotIn("abc", record.getMessage())

    def test_formatter_outputs_valid_json(self):
        record = logging.LogRecord("eas", logging.INFO, __file__, 1, "ready", (), None)
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["message"], "ready")


if __name__ == "__main__":
    unittest.main()
