# Chạy EAS trên Supabase local

Sao chép schema và dữ liệu từ Supabase cloud (dùng chung cả nhóm) về một Supabase chạy bằng Docker trên máy, rồi trỏ API, worker và mock_systems vào đó. Truy vấn local không phải đi qua pooler ở nước ngoài, nên trang tải nhanh hơn nhiều, và bạn ghi dữ liệu thử thoải mái mà không ảnh hưởng người khác.

> **Lưu ý:**
> - Ở cloud chỉ **đọc** (dump), không chạy migration hay ghi gì lên DB chung.
> - File dump có dữ liệu thật (email, hash mật khẩu, hồ sơ). Chỉ để trong `.supabase-local/` (đã có trong `.gitignore`), không commit và không gửi cho ai.
> - Không để worker chạy song song với cả hai DB. Mỗi lúc chỉ trỏ app vào **một** DB.

---

## 0. Chuẩn bị

| Cần có | Ghi chú |
|---|---|
| Docker Desktop đang chạy | Supabase local tải khoảng 5–7 GB image. Kiểm tra ổ C: còn trống trước khi tải. |
| Supabase CLI | `scoop bucket add supabase https://github.com/supabase/scoop-bucket.git` rồi `scoop install supabase`. Kiểm tra bằng `supabase --version`. |
| Mật khẩu user `postgres` của project cloud | Dashboard → Project Settings → Database. File `.env` chỉ có login của app, không đủ quyền dump roles và schema. |
| Chuỗi kết nối **Session pooler** (cổng **5432**) | Dashboard → nút **Connect** → Session pooler. Không dùng Transaction pooler (cổng 6543) vì nó không hợp với `pg_dump`. |

Các lệnh bên dưới chạy trong **PowerShell**, tại thư mục gốc repo (`D:\GitHub\DATN`).

---

## 1. Tạo project Supabase local riêng

**Không** chạy `supabase init`/`supabase start` trong thư mục `supabase/` có sẵn của repo. Lệnh `supabase start` sẽ tự áp `supabase/migrations/20261103_admin_full_upgrade.sql` lên DB trống, làm schema lệch với cloud. Dùng thư mục riêng `.supabase-local/`:

```powershell
New-Item -ItemType Directory -Force .supabase-local\dumps
supabase init --workdir .supabase-local        # hỏi tạo settings VS Code/IntelliJ: chọn N
```

Mở `.supabase-local\supabase\config.toml` và kiểm tra `[db] major_version = 17`, khớp cloud (PostgreSQL 17).

Khởi động. Cờ `-x` tắt các dịch vụ EAS không dùng để chạy nhẹ hơn:

```powershell
supabase start --workdir .supabase-local -x realtime,edge-runtime,logflare,vector,supavisor,imgproxy,gotrue
supabase status --workdir .supabase-local
```

`supabase status` in ra các địa chỉ cần dùng:

| Thành phần | Địa chỉ mặc định |
|---|---|
| Postgres (kết nối trực tiếp) | `127.0.0.1:55322`, user `postgres`, mật khẩu `postgres` |
| API / Storage | `http://127.0.0.1:55321` |
| Studio | `http://127.0.0.1:55323` |
| Secret key (`sb_secret_...` hoặc `service_role key`) | dùng cho Storage ở bước 5 |

---

## 2. Dump từ cloud (chỉ đọc)

```powershell
# Ký tự đặc biệt trong mật khẩu (@ : / # ?) phải percent-encode, ví dụ @ -> %40
$env:CLOUD_DB_URL = "postgresql://postgres.<project-ref>:<MK>@<host-session-pooler>:5432/postgres"

supabase db dump --db-url $env:CLOUD_DB_URL -f .supabase-local\dumps\roles.sql  --role-only
supabase db dump --db-url $env:CLOUD_DB_URL -f .supabase-local\dumps\schema.sql
supabase db dump --db-url $env:CLOUD_DB_URL -f .supabase-local\dumps\data.sql   --data-only --use-copy

Remove-Item Env:CLOUD_DB_URL     # xóa mật khẩu khỏi phiên PowerShell
```

