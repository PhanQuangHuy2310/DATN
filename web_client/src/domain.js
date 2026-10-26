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
  LEAVE_ANNUAL: "Nghỉ phép thường niên",
  LEAVE_LONG: "Nghỉ phép dài hạn (>2 ngày)",
  RESIGNATION: "Thôi việc / Bàn giao",
  OVERTIME_REQ: "Đăng ký làm thêm giờ (OT)",
  WFH_REQ: "Làm việc từ xa (WFH)",
  ROOM_VEHICLE: "Mượn phòng họp / Xe công vụ",
  ADVANCE_SMALL: "Tạm ứng chi phí (<10tr)",
  ADVANCE_MEDIUM: "Tạm ứng chi phí (10-50tr)",
  ADVANCE_LARGE: "Tạm ứng dự án lớn (>50tr)",
  REIMBURSEMENT: "Hoàn ứng / Thanh toán chi phí",
  VENDOR_PAYMENT: "Thanh toán Hợp đồng Vendor",
  LAPTOP_PROVISION: "Cấp phát Laptop / PC làm việc",
  SOFTWARE_ACCESS: "Cấp quyền phần mềm thông thường",
  PROD_DATA_ACCESS: "Cấp quyền Dữ liệu nhạy cảm/Server",
  SAAS_LICENSE_BUY: "Mua bản quyền phần mềm mới",
  OFFICE_SUPPLIES: "Văn phòng phẩm định mức tháng",
  ASSET_PURCHASE: "Mua sắm tài sản phòng ban",
  FACILITY_REPAIR: "Sửa chữa sự cố văn phòng",
  OVERTIME_APPROVAL: "Đăng ký làm thêm giờ (OT)",
  PURCHASE_REQUEST: "Đề nghị mua sắm",
  FACILITY_MAINTENANCE: "Sửa chữa cơ sở vật chất",
  REFUND_COMPENSATION: "Hoàn tiền / Đền bù",
  WAREHOUSE_TRANSFER: "Luân chuyển kho",
  FLASH_SALE_VOUCHER: "Flash Sale / Voucher",
  CONTRACT_APPROVAL: "Duyệt hợp đồng",
  DATA_UAT_EXPORT: "Trích xuất dữ liệu / UAT",
  FEATURE_RELEASE: "Feature Request / Release",
  SERVER_FIREWALL: "Cấp Server / Firewall",
  ROOM_STUDIO: "Mượn phòng họp / Studio",
  ATTENDANCE_ADJUSTMENT: "Đi muộn / Về sớm / Quên chấm công",
  EMPLOYEE_ONBOARDING: "Onboarding nhân viên",

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
/** UC06/UC10/UC12: client affordances mirror SoD and FSM.
 * API transaction and scoped role membership remain the source of truth.
 */
export function permissions(user, r) {
  const granted = new Set(user?.roles || []);
  const own = r.requester_id === user.id;
  const owner = own && granted.has("REQUESTER");
  const activeStep = r.approval_steps?.find((s) => s.state === "ACTIVE");
  const attempt = r.workflow?.attempt;
  const isExecutor = attempt?.executor_id === user.id;
  const hasApprovedStep = r.approval_steps?.some((s) => s.assignee_id === user.id);
  return {
    edit: owner && ["DRAFT", "NEEDS_INFO"].includes(r.status),
    cancel: owner && ["DRAFT", "NEEDS_INFO", "PENDING_APPROVAL"].includes(r.status),
    approve: granted.has("APPROVER") && r.status === "PENDING_APPROVAL" &&
      !own && activeStep?.assignee_id === user.id,
    claim: granted.has("EXECUTOR") && r.status === "READY_FOR_EXECUTION" &&
      !own && !hasApprovedStep && isExecutor && attempt?.state === "READY",
    execute: granted.has("EXECUTOR") && r.status === "IN_PROGRESS" &&
      !own && !hasApprovedStep && isExecutor && attempt?.state === "RUNNING",
    accept: granted.has("ACCEPTOR") && r.status === "WAITING_FOR_ACCEPTANCE" &&
      r.workflow?.lifecycle === "C" && r.workflow?.acceptor_id === user.id &&
      attempt?.state === "SUBMITTED" && !isExecutor,
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
    DATABASE_QUERY_FAILED: "Máy chủ gặp lỗi truy vấn dữ liệu. Vui lòng báo quản trị viên kèm mã lỗi để kiểm tra Backend.",
    DATABASE_TEMPORARILY_UNAVAILABLE: "Kết nối cơ sở dữ liệu đang gián đoạn hoặc quá thời gian chờ. Vui lòng thử lại sau vài giây; nếu còn lỗi hãy gửi mã lỗi cho quản trị viên.",
    SERVER_ERROR: "Máy chủ đang gặp lỗi (HTTP 500). Vui lòng thử lại sau.",
    INVALID_RESPONSE: "Máy chủ trả về dữ liệu không đúng định dạng. Hãy kiểm tra log Backend.",
    CATALOG_EXPANSION_DISABLED: "Chức năng thêm loại yêu cầu chưa được DBA phê duyệt/mở khóa migration. Danh mục P0 vẫn hoạt động bình thường.",
    REQUEST_TYPE_NOT_CONFIGURED: "Loại yêu cầu này chưa có phiên bản quy chế đã công bố.",
    ROUTE_CONFIGURATION_INVALID: "Quy trình chưa gán đủ người duyệt/thực hiện/nghiệm thu hợp lệ. Liên hệ quản trị viên quy chế.",
    ATTACHMENT_REQUIRED: "Loại yêu cầu này bắt buộc đính kèm tài liệu hợp lệ trước khi gửi.",
    DEPARTMENT_SCOPE_VIOLATION: "Bạn không được chọn phòng ban khác với phòng ban của mình.",
    INVALID_CURRENT_PASSWORD: "Mật khẩu hiện tại không đúng.",
    PASSWORD_REUSE_NOT_ALLOWED: "Mật khẩu mới phải khác mật khẩu cũ.",
    PASSWORD_POLICY_VIOLATION: "Mật khẩu mới phải có 15–128 ký tự, gồm chữ hoa, chữ thường, số, ký tự đặc biệt và không chứa tên đăng nhập.",
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
