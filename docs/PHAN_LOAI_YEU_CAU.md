# Phân loại yêu cầu: nhóm lớn → loại nhỏ (04/11/2026)

## 1. Vấn đề

Đang có 58 loại yêu cầu hoạt động, chia vào 10 nhóm theo **phòng ban xử lý** (Tài chính, Nhân sự, Hành chính & Kho…). Cách chia này gây khó cho người gửi:

- Các việc cùng bản chất bị tách ra. Ví dụ "Đi công tác" nằm ở Nhân sự, còn "Nghỉ phép" nằm ở Nghỉ phép & Chấm công.
- Các loại người dùng nghĩ là riêng biệt lại bị giấu thành giá trị của một trường. Ví dụ "Đi muộn" và "Về sớm" là lựa chọn trong đơn Điều chỉnh chấm công.
- Không có loại "Nghỉ không lương".
- Tệp `approval_menu.json` (bản kế hoạch cũ) còn xếp "Nghỉ phép" vào nhóm "Tài chính & Mua sắm".

## 2. Tiêu chí xếp nhóm

Một nhóm lớn gom các yêu cầu có **cùng câu hỏi người gửi đặt ra**. Ví dụ: "tôi sẽ vắng mặt", "tôi cần mượn tạm rồi trả", "tôi cần được cấp hẳn", "tôi cần tiền".

Nhóm **không** theo phòng duyệt. Người duyệt vẫn do tuyến duyệt của từng loại quyết định.

## 3. Danh mục

12 nhóm. Loại nhỏ mới là một **lựa chọn đặt sẵn** của loại có sẵn, không phải quy trình mới.

