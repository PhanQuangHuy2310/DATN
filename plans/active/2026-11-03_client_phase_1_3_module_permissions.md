# Kế hoạch: Cổng nhân viên Phase 1–3 — giao diện theo quyền module do admin cấp

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-11-03-03 |
| Ngày mở | 03/11/2026 |
| Trạng thái | ACTIVE |
| Đặc tả | Yêu cầu "Client Phase 1/2/3" của chủ dự án (03/11/2026) |
| Tài liệu sản phẩm | `docs/CHUC_NANG_UI_VA_PHAN_QUYEN.md` (cập nhật theo kế hoạch này) |

## 1. Quyết định kiến trúc (khác đặc tả, có lý do)

| Đặc tả | Làm | Lý do |
|---|---|---|
| Trình duyệt gọi Supabase (`supabase.schema('eas')`, Realtime) | Trình duyệt chỉ gọi API Django; backend đọc `eas` | AGENTS.md: trình duyệt không bao giờ nói chuyện với Supabase; migration 13 đã thu hồi quyền `anon`/`authenticated` |
| Ghi trực tiếp `eas.requests`, đổi `current_stage` | Dùng API quy trình thật (`request`, FSM, SoD, audit); 5 giai đoạn là cách hiển thị của các trạng thái thật | `eas.requests` chỉ là view tương thích; ghi thẳng bỏ qua phê duyệt, SoD, nhật ký |
| Khoá khi `sync_status !== 'COMPLETED'` | Khoá khi `client_maintenance_lock` (suy ra từ job AI đang mở) | AI học lỗi → trạng thái ERROR nhưng đã mở khoá, giữ luật cũ; khoá theo `sync_status` sẽ khoá nhân viên vĩnh viễn |
| `users` là module chỉ-admin | `users` được admin cấp cho nhân viên (đặc tả); 4 module `permissions`, `ai_engine`, `api_management`, `system_versions` không bao giờ cấp cho nhân viên | Theo đặc tả |
| Quyền module U/D trên `requests_workflows` vừa là "cấu hình mẫu" vừa là "sửa/huỷ hồ sơ của mình" | U/D = cấu hình mẫu (Tab 3); sửa/huỷ hồ sơ của mình theo chủ hồ sơ + trạng thái | Sửa lỗi nhân viên không thấy nút Sửa/Huỷ (docs mục 3) |

## 2. Hạng mục

| # | Hạng mục | Trạng thái |
|---|---|---|
| 1 | Backend: kiểm tra quyền module dùng chung (`require_module`), API `/api/v1/workspace/*` dùng lại logic quản trị | TODO |
| 2 | Backend: analytics theo phạm vi (cá nhân / phòng ban / toàn công ty), `/auth/me` thêm mã NV, chức danh, mã phòng, trạng thái làm việc | TODO |
| 3 | Backend: duyệt xong nghỉ phép/công tác/đi muộn/về sớm → ghi `user_leave_and_trips` | TODO |
| 4 | Frontend: menu nhân viên theo 5 module, header 5 thành phần, `ClientPermissionGuard`, làm mới quyền định kỳ | TODO |
| 5 | Frontend: Yêu cầu & Quy trình 3 tab; Tổng quan, Sơ đồ công ty, Người dùng, Quy định dùng lại màn hình admin qua `apiBase` | TODO |
| 6 | Kiểm thử: unit, build, 5 kịch bản liên thông trên bản sao live | TODO |
| 7 | Cập nhật docs, changelog | TODO |

## 3. Nhật ký tiến trình

- 03/11/2026: mở kế hoạch.
