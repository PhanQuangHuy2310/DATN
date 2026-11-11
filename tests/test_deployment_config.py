"""Deployment configuration, checked statically (no Docker or nginx needed).

- ai-service image is multi-stage, cache-friendly and lean (item 4.6);
- the root build context excludes what no root-context Dockerfile copies;
- ingress separation: which upstream each nginx config sends a path to;
- portal code split: admin screens load only in the admin portal (item 3.1).
"""

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI = ROOT / "ai_service"
DOCKERFILE = (AI / "Dockerfile").read_text(encoding="utf-8")
ROOT_CONTEXT_DOCKERFILES = (
    "api_core/Dockerfile",
    "web_client/Dockerfile",
    "web_admin/Dockerfile",
)
EXCLUDED = ("ai_service/", "mobile_app/", "database/", "tests/", "scripts/")
ADMIN_SCREENS = (
    "AuditorWorkspace",
    "IdentityAdmin",
    "components/OrgChart.jsx",
    "ApiAdministration",
    "PlanCatalog",
)


class AiDockerfileTests(unittest.TestCase):
    def test_multi_stage_with_lean_runtime(self):
        self.assertEqual(
            re.findall(r"^FROM .* AS (\w+)$", DOCKERFILE, re.MULTILINE),
            ["builder", "runtime"],
        )
        runtime = DOCKERFILE.split("AS runtime", 1)[1]
        self.assertIn("COPY --from=builder /opt/venv /opt/venv", runtime)
        self.assertNotIn("pip install", runtime)
        self.assertIn("USER aiuser", runtime)

    def test_paddle_layer_is_installed_before_other_requirements(self):
        paddle = DOCKERFILE.index("pip install -r requirements-paddle.txt")
        rest = DOCKERFILE.index("pip install -r requirements.txt")
        self.assertLess(paddle, rest)
        self.assertLess(
            DOCKERFILE.index("COPY requirements-paddle.txt"),
            DOCKERFILE.index("COPY requirements.txt"),
        )
        self.assertEqual(
            DOCKERFILE.count("--mount=type=cache,target=/root/.cache/pip"), 2
        )

    def test_apt_and_pip_caches_do_not_reach_layers(self):
        for run in re.findall(r"apt-get install[^\n]*(?:\n\s+[^\n]*)*", DOCKERFILE):
            self.assertIn("--no-install-recommends", run)
        self.assertEqual(DOCKERFILE.count("rm -rf /var/lib/apt/lists/*"), 2)

    def test_opencv_runtime_library_in_both_stages(self):
        # paddleocr pulls opencv-python, which needs libGL at import time.
        installs = re.findall(r"apt-get install[^\n]*", DOCKERFILE)
        self.assertEqual(len(installs), 2)
        for line in installs:
            self.assertIn("libgl1", line)

    def test_runtime_user_has_writable_home_for_ocr_models(self):
        # A --system user defaults to HOME=/nonexistent and PaddleOCR then
        # cannot download its models (PermissionError at the first OCR call).
        runtime = DOCKERFILE.split("AS runtime", 1)[1]
        self.assertIn("--home /home/aiuser aiuser", runtime)
        self.assertIn("HOME=/home/aiuser", runtime)
        self.assertIn("/home/aiuser/.paddlex", runtime)

    def test_ocr_models_persist_in_a_named_volume(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("ai_ocr_models:/home/aiuser/.paddlex", compose)
        self.assertRegex(compose, r"(?m)^volumes:\s+ai_ocr_models:")

    def test_dockerignore_keeps_local_venv_out_of_context(self):
        ignored = (AI / ".dockerignore").read_text(encoding="utf-8").split()
        for entry in (".venv*", "**/__pycache__", ".env", "training/data"):
            self.assertIn(entry, ignored)

    def test_paddle_is_pinned_to_the_patched_3x_stack(self):
        # paddlepaddle 2.6.2 / protobuf 3.20.2 carried CVEs (audit S7, 05/11/2026).
        main = (AI / "requirements.txt").read_text(encoding="utf-8")
        paddle = (AI / "requirements-paddle.txt").read_text(encoding="utf-8")
        for pin in ("paddlepaddle==3.3.1", "paddleocr==3.7.0", "protobuf==5.29.6"):
            self.assertIn(pin, paddle)
            self.assertNotIn(pin, main)
        for vulnerable in (
            "paddlepaddle==2.",
            "paddleocr==2.",
            "protobuf==3.",
            "imgaug",
        ):
            self.assertNotIn(vulnerable, paddle)
        self.assertIn("ARG ENABLE_PADDLE_OCR=true", DOCKERFILE)
        self.assertIn("pip==26.2 setuptools==84.1.0", DOCKERFILE)


class RootDockerContextTests(unittest.TestCase):
    def test_heavy_unused_folders_are_ignored(self):
        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
        for entry in EXCLUDED:
            self.assertIn(entry, ignored)

    def test_no_root_context_dockerfile_copies_an_ignored_path(self):
        for name in ROOT_CONTEXT_DOCKERFILES:
            text = (ROOT / name).read_text(encoding="utf-8")
            sources = [
                src
                for line in re.findall(r"^COPY (?!--from)(.+)$", text, re.MULTILINE)
                for src in line.split()[:-1]
                if not src.startswith("--")
            ]
            for src in sources:
                with self.subTest(dockerfile=name, source=src):
                    self.assertFalse(
                        any(src.startswith(entry) for entry in EXCLUDED), src
                    )


# Ingress: the helper reproduces nginx location selection (exact, longest
# prefix, ``^~`` short-circuit, then regex in file order) so the tests do not
# need a running nginx.
LOCATION = re.compile(r"location\s+(=|\^~|~\*?)?\s*(\S+)\s*\{")


def _locations(conf: str) -> list[tuple[str, str, str]]:
    found = []
    for match in LOCATION.finditer(conf):
        depth, index = 1, match.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(conf[index], 0)
            index += 1
        found.append(
            (match.group(1) or "", match.group(2), conf[match.end() : index - 1])
        )
    return found


def route(conf_path: str, uri: str) -> str:
    """Return 'proxy' or 'blocked' for a request URI."""
    locations = _locations((ROOT / conf_path).read_text(encoding="utf-8"))
    chosen = next((loc for loc in locations if loc[0] == "=" and loc[1] == uri), None)
    if chosen is None:
        prefixes = [
            loc for loc in locations if loc[0] in ("", "^~") and uri.startswith(loc[1])
        ]
        longest = max(prefixes, key=lambda loc: len(loc[1]), default=None)
        chosen = longest
        if longest is None or longest[0] != "^~":
            regex = next(
                (
                    loc
                    for loc in locations
                    if loc[0].startswith("~") and re.search(loc[1], uri)
                ),
                None,
            )
            chosen = regex or longest
    body = chosen[2] if chosen else ""
    return "proxy" if "proxy_pass" in body else "blocked"


class EmployeePortalIngressTests(unittest.TestCase):
    conf = "web_client/nginx.conf"

    def test_admin_ops_and_internal_apis_are_blocked(self):
        for uri in (
            "/api/v1/admin/users",
            "/api/v1/admin/memberships/1",
            "/api/v1/ops/requests",
            "/api/v1/internal/requests/1/auto-approve",
        ):
            with self.subTest(uri=uri):
                self.assertEqual(route(self.conf, uri), "blocked")

    def test_employee_apis_still_proxy(self):
        for uri in (
            "/api/v1/requests",
            "/api/v1/auth/login",
            "/api/v1/admin-events",
            "/api/v1/meta/colleagues",
            "/health/ready",
        ):
            with self.subTest(uri=uri):
                self.assertEqual(route(self.conf, uri), "proxy")


class AdminPortalIngressTests(unittest.TestCase):
    conf = "web_admin/nginx.conf"

    def test_admin_apis_proxy_but_internal_is_blocked(self):
        self.assertEqual(route(self.conf, "/api/v1/admin/users"), "proxy")
        self.assertEqual(route(self.conf, "/api/v1/ops/requests"), "proxy")
        self.assertEqual(
            route(self.conf, "/api/v1/internal/requests/1/auto-approve"), "blocked"
        )

    def test_admin_image_uses_its_own_config(self):
        dockerfile = (ROOT / "web_admin/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY web_admin/nginx.conf", dockerfile)

    def test_admin_image_copies_shared_public_assets(self):
        dockerfile = (ROOT / "web_admin/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY web_client/public ./web_client/public", dockerfile)


class GatewayIngressTests(unittest.TestCase):
    conf = "api_gateway/nginx.conf"

    def test_internal_api_returns_not_found(self):
        self.assertEqual(
            route(self.conf, "/api/v1/internal/requests/1/auto-approve"), "blocked"
        )

    def test_business_and_attachment_apis_proxy(self):
        self.assertEqual(route(self.conf, "/api/v1/requests"), "proxy")
        self.assertEqual(route(self.conf, "/api/v1/requests/1/attachments"), "proxy")

    def test_worker_reaches_api_over_docker_network(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("EAS_API_INTERNAL_URL: http://api:8000", compose)


class PortalCodeSplitTests(unittest.TestCase):
    def test_app_has_no_static_import_of_admin_screens(self):
        app = (ROOT / "web_client/src/App.jsx").read_text(encoding="utf-8")
        imports = [line for line in app.splitlines() if line.startswith("import ")]
        for screen in ADMIN_SCREENS:
            self.assertFalse([line for line in imports if screen in line], screen)
        admin_import = next(
            (line for line in imports if "components/Admin.jsx" in line), ""
        )
        for name in ("AdminEvents", "Operations", "Policy"):
            self.assertNotIn(name, admin_import)

    def test_secondary_client_screens_are_lazy_chunks(self):
        app = (ROOT / "web_client/src/App.jsx").read_text(encoding="utf-8")
        static = [line for line in app.splitlines() if line.startswith("import ")]
        for name in (
            "RequestEditor",
            "RequestDetail",
            "WorkflowDiagrams",
            "AiProcessGuide",
            "ClientOrgChart",
            "DelegationSettings",
        ):
            with self.subTest(screen=name):
                self.assertFalse([line for line in static if f"/{name}.jsx" in line])
                self.assertIn(
                    f'const {name} = lazy(() => import("./components/{name}.jsx"))', app
                )

    def test_only_admin_entry_injects_admin_screens(self):
        client = (ROOT / "web_client/src/main.jsx").read_text(encoding="utf-8")
        admin = (ROOT / "web_admin/src/main.jsx").read_text(encoding="utf-8")
        self.assertNotIn("adminScreens", client)
        self.assertIn("adminScreens={adminScreens}", admin)

    def test_lazy_map_covers_every_admin_screen(self):
        lazy = (ROOT / "web_client/src/adminScreens.jsx").read_text(encoding="utf-8")
        for name in (
            *ADMIN_SCREENS,
            "AdminEvents",
            "Operations",
            "Policy",
            "AiPolicyAdmin",
        ):
            self.assertIn(name.replace(".jsx", ""), lazy)

    def test_built_employee_bundle_has_no_admin_code_when_present(self):
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
