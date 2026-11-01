# BÁO CÁO TOÀN DIỆN AUDIT & NGHIÊN CỨU GIAO DIỆN HỆ THỐNG EAS
## (HỆ THỐNG PHÊ DUYỆT DOANH NGHIỆP — WEB CLIENT & WEB ADMIN)

---

> **Thời điểm lập báo cáo:** Ngày 01 tháng 11 năm 2026  
> **Phạm vi khảo sát:** Cổng nhân viên [Web Client (Port 5173)] và Cổng quản trị [Web Admin (Port 5174)]  
> **Mục tiêu:** Nhận diện toàn bộ các lỗ hổng trải nghiệm người dùng (UX), sai lệch phân quyền giao diện (UI RBAC/SoD), tình trạng rò rỉ trường dữ liệu CSDL / mã lỗi kỹ thuật, và đề xuất lộ trình chuẩn hóa giao diện theo tiêu chuẩn **Frontend UI Engineering**.

---

## 1. TỔNG QUAN ĐỢT AUDIT (EXECUTIVE SUMMARY)

Qua quá trình rà soát chi tiết mã nguồn, phân tích hành vi thực tế của các luồng nghiệp vụ trên cả hai cổng `web_client` và `web_admin`, nhóm kiểm toán ghi nhận:

**Giao diện hiện tại đang mang nặng tư duy "công cụ nội bộ của lập trình viên" (Internal Developer Tool) thay vì một sản phẩm phần mềm doanh nghiệp hoàn thiện (Enterprise-grade SaaS Application).**

Hệ thống đang tồn tại 4 nghịch lý giao diện nghiêm trọng:
1. **Nghịch lý thông tin:** Những thông tin nghiệp vụ cốt lõi mà nhân viên và người duyệt cần để ra quyết định (Tiêu đề đơn, Người gửi, Phòng ban, Hạn xử lý) thì **hoàn toàn không có**.
2. **Nghịch lý phân quyền:** Những dữ liệu kiểm toán nội bộ, chuỗi băm mật mã, sự kiện kỹ thuật mà nhân viên không có quyền/không cần biết thì **lại phơi bày công khai**.
3. **Nghịch lý ngôn ngữ:** Giao diện tràn ngập các tên cột cơ sở dữ liệu (`amount_vnd`, `handover_user_id`), chuỗi JSON thô, chuỗi định danh UUID 36 ký tự và các mã lỗi lập trình tiếng Anh viết hoa.
4. **Nghịch lý tương tác:** Người dùng bị bắt sao chép UUID bằng tay, sửa JSON thô trong ô nhập văn bản, nhập số tiền hàng trăm triệu đồng mà không có dấu phân cách hàng nghìn, và thiếu các hộp thoại xác nhận khi thực hiện thao tác nguy hiểm.

---

## 2. NHÓM 1: "CÁI CẦN XEM ĐƯỢC THÌ LẠI KHÔNG CÓ"
*(Thiếu các thông tin nghiệp vụ thiết yếu cho việc vận hành và ra quyết định)*

### 2.1. Danh sách yêu cầu (`RequestList`) không có Tiêu đề, Người gửi, Phòng ban và Hạn chót
- **Thực trạng phát hiện:**
  - Trong bảng danh sách yêu cầu (`RequestList` tại file `web_client/src/App.jsx`), các cột hiện có chỉ gồm: `Mã yêu cầu` (ví dụ `REQ-2026-001`), `Nghiệp vụ` (chỉ ghi chung chung `Nghỉ phép` hoặc `Cấp quyền`), `Trạng thái` và `Cập nhật`.
  - **Hoàn toàn thiếu vắng 4 trường tối quan trọng:**
    1. **Tiêu đề đơn (Title / Summary):** Không hiển thị lý do tóm tắt (ví dụ: *"Nghỉ phép kết hôn"*, *"Thanh toán hợp đồng Vendor FPT tháng 10"*).
    2. **Người tạo đơn (Requester Name):** Người duyệt mở "Hộp việc phê duyệt" lên không biết ai là người gửi đơn.
    3. **Phòng ban người gửi (Department):** Không biết đơn xuất phát từ phòng ban nào để đối chiếu thẩm quyền ngân sách.
    4. **Hạn xử lý (SLA / Due Date):** Không có chỉ số hạn chót, không biết đơn nào sắp trễ để ưu tiên xử lý trước.
