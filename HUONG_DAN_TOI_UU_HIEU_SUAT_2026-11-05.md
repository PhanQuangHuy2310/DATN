# Tối ưu hiệu suất DATN — 05/11/2026

## Thay đổi mã nguồn

1. `web_client/src/App.jsx`: các trang hồ sơ, hộp việc, quản trị công việc,
   thông báo, hồ sơ cá nhân… chuyển sang React.lazy/Suspense. Các trang chưa
   được mở không phải tải/parse JavaScript ban đầu. Giữ nguyên điều hướng,
   quyền, quy trình và dữ liệu.
2. `web_client/src/components/AppHeader.jsx` không còn vô tình import cả
   `NotificationsPage` chỉ để dịch nhãn thông báo. Nhãn riêng tại
   `notificationLabels.js`.
3. `web_client/src/components/ClientRequestsHub.jsx`: trang biểu đồ tách
   chunk và không gửi yêu cầu danh mục lặp lúc mount; chỉ polling 90 giây
   khi tab còn hiển thị (thay vì 15 giây).
4. `web_client/src/components/ClientRequests.jsx` sử dụng
   `GET /api/v1/meta/departments` (chỉ id/name) thay vì tải cả cây tổ chức và
   nhân viên từ `/api/v1/meta/org-chart` cho bộ lọc phòng ban. API mới vẫn
   yêu cầu đăng nhập và chỉ trả danh sách phòng ban đã hiển thị trước đó.
5. `web_client/src/api.js`: cache RAM 90 giây cho danh mục loại yêu cầu và
   phòng ban, 20 giây cho dữ liệu động. Cache giới hạn 120 URL để tránh tăng
   bộ nhớ khi người dùng tìm kiếm / phân trang liên tục. Mọi mutation thông thường vẫn gọi
   `invalidateResources`; đăng nhập/đăng xuất cũng xóa cache.
6. `api_core/workflow/reporting.py`: `list_notifications` gom truy vấn COUNT
   chưa đọc và dữ liệu trang vào 1 SQL statement / 1 lượt đi Supabase.
   Trường hợp trang rỗng vẫn trả đúng `unread_count`.
7. `database/performance/01_optional_indexes.sql`: đề xuất index PostgreSQL
   (KHÔNG tự chạy). Kiểm tra EXPLAIN trước khi triển khai trên DB thật.

## Xác định API nào chậm trên máy của bạn

1. Mở Chrome DevTools -> Network, bật Disable cache để đo cold load; tab
   Timing xem Wait for server response và Download; lọc `/api/`.
2. Trong Headers, `Server-Timing: app;dur=...` do middleware hiện có phát
   ra giúp phân biệt thời gian Django và thời gian network/proxy/browser.
3. Log backend hiện cảnh báo `Slow API request` khi trên 1200ms, gồm URL path,
   duration và HTTP status, không in payload, mật khẩu hay truy vấn.
4. Chạy EXPLAIN (ANALYZE, BUFFERS) cho truy vấn chậm với tham số THẬT trong
   Supabase SQL Editor (chỉ khi được quyền) trước khi thêm index.
5. Dữ liệu Supabase, quy mô bảng, băng thông và thời gian thực tế chưa đo
   trực tiếp được từ file ZIP; mọi lời khẳng định tăng N% tốc độ phải đo
   benchmark trên môi trường của bạn.

## Triển khai

Giữ `.env` và dữ liệu Supabase hiện tại. Dừng tiến trình dev cũ rồi chạy:

    start_backend_local.cmd
    start_frontend_local.cmd
    start_admin_local.cmd
    start_ai_local.cmd

Trên máy Windows, cài phụ thuộc nếu chưa cài:

    cd web_client && npm ci
    cd ..\web_admin && npm ci

Với Django, không cần migrate cho API mới vì không có thay đổi bảng.
Không áp dụng file SQL index nếu chưa xác minh quyền DBA / kế hoạch backup.

## Giới hạn kiểm thử

Node test và kiểm tra cú pháp có thể chạy ngoại tuyến; build React và test
Django tích hợp Supabase chỉ có thể xác thực khi có dependencies môi trường.
