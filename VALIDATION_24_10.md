# Kết quả kiểm tra — 24/10/2026

| Phần | Kết quả | Phạm vi |
|---|---|---|
| Django | 103 tests đạt | SQLite/mocks, gồm quyền quản trị và lịch sử/tệp |
| Kết nối database | 9 tests đạt | Phân tích cấu hình/DSN, kiểm tra đầu vào bằng mock |
| Frontend logic | 5 tests đạt | Điều kiện quyền/trạng thái |
| Chromium | 18 tests đạt | API fixtures; thao tác và payload |
| SQL | 86 assertions đạt | PGlite PostgreSQL WASM, schema/seed/rollback/hash |
| Kiểm tra tĩnh | Đạt | Ruff, ESLint, Vite production build |

Lệnh tái chạy từ thư mục DATN:

```bash
EAS_ENV=test python manage.py test api_core.tests
python -m unittest discover -s connection_tests
cd web_client
npm test
npm run lint
npm run build
npx playwright install chromium
npm run test:ui
```

Windows PowerShell đặt `$env:EAS_ENV='test'` trước lệnh Django. Bộ SQL chạy `npm ci` rồi `npm test` tại `database/EAS_Supabase_SQL/validation`.

Các thông báo Unauthorized, Forbidden, Hash mismatch trong ca âm là đầu ra có chủ đích; kết quả tổng phải là OK/exit 0. Chưa chạy tích hợp với Supabase, Storage, Redis, ClamAV và gateway thật. Không suy ra nghiệm thu toàn hệ thống từ test có mock. Cần cấu hình môi trường thật và chạy các kịch bản nghiệp vụ trước khi triển khai.
