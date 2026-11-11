# Chức năng giao diện và phân quyền — EAS

| Thuộc tính | Giá trị |
|---|---|
| Trạng thái | BẢN NHÁP để chủ dự án đọc và chỉnh sửa — cập nhật theo Client Phase 1–3 (mục 14) |
| Ngày | 03/11/2026 |
| Phạm vi | Cổng nhân viên (`web_client`), cổng quản trị (`web_admin`), API `api_core`, CSDL `eas` |
| Nguồn sự thật | Mã nguồn hiện tại + dữ liệu live (đọc ngày 03/11/2026) + đối chiếu sản phẩm đang hoạt động (mục 10) |

Tài liệu mô tả **người dùng thấy gì** và **được làm gì** trên giao diện, theo từng vai trò. Các mục `> Ghi chú` là chỗ hệ thống hiện tại khác với điều nên có; mục 11 là danh sách câu hỏi cần chủ dự án chốt.

---

## 1. Nguyên tắc phân quyền

Phân quyền đi qua **4 lớp**, lớp sau chỉ thu hẹp lớp trước, không bao giờ mở rộng:

| Lớp | Câu hỏi | Nơi quyết định | Ảnh hưởng UI |
|---|---|---|---|
| 1. Tài khoản & cổng | Tài khoản này được vào cổng nào? | `app_user.account_type`, `eas.admin_account`; API `auth/login` kiểm tra `portal` | Màn hình đăng nhập báo lỗi, không vào được cổng sai |
| 2. Vai trò & phạm vi | Có vai trò gì, áp cho phòng ban/loại yêu cầu nào? | `eas.role_membership` (role, `scope_kind` GLOBAL/DEPARTMENT, `type_scope` ALL/ONE, hiệu lực từ–đến) | Menu bên trái, hộp việc, danh sách được thấy |
| 3. Quyền module | Với mỗi module: Xem / Thêm / Sửa / Xoá? | `eas.role_module_permission` + quyền riêng `eas.user_permissions`, hợp nhất bởi `eas.get_effective_user_permissions` | Ẩn mục menu, ẩn/khoá nút Thêm/Sửa/Xoá |
| 4. Điều kiện trên từng hồ sơ | Hồ sơ đang ở trạng thái nào, ai là chủ, ai đang được giao? | Máy trạng thái (FSM) + tách biệt nhiệm vụ (SoD) trong `api_core/workflow/service.py` | Nút hành động trên chi tiết hồ sơ chỉ hiện khi đủ điều kiện |

Quy tắc bắt buộc:

- **Backend là người quyết định cuối cùng.** UI chỉ ẩn/hiện cho dễ dùng; mọi thao tác đều được API kiểm tra lại (vai trò + phạm vi + trạng thái + SoD). Gọi thẳng API mà sai quyền → `403`.
- **Một tài khoản quản trị duy nhất:** chỉ `admin@eas.com` đăng nhập được cổng quản trị và là tài khoản duy nhất giữ `OPS_ADMIN`, `POLICY_ADMIN`. Tài khoản này **không** đăng nhập được cổng nhân viên và không tạo/xử lý yêu cầu nghiệp vụ.
- **Nhân viên không bao giờ có quyền quản trị hệ thống:** 4 module hệ thống (`permissions`, `ai_engine`, `api_management`, `system_versions`) không thể cấp cho vai trò nhân viên hay cho từng nhân viên (API trả `422 ADMIN_MODULE_NOT_GRANTABLE`) và không bao giờ xuất hiện ở cổng nhân viên. 5 module nghiệp vụ (`dashboard`, `requests_workflows`, `org_chart`, `users`, `regulations`) admin được cấp cho vai trò hoặc từng người (mục 14).
- **Tài khoản hệ thống AI** (`ai.system@eas.com`) không đăng nhập được, không sửa/khoá/đổi quyền được.
- Thu hồi vai trò có hiệu lực ngay ở request kế tiếp (vai trò đọc lại từ DB mỗi request; thu hồi còn đăng xuất phiên cũ).

---

## 2. Vai trò

| Mã | Tên hiển thị | Ai giữ (live 03/11) | Cổng | Ý nghĩa |
|---|---|---|---|---|
| `REQUESTER` | Người tạo yêu cầu | 136 nhân viên | Nhân viên | Tạo, theo dõi, bổ sung, huỷ yêu cầu của mình |
| `ACCEPTOR` | Người nghiệm thu | 136 nhân viên | Nhân viên | Nghiệm thu kết quả yêu cầu nhóm C của mình |
| `APPROVER` | Người phê duyệt | Giám đốc, phó GĐ, trưởng phòng, trưởng nhóm | Nhân viên | Duyệt/từ chối/yêu cầu bổ sung khi đến lượt; xem báo cáo phòng ban; uỷ quyền |
| `EXECUTOR` | Người thực hiện | Nhân viên chuyên trách | Nhân viên | Nhận việc, báo vướng mắc, nộp kết quả |
| `POLICY_ADMIN` | Quản trị chính sách | Chỉ `admin@eas.com` | Quản trị | Quy định, bộ luật AI, phiên bản cấu hình quy trình |
| `OPS_ADMIN` | Quản trị vận hành | Chỉ `admin@eas.com` | Quản trị | Người dùng, phân quyền, điều phối, API tích hợp |
| `AUDITOR` | Kiểm toán viên | Không ai | — | Chỉ đọc để kiểm toán |

Phạm vi: `APPROVER`/`EXECUTOR` thường gắn `DEPARTMENT` (chỉ phòng mình); các vai trò còn lại `GLOBAL`. Một người có thể giữ nhiều vai trò; UI hiển thị vai trò cao nhất làm "chức vụ".

> Ghi chú: `AUDITOR` hiện **không dùng được**: cổng quản trị chỉ nhận `admin@eas.com`, cổng nhân viên chặn mọi tài khoản có vai trò quản trị không kèm vai trò nghiệp vụ. Cần chốt (mục 11): bỏ vai trò này, hay cho kiểm toán viên một cổng/chế độ chỉ đọc.

---

## 3. Ma trận quyền module (live)

`X` = Xem, `C` = Thêm, `U` = Sửa, `D` = Xoá/Khoá. `ADMIN` = module chỉ cho cổng quản trị.

