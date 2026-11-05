# Kiểm toán code, dữ liệu và CSDL — EAS (04/11/2026)

| Thuộc tính | Giá trị |
|---|---|
| Phạm vi | `api_core`, `ai_service`, `web_client`/`web_admin`, `api_gateway`, `mobile_app`, lược đồ và dữ liệu Supabase live |
| Cách làm | Đọc mã nguồn; chạy lại toàn bộ test, linter, kiểm phụ thuộc; truy vấn **chỉ đọc** trên DB live (catalog, RLS, policy, toàn vẹn dữ liệu); đo hiệu năng |
| Người soát | Nhóm vai trò Security · Backend · DBA · AI · QA · BA |
| Đã sửa gì | Lúc lập báo cáo: chưa sửa gì. Trạng thái xử lý từng mục: xem **§7** (cập nhật cùng ngày) |

## 0. Kết luận nhanh

| Câu hỏi | Trả lời |
|---|---|
| Logic chạy đúng chưa? | **Lõi đúng.** Máy trạng thái, tách nhiệm, chuỗi băm, outbox đều khớp thiết kế; 507 test đạt. Còn **4 lỗi logic** (L1–L4) và **5 vấn đề dữ liệu** (D1–D5) |
| Có lỗ hổng bảo mật không? | **1 lỗ hổng cao đang khai thác được** (S1: người duyệt sửa được cấu hình loại đơn toàn công ty). **2 rủi ro cao tiềm ẩn ở CSDL** (S2, S3). Còn lại ở mức trung bình / thấp |
| Đã tối ưu chưa? | Truy vấn và chỉ mục đường nóng tốt. Nút cổ chai thật là **độ trễ mạng tới DB Sydney** (~250 ms mỗi truy vấn). Có vài điểm tối ưu nhỏ |
| Đạt chuẩn chưa? | ruff 0 lỗi; web và backend lõi 0 lỗ hổng phụ thuộc; header bảo mật, Argon2, CSRF, RLS đạt. Lệch chuẩn: phụ thuộc OCR có CVE; mobile không ghim phiên bản; độ phủ test 62% |
| DB chuẩn chưa? | Thiết kế lõi tốt (FK kép, append-only, khoá lạc quan). Có **dữ liệu lặp ở 3–4 nơi** (trọng số rủi ro, bộ luật AI), **bảng di sản cần dọn**, và **thiếu 4 bảng** cho các tính năng đã chốt |

## 1. Kết quả kiểm tra tự động (chạy 04/11/2026)

| Hạng mục | Kết quả |
|---|---|
| `manage.py test api_core` | 290/290 đạt |
| `tests/run_tests.py` | 153 ca: 152 đạt, 1 bỏ qua |
| `npm test` (web_client) | 64/64 đạt |
| Độ phủ backend | 62% (thấp nhất `workflow/views.py` 51%) |
| `ruff` (api_core, ai_service, scripts, tests) | 0 lỗi |
| `npm audit` web_client, web_admin | 0 lỗ hổng |
| `pip-audit` api_core | 0 lỗ hổng |
| `pip-audit` ai_service | **có lỗ hổng**: `paddlepaddle 2.6.2`, `protobuf 3.20.2`, `imgaug 0.4.0` (xem S7). Sau khi sửa 05/11: sạch |
| Quét bí mật trong repo | `SECRET_GATE=PASS`; `.env` đã nằm trong `.gitignore` |
| SQL động | Không có nối chuỗi giá trị người dùng vào SQL. Tên bảng/cột động chỉ lấy từ danh sách cố định (`administration/service.py`) |
| XSS | Không dùng `dangerouslySetInnerHTML`/`innerHTML`; `localStorage` chỉ lưu cờ giao diện |
| Source map | Tắt ở cả hai bản build |

## 2. Bảo mật

### S1 — CAO, đang khai thác được: người duyệt sửa được cấu hình loại yêu cầu toàn công ty

