# Prompt Hướng Dẫn AI Agent Sửa Toàn Bộ Lỗi Dự Án EAS (DATN)

Bạn có thể copy toàn bộ nội dung dưới đây và dán trực tiếp cho AI Agent (Cursor, Windsurf, GitHub Copilot, Claude Code, Codex...) đang mở trong thư mục gốc dự án của bạn để Agent tự động thực thi và kiểm tra toàn bộ các bản vá.

```markdown
Bạn là một Senior Full-Stack & DevSecOps Engineer. Hãy kiểm tra và sửa triệt để toàn bộ các lỗi hiện có trong dự án **Enterprise Approval System (EAS / DATN)** theo danh sách đặc tả kỹ thuật chi tiết dưới đây.

## RÀNG BUỘC QUAN TRỌNG (CONSTRAINTS)
1. **Không làm hỏng các bài kiểm thử hiện tại**:
   - Trong `api_core/workflow/views.py` (`request_list`) và `api_core/workflow/ops_service.py` (`list_ops_metadata`), BẮT BUỘC giữ nguyên phép gán trực tiếp `sql = """..."""` và `params = [...]` bên trong thân hàm để AST parser của `connection_tests/test_ui_sql_regressions.py` đọc được.
   - Giữ nguyên URL `/api/v1/auth/me` (không gắn query string vào URL) khi gọi từ `web_client/src/App.jsx` để tương thích với Playwright mock `page.route('**/api/v1/auth/me', ...)` trong `web_client/e2e/ui.spec.js`.
   - Không sửa file `database/EAS_Supabase_SQL/01_demo_seed_DEV_ONLY.sql` vì `api_core/management/commands/configure_e2e_user.py` kiểm tra hằng số `!UNUSABLE_DEMO_REQUESTER`.
   - Không đụng vào các file cấu hình cá nhân chứa mật khẩu thật (`.env.database`, `.env.worker`, `ai_service/.env`) nếu chúng đã tồn tại; chỉ cập nhật các file `.example` và logic đọc cấu hình.

---

## NHIỆM VỤ 1: Sửa lỗi `401 Unauthorized` tại `/api/v1/auth/me`, lỗi mất phiên `LocMemCache` khi reload, và lỗi mật khẩu mẫu `Admin@123456` (`EAS-H04`, `EAS-006`)

### 1.1. File `api_core/authn/service.py`
- **Vấn đề**:
  1. Khi mở trang web lúc chưa đăng nhập, Frontend gọi `/api/v1/auth/me` và nhận `401`, làm trình duyệt báo đỏ 2 lỗi `Failed to load resource: 401 (Unauthorized)`.
  2. Khi chạy local không có Redis (`LocMemCache`), mỗi khi Django `runserver` reload thì cache RAM bị xóa làm `load_actor_from_session` trả về `None` dù cookie phiên và `auth_version` trong DB vẫn hợp lệ.
  3. Các tài khoản trong `database/seed.sql` và `database/schema.sql` đang chứa chuỗi hash giả lập (`pbkdf2_sha256$600000$seed$TempHashForDevOnly00000000000000000000000000000=` hoặc `pbkdf2_sha256$600000$admin_salt$dummy_hash_for_bootstrap_change_on_first_login` hoặc `!UNUSABLE_DEMO_...`) nên `check_password` luôn trả về `False` khi đăng nhập và khi đổi mật khẩu.
  4. Khi `actor.must_change_password = True`, `require_actor` chặn cả `/api/v1/auth/logout` và `/api/v1/auth/change-password`.
- **Cách sửa trong `api_core/authn/service.py`**:
  1. Bổ sung import `hmac`, `os`, `from django.conf import settings`, `JsonResponse`, và `correlation_id` từ `api_core.http`.
  2. Thêm hằng số `SEED_PLACEHOLDER_HASHES` và hàm `verify_user_password(password: str, password_hash: str) -> bool`:
     ```python
     SEED_PLACEHOLDER_HASHES = frozenset(
         {
             "pbkdf2_sha256$600000$seed$TempHashForDevOnly00000000000000000000000000000=",
             "pbkdf2_sha256$600000$admin_salt$dummy_hash_for_bootstrap_change_on_first_login",
         }
     )


     def verify_user_password(password: str, password_hash: str) -> bool:
         if not isinstance(password, str) or not isinstance(password_hash, str):
             return False
         if check_password(password, password_hash):
             return True
         if getattr(settings, "ENVIRONMENT", "") == "development" and (
             password_hash in SEED_PLACEHOLDER_HASHES
             or password_hash.startswith("!UNUSABLE_DEMO_")
         ):
             fallback_pwd = os.getenv("EAS_DEV_DEFAULT_PASSWORD", "Admin@123456")
             return hmac.compare_digest(password, fallback_pwd)
         return False
     ```
  3. Trong `change_password(...)`, thay `check_password(current_password, row[0])` và `check_password(new_password, row[0])` bằng `verify_user_password(current_password, row[0])` và `verify_user_password(new_password, row[0])`.
  4. Trong `load_actor_from_session(request)`:
     - Kiểm tra `if cache.get(f"eas:session:revoked:{session_id}"): return None`.
     - Đặt `expected_marker = f"{user_id}:{auth_version}"` và `active_session = cache.get(f"eas:session:{session_id}")`.
     - Nếu `active_session != expected_marker`: chỉ `return None` khi `active_session is not None or getattr(settings, "ENVIRONMENT", "") != "development" or getattr(settings, "REDIS_URL", "")`. Nếu đang ở `development` dùng `LocMemCache` và `active_session is None`, cho phép truy vấn PostgreSQL kiểm tra `WHERE id = %s AND is_active AND auth_version = %s`; nếu hợp lệ thì nạp lại `cache.set(f"eas:session:{session_id}", expected_marker, timeout=getattr(settings, "SESSION_COOKIE_AGE", 28800))`.
  5. Trong `require_actor(*required_roles)`:
     - Khi `actor is None`: sau `request.session.flush()`, nếu `request.headers.get("X-Auth-Optional") == "1"` và `request.path in {"/api/v1/auth/me", "/api/v1/me"}`, trả về `JsonResponse({"user": None, "authenticated": False, "correlation_id": correlation_id(request)}, status=200)`. Ngược lại giữ nguyên `return api_error(request, "AUTHENTICATION_REQUIRED", status=401)`.
     - Khi `actor.must_change_password` là `True`: cho phép `request.path in {"/api/v1/auth/password", "/api/v1/auth/change-password", "/api/v1/auth/logout"}`.

### 1.2. File `api_core/authn/views.py`
- Import `verify_user_password` từ `.service`.
- Trong `login(request)`: thay `check_password(password, user.password_hash)` bằng `verify_user_password(password, user.password_hash)`.
- Trong `logout(request)`: ngoài `cache.delete(f"eas:session:{session_id}")`, thêm:
  ```python
  cache.set(
      f"eas:session:revoked:{session_id}",
      "1",
      timeout=settings.SESSION_COOKIE_AGE,
  )
  ```

### 1.3. File `api_core/config/settings.py`
- Khi `ENVIRONMENT in {"development", "test"}`, tự động bổ sung các origin local vào `CSRF_TRUSTED_ORIGINS` nếu chưa có:
  `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:5174`, `http://127.0.0.1:5174`, `http://localhost:8000`, `http://127.0.0.1:8000`, `http://localhost:8080`, `http://127.0.0.1:8080`, `http://localhost:8088`, `http://127.0.0.1:8088`.