- **Nguyên nhân gốc rễ:**
  - API Backend `GET /api/v1/requests` (hàm `request_list` trong file `api_core/workflow/views.py`) chỉ chọn các cột `id`, `code`, `type_code`, `status`, `lock_version`, `updated_at`, `created_at`. Backend đã bỏ quên việc `JOIN` lấy `u.display_name`, `d.name` và `r.payload->>'title'`, dẫn đến Frontend hoàn toàn không có dữ liệu để hiển thị.
- **Tác động người dùng:** Cấp quản lý hoặc người thực hiện phải click chuột mở từng đơn một cách mò mẫm, gây lãng phí thời gian và dễ bỏ sót các đơn khẩn cấp.

---

### 2.2. Hồ sơ cá nhân (`Profile`) hiển thị mã phòng ban UUID thay vì tên phòng ban
- **Thực trạng phát hiện:**
  - Tại trang Hồ sơ cá nhân (`Profile` trong `web_client/src/components/Admin.jsx`), hệ thống hiển thị dòng chữ:
    ```
    user.username · user.department_id
    ```
    Ví dụ thực tế hiển thị: `lan.ngo · e2b58c79-1142-4f81-a982-127e908bce1a`.
  - Không có thông tin **Tên phòng ban tiếng Việt** (ví dụ: *"Phòng Tài chính - Kế toán"*).
  - Không có thông tin **Chức vụ / Cấp bậc** (Trưởng nhóm, Chuyên viên, Giám đốc).
  - Không có thông tin **Người quản lý trực tiếp (Manager)**.
  - Không có **Email công ty** hay số điện thoại liên hệ nội bộ.
- **Tác động người dùng:** Nhân viên nhìn vào hồ sơ của mình thấy một chuỗi ký tự mã hóa vô nghĩa, không xác nhận được mình đã được gán đúng phòng ban hay chưa.

---

### 2.3. Sơ đồ tổ chức (`Org Chart`) bị khóa chặt trên Web Admin, nhân viên không thể tiếp cận
- **Thực trạng phát hiện:**
  - Thành phần Sơ đồ tổ chức (`OrgChart.jsx`) hiển thị cấu trúc Ban Giám Đốc và 7 phòng ban rất trực quan nhưng hiện tại chỉ được cấu hình trong `rolePolicy.js` cho vai trò `OPS_ADMIN` sở hữu quyền `identity_manage` trên cổng `web_admin`.
  - Trên cổng nhân viên (`web_client`), toàn bộ người dùng thông thường (`REQUESTER`, `APPROVER`, `EXECUTOR`, `ACCEPTOR`) **hoàn toàn không có mục Sơ đồ tổ chức**.
- **Tác động người dùng:** Khi nhân viên muốn làm đơn bàn giao công việc (`handover_user_id`) hoặc muốn biết ai là cấp trên trực tiếp, ai là Trưởng bộ phận của mình để chọn người duyệt hợp lệ, họ không có sơ đồ cây để tra cứu.

---

### 2.4. Tiến trình duyệt không hiển thị các cấp duyệt tiếp theo và người duyệt dự kiến
- **Thực trạng phát hiện:**
  - Trong tab "Tiến trình" (`RequestDetail.jsx`), danh sách bước duyệt chỉ hiển thị những bước đã được kích hoạt hoặc đã đóng. Các cấp duyệt tương lai (ví dụ đơn cần duyệt 3 cấp nhưng mới ở cấp 1) thường không hiển thị rõ cấp 2 và cấp 3 sẽ do chức danh nào/ai thụ lý.
  - Nếu bước duyệt chưa được gán người xử lý có tên, giao diện in ra mã: `s.assignee_id` (một chuỗi UUID dài ngoằng) thay vì ghi rõ *"Đang chờ hệ thống chỉ định Quản lý trực tiếp"*.
- **Tác động người dùng:** Người gửi đơn không biết hồ sơ của mình sau khi qua người này thì sẽ đi về đâu, gây tâm lý hoang mang và phải nhắn tin hỏi bộ phận hỗ trợ.

---

### 2.5. Thiếu bộ lọc theo Người tạo và Phòng ban trong các bảng tra cứu
- **Thực trạng phát hiện:**
  - Thanh công cụ lọc (`filter-panel`) trong danh sách yêu cầu chỉ hỗ trợ: Tìm mã đơn (`q`), Loại đơn (`type`), Trạng thái (`status`), và Khoảng thời gian (`from` - `to`).
  - **Không có ô lọc theo Người gửi (Requester)**.
  - **Không có ô lọc theo Phòng ban (Department)**.
