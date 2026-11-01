"""Item 5.3: Redis port comes from the environment (6380 outside Docker)."""

from django.test import SimpleTestCase

from api_core.config.redis_url import resolve_redis_url


class RedisUrlTests(SimpleTestCase):
    def test_explicit_url_wins(self):
        env = {"REDIS_URL": " redis://redis:6379/0 ", "EAS_REDIS_PORT": "7000"}
        self.assertEqual(resolve_redis_url(env), "redis://redis:6379/0")

    def test_port_defaults_to_6380_outside_docker(self):
        self.assertEqual(
            resolve_redis_url({"EAS_REDIS_HOST": "127.0.0.1"}),
            "redis://127.0.0.1:6380/0",
        )
        self.assertEqual(
            resolve_redis_url({"EAS_REDIS_PORT": "6390"}), "redis://127.0.0.1:6390/0"
        )

    def test_no_redis_configured(self):
        self.assertEqual(resolve_redis_url({}), "")

    def test_invalid_port_rejected(self):
        with self.assertRaises(RuntimeError):
            resolve_redis_url({"EAS_REDIS_PORT": "70000"})

    def test_compose_publishes_redis_on_6380(self):
        from pathlib import Path

        compose = (
            Path(__file__).resolve().parents[2] / "docker-compose.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('"127.0.0.1:${EAS_REDIS_HOST_PORT:-6380}:6379"', compose)
