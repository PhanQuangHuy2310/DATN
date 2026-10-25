# Kết nối database EAS

File `connect_database.py` đọc cấu hình, kết nối PostgreSQL bằng psycopg và kiểm tra sự tồn tại của 30 bảng `eas`. Có thể dùng độc lập để kiểm tra, hoặc đặt cạnh `DATN/manage.py` để khởi động Django với chính kết nối đó.

## 1. Chép file và cấu hình (Windows PowerShell)

Giải nén gói này; chép `connect_database.py`, `requirements-db.txt` và `.env.database.example` vào thư mục DATN (cạnh manage.py). Mở terminal tại DATN:

```powershell
python -m pip install -r requirements-db.txt
Copy-Item .env.database.example .env.database
notepad .env.database
```

Điền DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD bằng thông tin kết nối database thực tế. Mật khẩu trong DB_PASSWORD là mật khẩu nguyên bản, không cần URL-encode. Không đặt comment ở cuối dòng giá trị. File hỗ trợ KEY=VALUE, dấu nháy đơn/đôi; không hỗ trợ nội suy biến hoặc giá trị nhiều dòng.

Dùng tài khoản runtime đã được cấp quyền cho EAS. Với endpoint qua pooler, điền đúng username và port được cấu hình cho endpoint đó; không suy ra username từ tên schema. Đây là mật khẩu PostgreSQL, không phải mật khẩu người dùng eas.app_user hay API key Supabase.

## 2. Kiểm tra kết nối

```powershell
python connect_database.py
```

Có thể chọn file môi trường khác:

```powershell
python connect_database.py --env-file .env.database
```

Mã thoát: 0 = kết nối và tìm thấy đủ bảng; 1 = lỗi PostgreSQL/kết nối; 2 = lỗi cấu hình/dependency; 3 = thiếu schema/quyền USAGE/bảng. Thiếu SELECT trực tiếp chỉ được báo chú thích vì tài khoản hạn chế có thể truy cập qua hàm có phân quyền. Kết quả không chứng minh quyền ghi, RLS hay nghiệp vụ hoạt động.

## 3. Khởi động backend dự án

Cài đầy đủ dependencies dự án nếu chưa có:

```powershell
python -m pip install -r api_core/requirements.txt
python connect_database.py --runserver
```

Lệnh này nạp `.env.database`, thiết lập DATABASE_URL rồi chạy manage.py runserver. `python manage.py runserver` trực tiếp KHÔNG tự nạp file này. Những cấu hình Redis, storage, antivirus và AI tiếp tục tuân theo dự án gốc; kết nối database không thay thế các dịch vụ đó.

Trong terminal khác, chạy giao diện:

```powershell
cd web_client
npm ci
npm run dev -- --host 127.0.0.1
```

Vite hiện chuyển `/api` đến `127.0.0.1:8000`. Trình duyệt chỉ gọi Django, không chứa chuỗi kết nối database.

## Cấu hình và lưu ý

- Biến môi trường của tiến trình ưu tiên hơn file. DATABASE_URL ưu tiên EAS_API_DATABASE_URL, rồi mới DB_*.
- Nếu đã có DATABASE_URL cũ trong terminal, hãy cập nhật hoặc bỏ biến đó để sử dụng DB_* mới.
- SSL mặc định require; nếu cần xác minh chứng chỉ, dùng verify-full với cấu hình chứng chỉ CA thích hợp của môi trường.
- File chỉ đọc metadata trong transaction READ ONLY khi kiểm tra. Không chạy dtb.txt, không tạo/xóa bảng, không migrate/seed tự động.
- Không cần đọc các schema auth/storage/vault để kết nối nghiệp vụ eas.
- Mẫu EAS_ENV=development dùng để chạy cục bộ. Production dùng process manager và cấu hình production sẵn có, không dùng runserver.
- Giữ .env.database ngoài Git. Dự án gốc đã có quy tắc ignore file môi trường; kiểm tra trước khi commit.

## Kiểm tra mã

```powershell
python -m unittest discover -s tests -v
```

Unit tests kiểm tra nạp môi trường, ưu tiên cấu hình, ký tự đặc biệt trong mật khẩu và chẩn đoán metadata giả lập. Chưa kiểm tra kết nối thật vì file dtb.txt không chứa host và thông tin xác thực.
