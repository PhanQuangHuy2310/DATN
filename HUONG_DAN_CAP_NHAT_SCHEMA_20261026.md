# Đồng bộ mã nguồn EAS với schema Supabase ngày 26/10/2026

## Thay đổi phát hiện trong bản xuất schema

- `eas.request_type` có cột bắt buộc `name`, `description`, `category`; `created_at` không nằm trong bản xuất.
- Giá trị `category` **chỉ được phép**: `HR`, `IT`, `FACILITY`, `PROCUREMENT`, `ASSET`, `FINANCE`, `GENERAL`.
- `eas.config_release` **không có `updated_at`** trong bản xuất, nên các thao tác cập nhật release phải dùng `lock_version` thay vì cập nhật cột không tồn tại.
- Ngoài yêu cầu thay đổi một bảng, bản xuất cũng cho thấy `app_user`, `department` không có `updated_at`; các cột `request_revision.revision_no`, `execution_attempt.attempt_no`, `attachment.scan_attempts`, `outbox_event.attempts/replay_count` cần được xử lý đúng. Backend hiện đã ghi rõ `revision_no`, `attempt_no`; các cột đếm có default.
- Bản xuất schema chứa 30 bảng nghiệp vụ, thêm bảng danh mục `role` và `lifecycle`; đây là DDL **chỉ để tham chiếu**, có ràng buộc FK trùng tên trong bản xuất và **không được chạy như migration**.

## Code đã sửa

1. `api_core/administration/service.py`: API quản lý RequestType trả ba trường metadata mới, cho tạo/sửa với validation rõ ràng, tìm kiếm tên/mô tả/nhóm, giữ audit và phân quyền OPS_ADMIN GLOBAL + ALL. Loại mới buộc phải inactive; chỉ mở lại khi đã có release `PUBLISHED` đúng type/lifecycle.
2. `api_core/catalog/views.py`: các API đọc loại đơn và form ưu tiên tên/nhóm/mô tả trong **Database** thay vì dữ liệu mẫu trong JSON. Luồng tạo đơn vẫn kiểm tra `REQUESTER`, release và scope khi ghi.
3. `api_core/workflow/config_service.py`: bỏ cập nhật `updated_at` trên release và loại yêu cầu; giữ `lock_version` cho khóa lạc quan.
4. `web_client/src/components/IdentityAdmin.jsx`: bổ sung trường nhập Tên loại, Mô tả, Nhóm theo 7 mã DB; loại mới mặc định không kích hoạt.
5. `database/report_migrations/02...` và `03...`: mọi câu INSERT bổ sung ba cột NOT NULL (vẫn **DBA REVIEW ONLY**). Metadata được điền từ danh mục plan và các nhóm đã quy đổi rõ ràng; người có thẩm quyền cần rà soát phân loại trước khi áp dụng.
6. Seed/bootstrap SQL dành cho **database trống** cập nhật đồng bộ 3 cột này. **Không chạy lại** seed/bootstrap trên Supabase hiện có.

## Kiểm tra trên Windows (chỉ đọc)

```cmd
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe check_schema_contract.py
.\.venv\Scripts\python.exe -m unittest tests_business.test_live_schema_contract -v
```

Khởi động lại Backend `start_backend_local.cmd` và Frontend `start_frontend_local.cmd`, sau đó kiểm tra giao diện Quản lý loại yêu cầu trên tài khoản OPS_ADMIN có `GLOBAL + ALL`.

**Không áp dụng migration hoặc seed trên Supabase production khi chưa kiểm thử bản sao UAT, backup và đối chiếu quyền SQL.** Mã nguồn đã sửa theo cấu trúc cung cấp; chưa xác nhận chạy kết nối mạng đến database thực tế của bạn.