- **Tác động người dùng:** Người quản lý điều hành nhiều phòng ban hoặc nhân viên kế toán muốn kiểm tra toàn bộ đơn của "Phòng Marketing" trong tháng thì không thể lọc được, buộc phải cuộn trang tìm thủ công từng dòng.

---

## 3. NHÓM 2: "CÁI KHÔNG CÓ QUYỀN XEM THÌ LẠI CÓ"
*(Lộ lọt thông tin kỹ thuật, vi phạm nguyên tắc tối thiểu đặc quyền và phân tách giao diện)*

### 3.1. Tab "Nhật ký kiểm toán" (Audit Log) bị mở công khai cho mọi vai trò người dùng
- **Thực trạng phát hiện:**
  - Trong file `web_client/src/components/RequestDetail.jsx`, thanh tab điều hướng của chi tiết hồ sơ gồm có:
    ```javascript
    ["info", "Thông tin yêu cầu"],
    ["progress", "Tiến trình"],
    ["diagrams", "Sơ đồ luồng"],
    ["history", "Phiên bản & tài liệu"],
    ["audit", "Nhật ký"]  <-- HIỂN THỊ CHO TẤT CẢ MỌI NGƯỜI
    ```
  - Bất kỳ nhân viên nào (kể cả người vừa tạo tài khoản, chỉ có quyền `REQUESTER`) khi bấm vào xem đơn đều bấm được vào tab **"Nhật ký"** (`audit`).
  - Khi bấm vào tab này, hệ thống gọi API `/api/v1/requests/{id}/audit`, phơi bày toàn bộ dữ liệu kiểm toán nội bộ:
    - Địa chỉ IP mạng của những người thao tác (`client_ip`).
    - Mã định danh tài khoản nội bộ (`actor_id: 00000002-...`).
    - Tên hàm nghiệp vụ và hành động backend (`action: REQUEST_DRAFT_CREATED`, `target_type`).
    - Toàn bộ chuỗi sự kiện kiểm toán hệ thống.
- **Nguyên nhân gốc rễ:**
  - Giao diện không kiểm tra quyền `user.roles.includes("AUDITOR")` trước khi hiển thị tab `audit`.
  - Backend API endpoint `requests/<uuid:request_id>/audit` cũng thiếu decorator giới hạn quyền `@require_actor("AUDITOR")`.
- **Rủi ro an toàn:** Vi phạm nghiêm trọng nguyên tắc bảo mật thông tin (Principle of Least Privilege) và lộ lọt hạ tầng mạng nội bộ của doanh nghiệp.

---

### 3.2. Hiển thị khối xác minh tính toàn vẹn và chuỗi mã băm mật mã (Cryptographic Hash)
- **Thực trạng phát hiện:**
  - Ở thanh tác vụ bên phải của `RequestDetail.jsx` và trong `AuditorWorkspace.jsx`, giao diện xuất hiện nút *"Xác minh nhật ký"*.
  - Khi bấm vào nút này, hệ thống in ra màn hình một khối dữ liệu kỹ thuật:
    ```json
    {
      "verified": true,
      "algorithm": "sha256",
      "chain_hash": "a4f89b72c91823...3f8a",
      "count": 6
    }
    ```
- **Tác động người dùng:** Đây là nghiệp vụ kiểm toán hệ thống cấp chuyên sâu, việc hiển thị các đoạn mã hash SHA-256 trần trụi trên giao diện người dùng văn phòng gây rối mắt, tạo cảm giác như trang web chưa hoàn thiện hoặc đang ở chế độ debug.

---

### 3.3. Lộ lọt thông tin cấu trúc bảo mật nội bộ trong mục Quản trị Danh tính
- **Thực trạng phát hiện:**
  - Trong trang `IdentityAdmin.jsx`, khi người quản trị mở modal "Chi tiết người dùng" (`UserDetail`), hệ thống sử dụng component `<Data value={...} />` để hiển thị toàn bộ thuộc tính của bản ghi tài khoản.
  - Trên màn hình xuất hiện các trường kỹ thuật nhạy cảm:
    - `security_epoch: 12`
    - `auth_version: 3`
    - `revision: 5`
    - `must_change_password: true`
    - Các chuỗi UUID phân quyền phức tạp.
