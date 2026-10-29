"""No external credentials/DB required: SRS NFR01 5/account and 30/IP."""
import unittest
from api_core.authn.login_throttle import (
    clear_account_failures, is_throttled, register_login_failure, throttle_keys,
)


class FakeCache:
    def __init__(self):
        self.values = {}

    def get(self, key, default=0):
        return self.values.get(key, default)

    def add(self, key, value, timeout=None):
        if key in self.values:
            return False
        self.values[key] = value
        return True

    def incr(self, key):
        self.values[key] += 1

    def delete(self, key):
        self.values.pop(key, None)


class LoginThrottleTests(unittest.TestCase):
    def setUp(self):
        self.cache = FakeCache()

    def test_account_limit_across_ips(self):
        for i in range(5):
            register_login_failure(self.cache, throttle_keys('Employee', f'192.0.2.{i}'), window_seconds=900)
        self.assertTrue(is_throttled(self.cache, throttle_keys('employee', '203.0.113.9'), account_limit=5, ip_limit=30))

    def test_ip_limit_across_accounts(self):
        for i in range(30):
            register_login_failure(self.cache, throttle_keys(f'person{i}', '192.0.2.10'), window_seconds=900)
        self.assertTrue(is_throttled(self.cache, throttle_keys('person-new', '192.0.2.10'), account_limit=5, ip_limit=30))
        self.assertFalse(is_throttled(self.cache, throttle_keys('person-new', '198.51.100.10'), account_limit=5, ip_limit=30))

    def test_success_only_resets_account_budget(self):
        keys = throttle_keys('Employee', '192.0.2.10')
        register_login_failure(self.cache, keys, window_seconds=900)
        clear_account_failures(self.cache, keys)
        self.assertEqual(self.cache.get(keys[0]), 0)
        self.assertEqual(self.cache.get(keys[1]), 1)

    def test_no_identifiers_in_cache_key(self):
        keys = throttle_keys('employee@example.com', '192.0.2.10')
        self.assertTrue(all('employee' not in k and '192.0.2' not in k for k in keys))


if __name__ == '__main__':
    unittest.main()
