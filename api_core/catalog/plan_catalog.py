"""Planning catalogue transcribed from plan.docx and enterprise 5-level audit.

Read-only blueprints never bypass the database's published-release, scope,
policy validation or request state machine. No AI auto approvals are enabled.
"""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def plan_items():
    data = json.loads(
        Path(__file__).with_name("plan_types.json").read_text(encoding="utf-8")
    )
    items = data["items"]
    if (
        data.get("count") != 18
        or len(items) != 18
        or len({x["code"] for x in items}) != 18
    ):
        raise RuntimeError("Invalid plan request catalogue")
    return items


@lru_cache(maxsize=1)
def enterprise_catalog():
    data = json.loads(
        Path(__file__).with_name("enterprise_types.json").read_text(encoding="utf-8")
    )
    items = data.get("items", [])
    if (
        data.get("count") != 12
        or len(items) != 12
        or len({x["code"] for x in items}) != 12
    ):
        raise RuntimeError("Invalid enterprise 5-level request catalogue")
    return data


# Request groups by nature (docs/PHAN_LOAI_YEU_CAU.md); same codes as eas.request_group.
CATALOG_V2_GROUPS = (
    "ABSENCE",
    "WORKTIME",
    "BORROW",
    "PROVISION",
    "PAYMENT",
    "PROCUREMENT",
    "PEOPLE",
    "SUPPORT",
    "WORK",
    "LEGAL",
    "SALES",
    "ASSET",
)


@lru_cache(maxsize=1)
def catalog_v2():
    """Seed catalogue: 12 groups by nature, 58 active types, 8 deprecated duplicates."""
    data = json.loads(
        Path(__file__).with_name("catalog_v2.json").read_text(encoding="utf-8")
    )
    items = data.get("items", [])
    active = [x for x in items if x.get("status") == "ACTIVE"]
    if (
        tuple(g["code"] for g in data.get("groups", [])) != CATALOG_V2_GROUPS
        or len(active) != 58
        or len({x["code"] for x in items}) != len(items)
        or any(x["category"] not in CATALOG_V2_GROUPS for x in items)
    ):
        raise RuntimeError("Invalid request catalogue groups")
    return data


def catalog_v2_item(code):
    return next((x for x in catalog_v2()["items"] if x["code"] == code), None)


def catalog_v2_active():
    return [x for x in catalog_v2()["items"] if x["status"] == "ACTIVE"]


def category_label(code):
    return next((g["label"] for g in catalog_v2()["groups"] if g["code"] == code), code)


def enterprise_items():
    return enterprise_catalog()["items"]


def enterprise_options():
    return enterprise_catalog().get("options", [])


def five_level_framework():
    return enterprise_catalog().get("five_level_framework", {})


def resolve_five_level_metadata(
    code: str,
    db_risk_weight: int | None = None,
    db_approval_level: int | None = None,
) -> tuple[int, int]:
    matrix = enterprise_catalog().get("type_level_matrix", {})
    default_entry = catalog_v2_item(code) or matrix.get(code, {})
    risk_w = (
        int(db_risk_weight)
        if isinstance(db_risk_weight, int) and 1 <= db_risk_weight <= 5
        else int(default_entry.get("risk_weight", 3))
    )
    app_lvl = (
        int(db_approval_level)
        if isinstance(db_approval_level, int) and 1 <= db_approval_level <= 5
        else int(default_entry.get("approval_level", 1))
    )
    return max(1, min(5, risk_w)), max(1, min(5, app_lvl))


def plan_item(code):
    return next((item for item in plan_items() if item["code"] == code), None)


def enterprise_item(code):
    return next((item for item in enterprise_items() if item["code"] == code), None)


def safe_display_name(code):
    item = plan_item(code) or enterprise_item(code)
    return item["name"] if item else code
