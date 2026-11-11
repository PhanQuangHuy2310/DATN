"""Contract checks for read-only system smoke classifier."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts" / "system_smoke_local.py"
spec = importlib.util.spec_from_file_location("eas_smoke", path)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class SmokeTestClassifierTests(unittest.TestCase):
    def test_ready_endpoint_requires_ready_body(self):
        self.assertEqual(smoke.classify_http("Backend readiness", 200, b'{"status":"ready"}', {})[0], "PASS")
        self.assertEqual(smoke.classify_http("Backend readiness", 200, b'{"status":"not_ready"}', {})[0], "WARN")

    def test_csrf_rate_limit_is_reported_without_retrying(self):
        status, text = smoke.classify_http("Backend auth/CSRF", 429, b"", {"Retry-After": "60"})
        self.assertEqual(status, "WARN")
        self.assertIn("60", text)

    def test_html_entry_point(self):
        self.assertEqual(smoke.classify_http("Employee UI", 200, b"<!doctype html><html", {})[0], "PASS")
        self.assertEqual(smoke.classify_http("Employee UI", 200, b"{\"ok\":true}", {})[0], "FAIL")

    def test_unreachable(self):
        self.assertEqual(smoke.classify_http("AI Service", None, b"", {})[0], "FAIL")
