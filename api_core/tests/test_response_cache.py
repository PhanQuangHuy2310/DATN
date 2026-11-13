from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from api_core import read_cache
from api_core.response_cache import ApiResponseCacheMiddleware

PATH = "/api/v1/workspace/regulations"


def actor(user_id="u1", must_change=False, roles=frozenset({"REQUESTER"})):
    return SimpleNamespace(
        id=user_id, auth_version=1, must_change_password=must_change, roles=roles
    )


class ResponseCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.calls = 0

    def view(self, request):
        self.calls += 1
        who = getattr(getattr(request, "actor", None), "id", None)
        return JsonResponse({"n": self.calls, "who": who})

    def get(self, who, path=PATH, method="get"):
        middleware = ApiResponseCacheMiddleware(self.view)
        request = getattr(RequestFactory(), method)(path)
        with (
            mock.patch(
                "api_core.authn.service.load_actor_from_session", return_value=who
            ),
            mock.patch(
                "api_core.maintenance.is_maintenance_active", return_value=False
            ),
        ):
            return middleware(request)

    def test_second_identical_get_is_served_from_redis(self):
        first = self.get(actor())
        second = self.get(actor())
        self.assertEqual(self.calls, 1)
        self.assertEqual(first.content, second.content)
        self.assertEqual(second["X-EAS-Cache"], "hit")

    def test_entries_are_per_user(self):
        self.get(actor("u1"))
        other = self.get(actor("u2"))
        self.assertEqual(self.calls, 2)
        self.assertIn(b'"who": "u2"', other.content)

    def test_write_version_bump_invalidates(self):
        self.get(actor())
        read_cache.invalidate()
        self.get(actor())
        self.assertEqual(self.calls, 2)

    def test_bypassed_without_session_or_with_forced_password_change(self):
        middleware = ApiResponseCacheMiddleware(lambda r: JsonResponse({}, status=401))
        with mock.patch(
            "api_core.authn.service.load_actor_from_session", return_value=None
        ):
            self.assertEqual(middleware(RequestFactory().get(PATH)).status_code, 401)
        self.get(actor(must_change=True))
        self.get(actor(must_change=True))
        self.assertEqual(self.calls, 2)

    def test_live_and_non_get_paths_are_not_cached(self):
        for _ in range(2):
            self.get(actor(), path="/api/v1/admin/ai-engine/status")
        self.assertEqual(self.calls, 2)
