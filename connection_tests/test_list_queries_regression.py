"""Static regression checks requiring no live Supabase credentials."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ListQueryRegression(unittest.TestCase):
    def test_request_list_avoids_distinct_uuid_order_mismatch(self):
        source = (ROOT / "api_core/workflow/views.py").read_text(encoding="utf-8")
        self.assertIn("SELECT r.id::text, r.code, rt.code", source)
        self.assertNotIn("SELECT DISTINCT r.id::text, r.code, rt.code", source)
        self.assertIn("ORDER BY r.updated_at DESC, r.id DESC", source)

    def test_json_database_failure_for_api(self):
        source = (ROOT / "api_core/middleware.py").read_text(encoding="utf-8")
        mapping = (ROOT / "api_core/db_diagnostics.py").read_text(encoding="utf-8")
        self.assertIn("api_db_failure(exception)", source)
        self.assertIn('return "DATABASE_QUERY_FAILED", 500', mapping)
        self.assertIn('return "DATABASE_TEMPORARILY_UNAVAILABLE", 503', mapping)
        self.assertNotIn("str(exception)", source)
        self.assertNotIn("str(exc)", mapping)

    def test_frontend_does_not_label_html_500_invalid_response(self):
        source = (ROOT / "web_client/src/api.js").read_text(encoding="utf-8")
        self.assertIn("SERVER_ERROR", source)
        self.assertIn("response.status >= 500", source)

if __name__ == "__main__": unittest.main()
