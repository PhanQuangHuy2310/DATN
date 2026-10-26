# EAS / UC17 — Quản lý người dùng, API và ma trận phân quyền

**Căn cứ:** `01_SRS_v2.docx`, `02_Phan_tich_thiet_ke_v2.docx`, `03_Du_lieu_va_API_v2.docx`, sơ đồ `02_USE_CASE`, `04_STATE_MACHINE`, `06_SEQUENCE`, và TC007–TC009, TC023–TC026 trong kế hoạch kiểm thử v2.

## 1. Phạm vi đã triển khai trong bản cập nhật

| Hạng mục | UI | Backend | Nguyên tắc bảo vệ |
| --- | --- | --- | --- |
| User | Tạo/sửa/khóa, tìm kiếm theo tên, lọc theo role và trạng thái, xem chi tiết | GET list/detail, POST, PATCH, DELETE-soft | Chỉ GLOBAL+ALL OPS_ADMIN, reason >=10, idempotency, revision, audit, security_epoch |
| Phòng ban | Tạo/sửa/vô hiệu hóa, chọn phòng ban cha từ danh mục có tìm kiếm | GET list/detail, POST, PATCH, DELETE-soft | Không tạo chu kỳ, không vô hiệu phòng đang được sử dụng |
| Role membership | Cấp/sửa thời hạn/thu hồi, chọn user/phòng ban/loại yêu cầu bằng tên | GET list/detail, POST, PATCH, DELETE-revoke | Role allowlist, scope GLOBAL/DEPARTMENT và ALL/ONE rõ ràng, không tự sửa quyền, auth_version |
| Loại yêu cầu P0 | Xem, vô hiệu hóa theo quyền | GET list/detail và PATCH/DELETE-soft | Không tạo loại P0 tùy ý (LEAVE, ACCESS, EQUIPMENT) |
| Ma trận quyền | 7 thẻ role, quyền đọc/ghi/giới hạn và UC | GET `/api/v1/admin/access-matrix` | Chỉ GLOBAL+ALL OPS_ADMIN; dữ liệu đặc tả, không thay thế authorize runtime |
| Quản lý API | 40 hợp đồng phương thức/endpoint, tìm kiếm, lọc domain, method, role, phân trang, kiểm tra readiness | GET `/api/v1/admin/api-catalog` | Chỉ GLOBAL+ALL OPS_ADMIN; danh mục chỉ đọc, không cấp token hay thay đổi route |

**Phân biệt quan trọng với đặc tả:** SRS P0 UC17 nêu danh tính vận hành bằng công cụ quản trị có kiểm soát (`identity_import --dry-run/--apply`) và không có API-key CRUD động. UI CRUD đang có từ phiên bản trước là phần mở rộng phục vụ đồ án, không thay thế lệnh import nguyên tử cho dữ liệu nhiều user. Bộ API catalog mới không cho phép tự ý bật/tắt endpoint, tạo token, thay đổi policy hoặc gọi proxy HTTP tùy ý vì không có hợp đồng SRS/DB/audit tương ứng.

## 2. Ma trận phân quyền P0

| Role | Đọc | Ghi | Guard bắt buộc |
| --- | --- | --- | --- |
| REQUESTER | Hồ sơ sở hữu | Draft, submit, resubmit, cancel | Owner, state, no self-approval |
| APPROVER | Hồ sơ được gán | approve / reject / needs info | ACTIVE step, scope, SoD |
| EXECUTOR | Công việc được giao | claim, issue, submit execution | Current attempt và assignee |
| ACCEPTOR | Hồ sơ cần nghiệm thu | accept / rework | Lifecycle C và khác executor thực tế |
| POLICY_ADMIN | Cấu hình, audit cùng loại | draft/validate/publish | Không mặc định được đọc nội dung yêu cầu |
| OPS_ADMIN | Metadata điều phối | reassign, outbox replay | Scope department/type, reason, không quyết định thay |
| AUDITOR | Hồ sơ/audit/report theo scope | Không ghi nghiệp vụ | Không sửa role hoặc audit |