- **Rủi ro:** Các tham số kiểm soát phiên làm việc và bảo mật hạt nhân không nên hiển thị trực tiếp cho người vận hành cấp cao nếu không phục vụ mục đích quản trị cụ thể.

---

### 3.4. Rủi ro dùng chung mã nguồn và rò rỉ phân quyền giữa Web Client và Web Admin
- **Thực trạng phát hiện:**
  - Hai ứng dụng `web_client` (chạy port 5173) và `web_admin` (chạy port 5174) thực chất **dùng chung 100% cùng một file mã nguồn `App.jsx`**.
  - `web_admin/src/main.jsx` chỉ đơn giản là import lại `App` từ `web_client` và truyền prop `portal="admin"`.
  - Toàn bộ các trang quản trị nguy hiểm (`identity`, `policy`, `api-admin`, `audit`, `ops`, `plan-catalog`) đều nằm chung trong cây component của `web_client`.
  - Trong thanh menu bên trái (`sidebar`), cấu trúc nhóm menu `"QUẢN TRỊ HỆ THỐNG"` vẫn được định nghĩa trong cùng một component.
- **Rủi ro:** Nếu một nhân viên được tạm thời cấp thêm một quyền (ví dụ quyền Auditor hoặc Policy), thanh menu quản trị hệ thống sẽ bung ra ngay trên cổng của nhân viên. Sự rẽ nhánh bằng biến logic `portal === "admin"` rất dễ phát sinh lỗi hổng hiển thị hoặc nhầm lẫn ngữ cảnh làm việc giữa nhân viên và quản trị viên.

---

## 4. NHÓM 3: "HIỂN THỊ MÃ LỖI KỸ THUẬT & CÁC TRƯỜNG TRUY VẤN SQL"
*(Sự cố rò rỉ mã lỗi lập trình, tên cột CSDL và trải nghiệm nhập liệu thô sơ)*

### 4.1. Thành phần `<Data />` phơi bày nguyên văn tên cột SQL (Database Column Names)
- **Thực trạng phát hiện:**
  - Thành phần `<Data value={...} />` trong file `web_client/src/components/ui.jsx` được sử dụng khắp nơi trong hệ thống (lịch sử đơn, nhật ký kiểm toán, chi tiết người dùng, kết quả xác minh...).
  - Mã nguồn của component này:
    ```javascript
    Object.entries(value).map(([k, v]) => (
      <div key={k}>
        <dt>{k}</dt>        <-- IN TRỰC TIẾP TÊN CỘT DATABASE
        <dd><Data value={v} /></dd>
      </div>
    ))
    ```
  - **Hậu quả:** Người dùng liên tục nhìn thấy các tên cột cơ sở dữ liệu dạng `snake_case` tiếng Anh:
    - `event_id`, `aggregate_id`, `actor_id`, `correlation_id`, `recorded_at`
    - `handover_user_id`, `department_id`, `manager_id`, `user_id`
    - `amount_vnd`, `duration_days`, `app_code`, `requested_role`
    - `lock_version`, `expected_version`, `scan_state`, `checksum_sha256`
    - `scope_kind`, `type_scope`, `valid_from`, `valid_to`
  - Trong `RequestDetail.jsx`, nếu một trường trong biểu mẫu không nằm trong từ điển dịch, hệ thống tự động chạy lệnh `name.replaceAll("_", " ")` biến `source_budget_code` thành `"source budget code"` (tiếng Anh không dấu, không dịch nghĩa).
- **Đánh giá:** Tạo ấn tượng giao diện như một màn hình phpMyAdmin / PgAdmin thô sơ, gây khó khăn cho nhân viên văn phòng.

---

### 4.2. Hiển thị mã lỗi lập trình tiếng Anh viết hoa và mã GUID kỹ thuật
- **Thực trạng phát hiện:**
  - Hàm xử lý thông báo lỗi `errorText()` trong file `web_client/src/domain.js` có đoạn mã:
    ```javascript
    return (
      (messages[e.message] || e.message) +
      (e.fields ? " " + JSON.stringify(e.fields) : "") +
      (e.correlationId ? ` (Mã lỗi: ${e.correlationId})` : "")
    );
    ```
  - **Khi xảy ra sự cố, người dùng sẽ nhìn thấy các dòng thông báo lỗi sau:**
    - `DATABASE_QUERY_FAILED (Mã lỗi: 0192e45f-7c10-7812-98ab-3120cb451000)`
    - `SO_D_VIOLATION`
    - `REQUEST_STATE_CONFLICT`
    - `UNAUTHORIZED_SCOPE`
    - `{"sql_error": "column does not exist", "handover_user_id": ["Invalid UUID"]}`
