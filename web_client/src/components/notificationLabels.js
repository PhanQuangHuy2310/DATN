const EVENT_NOTIFICATION_LABELS = {
  REQUEST_SUBMITTED: "Có hồ sơ yêu cầu mới vừa được gửi phê duyệt",
  APPROVAL_APPROVE: "Hồ sơ đã được phê duyệt ở bước hiện tại",
  APPROVAL_REJECT: "Hồ sơ yêu cầu đã bị từ chối",
  APPROVAL_NEEDS_INFO: "Người phê duyệt yêu cầu bổ sung thêm thông tin",
  AI_AUTO_APPROVED: "Hồ sơ đã được AI phê duyệt tự động theo quy chế",
  AI_AUTO_APPROVAL_REVOKED: "Quyết định duyệt tự động của AI đã được thu hồi để xét duyệt lại",
  DELEGATION_APPLIED: "Bạn nhận được hồ sơ chuyển tiếp theo ủy quyền phê duyệt",
  EXECUTION_STARTED: "Công việc thực hiện trên hồ sơ đã được tiếp nhận",
  EXECUTION_RESULT_SUBMITTED: "Kết quả thực hiện đã được nộp và chờ nghiệm thu",
  EXECUTION_ISSUE_BLOCKED: "Người thực hiện báo cáo vướng mắc phát sinh",
  EXECUTION_ISSUE_UNABLE_TO_CLAIM: "Người thực hiện báo không thể tiếp nhận công việc",
  ACCEPTANCE_ACCEPT: "Hồ sơ đã được nghiệm thu hoàn tất",
  ACCEPTANCE_REWORK: "Người nghiệm thu yêu cầu thực hiện lại công việc",
  REQUEST_CANCELLED: "Hồ sơ yêu cầu đã bị hủy bởi người tạo",
  ACTOR_REASSIGNED: "Bạn vừa được phân công xử lý hồ sơ",
  SLA_REMINDER: "Nhắc hạn xử lý hồ sơ sắp đến hạn SLA",
  SLA_BREACH: "Cảnh báo hồ sơ đã quá thời hạn xử lý SLA",
};

export function formatNotificationLabel(label) {
  if (!label) return "Thông báo cập nhật hồ sơ";
  const trimmed = String(label).trim();
  if (EVENT_NOTIFICATION_LABELS[trimmed]) return EVENT_NOTIFICATION_LABELS[trimmed];
  return trimmed;
}