- Nếu `EAS_AI_INTERNAL_SECRET` đang trống và `ENVIRONMENT in {"development", "test"}`, đặt giá trị mặc định `"eas-local-dev-shared-internal-secret-2026"`.

---

## NHIỆM VỤ 2: Sửa lỗi `404 Not Found` (Favicon, Root Route, Vite Proxy) và tối ưu khởi tạo phiên ở Frontend (`web_client`)

### 2.1. File `api_core/config/urls.py`
- Bổ sung route gốc `""` (trỏ tới `health_views.live`) và route `"favicon.ico"` (trả về `HttpResponse(status=204)`) vào đầu `urlpatterns` để truy cập trực tiếp `http://127.0.0.1:8000/` hoặc `/favicon.ico` không bị lỗi 404.

### 2.2. Tạo Favicon và cập nhật `web_client/index.html` & `web_client/vite.config.js`
- Tạo `web_client/public/favicon.svg` (biểu tượng chữ E màu xanh `#1e3a8a`) và file nhị phân `web_client/public/favicon.ico` hợp lệ.
- Trong `web_client/index.html`, thêm vào `<head>`:
  ```html
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="alternate icon" href="/favicon.ico" />
  ```
- Trong `web_client/vite.config.js`, cấu hình proxy cho `/api` (`http://127.0.0.1:8000`), `/health` (`http://127.0.0.1:8000`), và `/ai` (`http://127.0.0.1:8001`) với `changeOrigin: false`.

