# 2.2. PHÂN TÍCH VÀ MÔ HÌNH HOÁ QUY TRÌNH NGHIỆP VỤ

## 2.2.1. Quy trình tổng thể quản lý vòng đời yêu cầu

EAS chuẩn hoá mọi loại yêu cầu theo ba **mẫu vòng đời** (lifecycle). Mẫu vòng đời chỉ mô tả **hình dạng** quy trình, tức là có bước thực hiện hay không và có bước nghiệm thu hay không. Số cấp duyệt và mức rủi ro được cấu hình riêng (xem Bảng 1.2).

- **Mẫu A — chỉ phê duyệt.** Yêu cầu hoàn tất ngay khi cấp duyệt cuối đồng ý. Ví dụ: nghỉ phép, làm việc từ xa, đặt phòng họp, thanh toán chi phí.
- **Mẫu B — phê duyệt rồi thực hiện.** Sau khi duyệt, bộ phận chuyên môn nhận việc và nộp kết quả; hồ sơ hoàn tất khi nộp kết quả. Ví dụ: cấp quyền truy cập, cấp văn phòng phẩm, tạm ứng, đề nghị mua sắm.
- **Mẫu C — phê duyệt, thực hiện và nghiệm thu.** Sau khi người thực hiện nộp kết quả, một người **khác người thực hiện** kiểm tra và chấp nhận hoặc yêu cầu làm lại. Ví dụ: mua sắm tài sản, cấp máy tính, duyệt hợp đồng, cấp quyền dữ liệu nhạy cảm. Với mẫu C, hồ sơ bắt buộc có số tiền (`amount_vnd`) để phục vụ kiểm soát.

Cấu hình thực tế ngày 04/11/2026 có **58 loại yêu cầu đang hoạt động**:
- 9 loại mẫu A;
- 27 loại mẫu B;
- 22 loại mẫu C.

Bảng 2.4 liệt kê đầy đủ; dữ liệu trích từ phiên bản quy chế đang hiệu lực của từng loại.

**Bảng 2.4. Danh mục loại yêu cầu đang hoạt động theo mẫu vòng đời**

