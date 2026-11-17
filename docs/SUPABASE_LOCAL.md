# Chạy EAS với Supabase local (bản sao đầy đủ của cloud)

Dùng khi cần một database riêng trên máy để phát triển hoặc kiểm thử mà không đụng vào dữ liệu thật trên cloud. Bản sao gồm:

- Mọi schema của EAS (`eas`, `eas_archive` và tất cả `mock_*`): bảng, function, trigger, policy RLS, quyền và **toàn bộ dữ liệu**, kể cả chuỗi nhật ký kiểm toán.
- Các role của EAS cùng thiết lập (`search_path`, `statement_timeout`, `lock_timeout`) và quan hệ thành viên.
- Toàn bộ file trong Storage (bucket `eas-private`), được đối chiếu SHA-256 từng file.
- Các SQL snippet của SQL editor trên cloud, lưu vào `supabase/snippets/`.

**Dữ liệu không nằm trong git.** Repository này public, còn dữ liệu có hash mật khẩu, thông tin nhân sự và file đính kèm. Mỗi người tự kéo dữ liệu về máy mình bằng quyền Supabase của chính mình. Các file `supabase/seed.sql` và `supabase/snippets/` đã nằm trong `.gitignore`. Không gỡ chúng khỏi đó.

## Cần có

1. Docker Desktop đang chạy.
2. [Supabase CLI](https://supabase.com/docs/guides/cli), và được chủ dự án mời vào organization chứa project `emnusiybdkpibtqsplta` (DATN).
3. Python 3.11 trở lên.
4. Khoá **`service_role`** của project cloud: Dashboard → Project Settings → API Keys → **Legacy API keys** → `service_role`. Không dùng JWT Secret và không dùng khoá `sb_publishable_…`.

## Các bước

1. Đăng nhập và khởi động Supabase local. Cổng nằm trong `supabase/config.toml`: API ở 55321, DB ở 55322, Studio ở 55323.

   ```powershell
   supabase login
   supabase start
   ```

2. Trong `.env` ở thư mục gốc, trỏ ba URL database về DB local. Mật khẩu là mật khẩu bạn chọn cho máy mình; script sẽ đặt chúng cho các login role.

   ```dotenv
   EAS_API_DATABASE_URL=postgresql://eas_backend_login:<pw>@127.0.0.1:55322/postgres?sslmode=disable
   EAS_WORKER_DATABASE_URL=postgresql://eas_worker_login:<pw>@127.0.0.1:55322/postgres?sslmode=disable
   EAS_MOCK_DATABASE_URL=postgresql://eas_mock_login:<pw>@127.0.0.1:55322/postgres?sslmode=disable
   # Storage local. Lấy SECRET_KEY bằng lệnh: supabase status -o env
   EAS_SUPABASE_URL=http://host.docker.internal:55321
   EAS_SUPABASE_SECRET_KEY=<SECRET_KEY của Supabase local>
   ```

   Khi chạy bằng Docker, các container tự đổi `127.0.0.1` thành `host.docker.internal` (`EAS_IN_DOCKER=1` trong `docker-compose.yml`). Khi chạy thẳng trên máy (terminal), đặt `EAS_SUPABASE_URL=http://127.0.0.1:55321`.

3. Đồng bộ từ cloud. Lệnh này chỉ đọc trên cloud và chỉ ghi vào DB local. Phần dựng lại schema chạy trong một transaction, nên nếu lỗi thì DB local giữ nguyên như cũ.

   ```powershell
   $env:SUPABASE_CLOUD_SERVICE_KEY = "<khoá service_role của cloud>"
   python scripts\supabase_local_sync.py
   Remove-Item Env:SUPABASE_CLOUD_SERVICE_KEY
   ```

   Script tự kiểm tra rằng từng bảng có đúng số dòng như cloud và từng file Storage trùng SHA-256. Có sai lệch là script dừng và báo lỗi.

4. Chạy dự án như bình thường:

   ```powershell
   docker compose up -d --build
   ```

   Kiểm tra: `http://127.0.0.1:8000/health/ready` phải có `"database": true`.

Muốn lấy lại dữ liệu mới nhất từ cloud thì chạy lại bước 3. Bỏ qua Storage bằng `--skip-storage`.

## Lưu ý

- **Dùng thử là dữ liệu local sẽ khác cloud.** Mỗi thao tác như đăng nhập, tải file hay duyệt hồ sơ đều ghi nhật ký kiểm toán, nên local chỉ giống cloud tại thời điểm đồng bộ.
- **Không dán khoá vào chat, issue hay commit.** Khoá `service_role` có toàn quyền trên project cloud. Nếu lỡ để lộ, chủ dự án phải rotate JWT Secret trên Dashboard.
- Về cấu trúc, bản sao giống hệt cloud. Riêng một số định nghĩa `CHECK` dạng `ARRAY[...]` được Postgres viết lại sau khi dump/restore: cách viết khác nhưng ý nghĩa không đổi.
