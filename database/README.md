# Cấu trúc Quản lý Database

Thư mục `database/` được sử dụng để quản lý trực tiếp các thay đổi, logic và kiểm thử ở tầng Cơ sở dữ liệu (Database Layer). Phương pháp này (thường thấy khi dùng Sqitch hoặc Supabase) giúp tách biệt quản lý cấu trúc DB khỏi Backend, đảm bảo tính nhất quán của dữ liệu.

Dưới đây là tác dụng và nhiệm vụ chi tiết của 3 thư mục chính trong cấu trúc này:

## 1. Thư mục `migrations/`
**Tác dụng:** Nơi chứa các file mã lệnh SQL chịu trách nhiệm làm thay đổi cấu trúc của cơ sở dữ liệu (Database Schema).

**Nhiệm vụ:**
- Khởi tạo các bảng mới (CREATE TABLE).
- Thay đổi cấu trúc bảng hiện có (Thêm, sửa, xóa cột - ALTER TABLE).
- Thiết lập các ràng buộc dữ liệu (Primary Key, Foreign Key, Check Constraints, Index).
- Quản lý các phiên bản cấu trúc dữ liệu theo thời gian (Version Control cho Database), giúp dễ dàng rollback lại trạng thái cũ nếu có lỗi xảy ra.

**Ví dụ thao tác:** Bạn cần thêm cột `risk_level` vào bảng `requests`. Bạn sẽ tạo một file SQL trong thư mục này (VD: `20260911_add_risk_level.sql`) chứa lệnh `ALTER TABLE requests ADD COLUMN risk_level INT;`.

---

## 2. Thư mục `functions/`
**Tác dụng:** Nơi chứa các đoạn mã xử lý logic nghiệp vụ được thực thi trực tiếp bên dưới Cơ sở dữ liệu (Stored Procedures, DB Functions, Triggers).

**Nhiệm vụ:**
- **Tạo Functions/Procedures:** Đóng gói các logic tính toán phức tạp thành hàm SQL có thể tái sử dụng. Việc chạy logic trực tiếp trên DB thường nhanh hơn rất nhiều so với việc tải toàn bộ dữ liệu lên Backend rồi mới tính toán.
- **Xây dựng Triggers:** Lắng nghe các sự kiện (INSERT, UPDATE, DELETE) và tự động phản ứng lại. Ví dụ: tự động cập nhật trường `updated_at`, hoặc tự động ghi log vào bảng `audit_logs` mỗi khi trạng thái Yêu cầu bị thay đổi.

**Ví dụ thao tác:** Bạn tạo một file `trigger_audit_log.sql` chứa lệnh tạo một Function ghi log và một Trigger gắn Function đó vào bảng `requests`.

---

## 3. Thư mục `verify/`
**Tác dụng:** Nơi chứa các đoạn script SQL đặc biệt dùng để kiểm tra (Test) xem các câu lệnh trong `migrations/` và `functions/` đã được áp dụng và cấu hình đúng hay chưa.

**Nhiệm vụ:**
- **Unit Test cho Database:** Đảm bảo rằng việc thay đổi database không phá vỡ cấu trúc hiện tại.
- **Đảm bảo an toàn CI/CD:** Khi chạy tự động (deploy lên server), hệ thống sẽ chạy script verify. Nếu script verify gặp lỗi (ví dụ, cố gắng SELECT cột vừa tạo nhưng bị lỗi `column does not exist`), toàn bộ tiến trình thay đổi (migration) sẽ lập tức bị hủy bỏ (rollback).

**Ví dụ thao tác:** Cùng với việc thêm cột `risk_level` ở trên, bạn tạo một file verify chứa câu truy vấn `SELECT risk_level FROM requests WHERE FALSE;`. Nếu cột này chưa được tạo thành công, lệnh SELECT sẽ báo lỗi và ngăn chặn rủi ro.