| Vai trò | Tổng quan | Yêu cầu & Quy trình | Sơ đồ tổ chức | Người dùng `ADMIN` | Phân quyền `ADMIN` | Quy định | Quản trị AI `ADMIN` | Quản lý API `ADMIN` | Phiên bản hệ thống `ADMIN` |
|---|---|---|---|---|---|---|---|---|---|
| REQUESTER | X | XC | X | — | — | X | — | — | — |
| APPROVER | X | XCU | X | — | — | X | — | — | — |
| EXECUTOR | X | XC | X | — | — | X | — | — | — |
| ACCEPTOR | X | XC | X | — | — | X | — | — | — |
| AUDITOR | X | XC | X | — | — | X | — | — | X |
| POLICY_ADMIN | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD |
| OPS_ADMIN | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD | XCUD |

Quyền của một người = hợp các vai trò đang hiệu lực, rồi **quyền riêng** (nếu có) ghi đè cho đúng module đó. Ma trận DB là nguồn duy nhất: không có dòng nào cho phép thì không có quyền (không rơi về quyền theo vai trò).

> Ghi chú (ĐÃ SỬA 03/11 — mục 14): UI dùng `requests_workflows.can_update` để hiện nút **Sửa** hồ sơ và `can_delete` để hiện nút **Huỷ**. `REQUESTER` chỉ có `XC` nên **nhân viên hiện không thấy nút sửa bản nháp/bổ sung và nút huỷ yêu cầu của chính mình** (API vẫn cho phép). Đề xuất: cấp `U`, `D` trên `requests_workflows` cho `REQUESTER` (giới hạn bởi lớp 4: chỉ hồ sơ của mình, chỉ ở trạng thái cho phép), hoặc bỏ điều kiện module khỏi 2 nút này.
>
> Ghi chú: `AUDITOR` có `C` trên "Yêu cầu & Quy trình" — mâu thuẫn với "chỉ đọc".

---

## 4. Đăng nhập, phiên, thông báo hệ thống (mọi người dùng)

| Chức năng | Mô tả | Quy tắc |
|---|---|---|
| Đăng nhập | Email công ty `@eas.com` + mật khẩu | Sai mật khẩu nhiều lần → khoá tạm (`LOGIN_RATE_LIMITED`); quá 300 request/phút/IP → `RATE_LIMIT_EXCEEDED` |
| Chặn sai cổng | Nhân viên vào cổng quản trị, hoặc `admin@eas.com` vào cổng nhân viên → thông báo đỏ, không vào được | Kiểm tra cả ở UI và API |
| Đổi mật khẩu lần đầu | Tài khoản có `must_change_password` chỉ thấy màn hình đổi mật khẩu | Chính sách mật khẩu 15–128 ký tự, mã hoá Argon2 |
| Quên mật khẩu | Gửi yêu cầu đặt lại; quản trị viên duyệt | Không tiết lộ email có tồn tại hay không |
| Hết phiên | Phiên rảnh quá hạn → về màn hình đăng nhập | Cookie `httpOnly`, `sameSite=Lax`, `secure` khi production |
| **Khoá khi AI học quy định** | Khi quy định đổi, cổng nhân viên hiện màn hình "Hệ thống đang cập nhật và huấn luyện AI" với 4 bước + % rồi tự đăng xuất sau 5 giây; nút đăng nhập bị khoá đến khi AI áp dụng xong | Cổng quản trị không bị khoá. AI lỗi sau 3 lần thử → mở khoá, giữ luật cũ, chỉ admin nhận cảnh báo |
| **Hộp "Hệ thống đã cập nhật quy định vX"** | Lần đăng nhập đầu sau cập nhật: danh sách thay đổi + hướng dẫn thao tác theo quy trình mới; nút "Đã hiểu" | Xem lại ở trang Thông báo → "Cập nhật hệ thống" |
| Thông báo | Chuông trên thanh đầu trang + trang "Thông báo": lọc chưa đọc, đánh dấu đã đọc, "Mở hồ sơ" | Chỉ thấy thông báo của mình |
| Tìm nhanh | Ô tìm trên thanh đầu trang: theo mã hồ sơ, tiêu đề, tên chức năng | Chỉ trả hồ sơ người đó được xem |
| Giao diện | Sáng/tối, thu gọn thanh bên, dùng được trên điện thoại (menu trượt) | Lưu theo trình duyệt |

---

## 5. Cổng nhân viên — menu theo vai trò

> Từ Client Phase 1–3, menu cổng nhân viên theo 5 module nghiệp vụ — xem **mục 14.2**. Bảng dưới là thiết kế trước đó, giữ lại để đối chiếu.

| Nhóm menu | Mục | REQUESTER | APPROVER | EXECUTOR | ACCEPTOR |
|---|---|---|---|---|---|
| Không gian cá nhân | Tổng quan | ✓ | ✓ | ✓ | ✓ |
| | Yêu cầu của tôi | ✓ | | | |
| Công việc được giao | Chờ phê duyệt | | ✓ | | |
| | Công việc thực hiện | | | ✓ | |
| | Chờ nghiệm thu | | | | ✓ |
| Quản lý phòng ban | Tổng quan phòng ban | | ✓ | | |
| | Nhân viên phòng ban | | ✓ | | |
| Tổ chức & công cụ | Sơ đồ tổ chức | ✓ | ✓ | ✓ | ✓ |
| | Sơ đồ luồng | ✓ | ✓ | ✓ | ✓ |
| | Quy trình AI | ✓ | ✓ | ✓ | ✓ |
| Tài khoản | Tài khoản cá nhân | ✓ | ✓ | ✓ | ✓ |

Mục chỉ hiện khi người đó vừa có vai trò tương ứng vừa có quyền **Xem** module (mục 3). Nút **"Tạo yêu cầu mới"** chỉ hiện khi có quyền **Thêm** trên "Yêu cầu & Quy trình" và không bao giờ có ở cổng quản trị.

### 5.1 Tổng quan
- Lời chào, bộ lọc thời gian (Hôm nay / 7 ngày / 30 ngày / 12 tháng / tuỳ chọn).
- Thẻ số liệu **chỉ của chính mình**: đã gửi, đang xử lý, chờ duyệt (gồm cần bổ sung), bị từ chối, hoàn thành, tỉ lệ hoàn thành, thời gian hoàn thành và thời gian duyệt trung bình. Không tính bản nháp.
- Phân bố trạng thái, loại yêu cầu thường gặp.
- Người không có `REQUESTER`: tổng quan việc được giao thay vì thống kê yêu cầu.

