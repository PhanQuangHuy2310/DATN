"""Offline, no-Django tests for the Windows local Redis preflight."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_cache_local.py"
spec = importlib.util.spec_from_file_location("eas_cache_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class CachePreflightTests(unittest.TestCase):
    def test_local_cache_does_not_require_redis(self):
        self.assertTrue(preflight.check_cache("django.core.cache.backends.locmem.LocMemCache", None))

    def test_redis_cache_roundtrip(self):
        cache = Mock()
        cache.get.return_value = "OK"
        self.assertTrue(preflight.check_cache("django.core.cache.backends.redis.RedisCache", cache))
        cache.set.assert_called_once()
        self.assertEqual(cache.set.call_args.kwargs["timeout"], 5)

    def test_unavailable_redis_refuses_to_start_backend(self):
        cache = Mock()
        cache.set.side_effect = TimeoutError("contains a connection secret")
        self.assertFalse(preflight.check_cache("django.core.cache.backends.redis.RedisCache", cache, sleep=lambda _: None))
        self.assertEqual(cache.set.call_count, 3)

    def test_empty_response_is_not_treated_as_reachable(self):
        cache = Mock()
        cache.get.return_value = None
        self.assertFalse(preflight.check_cache("django.core.cache.backends.redis.RedisCache", cache, sleep=lambda _: None))
