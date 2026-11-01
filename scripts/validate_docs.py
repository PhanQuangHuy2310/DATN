from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main() -> int:
    markdown_files = sorted(DOCS.rglob("*.md"))
    broken: list[str] = []
    fence_errors: list[str] = []

    for path in markdown_files:
        text = path.read_text(encoding="utf-8-sig")
        if text.count("```") % 2:
            fence_errors.append(str(path.relative_to(ROOT)))
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative = unquote(target.split("#", 1)[0])
            if relative and not (path.parent / relative).resolve().exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")

    diagram_text = "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in sorted((DOCS / "diagrams").glob("*.md"))
    )
    mermaid_count = diagram_text.count("```mermaid")

    failures = []
    if broken:
        failures.append(f"broken_links={len(broken)}")
    if fence_errors:
        failures.append(f"unbalanced_fences={len(fence_errors)}")

    print(f"markdown_files={len(markdown_files)}")
    print(f"mermaid_blocks={mermaid_count}")
    print(f"broken_links={len(broken)}")
    print(f"unbalanced_fences={len(fence_errors)}")
    for item in broken + fence_errors:
        print(f"- {item}")
    if failures:
        print("DOCS_GATE=FAIL: " + "; ".join(failures))
        return 1
    print("DOCS_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