### 5.2 Tạo yêu cầu mới
- Chọn loại theo 10 nhóm catalog (Tài chính, Nguồn lực, Cơ sở vật chất, Công việc, Nhân sự, Thời gian, CNTT, Pháp lý, Kinh doanh, Hành chính); tìm theo tên.
- Loại **bị khoá** kèm lý do khi: chưa có phiên bản cấu hình đã công bố, loại đang tạm ngừng, không có quyền tạo cho phòng ban, hoặc **API tích hợp liên quan đang bị tắt** (ví dụ tắt API Nhân sự → khoá Nghỉ phép, Công tác...). Server chặn cả khi gọi thẳng (`409 INTEGRATION_UNAVAILABLE`).
- Biểu mẫu theo phiên bản cấu hình của loại; đính kèm tệp (kiểm tra loại tệp theo nội dung); **xem trước luồng duyệt** (ai duyệt, bao nhiêu bước) trước khi gửi.
- Lưu nháp; gửi cần xác nhận lại.
- Sau khi gửi, AI chấm rủi ro và có thể **tự duyệt** với loại nhóm A rủi ro thấp đúng quy định hiện hành.

### 5.3 Yêu cầu của tôi
- Các tab theo giai đoạn: Tất cả / Nháp / Chờ duyệt / Cần bổ sung / Đang thực hiện / Chờ nghiệm thu / Hoàn thành / Từ chối / Đã huỷ; lọc, tìm, phân trang.
- Mở chi tiết hồ sơ (mục 7).

### 5.4 Chờ phê duyệt (APPROVER)
- Hộp việc gồm hồ sơ đang ở bước do mình (hoặc người uỷ quyền cho mình) phụ trách; đánh dấu quá hạn SLA.
- Thao tác ở chi tiết hồ sơ: **Duyệt**, **Từ chối** (bắt buộc lý do), **Yêu cầu bổ sung** (bắt buộc lý do); khi duyệt bước cuối của loại B/C có thể chọn người thực hiện trong danh sách được phép.
- **Thu hồi duyệt tự động của AI** trong 24 giờ sau khi AI tự duyệt (đưa về duyệt tay).

### 5.5 Công việc thực hiện (EXECUTOR)
- Danh sách việc được giao. Thao tác: **Nhận việc**, **Báo vướng mắc**, **Nộp kết quả** (kèm tệp).

### 5.6 Chờ nghiệm thu (ACCEPTOR)
- Hồ sơ nhóm C mình là người nghiệm thu. Thao tác: **Chấp nhận** hoặc **Yêu cầu làm lại** (bắt buộc lý do).

### 5.7 Tổng quan phòng ban / Nhân viên phòng ban (APPROVER)
- Báo cáo yêu cầu của phòng mình theo trạng thái, loại, thời gian; danh sách nhân viên trong phòng, xem số hồ sơ theo 5 giai đoạn của từng người.
- Phạm vi = phòng ban của vai trò `APPROVER` (giám đốc/phó GĐ phạm vi toàn công ty).

### 5.8 Sơ đồ tổ chức, Sơ đồ luồng, Quy trình AI
- Sơ đồ tổ chức: ban giám đốc → phòng ban → nhân sự, người phụ trách, trạng thái làm việc (Đang làm 08:00–17:30 T2–T6 / Nghỉ / Công tác). Chỉ đọc.
- Sơ đồ luồng: vòng đời A/B/C và các trạng thái. Chỉ đọc.
- Quy trình AI: AI tham gia ở đâu, đánh giá AI đã lưu cho từng hồ sơ. Chỉ đọc.

> Ghi chú: module "Quy định" cho nhân viên quyền **Xem**, nhưng cổng nhân viên chưa có trang đọc quy định công ty. Đề xuất thêm trang "Quy định công ty" chỉ đọc (phiên bản hiện hành + lịch sử thay đổi).

### 5.9 Tài khoản cá nhân
- Thông tin cá nhân, phòng ban, vai trò; đổi mật khẩu.
- `APPROVER`: **Uỷ quyền phê duyệt** cho một người duyệt khác trong khoảng thời gian (tối đa 90 ngày, không chồng lấn), thu hồi uỷ quyền.

---

## 6. Vòng đời yêu cầu

| Nhóm | Các bước |
|---|---|
| A — Chỉ phê duyệt | Tạo → Phê duyệt (1..n bước) → Hoàn thành |
| B — Phê duyệt + thực hiện | Tạo → Phê duyệt → Thực hiện → Hoàn thành |
| C — Phê duyệt + thực hiện + nghiệm thu | Tạo → Phê duyệt → Thực hiện → Nghiệm thu → Hoàn thành |

Trạng thái: `DRAFT` Bản nháp · `PENDING_APPROVAL` Chờ phê duyệt · `NEEDS_INFO` Cần bổ sung · `READY_FOR_EXECUTION` Chờ thực hiện · `IN_PROGRESS` Đang thực hiện · `WAITING_FOR_ACCEPTANCE` Chờ nghiệm thu · `COMPLETED` Hoàn thành · `REJECTED` Từ chối · `CANCELLED` Đã huỷ.

---

## 7. Chi tiết hồ sơ — ai được bấm nút nào

Các tab: Thông tin, Tiến độ (ai đang xử lý, bước kế tiếp, hạn SLA), Phê duyệt, Thực hiện, Đính kèm, Lịch sử phiên bản, Hoạt động, Đánh giá AI.

| Nút | Ai thấy | Khi nào | Bắt buộc |
|---|---|---|---|
| Sửa | Người tạo (`REQUESTER`) | `DRAFT`, `NEEDS_INFO` | Đúng phiên bản dữ liệu (chống ghi đè) |
| Gửi / Gửi lại | Người tạo | `DRAFT`, `NEEDS_INFO` | Xác nhận trước khi gửi |
| Huỷ | Người tạo | `DRAFT`, `NEEDS_INFO`, `PENDING_APPROVAL` (trước khi duyệt xong) | Lý do |
| Duyệt / Từ chối / Yêu cầu bổ sung | `APPROVER` đang được giao bước hiện tại (kể cả người nhận uỷ quyền) | `PENDING_APPROVAL` | Từ chối & bổ sung bắt buộc lý do; không duyệt hồ sơ của chính mình |
| Thu hồi AI tự duyệt | `APPROVER` khác người tạo | `COMPLETED` do AI tự duyệt, trong 24 giờ | Lý do |
| Nhận việc | `EXECUTOR` được giao | `READY_FOR_EXECUTION` | Không phải người tạo, không phải người đã duyệt hồ sơ |
| Báo vướng mắc / Nộp kết quả | `EXECUTOR` được giao | `IN_PROGRESS` | Như trên |
| Chấp nhận / Làm lại | `ACCEPTOR` được chỉ định | `WAITING_FOR_ACCEPTANCE` (nhóm C) | Không phải người thực hiện; làm lại bắt buộc lý do |
| Điều chuyển người xử lý | `OPS_ADMIN` (cổng quản trị) | Bước duyệt/thực hiện đang mở | Lý do, đúng phiên bản |

