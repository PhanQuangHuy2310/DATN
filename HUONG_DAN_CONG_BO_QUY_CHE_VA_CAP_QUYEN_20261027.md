# HƯỚNG DẪN CÔNG BỐ QUY CHẾ VÀ CẤP QUYỀN TẠO ĐƠN — EAS

## Tại sao có dòng "Chưa có quy chế đã công bố / quyền tạo đơn phù hợp"?

Thông báo trước đây trộn lẫn nhiều nguyên nhân khác nhau. Bản cập nhật phân biệt:

- `TYPE_NOT_REGISTERED`: mã loại yêu cầu chưa tồn tại trong `eas.request_type`.
- `TYPE_INACTIVE`: loại yêu cầu đang bị tạm ngừng.
- `LIFECYCLE_MISMATCH`: mẫu vòng đời không khớp với mục danh sách đang chọn.
- `NO_PUBLISHED_RELEASE`: chưa gắn `active_release_id` tới release `PUBLISHED`, đúng loại và đúng lifecycle.
- `REQUESTER_SCOPE_DENIED`: chưa có membership `REQUESTER` đang hiệu lực trong loại đơn/phòng ban.

Chỉ loại đơn ACTIVE + PUBLISHED + REQUESTER trong phạm vi mới có nút **Chọn và tạo đơn**. **Việc hiển thị không đồng nghĩa cam kết gửi đơn thành công**: khi gửi, Backend luôn kiểm tra lại quy chế, tình trạng user/role, manager, phân tách nhiệm vụ và người được phân công.

## Quy trình thực tế — không cần SQL sửa dữ liệu thật

1. **Đăng nhập bằng `POLICY_ADMIN`**. Vào **Cấu hình quy trình** → **Tình trạng công bố & quyền tạo đơn**. Thống kê này chỉ hiển thị mã loại trong scope của tài khoản Policy Admin.
2. Với loại báo **Chưa có release PUBLISHED**, chọn **Tạo quy chế nháp**. Với loại đã có `DRAFT`, chọn **Mở nháp**.
3. Hệ thống sinh bản nháp:
   - Nếu mã có mẫu trong `docs/APPROVAL_MENU_POLICY_DRAFTS.json`, dùng mẫu A/B/C có sẵn.
   - Với các mã từ `plan_types.json`, giữ schema trường dữ liệu từ plan và gợi ý tuyến duyệt để người quản trị kiểm tra.
   - Bảy mã mở rộng có sẵn ở Database nhưng chưa có đặc tả biểu mẫu trong plan (liệt kê dưới đây) dùng khung nháp an toàn. **Cần thêm trường thông tin đặc thù vào `form_schema` mới được công bố**.
   - Không tự sinh người duyệt, tự cấp quyền hoặc tự bật AI auto approval.
4. Soát 4 tài liệu JSON: `form_schema`, `route_rules`, `actor_bindings`, `sla_profile`. Với Template B phải có `executor`; Template C phải có `executor` và `acceptor`.
5. Ở phần **Hỗ trợ phân công theo role**, chọn phòng ban, chọn slot cần phân công và người được cấp role còn hiệu lực. Nút **Thêm phòng ban/Gán người vào JSON** chỉ chỉnh bản nháp hiển thị; nhấn **Lưu bản nháp** mới gửi thay đổi lên Backend.
6. Nhấn **Kiểm tra cấu hình**. Backend kiểm tra schema, trạng thái phòng ban, tất cả slot bắt buộc, UUID người được phân công, membership có scope đúng loại/phòng ban, và xung đột phân tách nhiệm vụ rõ ràng.
7. Nếu **Kiểm tra** hợp lệ, nhấn **Công bố phiên bản** và nhập lý do (ít nhất 10 ký tự). Backend ghi audit, chuyển release thành `PUBLISHED`, gắn `active_release_id` **trong một giao dịch**. Release đã công bố bất biến; muốn thay đổi phải tạo phiên bản mới.
8. **Đăng nhập bằng `OPS_ADMIN` có `GLOBAL + ALL`**, vào **Danh tính & phân quyền**, cấp `REQUESTER` cho nhân viên: chọn user, phạm vi `DEPARTMENT` + phòng ban (hoặc `GLOBAL` nếu thật sự được phép), phạm vi loại `ONE` + loại đơn (hoặc `ALL` nếu cần), thời hạn hiệu lực. Đối với người duyệt/thực hiện/nghiệm thu, cấp các quyền `APPROVER`, `EXECUTOR`, `ACCEPTOR` tương ứng và đảm bảo SoD.
9. Kiểm tra loại yêu cầu đang **is_active=true** qua màn hình OPS_ADMIN. Nếu không thì chỉ kích hoạt sau khi đã hoàn thiện quy chế và quyền, trên UAT trước rồi mới lên production.
10. Đăng nhập bằng `REQUESTER` vào **Tạo yêu cầu**. Loại đơn được cấp quyền giờ có nút **Chọn và tạo đơn**.

