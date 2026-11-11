"""Documented mapping between the stored contract and the thesis vocabulary.

Owner decisions B1/B2: the database status and outcome codes are preserved
(no destructive renaming); the thesis report (ST-01, Table 2.5, Table 2.15)
names the same states differently. This module is the single, tested
translation used for documentation, reports and the thesis revision.
"""

from __future__ import annotations

# Stored eas.request.status -> thesis ST-01 state. SUBMITTED is never stored:
# submit snapshots the release and resolves the route in one transaction, so a
# request goes straight from DRAFT to PENDING_APPROVAL (thesis SUBMITTED ->
# ROUTE_SUCCESS -> IN_REVIEW collapsed atomically).
REQUEST_STATUS_TO_THESIS: dict[str, str] = {
    "DRAFT": "DRAFT",
    # Thesis REQUEST_INFO returns the file to DRAFT (Needs Info). It is kept as
    # its own code so the requester, reports and SLA can tell it apart; it is
    # editable exactly like a draft.
    "NEEDS_INFO": "DRAFT",
    "PENDING_APPROVAL": "IN_REVIEW",
    "READY_FOR_EXECUTION": "READY",
    "IN_PROGRESS": "IN_PROGRESS",
    "WAITING_FOR_ACCEPTANCE": "SUBMITTED_ACCEPT",
    # Template A final approval closes the file directly (thesis: APPROVED is
    # the instant of final approval; COMPLETED is the terminal state).
    "COMPLETED": "COMPLETED",
    "REJECTED": "REJECTED",
    "CANCELLED": "CANCELLED",
}

# Stored eas.acceptance_decision.outcome -> thesis Table 2.15 outcome. FAIL is
# not terminal in the thesis either (Table 2.5: REWORK -> back to execution).
ACCEPTANCE_OUTCOME_TO_THESIS: dict[str, str] = {
    "ACCEPT": "PASS",
    "REWORK": "FAIL",
}

# Known, documented behavioural differences that a pure rename cannot express.
DOCUMENTED_DEVIATIONS: tuple[str, ...] = (
    "NEEDS_INFO is a distinct stored code; the thesis folds it into DRAFT.",
    (
        "REWORK opens a new execution attempt in READY_FOR_EXECUTION (executor "
        "re-claims); the thesis returns directly to IN_PROGRESS."
    ),
    "SUBMITTED is transient and not persisted (atomic submit).",
)


def thesis_status(status: str) -> str:
    try:
        return REQUEST_STATUS_TO_THESIS[status]
    except KeyError:
        raise ValueError(f"Unknown request status: {status}") from None


def thesis_acceptance_outcome(outcome: str) -> str:
    try:
        return ACCEPTANCE_OUTCOME_TO_THESIS[outcome]
    except KeyError:
        raise ValueError(f"Unknown acceptance outcome: {outcome}") from None
