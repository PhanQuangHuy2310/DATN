"""Fixed-window counters must never be left without an expiry."""

from django.test import SimpleTestCase

from api_core.authn.login_throttle import incr_window


class FakeRedis:
    """Mimics django-redis: INCR on an expired key recreates it with no TTL."""

    def __init__(self):
        self.values, self.ttls, self.expired_between = {}, {}, False

    def add(self, key, value, timeout):
        if key in self.values:
            if self.expired_between:  # key expires right after add() fails
                self.values.pop(key)
                self.ttls.pop(key)
            return False
        self.values[key], self.ttls[key] = value, timeout
        return True

    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        self.ttls.setdefault(key, None)  # INCRBY: no expiry on a new key
        return self.values[key]

    def ttl(self, key):
        return self.ttls.get(key)

    def expire(self, key, timeout):
        self.ttls[key] = timeout


class IncrWindowTests(SimpleTestCase):
    def test_counts_within_one_window(self):
        store = FakeRedis()
        self.assertEqual([incr_window(store, "k", 60) for _ in range(3)], [1, 2, 3])
        self.assertEqual(store.ttl("k"), 60)

    def test_key_recreated_by_incr_gets_its_window_back(self):
        store = FakeRedis()
        incr_window(store, "k", 60)
        store.expired_between = True
        incr_window(store, "k", 60)
        self.assertEqual(store.ttl("k"), 60)
