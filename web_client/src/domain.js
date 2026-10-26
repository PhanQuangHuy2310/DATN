export const statuses = {
  DRAFT: "Bản nháp",
  PENDING_APPROVAL: "Chờ phê duyệt",
  NEEDS_INFO: "Cần bổ sung",
  READY_FOR_EXECUTION: "Chờ thực hiện",
  IN_PROGRESS: "Đang thực hiện",
  WAITING_FOR_ACCEPTANCE: "Chờ nghiệm thu",
  COMPLETED: "Đã hoàn thành",
  REJECTED: "Bị từ chối",
  CANCELLED: "Đã hủy",
};
export const types = {
  LEAVE: "Nghỉ phép",
  ACCESS: "Cấp quyền truy cập",
  EQUIPMENT: "Đề nghị thiết bị",
};
export const roles = {
  REQUESTER: "Người gửi yêu cầu",
  APPROVER: "Người phê duyệt",
  EXECUTOR: "Người thực hiện",
  ACCEPTOR: "Người nghiệm thu",
  POLICY_ADMIN: "Quản trị chính sách",
  OPS_ADMIN: "Quản trị vận hành",
  AUDITOR: "Người kiểm tra",
};
export const fields = {
  LEAVE: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["start_date", "Ngày bắt đầu", "date"],
    ["end_date", "Ngày kết thúc", "date"],
    ["handover_user_id", "ID người nhận bàn giao", "text"],
  ],
  ACCESS: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["app_code", "Mã ứng dụng", "text"],
    ["requested_role", "Quyền đề nghị", "text"],
    ["duration_days", "Số ngày", "number"],
    ["purpose", "Mục đích", "textarea"],
  ],
  EQUIPMENT: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["item_name", "Tên thiết bị", "text"],
    ["quantity", "Số lượng", "number"],
    ["amount_vnd", "Giá trị (VND)", "number"],
    ["specs", "Cấu hình", "textarea"],
    ["location", "Nơi sử dụng", "text"],
  ],
};
export const labels = {
  ...statuses,
  ACTIVE: "Đang xử lý",
  WAITING: "Chưa đến lượt",
  APPROVED: "Đã duyệt",
  SKIPPED: "Bỏ qua",
  READY: "Chờ nhận",
  RUNNING: "Đang thực hiện",
  SUBMITTED: "Đã nộp kết quả",
  FINISHED: "Kết thúc lần thực hiện",
  PUBLISHED: "Đã công bố",
  QUEUED: "Chờ kiểm tra",
  CLEAN: "Tệp hợp lệ",
  INFECTED: "Tệp bị cách ly",
  ERROR: "Kiểm tra thất bại",
};
export function permissions(user, r) {
  const has = (role) => user.roles.includes(role);
  const owner = has("REQUESTER") && r.requester_id === user.id;
  const executor =
    has("EXECUTOR") && r.workflow?.attempt?.executor_id === user.id;
  return {
    edit: owner && ["DRAFT", "NEEDS_INFO"].includes(r.status),
    cancel:
      owner && ["DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"].includes(r.status),
    approve:
      has("APPROVER") &&
      r.status === "PENDING_APPROVAL" &&
      r.approval_steps?.some(
        (s) => s.state === "ACTIVE" && s.assignee_id === user.id,
      ),
    claim: executor && r.status === "READY_FOR_EXECUTION",
    execute: executor && r.status === "IN_PROGRESS",
    accept:
      has("ACCEPTOR") &&
      r.status === "WAITING_FOR_ACCEPTANCE" &&
      r.workflow?.acceptor_id === user.id,
  };
}
export const date = (v) => (v ? new Date(v).toLocaleString("vi-VN") : "—");
export function errorText(e) {
  const messages = {
    VERSION_CONFLICT:
      "Dữ liệu đã thay đổi. Hãy tải lại hồ sơ trước khi tiếp tục.",
    REQUEST_STATE_CONFLICT: "Trạng thái đã thay đổi. Hãy tải lại hồ sơ.",
    FORBIDDEN: "Bạn không có quyền thực hiện thao tác này.",
    INVALID_CREDENTIALS: "Tên đăng nhập hoặc mật khẩu không đúng.",
    DATABASE_QUERY_FAILED: "Máy chủ gặp lỗi truy vấn dữ liệu. Vui lòng thử lại hoặc báo quản trị viên.",
    SERVER_ERROR: "Máy chủ đang gặp lỗi (HTTP 500). Vui lòng thử lại sau.",
    INVALID_RESPONSE: "Máy chủ trả về dữ liệu không đúng định dạng. Hãy kiểm tra log Backend.",
    INVALID_CURRENT_PASSWORD: "Mật khẩu hiện tại không đúng.",
    PASSWORD_REUSE_NOT_ALLOWED: "Mật khẩu mới phải khác mật khẩu cũ.",
    PASSWORD_POLICY_VIOLATION: "Mật khẩu mới phải có 12–128 ký tự, gồm chữ hoa, chữ thường, số, ký tự đặc biệt và không chứa tên đăng nhập.",
    LOGIN_RATE_LIMITED: "Bạn đã thử quá nhiều lần. Vui lòng thử lại sau.",
    VALIDATION_FAILED: "Dữ liệu chưa hợp lệ.",
    VALIDATION_STALE:
      "Cấu hình đã thay đổi. Hãy kiểm tra lại trước khi công bố.",
    ATTACHMENT_NOT_CLEAN: "Tệp chưa vượt qua kiểm tra. Hãy kiểm tra lại tệp.",
  };
  return (
    (messages[e.message] || (e.status === 401
      ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
      : e.message)) +
    (e.fields ? " " + JSON.stringify(e.fields) : "") +
    (e.correlationId ? ` (Mã lỗi: ${e.correlationId})` : "")
  );
}