**Sự kiện quyền:** user inactive -> không truy cập; quyền mới chỉ có hiệu lực theo `security_epoch`; quyền lịch sử không hồi tố quyết định hợp lệ. `DEPARTMENT` chỉ đúng department_id, không tự bao gồm phòng con. `GLOBAL/ALL` phải khai báo tường minh. Nhiều role không bỏ guard SoD.

## 3. API quản trị mới / được mở rộng

| Method | Endpoint | Ý nghĩa |
| --- | --- | --- |
| GET | `/api/v1/admin/users?limit=20&offset=0&q=an&active=true&role=APPROVER` | Search, filter, total và next_offset theo PostgreSQL |
| GET | `/api/v1/admin/users/{uuid}` | Thông tin user + role membership đã cấp, không có password/hash |
| POST | `/api/v1/admin/users` | Thêm người dùng (lý do bắt buộc, tạm password hợp lệ) |
| PATCH | `/api/v1/admin/users/{uuid}` | Cập nhật, khóa/mở, cấp lại mật khẩu tạm (expected_revision) |
| DELETE | `/api/v1/admin/users/{uuid}` | Vô hiệu hóa, không xóa audit/history |
| GET | `/api/v1/admin/memberships?q=APPROVER&state=ACTIVE` | Lọc role theo hiệu lực |
| POST/PATCH/DELETE | `/api/v1/admin/memberships[/{uuid}]` | Gán, cập nhật hoặc thu hồi quyền |
| GET | `/api/v1/admin/departments?q=IT` | Tìm phòng ban cho ô chọn giao diện |
| GET | `/api/v1/admin/request-types` | Danh mục loại yêu cầu |
| GET | `/api/v1/admin/api-catalog` | Danh mục phương thức, chức năng, role, scope và UC (read-only) |
| GET | `/api/v1/admin/access-matrix` | Ma trận quyền theo SRS v2 (read-only) |

### Phản hồi list

```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0,
  "next_offset": null
}
```

Mọi câu lệnh ghi có `Idempotency-Key`, `reason` từ 10 ký tự, và khi cập nhật/xóa cần `expected_revision` lấy từ GET. Vi phạm role -> 403, không tìm thấy -> 404, payload sai -> 422, revision cũ -> 409. Không có endpoint DELETE vật lý user.

## 4. UX bám giao diện quản trị Stitch

- Sidebar nhóm quản trị, trang quản trị user riêng và API riêng, thẻ tổng quan, bảng dữ liệu nhiều cột và dạng card khi màn nhỏ.
- Tìm kiếm và phân trang **phía server** cho user/departments/role memberships; filter active/role/effectiveness; không tải toàn bộ user về trình duyệt để lọc.
- Khi nhập user/manager/department/type dùng ô tìm tên và selector; không bắt người dùng nhớ UUID. Với danh mục >100 bản ghi, nhập tên để truy xuất chính xác.
- Hiển thị chi tiết user gồm các lần cấp quyền kể cả đã thu hồi để truy vết; không hiển thị password/hash.
- Password có nút Hiện/Ẩn, giới hạn 15–128 ký tự; Backend vẫn kiểm chính sách.
- Khi đổi trang, component phân trang tự cuộn đến bảng. Phân trang API là client-side trên *40 hợp đồng cố định*, không phải dữ liệu nghiệp vụ.
- Giám sát API: đọc trạng thái readiness thật; không hiển thị số liệu giả.

## 5. Kiểm thử và giới hạn

- Đã chạy: `python verify_uc17_static.py` — PASS (catalog, 7 role, parameterized SQL filters, khóa truy cập).
- Đã chạy: `node --test e2e/*.test.mjs` — 15/15 PASS.
- Đã chạy: kiểm tra cú pháp Python và 15 file JS/JSX — PASS.
- **Chưa xác nhận:** Django integration tests với PostgreSQL/Supabase thật, npm Vite production build, E2E chạy qua trình duyệt, import/dry-run khối lượng lớn. Tại môi trường đóng gói thiếu Django/psycopg và npm cache thiếu package để cài bằng `npm ci --offline`.
- Các lỗi 500 đã từng xuất hiện ở Requests/Notifications/Reports cần tiếp tục kiểm tra riêng trên Supabase máy bạn. Patch UC17 này không tự thay đổi những truy vấn nghiệp vụ đó.
- Không thay schema DB, không chạy migration, không sửa credential hoặc .env.
