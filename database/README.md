# Quản lý Database (Migrations, Functions, Verify)

Thư mục này chứa các file SQL nguyên thủy (raw SQL) để quản lý cơ sở dữ liệu (tương tự kiến trúc Sqitch hoặc Supabase).

## Cấu trúc thư mục

- `migrations/`: Chứa các file SQL thay đổi cấu trúc DB (tạo bảng, thêm cột, sửa kiểu dữ liệu).
- `functions/`: Chứa các file SQL tạo Stored Procedures, Functions, hoặc Triggers trong cơ sở dữ liệu.
- `verify/`: Chứa các script SQL để kiểm tra (verify) xem các migration/function đã được áp dụng đúng hay chưa.

*Lưu ý: Nếu bạn sử dụng Django làm Backend chính như trong `plan.md`, Django cũng đã có sẵn cơ chế `makemigrations` và `migrate` ở thư mục ứng dụng. Tuy nhiên, bạn có thể dùng thư mục này nếu muốn quản lý DB độc lập bằng SQL thuần, Supabase hoặc Sqitch.*
