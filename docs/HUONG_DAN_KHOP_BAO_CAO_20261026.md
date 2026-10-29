# Đối chiếu đồ án EAS với Report_DATN_CNTT_Nhom07_v1.0.docx

## Căn cứ và phạm vi

- Báo cáo Chương 2, Bảng 2.2: **16 ca sử dụng UC01–UC15 và UC17** (UC16 không có trong bảng P0).
- Báo cáo Mở đầu 3.2: **16 loại yêu cầu** trong 3 mẫu A/B/C và 8 phòng ban.
- Bảng 2.6: luật R01–R07, ngưỡng tài chính <5m, 5m–50m, >50m, yêu cầu 2 cấp cho quyền IT Admin.
- Bảng 2.7: 7 actor nghiệp vụ và ma trận quyền.
- Bảng 2.9: nhắc SLA tại 80%, escalations 100% và 150%.
- Phần 2.4 và 3.2: Web Portal, Web Admin, Mobile; AI classify/risk/auto-approve/OCR/summarize.

## Điều đã sửa trong bản này

1. Đọc danh mục biểu mẫu từ release `PUBLISHED` + role membership hợp lệ; không hiển thị loại ngoài scope.
2. Form React được tạo từ JSON Schema đã được Backend công bố; vẫn giữ label đặc thù của LEAVE/ACCESS/EQUIPMENT.
3. Detail hiển thị mọi trường payload thay vì bỏ mất trường cho các loại mở rộng.
4. Validator Python hỗ trợ mã loại mở rộng trong profile JSON Schema giới hạn, nhưng chỉ thực thi khi **DB đã có loại và published release**; các invariant đặc thù LEAVE/EQUIPMENT vẫn giữ.
5. Readiness vẫn kiểm ba loại P0 có mặt nhưng cho phép thêm loại đã cấu hình hợp lệ.
6. Chức năng tạo loại mới của OPS_ADMIN yêu cầu `EAS_ALLOW_REPORT_CATALOG_EXPANSION=true`, `GLOBAL + ALL`, reason/idempotency/audit và migration DBA; mặc định **tắt**.
7. POLICY_ADMIN được phép tạo / kiểm tra / công bố config cho loại đã được đăng ký và cấp scope.
8. `report_conformance.py` báo trạng thái CODE_PRESENT/GAP/NOT_VERIFIED/MIGRATION_REQUIRED; không lộ khóa.

## Bất đồng tài liệu chưa thể tự giải quyết

| Chủ đề | Báo cáo v1.0 | Mã/schema P0 v2 | Cách xử lý |
|---|---|---|---|
| Số loại đơn | 16 loại, không có bảng tên mã đầy đủ | 3 mã LEAVE/ACCESS/EQUIPMENT và CHECK type_p0 | Chờ danh mục 16 mã chính thức; chạy migration riêng bằng vai trò DBA; không bịa seed |
| Ngưỡng route | 5m và 50m (Bảng 2.6) | Demo 10m và 50m | Giữ quyết định đã snapshot; cập nhật release mới qua Policy Admin sau duyệt, không sửa lịch sử |
| SLA reminder | 80% (Bảng 2.9) | Guard DB `reminder_fraction=0.5` | Cần migration guard, test worker và dữ liệu; **chưa sửa** |
| Auto-approval | R01 nghỉ phép <=2 ngày & risk<=2 | P0 yêu cầu duyệt người | Không bật tự duyệt cho tới khi policy/SoD/risk/audit/budget được kiểm chứng |
| Quyền đọc | Bảng RBAC ghi Policy/Ops/Auditor xem tất cả | SRS v2 scoped RBAC và bảo mật dữ liệu | Giữ giới hạn scope của Backend; cần quyết định chính thức trước khi cấp thêm quyền |
| Ứng dụng Mobile | Flutter, FCM, biometric | Source hiện có Web/AI/Worker | Chưa triển khai/kiểm chứng Mobile trong bản vá |
| Số bước duyệt Template C | Từ 03 cấp trở lên | Trình resolve giới hạn 1..3 | 3 cấp được; >3 cần thay contract+schema+test đồng thời |
| Bảo cáo chương 3 | Nhiều mục là đề mục chưa có nội dung thực nghiệm | Code có chức năng nhưng còn lỗi E2E | Không coi báo cáo là bằng chứng PASS; cần log/test thực tế |

## Quy trình bật rộng danh mục (không tự động)

1. Sao lưu Supabase và đối chiếu đúng danh sách 16 code + template theo nhóm phê duyệt của đề tài.
2. DBA review `database/report_migrations/01_request_catalog_expansion_REVIEW_BEFORE_RUN.sql` (bao gồm quyền INSERT hạn chế cho service role eas_api); chạy **chỉ trên môi trường thử nghiệm trước** bằng vai trò migration, KHÔNG chạy bằng Backend.
3. Trong môi trường test đặt `EAS_ALLOW_REPORT_CATALOG_EXPANSION=true` rồi restart Backend.
4. Dùng OPS_ADMIN scope GLOBAL/ALL để khai báo mã mới và lifecycle A/B/C. Thao tác luôn cần lý do.
5. POLICY_ADMIN đủ quyền cho mã đó tạo bản config DRAFT, bổ sung JSON Schema/rules/bindings/SLA, VALIDATE, PUBLISH.
6. Identity operator cấp quyền REQUESTER theo department/type. Người dùng thấy biểu mẫu động và có thể soạn/gửi.
7. Chạy test workflow A/B/C, SoD, idempotency, audit và worker trên DB test trước khi triển khai prod.
8. **Không áp dụng** các mô tả 80% SLA và auto-approval trực tiếp vào PROD khi chưa có migration, approvals và ca kiểm thử.

## Chạy & kiểm tra

```cmd
cd /d "D:\Đồ án\DATN"
py -3.12 report_conformance.py
py -3.12 report_conformance.py --json
.\.venv\Scripts\python.exe report_conformance.py --live-db
start_backend_local.cmd
```

Terminal khác:

```cmd
cd /d "D:\Đồ án\DATN\web_client"
npm ci
npm test
npm run build
npm run dev -- --host 127.0.0.1
```

API mới sau đăng nhập REQUESTER: `GET /api/v1/meta/request-type-forms`.

Mọi migration/toggle đều độc lập với bản Patch: mặc định bản Patch **không thay đổi schema Supabase**.
