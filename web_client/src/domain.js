import { catalogTypeLevels, catalogTypeNames } from "./catalogV2.js";

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
  LEAVE_SPECIAL: "Nghỉ phép đặc biệt",
  ROOM_BOOKING: "Đặt phòng họp",
  VEHICLE_BOOKING: "Đặt xe công vụ",
  EXPENSE_CLAIM: "Thanh toán chi phí",
  ACCESS: "Cấp quyền truy cập",
  ACCESS_FACILITY: "Cấp quyền ra vào",
  BUSINESS_TRIP: "Công tác",
  IT_SUPPORT: "Yêu cầu hỗ trợ IT",
  EQUIPMENT: "Đề nghị thiết bị",
  EQUIPMENT_BORROW: "Mượn thiết bị",
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
  VPN_SERVER_ACCESS: "Cấp quyền VPN / Server",
  FIREWALL_CHANGE: "Mở Port / Thay đổi Firewall",
  SERVER_PROVISION: "Khởi tạo Máy chủ / Cloud VM",
  EXPENSE_REIMBURSEMENT: "Hoàn ứng chi phí công tác",
  CUSTOMER_ONBOARDING: "Onboarding đối tác / khách hàng",
  ROOM_STUDIO: "Mượn phòng họp / Studio",
  ATTENDANCE_ADJUSTMENT: "Đi muộn / Về sớm / Quên chấm công",
  EMPLOYEE_ONBOARDING: "Onboarding nhân viên",
  VISITOR_SECURITY_PASS: "Thẻ an ninh khách & đối tác ra vào",
  TAX_INVOICE_ISSUE: "Phát hành / điều chỉnh hóa đơn VAT",
  TRAINING_COURSE: "Đăng ký đào tạo & chứng chỉ nghề nghiệp",
  NDA_PRIVACY_CLEARANCE: "Thẩm định NDA & chia sẻ dữ liệu đối tác",
  INTERNAL_TRANSFER: "Điều chuyển nội bộ & bổ nhiệm nhân sự",
  SPECIAL_DISCOUNT: "Phê duyệt chiết khấu thương mại đặc biệt",
  SUPPLIER_ONBOARDING: "Thẩm định & phê duyệt nhà cung cấp mới",
  RECRUITMENT_REQ: "Yêu cầu tuyển dụng nhân sự (Headcount)",
  MARKETING_CAMPAIGN: "Ngân sách chiến dịch Marketing & Sự kiện",
  ASSET_DISPOSAL: "Thanh lý & hủy tài sản cố định",
  BUDGET_REALLOCATION: "Điều chuyển & bổ sung ngân sách liên bộ phận",
  SECURITY_INCIDENT_HOTFIX: "Khắc phục sự cố bảo mật & Hotfix khẩn cấp",
};

export const riskLevels = {
  1: "Cấp 1 — Rất thấp",
  2: "Cấp 2 — Thấp",
  3: "Cấp 3 — Trung bình",
  4: "Cấp 4 — Cao",
  5: "Cấp 5 — Trọng yếu",
};

export const approvalLevels = {
  1: "Duyệt 1 cấp (Quản lý trực tiếp)",
  2: "Duyệt 2 cấp (Trưởng bộ phận)",
  3: "Duyệt 3 cấp (Kiểm soát liên phòng ban)",
  4: "Duyệt 4 cấp (Giám đốc Khối / Tài chính)",
  5: "Duyệt 5 cấp (Tổng Giám đốc / CTO / CISO)",
};

export const resolverLabels = {
  DIRECT_MANAGER: "Quản lý trực tiếp",
  PROJECT_MANAGER: "Giám đốc Dự án (PM)",
  HR_MANAGER: "Trưởng phòng Nhân sự",
  IT_MANAGER: "Trưởng phòng CNTT",
  FINANCE: "Kế toán trưởng / Giám đốc Tài chính",
  LEGAL: "Trưởng bộ phận Pháp chế",
  MARKETING_MANAGER: "Trưởng phòng Marketing",
  OPERATIONS_MANAGER: "Trưởng phòng Vận hành",
  PROCUREMENT_MANAGER: "Trưởng phòng Mua sắm",
  WAREHOUSE_MANAGER: "Trưởng kho trung tâm",
  SECURITY: "Chuyên gia An ninh thông tin",
  CISO: "Giám đốc An toàn thông tin (CISO)",
  CTO: "Giám đốc Công nghệ (CTO)",
  DIRECTOR: "Tổng Giám đốc / Ban Giám đốc (CEO)",
};

