"""Planning catalogue transcribed from plan.docx, NOT an active policy release.

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

def plan_item(code):
    return next((item for item in plan_items() if item["code"] == code), None)

def safe_display_name(code):
    item = plan_item(code)
    return item["name"] if item else code