Tách biệt nhiệm vụ (SoD): người tạo không tự duyệt; người duyệt không thực hiện cùng hồ sơ; người thực hiện không nghiệm thu; bị thu hồi vai trò thì không thao tác được nữa kể cả hồ sơ của mình. Hồ sơ ở trạng thái kết thúc không có nút thao tác nào.

---

## 8. Cổng quản trị (chỉ `admin@eas.com`)

Menu gồm đúng 9 mục.

| Nhóm | Mục | Chức năng | Thao tác (quyền module) |
|---|---|---|---|
| GIÁM SÁT | **Tổng quan** | KPI (tổng, thành công, từ chối, đang xử lý) theo ngày/tuần/tháng/năm/tuỳ chọn; hiệu suất SLA nhóm A/B/C; xu hướng; top loại, phòng ban, người gửi. Nút "Theo dõi chi tiết vận hành" → trang vận hành: lọc hồ sơ toàn công ty, **điều chuyển** người duyệt/thực hiện, gửi lại sự kiện lỗi | Xem; điều chuyển cần `OPS_ADMIN` |
| LUỒNG CÔNG VIỆC | **Yêu cầu & Quy trình** | Nhóm A/B/C (bước, SLA điển hình); danh sách loại yêu cầu (nhóm catalog, vòng đời, SLA, mức tự động hoá, phiên bản cấu hình, bước duyệt); sửa tên, nhóm, bật/tắt, mức tự động hoá. Đổi vòng đời/biểu mẫu/luồng duyệt cần **phát hành phiên bản cấu hình mới** | X / C / U / D |
| TỔ CHỨC & NHÂN SỰ | **Sơ đồ công ty** | Cây phòng ban, người phụ trách, nhân sự, trạng thái làm việc | X |
| | **Người dùng** | Danh sách nhân viên (mã, phòng, vai trò, trạng thái làm việc, số hồ sơ 5 giai đoạn); tạo tài khoản (mật khẩu theo chính sách, tự gán quản lý trực tiếp, vai trò nghiệp vụ); sửa; khoá/mở; ghi nhận nghỉ/công tác; xem hồ sơ theo 5 giai đoạn | X / C / U / D. Chỉ gán được vai trò nghiệp vụ |
| | **Phân quyền** | Ma trận vai trò × module; quyền riêng từng nhân viên; khôi phục mặc định | U. Module chỉ-admin bị khoá với nhân viên |
| TRI THỨC & AI | **Quy định** | CRUD quy định công ty; tạo/xoá tăng phiên bản chính, sửa tăng phiên bản phụ; mỗi thay đổi xếp lượt **AI học lại** → khoá cổng nhân viên đến khi áp dụng xong → gửi thông báo cho mọi người | X / C / U / D |
| | **Quản trị AI** | Trạng thái 4 bước, phiên bản đang áp dụng, lịch sử các lượt học; **Học lại**; **thử AI thật** (chọn loại, số tiền, số ngày → AI tự duyệt hay chuyển người) | X; Học lại cần U |
| HỆ THỐNG | **Quản lý API** | 8 API tích hợp (HR, Tài chính, CNTT, Mua sắm, Tài sản, Toà nhà, Công tác, CRM), loại yêu cầu phụ thuộc; **tắt/bật** (circuit breaker) — tắt là khoá các loại yêu cầu liên quan ngay | X / U |
| | **Phiên bản hệ thống** | Nhật ký thay đổi (quy định, API, cấu hình), xem so sánh trước/sau, xuất bản sao cấu hình | X |

Mọi thao tác ghi đều: kiểm tra phía server, ghi **nhật ký quản trị** (`admin_event`, chuỗi băm chống sửa) kèm lý do ≥ 10 ký tự, có khoá chống ghi đè đồng thời.

> Ghi chú: các màn hình sau **vẫn còn trong mã** nhưng không có trên menu 9 mục: Danh tính & phạm vi quyền (gán vai trò theo phòng ban/loại yêu cầu, quản lý phòng ban), Phiên bản cấu hình quy trình (soạn, kiểm tra, công bố luồng duyệt/biểu mẫu/SLA), Luật AI thủ công, Thông báo SLA, Nhật ký kiểm toán. Không có chúng thì admin **không đổi được phạm vi duyệt, luồng duyệt, biểu mẫu, SLA** và không xem được nhật ký kiểm toán trên UI. Cần chốt (mục 11).

---

## 9. Hành vi xuyên suốt

| Chủ đề | Hành vi trên UI |
|---|---|
| Khoá AI học quy định | Mục 4. Thời gian khoá thường 1–10 giây; tối đa ~1 phút nếu AI không phản hồi |
| Thông báo cập nhật | Mục 4. Nội dung tự sinh từ thay đổi quy định: luật mới/sửa/bỏ (ví dụ "Mọi yêu cầu từ 50.000.000 đ trở lên: bắt buộc người duyệt xét thủ công") và các bước thao tác |
| API tích hợp tắt | Loại yêu cầu liên quan hiện "Tạm ngưng" kèm lý do, nút gửi bị khoá; bật lại thì mở ngay |
| Uỷ quyền | Người nhận uỷ quyền thấy hồ sơ trong "Chờ phê duyệt" như người duyệt gốc trong khoảng thời gian uỷ quyền |
| AI tự duyệt | Chỉ nhóm A, rủi ro thấp, không vi phạm luật bắt buộc duyệt tay; hồ sơ hiện huy hiệu AI; thu hồi được trong 24 giờ |
| Lỗi | Thông báo tiếng Việt + mã tra cứu; không lộ chi tiết kỹ thuật |
| Xung đột dữ liệu | "Dữ liệu đã thay đổi. Hãy tải lại hồ sơ" khi hai người cùng sửa |

