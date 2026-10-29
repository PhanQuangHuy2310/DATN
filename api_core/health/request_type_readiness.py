"""Release coverage for core readiness and expanded request catalog.

Unpublished optional templates do not make valid P0 workflows unavailable.
This module does not authorize request creation. The workflow/catalog APIs must
still require a published, type-matched, active release for every request.
"""

from __future__ import annotations

EXPECTED_TYPES = frozenset({("ACCESS", "B"), ("EQUIPMENT", "C"), ("LEAVE", "A")})


def assess_request_types(rows, *, require_active_releases: bool):
    """Evaluate active types returned as (code, lifecycle, release_is_valid).

    ``all_active_types_configured`` is ALWAYS factual even if release checks are
    optional for the health probe. Presence and release validity of required P0
    templates are two separate checks.
    """
    active = {(code, lifecycle): bool(valid) for code, lifecycle, valid in rows}
    required_present = EXPECTED_TYPES.issubset(active)
    p0_ready = required_present and all(
        active.get(key, False) for key in EXPECTED_TYPES
    )
    return {
        "request_types_match_p0": required_present,
        "p0_active_types_configured": not require_active_releases or p0_ready,
        "all_active_types_configured": bool(rows) and all(active.values()),
    }


def catalog_readiness_summary(rows):
    """Public metrics only; do not expose internal type codes on public health."""
    count = sum(not bool(valid) for _, _, valid in rows)
    return {
        "status": "needs_configuration" if count else "configured",
        "active_type_count": len(rows),
        "unconfigured_active_type_count": count,
        "all_active_types_configured": count == 0 and len(rows) > 0,
    }