| Mẫu | Mã | Tên loại | Trọng số | Số cấp (theo luật) | Thực hiện | Nghiệm thu | SLA duyệt (giờ) |
|---|---|---|---|---|---|---|---|
| A | `ATTENDANCE_ADJUSTMENT` | Điều chỉnh chấm công | 2 | 1 | — | — | 24 |
| A | `EXPENSE_CLAIM` | Thanh toán chi phí | 3 | 2–3 | — | — | 24 |
| A | `LEAVE` | Nghỉ phép | 1 | 1–2 | — | — | 24 |
| A | `LEAVE_SPECIAL` | Nghỉ phép đặc biệt | 2 | 2–3 | — | — | 24 |
| A | `REFUND_COMPENSATION` | Hoàn tiền / Đền bù | 2 | 1 | — | — | 24 |
| A | `ROOM_BOOKING` | Đặt phòng họp | 1 | 1 | — | — | 8 |
| A | `SPECIAL_DISCOUNT` | Phê duyệt chiết khấu thương mại đặc biệt | 3 | 3 | — | — | 24 |
| A | `VISITOR_SECURITY_PASS` | Thẻ an ninh khách & đối tác ra vào | 1 | 1 | — | — | 12 |
| A | `WFH_REQ` | Làm việc từ xa (WFH) | 1 | 1 | — | — | 12 |
| B | `ACCESS` | Cấp tài khoản & quyền truy cập | 2 | 1–2 | CNTT | — | 24 |
| B | `ACCESS_FACILITY` | Cấp thẻ ra vào | 2 | 2 | Cơ sở vật chất | — | 12 |
| B | `ADVANCE_LARGE` | Tạm ứng dự án lớn (>50tr) | 4 | 3 | Tài chính | — | 72 |
| B | `ADVANCE_MEDIUM` | Tạm ứng chi phí (10-50tr) | 3 | 2 | Tài chính | — | 48 |
| B | `ADVANCE_SMALL` | Tạm ứng chi phí (<10tr) | 2 | 2 | Tài chính | — | 24 |
| B | `BUSINESS_TRIP` | Đăng ký đi công tác | 3 | 2–3 | Hành chính | — | 24 |
| B | `DATA_UAT_EXPORT` | Trích xuất dữ liệu / UAT | 3 | 2 | Kỹ thuật | — | 24 |
| B | `DISCIPLINE_REQ` | Đề xuất kỷ luật | 4 | 3 | Nhân sự | — | 24 |
| B | `DOCUMENT_SEAL` | Đóng dấu / ký văn bản | 2 | 2 | Hành chính | — | 24 |
| B | `FLASH_SALE_VOUCHER` | Flash Sale / Voucher | 4 | 2 | Marketing | — | 24 |
| B | `HR_CERTIFICATE` | Xin giấy xác nhận công tác / thu nhập | 1 | 1 | Nhân sự | — | 24 |
| B | `INTERNAL_TRANSFER` | Điều chuyển nội bộ | 3 | 3 | Nhân sự | — | 36 |
| B | `IT_SUPPORT` | Yêu cầu hỗ trợ IT | 1 | 1 | CNTT | — | 8 |
| B | `NDA_PRIVACY_CLEARANCE` | Thẩm định NDA & chia sẻ dữ liệu đối tác | 2 | 2 | Pháp chế | — | 24 |
| B | `OFFICE_SUPPLIES` | Cấp văn phòng phẩm | 1 | 1 | Hành chính | — | 24 |
| B | `OVERTIME_REQ` | Đăng ký làm thêm giờ (OT) | 2 | 1 | Nhân sự | — | 24 |
| B | `POLICY_ISSUANCE` | Ban hành quy chế nội bộ | 4 | 3 | Pháp chế | — | 24 |
| B | `PROMOTION_REQ` | Đề xuất thăng chức | 4 | 3 | Nhân sự | — | 24 |
| B | `PURCHASE_REQUEST` | Đề nghị mua sắm | 3 | 1–3 | Mua sắm | — | 24 |
| B | `REIMBURSEMENT` | Quyết toán tạm ứng | 2 | 2 | Tài chính | — | 48 |
| B | `REWARD_REQ` | Đề xuất khen thưởng | 3 | 2–3 | Tài chính | — | 24 |
| B | `SALARY_ADJUSTMENT` | Điều chỉnh lương | 5 | 4 | Nhân sự | — | 24 |
| B | `SALARY_ADVANCE` | Ứng lương | 2 | 2 | Tài chính | — | 24 |
| B | `SUPPLIER_ONBOARDING` | Thẩm định & phê duyệt nhà cung cấp mới | 3 | 3 | Mua sắm | — | 36 |
| B | `TAX_INVOICE_ISSUE` | Phát hành / điều chỉnh hóa đơn VAT | 1 | 1 | Tài chính | — | 16 |
| B | `TRAINING_COURSE` | Đăng ký đào tạo & chứng chỉ nghề nghiệp | 2 | 2 | Nhân sự | — | 24 |
| B | `WAREHOUSE_TRANSFER` | Luân chuyển kho | 3 | 1 | Kho | — | 24 |
| C | `ASSET_DISPOSAL` | Thanh lý & hủy tài sản cố định | 4 | 4 | Tài sản | QL trực tiếp | 48 |
| C | `BUDGET_REALLOCATION` | Điều chuyển & bổ sung ngân sách liên bộ phận | 5 | 5 | Tài chính | Người yêu cầu | 72 |
| C | `CONTRACT_APPROVAL` | Duyệt hợp đồng | 5 | 3 | Tài chính | Pháp chế | 24 |
| C | `CROSS_DEPT_SUPPORT` | Hỗ trợ liên phòng ban | 2 | 2 | Hành chính | Người yêu cầu | 24 |
| C | `EMPLOYEE_ONBOARDING` | Tiếp nhận nhân viên mới | 3 | 2 | Nhân sự | QL trực tiếp | 24 |
| C | `EQUIPMENT` | Mua sắm thiết bị / tài sản | 3 | 1–3 | Tài sản | Người yêu cầu | 24 |
| C | `EQUIPMENT_BORROW` | Mượn thiết bị / đồ dùng | 2 | 2 | Tài sản | Người yêu cầu | 12 |
| C | `FACILITY_REPAIR` | Sửa chữa sự cố văn phòng | 2 | 1 | Cơ sở vật chất | QL trực tiếp | 12 |
| C | `FEATURE_RELEASE` | Feature Request / Release | 3 | 2 | Kỹ thuật | QL dự án | 24 |
| C | `LAPTOP_PROVISION` | Cấp máy tính / thiết bị làm việc | 2 | 1 | CNTT | Người yêu cầu | 24 |
| C | `MARKETING_CAMPAIGN` | Ngân sách chiến dịch Marketing & Sự kiện | 4 | 4 | Marketing | Người yêu cầu | 48 |
| C | `PROD_DATA_ACCESS` | Cấp quyền Dữ liệu nhạy cảm/Server | 5 | 3 | CNTT | CTO | 24 |
| C | `PROJECT_INITIATION` | Đề xuất khởi tạo dự án | 4 | 4 | Kỹ thuật | QL dự án | 24 |
| C | `RECRUITMENT_REQ` | Yêu cầu tuyển dụng nhân sự | 4 | 4 | Nhân sự | QL trực tiếp | 48 |
| C | `RESIGNATION` | Thôi việc / Bàn giao | 4 | 3 | Nhân sự | Người yêu cầu | 168 |
| C | `RESOURCE_REVOKE` | Thu hồi tài khoản / thiết bị | 2 | 1 | CNTT | QL trực tiếp | 24 |
| C | `SAAS_LICENSE_BUY` | Mua bản quyền phần mềm mới | 3 | 3 | Mua sắm | QL trực tiếp | 72 |
| C | `SECURITY_INCIDENT_HOTFIX` | Khắc phục sự cố bảo mật & Hotfix khẩn cấp | 5 | 5 | Kỹ thuật | CTO | 12 |
| C | `SERVER_FIREWALL` | Cấp Server / Firewall | 3 | 3 | CNTT | CTO | 24 |
| C | `TASK_REQUEST` | Yêu cầu xử lý công việc | 1 | 1 | Hành chính | Người yêu cầu | 24 |
| C | `VEHICLE_BOOKING` | Mượn xe công vụ | 2 | 1 | Hành chính | Người yêu cầu | 24 |
| C | `VENDOR_PAYMENT` | Thanh toán Hợp đồng Vendor | 5 | 3 | Tài chính | QL trực tiếp | 72 |

