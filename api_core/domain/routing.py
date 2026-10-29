from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


class RoutingError(ValueError):
    pass


APPROVER_SLOTS = {
    "CISO",
    "CTO",
    "DIRECTOR",
    "DIRECT_MANAGER",
    "FINANCE",
    "HR_MANAGER",
    "IT_MANAGER",
    "LEGAL",
    "MARKETING_MANAGER",
    "OPERATIONS_MANAGER",
    "PROCUREMENT_MANAGER",
    "PROJECT_MANAGER",
    "SECURITY",
    "WAREHOUSE_MANAGER",
}
EXECUTOR_SLOTS = {None} | {
    "EXECUTOR_ADMIN",
    "EXECUTOR_ASSET",
    "EXECUTOR_FACILITY",
    "EXECUTOR_FINANCE",
    "EXECUTOR_HR",
    "EXECUTOR_IT",
    "EXECUTOR_LEGAL",
    "EXECUTOR_MARKETING",
    "EXECUTOR_PROCUREMENT",
    "EXECUTOR_TECH",
    "EXECUTOR_WAREHOUSE",
}
ACCEPTOR_SLOTS = {None} | {
    "CTO",
    "DIRECT_MANAGER",
    "LEGAL",
    "PROJECT_MANAGER",
    "REQUESTER",
}
SUPPORTED_OPERATORS = {"amount_gt", "amount_gte", "days_gt", "app_code_in"}
MONETARY_PAYLOAD_FIELDS = (
    "amount_vnd",
    "amount",
    "estimated_budget",
    "refund_amount",
    "contract_value",
    "estimated_cost",
    "estimated_price", "deal_value_vnd", "salary_budget_vnd", "residual_value_vnd",
)


def extract_amount_vnd(
    payload: dict[str, Any] | None,
    explicit_amount: int | None = None,
    *,
    allow_zero: bool = False,
) -> int | None:
    if (
        explicit_amount is not None
        and not isinstance(explicit_amount, bool)
        and isinstance(explicit_amount, int)
        and (explicit_amount >= 0 if allow_zero else explicit_amount > 0)
    ):
        return explicit_amount
    if not isinstance(payload, dict):
        return None
    for field in MONETARY_PAYLOAD_FIELDS:
        val = payload.get(field)
        if val is not None and not isinstance(val, bool) and isinstance(val, int):
            if (val >= 0) if allow_zero else (val > 0):
                return val
    return None


@dataclass(frozen=True)
class RouteDecision:
    matched_rule_id: str
    approver_slots: tuple[str, ...]
    approver_ids: tuple[str, ...]
    executor_id: str | None
    acceptor_id: str | None

    @property
    def resolved_route(self) -> list[dict[str, object]]:
        return [
            {"step_no": index, "assignee_id": actor_id, "resolver": slot}
            for index, (slot, actor_id) in enumerate(
                zip(self.approver_slots, self.approver_ids), start=1
            )
        ]


def _uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise RoutingError(f"{label} must resolve to one UUID") from None


def _extract_days(payload: dict[str, Any]) -> int | None:
    for field in ("duration_days", "days", "number_of_days", "leave_days"):
        val = payload.get(field)
        if val is not None and not isinstance(val, bool):
            try:
                days_int = int(val)
                if days_int >= 0:
                    return days_int
            except (ValueError, TypeError):
                pass

    start = payload.get("start_date")
    end = payload.get("end_date")
    if isinstance(start, str) and isinstance(end, str):
        try:
            from datetime import date

            d_start = date.fromisoformat(start)
            d_end = date.fromisoformat(end)
            diff = (d_end - d_start).days + 1
            if diff >= 0:
                return diff
        except (ValueError, TypeError):
            pass

    return None


def _match_amount(key: str, value: Any, amount_vnd: int | None) -> bool:
    if (
        amount_vnd is None
        or isinstance(amount_vnd, bool)
        or not isinstance(amount_vnd, int)
    ):
        return False
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 1_000_000_000_000
    ):
        raise RoutingError("Route threshold must be an integer VND value")
    if key == "amount_gt":
        return amount_vnd > value
    if key == "amount_gte":
        return amount_vnd >= value
    return True


def _match_days(value: Any, payload: dict[str, Any]) -> bool:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RoutingError("Route days_gt threshold must be a non-negative integer")
    days = _extract_days(payload)
    return days is not None and (days > value)


def _match_app_code(value: Any, payload: dict[str, Any]) -> bool:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(x, str) and x.strip() for x in value)
    ):
        raise RoutingError("Route app_code_in must be a non-empty list of strings")
    app_code = (
        payload.get("app_code") or payload.get("application") or payload.get("system")
    )
    return isinstance(app_code, str) and bool(app_code.strip()) and app_code in value


