"""General purchasing approval ladder (owner decision A3, thesis R03–R05).

    amount <  5,000,000 VND  -> the type's own default route
    amount >= 5,000,000 VND  -> default route + FINANCE (chief accountant)
    amount > 50,000,000 VND  -> the above + DIRECTOR (CEO)

Applied only to general purchasing types. A type whose default route is
already stricter keeps it (levels are only ever added, never removed), and
non-amount rules (e.g. privileged-app access) are preserved. EXPENSE_CLAIM and
BUSINESS_TRIP keep their own, stricter policies.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

LADDER_MID_VND = 5_000_000
LADDER_HIGH_VND = 50_000_000
MAX_APPROVERS = 5

GENERAL_PURCHASING_TYPES = frozenset(
    {
        "PURCHASE_REQUEST",
        "EQUIPMENT",
        "OFFICE_SUPPLIES",
        "ASSET_PURCHASE",
        "SAAS_LICENSE_BUY",
    }
)
PRESERVED_STRICTER = {
    "EXPENSE_CLAIM": "Luôn 2 cấp (Trưởng bộ phận → Kế toán) kể cả dưới 5 triệu; "
    "lên Giám đốc từ trên 20 triệu — chặt hơn R03–R05, giữ nguyên.",
    "BUSINESS_TRIP": "Lên Kế toán + Giám đốc từ trên 30 triệu — chặt hơn R05; "
    "tuyến mặc định qua Nhân sự (HR) thay vì Kế toán, cần xác nhận riêng.",
}
AMOUNT_OPERATORS = {"amount_gt", "amount_gte"}


def _with(approvers: list[str], slot: str) -> list[str]:
    return approvers if slot in approvers else [*approvers, slot]


def apply_purchasing_ladder(route_rules: dict[str, Any]) -> dict[str, Any]:
    rules = route_rules["rules"]
    default = next(r for r in rules if r.get("default"))
    base = list(default["approvers"])
    mid = _with(base, "FINANCE")
    high = _with(mid, "DIRECTOR")
    if len(high) > MAX_APPROVERS:
        raise ValueError("Ladder would exceed the five-approver limit")
    ladder: list[dict[str, Any]] = []
    if high != mid:
        ladder.append(
            {
                "id": "R05-GT-50M",
                "when": {"amount_gt": LADDER_HIGH_VND},
                "approvers": high,
            }
        )
    if mid != base:
        ladder.append(
            {
                "id": "R04-GTE-5M",
                "when": {"amount_gte": LADDER_MID_VND},
                "approvers": mid,
            }
        )
    kept = [
        r
        for r in rules
        if not r.get("default") and not AMOUNT_OPERATORS & set(r.get("when", {}))
    ]
    ordered = [*ladder, *sorted(kept, key=lambda r: r["priority"])]
    result = deepcopy(route_rules)
    result["rules"] = [
        {**deepcopy(rule), "priority": 10 * (index + 1)}
        for index, rule in enumerate(ordered)
    ] + [deepcopy(default)]
    return result


def describe_rules(route_rules: dict[str, Any]) -> list[str]:
    out = []
    for rule in sorted(
        route_rules.get("rules", []),
        key=lambda r: (bool(r.get("default")), r.get("priority", 0)),
    ):
        cond = (
            "mặc định"
            if rule.get("default")
            else ", ".join(f"{k} {v}" for k, v in rule.get("when", {}).items())
        )
        out.append(f"{cond}: {' → '.join(rule.get('approvers', []))}")
    return out
