// Pure UI labels. The audit API and permissions stay server-authoritative.
export const activityLabels = Object.freeze({
  DRAFT_CREATED: "Đã tạo bản nháp",
  DRAFT_UPDATED: "Đã cập nhật nội dung",
  DRAFT_ATTACHMENT_REMOVED: "Đã gỡ tệp đính kèm",
  ATTACHMENT_ADDED: "Đã thêm tệp đính kèm",
  REQUEST_SUBMITTED: "Đã gửi yêu cầu",
  APPROVAL_APPROVE: "Đã phê duyệt một cấp",
  APPROVAL_REJECT: "Đã từ chối",
  APPROVAL_NEEDS_INFO: "Yêu cầu bổ sung",
  EXECUTION_STARTED: "Đã nhận thực hiện",
  EXECUTION_RESULT_SUBMITTED: "Đã nộp kết quả",
  EXECUTION_EVIDENCE_ADDED: "Đã thêm minh chứng",
  ACCEPTANCE_ACCEPT: "Nghiệm thu đạt",
  ACCEPTANCE_REWORK: "Yêu cầu làm lại",
  REQUEST_CANCELLED: "Đã hủy yêu cầu",
  ACTOR_REASSIGNED: "Đã điều chuyển người phụ trách",
  EXECUTION_ISSUE_BLOCKED: "Đã báo vướng mắc",
  EXECUTION_ISSUE_DELAY: "Đã báo chậm tiến độ",
});
export function activityLabel(action) {
  if (typeof action !== "string") return "Hoạt động hồ sơ";
  if (action.startsWith("EXECUTION_ISSUE_")) return "Có báo cáo vướng mắc";
  return activityLabels[action] || "Hoạt động hồ sơ";
}