export const typeLevels = {
  LEAVE: { risk_weight: 1, approval_level: 3 },
  LEAVE_SPECIAL: { risk_weight: 2, approval_level: 3 },
  ROOM_BOOKING: { risk_weight: 1, approval_level: 1 },
  VEHICLE_BOOKING: { risk_weight: 2, approval_level: 2 },
  EXPENSE_CLAIM: { risk_weight: 3, approval_level: 3 },
  ACCESS: { risk_weight: 3, approval_level: 2 },
  ACCESS_FACILITY: { risk_weight: 2, approval_level: 2 },
  BUSINESS_TRIP: { risk_weight: 3, approval_level: 3 },
  IT_SUPPORT: { risk_weight: 1, approval_level: 1 },
  EQUIPMENT: { risk_weight: 3, approval_level: 3 },
  EQUIPMENT_BORROW: { risk_weight: 2, approval_level: 2 },
  LEAVE_ANNUAL: { risk_weight: 1, approval_level: 1 },
  LEAVE_LONG: { risk_weight: 3, approval_level: 1 },
  OFFICE_SUPPLIES: { risk_weight: 1, approval_level: 1 },
  LAPTOP_PROVISION: { risk_weight: 3, approval_level: 2 },
  OVERTIME_APPROVAL: { risk_weight: 2, approval_level: 1 },
  PURCHASE_REQUEST: { risk_weight: 5, approval_level: 3 },
  FACILITY_MAINTENANCE: { risk_weight: 2, approval_level: 1 },
  REFUND_COMPENSATION: { risk_weight: 2, approval_level: 3 },
  WAREHOUSE_TRANSFER: { risk_weight: 3, approval_level: 1 },
  FLASH_SALE_VOUCHER: { risk_weight: 4, approval_level: 2 },
  CONTRACT_APPROVAL: { risk_weight: 5, approval_level: 3 },
  VPN_SERVER_ACCESS: { risk_weight: 4, approval_level: 3 },
  FIREWALL_CHANGE: { risk_weight: 5, approval_level: 3 },
  SERVER_PROVISION: { risk_weight: 5, approval_level: 3 },
  EXPENSE_REIMBURSEMENT: { risk_weight: 2, approval_level: 2 },
  SOFTWARE_ACCESS: { risk_weight: 2, approval_level: 1 },
  ROOM_STUDIO: { risk_weight: 1, approval_level: 1 },
  CUSTOMER_ONBOARDING: { risk_weight: 3, approval_level: 1 },
  OVERTIME_REQ: { risk_weight: 2, approval_level: 1 },
  WFH_REQ: { risk_weight: 1, approval_level: 1 },
  RESIGNATION: { risk_weight: 4, approval_level: 3 },
  ROOM_VEHICLE: { risk_weight: 1, approval_level: 1 },
  ADVANCE_SMALL: { risk_weight: 2, approval_level: 2 },
  ADVANCE_MEDIUM: { risk_weight: 3, approval_level: 2 },
  ADVANCE_LARGE: { risk_weight: 4, approval_level: 3 },
  REIMBURSEMENT: { risk_weight: 2, approval_level: 2 },
  VENDOR_PAYMENT: { risk_weight: 5, approval_level: 3 },
  PROD_DATA_ACCESS: { risk_weight: 5, approval_level: 3 },
  SAAS_LICENSE_BUY: { risk_weight: 3, approval_level: 3 },
  ASSET_PURCHASE: { risk_weight: 4, approval_level: 3 },
  FACILITY_REPAIR: { risk_weight: 2, approval_level: 1 },
  VISITOR_SECURITY_PASS: { risk_weight: 1, approval_level: 1 },
  TAX_INVOICE_ISSUE: { risk_weight: 1, approval_level: 1 },
  TRAINING_COURSE: { risk_weight: 2, approval_level: 2 },
  NDA_PRIVACY_CLEARANCE: { risk_weight: 2, approval_level: 2 },
  INTERNAL_TRANSFER: { risk_weight: 3, approval_level: 3 },
  SPECIAL_DISCOUNT: { risk_weight: 3, approval_level: 3 },
  SUPPLIER_ONBOARDING: { risk_weight: 3, approval_level: 3 },
  RECRUITMENT_REQ: { risk_weight: 4, approval_level: 4 },
  MARKETING_CAMPAIGN: { risk_weight: 4, approval_level: 4 },
  ASSET_DISPOSAL: { risk_weight: 4, approval_level: 4 },
  BUDGET_REALLOCATION: { risk_weight: 5, approval_level: 5 },
  SECURITY_INCIDENT_HOTFIX: { risk_weight: 5, approval_level: 5 },
};

// The approved catalogue overrides older names and levels.
Object.assign(types, catalogTypeNames);
Object.assign(typeLevels, catalogTypeLevels);

export const roles = {
  STAFF: "Nhân viên",
  TEAM_LEAD: "Trưởng nhóm",
  MANAGER: "Trưởng phòng",
  VICE_DIRECTOR: "Phó giám đốc",
  DIRECTOR: "Giám đốc",
  REQUESTER: "Người gửi yêu cầu",
  APPROVER: "Người phê duyệt",
  EXECUTOR: "Người thực hiện",
  ACCEPTOR: "Người nghiệm thu",
  POLICY_ADMIN: "Quản trị chính sách",
  OPS_ADMIN: "Quản trị vận hành",
  AUDITOR: "Kiểm toán viên",
};

export const POSITION_CODES = [
  "DIRECTOR",
  "VICE_DIRECTOR",
  "MANAGER",
  "TEAM_LEAD",
  "STAFF",
];

export function getPrimaryRoleBadge(userRoles = []) {
  if (!userRoles || !userRoles.length) return { name: "Nhân viên", tone: "badge-default" };
  if (userRoles.includes("OPS_ADMIN")) return { name: "Quản trị vận hành", tone: "badge-admin" };
  if (userRoles.includes("POLICY_ADMIN")) return { name: "Quản trị chính sách", tone: "badge-policy" };
  if (userRoles.includes("DIRECTOR")) return { name: "Giám đốc", tone: "badge-approver" };
  if (userRoles.includes("VICE_DIRECTOR")) return { name: "Phó giám đốc", tone: "badge-approver" };
  if (userRoles.includes("MANAGER")) return { name: "Trưởng phòng", tone: "badge-approver" };
  if (userRoles.includes("TEAM_LEAD")) return { name: "Trưởng nhóm", tone: "badge-approver" };
  if (userRoles.includes("STAFF")) return { name: "Nhân viên", tone: "badge-requester" };
  if (userRoles.includes("AUDITOR")) return { name: "Kiểm toán viên", tone: "badge-audit" };
  if (userRoles.includes("APPROVER")) return { name: "Người phê duyệt", tone: "badge-approver" };
  if (userRoles.includes("EXECUTOR")) return { name: "Người thực hiện", tone: "badge-executor" };
  if (userRoles.includes("ACCEPTOR")) return { name: "Người nghiệm thu", tone: "badge-acceptor" };
  if (userRoles.includes("REQUESTER")) return { name: "Nhân viên", tone: "badge-requester" };
  return { name: "Nhân viên", tone: "badge-default" };
}