| # | Nhóm lớn (mã) | Điểm chung | Loại nhỏ (mã loại; *đặt sẵn* nếu có) |
|---|---|---|---|
| 1 | **Vắng mặt** (`ABSENCE`) | Người gửi không có mặt tại nơi làm việc trong một khoảng giờ hoặc ngày | Đi muộn (`ATTENDANCE_ADJUSTMENT`, *change_type = Đi muộn*); Về sớm (*Về sớm*); Nghỉ phép có lương (`LEAVE`, *leave_kind = CO_LUONG*); Nghỉ không lương (`LEAVE`, *KHONG_LUONG*); Nghỉ chế độ: cưới, tang, thai sản, ốm dài ngày (`LEAVE_SPECIAL`); Đi công tác (`BUSINESS_TRIP`); Làm việc từ xa (`WFH_REQ`) |
| 2 | **Chấm công & giờ làm** (`WORKTIME`) | Sửa hoặc bổ sung số giờ công | Quên chấm công (`ATTENDANCE_ADJUSTMENT`, *Quên chấm công*); Làm thêm giờ (`OVERTIME_REQ`) |
| 3 | **Mượn & đặt chỗ** (`BORROW`) | Dùng tạm có thời hạn, hết hạn trả lại kho | Đặt phòng họp (`ROOM_BOOKING`); Mượn xe công vụ (`VEHICLE_BOOKING`); Mượn thiết bị / đồ dùng (`EQUIPMENT_BORROW`) |
| 4 | **Cấp phát & quyền truy cập** (`PROVISION`) | Được cấp hẳn tài sản hoặc quyền để làm việc, hoặc bị thu hồi | Cấp máy tính / thiết bị (`LAPTOP_PROVISION`); Cấp văn phòng phẩm (`OFFICE_SUPPLIES`); Cấp tài khoản & quyền (`ACCESS`); Quyền dữ liệu nhạy cảm / server (`PROD_DATA_ACCESS`); Cấp server / firewall (`SERVER_FIREWALL`); Thẻ ra vào (`ACCESS_FACILITY`); Thẻ khách (`VISITOR_SECURITY_PASS`); Thu hồi tài khoản / thiết bị (`RESOURCE_REVOKE`) |
| 5 | **Tạm ứng & thanh toán** (`PAYMENT`) | Tiền chi ra hoặc hoàn lại | Tạm ứng < 10 triệu (`ADVANCE_SMALL`); 10–50 triệu (`ADVANCE_MEDIUM`); > 50 triệu (`ADVANCE_LARGE`); Ứng lương (`SALARY_ADVANCE`); Quyết toán tạm ứng (`REIMBURSEMENT`); Thanh toán chi phí (`EXPENSE_CLAIM`); Hoàn tiền / đền bù (`REFUND_COMPENSATION`); Thanh toán hợp đồng vendor (`VENDOR_PAYMENT`); Phát hành / điều chỉnh hoá đơn VAT (`TAX_INVOICE_ISSUE`) |
| 6 | **Mua sắm & ngân sách** (`PROCUREMENT`) | Mua mới hoặc thay đổi ngân sách | Đề nghị mua sắm (`PURCHASE_REQUEST`); Mua thiết bị / tài sản (`EQUIPMENT`); Mua bản quyền phần mềm (`SAAS_LICENSE_BUY`); Duyệt nhà cung cấp mới (`SUPPLIER_ONBOARDING`); Điều chuyển ngân sách (`BUDGET_REALLOCATION`) |
| 7 | **Nhân sự & chế độ** (`PEOPLE`) | Quyết định về một nhân sự trong vòng đời làm việc | Tuyển dụng (`RECRUITMENT_REQ`); Tiếp nhận nhân viên mới (`EMPLOYEE_ONBOARDING`); Điều chuyển nội bộ (`INTERNAL_TRANSFER`); Thăng chức (`PROMOTION_REQ`); Điều chỉnh lương (`SALARY_ADJUSTMENT`); Khen thưởng (`REWARD_REQ`); Kỷ luật (`DISCIPLINE_REQ`); Đào tạo & chứng chỉ (`TRAINING_COURSE`); Giấy xác nhận công tác / thu nhập (`HR_CERTIFICATE`); Thôi việc / bàn giao (`RESIGNATION`) |
| 8 | **Hỗ trợ & sự cố** (`SUPPORT`) | Có thứ đang hỏng hoặc gặp sự cố cần xử lý | Hỗ trợ IT (`IT_SUPPORT`); Sửa chữa sự cố văn phòng (`FACILITY_REPAIR`); Sự cố bảo mật & hotfix (`SECURITY_INCIDENT_HOTFIX`) |
| 9 | **Công việc & dự án** (`WORK`) | Giao hoặc khởi tạo một đầu việc có kế hoạch | Yêu cầu xử lý công việc (`TASK_REQUEST`); Hỗ trợ liên phòng ban (`CROSS_DEPT_SUPPORT`); Khởi tạo dự án (`PROJECT_INITIATION`); Feature request / release (`FEATURE_RELEASE`); Trích xuất dữ liệu / UAT (`DATA_UAT_EXPORT`) |
| 10 | **Văn bản & pháp chế** (`LEGAL`) | Văn bản ràng buộc pháp lý cần thẩm định hoặc ký | Duyệt hợp đồng (`CONTRACT_APPROVAL`); Đóng dấu / ký văn bản (`DOCUMENT_SEAL`); NDA & chia sẻ dữ liệu (`NDA_PRIVACY_CLEARANCE`); Ban hành quy chế (`POLICY_ISSUANCE`) |
| 11 | **Kinh doanh & marketing** (`SALES`) | Chính sách bán hàng và quảng bá | Chiết khấu đặc biệt (`SPECIAL_DISCOUNT`); Flash sale / voucher (`FLASH_SALE_VOUCHER`); Chiến dịch marketing & sự kiện (`MARKETING_CAMPAIGN`) |
| 12 | **Kho & tài sản cố định** (`ASSET`) | Thay đổi vị trí hoặc trạng thái tài sản của công ty | Luân chuyển kho (`WAREHOUSE_TRANSFER`); Thanh lý tài sản (`ASSET_DISPOSAL`) |

Tổng cộng **61 loại nhỏ trên menu**:

- 56 loại hiện trực tiếp: 58 loại đang hoạt động, trừ `ATTENDANCE_ADJUSTMENT` và `LEAVE`.
- 5 lựa chọn đặt sẵn của hai loại đó: Đi muộn, Về sớm, Quên chấm công, Nghỉ có lương, Nghỉ không lương.

## 4. Mô hình dữ liệu

