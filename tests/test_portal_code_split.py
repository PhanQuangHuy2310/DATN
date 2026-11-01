"""Item 3.1: admin screens load only in the admin portal."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_SCREENS = (
    "AuditorWorkspace",
    "IdentityAdmin",
    "components/OrgChart.jsx",
    "ApiAdministration",
    "PlanCatalog",
)


class PortalCodeSplitTests(unittest.TestCase):
    def test_app_has_no_static_import_of_admin_screens(self):
        app = (ROOT / "web_client/src/App.jsx").read_text(encoding="utf-8")
        imports = [line for line in app.splitlines() if line.startswith("import ")]
        for screen in ADMIN_SCREENS:
            self.assertFalse([line for line in imports if screen in line], screen)
        admin_import = next(line for line in imports if "components/Admin.jsx" in line)
        for name in ("AdminEvents", "Operations", "Policy"):
            self.assertNotIn(name, admin_import)

    def test_only_admin_entry_injects_admin_screens(self):
        client = (ROOT / "web_client/src/main.jsx").read_text(encoding="utf-8")
        admin = (ROOT / "web_admin/src/main.jsx").read_text(encoding="utf-8")
        self.assertNotIn("adminScreens", client)
        self.assertIn("adminScreens={adminScreens}", admin)

    def test_lazy_map_covers_every_admin_screen(self):
        lazy = (ROOT / "web_client/src/adminScreens.jsx").read_text(encoding="utf-8")
        for name in (*ADMIN_SCREENS, "AdminEvents", "Operations", "Policy"):
            self.assertIn(name.replace(".jsx", ""), lazy)

    def test_built_employee_bundle_has_no_admin_code_when_present(self):
        import importlib.util

        if not (ROOT / "web_client/dist/assets").is_dir():
            self.skipTest("web_client not built")
        spec = importlib.util.spec_from_file_location(
            "check_client_bundle", ROOT / "scripts/check_client_bundle.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.main(), 0)


if __name__ == "__main__":
    unittest.main()
