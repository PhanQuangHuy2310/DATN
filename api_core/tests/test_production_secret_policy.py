from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[2]

_PROBE = (
    "import django, os;"
    "os.environ['DJANGO_SETTINGS_MODULE']='api_core.config.settings';"
    "django.setup()"
)


def _boot(extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("EAS_", "DJANGO_", "INTERNAL_API"))
    }
    # Never read the developer's .env: the probe must see only these variables.
    env["EAS_SKIP_DOTENV"] = "1"
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


class ProductionSecretPolicyTests(unittest.TestCase):
    """Production must refuse to start with weak or publicly known AI secrets."""

    base: ClassVar[dict[str, str]] = {
        "EAS_ENV": "production",
        "DATABASE_URL": "postgresql://u:p@db.example.invalid:5432/postgres?sslmode=require",
        "DJANGO_SECRET_KEY": "x" * 64,
        "REDIS_URL": "redis://redis:6379/0",
    }

    def test_rejects_publicly_known_dev_secret(self):
        result = _boot(
            {
                **self.base,
                "EAS_AI_INTERNAL_SECRET": "eas-local-dev-shared-internal-secret-2026",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EAS_AI_INTERNAL_SECRET", result.stderr)

    def test_rejects_short_secret(self):
        result = _boot({**self.base, "EAS_AI_INTERNAL_SECRET": "short"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EAS_AI_INTERNAL_SECRET", result.stderr)

    def test_rejects_missing_secret(self):
        result = _boot(self.base)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()


class DotenvIsolationTests(unittest.TestCase):
    def test_probe_ignores_local_dotenv(self):
        import tempfile

        from project_env import load_project_env

        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "EAS_ISOLATION_PROBE=from-file" + chr(10), encoding="utf-8"
            )
            saved = dict(os.environ)
            try:
                os.environ.pop("EAS_ISOLATION_PROBE", None)
                os.environ["EAS_SKIP_DOTENV"] = "1"
                load_project_env(env_file)
                self.assertNotIn("EAS_ISOLATION_PROBE", os.environ)
                os.environ.pop("EAS_SKIP_DOTENV")
                load_project_env(env_file)
                self.assertEqual(os.environ["EAS_ISOLATION_PROBE"], "from-file")
            finally:
                os.environ.clear()
                os.environ.update(saved)
