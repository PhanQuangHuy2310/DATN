# API Core (Backend)

Thư mục này chứa mã nguồn của hệ thống Backend chính (Core Backend), đóng vai trò trung tâm điều phối toàn bộ các nghiệp vụ của **Enterprise Approval System**.

Hệ thống Core Backend (thường sử dụng Django) đảm nhiệm các module chính:
- **Quản trị Định danh & Tổ chức:** Quản lý người dùng, phòng ban, phân quyền và ủy quyền.
- **Quản lý Yêu cầu & Workflow:** Quản lý vòng đời yêu cầu (Draft -> Pending -> Approved...), tích hợp State Machine (như `django-river`) và theo dõi SLA.
- **Ghi nhận Kiểm toán (Audit):** Tự động ghi nhận (audit log) mọi thao tác thay đổi dữ liệu, ứng dụng hash SHA-256 để đảm bảo tính bất biến.
- **Điều phối (Orchestration):** Giao tiếp với Drools (Rules Engine) để lấy luồng phê duyệt và gọi sang AI Service (FastAPI) để xử lý dữ liệu thông minh.
