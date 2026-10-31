// Static workflow illustrations. Lifecycle mapping is derived from the plan catalog;
// a request's released workflow lifecycle always takes precedence when available.
export const TYPE_LIFECYCLES = Object.freeze({
  "LEAVE_ANNUAL": "A",
  "LEAVE_LONG": "A",
  "RESIGNATION": "C",
  "OVERTIME_REQ": "B",
  "WFH_REQ": "A",
  "ROOM_VEHICLE": "B",
  "ADVANCE_SMALL": "B",
  "ADVANCE_MEDIUM": "B",
  "ADVANCE_LARGE": "B",
  "REIMBURSEMENT": "B",
  "VENDOR_PAYMENT": "C",
  "LAPTOP_PROVISION": "C",
  "SOFTWARE_ACCESS": "B",
  "PROD_DATA_ACCESS": "C",
  "SAAS_LICENSE_BUY": "C",
  "OFFICE_SUPPLIES": "B",
  "ASSET_PURCHASE": "C",
  "FACILITY_REPAIR": "C"
});

const asset = (id) => `${import.meta.env?.BASE_URL || "/"}flow-diagrams/${id}.webp`;
export const FLOW_DIAGRAMS = Object.freeze([
  { id: "create-submit", title: "Tạo và gửi yêu cầu", category: "Yêu cầu", description: "Tạo bản nháp, nhập dữ liệu, kiểm tra và gửi yêu cầu để bắt đầu quy trình." },
  { id: "lifecycle-a", title: "Vòng đời A · Phê duyệt", category: "Phê duyệt", lifecycle: "A", description: "Quy trình xử lý yêu cầu theo vòng đời A. Các cấp duyệt thực tế được xác định bởi quy chế đã công bố." },
  { id: "lifecycle-b", title: "Vòng đời B · Phê duyệt & thực hiện", category: "Phê duyệt", lifecycle: "B", description: "Quy trình phê duyệt, bàn giao thực hiện và cập nhật kết quả." },
  { id: "lifecycle-c", title: "Vòng đời C · Phê duyệt, thực hiện & nghiệm thu", category: "Phê duyệt", lifecycle: "C", description: "Quy trình có các bước phê duyệt, thực hiện và nghiệm thu kết quả." },
  { id: "revision", title: "Bổ sung và gửi lại", category: "Yêu cầu", description: "Xử lý hồ sơ cần bổ sung và tiếp tục quy trình sau khi người gửi chỉnh sửa." },
  { id: "cancel", title: "Hủy hoặc rút yêu cầu", category: "Yêu cầu", description: "Các nhánh xử lý khi rút yêu cầu; điều kiện thực tế tùy trạng thái và quyền của người thao tác." },
  { id: "admin", title: "Quản trị hệ thống", category: "Hệ thống", description: "Phân quyền, công bố cấu hình, giám sát hoạt động và kiểm toán trên cổng quản trị riêng." },
  { id: "ai", title: "AI hỗ trợ hồ sơ", category: "Hệ thống", description: "Các bước trích xuất, phân loại, đánh giá rủi ro và phản hồi cho người dùng khi dịch vụ hỗ trợ." },
  { id: "ui-sync", title: "Đồng bộ trạng thái giao diện", category: "Hệ thống", description: "Cập nhật dữ liệu, hiển thị thông báo thành công hoặc lỗi sau khi thao tác mà không cần tải lại trang." },
].map((item) => Object.freeze({ ...item, src: asset(item.id) })));

export function resolveLifecycle(request, explicitLifecycle) {
  const value = request?.workflow?.lifecycle || explicitLifecycle || TYPE_LIFECYCLES[request?.type_code];
  return ["A", "B", "C"].includes(value) ? value : null;
}

export function relevantDiagrams(request, explicitLifecycle) {
  const lifecycle = resolveLifecycle(request, explicitLifecycle);
  const ids = ["create-submit", lifecycle ? `lifecycle-${lifecycle.toLowerCase()}` : null, "revision", "cancel", "ai", "ui-sync"];
  return FLOW_DIAGRAMS.filter((item) => ids.includes(item.id));
}
