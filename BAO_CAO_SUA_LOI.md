# Bàn giao mã nguồn EAS — Bản sửa kết nối local

Nguồn: `DATN(3).zip`. Bản này giữ source Backend, Frontend/Web Admin, AI model files, worker, SQL và tài liệu; loại `.venv`, `node_modules`, `.git` và `.env` chứa thông tin đăng nhập.

## Các sửa đổi đã thực hiện

- `ai_service/routers/classify.py`: route chính `/ai/classify/request` đúng Django; route cũ `/ai/classify/classify` tiếp tục dùng được (ẩn khỏi Swagger).
- `api_core/ai_client.py` và bản sao `ai_service/ai_client.py`: sửa ánh xạ Risk payload theo schema FastAPI (`amount_vnd`, `num_attachments`, `past_requests_count`, `past_rejection_rate`, `is_off_hours`, `urgency`, `department`). Không tự suy đoán số tiền ngân sách, hóa đơn hay thâm niên từ dữ liệu không có.
- `api_core/storage.py`: API key Supabase mới `sb_secret_*` chỉ gửi qua `apikey`, không gửi `Authorization: Bearer` như JWT. Key JWT legacy vẫn có Bearer; bổ sung test.
- `ai_service/main.py`: phản hồi version thực tế của app và từ chối endpoint nội bộ nếu chưa đặt `INTERNAL_API_SECRET`.
- Cấu hình: bỏ default secret nội bộ đã công khai trong code và Docker Compose; Docker bắt buộc cung cấp `INTERNAL_API_SECRET`. Chuẩn hóa `.env.database.example`, `ai_service/.env.example`, thêm `.env.worker.example`; không bao gồm key thật.
- Bổ sung `setup_local.cmd`, `start_backend_local.cmd`, `start_frontend_local.cmd`, `start_ai_local.cmd`, `start_worker_local.cmd`, `check_local.cmd` và `HUONG_DAN_CHAY_LOCAL.md`.
- `run_worker_local.py`: dùng `.env.worker` riêng; `verify_admin_password_local.py` chỉ kiểm tra hash mật khẩu bằng cách nhập ẩn (không reset).
- `check_eas_connections_local.py`: đối chiếu secret mà không hiển thị, kiểm route/payload, health/proxy, DB/backend/worker và Storage/ClamAV nếu có cấu hình.
- `ai_service/requirements-local.txt`: bộ thư viện chạy AI lõi trên Windows không gồm Paddle; OCR Paddle cần thiết lập riêng nếu kiểm thử OCR thực tế.

## Kiểm chứng đã chạy trong môi trường đóng gói

- 9/9 unit tests cho `connect_database.py` đạt.
- 108 file Python parse cú pháp thành công.
- `node --check` cho `web_client/src/api.js` và `vite.config.js` đạt.
- FastAPI TestClient trả HTTP 200 ở `/health`, 401 nếu thiếu secret, 422 nếu có secret nhưng sai schema trên route `/ai/classify/request`; route mới và legacy đều tồn tại.
- Mô phỏng HTTP của Django AI client xác nhận Risk payload mới gửi đúng các trường số tiền, tệp đính kèm, tỷ lệ từ chối.
- **Chưa thể kiểm thử kết nối thật trên Windows của người dùng, đăng nhập admin, Worker ghi dữ liệu, OCR Paddle, Cloud Storage upload, ClamAV scan hay workflow end-to-end.** Kết quả `health/ready=200` trước đó của người dùng đã xác nhận hệ thống tại thời điểm log, nhưng không thay thế kiểm thử trên bản đã sửa.

## Những việc còn phải thực hiện

1. Sao chép thông tin Supabase role vào `.env.database` và đặt mật khẩu/secret mới đã xoay khóa.
2. Cấu hình `EAS_AI_INTERNAL_SECRET` bằng đúng `INTERNAL_API_SECRET` trong `ai_service/.env`.
3. Chạy `check_local.cmd` trên máy Windows khi service đã lên.
4. Nếu POST login còn 401, dùng `verify_admin_password_local.py`; không tự gán role hoặc ghi đè `password_hash` trong DB.
5. Nếu bật Storage: cài ClamAV Windows, bucket private, key Supabase mới; xác nhận thao tác upload/download thật.
6. AI client hiện mới chuẩn hóa interface, **không tự động đưa AI ra quyết định phê duyệt trong các view nghiệp vụ**. Việc tích hợp workflow cần thiết kế và kiểm thử phân quyền riêng, tránh thay đổi quyết định doanh nghiệp ngoài kế hoạch.

**Không nên coi bản vá kết nối là chứng chỉ sẵn sàng production hoặc chứng minh hoàn thành mọi yêu cầu chức năng.**