**Cơ chế:**
1. Ma trận quyền live cấp `requests_workflows: View, Create, Update` cho **APPROVER**, tức 46 tài khoản.
2. API cổng nhân viên `/api/v1/workspace/request-templates` và `/request-templates/{id}` (`api_core/administration/workspace.py:132-141`) dùng lại view quản trị nhưng **bỏ qua `require_actor(*READ_ROLES)`**: nó lấy `__wrapped__` rồi chỉ kiểm quyền module. Hàm `_require_writer` (`administration/workflows.py:235`) cho qua mọi ai có `update`.

**Hậu quả:** một người duyệt bất kỳ có thể:
- tạo loại yêu cầu mới;
- bật / tắt loại yêu cầu;
- đổi `lifecycle` A/B/C (`workflows.py`, câu `UPDATE eas.request_type SET lifecycle`);
- đổi "trọng số tự động hoá".

Hai việc cuối là thay đổi cấu hình kiểm soát mà theo thiết kế chỉ POLICY_ADMIN được làm. Điều này **vi phạm tách nhiệm**: người duyệt tự nới quy trình mà chính họ duyệt.

Ghi chú: việc đổi trọng số hiện không ảnh hưởng tới AI tự duyệt, do lỗi L2 (submit đọc trọng số từ JSON). Nhưng sửa L2 mà chưa sửa S1 thì lỗ hổng trở thành **leo thang quyền**: hạ trọng số ≤ 2 là AI tự duyệt.

**Khắc phục (cả hai, không chọn một):**
1. Dữ liệu: thu hồi `can_update` của APPROVER trên `requests_workflows` (đặt lại thành V/C như các vai trò khác).
2. Code: thao tác cấu hình loại yêu cầu phải đòi `POLICY_ADMIN` ở **máy chủ**, không chỉ dựa vào quyền module. Thêm test "APPROVER gọi PATCH `/workspace/request-templates/{id}` → 403".

### S2 — CAO (tiềm ẩn): 16 policy RLS `USING (true)` cho `anon`/`authenticated`

Live có các policy `anon_auth_read_*` (`SELECT … USING (true)`, role `anon`, `authenticated`) trên 16 bảng, trong đó có:
- `app_user`: chứa `password_hash`;
- `request`;
- `role_membership`;
- `user_permissions`;
- `admin_account`.

Hiện **chưa khai thác được**, vì `anon`/`authenticated` không có quyền `USAGE` trên schema `eas` và không có GRANT bảng. Tuy vậy, chỉ cần một lệnh GRANT lại (Supabase dashboard, migration nhầm) là **lộ toàn bộ băm mật khẩu và hồ sơ** qua REST công khai. Các policy này cũng vi phạm trực tiếp quy tắc AGENTS.md ("NEVER `USING (true)`").

Nguồn gốc: `supabase/migrations/20261103_admin_full_upgrade.sql`.

**Khắc phục:** migration xoá 16 policy `anon_auth_read_*`, kèm câu kiểm tra sau migration bảo đảm không còn policy nào có `roles` chứa `anon`/`authenticated` trong schema `eas`.

### S3 — CAO (tiềm ẩn): 3 hàm `SECURITY DEFINER` không cố định `search_path`, EXECUTE cấp cho PUBLIC

Ba hàm `eas.verify_client_portal_access`, `eas.verify_admin_portal_access`, `eas.get_user_requests_detail` có hai vấn đề:
- chạy với quyền chủ sở hữu và bỏ qua RLS;
- không có `SET search_path`, trong khi ACL cho `PUBLIC` quyền EXECUTE (`=X/eas_migration`).

Rủi ro chuẩn của PostgreSQL: chiếm `search_path` (tạo hàm/bảng cùng tên ở schema khác để hàm definer gọi nhầm). Hiện giảm nhẹ vì PUBLIC không có `USAGE` trên `eas`.

**Khắc phục:** `ALTER FUNCTION … SET search_path = pg_catalog, eas;` và `REVOKE EXECUTE … FROM PUBLIC;` rồi GRANT lại cho `eas_api`, `eas_worker`.

### S4 — TRUNG BÌNH: cổng web gọi thẳng `api:8000`, bỏ qua cổng Nginx

