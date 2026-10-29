# Nguồn yêu cầu

Trích nguyên tên/mã/mẫu/trường nhập/tuyến duyệt, SLA, executor, acceptor, AI hook từ bốn bảng trong `plan.docx`. Cột `form_schema`, `field_labels`, `activation_warnings` là sản phẩm triển khai để phục vụ hiển thị, KHÔNG phải trích dẫn nguyên văn. Chưa tự công bố chính sách hay thay đổi DB.

- **LEAVE_ANNUAL** — Nghỉ phép thường niên — Template A, SLA 24 giờ; duyệt: Trưởng phòng duyệt; người thực hiện: Không cần; nghiệm thu: Không cần
- **LEAVE_LONG** — Nghỉ phép dài hạn (>2 ngày) — Template A, SLA 48 giờ; duyệt: Cấp 1: Trưởng phòng
 Cấp 2: Giám đốc Khối; người thực hiện: HR ghi nhận; nghiệm thu: Trưởng phòng
- **RESIGNATION** — Thôi việc / Bàn giao — Template C, SLA 168 giờ; duyệt: Cấp 1: Trưởng phòng
 Cấp 2: Giám đốc HR
 Cấp 3: CEO; người thực hiện: 4 bên song song (IT, Admin, Kế toán, Sếp); nghiệm thu: HR & Người gửi
- **OVERTIME_REQ** — Đăng ký làm thêm giờ (OT) — Template B, SLA 24 giờ; duyệt: Trưởng phòng duyệt; người thực hiện: HR tính lương; nghiệm thu: Trưởng phòng
- **WFH_REQ** — Làm việc từ xa (WFH) — Template A, SLA 12 giờ; duyệt: Trưởng nhóm / Trưởng phòng; người thực hiện: Không cần; nghiệm thu: Sếp đánh giá task
- **ROOM_VEHICLE** — Mượn phòng họp / Xe công vụ — Template B, SLA 1 giờ; duyệt: AI Auto-Approve (nếu lịch trống); người thực hiện: Lễ tân / Đội xe; nghiệm thu: Người đặt
- **ADVANCE_SMALL** — Tạm ứng chi phí (<10tr) — Template B, SLA 24 giờ; duyệt: Cấp 1: Quản lý trực tiếp
 Cấp 2: Kế toán thanh toán; người thực hiện: Thủ quỹ chi trả; nghiệm thu: Người nhận tiền
- **ADVANCE_MEDIUM** — Tạm ứng chi phí (10-50tr) — Template B, SLA 48 giờ; duyệt: Cấp 1: Quản lý trực tiếp
 Cấp 2: Kế toán trưởng; người thực hiện: Kế toán thanh toán; nghiệm thu: Người nhận tiền
- **ADVANCE_LARGE** — Tạm ứng dự án lớn (>50tr) — Template B, SLA 72 giờ; duyệt: Cấp 1: Quản lý trực tiếp
 Cấp 2: Kế toán trưởng
 Cấp 3: CEO; người thực hiện: Kế toán chuyển khoản; nghiệm thu: Kế toán viên
- **REIMBURSEMENT** — Hoàn ứng / Thanh toán chi phí — Template B, SLA 48 giờ; duyệt: Cấp 1: Trưởng phòng trực thuộc
 Cấp 2: Kế toán trưởng; người thực hiện: Thủ quỹ / Kế toán; nghiệm thu: Người nhận tiền
- **VENDOR_PAYMENT** — Thanh toán Hợp đồng Vendor — Template C, SLA 72 giờ; duyệt: Cấp 1: Trưởng phòng trực thuộc
 Cấp 2: Kế toán trưởng
 Cấp 3: CEO; người thực hiện: Kế toán chuyển khoản; nghiệm thu: Bộ phận thụ hưởng
- **LAPTOP_PROVISION** — Cấp phát Laptop / PC làm việc — Template C, SLA 48 giờ; duyệt: Quản lý trực tiếp duyệt nhu cầu; người thực hiện: IT Helpdesk cài đặt; nghiệm thu: Nhân viên nhận máy
- **SOFTWARE_ACCESS** — Cấp quyền phần mềm thông thường — Template B, SLA 12 giờ; duyệt: Quản lý trực tiếp duyệt; người thực hiện: IT Admin tạo tài khoản; nghiệm thu: Nhân viên đăng nhập
- **PROD_DATA_ACCESS** — Cấp quyền Dữ liệu nhạy cảm/Server — Template C, SLA 24 giờ; duyệt: Cấp 1: Quản lý trực tiếp
 Cấp 2: Trưởng phòng Security
 Cấp 3: CTO; người thực hiện: SysAdmin mở quyền; nghiệm thu: Security Audit log
- **SAAS_LICENSE_BUY** — Mua bản quyền phần mềm mới — Template C, SLA 72 giờ; duyệt: Cấp 1: Quản lý trực tiếp
 Cấp 2: IT Lead
 Cấp 3: Kế toán trưởng; người thực hiện: IT / Mua sắm mua key; nghiệm thu: Trưởng nhóm tech
- **OFFICE_SUPPLIES** — Văn phòng phẩm định mức tháng — Template B, SLA 24 giờ; duyệt: AI Auto-Approve (trong định mức); người thực hiện: Thủ kho xuất đồ; nghiệm thu: Nhân viên nhận
- **ASSET_PURCHASE** — Mua sắm tài sản phòng ban — Template C, SLA 120 giờ; duyệt: Cấp 1: Trưởng phòng yêu cầu
 Cấp 2: Trưởng phòng Mua sắm
 Cấp 3: Giám đốc Tài chính; người thực hiện: Chuyên viên Mua sắm; nghiệm thu: Trưởng phòng nhận
- **FACILITY_REPAIR** — Sửa chữa sự cố văn phòng — Template C, SLA 12 giờ; duyệt: Quản lý tòa nhà / Hành chính; người thực hiện: Thợ kỹ thuật sửa; nghiệm thu: Hành chính nghiệm thu
