# Enterprise Approval System - End-to-End Tests

Thư mục này chứa các bài test End-to-End (E2E) và Integration test cho toàn bộ hệ thống Enterprise Approval System. 

Các bài test ở đây sẽ kiểm thử luồng hoạt động (workflows) đi qua nhiều microservices như:
- API Gateway
- Django Backend (API Core, Rules Engine, Workflow)
- FastAPI (AI Service)

## Cấu trúc dự kiến
- `e2e/`: Các kịch bản test giả lập hành vi người dùng cuối.
- `integration/`: Kiểm thử giao tiếp giữa các services với nhau.
- `fixtures/`: Dữ liệu mẫu dùng chung cho các bài test.
