"""Static regression tests; run without Django, npm or network.

These tests do NOT claim live SQL execution or visual browser validation.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sql_and_params(relpath: str, function_name: str):
    source = (ROOT / relpath).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    found = {}
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("sql", "params")
        ):
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
        sql, count = sql_and_params(
            "api_core/workflow/ops_service.py", "list_ops_metadata"
        )
        self.assertEqual(sql.count("%s"), count)
        self.assertIn("%s::uuid IS NULL", sql)
        self.assertIn("STRPOS(LOWER(r.code)", sql)

    def test_other_nullable_filters_are_typed(self):
        for path in [
            "api_core/workflow/reporting.py",
            "api_core/workflow/config_service.py",
        ]:
            source = (ROOT / path).read_text(encoding="utf-8")
            self.assertNotIn("(%s IS NULL", source)
        self.assertIn(
            "%s::boolean IS FALSE",
            (ROOT / "api_core/workflow/reporting.py").read_text(encoding="utf-8"),
        )

    def test_password_visibility_available_everywhere(self):
        component = (ROOT / "web_client/src/components/ux.jsx").read_text(
            encoding="utf-8"
        )
        self.assertIn('type={visible ? "text" : "password"}', component)
        self.assertIn("aria-pressed={visible}", component)
        for path in [
            "web_client/src/App.jsx",
            "web_client/src/components/Admin.jsx",
            "web_client/src/components/IdentityAdmin.jsx",
        ]:
            self.assertIn("PasswordField", (ROOT / path).read_text(encoding="utf-8"))

    def test_list_pagination_and_responsiveness(self):
        css = (ROOT / "web_client/src/eas-enhancements.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:800px)", css)
        self.assertIn(".responsive-records", css)
        self.assertIn(".pagination-extended", css)
        for path in [
            "web_client/src/App.jsx",
            "web_client/src/components/Admin.jsx",
            "web_client/src/components/IdentityAdmin.jsx",
        ]:
            self.assertIn("PageControls", (ROOT / path).read_text(encoding="utf-8"))

    def test_auth_me_optional_bootstrap_and_favicon_prevent_401_404(self):
        auth_service = (ROOT / "api_core/authn/service.py").read_text(encoding="utf-8")
        self.assertIn("X-Auth-Optional", auth_service)
        self.assertIn('"authenticated": False', auth_service)

        urls_py = (ROOT / "api_core/config/urls.py").read_text(encoding="utf-8")
        self.assertIn('path("", health_views.live', urls_py)
        self.assertIn('path("favicon.ico"', urls_py)

        self.assertTrue((ROOT / "web_client/public/favicon.svg").is_file())
        self.assertTrue((ROOT / "web_client/public/favicon.ico").is_file())

        app_jsx = (ROOT / "web_client/src/App.jsx").read_text(encoding="utf-8")
        self.assertIn("X-Auth-Optional", app_jsx)
        self.assertIn("_bootstrapSessionPromise", app_jsx)

        vite_cfg = (ROOT / "web_client/vite.config.js").read_text(encoding="utf-8")
        self.assertIn('"/ai"', vite_cfg)
        self.assertIn("127.0.0.1:8001", vite_cfg)

    def test_sql_queries_do_not_reference_nonexistent_columns(self):
        config_src = (ROOT / "api_core/workflow/config_service.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("updated_at = statement_timestamp()", config_src)

        reporting_src = (ROOT / "api_core/workflow/reporting.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("WHERE scope_key = 'ADMIN'", reporting_src)

        privacy_src = (
            ROOT / "api_core/management/commands/privacy_case.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("u.email", privacy_src)
        self.assertNotIn("email = %s", privacy_src)

    def test_service_and_worker_nullable_uuid_parameters_are_typed(self):
        service_src = (ROOT / "api_core/workflow/service.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "%s::uuid IS NULL AND a.state IN ('READY', 'RUNNING') OR a.id = %s::uuid",
            service_src,
        )

        worker_src = (ROOT / "api_core/worker.py").read_text(encoding="utf-8")
        self.assertIn("WHEN %s::uuid IS NULL THEN TRUE", worker_src)
        self.assertIn("LEFT JOIN eas.request r ON r.id = %s::uuid", worker_src)
        self.assertIn(
            "LEFT JOIN eas.request_participant p ON p.request_id = %s::uuid", worker_src
        )


if __name__ == "__main__":
    unittest.main()
