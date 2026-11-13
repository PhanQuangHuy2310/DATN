"""Fixed-window counters must never be left without an expiry."""

from django.test import SimpleTestCase

from api_core.authn.login_throttle import ensure_window, incr_window


class FakeRedisClient:
    """INCR / EXPIRE NX / MULTI subset of redis-py, with real TTL semantics."""

    def __init__(self):
        self.values, self.ttls = {}, {}

    def pipeline(self, transaction=True):
        client, ops = self, []

        class Pipe:
            def incr(self, key):
                ops.append(("incr", key))

            def expire(self, key, seconds, nx=False):
                ops.append(("expire", key, seconds, nx))

            def execute(self):
                return [getattr(client, op[0])(*op[1:]) for op in ops]

        return Pipe()

    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        self.ttls.setdefault(key, None)  # INCR on a missing key: no expiry
        return self.values[key]

    def expire(self, key, seconds, nx=False):
        if key not in self.values or (nx and self.ttls.get(key) is not None):
            return False
        self.ttls[key] = seconds
        return True


class FakeRedisCache:
    """Shape of django.core.cache.backends.redis.RedisCache used by the helper."""

    def __init__(self):
        self.client = FakeRedisClient()
        self._cache = self

    def get_client(self, key, write=False):
        return self.client

    def make_and_validate_key(self, key):
        return f":1:{key}"


class IncrWindowTests(SimpleTestCase):
    def test_counts_within_one_window_and_sets_expiry_once(self):
        store = FakeRedisCache()
        self.assertEqual([incr_window(store, "k", 60) for _ in range(3)], [1, 2, 3])
        self.assertEqual(store.client.ttls[":1:k"], 60)

    def test_key_recreated_after_expiry_always_gets_a_window(self):
        store = FakeRedisCache()
        incr_window(store, "k", 60)
        store.client.values.clear()  # window expired
        store.client.ttls.clear()
        self.assertEqual(incr_window(store, "k", 60), 1)
        self.assertEqual(store.client.ttls[":1:k"], 60)

    def test_stuck_counter_from_older_build_is_released(self):
        store = FakeRedisCache()
        store.client.values[":1:k"], store.client.ttls[":1:k"] = 1200, None
        ensure_window(store, "k", 60)
        self.assertEqual(store.client.ttls[":1:k"], 60)

    def test_locmem_fallback(self):
        from django.core.cache.backends.locmem import LocMemCache

        store = LocMemCache("t", {})
        self.assertEqual([incr_window(store, "k", 60) for _ in range(2)], [1, 2])
