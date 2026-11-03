# Kế hoạch: Học quy định AI đáng tin cậy, thông báo cập nhật và khắc phục phase 0–5 quản trị

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-11-03-02 |
| Ngày mở | 03/11/2026 |
| Trạng thái | ACTIVE |
| Liên quan | EAS-PLAN-2026-11-03-01 (dọn bảng, tách admin), roadmap `2026-11-03_admin_9_features_roadmap.md` |

## 1. Yêu cầu của chủ dự án

1. Hệ thống và AI hoạt động đúng.
2. AI học xong **và** áp dụng quy định mới thì mới mở khoá đăng nhập.
3. Sau cập nhật gửi thông báo cho người dùng: đã cập nhật gì; nếu đổi quy trình thì hướng dẫn thao tác theo quy trình mới.
4. Tối ưu, tăng tốc AI mà không đổi chi phí.

## 2. Hiện trạng (rà soát 03/11/2026)

| # | Vấn đề | Bằng chứng |
|---|---|---|
| H1 | Học AI chạy bằng `threading.Thread` trong tiến trình Django, chỉ `sleep` rồi ghi tiến độ; runserver reload là luồng chết, `client_maintenance_lock` kẹt `true` mãi | `regulations_ai.py:218`; live kẹt APPLYING 75% từ 22:13:59 UTC |
| H2 | "Học" không thay đổi hành vi AI: không trích luật, không nạp sang ai_service | worker chỉ sleep |
| H3 | Trigger DB `fn_after_regulation_versioning` tự bật khoá 45% và ghi lịch sử; code ứng dụng cũng ghi lịch sử → khoá không có người mở, lịch sử ghi đôi | `supabase/migrations/20261103_admin_full_upgrade.sql:755` |
| H4 | Module quản trị mới đọc/ghi bộ bảng song song (`eas.users`, `roles`, `role_permissions`, `departments`, `request_templates`, `workflow_categories`, `requests`) → tạo user không đăng nhập được, đổi quyền không có tác dụng; 6 API 500 sau migration 11 | `org_users_rbac.py`, `workflows.py`, `analytics.py` |
| H5 | Cổng admin mất đường vào `IdentityAdmin`, `PolicyWorkspace`, `AiPolicyAdmin` | `App.jsx:919-958` |
| H6 | `supabase/migrations/20261103_admin_full_upgrade.sql` cấp `GRANT ALL` cho anon/authenticated | dòng 984–991 |
| H7 | AUDITOR tạo được user; thao tác ghi mới không audit | `org_users_rbac.py:202` |
| H8 | `maintenance.py` query DB mỗi request (+~300ms), nuốt lỗi, làm 2 test fail | `api_core/maintenance.py` |
| H9 | ruff 32 lỗi + 9 file format; ESLint 89 lỗi | gate |
| H10 | Live chưa chạy migration 08/09/10 (dat) dù code đã dùng | `ai_policy_version`, `approval_delegation` không tồn tại |
| H11 | ai_service: endpoint `async def` gọi sklearn/xgboost đồng bộ (chặn event loop), không cache, api_core tạo HTTP client mới mỗi lần gọi | xem bước 6 |

## 3. Thiết kế

### 3.1 Học quy định = công việc có lease (thay thread)
- Bảng `eas.ai_learning_job` (QUEUED → RUNNING → APPLIED | FAILED), `lease_until`, `heartbeat_at`, `attempts`, `snapshot` (bộ quy định đã chụp), `compiled_policy`, `diff`, `error`.
- Khoá đăng nhập **suy ra từ job**: đang có job QUEUED/RUNNING còn lease → khoá. Không còn cờ boolean có thể kẹt.
- Bất kỳ tiến trình nào (worker, hoặc API khi có request) cũng có thể nhận job hết lease và chạy lại (idempotent). Quá số lần thử → FAILED: giữ nguyên bộ luật cũ đang áp dụng, mở khoá, báo admin.
- Các bước: SNAPSHOT (chụp quy định + hash) → LEARN (trích luật tất định từ văn bản tiếng Việt: ngưỡng tiền, số ngày, phân loại A/B/C, "bắt buộc duyệt", "tự động") → APPLY (đẩy bộ luật sang ai_service `/ai/policy/rules`, đọc lại xác nhận đúng phiên bản, chạy ca kiểm thử vàng qua engine) → COMMIT (một transaction: đặt phiên bản đang áp dụng, lưu bộ luật hiệu lực, ghi changelog, tạo thông báo, mở khoá).
- Trigger DB chỉ còn tính số phiên bản (BEFORE) + ghi lịch sử (AFTER); bỏ phần bật khoá/changelog trong trigger; code ứng dụng thôi ghi lịch sử trùng.

