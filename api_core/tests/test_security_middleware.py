from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from api_core.middleware import ApiRateLimitMiddleware, ApiSecurityHeadersMiddleware


def _ok(_request):
    return HttpResponse("ok")


class SecurityHeadersTests(SimpleTestCase):
    def test_defense_in_depth_headers_are_present(self):
        response = ApiSecurityHeadersMiddleware(_ok)(RequestFactory().get("/api/v1/x"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
        self.assertIn("camera=()", response["Permissions-Policy"])
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")

    def test_existing_csp_is_not_overwritten(self):
        def with_csp(_request):
            response = HttpResponse("ok")
            response["Content-Security-Policy"] = "default-src 'none'"
            return response

        response = ApiSecurityHeadersMiddleware(with_csp)(
            RequestFactory().get("/api/v1/x")
        )
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none'")


@override_settings(ENVIRONMENT="development", EAS_API_RATE_LIMIT_PER_MINUTE=3)
class RateLimitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_blocks_after_limit_with_retry_after(self):
        middleware = ApiRateLimitMiddleware(_ok)
        request = RequestFactory().get("/api/v1/requests")
        statuses = [middleware(request).status_code for _ in range(5)]
        self.assertEqual(statuses[:3], [200, 200, 200])
        self.assertEqual(statuses[3:], [429, 429])
        blocked = middleware(request)
        self.assertEqual(blocked["Retry-After"], "60")

    def test_non_api_paths_are_not_limited(self):
        middleware = ApiRateLimitMiddleware(_ok)
        request = RequestFactory().get("/health/live")
        self.assertTrue(all(middleware(request).status_code == 200 for _ in range(10)))

    def test_limits_are_tracked_per_client_ip(self):
        middleware = ApiRateLimitMiddleware(_ok)
        first = RequestFactory().get("/api/v1/x", REMOTE_ADDR="10.0.0.1")
        second = RequestFactory().get("/api/v1/x", REMOTE_ADDR="10.0.0.2")
        for _ in range(4):
            middleware(first)
        self.assertEqual(middleware(first).status_code, 429)
        self.assertEqual(middleware(second).status_code, 200)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_trusted_proxy_does_not_collapse_all_users_into_one_bucket(self):
        middleware = ApiRateLimitMiddleware(_ok)
        proxy = "172.18.0.2"
        alice = RequestFactory().get(
            "/api/v1/x", REMOTE_ADDR=proxy, HTTP_X_FORWARDED_FOR="203.0.113.10"
        )
        bob = RequestFactory().get(
            "/api/v1/x", REMOTE_ADDR=proxy, HTTP_X_FORWARDED_FOR="203.0.113.20"
        )
        for _ in range(4):
            middleware(alice)
        self.assertEqual(middleware(alice).status_code, 429)
        self.assertEqual(middleware(bob).status_code, 200)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_client_supplied_forwarded_entries_cannot_evade_the_limit(self):
        middleware = ApiRateLimitMiddleware(_ok)
        proxy = "172.18.0.2"
        statuses = [
            middleware(
                RequestFactory().get(
                    "/api/v1/x",
                    REMOTE_ADDR=proxy,
                    HTTP_X_FORWARDED_FOR=f"198.51.100.{n}, 203.0.113.99",
                )
            ).status_code
            for n in range(6)
        ]
        self.assertEqual(statuses[3:], [429, 429, 429])

    def test_forwarded_header_ignored_without_trusted_proxy(self):
        middleware = ApiRateLimitMiddleware(_ok)
        statuses = [
            middleware(
                RequestFactory().get(
                    "/api/v1/x",
                    REMOTE_ADDR="10.9.9.9",
                    HTTP_X_FORWARDED_FOR=f"1.1.1.{n}",
                )
            ).status_code
            for n in range(5)
        ]
        self.assertEqual(statuses[3:], [429, 429])

    def test_fails_open_when_cache_backend_is_down(self):
        middleware = ApiRateLimitMiddleware(_ok)
        with patch(
            "api_core.middleware.cache.get", side_effect=ConnectionError("redis down")
        ):
            response = middleware(RequestFactory().get("/api/v1/x"))
        self.assertEqual(response.status_code, 200)