- **Tác động người dùng:** Người dùng thông thường không biết `SO_D_VIOLATION` (Segregation of Duties) nghĩa là gì, họ tưởng hệ thống bị crash. Việc in chuỗi JSON `e.fields` ra màn hình là vi phạm tiêu chuẩn thiết kế UI/UX cơ bản.

---

### 4.3. Dữ liệu phức tạp (Object / Mảng) bị in thành chuỗi JSON thô
- **Thực trạng phát hiện:**
  - Trong tab "Thông tin yêu cầu" (`RequestDetail.jsx`), dòng 154 có đoạn mã:
    ```javascript
    <dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "—")}</dd>
    ```
  - Đối với các yêu cầu có cấu trúc phức tạp như danh mục tài sản, danh sách mặt hàng, chi phí nhiều hạng mục, giao diện in thẳng một chuỗi JSON trần trụi:
    ```
    {"item_name": "MacBook Pro M3", "quantity": 1, "unit_price": 45000000}
    ```
  - Thay vì dựng một bảng con (Sub-table) hoặc danh sách thẻ trực quan, người dùng buộc phải đọc cú pháp JSON ngoặc nhọn, ngoặc kép.

---

### 4.4. Bắt người dùng nhập liệu bằng chuỗi UUID 36 ký tự
- **Thực trạng phát hiện:**
  - Trong trang Vận hành (`Operations` tại `Admin.jsx`):
    - Mục *"Thử lại sự kiện gửi thông báo"* yêu cầu nhập **ID sự kiện** với mẫu kiểm tra:
      ```html
      <input name="event_id" required pattern="[0-9a-fA-F-]{36}" />
      ```
    - Mục *"Điều chuyển hồ sơ"* yêu cầu nhập:
      - **ID đối tượng được điều chuyển:** `<input name="target_id" pattern="[0-9a-fA-F-]{36}" />`
      - **ID người nhận mới:** `<input name="new_user_id" pattern="[0-9a-fA-F-]{36}" />`
- **Tác động người dùng:** Không ai có thể nhớ hoặc gõ đúng một chuỗi UUID 36 ký tự như `c84d7201-9a1b-4192-8091-a1b2c3d4e5f6`. Đây là lỗi thiết kế nghiêm trọng, bắt buộc phải thay thế bằng bộ chọn người dùng có tìm kiếm họ tên và ảnh đại diện.

---

### 4.5. Ép Quản trị viên viết JSON Schema và JSON Route Rules bằng tay
- **Thực trạng phát hiện:**
  - Trong trang Quản trị quy chế (`Policy` tại `Admin.jsx`), khi mở một bản nháp quy trình, giao diện cung cấp 4 ô `textarea` lớn:
    1. Biểu mẫu (`form_schema`)
    2. Quy tắc định tuyến (`route_rules`)
    3. Phân công vai trò (`actor_bindings`)
    4. Thời hạn SLA (`sla_profile`)
  - Giao diện thậm chí còn hiển thị dòng hướng dẫn kỹ thuật:
    > *"Hãy kiểm tra biểu mẫu, tuyến duyệt và điền actor_bindings bằng UUID người được cấp role hợp lệ."*
- **Tác động người dùng:** Chỉ cần một dấu phẩy đặt sai vị trí hoặc một ngoặc nhọn chưa đóng trong JSON, hệ thống sẽ báo lỗi. Một hệ thống quản trị chuyên nghiệp cần có giao diện kéo thả (Visual Workflow Builder) hoặc form cấu hình từng bước (Step-by-step Wizard).

---

## 5. NHÓM 4: "VẤN ĐỀ VỀ TRẢI NGHIỆM NGƯỜI DÙNG (UX) & BỐ CỤC"

### 5.1. Thiếu hoàn toàn định dạng tiền tệ (Currency Formatting)
- **Thực trạng phát hiện:**
  - Trong tất cả các form nhập liệu (`RequestEditor.jsx`) và màn hình hiển thị chi tiết (`RequestDetail.jsx`), các trường liên quan đến tài chính:
    - `amount_vnd` (Số tiền đề nghị)
    - `estimated_budget` (Dự toán kinh phí)
    - `deal_value_vnd` (Giá trị đơn hàng)
    - `residual_value_vnd` (Giá trị thu hồi)
  - Đều hiển thị và nhập dưới dạng số thô, ví dụ: `50000000`.
  - Không có dấu chấm phân cách hàng nghìn (`50.000.000 ₫`).
  - Không có chữ đọc số tiền bằng chữ (ví dụ: *"Năm mươi triệu đồng chẵn"*).