export const fields = {
  LEAVE: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["start_date", "Ngày bắt đầu", "date"],
    ["end_date", "Ngày kết thúc", "date"],
    ["handover_user_id", "Người nhận bàn giao công việc", "text"],
  ],
  ACCESS: [
    ["title", "Tiêu đề", "text"],
    ["reason", "Lý do", "textarea"],
    ["app_code", "Hệ thống / Ứng dụng", "text"],
    ["requested_role", "Quyền đề nghị", "text"],
    ["duration_days", "Số ngày cấp quyền", "number"],
    ["purpose", "Mục đích sử dụng", "textarea"],
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

export const fieldLabels = {
  title: "Tiêu đề yêu cầu",
  reason: "Lý do / Diễn giải chi tiết",
  description: "Mô tả chi tiết",
  notes: "Ghi chú bổ sung",
  note: "Ghi chú",
  comment: "Nhận xét",
  start_date: "Ngày bắt đầu",
  end_date: "Ngày kết thúc",
  borrow_date: "Ngày mượn",
  return_date: "Ngày hoàn trả dự kiến",
  handover_user_id: "Người nhận bàn giao công việc",
  special_leave_type: "Loại chế độ nghỉ đặc biệt",
  room_name: "Phòng họp / Không gian",
  room_code: "Phòng họp",
  leave_kind: "Hình thức nghỉ",
  vehicle_code: "Xe công vụ",
  pickup_location: "Điểm đón",
  dropoff_location: "Điểm đến",
  passenger_count: "Số hành khách",
  driver_required: "Yêu cầu tài xế",
  asset_category: "Nhóm thiết bị / Tài sản",
  booking_date: "Ngày sử dụng",
  start_time: "Giờ bắt đầu",
  end_time: "Giờ kết thúc",
  attendees_count: "Số người tham dự",
  purpose: "Mục đích sử dụng",
  expense_category: "Hạng mục chi phí",
  amount_vnd: "Giá trị / Số tiền (VND)",
  amount: "Số tiền (VND)",
  invoice_number: "Số hóa đơn / Chứng từ",
  beneficiary_account: "Tài khoản thụ hưởng",
  app_code: "Hệ thống / Ứng dụng",
  requested_role: "Quyền đề nghị",
  duration_days: "Thời hạn sử dụng (ngày)",
  facility_zone: "Khu vực cần ra vào",
  access_window: "Khung giờ đăng ký",
  destination: "Địa điểm công tác",
  transportation: "Phương tiện di chuyển",
  support_category: "Nhóm hỗ trợ kỹ thuật",
  change_type: "Phân loại thay đổi / hỗ trợ",
  urgency: "Mức độ ưu tiên",
  priority: "Độ ưu tiên",
  device_asset_tag: "Mã tài sản / Tên thiết bị",
  item_name: "Tên thiết bị / Vật tư",
  quantity: "Số lượng",
  specification: "Cấu hình / Thông số kỹ thuật",
  specs: "Cấu hình kỹ thuật",
  location: "Địa điểm sử dụng",
  leave_type: "Loại nghỉ phép",
  leave_days: "Số ngày nghỉ",
  evidence_file: "Tài liệu minh chứng",
  item_list: "Danh sách vật phẩm",
  device_type: "Loại thiết bị",
  work_date: "Ngày làm việc",
  overtime_hours: "Số giờ làm thêm",
  task_description: "Nội dung công việc",
  estimated_budget: "Dự toán kinh phí (VND)",
  estimated_price: "Đơn giá dự kiến (VND)",
  estimated_cost: "Chi phí dự kiến (VND)",
  vendor_quote_file: "Báo giá nhà cung cấp",
  quotation_file: "Tệp báo giá đính kèm",
  issue_location: "Vị trí sự cố",
  issue_description: "Mô tả sự cố",
  photo_evidence: "Ảnh chụp hiện trạng",
  customer_id: "Mã khách hàng",
  order_id: "Mã đơn hàng",
  refund_amount: "Số tiền hoàn / đền bù (VND)",
  source_warehouse: "Kho xuất",
  destination_warehouse: "Kho nhập",
  sku_list: "Danh mục mã hàng (SKU)",
  campaign_name: "Tên chiến dịch",
  discount_percent: "Mức giảm giá (%)",
  max_budget: "Ngân sách tối đa (VND)",
  partner_name: "Tên đối tác",
  contract_value: "Giá trị hợp đồng (VND)",
  contract_pdf: "Bản thảo hợp đồng (PDF)",
  environment: "Môi trường hệ thống",
  data_scope: "Phạm vi dữ liệu",
  release_version: "Phiên bản phát hành",
  change_log: "Nội dung thay đổi",
  rollback_plan: "Phương án hoàn tác",
  test_report_file: "Báo cáo kiểm thử (UAT)",
  server_ip: "Địa chỉ IP / Máy chủ",
  port_range: "Dải cổng mạng",
  protocol: "Giao thức kết nối",
  adjustment_date: "Ngày điều chỉnh công",
  check_in_time: "Giờ vào thực tế",
  check_out_time: "Giờ ra thực tế",
  explanation: "Giải trình chi tiết",
  system_name: "Tên phần mềm / Hệ thống",
  access_level: "Mức quyền truy cập",
  candidate_name: "Họ tên nhân sự mới",
  position: "Vị trí công việc",
  onboard_date: "Ngày nhận việc",
  equipment_pack: "Gói thiết bị tiêu chuẩn",
  last_working_day: "Ngày làm việc cuối cùng",
  handover_doc: "Biên bản bàn giao",
  asset_checklist: "Danh mục tài sản hoàn trả",
  ot_date: "Ngày làm thêm giờ",
  hours: "Số giờ",
  project_code: "Mã dự án",
  wfh_plan: "Kế hoạch công việc từ xa",
  resource_type: "Loại tài nguyên",
  resource_id: "Mã phòng / Xe công vụ",
  bank_account: "Tài khoản ngân hàng nhận",
  expected_settlement_date: "Ngày dự kiến hoàn ứng",
  board_resolution: "Nghị quyết / Tờ trình phê duyệt",
  expense_date: "Ngày phát sinh chi phí",
  receipt_file: "Chứng từ / Hóa đơn đính kèm",
  contract_no: "Số hợp đồng",
  vendor_name: "Tên nhà cung cấp",
  tax_code: "Mã số thuế",
  invoice_pdf: "Hóa đơn điện tử (PDF)",
  system_code: "Mã hệ thống / CSDL",
  access_type: "Loại quyền truy cập",
  software_name: "Tên phần mềm",
  seats: "Số lượng bản quyền",
  billing_cycle: "Chu kỳ thanh toán",
  urgency_level: "Mức độ khẩn cấp",
  visitor_name: "Họ tên khách / đối tác",
  visitor_org: "Đơn vị / Công ty đối tác",
  visit_date: "Ngày ra vào",
  customer_name: "Tên pháp nhân khách hàng",
  contract_code: "Mã hợp đồng / đơn hàng",
  course_name: "Tên khóa học / chứng chỉ",
  provider: "Đơn vị đào tạo / Tổ chức cấp",
  effective_date: "Ngày hiệu lực",
  employee_code: "Mã nhân viên",
  target_department: "Phòng ban tiếp nhận",
  new_position: "Chức danh / Vị trí mới",
  deal_value_vnd: "Tổng giá trị đơn hàng gốc (VND)",
  supplier_name: "Tên pháp nhân nhà cung cấp",
  supply_category: "Nhóm hàng hóa / dịch vụ cung ứng",
  job_title: "Vị trí / Chức danh",
  headcount: "Số lượng cần tuyển",
  salary_budget_vnd: "Quỹ lương dự kiến / tháng (VND)",
  target_channel: "Kênh triển khai chính",
  asset_code: "Mã tài sản cố định",
  disposal_method: "Hình thức xử lý tài sản",
  residual_value_vnd: "Giá trị thu hồi / còn lại (VND)",
  fiscal_quarter: "Kỳ ngân sách (Quý / Năm)",
  source_budget_code: "Mã ngân sách nguồn (Điều giảm)",
  target_budget_code: "Mã ngân sách đích (Bổ sung)",
  system_affected: "Hệ thống / Dịch vụ bị ảnh hưởng",
  severity_level: "Mức độ nghiêm trọng",
  hotfix_version: "Phiên bản bản vá",
  result_note: "Ghi chú kết quả thực hiện",
  external_reference: "Mã tham chiếu nghiệm thu / hệ thống ngoài",
  attachment_ids: "Tệp đính kèm",
  requester_name: "Người gửi yêu cầu",
  department_name: "Phòng ban",
  current_assignee_name: "Người đang xử lý",
  due_at: "Hạn xử lý",
};

export function resolveFieldLabel(name, { technical = false } = {}) {
  if (!name) return "Thông tin";
  if (fieldLabels[name]) return fieldLabels[name];
  if (technical) return name;
  return "Thông tin bổ sung";
}

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
    revokeAi: granted.has("APPROVER") && !own && r.status === "COMPLETED" &&
      Boolean(r.ai_auto_approval?.revocable) &&
      Date.now() < Date.parse(r.ai_auto_approval?.revocable_until || 0),
  };
}

