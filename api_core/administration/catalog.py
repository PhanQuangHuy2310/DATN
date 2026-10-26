"""SRS v2 access matrix and versioned API inventory.

P0 APIs are code-defined contracts. This catalog is read-only: editing a route,
secret or authorization rule from a browser is deliberately unsupported.
"""

ROLE_MATRIX = (
    {"role": "REQUESTER", "name": "Người yêu cầu", "read": "Yêu cầu sở hữu và lịch sử được tham gia", "write": "Nháp · gửi · bổ sung · hủy trước duyệt đủ", "constraints": "Không tự duyệt; DRAFT chỉ owner đọc", "uc": "UC03 · UC04 · UC07 · UC08"},
    {"role": "APPROVER", "name": "Người phê duyệt", "read": "Hồ sơ tham gia được giao", "write": "Duyệt · từ chối · yêu cầu bổ sung", "constraints": "ACTIVE step, phòng snapshot, loại, SoD", "uc": "UC06"},
    {"role": "EXECUTOR", "name": "Người thực hiện", "read": "Công việc được giao", "write": "Nhận việc · báo vướng · nộp kết quả", "constraints": "Attempt hiện hành, không duyệt thay", "uc": "UC10 · UC11"},
    {"role": "ACCEPTOR", "name": "Người nghiệm thu", "read": "Yêu cầu thuộc lượt nghiệm thu", "write": "Chấp nhận · yêu cầu làm lại", "constraints": "Chỉ loại C; khác executor thực tế", "uc": "UC12"},
    {"role": "POLICY_ADMIN", "name": "Quản trị chính sách", "read": "Cấu hình và audit quản trị cùng loại", "write": "Soạn · kiểm tra · công bố release", "constraints": "Không tự có quyền xem nội dung hồ sơ", "uc": "UC02"},
    {"role": "OPS_ADMIN", "name": "Điều phối vận hành", "read": "Metadata điều phối theo scope", "write": "Gán lại · replay event với lý do", "constraints": "Không tự duyệt; quản trị danh tính chỉ GLOBAL/ALL", "uc": "UC09 · UC14 · UC17"},
    {"role": "AUDITOR", "name": "Kiểm toán", "read": "Hồ sơ, audit và báo cáo theo scope", "write": "Không ghi nghiệp vụ", "constraints": "Không sửa role hay nhật ký", "uc": "UC05 · UC15"},
)

# Only canonical implemented contracts, not every compatibility alias.
def _api(domain, method, route, purpose, role, uc, protection="session / scope"):
    return {"domain": domain, "method": method, "path": "/api/v1/" + route,
            "purpose": purpose, "roles": role, "uc": uc, "protection": protection}

