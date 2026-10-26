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
        self.assertIn("DATABASE_QUERY_FAILED", source)
        self.assertIn("status=500", source)
        self.assertNotIn("str(exception)", source)

    def test_frontend_does_not_label_html_500_invalid_response(self):
        source = (ROOT / "web_client/src/api.js").read_text(encoding="utf-8")
        self.assertIn("SERVER_ERROR", source)
        self.assertIn("response.status >= 500", source)

if __name__ == "__main__": unittest.main()