*Ghi chú.*
- "Số cấp" là số người duyệt nhỏ nhất – lớn nhất trên các luật của loại đó. Ví dụ, `PURCHASE_REQUEST` cần 1 cấp khi dưới 5 triệu, 2 cấp từ 5 triệu và 3 cấp khi trên 50 triệu.
- "Trọng số" là mức rủi ro mặc định 1–5. Chỉ loại mẫu A có trọng số ≤ 2 mới được xét tự duyệt.
- "SLA duyệt" là thời hạn của **mỗi** bước duyệt.

## 2.2.2. Quy trình tạo, chỉnh sửa và gửi yêu cầu

**Bước 1 — Chọn loại.** Nhân viên chọn một trong **12 nhóm lớn theo mục đích sử dụng** (`eas.request_group`), rồi chọn một trong **61 mục yêu cầu nhỏ trên menu** (`eas.request_menu_item`, gồm 56 loại trực tiếp và 5 mục đặt sẵn `preset` như Đi muộn, Về sớm, Quên chấm công, Nghỉ phép có lương `CO_LUONG`, Nghỉ không lương `KHONG_LUONG`), hoặc tìm trực tiếp theo tên. Một loại bị **khoá kèm lý do** nếu:
- loại chưa có phiên bản quy chế được ban hành;
- loại đang tạm ngưng;
- nhân viên không có quyền tạo loại đó cho phòng ban của mình;
- hệ thống nghiệp vụ mà loại đó phụ thuộc đang bị tắt (máy chủ trả mã `409 INTEGRATION_UNAVAILABLE` nếu gọi thẳng).