API_ENDPOINTS = (
    _api("Xác thực", "GET", "auth/csrf", "Nhận CSRF cookie", ["ANONYMOUS"], "UC01", "CSRF cookie"),
    _api("Xác thực", "POST", "auth/login", "Đăng nhập / rate limit", ["ANONYMOUS"], "UC01", "CSRF + rate limit"),
    _api("Xác thực", "POST", "auth/logout", "Kết thúc phiên", ["AUTHENTICATED"], "UC01", "CSRF + session"),
    _api("Xác thực", "GET", "auth/me", "Thông tin người dùng hiện tại", ["AUTHENTICATED"], "UC01", "session"),
    _api("Xác thực", "POST", "auth/password", "Đổi mật khẩu", ["AUTHENTICATED"], "UC01", "CSRF + security_epoch"),
    _api("Yêu cầu", "GET", "requests", "Danh sách theo quyền + phân trang", ["REQUESTER", "APPROVER", "EXECUTOR", "ACCEPTOR", "AUDITOR"], "UC05", "row-level predicate"),
    _api("Yêu cầu", "POST", "request-drafts", "Tạo nháp", ["REQUESTER"], "UC03", "owner + idempotency"),
    _api("Yêu cầu", "PATCH", "request-drafts/{id}", "Sửa nháp", ["REQUESTER"], "UC03", "owner + version"),
    _api("Yêu cầu", "POST", "requests/{id}/submit", "Gửi hoặc gửi lại", ["REQUESTER"], "UC04 · UC07", "scope + version + idempotency"),
    _api("Yêu cầu", "GET", "requests/{id}", "Chi tiết theo predicate", ["PARTICIPANT", "AUDITOR"], "UC05", "404 ngoài quyền"),
    _api("Yêu cầu", "POST", "requests/{id}/cancel", "Hủy trước duyệt đủ", ["REQUESTER"], "UC08", "owner + state"),
    _api("Phê duyệt", "POST", "requests/{id}/approval-decisions", "Quyết định từng cấp", ["APPROVER"], "UC06", "ACTIVE + scope + SoD"),
    _api("Thực hiện", "POST", "requests/{id}/execution/start", "Nhận việc", ["EXECUTOR"], "UC10", "assignee + attempt"),
    _api("Thực hiện", "POST", "requests/{id}/issues", "Báo vướng mắc", ["EXECUTOR"], "UC10", "assignee + reason"),
    _api("Thực hiện", "POST", "requests/{id}/execution/submit", "Nộp kết quả", ["EXECUTOR"], "UC11", "evidence + SoD"),
    _api("Nghiệm thu", "POST", "requests/{id}/acceptance-decisions", "Nghiệm thu hoặc làm lại", ["ACCEPTOR"], "UC12", "C + khác executor"),
    _api("Tệp", "GET", "attachments/{id}/download", "Tải tệp CLEAN có quyền", ["PARTICIPANT", "AUDITOR"], "UC03 · UC05", "private + per-download guard"),
    _api("Thông báo", "GET", "notifications", "Hộp thông báo cá nhân", ["AUTHENTICATED"], "UC13", "recipient only"),
    _api("Thông báo", "PATCH", "notifications/{id}", "Đánh dấu đã đọc", ["AUTHENTICATED"], "UC13", "recipient only"),
    _api("Vận hành", "GET", "ops/requests", "Metadata điều phối", ["OPS_ADMIN"], "UC09", "department + type scope"),
    _api("Vận hành", "POST", "requests/{id}/reassign", "Gán thay actor", ["OPS_ADMIN"], "UC09", "scope + reason + SoD"),
    _api("Vận hành", "POST", "ops/outbox/{id}/replay", "Phát lại sự kiện lỗi", ["OPS_ADMIN"], "UC14", "scope + audit"),
    _api("Chính sách", "GET", "config-releases", "Danh sách phiên bản cấu hình", ["POLICY_ADMIN"], "UC02", "type scope"),
    _api("Chính sách", "POST", "config-releases", "Tạo release DRAFT", ["POLICY_ADMIN"], "UC02", "scope + version"),
    _api("Chính sách", "POST", "config-releases/{id}/publish", "Công bố release", ["POLICY_ADMIN"], "UC02", "validation + audit"),
    _api("Báo cáo", "GET", "reports/requests", "Thống kê theo phạm vi", ["PARTICIPANT", "AUDITOR"], "UC15", "predicate before count"),
    _api("Kiểm toán", "GET", "requests/{id}/audit", "Lịch sử audit hồ sơ", ["PARTICIPANT", "AUDITOR"], "UC15", "request predicate"),
    _api("Kiểm toán", "GET", "admin-events", "Nhật ký hành chính", ["AUDITOR", "OPS_ADMIN", "POLICY_ADMIN"], "UC15", "admin target scope"),
    _api("Danh tính", "GET", "admin/users", "Danh sách user có tìm kiếm", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL only"),
    _api("Danh tính", "POST", "admin/users", "Tạo user", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL + reason + audit"),
    _api("Danh tính", "PATCH", "admin/users/{id}", "Sửa / đặt mật khẩu tạm", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL + revision"),
    _api("Danh tính", "DELETE", "admin/users/{id}", "Vô hiệu tài khoản", ["OPS_ADMIN"], "UC17", "soft delete"),
    _api("Danh tính", "GET", "admin/memberships", "Tra cứu cấp quyền", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL"),
    _api("Danh tính", "POST", "admin/memberships", "Gán role theo scope", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL + epoch"),
    _api("Danh tính", "PATCH", "admin/memberships/{id}", "Cập nhật thời hạn/role", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL + revision"),
    _api("Danh tính", "DELETE", "admin/memberships/{id}", "Thu hồi role", ["OPS_ADMIN"], "UC17", "revoke + session invalidation"),
    _api("Danh tính", "GET", "admin/departments", "Danh mục phòng ban", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL"),
    _api("Danh tính", "GET", "admin/request-types", "Danh mục loại yêu cầu đã khai báo", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL"),
    _api("Danh mục", "GET", "meta/request-type-forms", "Biểu mẫu đã công bố đúng scope", ["REQUESTER"], "UC03", "chỉ published + membership"),
    _api("Danh tính", "POST", "admin/request-types", "Đăng ký loại mới (opt-in)", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL + migration"),
    _api("Quản lý API", "GET", "admin/api-catalog", "Danh mục API và luật truy cập", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL; read only"),
    _api("Quản lý API", "GET", "admin/access-matrix", "Ma trận role theo SRS", ["OPS_ADMIN"], "UC17", "GLOBAL/ALL; read only"),
)


def api_catalog():
    return {"items": list(API_ENDPOINTS), "total": len(API_ENDPOINTS),
            "contract": "EAS P0 / SRS v2 / API v1", "mutable": False,
            "note": "Danh mục hợp đồng API, không cấp quyền hoặc bật/tắt endpoint. Quyền thật được kiểm ở Django."}


def access_matrix():
    return {"items": list(ROLE_MATRIX), "scope_model": "GLOBAL|DEPARTMENT × ALL|ONE",
            "sod": ["Requester không tự duyệt", "Không trùng approver cùng revision", "Acceptor khác executor thực tế"],
            "note": "Quyền ghi còn phụ thuộc actor, trạng thái, revision và SoD; nhiều role không bỏ qua giới hạn."}