### Bảy mã đang active nhưng thiếu release trong bản chẩn đoán của bạn

`ACCESS_FACILITY`, `BUSINESS_TRIP`, `EQUIPMENT_BORROW`, `EXPENSE_CLAIM`, `IT_SUPPORT`, `LEAVE_SPECIAL`, `ROOM_BOOKING`.

Đây là **các mã riêng có trong DB hiện tại** nhưng không thuộc toàn bộ danh sách 18 mã chuẩn của `plan_types.json`. Hệ thống **không thể tự suy ra** đủ trường nghiệp vụ và tuyến duyệt chính xác của chúng; cần POLICY_ADMIN chốt dữ liệu đầu vào, route, SLA và role theo nghiệp vụ thực tế trước khi công bố. Nếu dự định thay bằng loại đơn chính thức từ plan, tránh tạo hai mã có cùng chức năng một cách tùy tiện.

### Giới hạn và an toàn

- `RESIGNATION`: plan yêu cầu bốn bên thực hiện **song song**. Runtime hiện chỉ có một Executor; phiên bản này cố ý từ chối công bố loại này để không biến quy trình bốn bên thành một bên. Cần phát triển parallel workflow thực sự trước khi triển khai.
- `LEAVE_LONG` có trường "HR ghi nhận" trong plan nhưng gán Template A (approve-only); người quản trị phải xác nhận yêu cầu trước khi dùng. Các bước thực hiện chưa được tự động thêm trái Template A.
- Backend không cấp permission chỉ vì bản release đã công bố. `REQUESTER` là grant độc lập của OPS_ADMIN.
- Role có thể bị thu hồi sau khi công bố; Backend vẫn kiểm tra lại mọi grant khi người dùng gửi đơn.
- Phân công quản lý trực tiếp `DIRECT_MANAGER` là động theo `app_user.manager_id`, kiểm tra khi gửi; có thể không xác định trước tại lúc công bố.
- Schema cũ trên Supabase có thể vẫn chạy `eas.guard_release()` bản P0 với allowlist chỉ 3 role. Cần **DBA so sánh định nghĩa trigger đang có** với `database/report_migrations/04_approved_actor_resolvers_DBA_REVIEW_ONLY.sql` và nâng cấp trên UAT nếu cần, KHÔNG áp dụng mù lên production.
- Không chạy lại `database/schema.sql`, `seed.sql`, hoặc chỉnh trực tiếp `active_release_id`/`role_membership` bằng SQL thủ công.
- Không có tự động công bố hàng loạt; tất cả các release phải được một Policy Admin có scope hợp lệ xác nhận.

## API và kiểm thử

- `GET /api/v1/config-releases/status` — trạng thái loại/release/số tài khoản REQUESTER, yêu cầu POLICY_ADMIN; không lộ danh tính/request data.
- `GET /api/v1/config-releases/actor-options?type_code=ROOM_BOOKING` — phòng ban và những user được cấp grant APPROVER/EXECUTOR/ACCEPTOR trong scope của Policy Admin và loại đơn.
- `POST /api/v1/config-releases` — tạo nháp.
- `PATCH /api/v1/config-releases/{uuid}` — lưu 4 tài liệu JSON.
- `POST /api/v1/config-releases/{uuid}/validate` — kiểm tra khả năng công bố.
- `POST /api/v1/config-releases/{uuid}/publish` — công bố atomically, audit.
- `GET /api/v1/meta/request-type-forms` — danh sách biểu mẫu cho REQUESTER, có `blocker_code` và `disabled_reason` riêng theo từng mục.

Trên Windows (từ thư mục `DATN`):

```cmd
.\.venv\Scripts\python.exe -m unittest discover -s tests_business -p "test_policy_publication.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests_business -p "test_request_catalog_availability.py" -v
cd web_client
npm test
npm run build
```

Sau cập nhật code, restart Backend và chạy Vite. Test HTTP/DB end-to-end phải thực hiện trên môi trường có Django, `psycopg`, PostgreSQL và các role được cấp chính xác. Bản vá **không sửa cơ sở dữ liệu thực tế** và **không tự khắc phục HTTP 503** nếu còn nguyên nhân hạ tầng khác.
