"""vibe-check #15/#9: ai_service hides docs/schema and protects /metrics in
production, and its CORS policy never allows credentials."""

import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_DIR = os.path.join(REPO_ROOT, "ai_service")

PROBE = """
import json
from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
paths = ["/docs", "/redoc", "/openapi.json", "/metrics", "/health"]
codes = {p: client.get(p).status_code for p in paths}
pre = client.options("/ai/classify/", headers={
    "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
codes["cors_credentials"] = pre.headers.get("access-control-allow-credentials")
print(json.dumps(codes))
"""


def _probe(env_name):
    env = {
        **os.environ,
        "EAS_ENV": env_name,
        "INTERNAL_API_SECRET": "x" * 48,
        "PYTHONPATH": os.pathsep.join([AI_DIR, REPO_ROOT]),
    }
    out = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=AI_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


try:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import loguru  # noqa: F401

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "fastapi, httpx and loguru are required")
class AiServiceExposureTests(unittest.TestCase):
    def test_production_hides_docs_and_protects_metrics(self):
        codes = _probe("production")
        # Disabled routes sit behind the internal-secret middleware: 401/404.
        for path in ("/docs", "/redoc", "/openapi.json", "/metrics"):
            self.assertIn(codes[path], (401, 404), path)
        self.assertEqual(codes["/health"], 200)
        self.assertIsNone(codes["cors_credentials"])

    def test_development_keeps_docs_for_local_work(self):
        codes = _probe("development")
        self.assertEqual(codes["/docs"], 200)
        self.assertEqual(codes["/openapi.json"], 200)
