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
export const fieldLabels = {
  title: "Tiêu đề yêu cầu",
  reason: "Lý do / Diễn giải chi tiết",
  start_date: "Ngày bắt đầu",
  end_date: "Ngày kết thúc",
  handover_user_id: "Người nhận bàn giao công việc",
  special_leave_type: "Loại chế độ nghỉ đặc biệt",
  room_name: "Phòng họp / Không gian",
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
  duration_days: "Số ngày",
  facility_zone: "Khu vực cần ra vào",
  access_window: "Khung giờ đăng ký",
  destination: "Địa điểm công tác",
  transportation: "Phương tiện di chuyển",
  support_category: "Nhóm hỗ trợ kỹ thuật",
  urgency: "Mức độ ưu tiên",
  device_asset_tag: "Mã tài sản / Tên thiết bị",
  item_name: "Tên thiết bị / Vật tư",
  quantity: "Số lượng",
  specification: "Cấu hình / Thông số kỹ thuật",
  specs: "Cấu hình",
  location: "Nơi sử dụng",
  leave_type: "Loại nghỉ phép",
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
  environment: "Môi trường dữ liệu",
  data_scope: "Phạm vi dữ liệu",
  release_version: "Phiên bản phát hành",
  change_log: "Nội dung thay đổi",
  rollback_plan: "Phương án hoàn tác (Rollback)",
  test_report_file: "Báo cáo kiểm thử (UAT)",
  server_ip: "Địa chỉ IP / Máy chủ",
  port_range: "Dải cổng (Port)",
  protocol: "Giao thức",
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
  vendor_name: "Tên nhà cung cấp (Vendor)",
  tax_code: "Mã số thuế",
  invoice_pdf: "Hóa đơn điện tử (PDF)",
  system_code: "Mã hệ thống / CSDL",
  access_type: "Loại quyền truy cập",
  software_name: "Tên phần mềm",
  seats: "Số lượng license (Seats)",
  billing_cycle: "Chu kỳ thanh toán",
  asset_category: "Nhóm tài sản",
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
  job_title: "Vị trí / Chức danh tuyển dụng",
  headcount: "Số lượng cần tuyển",
  salary_budget_vnd: "Quỹ lương dự kiến / tháng (VND)",
  target_channel: "Kênh triển khai chính",
  asset_code: "Mã tài sản cố định",
  disposal_method: "Hình thức xử lý (Thanh lý / Tiêu hủy)",
  residual_value_vnd: "Giá trị thu hồi / Giá trị còn lại (VND)",
  fiscal_quarter: "Kỳ ngân sách (Quý / Năm)",
  source_budget_code: "Mã ngân sách nguồn (Điều giảm)",
  target_budget_code: "Mã ngân sách đích (Bổ sung)",
  system_affected: "Hệ thống / Dịch vụ bị ảnh hưởng",
  severity_level: "Mức độ nghiêm trọng (CVSS / P0-P1)",
  hotfix_version: "Phiên bản bản vá / Commit tag",
  // Thuộc tính hệ thống & CSDL
  id: "Mã định danh",
  event_id: "Mã sự kiện",
  aggregate_id: "Mã đối tượng",
  actor_id: "Mã người thực hiện",
  actor_name: "Người thực hiện",
  actor_role: "Vai trò thực hiện",
  action: "Hành động",
  target_type: "Loại đối tượng",
  target_id: "Mã đối tượng đích",
  recorded_at: "Thời gian ghi nhận",
  occurred_at: "Thời gian diễn ra",
  client_ip: "Địa chỉ IP",
  user_id: "Mã người dùng",
  username: "Tên đăng nhập",
  display_name: "Họ và tên",
  department_id: "Phòng ban",
  department_name: "Tên phòng ban",
  department_code: "Mã phòng ban",
  manager_id: "Người quản lý trực tiếp",
  manager_name: "Họ tên người quản lý",
  is_active: "Trạng thái hoạt động",
  role: "Vai trò",
  roles: "Danh sách vai trò",
  scope_kind: "Phạm vi phòng ban",
  type_scope: "Phạm vi loại đơn",
  type_id: "Loại yêu cầu",
  valid_from: "Hiệu lực từ ngày",
  valid_to: "Hiệu lực đến ngày",
  lock_version: "Phiên bản khóa",
  expected_version: "Phiên bản kỳ vọng",
  revision: "Phiên bản sửa đổi",
  revision_no: "Số thứ tự phiên bản",
  created_at: "Ngày khởi tạo",
  updated_at: "Ngày cập nhật",
  submitted_at: "Ngày nộp đơn",
  approved_at: "Ngày phê duyệt",
  completed_at: "Ngày hoàn thành",
  scan_state: "Kiểm tra an toàn tệp",
  original_name: "Tên tệp gốc",
  size_bytes: "Dung lượng (bytes)",
  mime_type: "Định dạng tệp",
  mime: "Định dạng tệp",
  checksum_sha256: "Mã kiểm tra tệp (SHA-256)",
  hash: "Mã băm kiểm toán",
  prev_hash: "Mã băm sự kiện trước",
  verified: "Trạng thái xác minh",
  algorithm: "Thuật toán kiểm tra",
  chain_hash: "Mã băm chuỗi kiểm toán",
  count: "Số lượng bản ghi",
  code: "Mã hiệu",
  name: "Tên gọi",
  description: "Mô tả",
  category: "Nhóm nghiệp vụ",
  lifecycle: "Mẫu quy trình",
  risk_weight: "Trọng số rủi ro",
  approval_level: "Cấp độ phê duyệt",
  status: "Trạng thái",
  due_at: "Hạn xử lý",
  breached_at: "Thời điểm quá hạn",
  result_note: "Ghi chú kết quả",
  external_reference: "Mã tham chiếu ngoài",
  reason: "Lý do",
  outcome: "Kết quả quyết định",
  decided_at: "Thời điểm quyết định",
  attempt_no: "Lần thực hiện",
  step_no: "Bước phê duyệt",
  tier_level: "Cấp phê duyệt",
  resolver_code: "Chức danh xử lý",
};

