# Nhật ký phát triển Server API - Nền tảng tìm phòng trọ

## 1. Thông tin chung
- **Dự án**: Nền tảng tìm phòng trọ (Đồ án tốt nghiệp)
- **Component**: Server API (Backend)
- **Tech stack**: Java 17, Spring Boot 3.x, Spring Security (JWT), Spring Data JPA, Hibernate, PostgreSQL (có sử dụng extension PostGIS), Supabase Storage.

## 2. Quy tắc Code (Coding Conventions)
- **Kiến trúc**: Clean Code, tuân thủ SOLID, chia rõ layer (Controller, Service, Repository).
- **Data Transfer Object (DTO)**: Luôn sử dụng DTO cho request/response. Mapping giữa Entity và DTO bằng **MapStruct**.
- **Xử lý Exception**: Tập trung bằng `@RestControllerAdvice`.
- **Comment**: Giải thích rõ ràng các đoạn logic phức tạp, đặc biệt là SQL/GIS queries.

## 3. Trạng thái hiện tại (Current Status)
- [x] Khởi tạo file nhật ký `server_api.md` để lưu vết quá trình làm việc.
- [x] Task 1: Setup PostGIS và Hibernate Spatial.
- [x] Task 2: Setup Cốt lõi Security & JWT (Stateless, Spring Security 6).
- [x] Task 3: Phát triển API Đăng ký và luồng gửi mã OTP qua Email.
- [x] Task 4: API Tin đăng (GIS), Giới hạn hạn mức (Quota 5 tin) & Quản lý gói cước (Subscription) (M04, M08).
- [x] Task 5: Thuật toán tính Điểm trung vị (Midpoint) và Haversine Distance (M09).
- [x] Task 6: Luồng Đặt lịch xem phòng (M12).
- [x] Task 7: Tương tác Real-time Chat qua WebSocket (M13).
- [x] Task 8: Cảnh báo tự động Background Job (M14).
- [x] Task 9: API Thống kê cho Chủ trọ (M20).
- [ ] Chờ yêu cầu tiếp theo...
## 4. Nhật ký công việc (Changelog / Work Log)
### Phiên làm việc: 20/06/2026 (Task 9: API Thống kê cho Chủ trọ)
- **Trạng thái**: Hoàn thành API thống kê lượng VIEW và CONTACT_CLICK.
- **Chi tiết**:
  - Tạo `EventType` enum và entity `ViewEvent` lưu vết thao tác người dùng.
  - Viết Native Query PostgreSQL gom nhóm (Group by) số lượng theo từng ngày trong 7 ngày gần nhất.
  - Xây dựng `StatisticProjection`, `ViewEventRepository`, `StatisticService`, và `StatisticController` để trả về dữ liệu chuẩn cho biểu đồ.

### Phiên làm việc: 19/06/2026 (Task 4: Quản lý Tin đăng & Gói cước)
- **Trạng thái**: Hoàn thành API tạo tin đăng, cơ sở dữ liệu không gian và logic tính phí.
- **Chi tiết**:
  - Tích hợp `PostGIS` với Native Query `ST_DWithin` và `ST_Distance` để tìm kiếm và trả về DTO `ListingDistanceProjection`.
  - Cập nhật `User` thêm trường `premiumExpiryDate` để theo dõi thuê bao đóng phí.
  - Xây dựng API Tạo tin đăng chặn/cho phép dựa theo điều kiện: 5 tin đầu miễn phí. Tin thứ 6 yêu cầu `premiumExpiryDate` hợp lệ, nếu không trả về HTTP 402 Payment Required.
  - Thêm `SubscriptionCleanupScheduler` chạy ngầm mỗi ngày. Tự động rà soát những `User` hết hạn, đếm số tin đăng và tự động đổi `status` các tin từ thứ 6 trở đi sang `HIDDEN` (giữ lại 5 tin đầu theo thứ tự ngày tạo `createdAt`).
  - Xây dựng Mock API gia hạn Premium để phục vụ Test (cộng 30 ngày sử dụng).
  - **Refactor**: Chuyển đổi toàn bộ `Long id` sang `UUID id` (Entities, Repositories, DTO, Controllers, Service) để đồng nhất hoàn toàn với bảng auth.users mặc định của Supabase Postgres. Ứng dụng đã kết nối thành công và khởi động hoàn chỉnh!

### Phiên làm việc: 19/06/2026 (Task 3: API Đăng ký & OTP)
- **Trạng thái**: Hoàn thành API đăng ký và gửi mã OTP, cấu hình dọn dẹp OTP hết hạn.
- **Chi tiết**:
  - Tích hợp `spring-boot-starter-mail` để hỗ trợ gửi Email.
  - Tạo các Entity `User` (với các trường: id, email, password, role, status) và `OtpToken`.
  - Bổ sung `GlobalExceptionHandler` để bắt lỗi Validation định dạng (ví dụ: `MethodArgumentNotValidException`) và trả về message lỗi chi tiết từng trường.
  - Áp dụng Regex bảo mật `@Pattern` cho Mật khẩu (yêu cầu chữ hoa, thường, số, ký tự đặc biệt, min 8 ký tự).
  - Xây dựng API `POST /api/auth/register`:
    - Tạo tài khoản TENANT (status = ACTIVE).
    - Tạo tài khoản LANDLORD (status = INACTIVE), đồng thời sinh mã OTP 6 số lưu DB và giả lập gửi qua email (log).
  - Cập nhật `CustomUserDetailsService` dùng `UserRepository` thực tế kết nối vào DB.
  - Bổ sung `OtpCleanupScheduler` chạy định kỳ (`@Scheduled`) xóa OTP cũ hơn 7 ngày.

### Phiên làm việc: 19/06/2026 (Task 2: Setup Security)
- **Trạng thái**: Setup Cốt lõi Security & JWT.
- **Chi tiết**: 
  - Đã thêm thư viện `jjwt` vào `pom.xml`.
  - Tạo cấu hình bí mật JWT trong `application.yml`.
  - Xây dựng `JwtTokenProvider` để sinh và giải mã token (Hỗ trợ cả Access/Refresh token).
  - Xây dựng `JwtAuthenticationFilter` để parse header `Authorization` và inject authentication vào Security Context.
  - Cấu hình chuỗi `SecurityFilterChain` qua class `SecurityConfig`, chuyển config sang Stateless và mở khóa URL theo mẫu `/api/auth/**`, `/api/public/**`.

## 5. Nhiệm vụ tiếp theo (Next Tasks)
- Chờ yêu cầu task tiếp theo từ User.
