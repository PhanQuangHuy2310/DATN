"""Root build context excludes what no root-context Dockerfile copies."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_CONTEXT_DOCKERFILES = (
    "api_core/Dockerfile",
    "web_client/Dockerfile",
    "web_admin/Dockerfile",
)
EXCLUDED = ("ai_service/", "mobile_app/", "database/", "tests/", "scripts/")


class RootDockerContextTests(unittest.TestCase):
    def test_heavy_unused_folders_are_ignored(self):
        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
        for entry in EXCLUDED:
            self.assertIn(entry, ignored)

    def test_no_root_context_dockerfile_copies_an_ignored_path(self):
        for name in ROOT_CONTEXT_DOCKERFILES:
            text = (ROOT / name).read_text(encoding="utf-8")
            sources = [
                src
                for line in re.findall(r"^COPY (?!--from)(.+)$", text, re.M)
                for src in line.split()[:-1]
                if not src.startswith("--")
            ]
            for src in sources:
                with self.subTest(dockerfile=name, source=src):
                    self.assertFalse(
                        any(src.startswith(entry) for entry in EXCLUDED), src
                    )


if __name__ == "__main__":
    unittest.main()