**Bước 2 — Soạn nháp.**
- Hệ thống tạo hồ sơ ở trạng thái `DRAFT` với mã `REQ-…`.
- Biểu mẫu sinh tự động theo `form_schema` của phiên bản quy chế.
- Mỗi lần lưu nháp gửi kèm số phiên bản đang xem (`expected_version`). Nếu người khác (hoặc tab khác) đã lưu trước, hệ thống trả `409 VERSION_CONFLICT` thay vì ghi đè.

**Bước 3 — Đính kèm.** Tệp được chấp nhận khi thoả cả bốn điều kiện:
- kích thước ≤ 10 MB;
- tên tệp an toàn;
- nội dung thật là PDF, PNG hoặc JPEG, kiểm bằng chữ ký đầu tệp (magic bytes), không tin phần mở rộng;
- quét ClamAV không phát hiện mã độc.

Tệp hợp lệ được đổi tên thành UUID, lưu vào kho Supabase Storage riêng tư cùng mã băm SHA-256.

**Bước 4 — Xem trước tuyến duyệt.** Trước khi gửi, người dùng xem được tuyến duyệt dự kiến: bao nhiêu bước, ai duyệt. Tuyến này được tính theo dữ liệu đang nhập (`/requests/route-preview`).

**Bước 5 — Gửi.** Toàn bộ các việc sau diễn ra trong **một giao dịch nguyên tử**:
- kiểm tra dữ liệu;
- tạo phiên bản hồ sơ bất biến (`request_revision`, kèm mã băm nội dung);
- chụp lại phiên bản quy chế đang áp dụng;
- định tuyến;
- tạo phiên quy trình và các bước duyệt;
- mở chặng SLA bước 1;
- ghi kiểm toán và sự kiện.

Nếu bất kỳ việc nào lỗi thì không có thay đổi nào được lưu. Hồ sơ chuyển sang `PENDING_APPROVAL`.

## 2.2.3. Quy trình kiểm tra quy định nội bộ và xác định cấp phê duyệt

Động cơ luật (BRE, `api_core/domain/routing.py`) xét các luật của phiên bản quy chế **theo thứ tự ưu tiên tăng dần**. Luật đầu tiên có điều kiện đúng được chọn; nếu không có luật nào khớp thì dùng luật mặc định ở cuối. Có bốn loại điều kiện:
- `amount_gt` — số tiền lớn hơn ngưỡng;
- `amount_gte` — số tiền lớn hơn hoặc bằng ngưỡng;
- `days_gt` — số ngày lớn hơn ngưỡng (tính từ trường số ngày, hoặc từ ngày bắt đầu và ngày kết thúc);
- `app_code_in` — ứng dụng được yêu cầu thuộc danh sách nhạy cảm.

Luật được chọn trả về danh sách **vị trí** người duyệt (1–5 vị trí), ví dụ `DIRECT_MANAGER → FINANCE → DIRECTOR`. Mỗi vị trí được phân giải thành người cụ thể:
- quản lý trực tiếp lấy từ hồ sơ nhân sự;
- các vị trí khác lấy theo bảng gán người của phòng ban trong quy chế.

Sau đó hệ thống kiểm **tách nhiệm**:
- người yêu cầu không có trong danh sách duyệt;
- các người duyệt khác nhau;
- người thực hiện không phải người yêu cầu và không phải người duyệt;
- người nghiệm thu khác người thực hiện.

Nếu không thoả (sau khi đã tự động điều chỉnh bước `DIRECT_MANAGER` cho lãnh đạo cao nhất bằng `TOP_LEVEL_APPROVER` / `TOP_LEVEL_SKIPPED`, leo thang bước tự duyệt lên quản lý trực tiếp `SOD_ESCALATED` và gộp bước liền trùng người `DUPLICATE_SKIPPED` trong `api_core/domain/routing.py`), hoặc tuyến rỗng, hồ sơ không được gửi (`409 ROUTE_CONFIGURATION_INVALID`).

