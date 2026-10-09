from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


class RoutingError(ValueError):
    pass


APPROVER_SLOTS = {"DIRECT_MANAGER", "DIRECTOR", "FINANCE"}
EXECUTOR_SLOTS = {None, "EXECUTOR_ASSET", "EXECUTOR_IT"}
ACCEPTOR_SLOTS = {None, "REQUESTER"}
SUPPORTED_OPERATORS = {"amount_gt", "amount_gte"}


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


def _matches(when: dict[str, Any], amount_vnd: int | None) -> bool:
    if set(when) - SUPPORTED_OPERATORS:
        raise RoutingError("Unsupported route operator")
    if not when:
        return True
    if (
        amount_vnd is None
        or isinstance(amount_vnd, bool)
        or not isinstance(amount_vnd, int)
    ):
        return False
    checks = {
        "amount_gt": lambda threshold: amount_vnd > threshold,
        "amount_gte": lambda threshold: amount_vnd >= threshold,
    }
    for key, value in when.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 1_000_000_000_000
        ):
            raise RoutingError("Route threshold must be an integer VND value")
        if not checks[key](value):
            return False
    return True


def resolve_route(
    *,
    route_rules: dict[str, Any],
    actor_bindings: dict[str, Any],
    department_id: str,
    requester_id: str,
    manager_id: str | None,
    amount_vnd: int | None,
) -> RouteDecision:
    if (
        route_rules.get("schema_version") != 1
        or actor_bindings.get("schema_version") != 1
    ):
        raise RoutingError("Unsupported route or binding schema")
    rules = route_rules.get("rules")
    if not isinstance(rules, list) or not rules:
        raise RoutingError("At least one route rule is required")

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

    matched = next(
        (
            rule
            for rule in sorted(conditional, key=lambda item: item["priority"])
            if _matches(rule.get("when", {}), amount_vnd)
        ),
        defaults[0],
    )
    rule_id = matched.get("id")
    slots = matched.get("approvers")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise RoutingError("Matched rule requires an ID")
    if (
        not isinstance(slots, list)
        or not 1 <= len(slots) <= 3
        or not all(slot in APPROVER_SLOTS for slot in slots)
    ):
        raise RoutingError("Approval route must contain one to three allowed slots")

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
    if requester in approvers:
        raise RoutingError("Requester cannot approve own request")
    if len(set(approvers)) != len(approvers):
        raise RoutingError("Approval actors must be different")

    executor = actor_for(executor_slot)
    acceptor = actor_for(acceptor_slot)
    if executor is not None and executor == requester:
        raise RoutingError("Requester cannot execute own request")
    if executor is not None and executor in approvers:
        raise RoutingError("Executor cannot also approve")
    if acceptor is not None and acceptor == executor:
        raise RoutingError("Acceptor cannot be the executor")

    return RouteDecision(
        matched_rule_id=rule_id,
        approver_slots=tuple(slots),
        approver_ids=approvers,
        executor_id=executor,
        acceptor_id=acceptor,
    )
