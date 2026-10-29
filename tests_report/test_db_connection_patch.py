"""Offline tests for connection lifecycle defaults (no live Supabase required)."""
import os
import runpy
import unittest
from unittest.mock import patch

from api_core.config.database import parse_database_url
from api_core.query_timing import QueryTiming

URL = 'postgresql://limited_user:fake-password@pool.example.test:5432/postgres?sslmode=require'


class DatabaseConnectionTuningTests(unittest.TestCase):
    def settings_for(self, env, **variables):
        settings_env = dict(
            EAS_ENV=env,
            DATABASE_URL=URL,
            DJANGO_DEBUG='true' if env == 'development' else 'false',
            DJANGO_SECRET_KEY='unit-test-only-placeholder',
            REDIS_URL='redis://localhost:6379/0',
        )
        settings_env.update(variables)
        with patch.dict(os.environ, settings_env, clear=True):
            return runpy.run_module('api_core.config.settings')

    def test_dev_does_not_hold_one_supabase_connection_per_thread(self):
        settings = self.settings_for('development')
        self.assertEqual(settings['DATABASES']['default']['CONN_MAX_AGE'], 0)
        self.assertTrue(settings['DATABASES']['default']['CONN_HEALTH_CHECKS'])

    def test_production_policy_is_unchanged(self):
        settings = self.settings_for('production')
        self.assertEqual(settings['DATABASES']['default']['CONN_MAX_AGE'], 60)

    def test_operator_can_override_age_explicitly(self):
        settings = self.settings_for('development', EAS_DB_CONN_MAX_AGE='10')
        self.assertEqual(settings['DATABASES']['default']['CONN_MAX_AGE'], 10)

    def test_negative_age_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'EAS_DB_CONN_MAX_AGE'):
            self.settings_for('development', EAS_DB_CONN_MAX_AGE='-5')

    def test_keepalive_helps_detect_disconnected_pooler(self):
        options = parse_database_url(URL)['OPTIONS']
        self.assertEqual(options['keepalives'], 1)
        self.assertEqual(options['prepare_threshold'], None)
        self.assertEqual(options['connect_timeout'], 10)

    def test_timing_never_stores_sql_or_parameters(self):
        timing = QueryTiming()
        result = timing(lambda sql, params, many, ctx: 'ok', 'SELECT secret', ['hidden'], False, {})
        self.assertEqual(result, 'ok')
        self.assertEqual(timing.count, 1)
        self.assertFalse(hasattr(timing, 'sql'))
        self.assertGreaterEqual(timing.duration_ms, 0)


if __name__ == '__main__':
    unittest.main()
