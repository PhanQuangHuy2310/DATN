"""Item 4.6: ai-service image is multi-stage, cache-friendly and lean."""

import re
import unittest
from pathlib import Path

AI = Path(__file__).resolve().parents[1] / "ai_service"
DOCKERFILE = (AI / "Dockerfile").read_text(encoding="utf-8")


class AiDockerfileTests(unittest.TestCase):
    def test_multi_stage_with_lean_runtime(self):
        self.assertEqual(
            re.findall(r"^FROM .* AS (\w+)$", DOCKERFILE, re.MULTILINE), ["builder", "runtime"]
        )
        runtime = DOCKERFILE.split("AS runtime", 1)[1]
        self.assertIn("COPY --from=builder /opt/venv /opt/venv", runtime)
        self.assertNotIn("pip install", runtime)
        self.assertIn("USER aiuser", runtime)

    def test_paddle_layer_is_installed_before_other_requirements(self):
        paddle = DOCKERFILE.index("pip install -r requirements-paddle.txt")
        rest = DOCKERFILE.index("pip install -r requirements.txt")
        self.assertLess(paddle, rest)
        self.assertLess(
            DOCKERFILE.index("COPY requirements-paddle.txt"),
            DOCKERFILE.index("COPY requirements.txt"),
        )
        self.assertEqual(
            DOCKERFILE.count("--mount=type=cache,target=/root/.cache/pip"), 2
        )

    def test_apt_and_pip_caches_do_not_reach_layers(self):
        for run in re.findall(r"apt-get install[^\n]*(?:\n\s+[^\n]*)*", DOCKERFILE):
            self.assertIn("--no-install-recommends", run)
        self.assertEqual(DOCKERFILE.count("rm -rf /var/lib/apt/lists/*"), 2)

    def test_opencv_runtime_library_in_both_stages(self):
        # paddleocr pulls opencv-python, which needs libGL at import time.
        installs = re.findall(r"apt-get install[^\n]*", DOCKERFILE)
        self.assertEqual(len(installs), 2)
        for line in installs:
            self.assertIn("libgl1", line)

    def test_dockerignore_keeps_local_venv_out_of_context(self):
        ignored = (AI / ".dockerignore").read_text(encoding="utf-8").split()
        for entry in (".venv*", "**/__pycache__", ".env", "training/data"):
            self.assertIn(entry, ignored)

    def test_requirements_still_pin_the_full_stack(self):
        main = (AI / "requirements.txt").read_text(encoding="utf-8")
        paddle = (AI / "requirements-paddle.txt").read_text(encoding="utf-8")
        self.assertIn("-r requirements-paddle.txt", main)
        for pin in ("paddlepaddle==2.6.2", "paddleocr==2.8.1", "numpy==1.26.4"):
            self.assertIn(pin, paddle)
            self.assertNotIn(pin, main)


if __name__ == "__main__":
    unittest.main()