## 2.2.4. Quy trình phê duyệt đa cấp

**Tuần tự từng bước.** Các bước duyệt thực hiện tuần tự; tại mỗi thời điểm chỉ có một bước ở trạng thái `ACTIVE`. Người duyệt:
- nhận thông báo trong ứng dụng;
- mở hồ sơ để xem nội dung, tệp đính kèm, lịch sử, hạn SLA và tóm tắt AI;
- đưa ra quyết định.

**Khi chấp thuận** (cả bốn việc thuộc cùng giao dịch):
1. Hệ thống đóng chặng SLA của bước hiện tại.
2. Nếu còn bước sau, hệ thống kích hoạt bước sau. Nếu người duyệt kế tiếp đã ủy quyền cho người khác, hoặc đang vắng mặt và không có ủy quyền, bước được chuyển cho người được ủy quyền hoặc quản lý trực tiếp của họ. Việc chuyển được ghi kiểm toán.
3. Nếu là bước cuối của **mẫu A**, hồ sơ chuyển sang `COMPLETED` (với đơn nghỉ phép có lương `LEAVE` `leave_kind = CO_LUONG`, hệ thống gọi `POST /mock-api/v1/hr/leave-usages` sang HRM để trừ quỹ phép; với đơn mượn phòng họp/xe/thiết bị, hệ thống gọi Mock Systems API giữ chỗ theo nguyên tắc **duyệt trước thắng**, riêng thành viên **Ban Giám đốc `BOD` được ưu tiên thu hồi** phần của nhân viên thường và chuyển đơn nhân viên sang `REJECTED` kèm thông báo `RESOURCE_PREEMPTED`, hết hạn thì worker tự động trả lại qua API).
4. Nếu là bước cuối của **mẫu B/C**, hệ thống:
   - xác nhận người thực hiện (người duyệt cuối có thể chỉ định trong danh sách được phép);
   - tạo lượt thực hiện đầu tiên;
   - mở chặng SLA thực hiện;
   - chuyển hồ sơ sang `READY_FOR_EXECUTION`.

**Tự duyệt bởi AI.** Ngay sau khi hồ sơ được gửi, tiến trình nền xét tự duyệt (§1.3.4). Nếu đủ điều kiện, bước được ký bởi tài khoản AI hệ thống. Người duyệt có quyền thu hồi trong 24 giờ; khi thu hồi, hồ sơ quay về duyệt thủ công.

## 2.2.5. Quy trình bổ sung thông tin, từ chối và xử lý ngoại lệ

- **Yêu cầu bổ sung.**
  - Người duyệt phải ghi lý do (10–2000 ký tự).
  - Phiên quy trình hiện tại bị thay thế (`SUPERSEDED`); các bước chưa tới bị bỏ qua (`SKIPPED`).
  - Hồ sơ chuyển sang `NEEDS_INFO`. Các tệp đã nộp được chép về bản nháp.
  - Người yêu cầu sửa và **nộp lại**. Hệ thống tạo phiên bản mới, định tuyến lại và **duyệt lại từ bước 1**, vì nội dung đã thay đổi nên mọi cấp phải xem lại.
- **Từ chối.** Bắt buộc lý do. Hồ sơ chuyển sang `REJECTED`, là trạng thái cuối: không sửa, không nộp lại được. Người yêu cầu muốn tiếp tục thì phải lập hồ sơ mới.
- **Rút đơn.**
  - Được rút khi hồ sơ ở `DRAFT`, `NEEDS_INFO` hoặc `PENDING_APPROVAL`, tức là chưa có quyết định duyệt cuối. Bắt buộc ghi lý do; phiên quy trình đang chạy (nếu có) chuyển `CANCELLED` và các bước còn lại bị bỏ qua (`api_core/workflow/service.py:2865`).
  - Nếu người yêu cầu rút đúng lúc người duyệt cuối đang ký, cơ chế khoá dòng bảo đảm chỉ một thao tác thành công; thao tác còn lại nhận `409 REQUEST_STATE_CONFLICT`.
