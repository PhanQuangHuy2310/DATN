# API Gateway

Thư mục này cấu hình **API Gateway** cho hệ thống.

API Gateway đóng vai trò là cửa ngõ duy nhất (Single Point of Entry) tiếp nhận mọi luồng request từ các Client (Web Admin, Web Client, Mobile App).
Nhiệm vụ chính:
- **Routing:** Định tuyến các request tới đúng service (API Core, AI Service,...).
- **Load Balancing:** Cân bằng tải giữa các instances của các services.
- **Bảo mật:** Xử lý xác thực (Authentication), phân quyền (Authorization), Rate limiting và ngăn chặn các luồng truy cập không hợp lệ.
- **Gộp API (API Aggregation):** Tối ưu hóa số lượng request từ client bằng cách gộp nhiều phản hồi từ các services khác nhau.