def _matches(
    when: dict[str, Any],
    amount_vnd: int | None,
    payload: dict[str, Any] | None = None,
) -> bool:
    if set(when) - SUPPORTED_OPERATORS:
        raise RoutingError("Unsupported route operator")
    if not when:
        return True

    payload = payload or {}

    for key, value in when.items():
        if key in ("amount_gt", "amount_gte") and not _match_amount(
            key, value, amount_vnd
        ):
            return False
        if key == "days_gt" and not _match_days(value, payload):
            return False
        if key == "app_code_in" and not _match_app_code(value, payload):
            return False

    return True


def _validate_route_rules_structure(
    rules: list[Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    defaults = [
        rule for rule in rules if isinstance(rule, dict) and rule.get("default") is True
    ]
    if len(defaults) != 1 or rules[-1] is not defaults[0]:
        raise RoutingError("Exactly one final default rule is required")
    if "when" in defaults[0] or "priority" in defaults[0]:
        raise RoutingError("Default rule cannot have condition or priority")

    conditional = [
        rule for rule in rules if isinstance(rule, dict) and not rule.get("default")
    ]
    priorities = [rule.get("priority") for rule in conditional]
    if any(
        not isinstance(value, int) or isinstance(value, bool) for value in priorities
    ) or len(set(priorities)) != len(priorities):
        raise RoutingError("Conditional priorities must be unique integers")
    rule_ids = [rule.get("id") for rule in rules if isinstance(rule, dict)]
    if (
        len(rule_ids) != len(rules)
        or any(not isinstance(value, str) or not value.strip() for value in rule_ids)
        or len(set(rule_ids)) != len(rule_ids)
    ):
        raise RoutingError("Route rule IDs must be non-empty and unique")
    for rule in conditional:
        when = rule.get("when")
        if not isinstance(when, dict) or not when:
            raise RoutingError("Conditional rule requires a condition")
        if set(when) - SUPPORTED_OPERATORS:
            raise RoutingError("Unsupported route operator")

    return defaults[0], conditional


def _validate_resolved_actors(
    requester: str,
    approvers: tuple[str, ...],
    executor: str | None,
    acceptor: str | None,
) -> None:
    if requester in approvers:
        raise RoutingError("Requester cannot approve own request")
    if len(set(approvers)) != len(approvers):
        raise RoutingError("Approval actors must be different")
    if executor is not None and executor == requester:
        raise RoutingError("Requester cannot execute own request")
    if executor is not None and executor in approvers:
        raise RoutingError("Executor cannot also approve")
    if acceptor is not None and acceptor == executor:
        raise RoutingError("Acceptor cannot be the executor")


def resolve_route(
    *,
    route_rules: dict[str, Any],
    actor_bindings: dict[str, Any],
    department_id: str,
    requester_id: str,
    manager_id: str | None,
    amount_vnd: int | None = None,
    payload: dict[str, Any] | None = None,
) -> RouteDecision:
    if (
        route_rules.get("schema_version") != 1
        or actor_bindings.get("schema_version") != 1
    ):
        raise RoutingError("Unsupported route or binding schema")
    rules = route_rules.get("rules")
    if not isinstance(rules, list) or not rules:
        raise RoutingError("At least one route rule is required")

    default_rule, conditional = _validate_route_rules_structure(rules)
    effective_amount = extract_amount_vnd(payload, amount_vnd, allow_zero=True)

    matched = next(
        (
            rule
            for rule in sorted(conditional, key=lambda item: item["priority"])
            if _matches(rule.get("when", {}), effective_amount, payload)
        ),
        default_rule,
    )
    rule_id = matched.get("id")
    slots = matched.get("approvers")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise RoutingError("Matched rule requires an ID")
    if (
        not isinstance(slots, list)
        or not 1 <= len(slots) <= 5
        or not all(slot in APPROVER_SLOTS for slot in slots)
    ):
        raise RoutingError("Approval route must contain one to five allowed slots")

    executor_slot = route_rules.get("executor")
    acceptor_slot = route_rules.get("acceptor")
    if executor_slot not in EXECUTOR_SLOTS or acceptor_slot not in ACCEPTOR_SLOTS:
        raise RoutingError("Executor or acceptor resolver is outside the P0 allowlist")

    department_bindings = actor_bindings.get("departments", {}).get(department_id)
    if not isinstance(department_bindings, dict):
        raise RoutingError("Department has no actor bindings")

    def actor_for(slot: str | None) -> str | None:
        if slot is None:
            return None
        if slot == "REQUESTER":
            return _uuid(requester_id, slot)
        if slot == "DIRECT_MANAGER":
            if manager_id is None:
                raise RoutingError("Requester has no direct manager")
            return _uuid(manager_id, slot)
        return _uuid(department_bindings.get(slot), slot)

    approvers = tuple(actor_for(slot) for slot in slots)
    requester = _uuid(requester_id, "REQUESTER")
    executor = actor_for(executor_slot)
    acceptor = actor_for(acceptor_slot)

    _validate_resolved_actors(requester, approvers, executor, acceptor)

    return RouteDecision(
        matched_rule_id=rule_id,
        approver_slots=tuple(slots),
        approver_ids=approvers,
        executor_id=executor,
        acceptor_id=acceptor,
    )
