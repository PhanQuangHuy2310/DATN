"""Time-limited approval delegation applied at routing time (thesis §2.3.4).

A delegation lets an approver's active steps go to a deputy for a bounded
period. The deputy must pass the same eligibility checks as any approver; if
no eligible deputy exists the original approver keeps the step (their own
authority is unchanged), so delegation can never produce an arbitrary or
unauthorized assignee. Delegation is not transitive.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace

from .routing import RouteDecision


def apply_delegations(
    decision: RouteDecision,
    *,
    requester_id: str,
    delegations: Mapping[str, Sequence[tuple[str, str]]],
    is_eligible: Callable[[str], bool],
) -> RouteDecision:
    """``delegations`` maps delegator id -> [(delegation_id, delegate_id)],
    most specific / most recent first."""
    approvers = list(decision.approver_ids)
    records: list[dict[str, object]] = []
    for index, delegator in enumerate(decision.approver_ids):
        for delegation_id, delegate in delegations.get(delegator, ()):
            if (
                delegate == requester_id
                or delegate in approvers
                or delegate == decision.executor_id
                or not is_eligible(delegate)
            ):
                continue
            approvers[index] = delegate
            records.append(
                {
                    "step_no": index + 1,
                    "delegation_id": delegation_id,
                    "delegator_id": delegator,
                    "delegate_id": delegate,
                }
            )
            break
    if not records:
        return decision
    return replace(decision, approver_ids=tuple(approvers), delegations=tuple(records))
