# EAS — Sổ theo dõi lỗi hiện tại (26/10/2026)

**Phạm vi:** dự án `DATN` (Django, React + Vite/Web Admin, AI FastAPI, Supabase, Worker, Storage, ClamAV, Git). Nguồn: các log người sử dụng cung cấp trong cuộc trò chuyện, kết quả `check_local.cmd` gần nhất (22 PASS / 6 WARN / 2 FAIL / 2 SKIP, sau đó chưa có bản kiểm tra toàn bộ mới) và rà soát **bản ZIP đã sửa kết nối** (`DATN_EAS_Ban_Sua_Ket_Noi_Local.zip`). Không truy cập được phiên chạy trên máy Windows của người sử dụng. **Không được coi mọi lỗi bên dưới đang tái hiện ngay lúc đọc.**

## A. Lỗi chưa được chứng minh đã khắc phục

| ID | Mức độ | Bằng chứng đã ghi nhận | Nguyên nhân đã xác nhận / giả thuyết | Cách xác nhận và xử lý |
|---|---|---|---|---|
| EAS-001 | High | `git push -u origin dangduy` bị GitHub từ chối: DLL XGBoost 169.03 MB > 100 MB | `.venv-ai` đã xuất hiện trong **ít nhất một commit được push**, `.gitignore` ở bản ZIP đã sửa chỉ khai báo `.venv/`, chưa khai báo `.venv-ai/` rõ ràng | Thêm `.venv-ai/`, `logs/`, loại file khỏi Git **và lịch sử các commit chưa push**; không chỉ `git rm --cached` trong commit mới. Chỉ push khi đã kiểm tra lịch sử và file `.env` có secret. |
| EAS-002 | High | `GET /api/v1/notifications?limit=20&offset=0&unread=false` HTTP **500** | Exception khi Django xử lý API; nguyên nhân SQL/quyền/logic **chưa xác định** vì chưa có traceback hay kết quả diagnostic | Chạy `diagnose_eas_500.py` ở chế độ chỉ đọc, ghi log backend, lấy exception / SQLSTATE; không chạy migrate hoặc sửa DB tùy tiện. |
| EAS-003 | High | `GET /api/v1/requests?limit=20&offset=0&tab=mine&_revision=0` HTTP **500** (2 lần) | Lỗi backend truy vấn/lọc dữ liệu. Trước đó có giả thuyết `NULL` chưa định kiểu (`42P18`), **chưa được chứng minh** | Chạy chẩn đoán read-only và lấy traceback; nếu `42P18` thì sửa placeholder `%s` với kiểu SQL phù hợp (phải kiểm tra query cụ thể). |
| EAS-004 | High | `PostgreSQL Worker: ProgrammingError, SQLSTATE=unknown`; checker cảnh báo DSN không có username Worker mong đợi | File `.env.worker` / `EAS_WORKER_DATABASE_URL` có thể dùng nhầm role hoặc DSN sai; chưa đủ chứng cứ chốt nguyên nhân | Xem role `eas_worker_login` và tư cách thành viên `eas_worker`, kiểm URL không in password; tái chạy `check_local.cmd`; không chạy Worker ghi dữ liệu cho tới khi DB probe PASS. |
| EAS-005 | Medium | `Django → AI xác thực nội bộ` HTTP **401**, trong khi AI `/health` **200** | FastAPI không chấp nhận header/secret đang dùng tại thời điểm kiểm tra, hoặc tiến trình AI dùng env cũ | Đối chiếu `EAS_AI_INTERNAL_SECRET` và `INTERNAL_API_SECRET` không in giá trị, dừng tiến trình AI cũ, chạy lại cả Django & AI, kiểm 404 trên endpoint test chưa tồn tại (404 tại endpoint này là PASS). |
| EAS-006 | Medium | `POST /api/v1/auth/password` HTTP **400** `PASSWORD_POLICY_VIOLATION` | Mật khẩu mới không đáp ứng chính sách. Chưa có log chứng minh đổi thành công | Dùng mật khẩu riêng 12–128 ký tự, hoa/thường/số/ký tự đặc biệt, không chứa username, khác mật khẩu cũ; kiểm code lỗi response. Không log mật khẩu. |
| EAS-007 | Medium | `[WARN] Django secret: Thiếu DJANGO_SECRET_KEY` | Backend local có thể dùng khóa mặc định dev | Thiết lập secret ngẫu nhiên mới trong `.env.database`; khởi động lại Django, các session trước có thể hết hạn. Không dùng chung key với AI. |
| EAS-008 | Medium | `[WARN] Storage local ... EAS_REQUIRE_STORAGE=false` và `[WARN] Supabase Storage ... thiếu URL/key` | Readiness bỏ qua Storage/ClamAV; upload/downloading / quét mã độc chưa chứng minh | Cấu hình private bucket, Storage secret (mới), ClamAV cổng TCP, chuyển `EAS_REQUIRE_STORAGE=true`, test E2E upload/download/virus scan. |
| EAS-009 | Medium | `[WARN] AI tích hợp nghiệp vụ: Không tìm thấy code gọi AI client từ view/service` | Mô hình FastAPI chạy độc lập chưa có bằng chứng được gọi trong workflow | Bổ sung gọi AI với giới hạn tác động theo chính sách dự án, test kết quả trên hồ sơ thật và fallback khi AI lỗi. |
| EAS-010 | Low | `[WARN] Redis/cache: chạy LocMem` | Cache không chia sẻ giữa nhiều process/server | Local 1 process có thể dùng LocMem; trước triển khai nhiều process, cấu hình Redis, test auth/session/rate-limit. |