export function humanizeKey(key) {
  if (!key) return "—";
  if (fieldLabels[key]) return fieldLabels[key];
  const cleaned = key.replace(/([A-Z])/g, "_$1").toLowerCase();
  if (fieldLabels[cleaned]) return fieldLabels[cleaned];
  return key
    .replace(/_id$/, " (Mã)")
    .replace(/_at$/, " (Thời gian)")
    .replace(/_vnd$/, " (VNĐ)")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatCurrency(amount) {
  if (amount === null || amount === undefined || amount === "") return "—";
  const num = Number(amount);
  if (isNaN(num)) return String(amount);
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(num);
}

const VI_UNITS = ["", " nghìn", " triệu", " tỷ", " nghìn tỷ", " triệu tỷ"];
const VI_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"];

function readGroupThree(group, isFirst) {
  const h = Math.floor(group / 100);
  const t = Math.floor((group % 100) / 10);
  const u = group % 10;
  if (h === 0 && t === 0 && u === 0) return "";
  let res = "";
  if (h > 0 || !isFirst) res += VI_DIGITS[h] + " trăm ";
  if (t === 0 && u !== 0) {
    if (h > 0 || !isFirst) res += "lẻ ";
    res += VI_DIGITS[u];
  } else if (t === 1) {
    res += "mười ";
    if (u === 5) res += "lăm";
    else if (u > 0) res += VI_DIGITS[u];
  } else if (t > 1) {
    res += VI_DIGITS[t] + " mươi ";
    if (u === 1) res += "mốt";
    else if (u === 5) res += "lăm";
    else if (u > 0) res += VI_DIGITS[u];
  } else if (u > 0) {
    res += VI_DIGITS[u];
  }
  return res.trim();
}

export function numberToVietnameseWords(amount) {
  let num = Math.floor(Math.abs(Number(amount)));
  if (!num || isNaN(num)) return "";
  if (num === 0) return "Không đồng";
  const groups = [];
  while (num > 0) {
    groups.push(num % 1000);
    num = Math.floor(num / 1000);
  }
  let words = "";
  for (let i = groups.length - 1; i >= 0; i--) {
    const g = groups[i];
    if (g > 0) {
      const read = readGroupThree(g, i === groups.length - 1);
      words += (words ? " " : "") + read + VI_UNITS[i];
    }
  }
  const capitalized = words.trim().charAt(0).toUpperCase() + words.trim().slice(1) + " đồng";
  return capitalized;
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
    ADMIN_PORTAL_ONLY: "Tài khoản quản trị chỉ được phép sử dụng chức năng quản lý hệ thống.",
    REQUEST_TIMEOUT_UNKNOWN: "Kết nối quá thời gian xử lý. Kiểm tra trạng thái trước khi thực hiện lại để tránh trùng lặp.",
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
    SO_D_VIOLATION: "Quy định kiểm soát nội bộ (SoD): Bạn không được tự phê duyệt hoặc xử lý yêu cầu do chính mình khởi tạo.",
    UNAUTHORIZED_SCOPE: "Tài khoản của bạn không có thẩm quyền trên phòng ban hoặc loại yêu cầu này.",
    REQUEST_NOT_FOUND: "Không tìm thấy hồ sơ yêu cầu trong hệ thống.",
    ATTACHMENT_NOT_FOUND: "Không tìm thấy tệp đính kèm yêu cầu.",
    FILE_TOO_LARGE: "Dung lượng tệp vượt quá giới hạn 10 MB cho phép.",
    FILE_TYPE_NOT_ALLOWED: "Định dạng tệp không được hỗ trợ (chỉ chấp nhận PDF, JPG, PNG).",
    IDEMPOTENCY_KEY_REQUIRED: "Thiếu khóa chống gửi trùng lặp (Idempotency Key).",
    CONSTRAINT_CONFLICT: "Dữ liệu bị xung đột hoặc đã tồn tại trong cơ sở dữ liệu.",
    USER_NOT_FOUND: "Không tìm thấy thông tin người dùng được chỉ định.",
    DEPARTMENT_NOT_FOUND: "Không tìm thấy phòng ban được chỉ định.",
    ACCOUNT_DISABLED: "Tài khoản người dùng hiện đang ở trạng thái ngừng hoạt động.",
    PASSWORD_MISMATCH: "Mật khẩu xác nhận không khớp với mật khẩu mới.",
    STEP_NOT_FOUND: "Không tìm thấy bước duyệt tương ứng trong quy trình.",
    EXECUTION_ALREADY_CLAIMED: "Công việc đã được nhận bởi một người thực hiện khác.",
    ACCEPTANCE_NOT_READY: "Hồ sơ chưa hoàn thành thực hiện để chuyển sang nghiệm thu.",
  };

  let base = messages[e.message] || (e.status === 401
    ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
    : e.message || "Đã xảy ra lỗi không xác định. Vui lòng thử lại sau.");

  if (e.fields && typeof e.fields === "object") {
    const fieldDetails = Object.entries(e.fields).map(([k, val]) => {
      const label = fieldLabels[k] || humanizeKey(k);
      const msg = Array.isArray(val) ? val.join(", ") : String(val);
      return `${label}: ${msg}`;
    }).filter(Boolean);
    if (fieldDetails.length > 0) {
      base += ` (${fieldDetails.join("; ")})`;
    }
  }

  return base;
}