`web_client/nginx.conf:33` và `web_admin/nginx.conf` proxy `/api/` **trực tiếp** tới `api:8000`. Hệ quả: giới hạn tần suất của gateway (đăng nhập 5 lần/phút, upload, API 60 lần/phút) **không áp dụng** cho người dùng web; chỉ còn giới hạn của Django (5 lần/tài khoản, 30 lần/IP mỗi 15 phút). Gateway hiện chỉ phục vụ client khác (mobile, công cụ).

**Khắc phục:** cho hai cổng web proxy tới `gateway:8080`, hoặc chép các `limit_req` vào hai file cấu hình web.

### S5 — TRUNG BÌNH: cổng quản trị thiếu một số header so với cổng nhân viên

`web_admin/nginx.conf` thiếu `Strict-Transport-Security`, `Permissions-Policy`, `server_tokens off`, `autoindex off`, và `object-src 'none'` trong CSP. `web_client/nginx.conf` đã có đủ.

**Khắc phục:** đồng bộ hai file. Nên tách ra một tệp `security_headers.conf` dùng chung.

### S6 — TRUNG BÌNH: gateway mở `/ai/*` ra ngoài

`api_gateway/nginx.conf:177` chuyển `/ai/*` tới dịch vụ AI. Dịch vụ AI đòi `X-Internal-Secret` nên chưa khai thác được, nhưng đây là bề mặt thừa (trình duyệt đã gọi AI qua `api_core`).

**Khắc phục:** gỡ `location /ai/`.

### S7 — TRUNG BÌNH: phụ thuộc OCR có lỗ hổng đã công bố

`ai_service/requirements-paddle.txt`: `paddlepaddle==2.6.2` (PYSEC-2026-1754/1756, sửa ở 3.0.0), `protobuf 3.20.2` (PYSEC-2026-1805/1806), `imgaug 0.4.0` (PYSEC-2026-356). OCR chưa được nối vào giao diện và chỉ gọi nội bộ có khoá.

**Khắc phục:** nâng PaddlePaddle/PaddleOCR lên 3.x, hoặc tách OCR thành image tuỳ chọn không cài mặc định cho tới khi dùng.

### S8 — THẤP

| # | Vấn đề | Vị trí | Khắc phục |
|---|---|---|---|
| S8a | OCR từ URL: kiểm IP trước khi gọi (tốt), nhưng còn **DNS rebinding** (httpx phân giải lại) và đọc toàn bộ phản hồi, không giới hạn kích thước | `ai_service/routers/ocr.py:390-424` | Gọi tới IP đã kiểm (gắn header `Host`); stream có giới hạn 10 MB |
| S8b | Tìm kiếm `ILIKE` không thoát ký tự `%`/`_` | `administration/service.py:226` | Thoát wildcard |
| S8c | `mobile_app/pubspec.yaml` dùng `^1.5.0`, `^6.0.0` | — | Ghim phiên bản chính xác (AGENTS.md) |
| S8d | `@supabase/supabase-js` và `src/supabase.js` không dùng nhưng vẫn nằm trong gói | `web_client`, `web_admin` | Xoá |
| S8e | Elasticsearch trong compose, `xpack.security.enabled=false`, không có code dùng | `docker-compose.yml:214` | Xoá service |
| S8f | Bảng `idempotency_record`: 5/6 dòng đã hết hạn nhưng chưa dọn | — | Job dọn theo `expires_at` / `tombstone_until` |

**Đã đạt** (giữ nguyên):
- Argon2 cho mọi tài khoản (137 `argon2`, 1 tài khoản AI không dùng được);
- cookie HttpOnly / SameSite / Secure khi production;
- CSRF; endpoint nội bộ dùng `hmac.compare_digest`;
- chống dò mật khẩu theo tài khoản và IP, lấy IP phải-nhất trong XFF sau proxy tin cậy (`middleware.py:58-62`);
- 404 khi ngoài phạm vi (chống IDOR);
- kiểm magic bytes + ClamAV;
- tắt Swagger ở production;
- `DEBUG` chỉ bật ở môi trường development;
- `SECRET_KEY` bắt buộc ngoài dev/test;
- RLS bật 49/49 bảng;
- không có GRANT cho `anon`/`authenticated`/`PUBLIC` trên bảng `eas`.