### 2.3. File `web_client/src/api.js` và `web_client/src/App.jsx`
- Trong `web_client/src/api.js`: đổi `credentials: "same-origin"` thành `credentials: "include"`.
- Trong `web_client/src/App.jsx`:
  - Tạo hàm `fetchInitialSession()` dùng biến module-level `_bootstrapSessionPromise` để deduplicate 2 lần gọi song song của React `<StrictMode>` khi mount lần đầu, gọi `initializeCsrf().then(() => api("/api/v1/auth/me", { headers: { "X-Auth-Optional": "1" } }))` rồi giải phóng `_bootstrapSessionPromise` sau 50ms.
  - Khi nhận phản hồi từ `fetchInitialSession()`, cập nhật `setUser(r?.user || null)`. Giữ nguyên khối `.catch()` xử lý `PASSWORD_CHANGE_REQUIRED`, `401`, `403`.

---

## NHIỆM VỤ 3: Sửa toàn bộ lỗi SQL Schema Mismatch (`42703`), Untyped NULL (`42P18`), và chuẩn hóa tham số lọc (`22P02` / `22007`)

### 3.1. File `api_core/workflow/views.py` (hàm `request_list`)
- Chuẩn hóa các tham số query string rỗng `""` về `None`:
  ```python
  tab = (request.GET.get("tab") or "").strip() or None
  status_filter = (request.GET.get("status") or "").strip() or None
  search_filter = (request.GET.get("q") or "").strip()[:100] or None
  type_code_filter = (request.GET.get("type_code") or "").strip() or None
  dept_raw = (request.GET.get("department_id") or "").strip() or None
  from_raw = (request.GET.get("created_from") or "").strip() or None
  to_raw = (request.GET.get("created_to") or "").strip() or None
  ```
- Kiểm tra `dept_raw` bằng `UUID(dept_raw)` (nếu lỗi trả về `api_error(request, "INVALID_DEPARTMENT_ID", status=400)`).
- Kiểm tra `from_raw` và `to_raw` bằng `datetime.fromisoformat(val.replace("Z", "+00:00"))` (nếu lỗi trả về `api_error(request, "INVALID_DATE_FILTER", status=400)`).
- Giữ nguyên phép gán `sql = """..."""` và `params = [...]` trong thân hàm `request_list`.

### 3.2. File `api_core/workflow/ops_service.py` (hàm `list_ops_metadata`)
- Chuẩn hóa `status_filter`, `search_filter`, `type_code_filter`, `dept_filter` sao cho chuỗi rỗng `""` hoặc chỉ chứa khoảng trắng được chuyển thành `None`.

### 3.3. File `api_core/workflow/service.py` (hàm `report_execution_issue`)
- Sửa dòng điều kiện JOIN `eas.execution_attempt`:
  - Từ: `AND (%s IS NULL AND a.state IN ('READY', 'RUNNING') OR a.id = %s)`
  - Thành: `AND (%s::uuid IS NULL AND a.state IN ('READY', 'RUNNING') OR a.id = %s::uuid)`

