# Business Rules Engine

Thư mục này chứa mã nguồn và cấu hình cho **Module Đánh giá Luật Nghiệp vụ (Business Rule Engine)**, sử dụng **Drools KIE Server**.

Drools đóng vai trò "Bộ não" đưa ra các quyết định luồng đi của hệ thống mà không cần hardcode vào Backend.
- **Tập luật (Rules):** Lưu trữ các file luật định dạng `.drl`.
- **Đầu vào:** Nhận thông tin về yêu cầu (Loại yêu cầu, Số tiền, Chức vụ người gửi...) từ hệ thống Core.
- **Đầu ra:** Phân tích và trả về `ApprovalChain` (Danh sách chi tiết những người hoặc phòng ban cần duyệt, số cấp duyệt) và quy định về thời gian SLA tương ứng.
Việc tách biệt Rule Engine giúp doanh nghiệp dễ dàng thay đổi chính sách phê duyệt mà không cần phải triển khai lại toàn bộ mã nguồn Backend.
