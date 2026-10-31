/** EAS-P0 / UC-CTX-01, UC-BIZ-01, UC-ADM-01: navigation is presentational.
 * Authorization always remains enforced on the Django API with role + scope + SoD.
 */
export const ROLE_NAVIGATION = Object.freeze({
  REQUESTER: ["home", "flow-diagrams", "mine", "history", "notifications", "profile"],
  APPROVER: ["home", "flow-diagrams", "approval", "history", "notifications", "profile"],
  EXECUTOR: ["home", "flow-diagrams", "execution", "history", "notifications", "profile"],
  ACCEPTOR: ["home", "flow-diagrams", "acceptance", "history", "notifications", "profile"],
  POLICY_ADMIN: ["home", "flow-diagrams", "policy", "plan-catalog", "notifications", "profile"],
  OPS_ADMIN: ["home", "flow-diagrams", "ops", "identity", "api-admin", "plan-catalog", "notifications", "profile"],
  AUDITOR: ["home", "flow-diagrams", "audit", "events", "notifications", "profile"],
});

const NAV_ORDER = ["home", "flow-diagrams", "mine", "approval", "execution", "acceptance", "history", "policy", "plan-catalog", "ops", "identity", "api-admin", "audit", "events", "notifications", "profile"];

export function visiblePages(roles = [], capabilities = {}) {
  const enabled = new Set(["home", "notifications", "profile"]);
  for (const role of roles) {
    for (const page of ROLE_NAVIGATION[role] || []) enabled.add(page);
  }
  // UC17: identity management is restricted to GLOBAL + ALL OPS admins.
  if (!capabilities.identity_manage) { enabled.delete("identity"); enabled.delete("api-admin"); }
  return NAV_ORDER.filter((page) => enabled.has(page));
}

export function canNavigate(roles, page, capabilities = {}) {
  return visiblePages(roles, capabilities).includes(page);
}

export const ROLE_TASKS = Object.freeze([
  { role: "REQUESTER", title: "Yêu cầu của tôi", description: "Soạn nháp, bổ sung, gửi và hủy trước khi duyệt xong", page: "mine", uc: "UC03 · UC04 · UC07 · UC08", icon: "▤" },
  { role: "APPROVER", title: "Hộp việc phê duyệt", description: "Duyệt, từ chối hoặc yêu cầu bổ sung theo đúng lượt", page: "approval", uc: "UC06", icon: "✓" },
  { role: "EXECUTOR", title: "Công việc thực hiện", description: "Nhận việc, báo vướng mắc và nộp kết quả", page: "execution", uc: "UC10 · UC11", icon: "▣" },
  { role: "ACCEPTOR", title: "Hàng đợi nghiệm thu", description: "Chấp nhận kết quả hoặc yêu cầu làm lại", page: "acceptance", uc: "UC12", icon: "◇" },
  { role: "POLICY_ADMIN", title: "Phiên bản chính sách", description: "Soạn, kiểm tra và công bố cấu hình có kiểm soát", page: "policy", uc: "UC02", icon: "⚙" },
  { role: "OPS_ADMIN", title: "Điều phối vận hành", description: "Điều chuyển, giám sát SLA và khôi phục outbox", page: "ops", uc: "UC09 · UC14", icon: "⇄" },
  { role: "OPS_ADMIN", title: "Danh tính & phân quyền", description: "Quản lý tổ chức và role theo phạm vi được cấp", page: "identity", uc: "UC17", icon: "◎" },
  { role: "OPS_ADMIN", title: "Quản lý API & ma trận quyền", description: "Đối chiếu endpoint, quyền truy cập và trạng thái API", page: "api-admin", uc: "UC17 · API v1", icon: "⌘" },
  { role: "AUDITOR", title: "Tra cứu kiểm toán", description: "Đọc hồ sơ được cấp phạm vi và xác minh chuỗi audit", page: "audit", uc: "UC05 · UC15", icon: "⌕" },
  { role: "AUDITOR", title: "Nhật ký quản trị", description: "Kiểm tra sự kiện vận hành, bất biến và phân trang", page: "events", uc: "UC15", icon: "≡" },
]);

export function roleTasks(roles = [], capabilities = {}) {
  const granted = new Set(roles);
  return ROLE_TASKS.filter((task) => granted.has(task.role) && (!["identity", "api-admin"].includes(task.page) || capabilities.identity_manage));
}