- **Điều chuyển.** Quản trị vận hành có thể đổi người duyệt, người thực hiện hoặc người nghiệm thu. Thao tác này:
  - bắt buộc có lý do;
  - kiểm người mới đang hoạt động, đúng vai trò và không vi phạm tách nhiệm;
  - giữ nguyên hạn SLA;
  - ghi kiểm toán đủ giá trị cũ, giá trị mới và lý do.

## 2.2.6. Quy trình thực hiện và nghiệm thu yêu cầu

1. **Nhận việc.** Người thực hiện được giao nhấn "Nhận việc"; lượt thực hiện chuyển `READY → RUNNING`, hồ sơ chuyển `IN_PROGRESS`. Nếu không thể nhận (quá tải, thiếu điều kiện), người thực hiện gửi báo cáo "không thể nhận" để quản trị vận hành điều phối.
2. **Báo vướng.** Trong khi làm, người thực hiện ghi nhận vướng mắc (ví dụ hết hàng). Báo vướng **không** tự đổi người và **không** dừng đồng hồ SLA. Việc kéo dài hạn phải do người có thẩm quyền quyết định qua điều chuyển.
3. **Nộp kết quả.** Gồm ghi chú (10–4000 ký tự), mã tham chiếu (ví dụ số phiếu nhập, mã tài khoản đã cấp) và tệp bằng chứng.
   - Mẫu B: hồ sơ hoàn tất (`COMPLETED`).
   - Mẫu C: hồ sơ chuyển `WAITING_FOR_ACCEPTANCE`, đồng thời mở chặng SLA nghiệm thu.
4. **Nghiệm thu** (mẫu C).
   - **Chấp nhận:** hồ sơ hoàn tất.
   - **Yêu cầu làm lại** (bắt buộc lý do): lượt hiện tại đóng với kết quả `REWORK`, hệ thống tạo **lượt thực hiện mới** ở trạng thái `READY` và hồ sơ quay về `READY_FOR_EXECUTION`. Mỗi lượt có lịch sử và SLA riêng, giúp đo được số lần làm lại.

## 2.2.7. Quy trình ghi nhận lịch sử và truy vết yêu cầu

Mọi thao tác thay đổi dữ liệu đều ghi một sự kiện kiểm toán **trong cùng giao dịch** với thay đổi đó: tạo nháp, lưu nháp, đính kèm, gửi, duyệt, từ chối, bổ sung, rút, nhận việc, báo vướng, nộp, nghiệm thu, điều chuyển, tự duyệt và thu hồi tự duyệt. Cách tạo một sự kiện:

1. Khoá "đầu chuỗi" của hồ sơ (`audit_head`). Mỗi hồ sơ có một chuỗi riêng; thao tác quản trị có chuỗi `ADMIN` riêng.
2. Chuẩn hoá nội dung sự kiện theo RFC 8785 (Canonical JSON), cộng chuẩn hoá Unicode NFC.
3. Tính `hash = SHA-256(prev_hash ‖ nội dung chuẩn hoá)`.
4. Ghi sự kiện và cập nhật đầu chuỗi.

Bảng sự kiện là chỉ-ghi-thêm. Kiểm toán viên gọi chức năng kiểm chứng để tính lại toàn chuỗi. Bất kỳ bản ghi nào bị sửa, chèn hay xoá đều làm chuỗi gãy và bị chỉ ra vị trí.

Ngoài sự kiện kiểm toán, hệ thống còn giữ ba loại bản ghi bất biến:
- các **phiên bản hồ sơ** (`request_revision`), kèm mã băm nội dung;
- các **quyết định** (`approval_decision`, `acceptance_decision`);
- các **báo cáo vướng** (`execution_issue`).

Nhờ vậy, có thể tái dựng chính xác ai đã quyết định gì, trên phiên bản nội dung nào và theo phiên bản quy chế nào.
