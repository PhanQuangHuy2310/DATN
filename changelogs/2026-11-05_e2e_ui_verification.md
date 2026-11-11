# Kiểm thử E2E trên giao diện thật (05/11/2026)

## Môi trường

Kiểm thử chạy trên bản sao local `m17test` (container `eas-pg-e2e`, cổng `127.0.0.1:55432`), không chạm Supabase live. Stack gồm:

- API Django: cổng 8000;
- Mock Systems API: cổng 8100;
- worker;
- AI service: cổng 8001;
- `web_client` (Vite): cổng 5173;
- `web_admin` (Vite): cổng 8081.

Mọi thao tác chạy bằng Playwright, đăng nhập bằng phiên thật của từng vai trò.

## Kết quả

| Nhóm | Kết quả |
|---|---|
| Hai cổng cùng template | Đạt. Cùng khung (sidebar, topbar, user pill), cùng token `--ds-*`, cùng font, cùng kiểu menu |
| RBAC | Đạt. Menu khác nhau theo vai trò. Nhân viên không đăng nhập được cổng quản trị. API trả 403 cho nhân viên ở các route `admin/*` và `ops/*`. Nhân viên không đọc được hồ sơ của người khác (404) |
| Tạo yêu cầu qua giao diện | Đạt. Menu có 12 nhóm và 61 biểu mẫu. Biểu mẫu WFH hiện đúng nhãn. Có hộp thoại xác nhận trước khi gửi |
| Quy trình C xen kẽ | Đạt. Chuỗi: yêu cầu bổ sung → gửi lại (2 phiên bản) → duyệt cấp 1 → duyệt cấp 2 → nhận việc → nộp kết quả (bắt buộc minh chứng) → yêu cầu làm lại → nhận lại việc → nộp lần 2 → nghiệm thu → hoàn tất. Chuỗi hash audit kiểm tra PASS (14 sự kiện) |
| Tranh chấp đồng thời | Đạt. Rút đơn và duyệt cùng lúc: chỉ 1 bên thắng. Duyệt 2 lần cùng `Idempotency-Key`: chỉ ghi 1 quyết định |
| Mượn tài nguyên | Đạt. Đơn được duyệt trước thắng; đơn sau tự bị từ chối, kèm thông báo lý do. Gửi khi phòng đã có người giữ: 409 `RESOURCE_UNAVAILABLE`. BGĐ được ưu tiên: người đang giữ phòng bị thu hồi |
| AI | Đạt. Trợ lý trong biểu mẫu trả kết quả phân loại và điểm rủi ro. Đơn WFH (rủi ro 1) được AI tự duyệt (`ai.system`) |
| Quy định → AI học lại | Đạt. Admin thêm quy định "WFH phải duyệt thủ công" → AI học 4 bước (SYNCING → LEARNING → APPLYING → COMPLETED), khoá cổng nhân viên trong lúc học, gửi thông báo. Đơn WFH mới chờ quản lý duyệt thủ công. Gỡ quy định → AI học lại → WFH lại được tự duyệt |

## Lỗi phát hiện và đã sửa

1. **Danh sách và chi tiết hồ sơ trả 500.**
   - Nguyên nhân: `api_core/workflow/views.py` đọc `r.amount_vnd`, nhưng bảng `eas.request` không có cột này.
   - Sửa: đổi thành `COALESCE(v.amount_vnd, r.draft_amount_vnd)`.
2. **101 trường biểu mẫu (35 loại) hiện cùng nhãn "Thông tin bổ sung".**
   - Nguyên nhân: `resolve_field_labels` dùng chuỗi `a or b`, nên mục trong `catalog_v2` (không có `field_labels`) che mất nhãn ở `plan_types.json`.
   - Sửa: gộp nhãn từ mọi nguồn; thêm nhãn cho `leave_kind`.
   - Test: `FieldLabelTests`.
3. **Trợ lý AI tự đổi loại biểu mẫu và xoá dữ liệu đã nhập.**
   - Biểu hiện: bấm "Gợi ý & đánh giá rủi ro" thì biểu mẫu WFH bị đổi sang ACCESS.
   - Sửa: AI chỉ gợi ý; người dùng bấm "Chuyển sang biểu mẫu này" mới đổi. Điểm rủi ro nay dùng quy trình và trọng số thật của loại yêu cầu, không còn gán cứng.
   - Test: thêm vào `e2e/client-refactor.test.mjs`.
4. **Modal quản trị không có CSS.**
   - Biểu hiện: ở các trang Quy định, Quản lý API và Phiên bản hệ thống, modal hiện trơn giữa trang.
   - Nguyên nhân: lớp `eas-modal-*` chưa từng có CSS.
   - Sửa: thêm CSS vào `design-system.css`, dùng token sẵn có.
5. **Tải lại trang trong lúc AI học báo "Không thể kết nối hệ thống".**
   - Sửa: mã `SYSTEM_UNDER_MAINTENANCE` đưa người dùng về trang đăng nhập; trang này đã có thanh tiến độ học.

## Điểm cần chủ dự án xử lý (chưa sửa)

- **Lãnh đạo cao nhất không gửi được loại chỉ có bước `DIRECT_MANAGER`** (ví dụ `ROOM_BOOKING`, `WFH_REQ`).
  - Hệ thống trả 409 `ROUTE_CONFIGURATION_INVALID`. Đây là hành vi đúng theo thiết kế (`docs/THIET_KE_SCHEMA_EAS_V2.md` §5.4).
  - Cần chạy `database/data_fixes/2026-11-04_top_level_approver_binding.sql` trên live để khai báo người duyệt thay.
- **Cổng quản trị chỉ cho đúng email `admin@eas.com`** (`api_core/authn/views.py`, hàm `login`).
  - Người có vai trò OPS_ADMIN, POLICY_ADMIN hoặc AUDITOR khác không vào được cổng quản trị. Ngược lại, admin không vào được cổng nhân viên.
  - API vẫn kiểm vai trò, nên đây không phải lỗ hổng. Tuy vậy, quyền nên dựa trên vai trò thay vì email.
- **Không ai giữ vai trò AUDITOR**, nên không ai kiểm được chuỗi audit từ giao diện. Việc kiểm phải chạy bằng lệnh `manage.py audit_verify`.
- **Lỗi trải nghiệm nhỏ:**
  - mở lại đúng hồ sơ đang xem thì trang không tải lại dữ liệu;
  - đánh dấu thông báo đã đọc vẫn bật toast "Thao tác thành công";
  - menu hiện chữ thô `khi days_gt 2`;
  - gợi ý "đính kèm báo giá / hóa đơn" xuất hiện ở mọi biểu mẫu.

## Ghi chú môi trường

- Bản sao `m17test` thiếu quyền `USAGE`/bảng cho `eas_worker`. Đã cấp lại trên bản sao theo đúng `00_eas_supabase_schema.sql` và các migration.
- Mật khẩu `admin@eas.com` trên bản sao bị đổi trong khoảng 09:53–10:32. Không xác định được nguồn; đã đặt lại, chỉ trên bản sao.