---

## 10. Đối chiếu sản phẩm đang hoạt động

| Hành vi | Jira Service Management | ServiceNow | Base Request | EAS hiện tại | Đề xuất |
|---|---|---|---|---|---|
| Duyệt / từ chối từ hộp việc | Có ("My approvals") | Có (To-dos) | Có | Có | — |
| Lý do khi từ chối | Khuyến nghị bình luận | **Bắt buộc** | Có | **Bắt buộc** | — |
| Nhiều người duyệt | Chờ đủ; 1 người từ chối là dừng | Cấu hình được | Thứ tự người duyệt | Nhiều bước tuần tự | — |
| Uỷ quyền khi vắng | Không có sẵn | Có (người thay thế + thời hạn) | Có (uỷ quyền khi nghỉ phép) | Có (≤ 90 ngày) | Hiện tên người nhận uỷ quyền trong lịch sử duyệt |
| Chuyển quyền duyệt khi đến lượt | — | — | Có | Chỉ admin điều chuyển | Cân nhắc cho người duyệt tự chuyển (có lý do, ghi nhật ký) |
| Người theo dõi | Có (participants) | Có (watch list) | Có | Chưa có | Cân nhắc thêm "người theo dõi" chỉ đọc |
| Duyệt qua email | Có | Có | — | Chưa có | Có thể bổ sung sau (link đăng nhập, không duyệt khi chưa xác thực) |
| Duyệt hàng loạt | Ứng dụng bên thứ ba | — | — | Chưa có | Chỉ nên cho nhóm A rủi ro thấp |
| Chặn người được uỷ quyền tự duyệt hồ sơ của mình | Câu hỏi còn bỏ ngỏ trên cộng đồng | Câu hỏi còn bỏ ngỏ trên cộng đồng | — | **Có** (SoD) | — |

