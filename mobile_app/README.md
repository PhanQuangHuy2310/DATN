# EAS Mobile (Flutter) — P1 quick approval client

Ứng dụng di động dựa theo nghiệp vụ trong báo cáo DATN và hợp đồng API thực tế của `api_core`. **Không được tính là UAT P0 đã hoàn tất.** Giao diện gồm: đăng nhập + CSRF + session cookie trong RAM, buộc đổi mật khẩu lần đầu, danh sách **Của tôi / Cần duyệt / Thực hiện / Nghiệm thu**, chi tiết hồ sơ, các quyết định với lý do bắt buộc, thông báo và đăng xuất. Mọi thao tác ghi có `expected_version` và `Idempotency-Key`; Django vẫn thực thi RBAC/SoD, không tin điều kiện hiển thị Flutter.

Cài Flutter SDK 3.x, sau đó chạy trong `mobile_app`:

```powershell
flutter pub get
flutter run --dart-define=EAS_API_BASE_URL=http://10.0.2.2:8000
```

Lệnh trên dành cho Android emulator **debug** và Django chạy ở máy host. Với thiết bị thật hoặc bản release, sử dụng endpoint **HTTPS hợp lệ**, ví dụ `--dart-define=EAS_API_BASE_URL=https://api.example.com` (thay bằng domain thực của bạn). Khi khởi tạo Flutter project trên máy local nếu chưa có thư mục `android/` hoặc `ios/`, chạy `flutter create --project-name eas_mobile --platforms android,ios .` trước `flutter pub get`; lệnh này chỉ tạo wrapper nền tảng, không sửa logic nghiệp vụ trong `lib/`.

**Giới hạn hiện tại:** chưa có upload chứng từ/thực hiện, tạo biểu mẫu động hoặc nhận push notification; công việc tạo hồ sơ đầy đủ vẫn làm tại Web. Chưa có kiểm chứng Flutter build trên môi trường này vì không cài Flutter SDK. Session chỉ ở RAM, đăng nhập lại sau khi khởi động; chưa triển khai secure background device trust, biometric, deep linking, offline/conflict reconciliation. Không nhúng `SUPABASE_SECRET_KEY`/DB password vào app.
