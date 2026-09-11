# Enterprise Approval System

Hệ thống quản lý và phê duyệt quy trình doanh nghiệp tích hợp AI.

## Cấu trúc dự án

- `api_gateway`: Nginx/Kong API Gateway
- `api_core`: Backend chính (Python - Django)
- `ai_service`: Dịch vụ AI (Python - FastAPI)
- `web_client`: Giao diện người dùng (React.js)
- `web_admin`: Giao diện quản trị viên (React.js)
- `mobile_app`: Ứng dụng di động (Flutter)
- `rules_engine`: Máy chủ luật (Drools KIE Server)
- `deploy`: Cấu hình Docker & Kubernetes

## Yêu cầu

- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
- Flutter SDK