### 3.2 Thông báo cập nhật + hướng dẫn quy trình mới
- `eas.system_announcement` (phiên bản, tiêu đề, tóm tắt, `changes` jsonb, `guidance` jsonb) + `eas.announcement_receipt` (user, read_at).
- Nội dung sinh tất định từ diff phiên bản: quy định thêm/sửa/gỡ; luật AI thay đổi (ngưỡng, bắt buộc duyệt tay, tự duyệt). Nếu luật đổi luồng xử lý → bước hướng dẫn cụ thể theo loại yêu cầu.
- Client: sau đăng nhập hiện hộp "Hệ thống vừa cập nhật" (đánh dấu đã đọc), xem lại trong Thông báo.

### 3.3 Quản trị dùng một nguồn dữ liệu
- Viết lại `org_users_rbac.py`, `workflows.py`, `analytics.py` trên `app_user`, `role_membership`, `department`, `role_module_permission`, `user_permissions`, `request_type`, `config_release`, `request`. Ghi `admin_event`, khoá `security_epoch`.
- Khôi phục đường vào IdentityAdmin / PolicyWorkspace / AiPolicyAdmin trên cổng admin.

### 3.4 Tối ưu AI không đổi chi phí
- ai_service: endpoint suy luận CPU chuyển `def` (threadpool, không chặn event loop), nạp model khi khởi động (warm-up), cache LRU kết quả cho đầu vào giống hệt; tóm tắt Gemini cache theo nội dung (giảm, không tăng chi phí).
- api_core: tái sử dụng kết nối HTTP tới ai_service (keep-alive), timeout ngắn hợp lý.

## 4. Work breakdown

| # | Hạng mục | Trạng thái |
|---|---|---|
| 1 | Kiểm thử 08/09/10 trên bản sao (sau migration 11), sửa xung đột nếu có | TODO |
| 2 | Migration 12: job học AI, thông báo, sửa trigger quy định, trạng thái hiệu lực | TODO |
| 3 | Backend: job runner (lease), trích luật, áp dụng + xác nhận ai_service, thông báo; maintenance suy ra từ job (cache ngắn) | TODO |
| 4 | Viết lại module quản trị trên dữ liệu lõi; quyền AUDITOR; audit | TODO |
| 5 | Frontend: hộp thông báo cập nhật + hướng dẫn; khôi phục màn hình lõi; trang AI hiển thị job thật | TODO |
| 6 | Tối ưu ai_service + ai_client | TODO |
| 7 | Gỡ GRANT anon khỏi file supabase; dọn ruff/ESLint; test | TODO |
| 8 | Kiểm chứng trên bản sao live + chạy thật (ai_service + backend + trình duyệt) | TODO |
| 9 | Changelog, đóng kế hoạch | TODO |

## 5. Nhật ký tiến trình