## 3. Logic nghiệp vụ

### L1 — CAO: AI không thể tự duyệt từ bước thứ 2 trở đi (lỗi 500 ẩn)

Cách AI tự duyệt: gán `approval_step.assignee_id = tài khoản AI` rồi mới duyệt (`auto_approval.py:124-160`). Nhưng bảng có chỉ mục UNIQUE `approval_step_instance_id_assignee_id_key (instance_id, assignee_id)`.

Với loại có ≥ 2 cấp và trọng số ≤ 2, khi AI tiếp quản bước 2 sẽ xảy ra trùng khoá. Ví dụ: `LEAVE_SPECIAL` mặc định 2 cấp; `LEAVE` trên 2 ngày.

Diễn biến:
1. `IntegrityError` **không** bị bắt (code chỉ bắt `CommandError`).
2. Endpoint nội bộ trả 500.
3. Worker coi là "AI không khả dụng" và giao bước cho người.

Kết quả an toàn (không duyệt sai), nhưng sai thiết kế, sinh log lỗi 500, và chặn quyết định D5 (AI tự duyệt mọi bước trọng số 1–2).

**Khắc phục:** không đổi `assignee_id`. Ghi thông tin tiếp quản vào audit (`AI_AUTO_APPROVE_TAKEOVER` đã có) và cho `decide_approval` nhận "quyết định thay" của tài khoản AI. Hoặc bỏ ràng buộc UNIQUE đó và thay bằng kiểm tra "một người không duyệt hai bước" (loại trừ tài khoản hệ thống). Bổ sung test hai bước.

### L2 — CAO: ba nguồn "trọng số rủi ro" mâu thuẫn; chỉnh trên giao diện không có tác dụng

| Nguồn | Ai đọc | Ví dụ `ATTENDANCE_ADJUSTMENT` |
|---|---|---|
| `api_core/catalog/catalog_v2.json` | **Gửi đơn** (`service.py:455`, `:1430` gọi `resolve_five_level_metadata(type_code)` không truyền giá trị DB) → quyết định AI tự duyệt | **1** |
| `eas.request_type.risk_weight` | Màn hình danh mục, trang "Yêu cầu & Quy trình" (`catalog/views.py`, `workflow/views.py:543`) | 2 |
| `eas.config_release.risk_weight` | Không ai dùng để quyết định | 3 |

Live có 4 loại lệch giữa DB và quy chế: `ATTENDANCE_ADJUSTMENT`, `ACCESS`, `PURCHASE_REQUEST`, `LAPTOP_PROVISION`.

**Hậu quả:**
- Màn hình hiển thị một con số, hệ thống thực thi con số khác.
- Quản trị đổi "trọng số tự động hoá" thì không có hiệu lực.

**Khắc phục:** một nguồn sự thật duy nhất. Khuyến nghị dùng **quy chế đã ban hành** (`config_release`), vì có phiên bản và kiểm toán được:
- Gửi đơn đọc trọng số từ release của bản nháp, rồi chụp vào `request_revision`.
- `request_type.risk_weight` chỉ là giá trị mặc định khi tạo release mới.
- JSON catalog chỉ dùng để khởi tạo dữ liệu.

Sửa L2 **sau** S1.

### L3 — TRUNG BÌNH: lãnh đạo cao nhất không gửi được yêu cầu

`hung.nguyen@eas.com` (BOD, có vai trò REQUESTER) là người dùng nghiệp vụ duy nhất không có `manager_id`. Mọi loại yêu cầu có tuyến bắt đầu bằng `DIRECT_MANAGER` (gần như tất cả) sẽ báo `Requester has no direct manager` → `409 ROUTE_CONFIGURATION_INVALID`.

Lỗi cùng họ là R07: người yêu cầu trùng một vị trí duyệt thì bị chặn gửi.

