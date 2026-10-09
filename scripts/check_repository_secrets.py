"""Fail CI when tracked files look like secrets or local environment files.

The script never prints matched secret values.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

TRACKED_ENV = re.compile(r"(^|/)\.env(?:\.|$)")
SECRET_PATTERNS = {
    "Supabase secret key": re.compile(rb"sb_secret_[A-Za-z0-9_-]{20,}"),
    "JWT-like token": re.compile(
        rb"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"
    ),
    "Database URL with password": re.compile(rb"postgres(?:ql)?://[^:\s]+:[^@\s]{8,}@"),
}
MAX_SCAN_BYTES = 2 * 1024 * 1024


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True)
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[tuple[str, str]] = []
    for name in tracked_files():
        normalized = name.replace("\\", "/")
        if TRACKED_ENV.search(normalized) and not normalized.endswith(".example"):
            findings.append((normalized, "tracked environment file"))
            continue

        path = Path(name)
        if (
            not path.is_file()
            or path.stat().st_size > MAX_SCAN_BYTES
            or path.suffix == ".pdf"
        ):
            continue
        if path.name.endswith(".example") or ".example." in path.name:
            continue
        data = path.read_bytes()
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                findings.append((normalized, label))

    if findings:
        print("SECRET_GATE=FAIL")
        for path, label in sorted(set(findings)):
            print(f"- {path}: {label}")
        print(
            "Rotate exposed credentials, then remove secret files from the Git index/history through an approved branch workflow."
        )
        return 1

    print("SECRET_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