export const date = (v) => (v ? new Date(v).toLocaleString("vi-VN") : "—");

const FIELD_REASON_LABELS = {
  REQUIRED: "Vui lòng nhập thông tin bắt buộc",
  FIELD_REQUIRED: "Vui lòng nhập thông tin bắt buộc",
  INVALID_TYPE: "Định dạng dữ liệu không hợp lệ",
  INVALID_FORMAT: "Định dạng không đúng quy chuẩn",
  MIN_LENGTH: "Nội dung quá ngắn so với quy định",
  MAX_LENGTH: "Nội dung vượt quá độ dài cho phép",
  MIN_VALUE: "Giá trị thấp hơn mức tối thiểu cho phép",
  MAX_VALUE: "Giá trị vượt quá hạn mức tối đa cho phép",
  OUT_OF_RANGE: "Giá trị nằm ngoài phạm vi cho phép",
  UNKNOWN_EXTERNAL_CODE: "Mã danh mục không tồn tại trên hệ thống tích hợp",
  EXTERNAL_CODE_INACTIVE: "Danh mục đã chọn hiện đang tạm ngưng hoặc bảo trì",
  ROLE_NOT_IN_APPLICATION: "Quyền đề nghị không thuộc ứng dụng đã chọn",
  EXPENSE_DAILY_LIMIT_EXCEEDED: "Số tiền vượt hạn mức chi tiêu theo ngày của hạng mục này",
  END_BEFORE_START: "Thời gian kết thúc phải sau thời gian bắt đầu",
  END_MUST_BE_AFTER_START: "Giờ kết thúc phải sau giờ bắt đầu",
  INVALID_TIME_FORMAT: "Giờ phải theo định dạng HH:MM (ví dụ 09:30)",
  INVALID_ISO_DATETIME: "Ngày giờ không đúng định dạng",
  TIMEZONE_REQUIRED: "Ngày giờ cần kèm múi giờ; vui lòng chọn lại bằng bộ chọn ngày giờ",
  ADVANCE_AMOUNT_MUST_BE_BELOW_10M: "Biểu mẫu này dành cho khoản tạm ứng dưới 10.000.000 VNĐ; số lớn hơn hãy chọn biểu mẫu tạm ứng 10-50 triệu",
  ADVANCE_AMOUNT_MUST_BE_BETWEEN_10M_AND_50M: "Biểu mẫu này dành cho khoản tạm ứng từ 10.000.000 đến 50.000.000 VNĐ; hãy chọn đúng biểu mẫu theo số tiền",
  ADVANCE_AMOUNT_MUST_BE_OVER_50M: "Biểu mẫu này dành cho khoản tạm ứng trên 50.000.000 VNĐ; số nhỏ hơn hãy chọn biểu mẫu tạm ứng tương ứng",
  LEAVE_LONG_REQUIRES_MORE_THAN_TWO_DAYS: "Nghỉ dài ngày phải từ 3 ngày trở lên; nghỉ ngắn hơn hãy dùng biểu mẫu nghỉ phép thường",
  USE_LONG_LEAVE_FOR_THREE_OR_MORE_DAYS: "Nghỉ từ 3 ngày trở lên hãy dùng biểu mẫu nghỉ dài ngày",
  SOURCE_AND_DESTINATION_MUST_DIFFER: "Kho nhập phải khác kho xuất",
  SOURCE_AND_TARGET_BUDGET_MUST_DIFFER: "Ngân sách nhận phải khác ngân sách chuyển đi",
  DISCOUNT_EXCEEDS_DEAL_VALUE: "Giá trị chiết khấu không được lớn hơn giá trị hợp đồng",
  INVALID_PROPERTY_SCHEMA: "Biểu mẫu đang được cấu hình lại; vui lòng thử lại sau hoặc báo quản trị",
  NO_PUBLISHED_RELEASE: "Loại yêu cầu này chưa có quy trình được công bố",
  NO_REQUESTER_MEMBERSHIP: "Tài khoản chưa được cấp quyền tạo yêu cầu",
  TYPE_INACTIVE: "Loại yêu cầu này đang tạm ngưng",
};