- **Rủi ro vận hành:** Người nộp đơn hoặc người duyệt rất dễ nhầm lẫn giữa 5 triệu (`5000000`), 50 triệu (`50000000`) và 500 triệu (`500000000`), dẫn đến hậu quả phê duyệt sai ngân sách tài chính.

---

### 5.2. Thiếu trạng thái tải mượt mà (Skeleton Loading) gây giật màn hình
- **Thực trạng phát hiện:**
  - Khi tải danh sách đơn hoặc chuyển trang, giao diện hiện tại chỉ hiển thị một dòng text mộc: `Đang tải...` hoặc giữ nguyên màn hình trống.
  - Khi dữ liệu về, toàn bộ nội dung xuất hiện đột ngột làm dịch chuyển vị trí của các nút bấm (Cumulative Layout Shift - CLS), vi phạm tiêu chuẩn trong tài liệu kỹ năng `frontend-ui-engineering`.
- **Giải pháp chuẩn:** Cần thay thế bằng các khung xương động (Skeleton placeholders) mô phỏng chính xác hình dáng của các hàng bảng và các khối dữ liệu.

---

### 5.3. Thiếu hộp thoại xác nhận (Confirmation Dialog) cho các hành động nguy hiểm
- **Thực trạng phát hiện:**
  - Khi người dùng nhấn các nút có tính chất hủy bỏ hoặc thay đổi trạng thái lớn:
    - **Từ chối hồ sơ (Reject)**
    - **Yêu cầu làm lại (Rework)**
    - **Hủy yêu cầu (Cancel)**
    - **Vô hiệu hóa tài khoản (Deactivate User)**
    - **Thu hồi quyền (Revoke Role)**
  - Hệ thống mở trực tiếp form nhập lý do hoặc thực thi ngay mà không có một hộp thoại cảnh báo nguy hiểm (Danger Confirmation Dialog) nổi bật màu đỏ, cảnh báo rõ: *"Hành động này không thể hoàn tác"*.
- **Tác động người dùng:** Nguy cơ cao người duyệt hoặc quản trị viên click nhầm nút dẫn đến hủy nhầm hồ sơ của nhân viên.

---

### 5.4. Trộn lẫn tiếng Việt và tiếng Anh kỹ thuật thiếu nhất quán
- **Thực trạng phát hiện:**
  - Giao diện có sự pha trộn ngôn ngữ bất hợp lý:
    - `EAS CONTROL CENTER` thay vì `Trung tâm Điều hành Hệ thống`
    - `POLICY ADMIN`, `OPS ADMIN`, `AUDITOR` thay vì chức danh chuẩn tiếng Việt
    - `READY`, `PASS`, `FAIL`, `GLOBAL`, `ALL`, `DEPARTMENT`
    - `CVSS P0-P1`, `SoD`, `SLA`, `Outbox`, `Replay`
  - Các thông báo hệ thống mang giọng văn máy móc:
    - *"Chỉ áp dụng sự kiện DEAD đã được xác định trong vận hành"*
    - *"Dữ liệu đang hiển thị có thể chưa mới nhất. Thử lại"*
- **Yêu cầu:** Toàn bộ thuật ngữ phải được Việt hóa chuẩn mực theo thuật ngữ quản trị văn phòng Việt Nam.

---

### 5.5. Các dòng thông báo thống kê gây hoang mang
- **Thực trạng phát hiện:**
  - Tại trang Quản trị danh tính (`IdentityAdmin.jsx`) và Bảng thống kê yêu cầu (`App.jsx`), giao diện xuất hiện các dòng chữ:
    - *"10 bản ghi trên trang hiện tại, không phải toàn hệ thống"*
    - *"trên trang đang tải"*
- **Tác động người dùng:** Người quản trị nhìn thấy con số 10 nhưng lại đọc dòng chú thích bên dưới thì không biết thực tế công ty mình có bao nhiêu tài khoản đang hoạt động, gây mất niềm tin vào độ chính xác của số liệu báo cáo.

---

## 6. NHÓM 5: "VẤN ĐỀ VỀ KIẾN TRÚC & TIÊU CHUẨN KỸ THUẬT"

