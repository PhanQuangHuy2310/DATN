"""Redis outage: shared security state fails closed with a 503, caches fall back."""

from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from redis.exceptions import ConnectionError as RedisConnectionError

from api_core.catalog import integrations
from api_core.middleware import ApiDatabaseErrorMiddleware


class CacheOutageTests(SimpleTestCase):
    def test_redis_error_in_api_view_is_a_retryable_503(self):
        request = RequestFactory().post("/api/v1/auth/login")
        response = ApiDatabaseErrorMiddleware(lambda r: None).process_exception(
            request, RedisConnectionError("down")
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "5")
        self.assertIn(b"CACHE_UNAVAILABLE", response.content)

    def test_disabled_apis_reads_db_when_cache_is_down(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (True,)
        cursor.fetchall.return_value = [("HRM", "hr", "HRM")]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        broken = MagicMock()
        broken.get.side_effect = RedisConnectionError("down")
        broken.set.side_effect = RedisConnectionError("down")
        broken.delete.side_effect = RedisConnectionError("down")
        with (
            patch.object(integrations, "cache", broken),
            patch.object(integrations, "connection", connection),
        ):
            self.assertEqual(integrations.disabled_apis(), [("HRM", "hr", "HRM")])
            integrations.invalidate()  # must not raise either
