# Enterprise Approval System (EAS)

EAS là hệ thống tiếp nhận và phê duyệt yêu cầu nội bộ doanh nghiệp. Hệ thống gồm:

- cổng web cho nhân viên và cổng web cho quản trị;
- API Django và worker xử lý nền;
- dịch vụ AI (tùy chọn);
- dịch vụ **Mock Systems**, giả lập các hệ thống ngoài: nhân sự, tài sản, toà nhà, IT, tài chính…

Tài liệu này hướng dẫn **chạy hệ thống trên máy Windows**.

## 1. Hệ thống gồm những gì

| Dịch vụ | Địa chỉ sau khi chạy | Bắt buộc |
|---|---|---|
| Mock Systems API | http://127.0.0.1:8100 | Có |
| API (backend) | http://127.0.0.1:8000 | Có |
| Worker nền (thông báo, SLA, tự trả đồ mượn) | — | Có |
| Web nhân viên | http://127.0.0.1:5173 | Có |
| Web quản trị | http://127.0.0.1:5174 | Có |
| AI service | http://127.0.0.1:8001 | Không: thiếu AI thì hệ thống dùng quy tắc dự phòng |

Dữ liệu nằm trên **một database Supabase** có sẵn, không cần cài database trên máy.

## 2. Chuẩn bị (một lần)

1. Cài **Python 3.12** (https://www.python.org, chọn "Add python.exe to PATH") và **Node.js 22.12 trở lên** (https://nodejs.org). Muốn dùng AI thì cài thêm **Python 3.11**.
2. Giải nén dự án. Mở **PowerShell** tại thư mục dự án (thư mục chứa file này).
3. Nhận file **`.env`** từ chủ dự án và đặt vào thư mục dự án.

   > **Bảo mật:** `.env` chứa mật khẩu database và các khoá bí mật. Không gửi qua kênh công khai, không đưa lên GitHub, không chia sẻ ảnh chụp nội dung file. Repository đã có sẵn `.gitignore` cho `.env`.

4. Cài thư viện:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r api_core\requirements.txt
   cd web_client; npm ci; cd ..
   cd web_admin;  npm ci; cd ..
   ```

   Nếu dùng AI:

   ```powershell
   py -3.11 -m venv ai_service\.venv-ai
   .\ai_service\.venv-ai\Scripts\python.exe -m pip install -r ai_service\requirements-local.txt
   ```

5. Kiểm tra kết nối database: `.\check_local.cmd`.

## 3. Chạy hệ thống (mỗi lần dùng)

Mở **mỗi lệnh dưới đây trong một cửa sổ PowerShell riêng**, tại thư mục dự án, theo đúng thứ tự. Mỗi cửa sổ phải giữ mở trong lúc dùng hệ thống.

| # | Lệnh | Dịch vụ |
|---|---|---|
| 1 | `.\start_mock_local.cmd` | Mock Systems API |
| 2 | `.\start_backend_local.cmd` | API backend |
| 3 | `.\start_worker_local.cmd` | Worker nền |
| 4 | `.\start_ai_local.cmd` | AI (bỏ qua nếu không dùng) |
| 5 | `.\start_frontend_local.cmd` | Web nhân viên |
| 6 | `.\start_admin_local.cmd` | Web quản trị |

Sau đó mở trình duyệt:

- **Web nhân viên:** http://127.0.0.1:5173
- **Web quản trị:** http://127.0.0.1:5174

Đăng nhập bằng email và mật khẩu do chủ dự án cung cấp. Lần đầu đăng nhập bằng mật khẩu tạm, hệ thống yêu cầu đổi mật khẩu.

Tắt hệ thống: bấm `Ctrl+C` trong từng cửa sổ.

## 4. Kiểm tra hệ thống đã chạy đúng

Mở http://127.0.0.1:8000/health/ready. Kết quả đúng có `"status": "ready"`, trong đó:

- `mock_systems_api_reachable` là `true`;
- `eas_role_has_no_mock_table_access` là `true`.

## 5. Cách khác: chạy bằng Docker

Cần Docker Desktop. Đặt file `.env` vào thư mục dự án rồi chạy:

```powershell
docker compose --env-file .env up --build
```

Web nhân viên mở ở http://127.0.0.1:8080, web quản trị ở http://127.0.0.1:8081. Tắt bằng `docker compose down`.

## 6. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Báo thiếu `.venv` hoặc `node_modules` | Chưa làm bước 2.4 |
| `Copy .env.example to .env…` hoặc `Missing EAS_MOCK_DATABASE_URL` | Chưa có file `.env` đúng ở thư mục dự án (bước 2.3) |
| Gửi đơn mượn phòng/xe/thiết bị, nghỉ phép, mua sắm, cấp quyền báo `INTEGRATION_UNAVAILABLE` | Cửa sổ `start_mock_local.cmd` chưa chạy hoặc đã tắt |
| Báo `INTEGRATION_DISABLED` | Quản trị đã tắt kết nối hệ thống đó: vào web quản trị → Cấu hình hệ thống → API & tích hợp |
| Cổng 8000 / 8100 / 5173 / 5174 đã bị dùng | Tắt chương trình đang chiếm cổng, hoặc cửa sổ cũ của chính hệ thống này |
| Quên mật khẩu quản trị | `.\.venv\Scripts\python.exe set_temporary_admin_password.py` để tạo mật khẩu tạm (bắt buộc đổi khi đăng nhập) |
| Thông báo, nhắc hạn, trả đồ mượn không chạy | Cửa sổ `start_worker_local.cmd` chưa chạy |

## 7. Tài liệu thêm

- Phân loại yêu cầu (12 nhóm): [docs/PHAN_LOAI_YEU_CAU.md](./docs/PHAN_LOAI_YEU_CAU.md)
- Tích hợp hệ thống ngoài (Mock Systems): [docs/TICH_HOP_HE_THONG_NGOAI.md](./docs/TICH_HOP_HE_THONG_NGOAI.md)
- Thiết kế cơ sở dữ liệu: [docs/THIET_KE_SCHEMA_EAS_V2.md](./docs/THIET_KE_SCHEMA_EAS_V2.md). Dựng database mới: [database/README.md](./database/README.md)
- Theo phân hệ: [API](./api_core/README.md) · [AI](./ai_service/README.md) · [Web](./web_client/README.md) · [Mobile](./mobile_app/README.md) · [Kiểm thử](./tests/README.md) · [Triển khai](./deploy/README.md)
- Lịch sử thay đổi: thư mục [changelogs/](./changelogs/)