function formatFieldIssueItem(item) {
  if (!item) return "";
  const text = String(item).trim();
  if (FIELD_REASON_LABELS[text]) return FIELD_REASON_LABELS[text];
  // Translate quota codes inside HRM messages like "Quỹ ANNUAL còn 5 ngày"
  return text
    .replace(/\bANNUAL\b/g, "nghỉ phép năm")
    .replace(/\bPARENTAL\b/g, "nghỉ thai sản")
    .replace(/\bSICK\b/g, "nghỉ ốm")
    .replace(/^INVALID_[A-Z0-9_]+$/, "Giá trị không hợp lệ");
}

function formatValidationFields(rawFields) {
  if (!rawFields) return "";
  if (Array.isArray(rawFields)) {
    const names = rawFields.map((f) => fieldLabels[f] || "Trường thông tin").filter(Boolean);
    return names.length ? ` (Kiểm tra lại: ${names.join(", ")})` : "";
  }
  if (typeof rawFields === "object") {
    const parts = [];
    for (const [key, issues] of Object.entries(rawFields)) {
      const label = fieldLabels[key] || "Thông tin biểu mẫu";
      const list = Array.isArray(issues) ? issues : [issues];
      const detail = list.map(formatFieldIssueItem).filter(Boolean).join(", ");
      parts.push(detail ? `${label}: ${detail}` : label);
    }
    return parts.length ? ` — ${parts.join("; ")}` : "";
  }
  return "";
}

