"""Ingress separation: which upstream each nginx config sends a path to.

The helper reproduces nginx location selection (exact, longest prefix,
``^~`` short-circuit, then regex in file order) so the tests do not need a
running nginx.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


if __name__ == "__main__":
    unittest.main()
