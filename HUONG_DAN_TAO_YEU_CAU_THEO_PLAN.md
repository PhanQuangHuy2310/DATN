# EAS: Tạo yêu cầu theo danh mục Finance / Ops / IT / HR

Nguồn ưu tiên: bảng phân loại yêu cầu được người dùng cung cấp, đối chiếu `plan.docx`.
Bảng hiển thị 20 lựa chọn trong 4 nhóm, trong đó **nghỉ từ 3 ngày và cấp laptop xuất hiện ở hai nhóm**, dùng chung mã loại => **18 mã duy nhất**.

## Chức năng đã được lập trình

- REQUESTER nhấn **Tạo yêu cầu** → danh mục 4 nhóm có thể mở/đóng, tìm kiếm, nhãn mẫu A/B/C và trạng thái đã công bố/chưa kích hoạt.
- Chọn mục đã được cấp quyền → tự cuộn đến form nghiệp vụ sinh từ JSON Schema của config release đã công bố.
- **Không có ô nhập mã yêu cầu**. Lệnh `POST /api/v1/request-drafts` tạo bản ghi trên `eas.request`, PostgreSQL sinh `request.code` (`RETURNING code`). Code hiển thị sau khi tạo draft. UUID và số mã này khác nhau.
- Không nhập người tạo, phòng ban, người duyệt, executor hoặc acceptor. Dựa trên phiên người dùng, role membership có scope, chính sách đã công bố và actor bindings, Backend resolve và kiểm tra lại trong cùng transaction khi submit.
- Tiêu đề kỹ thuật được sinh từ tên loại yêu cầu và ngày, người dùng nhập **chỉ trường nghiệp vụ cụ thể** của schema. `department_id` được lấy từ phiên đăng nhập và chống giả mạo trên Backend.
- Trường người bàn giao dạng UUID được chọn bằng tên đồng nghiệp cùng phòng, không nhập UUID thủ công. Trường hóa đơn/chứng từ dạng filename dùng upload thực tế (CLEAN scan vẫn là điều kiện để gửi).
- Nguyên tắc SoD: không tự duyệt; executor không kiêm approver và không tự nghiệm thu. Chưa giải quyết được người nhận nhiệm vụ sẽ trả HTTP **409 ROUTE_CONFIGURATION_INVALID**, không tạo hồ sơ đã gửi với tuyến sai.
- Web Admin **Danh mục loại yêu cầu** có hai chế độ xem: danh mục theo 20 lựa chọn của nhân viên và 18 mã mở rộng nguyên bản của `plan.docx`.

## Kích hoạt trên DB (không chạy tự động)

Trên schema Supabase hiện tại, `type_p0` có thể vẫn giới hạn `LEAVE/ACCESS/EQUIPMENT` và các luật actor slot cũ. Vì vậy **danh mục hiện ra không đồng nghĩa 18 loại đã có thể gửi**. Bắt buộc:

1. BACKUP & UAT. Chạy `database/report_migrations/01_request_catalog_expansion_REVIEW_BEFORE_RUN.sql` bằng role DBA sau khi rà soát quyền và audit.
2. Nếu dùng các mã thuộc bảng lựa chọn mới, đăng ký INACTIVE qua `database/report_migrations/03_business_menu_registration_DBA_REVIEW_ONLY.sql`. Mã đã có sẵn giữ nguyên; tên/mẫu không được sửa trái lịch sử.
3. Rà soát kỹ và áp dụng `database/report_migrations/04_approved_actor_resolvers_DBA_REVIEW_ONLY.sql` để mở rộng các actor slot hợp lệ (`HR_MANAGER`, `CISO`, `LEGAL`, `EXECUTOR_FINANCE`...). Migration chỉ sửa allowlist của DB guard, **không cấp quyền tự động**. Kiểm thử các release P0 cũ sau khi thay đổi.
4. POLICY_ADMIN lập draft release theo `docs/APPROVAL_MENU_POLICY_DRAFTS.json`; thay `actor_bindings.departments` rỗng bằng phòng ban và ID user có **role membership hợp lệ**. Điều chỉnh tuyến trong draft theo thẩm quyền ký duyệt thực tế, sau đó validate & publish.
5. OPS_ADMIN kích hoạt loại đơn và cấp role `REQUESTER` theo department/type. Kiểm thử reject/needs-info/approve/execute/accept và scope bằng các user tách biệt trước khi dùng production.
6. Kiểm tra read-only: ` .\.venv\Scripts\python.exe check_approval_menu_readonly.py `.

## Quy tắc phân quyền và giới hạn

- Mẫu A: phê duyệt xong hoàn thành; B: duyệt + executor; C: duyệt + executor + acceptor.
- Nhãn trọng số 1–5 chỉ là dữ liệu mô tả trong menu, **không cấp quyền** và **không tự kích hoạt AI Auto-Approve**. Plan có mâu thuẫn cho auto-approve ở template B; giữ phê duyệt thủ công cho đến khi có thiết kế/kiểm thử an toàn riêng.
- Hỗ trợ mặc định tối đa ba bước duyệt tuần tự. Parallel consensus, 4 executor xử lý đồng thời, quy trình HR/IT tích hợp hệ ngoài thực sự, AI tự duyệt và cập nhật HRIS chưa được hoàn thành bằng patch này.
- Phê duyệt theo quyền/thẩm quyền luôn dựa trên bản config PUBLISHED và account role tại thời điểm xử lý. Không tin tham số role, approver_id, request_code do frontend gửi.
- Các ví dụ tuyến trong `APPROVAL_MENU_POLICY_DRAFTS.json` là **đề xuất cấu hình kỹ thuật**, không phải chứng nhận đã có người duyệt phù hợp trên Supabase của bạn.

## Chạy ở Windows CMD

Giải nén Patch vào `D:\Đồ án\` (bên trong có `DATN/`). Sao lưu và xem `git status` trước khi cập nhật. Không xóa hoặc ghi đè `.env`.

```cmd
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe -m unittest discover -s tests_business -v
.\.venv\Scripts\python.exe -m unittest discover -s tests_report -v
start_backend_local.cmd
```

Terminal Frontend:

```cmd
cd /d "D:\Đồ án\DATN\web_client"
npm ci
npm test
npm run build
npm run dev -- --host 127.0.0.1
```

Mở `http://127.0.0.1:5173`, đăng nhập tài khoản có REQUESTER, nhấn **Tạo yêu cầu**. Các mục chưa đủ điều kiện sẽ có nhãn **Chưa kích hoạt** và không cho gửi.
