# Enterprise Approval System (EAS)

EAS là hệ thống tiếp nhận và phê duyệt yêu cầu nội bộ. Repository gồm hai cổng web, API Django, dịch vụ AI tùy chọn, worker nền và các gói SQL PostgreSQL/Supabase.

## Khởi động local trên Windows

Yêu cầu: Python 3.12 cho API, Python 3.11 cho AI và Node.js 22.12 trở lên. Kiểm tra runtime Python đã cài bằng `py -0p`. Nếu thiếu phiên bản cần thiết, hãy cài Python trước khi tạo virtual environment; `venv` không thể tự cài runtime. AI là tùy chọn nếu chỉ chạy API và hai cổng web.

1. Sao chép `.env.example` thành `.env` tại thư mục gốc và cấu hình các biến phía server. Không đặt database/Supabase secret vào biến frontend.
2. Tạo môi trường và cài API:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r api_core\requirements.txt
   ```

3. Nếu cần chức năng AI, tạo môi trường và cài AI (có thể bỏ qua nếu chỉ chạy API và web):

   ```powershell
   py -3.11 -m venv ai_service\.venv-ai
   .\ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-local.txt
   ```

4. Cài từng ứng dụng web:

   ```powershell
   cd web_client
   npm ci
   cd ..\web_admin
   npm ci
   cd ..
   ```

5. Mở các terminal riêng tại thư mục gốc và chạy `start_backend_local.cmd`, `start_worker_local.cmd`, `start_frontend_local.cmd`, `start_admin_local.cmd`. Chạy thêm `start_ai_local.cmd` nếu đã cài môi trường AI và muốn bật AI.

Cổng nhân viên: `http://127.0.0.1:5173`; cổng quản trị: `http://127.0.0.1:5174`; API: `http://127.0.0.1:8000`; AI health: `http://127.0.0.1:8001/health`. Hai cổng web dùng chung mã giao diện trong `web_client`.

## Docker Compose

Cấu hình `.env` ở thư mục gốc rồi chạy:

```powershell
docker compose --env-file .env up --build
```

Hai cổng web được expose ở port 8080 và 8081. Compose khởi tạo Redis và kết nối API với AI service. API và worker nên dùng database login riêng; không dùng schema owner hoặc Supabase `service_role` làm runtime login.

## Database và khôi phục tài khoản

Installer baseline, kiểm tra chỉ đọc, seed/regression dành riêng cho development và hướng dẫn migration nằm trong [database/README.md](./database/README.md). Thay đổi production phải dùng migration tăng dần đã review; không chạy lại installer baseline trên database có dữ liệu.

Migration đăng nhập email/reset và migration Gmail aliases [đã được áp dụng và xác minh](./database/EAS_Supabase_SQL/README_VI.md) trên Supabase DATN. 42 tài khoản thử nghiệm hiện dùng alias Gmail riêng, tất cả chuyển về cùng inbox; phiên cũ đã bị vô hiệu hóa. API và hai web portal đã được rebuild local bằng Docker Compose; API báo ready. Gmail đã chấp nhận email thử nghiệm SMTP. Hướng dẫn và giới hạn nằm trong [API Core](./api_core/README.md) và [database migrations](./database/README.md).

## Kiểm thử và mức sẵn sàng

- API: từ thư mục gốc chạy `.\.venv\Scripts\python.exe manage.py test`.
- Web nhân viên: trong `web_client`, chạy `npm run lint`, `npm test`, `npm run build`.
- Web quản trị: trong `web_admin`, chạy `npm run build`.
- SQL validation: làm theo [hướng dẫn gói EAS Supabase SQL](./database/EAS_Supabase_SQL/README_VI.md).

Test local pass không đồng nghĩa hệ thống đã sẵn sàng production. Migration Supabase, SMTP, E2E staging, load, backup/restore và kiểm tra triển khai cần được xác minh riêng.

## Hướng dẫn theo phân hệ

Giữ hướng dẫn chi tiết cạnh các phân hệ phức tạp:

- [API Core](./api_core/README.md) · [AI service](./ai_service/README.md) · [API Gateway](./api_gateway/README.md)
- [Database](./database/README.md) · [Triển khai](./deploy/README.md) · [Kiểm thử](./tests/README.md)
- [Web](./web_client/README.md) · [Ứng dụng mobile](./mobile_app/README.md)
- [Sơ đồ kỹ thuật](./docs/README.md)