- `roles.sql` chứa các role tự tạo: `eas_api`, `eas_worker`, `eas_privacy`, `eas_backup`, `eas_mock`, `eas_migration` và các login `eas_backend_login`, `eas_worker_login`, `eas_mock_login`. **Mật khẩu role không được dump**, nên ở bước 4 phải đặt lại.
- `schema.sql`/`data.sql` lấy mọi schema không do Supabase quản lý, tức là `eas` và các schema `mock_*`.
- Kiểm tra nhanh: `(Get-Item .supabase-local\dumps\data.sql).Length` phải lớn hơn vài MB.

---

## 3. Nạp vào Postgres local

Copy file vào container rồi chạy `psql` **bên trong** container. Không pipe file qua PowerShell 5.1 (`Get-Content | docker exec`), vì cách đó làm hỏng chữ tiếng Việt.

```powershell
$DB = docker ps --filter "name=supabase_db" --format "{{.Names}}"
$DB                                                # ví dụ: supabase_db_.supabase-local
docker cp .supabase-local\dumps "${DB}:/tmp/dumps"

docker exec $DB psql "postgresql://postgres:postgres@127.0.0.1:5432/postgres" `
  -v ON_ERROR_STOP=1 --single-transaction `
  -f /tmp/dumps/roles.sql `
  -f /tmp/dumps/schema.sql `
  -c "SET session_replication_role = replica" `
  -f /tmp/dumps/data.sql
```

- `--single-transaction` + `ON_ERROR_STOP`: lỗi ở đâu thì rollback toàn bộ, không để lại DB dở dang.
- `session_replication_role = replica` tạm tắt trigger và FK khi nạp dữ liệu, tránh lỗi thứ tự bảng và trigger audit.
- Nạp xong thì xóa bản copy trong container: `docker exec $DB rm -rf /tmp/dumps`

---

## 4. Đặt mật khẩu cho các login của app

Đây là mật khẩu **chỉ dùng local**. Tự đặt chuỗi ngẫu nhiên và không dùng lại mật khẩu cloud.

```powershell
docker exec -it $DB psql "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
```

```sql
-- <MK1>, <MK2>, <MK3>: mật khẩu local bạn tự đặt cho từng role (dùng lại ở bước cấu hình .env).
ALTER ROLE eas_backend_login WITH LOGIN PASSWORD '<MK1>';
ALTER ROLE eas_worker_login  WITH LOGIN PASSWORD '<MK2>';
ALTER ROLE eas_mock_login    WITH LOGIN PASSWORD '<MK3>';

-- Kiểm tra bằng đúng login của API (RLS phải cho đọc):
SET ROLE eas_backend_login;
SELECT count(*) FROM eas.app_user;
RESET ROLE;
\q
```

Tài khoản người dùng EAS giữ nguyên hash mật khẩu từ cloud, nên **đăng nhập web bằng mật khẩu như trên cloud**.

---

## 5. Storage (tuỳ chọn)

File đính kèm nằm trong Supabase Storage và **không** đi theo dump DB. Có hai cách:

- **Không cần file đính kèm**: để `EAS_SUPABASE_SECRET_KEY=` trống và `EAS_REQUIRE_STORAGE=false`. Mọi chức năng khác vẫn chạy.
- **Muốn thử upload/tải file**: vào Studio `http://127.0.0.1:55323` → Storage → tạo bucket **private** tên `eas-private`, rồi dùng secret key local từ `supabase status`. File cũ trên cloud vẫn không mở được; chỉ file upload mới mở được.

---

## 6. Tạo file env cho Supabase local

Copy `.env` thành `.env.local-supabase` (mẫu `.env.*` đã bị gitignore) và chỉ sửa các dòng sau:

```dotenv
# Container gọi ra máy host qua host.docker.internal; Postgres local không bật TLS
EAS_API_DATABASE_URL=postgresql://eas_backend_login:<MK1>@host.docker.internal:55322/postgres?sslmode=disable
EAS_WORKER_DATABASE_URL=postgresql://eas_worker_login:<MK2>@host.docker.internal:55322/postgres?sslmode=disable
EAS_MOCK_DATABASE_URL=postgresql://eas_mock_login:<MK3>@host.docker.internal:55322/postgres?sslmode=disable

EAS_SUPABASE_URL=http://host.docker.internal:55321
EAS_SUPABASE_SECRET_KEY=            # hoặc secret key local (bước 5)
EAS_REQUIRE_STORAGE=false

# Tránh gửi email thật từ dữ liệu thử: để trống host,
# hoặc giữ SMTP nhưng gom mọi thư về hộp thư của bạn bằng EAS_EMAIL_TEST_RECIPIENT
EAS_EMAIL_HOST=
```

Nếu chạy API/worker **từ terminal** thay vì Docker, thay `host.docker.internal` bằng `127.0.0.1`.

`scripts/validate_env.py` sẽ báo "remote PostgreSQL connections must require TLS" cho host `host.docker.internal`. Với Supabase local, cảnh báo này có thể bỏ qua.

---

## 7. Trỏ app vào Supabase local

Chỉ cần tạo lại container với env mới, không phải build lại image:

```powershell
docker compose -p eas --env-file .env.local-supabase up -d --force-recreate api worker mock_systems
docker exec eas-redis-1 redis-cli FLUSHALL        # xóa cache còn dữ liệu của DB cũ
```

Kiểm tra:

```powershell
docker logs eas-api-1 --tail 30                   # không có lỗi kết nối DB
curl.exe -s http://127.0.0.1:8000/health/db       # trả về 200
```

Sau đó mở `http://127.0.0.1:8080` (nhân viên) hoặc `http://127.0.0.1:8081` (admin) và đăng nhập như bình thường.

---

## 8. Quay lại cloud và dừng local

```powershell
docker compose -p eas --env-file .env up -d --force-recreate api worker mock_systems
docker exec eas-redis-1 redis-cli FLUSHALL

supabase stop --workdir .supabase-local           # giữ dữ liệu cho lần sau
# supabase stop --workdir .supabase-local --no-backup   # xóa sạch dữ liệu local
```

## 9. Lấy lại dữ liệu mới nhất từ cloud

```powershell
supabase db reset --workdir .supabase-local       # DB local về trống (thư mục này không có migration nào)
```

Rồi làm lại bước 2 → 4. Mật khẩu login trong `.env.local-supabase` giữ nguyên, nên bước 4 dùng lại đúng các mật khẩu cũ.

---

## Sự cố thường gặp

| Hiện tượng | Nguyên nhân và cách xử lý |
|---|---|
| `supabase db dump` lỗi kết nối hoặc `prepared statement` | Đang dùng cổng 6543. Đổi sang Session pooler cổng **5432**. |
| `password authentication failed` khi dump | Mật khẩu chứa ký tự đặc biệt chưa percent-encode. |
| Nạp `roles.sql` báo `role ... already exists` | DB local đã nạp trước đó. Chạy `supabase db reset` (bước 9) rồi nạp lại. |
| API log `42704` (role không tồn tại) ở health/readiness | Thiếu role trong `roles.sql` (ví dụ `eas_migration`). Kiểm tra `SELECT rolname FROM pg_roles WHERE rolname LIKE 'eas%';`. |
| API log `password authentication failed for user "eas_backend_login"` | Chưa làm bước 4, hoặc mật khẩu trong `.env.local-supabase` không khớp. |
| API không kết nối được `host.docker.internal` | Docker Desktop tắt mục *Add the \*.docker.internal names to the host's /etc/hosts*. Bật lại trong Settings. |
| Trang vẫn hiện dữ liệu cũ sau khi đổi DB | Chưa `FLUSHALL` Redis. API còn cache trong process, nên chạy `docker restart eas-api-1`. |
| Lỗi tiếng Việt bị vỡ dấu sau khi nạp | Đã pipe file qua PowerShell. Nạp lại theo đúng bước 3 (`docker cp` + `psql -f`). |
