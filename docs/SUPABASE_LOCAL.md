# Chạy EAS với Supabase local (bản sao đầy đủ của cloud)

Dùng khi cần một database riêng trên máy để phát triển hoặc kiểm thử mà không đụng vào dữ liệu thật trên cloud. Khi chạy `supabase start` (hoặc `supabase db reset`), Supabase Local **tự động nạp sẵn** [supabase/seed.sql](../supabase/seed.sql) và thư mục `supabase/snippets/` đã đi kèm trong repository, bao gồm:

- Mọi schema của EAS (`eas`, `eas_archive` và tất cả 8 schema `mock_*`): 92 bảng, 8 view, function, trigger, policy RLS, quyền và **toàn bộ 7.346+ bản ghi**, kể cả chuỗi nhật ký kiểm toán.
- Các role của EAS (`eas_migration`, `eas_api`, `eas_worker`, `eas_privacy`, `eas_backup`, `eas_mock`) và 3 login role (`eas_backend_login`, `eas_worker_login`, `eas_mock_login`) với mật khẩu mặc định local là `postgres` cùng thiết lập `search_path`, `statement_timeout`, `lock_timeout`.
- Toàn bộ 35 kịch bản SQL Editor trong `supabase/snippets/` (hiển thị trực tiếp trong SQL Editor của Supabase Studio Local).

## Cần có

1. Docker Desktop đang chạy.
2. [Supabase CLI](https://supabase.com/docs/guides/cli) (hoặc chạy trực tiếp qua `npx supabase`).
3. Python 3.11 trở lên (chỉ cần thêm `SUPABASE_CLOUD_SERVICE_KEY` khi muốn tự kéo lại dữ liệu mới nhất hoặc file đính kèm trong Storage từ Supabase Cloud).

## Các bước chạy ngay bằng dữ liệu có sẵn trong Git

1. Khởi động Supabase Local (tự động tạo DB trên cổng `55322`, API ở `55321`, Studio ở `55323` và tự nạp `supabase/seed.sql`):

   ```powershell
   npx supabase start
   ```

   *(Nếu trước đó đã từng chạy `supabase start` với DB rỗng, chạy thêm `npx supabase db reset` để nạp `supabase/seed.sql`.)*

2. Trong `.env` ở thư mục gốc, trỏ 3 URL database và Storage về Supabase Local với mật khẩu mặc định `postgres`:

   ```dotenv
   EAS_API_DATABASE_URL=postgresql://eas_backend_login:postgres@127.0.0.1:55322/postgres?sslmode=disable
   EAS_WORKER_DATABASE_URL=postgresql://eas_worker_login:postgres@127.0.0.1:55322/postgres?sslmode=disable
   EAS_MOCK_DATABASE_URL=postgresql://eas_mock_login:postgres@127.0.0.1:55322/postgres?sslmode=disable
   # Storage local. Lấy SECRET_KEY bằng lệnh: npx supabase status -o env
   EAS_SUPABASE_URL=http://127.0.0.1:55321
   EAS_SUPABASE_SECRET_KEY=<SECRET_KEY của Supabase local>
   ```

   Khi chạy bằng Docker Compose (`docker compose up -d`), các container tự đổi `127.0.0.1` thành `host.docker.internal` nhờ `EAS_IN_DOCKER=1`. Khi chạy trực tiếp ngoài Docker trên máy (terminal), giữ nguyên `127.0.0.1:55321` và `127.0.0.1:55322`.

3. Chạy dự án như bình thường:

   ```powershell
   docker compose up -d --build
   ```

   Kiểm tra: `http://127.0.0.1:8000/health/ready` phải trả về `"status": "ready"` và `"database": true`.

## Đồng bộ lại bản mới nhất từ Supabase Cloud (tùy chọn)

Khi cần kéo lại dữ liệu mới nhất và toàn bộ file đính kèm trong bucket `eas-private` từ Supabase Cloud (`emnusiybdkpibtqsplta`), dùng `service_role` key trên Supabase Dashboard → Project Settings → API Keys → **Legacy API keys**:

```powershell
$env:SUPABASE_CLOUD_SERVICE_KEY = "<khoá service_role của cloud>"
python scripts\supabase_local_sync.py
Remove-Item Env:SUPABASE_CLOUD_SERVICE_KEY
```

Script tự kiểm tra từng bảng khớp đúng số dòng và từng file Storage trùng SHA-256. Bỏ qua Storage bằng `--skip-storage`.

## Lưu ý

- **Dùng thử là dữ liệu local sẽ khác cloud.** Mỗi thao tác như đăng nhập, tải file hay duyệt hồ sơ đều ghi nhật ký kiểm toán, nên local chỉ giống cloud tại thời điểm tạo `supabase/seed.sql` hoặc đồng bộ lại.
- **Không dán khoá Cloud `service_role` vào chat, issue hay commit.** Khoá `service_role` của cloud có toàn quyền trên project thật; chỉ dùng mật khẩu `postgres` cho môi trường local trên máy.
- **Không đóng gói `supabase/` vào Docker image**: thư mục `supabase/` đã nằm trong `.dockerignore`.
