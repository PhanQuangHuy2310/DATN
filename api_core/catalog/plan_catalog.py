"""Planning catalogue transcribed from plan.docx and enterprise 5-level audit.

Read-only blueprints never bypass the database's published-release, scope,
policy validation or request state machine. No AI auto approvals are enabled.
"""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def plan_items():
    data = json.loads(Path(__file__).with_name("plan_types.json").read_text(encoding="utf-8"))
    items = data["items"]
    if data.get("count") != 18 or len(items) != 18 or len({x["code"] for x in items}) != 18:
        raise RuntimeError("Invalid plan request catalogue")
    return items


@lru_cache(maxsize=1)
def enterprise_catalog():
    data = json.loads(Path(__file__).with_name("enterprise_types.json").read_text(encoding="utf-8"))
    items = data.get("items", [])
    if data.get("count") != 12 or len(items) != 12 or len({x["code"] for x in items}) != 12:
        raise RuntimeError("Invalid enterprise 5-level request catalogue")
    return data


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
    default_entry = matrix.get(code, {})
    risk_w = int(db_risk_weight) if isinstance(db_risk_weight, int) and 1 <= db_risk_weight <= 5 else int(default_entry.get("risk_weight", 3))
    app_lvl = int(db_approval_level) if isinstance(db_approval_level, int) and 1 <= db_approval_level <= 5 else int(default_entry.get("approval_level", 1))
    return max(1, min(5, risk_w)), max(1, min(5, app_lvl))


def plan_item(code):
    return next((item for item in plan_items() if item["code"] == code), None)


def enterprise_item(code):
    return next((item for item in enterprise_items() if item["code"] == code), None)


def safe_display_name(code):
    item = plan_item(code) or enterprise_item(code)
    return item["name"] if item else code