| Đối tượng | Nội dung |
|---|---|
| `eas.request_group` (mới) | `code`, `name`, `description`, `sort_order`. 12 dòng ở §3 |
| `eas.request_type.category` | Đổi thành khoá ngoại tới `request_group.code`. Đây là **nhóm chính** của loại, dùng cho báo cáo và lọc. Bỏ CHECK 10 mã cũ |
| `eas.request_menu_item` (mới) | `code`, `group_code`, `type_code`, `label`, `preset` (jsonb), `sort_order`, `is_active`. Mỗi dòng là một loại nhỏ trên menu. `preset` là các trường được điền sẵn và khoá lại, ví dụ `{"change_type": "Đi muộn"}` |
| Biểu mẫu `LEAVE` | Thêm trường `leave_kind` ∈ {`CO_LUONG`, `KHONG_LUONG`}, bắt buộc. Đơn có lương ghi vào trạng thái làm việc là `PAID_LEAVE`, không lương là `UNPAID_LEAVE`, và chỉ đơn có lương bị trừ quỹ phép (tài liệu tích hợp §4.1) |

- Một loại có thể xuất hiện ở nhiều nhóm qua các lựa chọn đặt sẵn. Ví dụ `ATTENDANCE_ADJUSTMENT` có mặt ở "Vắng mặt" (đi muộn, về sớm) và ở "Chấm công & giờ làm" (quên chấm công).
- Giá trị đặt sẵn chỉ giúp điền nhanh và được khoá trên giao diện. Máy chủ không cần kiểm tra riêng, vì mọi giá trị đặt sẵn đều là giá trị hợp lệ của biểu mẫu và vẫn được kiểm tra như dữ liệu nhập tay.
- `catalog_v2.json`, `catalogV2.js` và `approval_menu.json` không còn là nguồn của menu. Menu đọc từ DB. Tệp `approval_menu.json` (bản kế hoạch cũ, sai nhóm) bị xoá. `catalog_v2.json` chỉ còn là dữ liệu khởi tạo, và nhóm trong đó được cập nhật theo §3.

## 5. Giao diện người gửi

1. Màn hình đầu: 12 thẻ nhóm lớn. Mỗi thẻ có tên, một dòng mô tả điểm chung và số loại bên trong.
2. Chọn một nhóm: hiện danh sách loại nhỏ. Mỗi dòng có tên, tuyến duyệt và tình trạng sẵn sàng (lý do nếu bị khoá).
3. Chọn một loại nhỏ: mở biểu mẫu. Trường đặt sẵn hiển thị nhưng không cho sửa.
4. Có ô tìm kiếm trên toàn bộ loại nhỏ, không phân biệt nhóm.

## 6. Đã thực hiện (04/11/2026)

Tài liệu này được viết trước, sau đó dự án được sửa theo.

- Migration `17_external_systems_via_api.sql` tạo 12 nhóm và 61 loại nhỏ trên menu, đổi `category` của 66 loại, thêm `leave_kind`. Nhóm cũ được lưu vào `eas_archive.dropped_column_value`, rollback trả lại đúng giá trị.
- API `GET /api/v1/meta/request-type-forms` trả `groups` và `approval_menu` (kèm `menu_code` và `preset`) đọc từ DB. Trước khi có migration 17, API dùng tệp khởi tạo.
- Giao diện: 12 thẻ nhóm, chọn nhóm thì hiện loại nhỏ, ô tìm trên toàn bộ loại, trường đặt sẵn bị khoá.
- Test `TaxonomyTests` bảo đảm `catalog_v2.json` khớp mapping trong migration 17.

## 7. Thứ tự thực hiện (kế hoạch ban đầu)

1. Duyệt tài liệu này (xong).
2. Migration `17_external_systems_via_api.sql`, phần phân loại: tạo `request_group`, `request_menu_item`, gán `category` mới, thêm `leave_kind` vào biểu mẫu `LEAVE` (bản phát hành mới).
3. API `GET /api/v1/meta/request-type-forms` trả `groups` và `menu` từ DB.
4. Giao diện chọn theo nhóm, có khoá trường đặt sẵn.
5. Cập nhật `catalog_v2.json` và các test đồng bộ.