**Khắc phục:** cần chủ đầu tư chọn quy tắc. Khuyến nghị:
- với người không có quản lý: bỏ bước `DIRECT_MANAGER` và giữ các bước chức năng (Kế toán, Pháp chế…), ghi audit `ROUTE_STEP_SKIPPED_TOP_LEVEL`;
- hoặc chuyển sang một vị trí "Hội đồng quản trị" được cấu hình.

### L4 — TRUNG BÌNH: SoD chặn thay vì leo thang (R07)

`routing._validate_resolved_actors` từ chối khi người yêu cầu trùng một vị trí duyệt. Ví dụ: trưởng phòng Tài chính tự lập đề nghị chi thì không gửi được.

**Khắc phục:** thay bằng quản lý trực tiếp của người yêu cầu + audit (đã đề xuất trong kế hoạch auto-assignment).

### Các logic khác đã kiểm và **đúng**

- Rút đơn đóng phiên quy trình, bỏ qua các bước, đóng SLA (`service.py:2865-2925`).
- Mọi đường kết thúc đều đóng SLA (`SQL_CLOSE_SLA_STAGE` dùng ở 4 nơi).
- Outbox:
  - thuê theo lô `FOR UPDATE SKIP LOCKED`;
  - `DEAD` khi `attempts ≥ 4`;
  - thuê hết hạn thì nhả lại;
  - thông báo chống trùng (`ON CONFLICT (event_id, recipient_id)`).
- SLA: chống cảnh báo trùng (`UNIQUE(stage_id, kind)`, `ON CONFLICT DO NOTHING`).
- Phân tích (`/workspace/analytics`) giới hạn đúng phạm vi: nhân viên chỉ thấy đơn của mình, người duyệt phòng ban thấy phòng mình (`analytics._scope`).

## 4. Hiệu năng

| Đo | Trung vị / p95 |
|---|---|
| `SELECT 1` tới DB live | 249 / 261 ms (gần như toàn bộ là độ trễ mạng VN → Sydney) |
| Danh sách 50 hồ sơ | 250 / 297 ms |
| Phân loại NLP | 0,26 / 0,37 ms |
| XGBoost | 0,19 / 0,26 ms |

| # | Nhận xét | Khuyến nghị |
|---|---|---|
| P1 | Một lệnh gửi đơn chạy khoảng 15–25 câu SQL tuần tự trong một giao dịch, nên đặt máy chủ ở VN sẽ mất vài giây | **Đặt API cùng vùng DB** (hoặc chuyển DB sang Singapore). Đây là tối ưu lớn nhất; không cần sửa code |
| P2 | Worker poll mỗi 2 giây, mỗi vòng 3 giao dịch, kể cả khi rảnh | Tăng `--poll-seconds` lên 5–10, hoặc dùng `LISTEN/NOTIFY` của PostgreSQL |
| P3 | Chỉ mục đường nóng đầy đủ: `sla_open_due` (partial), `outbox_due`, `notification_inbox`, `approval_inbox`, `request_owner_updated`, `one_active_step`, `one_open_stage` | Giữ |
| P4 | 13 cột khoá ngoại chưa có chỉ mục (vd `approval_delegation.delegate_id`, `user_leave_and_trips.user_id`, `announcement_receipt.user_id`) | Thêm chỉ mục cho `delegate_id`, `user_leave_and_trips.user_id` (có truy vấn theo người). Các cột còn lại là bảng nhỏ, không cần |
| P5 | Nhiều file lớn: `workflow/service.py` 2.970 dòng, `views.py` 1.465 dòng, `App.jsx` 1.641 dòng | Tách theo miền (submit / approval / execution) khi tiếp tục phát triển; chưa gấp |

## 5. Cơ sở dữ liệu

### 5.1 Đánh giá chuẩn hoá

| Tiêu chí | Đánh giá |
|---|---|
| Khoá chính, khoá ngoại, khoá ngoại kép `(id, request_id)` | Tốt |
| Bảng quyết định / sự kiện chỉ-ghi-thêm (trigger, kể cả với role chủ sở hữu) | Tốt |
| Ràng buộc CHECK cho mọi trạng thái, mốc thời gian, tiền | Tốt |
| Chuẩn 3NF | Phần lõi đạt. Phần mở rộng có lặp dữ liệu (§5.2) |