const ERROR_MESSAGES = {
  ACCESS_DENIED: "Bạn không có quyền truy cập vào khu vực này.",
  UNAUTHORIZED: "Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.",
  AUTHENTICATION_REQUIRED: "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại để tiếp tục.",
  FORBIDDEN: "Tài khoản của bạn không có quyền thực hiện thao tác này.",
  MODULE_FORBIDDEN: "Bạn chưa được cấp quyền sử dụng phân hệ chức năng này.",
  ADMIN_PORTAL_ONLY: "Tài khoản quản trị chỉ được phép thao tác trên Cổng Quản trị hệ thống.",
  ACTOR_NOT_ACTIVE: "Tài khoản hiện đang tạm khóa hoặc ngừng hoạt động.",
  SYSTEM_ACCOUNT_LOCKED: "Tài khoản hệ thống được bảo vệ và không thể thay đổi.",
  SELF_ADMIN_CHANGE_FORBIDDEN: "Theo nguyên tắc phân tách nhiệm vụ, bạn không thể tự thay đổi quyền của chính mình.",
  SO_D_VIOLATION: "Thao tác bị từ chối theo nguyên tắc phân tách nhiệm vụ (không tự duyệt/nghiệm thu hồ sơ của chính mình).",
  SOD_VIOLATION: "Thao tác bị từ chối theo nguyên tắc phân tách nhiệm vụ (không tự duyệt/nghiệm thu hồ sơ của chính mình).",
  VERSION_CONFLICT: "Hồ sơ vừa được cập nhật bởi người khác. Vui lòng tải lại trang trước khi tiếp tục.",
  STATE_CONFLICT: "Trạng thái hồ sơ đã thay đổi. Vui lòng tải lại để xem thông tin mới nhất.",
  REQUEST_STATE_CONFLICT: "Trạng thái hồ sơ đã thay đổi. Vui lòng tải lại để xem thông tin mới nhất.",
  LIFECYCLE_CONFLICT: "Quy trình xử lý của hồ sơ không hỗ trợ thao tác ở bước hiện tại.",
  TARGET_IMMUTABLE: "Dữ liệu này đã chốt và không thể chỉnh sửa.",
  EXPECTED_VERSION_REQUIRED: "Thiếu thông tin phiên bản hồ sơ. Vui lòng tải lại trang và thử lại.",
  ACTIVE_STEP_NOT_FOUND: "Hiện không còn bước xử lý nào đang mở cho bạn trên hồ sơ này.",
  REQUEST_NOT_FOUND: "Không tìm thấy hồ sơ yêu cầu hoặc bạn không có quyền xem hồ sơ này.",
  NOT_FOUND: "Không tìm thấy dữ liệu yêu cầu.",
  RESOURCE_NOT_FOUND: "Không tìm thấy tài nguyên được chọn.",
  USER_NOT_FOUND: "Không tìm thấy thông tin nhân sự.",
  REVISION_NOT_FOUND: "Không tìm thấy phiên bản nội dung của hồ sơ.",
  REQUEST_TYPE_NOT_FOUND: "Loại yêu cầu không tồn tại trong danh mục hệ thống.",
  UNKNOWN_TYPE_CODE: "Loại yêu cầu chưa được đăng ký trong danh mục.",
  TYPE_CODE_REQUIRED: "Vui lòng chọn loại yêu cầu trước khi tiếp tục.",
  TITLE_REQUIRED: "Vui lòng nhập tiêu đề yêu cầu.",
  DECISION_REASON_REQUIRED: "Vui lòng nhập lý do chi tiết (tối thiểu 10 ký tự) cho quyết định này.",
  CANCELLATION_REASON_REQUIRED: "Vui lòng nhập lý do hủy yêu cầu (tối thiểu 10 ký tự).",
  ACCEPTANCE_REASON_REQUIRED: "Vui lòng nhập nhận xét nghiệm thu (tối thiểu 10 ký tự).",
  REVOKE_REASON_REQUIRED: "Vui lòng nhập lý do thu hồi phê duyệt tự động.",
  DELEGATION_REASON_REQUIRED: "Vui lòng nhập lý do ủy quyền phê duyệt.",
  REASON_INVALID: "Lý do nhập vào chưa hợp lệ (cần từ 10 đến 2.000 ký tự).",
  RESULT_NOTE_INVALID: "Vui lòng nhập ghi chú kết quả thực hiện rõ ràng hơn (tối thiểu 10 ký tự).",
  EXTERNAL_REFERENCE_INVALID: "Mã tham chiếu kết quả thực hiện không hợp lệ.",
  ISSUE_REASON_INVALID: "Vui lòng mô tả chi tiết vướng mắc phát sinh (tối thiểu 10 ký tự).",
  DELEGATION_OVERLAP: "Khoảng thời gian này đã trùng với một ủy quyền đang hiệu lực khác.",
  DELEGATE_NOT_APPROVER: "Người nhận ủy quyền phải là nhân sự có vai trò Phê duyệt đang hoạt động.",
  CANNOT_DELEGATE_TO_SELF: "Bạn không thể tự ủy quyền phê duyệt cho chính mình.",
  INVALID_DELEGATION: "Thông tin thiết lập ủy quyền chưa hợp lệ.",
  INVALID_DELEGATION_WINDOW: "Khoảng thời gian ủy quyền không hợp lệ (tối đa 90 ngày và ngày kết thúc phải sau ngày bắt đầu).",
  DELEGATION_NOT_INSTALLED: "Chức năng ủy quyền phê duyệt hiện đang tạm ngưng.",
  AI_APPROVAL_NOT_REVOCABLE: "Đã quá thời hạn 24 giờ hoặc hồ sơ không phải do AI tự động duyệt nên không thể thu hồi.",
  AI_SERVICE_UNAVAILABLE: "Trợ lý AI hiện đang bận hoặc bảo trì. Bạn vẫn có thể gửi và xử lý hồ sơ bình thường.",
  APPROVER_ROLE_ADMIN_ONLY: "Chỉ Quản trị viên được cấp vai trò Người phê duyệt.",
  AUDITOR_ROLE_ADMIN_ONLY: "Chỉ Quản trị viên được cấp vai trò Kiểm toán viên.",
  CACHE_UNAVAILABLE: "Hệ thống bảo mật tạm thời gián đoạn. Vui lòng thử lại sau vài giây.",
  AI_SERVICE_ERROR: "Trợ lý AI tạm thời chưa phản hồi được yêu cầu phân tích. Vui lòng thử lại sau.",
  INTEGRATION_UNAVAILABLE: "Kết nối đến hệ thống nghiệp vụ liên quan (Nhân sự / Tài chính / CNTT / Hành chính) đang tạm ngắt hoặc bảo trì. Vui lòng thử lại sau.",
  LEAVE_BALANCE_EXCEEDED: "Số ngày đăng ký vượt quá quỹ ngày phép còn lại của bạn trên hệ thống Nhân sự.",
  BUDGET_EXCEEDED: "Giá trị đề nghị vượt quá hạn mức ngân sách khả dụng của phòng ban trong năm nay.",
  EXPENSE_DAILY_LIMIT_EXCEEDED: "Số tiền vượt hạn mức chi tiêu theo ngày của hạng mục chi phí đã chọn.",
  ROLE_NOT_IN_APPLICATION: "Quyền truy cập đề nghị không thuộc hệ thống/ứng dụng đã chọn.",
  RESOURCE_UNAVAILABLE: "Phòng họp / Xe công vụ / Thiết bị đã có lịch đặt trùng trong khung giờ này. Vui lòng chọn khung giờ hoặc tài nguyên khác.",
  RESOURCE_PREEMPTED: "Tài nguyên vừa được ưu tiên cấp cho một yêu cầu khẩn cấp hơn. Vui lòng chọn khung giờ hoặc tài nguyên khác.",
  RESOURCE_OUT_OF_SERVICE: "Phòng họp / Xe công vụ / Thiết bị này đang bảo trì hoặc tạm ngưng phục vụ.",
  RESOURCE_CAPACITY_EXCEEDED: "Số người tham dự vượt quá sức chứa tiêu chuẩn của phòng họp / xe đã chọn.",
  RESOURCE_UNKNOWN: "Tài nguyên đã chọn không tồn tại hoặc đã ngừng sử dụng.",
  ASSIGNEE_UNAVAILABLE: "Người phụ trách xử lý hiện đang vắng mặt và chưa có người nhận ủy quyền thay thế.",
  ASSIGNEE_INVALID: "Người được phân công xử lý không hợp lệ hoặc không thuộc phạm vi phụ trách.",
  ROUTE_ACTOR_INACTIVE: "Một nhân sự trong tuyến duyệt hiện đã ngừng hoạt động. Vui lòng báo Quản trị quy chế cập nhật.",
  ROUTE_CONFIGURATION_INVALID: "Tuyến phê duyệt của loại yêu cầu này chưa đủ người phụ trách hợp lệ. Vui lòng liên hệ bộ phận Quản trị quy chế.",
  ROUTE_SOD_ESCALATION_UNRESOLVED: "Không tìm thấy người quản lý cấp trên đủ quyền thay thế để tránh tự duyệt. Vui lòng liên hệ quản trị để cập nhật sơ đồ tổ chức và quyền phê duyệt.",
  INVALID_PORTAL: "Yêu cầu đăng nhập không hợp lệ. Vui lòng tải lại trang và thử lại.",
  REQUEST_TYPE_NOT_CONFIGURED: "Loại yêu cầu này hiện chưa có quy trình phê duyệt được công bố.",
  CATALOG_EXPANSION_DISABLED: "Chức năng mở rộng danh mục hiện đang khóa.",
  ATTACHMENT_REQUIRED: "Loại yêu cầu này bắt buộc đính kèm chứng từ / tài liệu hợp lệ trước khi gửi.",
  EXECUTION_EVIDENCE_REQUIRED: "Vui lòng tải lên tệp minh chứng kết quả thực hiện trước khi hoàn tất.",
  EQUIPMENT_QUOTE_REQUIRED: "Đề nghị mua sắm thiết bị vượt ngưỡng quy định bắt buộc đính kèm báo giá nhà cung cấp.",
  ATTACHMENT_NOT_CLEAN: "Tệp đính kèm đang được quét an toàn hoặc không hợp lệ. Vui lòng kiểm tra lại tệp.",
  ATTACHMENT_NOT_READY: "Tệp đính kèm đang trong quá trình kiểm tra an toàn, vui lòng đợi vài giây rồi thử lại.",
  ATTACHMENT_INVALID: "Định dạng tệp đính kèm không được hỗ trợ hoặc tệp bị hỏng.",
  ATTACHMENT_NOT_FOUND: "Không tìm thấy tệp đính kèm trên hệ thống lưu trữ.",
  FILE_REQUIRED: "Vui lòng chọn tệp tài liệu để tải lên.",
  FILE_NAME_INVALID: "Tên tệp không hợp lệ. Vui lòng đổi tên tệp ngắn gọn và không chứa ký tự đặc biệt.",
  FILE_SIZE_INVALID: "Dung lượng tệp vượt quá giới hạn cho phép (tối đa 10 MB) hoặc tệp rỗng.",
  FILE_NOT_READY: "Tệp chưa sẵn sàng để tải xuống.",
  STORAGE_UNAVAILABLE: "Dịch vụ lưu trữ tệp đính kèm đang tạm gián đoạn. Vui lòng thử lại sau ít phút.",
  DEPARTMENT_SCOPE_VIOLATION: "Bạn chỉ được phép tạo hoặc xử lý hồ sơ thuộc phạm vi phòng ban của mình.",
  AMOUNT_NOT_ALLOWED: "Loại yêu cầu này không áp dụng trường số tiền.",
  INVALID_AMOUNT: "Số tiền nhập vào không hợp lệ (vui lòng nhập số nguyên dương).",
  INVALID_TIME_RANGE: "Khoảng thời gian bắt đầu và kết thúc không hợp lệ.",
  INVALID_DATETIME: "Ngày hoặc giờ nhập vào không đúng định dạng.",
  INVALID_DATE_FILTER: "Bộ lọc khoảng ngày chưa đúng định dạng.",
  PERIOD_INVALID: "Khoảng thời gian thống kê không hợp lệ (ngày bắt đầu phải trước ngày kết thúc và tối đa 12 tháng).",
  INVALID_PAGINATION: "Tham số phân trang không hợp lệ.",
  INVALID_SEARCH: "Từ khóa tìm kiếm không hợp lệ.",
  INVALID_PAYLOAD: "Thông tin biểu mẫu gửi lên chưa đúng quy chuẩn. Vui lòng kiểm tra lại các trường đã nhập.",
  INVALID_DRAFT_REQUEST: "Thông tin lưu nháp chưa hợp lệ. Vui lòng kiểm tra lại các trường trong biểu mẫu.",
  INVALID_SUBMISSION: "Thông tin gửi duyệt chưa đầy đủ hoặc không hợp lệ.",
  UNKNOWN_FIELD: "Biểu mẫu có trường thông tin không thuộc cấu hình hiện hành. Vui lòng tải lại trang.",
  INVALID_CREDENTIALS: "Email đăng nhập hoặc mật khẩu không chính xác.",
  INVALID_CURRENT_PASSWORD: "Mật khẩu hiện tại không chính xác.",
  INVALID_PASSWORD_CHANGE: "Thông tin đổi mật khẩu chưa đầy đủ hoặc không hợp lệ.",
  PASSWORD_CHANGE_REQUIRED: "Bạn cần đổi mật khẩu lần đầu trước khi sử dụng hệ thống.",
  PASSWORD_REUSE_NOT_ALLOWED: "Mật khẩu mới không được trùng với mật khẩu đang sử dụng.",
  PASSWORD_POLICY_VIOLATION: "Mật khẩu mới cần dài từ 15–128 ký tự, bao gồm chữ hoa, chữ thường, chữ số, ký tự đặc biệt và không chứa địa chỉ email của bạn.",
  LOGIN_RATE_LIMITED: "Tài khoản tạm khóa đăng nhập ngắn hạn do nhập sai nhiều lần. Vui lòng thử lại sau ít phút.",
  PASSWORD_CHANGE_RATE_LIMITED: "Bạn đã nhập sai mật khẩu hiện tại quá số lần quy định. Vui lòng thử lại sau ít phút.",
  PASSWORD_RESET_DELIVERY_FAILED: "Không thể gửi thông báo đặt lại mật khẩu lúc này. Vui lòng liên hệ bộ phận CNTT.",
  DATABASE_QUERY_FAILED: "Hệ thống gặp sự cố khi truy xuất dữ liệu. Vui lòng thử lại sau ít phút.",
  DATABASE_TEMPORARILY_UNAVAILABLE: "Kết nối dữ liệu đang bận. Vui lòng thử lại sau vài giây.",
  SERVER_ERROR: "Hệ thống đang bận xử lý hoặc gặp sự cố tạm thời. Vui lòng thử lại sau.",
  INTERNAL_SERVER_ERROR: "Hệ thống gặp sự cố nội bộ tạm thời. Vui lòng thử lại sau.",
  INVALID_RESPONSE: "Phản hồi từ máy chủ bị gián đoạn. Vui lòng tải lại trang và thử lại.",
  REQUEST_TIMEOUT_UNKNOWN: "Kết nối quá thời gian chờ phản hồi. Vui lòng kiểm tra lại danh sách hồ sơ trước khi gửi lại để tránh trùng lặp.",
  IDEMPOTENCY_KEY_REQUIRED: "Phiên gửi biểu mẫu thiếu khóa xác thực. Vui lòng thử lại.",
  IDEMPOTENCY_KEY_REUSED: "Thao tác đang được xử lý, vui lòng không bấm lặp lại.",
  VALIDATION_FAILED: "Một số thông tin trên biểu mẫu chưa hợp lệ",
  VALIDATION_STALE: "Cấu hình quy chế vừa thay đổi. Vui lòng kiểm tra lại trước khi thực hiện.",
};

