"""Presentation-only availability explanations. No authorization is decided here."""

from __future__ import annotations


def request_option_blocker(state, expected_lifecycle: str):
    """Return (machine_code, Vietnamese explanation) for a catalog option.

    `state`: None or (lifecycle, active, published_release, requester_scope).
    Write APIs independently reauthorize type, release, actor, and workflow.
    """
    if state is None:
        return ("TYPE_NOT_REGISTERED", "Loại đơn chưa được đăng ký trong Database.")
    lifecycle, active, published, scoped = state
    if not active:
        return ("TYPE_INACTIVE", "Loại đơn đang tạm ngừng hoạt động.")
    if lifecycle != expected_lifecycle:
        return ("LIFECYCLE_MISMATCH", "Mẫu vòng đời chưa khớp quy chế.")
    if not published:
        return (
            "NO_PUBLISHED_RELEASE",
            "Chưa có quy chế PUBLISHED hợp lệ. Liên hệ POLICY_ADMIN.",
        )
    if not scoped:
        return (
            "REQUESTER_SCOPE_DENIED",
            "Chưa có quyền REQUESTER cho loại đơn/phòng ban. Liên hệ OPS_ADMIN.",
        )
    return (None, None)
