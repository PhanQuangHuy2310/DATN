"""Fail when the employee-portal build contains admin-screen code.

Run after `npm run build` in web_client (and web_admin for the positive check).
Usage: python scripts/check_client_bundle.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# One distinctive string per admin screen (IdentityAdmin, PlanCatalog,
# ApiAdministration, OrgChart, Operations, AdminEvents, Policy, AiPolicyAdmin).
ADMIN_MARKERS = (
    "Yêu cầu đặt lại mật khẩu",
    "Danh mục 10 nhóm (58 loại)",
    "/api/v1/admin/api-catalog",
    "/api/v1/admin/departments",
    "ops/outbox",
    "/api/v1/admin-events",
    "config-releases",
    "Tải bộ luật mới",
)


def bundle_text(dist: Path) -> str:
    return "".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (dist / "assets").glob("*.js")
    )


def main() -> int:
    client = ROOT / "web_client/dist"
    if not (client / "assets").is_dir():
        print("web_client/dist missing: run npm run build first")
        return 2
    leaked = [m for m in ADMIN_MARKERS if m in bundle_text(client)]
    if leaked:
        print(f"Employee bundle contains admin code: {leaked}")
        return 1
    admin = ROOT / "web_admin/dist"
    if (admin / "assets").is_dir():
        missing = [m for m in ADMIN_MARKERS if m not in bundle_text(admin)]
        if missing:
            print(f"Admin bundle is missing admin screens: {missing}")
            return 1
    print("Employee bundle has no admin screens.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