### 3.4. File `api_core/workflow/config_service.py`
- Trong `list_config_releases`: chuẩn hóa `type_code_filter = (query_params.get("type_code") or "").strip() or None` và `state_filter = (query_params.get("state") or "").strip() or None`.
- Trong `create_or_clone_release` (nhánh tạo mới khi không có `source_release_id`):
  - Đặt `actor_bindings = {"schema_version": 1, "departments": {}}` (thay vì `"bindings": {}`).
  - Nếu `rt_lifecycle in ("B", "C")`, thêm `"executor": "IT_EXEC"` vào `default_rule` và đặt `"execution_hours": 48` trong `sla_profile`.
  - Nếu `rt_lifecycle == "C"`, thêm `"acceptor": "REQUESTER"` vào `default_rule` và đặt `"acceptance_hours": 24` trong `sla_profile`.
- Trong `update_draft_release`: xóa `, updated_at = statement_timestamp()` khỏi câu lệnh `UPDATE eas.config_release` (vì bảng `eas.config_release` không có cột `updated_at`).
- Trong `publish_config_release`: xóa `, updated_at = statement_timestamp()` khỏi câu lệnh `UPDATE eas.config_release` và câu lệnh `UPDATE eas.request_type` (vì cả 2 bảng đều không có cột `updated_at`).

### 3.5. File `api_core/workflow/reporting.py`
- Trong `get_request_metrics_report`: chuẩn hóa `type_code_filter` và `dept_filter` từ chuỗi rỗng về `None`.
- Trong `verify_audit_chain`: xóa dòng `WHERE scope_key = 'ADMIN'` khỏi câu lệnh `SELECT ... FROM eas.admin_event` (vì bảng `eas.admin_event` không có cột `scope_key`).

### 3.6. File `api_core/worker.py` (hàm `acknowledge_outbox`)
- Sửa câu truy vấn kiểm tra người nhận thông báo để ép kiểu UUID tường minh:
  ```sql
  SELECT u.is_active,
         CASE
           WHEN %s::uuid IS NULL THEN TRUE
           WHEN r.requester_id = u.id THEN TRUE
           WHEN p.id IS NOT NULL AND p.read_revoked_at IS NULL THEN TRUE
           ELSE FALSE
         END AS can_read
  FROM eas.app_user u
  LEFT JOIN eas.request r ON r.id = %s::uuid
  LEFT JOIN eas.request_participant p ON p.request_id = %s::uuid AND p.user_id = u.id
  WHERE u.id = %s
  ```

### 3.7. File `api_core/management/commands/privacy_case.py`
- Bảng `eas.app_user` không có cột `email`.
- Ở câu lệnh `SELECT` kiểm tra hồ sơ, thay `u.username, u.email` thành `u.username, u.display_name` (giữ nguyên 6 cột trả về để tương thích với mock trong `api_core/tests/test_reporting_and_cli.py`).
- Ở câu lệnh `UPDATE eas.app_user` trong nhánh `execute-erase`, xóa dòng `email = %s,` và bỏ tham số email tương ứng.

---

## NHIỆM VỤ 4: Cập nhật mã băm mật khẩu thật và bổ sung hàm PL/pgSQL trong `database/`

1. Tính mã băm PBKDF2-SHA256 chuẩn Django cho mật khẩu `Admin@123456` (ví dụ `pbkdf2_sha256$600000$eas_seed_2026$/yIu1DHt5Xd+/BX6FW+U9GwEEuZjgxwk1613D9BohoU=`) và thay thế:
   - Chuỗi `pbkdf2_sha256$600000$seed$TempHashForDevOnly00000000000000000000000000000=` trong `database/seed.sql`.
   - Chuỗi `pbkdf2_sha256$600000$admin_salt$dummy_hash_for_bootstrap_change_on_first_login` trong `database/schema.sql` và `database/migrations/init.sql`.
