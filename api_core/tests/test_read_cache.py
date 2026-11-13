from django.core.cache import cache
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from api_core import read_cache
from api_core.middleware import ApiDatabaseErrorMiddleware


class ReadCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.calls = 0

    def load(self):
        self.calls += 1
        return [{"n": self.calls}]

    def test_second_read_is_served_from_cache(self):
        self.assertEqual(read_cache.cached("x", self.load, "A"), [{"n": 1}])
        self.assertEqual(read_cache.cached("x", self.load, "A"), [{"n": 1}])
        self.assertEqual(self.calls, 1)
        read_cache.cached("x", self.load, "B")  # other key parts load separately
        self.assertEqual(self.calls, 2)

    def test_invalidate_forces_fresh_read(self):
        read_cache.cached("x", self.load)
        read_cache.invalidate()
        self.assertEqual(read_cache.cached("x", self.load), [{"n": 2}])

    def run_request(self, method, path, status=200):
        middleware = ApiDatabaseErrorMiddleware(
            lambda r: JsonResponse({}, status=status)
        )
        middleware(getattr(RequestFactory(), method.lower())(path))

    def test_only_successful_api_writes_invalidate(self):
        read_cache.cached("x", self.load)
        for method, path, status in [
            ("GET", "/api/v1/workspace/request-catalog", 200),
            ("POST", "/api/v1/workspace/regulations", 422),
            ("POST", "/api/v1/internal/delegations/tick", 200),
            ("POST", "/api/v1/auth/login", 200),
        ]:
            self.run_request(method, path, status)
        read_cache.cached("x", self.load)
        self.assertEqual(self.calls, 1)

        self.run_request("PATCH", "/api/v1/admin/mock-apis/X", 200)
        read_cache.cached("x", self.load)
        self.assertEqual(self.calls, 2)