- 03/11/2026: rà soát xong, ghi hiện trạng mục 2, thiết kế mục 3.
- #1 DONE: 08→09→10 chạy sạch trên bản sao sau migration 11. Phát hiện: data fix `2026-11-03_org_structure_and_passwords.sql` chạy sau 08 sẽ đặt mật khẩu cho `ai.system@eas.com` → đã loại tài khoản hệ thống khỏi script; `find_user` chặn đăng nhập tài khoản `is_system_account`.
- #2 DONE: `database/migrations/12_ai_learning_jobs_and_announcements.sql` + rollback (dời bảng sang schema `eas_rollback_12_<thời điểm>`). Kiểm thử bản sao: chạy, chạy lại, rollback, chạy lại, rollback 2 lần: sạch. Sửa quy định không còn tự khoá; lịch sử ghi 1 lần. Live đang kẹt 75% → migration xếp job học lại.
- #3 DONE (backend): `api_core/workflow/ai_learning.py` (trích luật tất định, job lease, áp dụng + kiểm thử vàng trên ai_service, thông báo, khoá suy ra từ job cache 3s), `maintenance.py` (job-based, legacy fallback, hết nuốt lỗi), `regulations_ai.py` viết lại (transaction, audit `admin_event`, AUDITOR chỉ đọc, xếp job), `ai_policy.py` (kích hoạt luật tay → job; `active_document` = bộ luật hiệu lực), `announcement_views.py` + URL `/api/v1/announcements`, worker gọi `run_pending`. Test: `api_core/tests/test_ai_learning.py` (11). Django 437 OK.
- E2E DONE (Postgres Docker `eas-pg-e2e` :55432 + ai_service :8101 + Django :8100, script `%TEMP%/claude/e2e_flow.py`): sửa REG-002 → nhân viên bị 503 kèm bước → mở khoá sau ~1s → thông báo + hướng dẫn; AI tắt → thử 3 lần (~71s) → FAILED, mở khoá, giữ luật cũ, chỉ admin nhận cảnh báo; bật lại AI + `POST /admin/ai-engine/retrain` → áp dụng v1.2.
- Lỗi tìm thấy + sửa: live có bộ đếm 1.0 nhưng target "2.1" → migration 12 chuẩn hoá `global_major/minor` + target theo phiên bản lớn nhất thực có (không lùi số). Chạy lại 12 vẫn idempotent.
- #4 DONE: `org_users_rbac.py`, `workflows.py`, `analytics.py` viết lại trên bảng lõi. Ghi người dùng/vai trò qua `service.mutate` (kiểm tra, mật khẩu argon2, idempotency UUID, audit); RBAC ghi `role_module_permission`/`user_permissions` + `lock_security` + audit + epoch; AUDITOR chỉ đọc (403 khi ghi). Quy trình = `request_type` + `config_release` (đổi vòng đời/biểu mẫu/định tuyến → 409 `RELEASE_REQUIRED`/`LIFECYCLE_REQUIRES_NEW_RELEASE`); `automation_weight` ↔ `risk_weight`. Analytics bỏ số liệu giả, tính từ `eas.request`. Sửa thêm lỗi cũ `service.SELECT_BY_ID_SQL` (đọc cột không tồn tại, sai thứ tự cột request-types → 500/sai revision). Leave-trip nhận `CANCEL_TODAY`/`reason` như frontend gửi. Kiểm thử API thật (`%TEMP%/claude/e2e_admin.py`): tất cả 200/đúng mã lỗi. Test `test_admin_core_modules.py` (6). Django 443 OK, ruff sạch.
- #7 một phần: gỡ GRANT anon/authenticated trong `supabase/migrations/20261103_admin_full_upgrade.sql` (+REVOKE). Live đã sạch (kiểm tra chỉ đọc: anon/authenticated 0 quyền, RLS bật mọi bảng).
- #5 DONE: `SystemUpdates.jsx` (hộp "Hệ thống đã cập nhật" sau đăng nhập, xem lại ở Thông báo); overlay khoá chỉ theo `client_maintenance_lock` (trước đây trạng thái ERROR khoá người dùng mãi); khôi phục IdentityAdmin (`identity`), PolicyWorkspace (`release-workspace`), AiPolicyAdmin (`ai-rules`) thành mục menu riêng; trang AI: bỏ bộ mô phỏng giả, gọi AI thật qua `POST /admin/ai-engine/test`, hiện lịch sử job; OrgChart bỏ tên/số liệu cứng. ESLint 89 → 0 lỗi (a11y modal/label, state-in-effect), `npm test` 64 pass, build client + admin OK.
- TIẾP: #6 tối ưu AI, kiểm tra trình duyệt, changelog.