2. Cuối file `database/schema.sql` và `database/migrations/init.sql`, bổ sung các hàm/trigger PL/pgSQL (`CREATE OR REPLACE FUNCTION`) còn thiếu để đồng bộ với `00_eas_supabase_schema.sql`: `eas.request_code_seq`, `eas.next_request_code()`, `eas.lock_security(boolean)`, `eas.lock_audit_head(text)`, `eas.initialize_request_head()`, và `eas.advance_audit_head()`.
3. Cập nhật `verify_admin_password_local.py` dùng `verify_user_password` và tạo mới script `fix_seed_passwords_local.py` để cập nhật tất cả mật khẩu placeholder trong bảng `eas.app_user` sang mã băm PBKDF2-SHA256 chuẩn của `Admin@123456`.

---

## NHIỆM VỤ 5: Đồng bộ Secret Django ↔ AI Service (`EAS-005`), Fallback Summarize (`503`), và chuẩn hóa Worker DSN (`EAS-004`)

1. Trong `.env.database.example` và `ai_service/.env.example`: đặt chung giá trị mặc định cho `EAS_AI_INTERNAL_SECRET` và `INTERNAL_API_SECRET` là `eas-local-dev-shared-internal-secret-2026`.
2. Trong `ai_service/config.py`:
   - Đổi `env_file_encoding="utf-8-sig"` để không lỗi BOM trên Windows.
   - Trong `model_post_init`, nếu `self.internal_api_secret` đang trống hoặc là chuỗi mẫu (`replace-with-the-same-random-secret-as-...`), tự động đọc `EAS_AI_INTERNAL_SECRET` từ `../.env.database` hoặc dùng `"eas-local-dev-shared-internal-secret-2026"` khi không phải môi trường `production`.
3. Trong `api_core/ai_client.py` (và `ai_service/ai_client.py` nếu có): viết hàm `_resolve_internal_secret()` đọc động từ `django.conf.settings.EAS_AI_INTERNAL_SECRET` / `os.environ` và fallback về `"eas-local-dev-shared-internal-secret-2026"` nếu đang mang giá trị mẫu rỗng.
4. Trong `ai_service/routers/summarize.py`:
   - Bổ sung hàm `_local_extractive_summarize(req: SummarizeRequest) -> SummarizeResult` để tạo bản tóm tắt tiếng Việt trích xuất từ `title`, `description`, `request_type`, `requester_name`, `amount`, `risk_score`, `data`.
   - Khi `not settings.gemini_api_key` hoặc khi gọi Gemini gặp ngoại lệ, trả về `_local_extractive_summarize(body)` thay vì ném `HTTPException(503)` / `HTTPException(500)`.
5. Trong `run_worker_local.py` và `check_eas_connections_local.py`:
   - Nhận diện các chuỗi mẫu chưa cấu hình (`YOUR_PROJECT_REF`, `YOUR_POOLER_HOST`, `ENCODED_PASSWORD`) trong `.env.worker` để báo `WARN` thay vì làm văng `psycopg.ProgrammingError`.
   - Tự động URL-encode phần `password` nếu `EAS_WORKER_DATABASE_URL` chứa ký tự đặc biệt (`@`, `:`), đồng thời hỗ trợ đọc `WORKER_DB_USER` + `WORKER_DB_PASSWORD` kết hợp với `DB_HOST`/`DB_PORT`/`DB_NAME` từ `.env.database`.

---

## NHIỆM VỤ 6: Bổ sung Regression Tests và Chạy Kiểm Tra Xác Nhận

1. Trong `connection_tests/test_ui_sql_regressions.py`, bổ sung 3 test method vào `EASRegressionTests`:
   - `test_auth_me_optional_bootstrap_and_favicon_prevent_401_404`
   - `test_sql_queries_do_not_reference_nonexistent_columns`
   - `test_service_and_worker_nullable_uuid_parameters_are_typed`
2. Chạy các lệnh kiểm tra sau để đảm bảo 100% pass và không có lỗi cú pháp:
   ```bash
   python -m compileall -q .
   python -m unittest discover -s connection_tests -p "test_*.py" -v
   node --test web_client/e2e/domain.test.mjs
   python check_eas_connections_local.py --config-only
   ```
```
