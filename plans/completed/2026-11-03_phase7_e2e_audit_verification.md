# Kế hoạch Triển khai: Giai đoạn 7 (Phase 7) — Kiểm Thử Toàn Diện (E2E Audit), Rà Soát Definition of Done & Cập Nhật Tài Liệu

| Thuộc tính | Giá trị |
|---|---|
| **Mã kế hoạch** | `EAS-PLAN-PHASE-7` |
| **Ngày khởi tạo** | 03/11/2026 |
| **Trạng thái** | `COMPLETED` |
| **Phạm vi** | Toàn bộ dự án (`web_admin`, `web_client`, `api_core`, `database`) |
| **Mục tiêu** | Kiểm thử End-to-End toàn diện 9 chức năng, đối chiếu Definition of Done và xác nhận sự đồng bộ thẩm mỹ, nghiệp vụ |

---

## 1. MỤC TIÊU & PHẠM VI

### 1.1 Rà soát 9 chức năng & Tính đồng nhất Giao diện (UI Consistency)
- Kiểm tra tính đồng bộ thẩm mỹ tuyệt đối giữa `web_admin` và `web_client`: Chung hệ màu, bo góc, bóng mờ, bảng biểu.
- Chế độ **Sáng / Tối (Dark Mode)**: Hoạt động mượt mà, lưu vào `localStorage`, chuyển đổi tức thì trên mọi trang.
- **Header & Sidebar**:
  - Tiêu đề trên Header tự động thay đổi tương ứng theo từng trang chức năng đang duyệt.
  - Thanh tìm kiếm chung (Global Search) hoạt động nhanh, lọc dữ liệu chính xác.
  - Nút Đăng xuất (`Logout`) hoạt động an toàn, xóa cookie phiên và chuyển hướng về màn hình đăng nhập.

### 1.2 Kiểm toán chéo 6 Luồng nghiệp vụ cốt lõi (Cross-cutting Workflows)
1. **Luồng 1 (Phân quyền RBAC):** Cấp quyền theo vai trò và ghi đè quyền theo từng người dùng. Xác nhận các menu Sidebar và nút chức năng (Thêm/Sửa/Xóa) ẩn/hiện chính xác.
2. **Luồng 2 (Trạng thái Người dùng & Chi tiết 5 giai đoạn):** Tính toán trạng thái Đang làm (08:00 - 17:30, T2-T6), Nghỉ phép, Công tác. Bấm vào tổng số đơn để mở modal chia nhỏ 5 giai đoạn.
3. **Luồng 3 (Yêu cầu & Quy trình A/B/C):** Chuyển đổi phân loại yêu cầu từ A sang B; điều chỉnh ma trận trọng số và kiểm tra cập nhật số bước duyệt.
4. **Luồng 4 (Quy định & AI Auto-Lock):** Sửa quy định tự động tăng Minor version, thêm/xóa tăng Major version; kích hoạt trạng thái AI học tập và màn hình khóa Maintenance Lock trên `web_client`; kiểm tra nút mở khóa khẩn cấp.
5. **Luồng 5 (Mock APIs & Circuit Breaker):** Tắt một API kiểm tra việc vô hiệu hóa việc tạo đơn kèm lý do; bật lại API kiểm tra việc mở khóa tức thì.
6. **Luồng 6 (Phiên bản hệ thống & Diff Viewer):** Kiểm tra danh sách nhật ký phiên bản, mở Modal Diff so sánh phiên bản và tải về file JSON sao lưu cấu hình.

---

## 2. KẾT QUẢ THỰC HIỆN
- Hoàn thành bộ kiểm thử E2E trực tiếp trên trình duyệt thực tế với cả tài khoản Quản trị viên (`admin@eas.com`) và các nhân viên đại diện (`lan.ngo@eas.com`, `an.pham@eas.com`, `an.do@eas.com`).
- Toàn bộ 6 luồng nghiệp vụ đạt chuẩn 100%, không phát sinh lỗi chặn (zero blocking bugs).
- Cập nhật tài liệu dự án `PROGRESS.md` và lưu trữ báo cáo kiểm thử chi tiết.