export function errorText(e) {
  if (!e) return "Đã xảy ra lỗi không xác định. Vui lòng thử lại.";
  if (e.serverMessage) {
    return e.serverMessage;
  }
  const code = String(e.message || "").trim();
  const fieldSummary = formatValidationFields(e.fields);

  let base = ERROR_MESSAGES[code];
  if (!base) {
    if (e.status === 401) {
      base = "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
    } else if (e.status === 403) {
      base = "Bạn không có quyền thực hiện thao tác này.";
    } else if (e.status === 404) {
      base = "Không tìm thấy dữ liệu yêu cầu.";
    } else if (e.status === 429) {
      base = "Bạn đang thao tác quá nhanh. Vui lòng đợi ít phút rồi thử lại.";
    } else if (e.status >= 500) {
      base = "Hệ thống đang bận hoặc gặp sự cố tạm thời. Vui lòng thử lại sau.";
    } else if (/^INVALID_([A-Z0-9_]+)$/.test(code)) {
      const rawField = code.replace(/^INVALID_/, "").toLowerCase();
      const friendly = fieldLabels[rawField];
      base = friendly
        ? `Thông tin "${friendly}" chưa hợp lệ. Vui lòng kiểm tra lại.`
        : "Thông tin nhập vào chưa đúng định dạng quy định.";
    } else if (/^[A-Z0-9_]{4,}$/.test(code)) {
      base = "Không thể hoàn tất thao tác do dữ liệu chưa thỏa điều kiện nghiệp vụ. Vui lòng kiểm tra lại.";
    } else {
      base = code || "Không thể hoàn tất thao tác. Vui lòng thử lại.";
    }
  }

  const refSuffix = e.status >= 500 && e.correlationId
    ? ` (Mã hỗ trợ kỹ thuật: ${String(e.correlationId).slice(0, 8)})`
    : "";

  const text = `${base}${fieldSummary}${refSuffix}`.trim();
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

// Display names of enum values in request forms & detail views.
export const enumLabels = {
  CO_LUONG: "Nghỉ phép có hưởng lương",
  KHONG_LUONG: "Nghỉ không hưởng lương",
  KET_HON: "Nghỉ kết hôn",
  TANG_CHE: "Nghỉ tang chế",
  THAI_SAN: "Nghỉ thai sản",
  NGHI_OM_DAI_NGAY: "Nghỉ ốm dài ngày",
  KHAC: "Trường hợp khác",
  MAY_BAY: "Máy bay",
  TAU_HOA: "Tàu hỏa",
  XE_CONG_TY: "Xe công vụ công ty",
  XE_KHACH_TAXI: "Xe khách / Taxi",
  BINH_THUONG: "Bình thường",
  THAP: "Thấp",
  TRUNG_BINH: "Trung bình",
  CAO: "Cao",
  KHAN_CAP: "Khẩn cấp",
  LOW: "Thấp",
  MEDIUM: "Trung bình",
  HIGH: "Cao",
  CRITICAL: "Nghiêm trọng",
  ANNUAL: "Phép năm",
  PARENTAL: "Thai sản",
  SICK: "Nghỉ ốm",
  MEETING_ROOM: "Phòng họp",
  VEHICLE: "Xe công vụ",
  AVAILABLE: "Sẵn sàng",
  RESERVED: "Đã đặt lịch",
  MAINTENANCE: "Đang bảo trì",
  DANG_LAM: "Đang làm việc",
  NGHI_LAM: "Đang nghỉ phép",
  CONG_TAC: "Đang công tác",
  NGOAI_GIO: "Ngoài giờ làm việc",
  USER: "Nhân sự",
  SYSTEM: "Hệ thống tự động",
  AI: "Trợ lý AI",
  PASS: "Toàn vẹn hợp lệ",
  FAIL: "Phát hiện sai lệch",
};