### 5.2 Dữ liệu lặp / bảng thừa

| # | Nội dung | Đề xuất |
|---|---|---|
| T1 | `risk_weight`, `approval_level` lặp ở 5 bảng (`request_type`, `config_release`, `request`, `request_revision`, `workflow_instance`) + JSON catalog | Nguồn: `config_release`; bản chụp: `request_revision`. Bỏ ở `request` và `workflow_instance` (đọc qua revision) |
| T2 | Bộ luật AI ở 4 nơi: `ai_policy_version` (0 dòng), `ai_learning_job.compiled_policy`, `ai_system_state.applied_policy`, tệp `ai_service/data/active_enterprise_policy.json` | Nguồn: `ai_policy_version` (bản ACTIVE). Hai nơi kia chỉ tham chiếu id; tệp JSON chỉ là bộ đệm của dịch vụ AI |
| T3 | `workflow_categories` (di sản; SLA A=4h, B=24h, C=72h, **mâu thuẫn** với SLA trong quy chế) và 9 view tương thích (`departments`, `requests`, `roles`…) còn trong `eas` | Kiểm không còn code đọc, rồi chuyển sang `eas_deprecated` |
| T4 | Cột `app_user.username` (138 dòng, song song `email`) | Xoá theo expand → contract |
| T5 | Schema `eas_deprecated` | Chạy `scheduled/2026-11-17_drop_eas_deprecated_after_11.sql` đúng hạn **sau** T3 |
| T6 | `system_versions_changelog` trùng chức năng với `admin_event` nhưng không có chuỗi băm | Giữ làm "nhật ký đọc cho người", nhưng mỗi dòng nên lưu `admin_event.id` để truy được bằng chứng |
| T7 | `role` và CHECK `role IN (…)` trên `role_membership` cùng ràng buộc | Chấp nhận (thừa an toàn) |

### 5.3 Bảng / thành phần còn thiếu

| # | Thiếu | Phục vụ |
|---|---|---|
| M1 | `mock_hr.attendance` **chưa có trên live** (migration `database/mock_enterprise_sql/migrations/004_hrm_attendance.sql` có sẵn) | Logic "người duyệt / người thực hiện vắng mặt" đang tắt |
| M2 | Bảng duyệt kép cho xoá dữ liệu cá nhân (`privacy_case_approval`) | Four-eyes, Nghị định 13 |
| M3 | Cấu hình leo thang SLA (nhắc / tự chuyển, mức 2) | Quyết định D3 |
| M4 | Bảng bàn giao công việc (handover) | Quyết định D4 |
| M5 | Lịch làm việc / ngày lễ | SLA theo giờ làm việc |
| M6 | Job xuất `audit_checkpoint` (bảng có, 0 dòng) | Neo kiểm toán ngoài |

### 5.4 Dữ liệu live sai lệch

| # | Phát hiện | Mức | Xử lý |
|---|---|---|---|
| D1 | **3 hồ sơ kẹt vĩnh viễn**: `REQ-2026-0002`, `REQ-2026-0009`, `REQ-2026-0026` ở `PENDING_APPROVAL`, bước trước `APPROVED`, bước sau `WAITING`, **không có bước `ACTIVE`**. Không ai thao tác được. Chỉ có 2 sự kiện audit/hồ sơ, nghĩa là dữ liệu seed chèn thẳng, không qua dịch vụ | Cao (demo sẽ lộ) | Kịch bản sửa: kích hoạt bước kế + mở SLA + audit; hoặc huỷ hẳn các hồ sơ seed này |
| D2 | `REQ-2026-0011` đã `CANCELLED` nhưng còn 1 chặng SLA mở (seed) | Thấp | Đóng chặng |
| D3 | 0 người giữ vai trò AUDITOR | Cao (không demo được kiểm toán) | Gán cho tài khoản kiểm soát riêng |
| D4 | 4 loại lệch trọng số DB ↔ quy chế | Trung bình | Xử lý cùng L2 |
| D5 | Hồ sơ seed không có chuỗi audit đầy đủ (không có `REQUEST_SUBMITTED`) | Thấp | Ghi chú "dữ liệu mẫu" hoặc làm lại seed qua API |

