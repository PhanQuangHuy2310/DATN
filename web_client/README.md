# Các cổng web EAS

`web_client` chứa giao diện React dùng chung cho cổng nhân viên và quản trị. `web_admin` là entry point Vite riêng, tái sử dụng source và public assets này. Cả hai cổng gọi Django API; không chứa database hay Supabase secret.

## Chạy và build

Cài dependency trong từng thư mục:

```powershell
cd web_client
npm ci
npm run lint
npm test
npm run build

cd ..\web_admin
npm ci
npm run build
```

Khi phát triển local, khởi động API trước, sau đó chạy `npm run dev` trong `web_client` và `web_admin`. Cổng nhân viên và quản trị lần lượt dùng port 5173 và 5174.

Hai ứng dụng dùng chung [`.env.example`](./.env.example) cho cấu hình Vite công khai; không đặt secret vào biến `VITE_*`. Docker của cả hai cổng cũng dùng chung [`nginx.conf`](./nginx.conf).

## Phạm vi và xác minh

Giao diện gồm đăng nhập/session, tạo và theo dõi yêu cầu, phê duyệt, thực thi/nghiệm thu, quản lý danh tính/vai trò, chính sách, vận hành, kiểm toán và duyệt yêu cầu reset mật khẩu. Django thực thi phân quyền; ẩn menu không thay thế kiểm tra quyền.

`npm test` và `npm run test:ui` dùng test fixture local, không chứng minh tích hợp staging/production. Cần cấu hình API, database, SMTP, storage và scanner thật trước khi nghiệm thu end-to-end.