| Vấn đề kiến trúc | Thực trạng trong mã nguồn | Chuẩn mực Frontend UI Engineering |
| :--- | :--- | :--- |
| **Kích thước Component** | `App.jsx` hiện tại dài **940 dòng**, chứa từ cấu hình Routing, Login, Header, Sidebar, Dashboard, RequestList đến Filter. | Component không nên vượt quá **200 dòng**. Cần tách nhỏ thành `Sidebar.jsx`, `Topbar.jsx`, `RequestTable.jsx`, `DashboardOverview.jsx`. |
| **Tách biệt Portal** | `web_admin` dùng chung `App.jsx` của `web_client` qua biến `portal`. | Cần tách biệt rõ ràng 2 ứng dụng hoặc 2 bộ Layout riêng biệt: `AdminLayout` và `ClientLayout` độc lập. |
| **Data Fetching vs UI** | Việc fetch dữ liệu từ `api()` bị trộn lẫn trực tiếp trong các hàm render giao diện. | Tách riêng tầng hook dữ liệu (Custom Hooks như `useRequests()`, `useIdentity()`) khỏi tầng hiển thị (Presentation). |
| **Quản lý CSS** | File `eas-enhancements.css` phình to hơn **61,000 bytes** với nhiều class ghi đè `!important`. | Cần quy hoạch lại Design Tokens (màu sắc, khoảng cách padding/margin scale 4px/8px/16px) theo thiết kế nhất quán. |

---

## 7. BẢNG TỔNG HỢP & MỨC ĐỘ ƯU TIÊN KHẮC PHỤC

| STT | Vấn đề cụ thể | Nhóm | Mức độ nghiêm trọng | Tệp nguồn liên quan |
| :---: | :--- | :--- | :---: | :--- |
| **1** | Bảng danh sách đơn thiếu Tiêu đề, Người gửi, Phòng ban, Hạn SLA | Thiếu thông tin | **P0 (Khẩn cấp)** | `api_core/workflow/views.py`<br>`web_client/src/App.jsx` |
| **2** | Tab "Nhật ký kiểm toán" bị lộ cho toàn bộ nhân viên | Lộ quyền / Rò rỉ | **P0 (Khẩn cấp)** | `web_client/src/components/RequestDetail.jsx`<br>`api_core/workflow/urls.py` |
| **3** | Component `<Data />` in nguyên văn tên cột SQL và raw JSON | Lộ Schema SQL | **P0 (Khẩn cấp)** | `web_client/src/components/ui.jsx` |
| **4** | Hàm `errorText()` in mã lỗi tiếng Anh viết hoa và chuỗi JSON fields | Trải nghiệm lỗi | **P0 (Khẩn cấp)** | `web_client/src/domain.js` |
| **5** | Ô nhập tiền tệ thiếu định dạng dấu chấm phân cách hàng nghìn | Trải nghiệm nhập | **P1 (Quan trọng)** | `web_client/src/components/RequestEditor.jsx`<br>`web_client/src/components/RequestDetail.jsx` |
| **6** | Trang Profile hiển thị mã phòng ban UUID thay vì tên tiếng Việt | Thiếu thông tin | **P1 (Quan trọng)** | `web_client/src/components/Admin.jsx` (`Profile`) |
| **7** | Các ô nhập liệu UUID 36 ký tự trong trang Vận hành và Quản trị | Lỗi tương tác | **P1 (Quan trọng)** | `web_client/src/components/Admin.jsx` (`Operations`) |
| **8** | Đưa Sơ đồ tổ chức ra Cổng Web Client cho toàn thể nhân viên xem | Thiếu thông tin | **P1 (Quan trọng)** | `web_client/src/rolePolicy.js`<br>`web_client/src/App.jsx` |
| **9** | Bổ sung hộp thoại xác nhận (Confirm Modal) cho thao tác nguy hiểm | Trải nghiệm UX | **P2 (Cần thiết)** | `web_client/src/components/RequestDetail.jsx`<br>`web_client/src/components/IdentityAdmin.jsx` |
| **10** | Thay thế chữ "Đang tải..." bằng Skeleton Loading chuẩn | Tiêu chuẩn UI | **P2 (Cần thiết)** | `web_client/src/components/ui.jsx` |
| **11** | Việt hóa đồng bộ toàn bộ thuật ngữ và thông báo hệ thống | Tiêu chuẩn UI | **P2 (Cần thiết)** | Toàn bộ các file trong `web_client/src` |
| **12** | Tách nhỏ file `App.jsx` và tách biệt hoàn toàn Client vs Admin | Kiến trúc code | **P3 (Dài hạn)** | `web_client/src/App.jsx`<br>`web_admin/src/main.jsx` |