## B. Lỗi/cảnh báo trước đây — đã khắc phục hoặc không phải lỗi

| ID | Bằng chứng | Trạng thái theo log |
|---|---|---|
| EAS-H01 | `FATAL: password authentication failed for user postgres` / `AUTH_FAILED` | **Đã khắc phục** — kết quả sau là `AUTH_SUCCESS`, `POSTGRES_ROLE: eas_backend_login`. |
| EAS-H02 | Vite proxy `ECONNREFUSED 127.0.0.1:8000` | **Đã khắc phục** — Django `/health/live` 200 và Frontend proxy CSRF 200. |
| EAS-H03 | `AI /health: không kết nối được` | **Đã khắc phục** — `AI /health: HTTP 200` trong checker mới hơn. |
| EAS-H04 | `POST /auth/login` HTTP 401 khi DB chứa password hash mẫu (đã xác nhận SQL placeholder true) | **Đã tìm được nguyên nhân**; không có bằng chứng cuối cùng chứng minh đăng nhập/đổi mật khẩu hoàn tất. |
| EAS-H05 | `GET /auth/me` HTTP 401 trước đăng nhập | **Bình thường**, không phải lỗi nếu chưa có session hợp lệ. |
| EAS-H06 | `favicon.ico` HTTP 404 | **Không chặn nghiệp vụ**. |
| EAS-H07 | Django: 3 migration chưa áp dụng (`contenttypes`,`sessions`) | **Cảnh báo chưa xác minh cần áp dụng**; không chạy migrate trên schema có sẵn khi chưa kiểm tra kế hoạch. |
| EAS-H08 | FastAPI route classify mismatch; risk JSON key mismatch; Supabase new key auth header | **Đã được sửa trong ZIP bàn giao**, nhưng chưa có E2E xác nhận ở máy local. |
| EAS-H09 | `ModuleNotFoundError: No module named django` khi dùng Python hệ thống | **Đã khắc phục** bằng `.venv`; `Django 5.2.18` đã được xác nhận. |
| EAS-H10 | `py -3.11 -m venv` báo thiếu Python 3.11 | **Đã tìm được cách chạy AI với Python 3.12**; `AI /health` về sau đạt HTTP 200. |
| EAS-H11 | `Test-NetConnection is not recognized` trong CMD | Không phải lỗi dự án; gọi bằng `powershell -Command ...` đã trả `TcpTestSucceeded: True`. |

## C. Những chức năng đã PASS theo checker gần nhất

- Backend `.env.database` nạp được; URL DB dùng user `eas_backend_login`.
- PostgreSQL Backend xác thực thành công; thuộc nhóm `eas_api`; đủ 30 bảng.
- Django `/health/live` 200; `/health/ready` 200 (trong chế độ bỏ qua Storage/ClamAV).
- CSRF Django và Frontend proxy CSRF 200.
- Vite frontend 200.
- AI health 200, 5 file model có mặt.
- Route phân loại AI không còn dấu hiệu mismatch đã biết.

## D. Thu thập lỗi MỚI trên Windows

Chép `collect_eas_logs.py`, `collect_logs.cmd` và `diagnose_eas_500.py` (nếu chưa có) vào `D:\Đồ án\DATN`. Mở Terminal CMD ngay tại `DATN`.

```
collect_logs.cmd
collect_logs.cmd --include-sql
```

Kết quả được lưu tại `D:\Đồ án\DATN\logs\eas_snapshot_YYYYMMDD_HHMMSS.log`.

Để khởi động và **ghi lại stdout/stderr mới** của từng tiến trình (không thu hồi log cũ):

```
collect_logs.cmd --watch backend
collect_logs.cmd --watch frontend
collect_logs.cmd --watch ai
```

Chạy mỗi lệnh trong một Terminal riêng, tránh chạy hai server trên cùng cổng. Worker có thể **ghi vào DB** nếu có việc chờ; chỉ chạy khi có chủ đích:

```
collect_logs.cmd --watch worker --allow-worker-write
```

Bộ công cụ không tự động đăng nhập, sửa database, push Git hoặc ghi tệp `.env`. `--include-sql` thử truy vấn xử lý hai API 500 trong transaction READ ONLY. Nếu script báo `SKIP`, hãy kiểm tra thiết lập môi trường. Không dùng kết quả file ZIP để khẳng định trạng thái máy Windows hiện tại.

**Bảo mật:** thêm `logs/`, `.venv-ai/`, `.env`, `.env.*` (ngoại trừ file `.example`) vào `.gitignore`; kiểm tra trước khi chia sẻ log. Bộ lọc log che các mẫu khóa thông dụng nhưng không thể bảo đảm phát hiện mọi bí mật trong traceback / URL / response.
