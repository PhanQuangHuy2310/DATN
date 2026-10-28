"""Static regression tests; run without Django, npm or network.

These tests do NOT claim live SQL execution or visual browser validation.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def sql_and_params(relpath: str, function_name: str):
    source = (ROOT / relpath).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == function_name)
    found = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("sql", "params"):
                found[node.targets[0].id] = node.value
    return found["sql"].value, len(found["params"].elts)


class EASRegressionTests(unittest.TestCase):
    def test_request_list_query_bindings(self):
        sql, count = sql_and_params("api_core/workflow/views.py", "request_list")
        self.assertEqual(sql.count("%s"), count)
        self.assertIn("%s::timestamptz IS NULL", sql)
        self.assertIn("%s::uuid IS NULL", sql)
        self.assertIn("%s::text = 'mine'", sql)
        self.assertIn("STRPOS(LOWER(r.code)", sql)
        self.assertIn("wi.revision_id = r.current_revision_id", sql)
        self.assertIn("r.status = 'PENDING_APPROVAL'", sql)
        self.assertIn("r.status = 'READY_FOR_EXECUTION'", sql)
        self.assertIn("r.status = 'WAITING_FOR_ACCEPTANCE'", sql)
        self.assertIn("rp.read_revoked_at IS NULL", sql)

    def test_ops_query_bindings(self):
        sql, count = sql_and_params("api_core/workflow/ops_service.py", "list_ops_metadata")
        self.assertEqual(sql.count("%s"), count)
        self.assertIn("%s::uuid IS NULL", sql)
        self.assertIn("STRPOS(LOWER(r.code)", sql)

    def test_other_nullable_filters_are_typed(self):
        for path in ["api_core/workflow/reporting.py", "api_core/workflow/config_service.py"]:
            source = (ROOT / path).read_text(encoding="utf-8")
            self.assertNotIn("(%s IS NULL", source)
        self.assertIn("%s::boolean IS FALSE", (ROOT / "api_core/workflow/reporting.py").read_text())

    def test_password_visibility_available_everywhere(self):
        component = (ROOT / "web_client/src/components/ux.jsx").read_text()
        self.assertIn('type={visible ? "text" : "password"}', component)
        self.assertIn("aria-pressed={visible}", component)
        for path in ["web_client/src/App.jsx", "web_client/src/components/Admin.jsx", "web_client/src/components/IdentityAdmin.jsx"]:
            self.assertIn("PasswordField", (ROOT / path).read_text())

    def test_list_pagination_and_responsiveness(self):
        css = (ROOT / "web_client/src/eas-enhancements.css").read_text()
        self.assertIn("@media(max-width:800px)", css)
        self.assertIn(".responsive-records", css)
        self.assertIn(".pagination-extended", css)
        for path in ["web_client/src/App.jsx", "web_client/src/components/Admin.jsx", "web_client/src/components/IdentityAdmin.jsx"]:
            self.assertIn("PageControls", (ROOT / path).read_text())


if __name__ == "__main__":
    unittest.main()