---

## 8. LỘ TRÌNH ĐỀ XUẤT THỰC THI (ACTIONABLE ROADMAP)

### Giai đoạn 1: Khắc phục triệt để các lỗi P0 (Bảo mật & Trải nghiệm cốt lõi)
1. **Nâng cấp Backend API `GET /api/v1/requests`:**
   - Bổ sung `JOIN` với bảng người dùng và phòng ban để trả về: `title`, `requester_name`, `department_name`, `due_at`.
   - Cập nhật bảng `RequestList` trên giao diện hiển thị rõ ràng: Cột 1: Mã đơn & Tiêu đề; Cột 2: Loại nghiệp vụ; Cột 3: Người gửi & Phòng ban; Cột 4: Trạng thái & Hạn xử lý; Cột 5: Nút thao tác.
2. **Khóa chặt Tab "Nhật ký kiểm toán":**
   - Ẩn hoàn toàn tab `audit` trong `RequestDetail.jsx` đối với các vai trò không phải `AUDITOR` hoặc `OPS_ADMIN`.
   - Bổ sung kiểm tra quyền nghiêm ngặt trên backend API.
3. **Thay thế `<Data />` bằng các Component hiển thị chuyên biệt:**
   - Xóa bỏ việc in `<dt>{k}</dt>`. Xây dựng bảng hiển thị có từ điển nhãn tiếng Việt 100%. Nếu gặp dữ liệu dạng object/array, render thành bảng con hoặc danh sách thẻ, tuyệt đối không in chuỗi JSON thô.
4. **Việt hóa toàn diện hàm xử lý lỗi `errorText()`:**
   - Mọi mã lỗi backend phải được ánh xạ sang câu thông báo tiếng Việt lịch sự, dễ hiểu (ví dụ: `SO_D_VIOLATION` -> *"Bạn không thể tự phê duyệt yêu cầu do chính mình tạo ra theo quy định kiểm soát nội bộ"*).
   - Ẩn correlation ID và chuỗi `fields` khỏi màn hình chính, chỉ để lại nút nhỏ *"Chi tiết kỹ thuật"* nếu người dùng muốn sao chép gửi cho IT.

### Giai đoạn 2: Chuẩn hóa UX Nhập liệu & Bổ sung thông tin nghiệp vụ (P1)
1. **Áp dụng bộ định dạng tiền tệ:**
   - Tích hợp hàm format tiền tệ tự động thêm dấu phân cách hàng nghìn khi người dùng đang gõ phím (`100,000,000 ₫`) kèm dòng đọc số thành chữ bên dưới.
2. **Cung cấp Sơ đồ tổ chức cho Web Client:**
   - Mở quyền xem Sơ đồ tổ chức ở chế độ chỉ đọc (Read-only) cho mọi nhân viên trên cổng Web Client để phục vụ tra cứu đồng nghiệp và tuyến báo cáo.
3. **Thay thế toàn bộ ô nhập UUID bằng Dropdown tìm kiếm:**
   - Thay thế các ô nhập `event_id`, `target_id`, `new_user_id` bằng bộ chọn người dùng có tìm kiếm theo tên, email và avatar.
4. **Hoàn thiện trang Hồ sơ cá nhân (`Profile`):**
   - Hiển thị đầy đủ Tên phòng ban tiếng Việt, Chức vụ, Người quản lý trực tiếp, Email và ngày gia nhập.

### Giai đoạn 3: Tối ưu hóa giao diện & Tiêu chuẩn hóa (P2 & P3)
1. **Xây dựng Skeleton Loader:**
   - Thiết kế các khối placeholder chuyển động nhẹ nhàng khi đang tải trang.
2. **Bổ sung Modal xác nhận an toàn:**
   - Khi bấm "Từ chối", "Hủy yêu cầu" hoặc "Thu hồi", hiển thị hộp thoại cảnh báo với 2 nút *"Hủy bỏ"* và *"Xác nhận thực hiện"*.
3. **Tái cấu trúc thư mục Component:**
   - Chia tách `App.jsx` thành các module độc lập theo đúng chỉ dẫn của kỹ năng **Frontend UI Engineering**.

