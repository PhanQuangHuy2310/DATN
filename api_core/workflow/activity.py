"""User-facing request activity labels; no SQL or sensitive audit details are exposed."""

# We don't publish notifications for attachment downloads: reading a file is
# not a workflow transition, and could generate unbounded noisy messages.
ACTIVITY_LABELS = {
    "DRAFT_CREATED": "Hồ sơ nháp đã được tạo",
    "DRAFT_UPDATED": "Nội dung hồ sơ đã được cập nhật",
    "DRAFT_ATTACHMENT_REMOVED": "Tệp đính kèm đã được gỡ khỏi hồ sơ",
    "ATTACHMENT_ADDED": "Hồ sơ có tệp đính kèm mới",
    "REQUEST_SUBMITTED": "Hồ sơ đã được gửi để phê duyệt",
    "APPROVAL_APPROVE": "Hồ sơ đã được phê duyệt một bước",
    "APPROVAL_REJECT": "Hồ sơ đã bị từ chối",
    "APPROVAL_NEEDS_INFO": "Hồ sơ cần bổ sung thông tin",
    "EXECUTION_STARTED": "Công việc đã được nhận xử lý",
    "EXECUTION_RESULT_SUBMITTED": "Đã nộp kết quả thực hiện",
    "EXECUTION_EVIDENCE_ADDED": "Đã bổ sung minh chứng thực hiện",
    "ACCEPTANCE_ACCEPT": "Kết quả đã được nghiệm thu",
    "ACCEPTANCE_REWORK": "Kết quả cần được làm lại",
    "REQUEST_CANCELLED": "Hồ sơ đã được hủy",
    "ACTOR_REASSIGNED": "Hồ sơ được điều chuyển người xử lý",
    "EXECUTION_ISSUE_BLOCKED": "Công việc được báo vướng mắc",
    "EXECUTION_ISSUE_DELAY": "Công việc được báo chậm tiến độ",
}


def activity_label(action: object) -> str:
    """Return a fixed, non-sensitive label for request audit events."""
    if not isinstance(action, str) or not action:
        return "Hồ sơ có hoạt động mới"
    if action.startswith("EXECUTION_ISSUE_"):
        return "Công việc có báo cáo vướng mắc mới"
    return ACTIVITY_LABELS.get(action, "Hồ sơ có hoạt động mới")


def is_notifiable_action(action: object) -> bool:
    """Explicitly exclude read-only and technical audit events."""
    return isinstance(action, str) and (
        action in ACTIVITY_LABELS or action.startswith("EXECUTION_ISSUE_")
    )