Nguồn:
- [Approving a service project request — Atlassian](https://confluence.atlassian.com/servicemanagementserver/approving-a-service-project-request-939937225.html)
- [What are approvals? — Jira Service Management Cloud](https://support.atlassian.com/jira-service-management-cloud/docs/set-up-an-approval-stage-for-a-request/)
- [JSM Approval Workflows: The Complete Guide 2026 — Atlassian Community](https://community.atlassian.com/forums/App-Central-articles/JSM-Approval-Workflows-The-Complete-Guide-2026/ba-p/3269187)
- [Approving approval requests — ServiceNow Docs](https://www.servicenow.com/docs/r/order-management/approving-approval-requests.html)
- [Working with approval requests as an approver — ServiceNow Docs](https://www.servicenow.com/docs/r/HGDW_sLOfs0QXhKu64QAng/QviGs2QqWAbK8Lqn2pY7Tg)
- [Delegate approvers — ServiceNow Community](https://www.servicenow.com/community/itsm-forum/delegate-approvers/m-p/3442447)
- [Base Request: How to delegate request approval](https://help.base.vn/support/solutions/articles/63000284958-base-request-how-to-delegate-request-approval)
- [Base Request: Transfer request approval rights to another approver](https://help.base.vn/support/solutions/articles/63000284957-request-transfer-request-approval-rights-to-another-approver)
- [Base Request: Set permissions to add followers](https://help.base.vn/support/solutions/articles/63000284916-base-request-set-permissions-to-add-followers-in-the-request-group)
- [Base Request: How to set up direct manager as approver](https://help.base.vn/support/solutions/articles/63000268684-base-request-how-to-set-up-direct-manager-as-approver)

---

## 11. Câu hỏi cần chủ dự án chốt

Phương án đề xuất cho từng câu: mục 12.1.

1. **Nút Sửa/Huỷ của nhân viên** (mục 3): cấp `U`, `D` trên "Yêu cầu & Quy trình" cho `REQUESTER`, hay bỏ điều kiện module khỏi 2 nút này?
2. **Vai trò `AUDITOR`**: bỏ, hay cho một chế độ chỉ đọc (cổng nào, xem được gì)?
3. **Menu quản trị 9 mục**: đưa các màn hình còn thiếu (mục 8 ghi chú) vào trong các trang hiện có (ví dụ tab "Phạm vi quyền" trong Người dùng, tab "Phiên bản cấu hình" trong Yêu cầu & Quy trình, tab "Nhật ký kiểm toán" trong Phiên bản hệ thống), hay bỏ hẳn?
4. **Trang "Quy định công ty" chỉ đọc** cho nhân viên (mục 5.8): có thêm không?
5. **Người theo dõi**, **người duyệt tự chuyển lượt**, **duyệt qua email** (mục 10): có đưa vào phạm vi không?
6. **Thông báo sai cổng** đang ghi cổng 8080/8081; môi trường phát triển chạy 5173/5174. Thống nhất số cổng hiển thị hay bỏ số cổng khỏi thông báo?

---

## 12. Phương án đề xuất của phòng IT

Góc nhìn: BA (đúng nghiệp vụ), Security (không nới quyền), Dev/Architect (ít mã, không trùng logic), QA (kiểm chứng được), Ops (vận hành được trên live). Nguyên tắc chọn: **sửa tận gốc, giữ quyết định đã chốt của chủ dự án (menu admin 9 mục, một tài khoản admin), không thêm tính năng chưa có người dùng cần**.

### 12.1 Trả lời 6 câu hỏi ở mục 11

| # | Câu hỏi | Phương án chọn | Vì sao (và vì sao không chọn cách kia) |
|---|---|---|---|
| 1 | Nút Sửa/Huỷ của nhân viên | **Bỏ điều kiện quyền module khỏi các nút trên từng hồ sơ.** Quyền module chỉ quyết định *thấy màn hình nào* và *được tạo yêu cầu không*; thao tác trên một hồ sơ cụ thể do lớp 4 (chủ hồ sơ + trạng thái + SoD) quyết định — đúng như backend đang làm | Cấp `U`/`D` cho `REQUESTER` sẽ làm `U`/`D` mang nghĩa "sửa/xoá mọi yêu cầu" ở chỗ khác (màn hình quản trị dùng chung module), dễ mở nhầm quyền sau này. ServiceNow, Jira cũng tách quyền màn hình khỏi quyền trên bản ghi |
| 2 | Vai trò `AUDITOR` | **Ngừng sử dụng**: ẩn khỏi danh sách vai trò có thể gán, bỏ quyền `C` thừa, giữ mã trong DB để không vỡ dữ liệu cũ. Nhu cầu kiểm toán do admin đáp ứng qua tab "Nhật ký kiểm toán" (12.1-3) và **xuất báo cáo kiểm toán** (CSV/PDF có mã băm) khi cần đưa cho kiểm toán viên | Quy tắc "chỉ `admin@eas.com` vào cổng quản trị" là yêu cầu của chủ dự án; mở thêm cổng/chế độ cho kiểm toán viên là thêm bề mặt tấn công cho một nhu cầu hiếm |
| 3 | Menu quản trị 9 mục thiếu chức năng | **Giữ đúng 9 mục, đưa màn hình còn thiếu vào thành tab** trong mục cùng chủ đề (bảng 12.2). Không thêm mục menu | Giữ thiết kế đã chốt, khôi phục đủ năng lực vận hành; các màn hình đã có sẵn trong mã nên chi phí thấp |
| 4 | Trang "Quy định công ty" cho nhân viên | **Có.** Mục "Quy định công ty" trong nhóm "Tổ chức & công cụ", chỉ đọc: bản hiện hành, phiên bản, ngày hiệu lực, lịch sử thay đổi; đánh dấu "mới cập nhật" so với lần đọc trước; hộp thông báo cập nhật có nút "Xem quy định" dẫn tới đây | Nhân viên đã có quyền Xem; thông báo cập nhật cần chỗ để người dùng đối chiếu; quy định phải truy cập được mới có giá trị ràng buộc |
| 5 | Người theo dõi / tự chuyển lượt / duyệt qua email / duyệt hàng loạt | **Làm sau, theo thứ tự:** (a) Người theo dõi chỉ đọc; (b) Người duyệt tự chuyển lượt cho người duyệt khác cùng phạm vi (bắt buộc lý do, ghi nhật ký, giữ SoD). **Không làm:** duyệt qua email (rủi ro giả mạo link, chi phí bảo mật lớn hơn lợi ích khi đã có thông báo + hộp việc) và duyệt hàng loạt (AI tự duyệt đã xử lý nhóm A rủi ro thấp) | Ưu tiên tính năng tăng minh bạch, không nới quyền |
| 6 | Số cổng trong thông báo lỗi | **Bỏ số cổng**, dùng tên cổng ("Cổng Nhân viên", "Cổng Quản trị") và nút mở cổng đúng lấy từ cấu hình `VITE_CLIENT_PORTAL_URL` / `VITE_ADMIN_PORTAL_URL` | Số cổng khác nhau giữa dev/production, hiển thị sai gây nhầm |

### 12.2 Bố cục cổng quản trị (9 mục, có tab)

| Mục menu | Tab | Nguồn màn hình (đã có) |
|---|---|---|
| Tổng quan | Tổng quan · **Vận hành** (điều chuyển, gửi lại sự kiện lỗi) | `AdminDashboard`, `OperationsPage` |
| Yêu cầu & Quy trình | Loại yêu cầu · **Phiên bản cấu hình** (luồng duyệt, biểu mẫu, SLA: soạn → kiểm tra → công bố) · **SLA & nhắc hạn** | `RequestWorkflowsPage`, `PolicyWorkspace`, `SlaNotificationsPage` |
| Sơ đồ công ty | Sơ đồ · **Phòng ban** (thêm/sửa/ngừng, đổi cấp trên) | `OrgChart`, `IdentityAdmin` (departments) |
| Người dùng | Danh sách · **Phạm vi quyền** (gán vai trò theo phòng ban / loại yêu cầu, có hiệu lực từ–đến) | `UserManagementPage`, `IdentityAdmin` (memberships) |
| Phân quyền | Ma trận vai trò · Quyền riêng | `RolePermissionMatrixPage` |
| Quy định | (giữ nguyên) | `RegulationsManagementPage` |
| Quản trị AI | Trạng thái & học lại · Thử AI · **Luật AI thủ công** | `AiEngineManagementPage`, `AiPolicyAdmin` |
| Quản lý API | (giữ nguyên) | `ApiAdministration` |
| Phiên bản hệ thống | Nhật ký thay đổi · **Nhật ký quản trị** · **Kiểm toán hồ sơ** (xác minh chuỗi băm) · Xuất báo cáo | `SystemVersionsPage`, `AdminEvents`, `AuditLogPage` |

Tab ghi nhớ trên URL (`?tab=`) để chia sẻ link và nút quay lại hoạt động đúng.

### 12.3 Cải tiến nền tảng phân quyền (gốc rễ, tránh lỗi lặp lại)

1. **Server trả danh sách thao tác được phép cho từng hồ sơ.** `GET /api/v1/requests/<id>` thêm `allowed_actions` (ví dụ `["edit","submit","cancel"]`), tính bằng đúng hàm kiểm tra mà API ghi dùng. UI chỉ hiện nút có trong danh sách. Hiện logic này viết **hai lần** (`domain.js` và `service.py`) và đã lệch nhau (lỗi nút Sửa/Huỷ); một nguồn duy nhất xoá hẳn loại lỗi này.
2. **Định nghĩa rõ nghĩa X/C/U/D cho từng module** (bảng dưới) và ghi vào `eas.modules.description` để trang Phân quyền hiển thị đúng ý nghĩa khi admin bật/tắt:

   | Module | X | C | U | D |
   |---|---|---|---|---|
   | Yêu cầu & Quy trình (cổng nhân viên) | Thấy mục yêu cầu | Tạo yêu cầu mới | — (theo lớp 4) | — (theo lớp 4) |
   | Yêu cầu & Quy trình (cổng quản trị) | Xem loại yêu cầu, cấu hình | Thêm loại | Sửa loại, công bố cấu hình | Ngừng loại |
   | Người dùng | Xem danh sách | Tạo tài khoản | Sửa, gán phạm vi | Khoá |
   | Các module chỉ-admin | Chỉ `OPS_ADMIN`/`POLICY_ADMIN`; không bao giờ cấp cho nhân viên | | | |

3. **Giới hạn tần suất theo người dùng**, không chỉ theo IP. Hiện 300 request/phút **mỗi IP**: khi cả công ty đi qua một IP công cộng (NAT văn phòng), 137 người dùng chung hạn mức và sẽ bị chặn giờ cao điểm. Đề xuất: request đã đăng nhập tính theo `user_id` (300/phút/người); request chưa đăng nhập (đăng nhập, quên mật khẩu) vẫn tính theo IP.

### 12.4 Bảo mật trước khi đưa vào sử dụng thật

| Việc | Mức | Lý do |
|---|---|---|
| Buộc **đổi mật khẩu lần đầu** cho mọi tài khoản đang dùng mật khẩu chung `Password@123456` (`must_change_password = true`) | Bắt buộc | Mật khẩu chung là mật khẩu demo; ai biết một tài khoản là biết tất cả |
| **Xác thực 2 lớp (TOTP)** cho `admin@eas.com` | Bắt buộc | Một tài khoản nắm toàn quyền; lộ mật khẩu là mất toàn hệ thống |
| Giới hạn cổng quản trị theo **mạng/IP công ty** ở tầng proxy | Nên có | Giảm bề mặt tấn công của tài khoản duy nhất |
| Đổi mật khẩu DB và `INTERNAL_API_SECRET` đã từng in ra terminal | Bắt buộc | Đã khuyến nghị trước đó |
| Quy trình "mất quyền truy cập admin": tài khoản khẩn cấp niêm phong hoặc thủ tục khôi phục qua SQL Editor có biên bản | Nên có | Chỉ có một admin là điểm lỗi duy nhất |

### 12.5 Lộ trình thực hiện

| Đợt | Hạng mục | Ước lượng | Tiêu chí nghiệm thu |
|---|---|---|---|
| **P0 — sửa lỗi** (1 ngày) | 12.1-1 nút Sửa/Huỷ; 12.1-6 bỏ số cổng; 12.1-2 ngừng `AUDITOR` (data fix bỏ quyền `C`, ẩn khỏi danh sách gán) | 0,5–1 ngày | Nhân viên sửa/gửi lại/huỷ được hồ sơ của mình đúng trạng thái và không thấy nút ở hồ sơ người khác; test Playwright cho 4 vai trò |
| **P0 — bảo mật** | 12.4 đổi mật khẩu lần đầu, TOTP admin, xoay vòng secret | 1–2 ngày | 136 tài khoản bị yêu cầu đổi mật khẩu ở lần đăng nhập đầu; admin phải nhập mã TOTP |
| **P1 — khôi phục năng lực quản trị** | 12.2 tab trong 9 mục | 1–2 ngày | Admin đổi được luồng duyệt/SLA/phạm vi duyệt và xem nhật ký kiểm toán mà không cần SQL; menu vẫn đúng 9 mục |
| **P1 — gốc rễ phân quyền** | 12.3-1 `allowed_actions`; 12.3-3 giới hạn theo người dùng | 1–2 ngày | Không còn logic nút trùng lặp trong `domain.js`; tải 137 phiên đồng thời không bị `429` |
| **P1 — quy định cho nhân viên** | 12.1-4 trang "Quy định công ty" | 0,5–1 ngày | Từ hộp thông báo cập nhật mở được đúng quy định đã đổi |
| **P2 — minh bạch** | Người theo dõi; người duyệt tự chuyển lượt; hiện tên người nhận uỷ quyền trong lịch sử duyệt | 2–3 ngày | Mỗi thao tác có lý do và nằm trong nhật ký; không vi phạm SoD |
| **P2 — hiệu năng** | Cân nhắc chuyển DB sang vùng Singapore (hiện Sydney, ~300 ms mỗi lượt gọi từ Việt Nam) | Theo kế hoạch hạ tầng | Trang tải dưới 1 giây |

Mỗi đợt: sửa backend trước, kiểm thử trên bản sao live, rồi giao diện; cập nhật tài liệu này, changelog và kế hoạch trong `plans/`.

## 13. Tham chiếu mã nguồn

| Nội dung | Vị trí |
|---|---|
| Menu theo vai trò | `web_client/src/rolePolicy.js` (`ROLE_NAVIGATION`), `web_client/src/App.jsx` (`CLIENT_NAV`, `ADMIN_NAV`, `pageToModuleCode`) |
| Nút trên chi tiết hồ sơ | `web_client/src/domain.js` (`permissions`) |
| Quyền module | `eas.modules`, `eas.role_module_permission`, `eas.user_permissions`, `eas.get_effective_user_permissions`; API `GET /api/v1/permissions/me` |
| Chặn sai cổng | `api_core/authn/views.py` (`login`) |
| Endpoint và vai trò | `api_core/workflow/urls.py`, `api_core/workflow/views.py` (`@require_actor`) |
| Quản trị | `api_core/administration/*.py` |
| Máy trạng thái, SoD | `api_core/workflow/service.py` |
| AI học quy định, thông báo | `api_core/workflow/ai_learning.py`, migration `12_ai_learning_jobs_and_announcements.sql` |
| Circuit breaker | `api_core/catalog/integrations.py` |

| Quyền module (backend) | `api_core/authn/module_access.py` (`can`, `require_module`, `NEVER_FOR_EMPLOYEES`) |
| API cổng nhân viên | `api_core/administration/workspace.py` (`/api/v1/workspace/*`) |
| Nghỉ phép → trạng thái làm việc | `api_core/workflow/leave_sync.py` |
| Màn hình dùng chung 2 cổng | `web_client/src/apiBase.js` (`/api/v1/admin` ↔ `/api/v1/workspace`), `web_client/src/components/ClientRequestsHub.jsx` |

---

## 14. Client Phase 1–3 — đã triển khai (03/11/2026)

Kế hoạch: `plans/active/2026-11-03_client_phase_1_3_module_permissions.md`.

### 14.1 Nguyên tắc đã áp dụng

- **Quyền module do admin cấp quyết định cả giao diện lẫn API.** Admin bật "Xem" cho vai trò hoặc từng người ở trang Phân quyền → mục đó hiện trên sidebar cổng nhân viên (tự làm mới trong ~15 giây, không cần đăng nhập lại). Bật Thêm/Sửa/Xoá → nút tương ứng hiện; API `/api/v1/workspace/*` kiểm tra đúng quyền đó (không có quyền → `403`).
- **Trình duyệt không gọi Supabase.** Đặc tả đề nghị `supabase.schema('eas')` và Realtime; làm vậy trái AGENTS.md và migration 13 đã thu hồi quyền `anon`. Mọi dữ liệu đi qua API Django, kết quả nghiệp vụ như nhau (trạng thái AI 2 giây/lần, quyền 15 giây/lần).
- **Không ghi thẳng `eas.requests`.** 5 giai đoạn (Yêu cầu → Phê duyệt → Thực hiện → Nghiệm thu → Hoàn thành) là cách hiển thị của trạng thái thật; mọi thao tác đi qua quy trình có máy trạng thái, SoD và nhật ký.
- **Khoá khi AI học** dựa trên `client_maintenance_lock` (job AI đang chạy), không dựa trên `sync_status !== 'COMPLETED'` — vì AI học lỗi thì giữ luật cũ và phải mở khoá.

### 14.2 Cổng nhân viên

| Nhóm | Mục | Hiện khi | Nút thao tác |
|---|---|---|---|
| GIÁM SÁT | Tổng quan | Xem `dashboard` (mặc định có) | — (chỉ xem). Số liệu theo phạm vi: nhân viên = yêu cầu của mình; trưởng phòng = phòng mình phụ trách; người duyệt toàn công ty = toàn công ty |
| LUỒNG CÔNG VIỆC | Yêu cầu & Quy trình | Xem `requests_workflows` (mặc định có) | Tab: Tạo yêu cầu mới (cần Thêm) · Theo dõi 5 giai đoạn · Yêu cầu của tôi · Việc được giao (người duyệt/thực hiện/nghiệm thu) · **Cấu hình mẫu** (chỉ khi có Sửa hoặc Xoá) · Sơ đồ luồng · Quy trình AI |
| TỔ CHỨC & NHÂN SỰ | Sơ đồ tổ chức | Xem `org_chart` (mặc định có) | — |
| | Người dùng | Xem `users` (**mặc định không có**, admin cấp) | Thêm (Thêm) · Sửa, cập nhật nghỉ/công tác (Sửa) · Khoá/mở (Xoá). Không gán được vai trò Người phê duyệt (chỉ admin) |
| TRI THỨC | Quy định | Xem `regulations` (mặc định có) | Thêm / Sửa (phiên bản phụ) / Xoá (phiên bản chính) theo quyền; mỗi thay đổi kích hoạt AI học lại |
| QUẢN LÝ PHÒNG BAN | Tổng quan phòng ban, Nhân viên phòng ban | Có vai trò Người phê duyệt | — |
| TÀI KHOẢN | Tài khoản cá nhân | Luôn | Đổi mật khẩu; uỷ quyền phê duyệt (người duyệt) |

Header: tên trang · tìm kiếm · **trạng thái làm việc** (Đang làm / Nghỉ làm / Công tác) · sáng/tối · họ tên, chức danh, phòng ban · đăng xuất.

Tạo yêu cầu: mỗi mẫu hiện tên, nhóm, phân loại A/B/C, SLA, các bước, hệ thống tích hợp. Hệ thống tích hợp đang bị admin tắt → thẻ đỏ "Yêu cầu này hiện không thể sử dụng do kết nối API của hệ thống [Tên hệ thống] đang bị tắt.", nút Tạo bị khoá; server cũng chặn.

Nghỉ phép / Nghỉ phép đặc biệt / Công tác / Điều chỉnh chấm công (đi muộn, về sớm): khi được duyệt xong (kể cả AI tự duyệt) hệ thống ghi `user_leave_and_trips` → trạng thái làm việc đổi ngay trên cả 2 cổng.

Sửa / Huỷ hồ sơ của chính mình: theo chủ hồ sơ + trạng thái (đã sửa lỗi mục 3). Quyền Sửa/Xoá module "Yêu cầu & Quy trình" nay chỉ có nghĩa là **cấu hình mẫu yêu cầu**.

### 14.3 Kết quả nghiệm thu

| Kiểm thử | Môi trường | Kết quả |
|---|---|---|
| 5 kịch bản liên thông 2 cổng trên trình duyệt thật (`web_client/e2e/cross_portal_scenarios.mjs`, ảnh + báo cáo `web_client/test-results/cross-portal/report.html`) | Bản sao live (Postgres cục bộ) | **21/21 bước đạt** |
| Nghỉ phép hôm nay → người quản lý duyệt → trạng thái "Nghỉ làm" | Bản sao live | Đạt |
| Hồi quy chỉ đọc trên live (48 kiểm tra) + API cổng nhân viên theo quyền | Live | 48/48; API không có quyền trả 403 |
| Django / `npm test` / ESLint / ruff / build 2 cổng / kiểm tra bundle | — | 448 OK / 64 / 0 lỗi / sạch / đạt / đạt |

Chi tiết 5 kịch bản:
1. `admin@eas.com` vào Cổng Quản trị; bị chặn ở Cổng Nhân viên với thông báo "Từ chối truy cập…".
2. `hung.nguyen@eas.com` bị chặn ở Cổng Quản trị; vào Cổng Nhân viên, sidebar không có 4 module hệ thống; header đủ 5 thành phần.
3. Admin cấp quyền riêng "Người dùng" cho `hung.nguyen`: chưa cấp → không có mục; cấp Xem → mục hiện, không nút; thêm Thêm/Sửa/Xoá → từng nút hiện; khôi phục mặc định → mục biến mất.
4. Admin sửa quy định → cổng nhân viên hiện màn hình AI đang học (bước + %), tự đăng xuất sau 3 giây, nút đăng nhập bị khoá kèm khung tiến trình; AI xong → đăng nhập lại được và nhận hộp "Hệ thống đã cập nhật quy định vX".
5. Admin tắt API Nhân sự → mẫu Nghỉ phép báo không thể dùng, nút khoá; bật lại → dùng được (danh sách tự làm mới 15 giây).

### 14.4 Còn lại / cần chủ dự án lưu ý

- Live: cột `employee_code` của nhân viên đang trống (header hiển thị khi có dữ liệu).
- Thông báo chặn ở cổng quản trị còn ghi số cổng 8080/8081 (đề xuất mục 12.1-6).
- Cổng nhân viên hiện chạy dev ở `:5173`; trên máy này cổng 8080 đang bị Apache của EnterpriseDB chiếm.
- `@supabase/supabase-js` và `src/supabase.js` không còn được dùng — có thể gỡ khi bạn đồng ý.