## 6. Thứ tự xử lý đề xuất

| Ưu tiên | Việc | Người làm | Ghi chú |
|---|---|---|---|
| 1 | S1: thu hồi `requests_workflows:U` của APPROVER + kiểm `POLICY_ADMIN` ở máy chủ + test | Dev + bạn chạy SQL | Làm ngay |
| 2 | S2, S3: migration xoá 16 policy `anon_auth_read_*`; cố định `search_path`, thu hồi EXECUTE của PUBLIC | DBA soạn, bạn chạy | Có kèm rollback |
| 3 | D1–D3: sửa dữ liệu demo (3 hồ sơ kẹt, SLA mở, gán AUDITOR) | DBA soạn, bạn chạy | Trước buổi bảo vệ |
| 4 | L1: AI tự duyệt nhiều bước | Dev + test | |
| 5 | L2 + T1: một nguồn trọng số rủi ro | Dev + DBA | Sau S1 |
| 6 | S4–S6: hợp nhất cổng (web qua gateway, header admin, gỡ `/ai/`) | DevOps | |
| 7 | M1: chạy migration chấm công trên live | Bạn chạy SQL | |
| 8 | L3, L4: quy tắc cho cấp cao nhất và SoD | Chủ đầu tư chốt, Dev làm | |
| 9 | S7, S8, P2, P4, T2–T6 | Theo lịch | |

> Theo quy ước dự án: mọi thay đổi DB live do bạn chạy trong Supabase SQL Editor; mọi kiểm thử ghi chạy trên bản sao local. Báo cáo này không thay đổi code hay dữ liệu.

## 7. Trạng thái xử lý (cập nhật 04/11/2026)

Thiết kế chi tiết: [THIET_KE_SCHEMA_EAS_V2.md](THIET_KE_SCHEMA_EAS_V2.md).

Các nhãn trạng thái dùng trong bảng:

- **Code**: đã sửa trong mã nguồn và có test.
- **M14**/**M15**: nằm trong migration 14 (đã chạy trên live) hoặc 15 (gộp bảng trùng, giữ dữ liệu). Bạn chạy trên Supabase.
- **Lệnh**: `python manage.py repair_workflow_consistency --apply`.
- **Chưa**: còn mở.

| Mã | Trạng thái | Chi tiết |
|---|---|---|
| S1 | Code + M14 | `_require_writer` đòi vai trò `POLICY_ADMIN` cùng quyền module. M14 thu hồi `requests_workflows` update/delete của vai trò nghiệp vụ |
| S2 | M14 | Xoá mọi policy cấp cho `anon`/`authenticated`/`public` trong `eas` |
| S3 | M14 | Hàm SECURITY DEFINER: `search_path = pg_catalog, eas`, thu hồi EXECUTE của PUBLIC |
| S4 | Đã sửa 05/11 | Hai cổng web có giới hạn tần suất riêng: đăng nhập / đổi / đặt lại mật khẩu 5 lần/phút/IP, upload 10 lần/phút, API 20 lần/giây |
| S5 | Đã sửa 05/11 | `web_admin/nginx.conf` có đủ HSTS, Permissions-Policy, `server_tokens off`, `autoindex off`, `object-src 'none'`, chặn file nhạy cảm |
| S6 | Đã sửa 05/11 | Gateway gỡ `/ai/*`, swagger AI và route thừa `/api/v1/mock/*`; gateway không còn phụ thuộc AI |
| S7 | Đã sửa 05/11 | Nâng lên `paddlepaddle 3.3.1`, `paddleocr 3.7.0`, `paddlex 3.7.2`, `protobuf 5.29.6`; bỏ `imgaug`. Image nâng `pip 26.2`, `setuptools 84.1.0`. `pip-audit` trên `python:3.11-slim` sạch. OCR thử thật trong container: đọc đúng hoá đơn mẫu, độ tin cậy 0,998. `ENABLE_PADDLE_OCR=false` vẫn build được image gọn dùng Gemini dự phòng |
| S8a | Đã sửa 05/11 | OCR từ URL: không theo redirect, kiểm tra lại IP đã kết nối (chống DNS rebinding), giới hạn 10 MB khi đọc dần |
| S8b | Đã sửa 05/11 | Tìm kiếm quản trị thoát `%`, `_`, `\` (`ESCAPE`) |
| S8c | Đã sửa 05/11 | Mobile ghim `http: 1.6.0`, `flutter_lints: 6.0.0` |
| S8d | Đã sửa 05/11 | Xoá `src/supabase.js` và `@supabase/supabase-js` khỏi hai web |
| S8e | Đã sửa 05/11 | Gỡ dịch vụ Elasticsearch (tắt bảo mật, không code nào dùng) |
| S8f | Đã sửa 05/11 | Worker xoá nội dung phản hồi khi hết `expires_at` và xoá dòng khi hết `tombstone_until` (đúng `guard_idempotency`) |
| L1 | Code + M14 | Bỏ `UNIQUE(instance_id, assignee_id)`, thay bằng trigger chỉ áp cho người thật. AI tiếp quản bước gặp xung đột thì ghi `STEP_TAKEOVER_CONFLICT`, không trả lỗi 500 |
| L2 | Code (+ M15) | Nguồn duy nhất: `request_type`. Bản chụp: `request_revision`. Gửi đơn đọc trọng số từ DB, không đọc JSON. M15 xoá cột trùng |
| L3 | Code | Lãnh đạo cao nhất: `TOP_LEVEL_FALLBACK` hoặc `TOP_LEVEL_SKIPPED`. Khai báo người duyệt thay bằng `database/data_fixes/2026-11-04_top_level_approver_binding.sql` |
| L4 | Code | Người gửi trùng người duyệt: chuyển lên quản lý (`SOD_ESCALATED`). Mọi điều chỉnh ghi trong `route_adjustments` của audit |
| M1 | Code (một phần) | Khi chưa có `mock_hr.attendance`, phát hiện vắng mặt dùng đơn nghỉ đã duyệt (`user_leave_and_trips`). Bảng chấm công vẫn cần chạy trên live |
| M2–M5 | M14 + M15 | `privacy_case_approval`, `sla_escalation_policy`, `business_holiday`. Bàn giao việc (M4) gộp vào `approval_delegation` ở M15 (cột `scope`). Worker SLA chưa đọc các bảng này |
| M6 | Chưa | Job xuất `audit_checkpoint` |
| D1, D2 | Lệnh | Bản sao local: sửa 4 hồ sơ, quét lại báo 0 |
| D3 | Chưa | Bạn gán vai trò AUDITOR qua màn hình quản trị |
| D4 | Code | Xử lý cùng L2 |
| D5 | Chấp nhận | Dữ liệu mẫu. Hồ sơ đã sửa có audit `DATA_REPAIR_*` |
| T1 | Code + M15 | Xem L2. M15 bỏ trọng số ở `request`, `workflow_instance`, `config_release`; giá trị cũ lưu ở `eas_archive.dropped_column_value` |
| T2 | Giữ nguyên | `ai_policy_version` đã là nguồn duy nhất trong code |
| T3, T4, T5 | M15 | Bỏ 9 view bí danh. `workflow_categories` và schema `eas_deprecated` dời sang `eas_archive`. `app_user.username` bỏ, giá trị được lưu. Không xoá dữ liệu |
| T6 | Code + lệnh + M15 | `system_versions_changelog` gộp vào `admin_event` (lệnh `import_legacy_changelog`); bỏ trigger ghi đúp `trg_after_mock_api_toggle` |
| P4 | M14 | Thêm chỉ mục cho khoá ngoại được truy vấn theo người |

Kiểm thử sau khi sửa:

- `manage.py test api_core`: 315/315 đạt.
- `tests/run_tests.py`: 153 ca đạt, 1 bỏ qua.
- `ruff`: sạch.
- Trên bản sao local dựng đúng hiện trạng live, chạy 14 → import → 15 → rollback → 15 cùng smoke. Tất cả đạt; rollback trả đúng giá trị cũ (so checksum).
