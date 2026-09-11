# Kế hoạch & Kiến trúc Hệ thống: Enterprise Approval System

Tài liệu này mô tả chi tiết các phân hệ (modules) và luồng hoạt động (workflows) cho Đề tài: **"Hệ thống tự động hóa quy trình xử lý yêu cầu nội bộ đa cấp tuân thủ theo quy định của doanh nghiệp"**.

## 1. Tổng quan Kiến trúc và Công nghệ (Ánh xạ từ mã nguồn mở)

Hệ thống được xây dựng trên kiến trúc Microservices/Monorepo, tích hợp các công nghệ và thư viện mã nguồn mở mạnh mẽ:

1. **Workflow & State Machine:**
   - Việc quản lý trạng thái của Yêu cầu (Request) từ `Khởi tạo -> Phê duyệt -> Hoàn tất` sẽ sử dụng **[django-river](https://github.com/javrasya/django-river.git)** (State Machine linh hoạt) hoặc **[viewflow](https://github.com/viewflow/viewflow.git)** (Workflow framework chuẩn BPMN). Điều này giúp tách biệt logic chuyển trạng thái ra khỏi code nghiệp vụ.
2. **Audit Log & Truy vết:**
   - Sử dụng **[django-auditlog](https://github.com/jazzband/django-auditlog.git)** để tự động theo dõi và ghi nhận mọi thay đổi trên cơ sở dữ liệu. Kết hợp với thuật toán Hash-chain SHA-256 tự viết để đảm bảo tính bất biến (Immutable).
3. **AI Support Service:**
   - Phân hệ AI được dựng độc lập dựa trên **[full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template.git)**. FastAPI cung cấp endpoint xử lý hình ảnh (OCR) và tóm tắt văn bản (LLM), giao tiếp nội bộ với Django qua REST API.
4. **Business Rule Engine (Cơ chế luật nghiệp vụ):**
   - Sử dụng **[Drools](https://github.com/kiegroup/drools.git)** thông qua KIE Server. Drools đóng vai trò "Bộ não" để phân tích: Dựa vào chức vụ người gửi, số tiền, loại yêu cầu -> Trả về kết quả: Ai phải duyệt? Mấy cấp? SLA bao lâu?

---

## 2. Phân rã Các Module Chức năng (Modules)

### 2.1. Module Quản trị Định danh & Tổ chức (Identity & Organization Module)
- **Chức năng:** Quản lý User, Roles (Nhân viên, Trưởng phòng, Giám đốc), Departments (Phòng ban), và Delegation (Ủy quyền phê duyệt khi vắng mặt).
- **Công nghệ:** Django Auth + JWT, phân quyền cấp Record (Row-level security nếu cần).

### 2.2. Module Quản lý Yêu cầu (Request Management Module)
- **Chức năng:** Cho phép người dùng tạo mới, lưu nháp, chỉnh sửa, đính kèm file và theo dõi trạng thái yêu cầu của mình.
- **Dữ liệu:** Các form động (Dynamic Forms) theo từng loại yêu cầu (Nghỉ phép, Thanh toán, Cấp phát thiết bị...).

### 2.3. Module Điều phối Quy trình (Workflow & State Module)
- **Chức năng:** 
  - Điều khiển vòng đời của Yêu cầu (Draft -> Pending Approval -> In Progress -> Done).
  - Tích hợp `django-river` để xử lý các logic rẽ nhánh (Từ chối -> Quay lại Khởi tạo, Yêu cầu bổ sung thông tin).
- **SLA & Escalation:** Bộ đếm thời gian. Nếu quá thời gian SLA không ai duyệt, hệ thống kích hoạt cảnh báo (Celery/Redis) để nhắc nhở hoặc tự động báo cáo lên cấp cao hơn (Escalation).

### 2.4. Module Đánh giá Luật Nghiệp vụ (Business Rule Engine Module)
- **Chức năng:** Giao tiếp với Drools KIE Server.
- **Hoạt động:** Khi Yêu cầu được gửi đi, Django bóc tách dữ liệu JSON gửi sang Drools. Drools chạy tập luật `.drl` và trả về `ApprovalChain` (Danh sách những người/phòng ban cần duyệt).

### 2.5. Module Trợ lý AI (AI Assistant Module)
- **Chức năng:** FastAPI cung cấp 3 dịch vụ chính:
  - **OCR:** Bóc tách thông tin từ hóa đơn, chứng từ đính kèm (giảm nhập liệu thủ công).
  - **Summarize:** Dùng LLM tóm tắt các yêu cầu quá dài hoặc phức tạp, giúp người phê duyệt nắm bắt nhanh (thích hợp hiển thị trên Mobile).
  - **Anomaly Detection:** Chấm điểm rủi ro (Risk Scoring). Ví dụ: Yêu cầu chi tiêu vượt mức trung bình của tháng -> Gắn cờ cảnh báo rủi ro cao.

### 2.6. Module Ghi nhận Kiểm toán (Audit & Compliance Module)
- **Chức năng:** 
  - Dùng `django-auditlog` để ghi nhận: Ai, làm gì, lúc nào, giá trị cũ/mới.
  - Sau mỗi thao tác, tạo một Block mới trong bảng `ImmutableAuditLog` với `Hash = SHA256(Hash_Previous + Data)`.
  - Đồng bộ log sang Elasticsearch để phục vụ việc Admin tìm kiếm nhanh chóng.

### 2.7. Module Thông báo (Notification Module)
- **Chức năng:** Gắn với vòng đời Workflow để gửi Email, In-app Notification (React) và Push Notification qua Firebase (FCM) tới ứng dụng Flutter.

---

## 3. Phân loại Yêu cầu và Cơ chế Trọng số (Request Types & Risk Weights)

Để tối ưu hóa thời gian xử lý và giảm tải cho cấp quản lý, hệ thống áp dụng cơ chế đánh trọng số rủi ro (Risk Weight) cho từng loại yêu cầu từ 1 đến 5. 

- **Trọng số từ 1 đến 2 (Rủi ro thấp):** Được đưa vào luồng **AI Tự động xử lý**. AI Agent chạy ngầm sẽ tự động trích xuất thông tin, đối chiếu với quỹ/hạn mức, luật công ty. Nếu hợp lệ, AI sẽ tự động thay mặt hệ thống ra quyết định **Phê duyệt ngay lập tức (Auto-Approve)**. Nếu AI thấy có bất thường (dấu hiệu gian lận), nó mới đẩy lên duyệt thủ công.
- **Trọng số từ 3 đến 5 (Rủi ro trung bình - cao):** Bắt buộc phải đưa vào luồng **Phê duyệt thủ công đa cấp**. AI lúc này chỉ đóng vai trò Trợ lý (tóm tắt, trích xuất OCR, cảnh báo) chứ không có quyền tự quyết.

### Danh mục Phân loại Yêu cầu theo Domain (Domain-based Request Catalog)

Hệ thống quản lý 4 nhóm yêu cầu cốt lõi. Mỗi loại yêu cầu được gán Trọng số rủi ro (Risk Weight) để hệ thống tự động điều hướng sang AI duyệt (Auto-Approve) hoặc đưa vào luồng duyệt thủ công (Manual Approval).

#### I. Nhóm Hành chính - Nhân sự (HR & Admin)
*Đặc thù: Các tác vụ vận hành văn phòng thường ngày, số lượng nhiều, liên quan trực tiếp đến quyền lợi nhân viên, cần giải quyết nhanh chóng (Real-time).*

| Loại Yêu cầu | Trọng số | Cơ chế xử lý | Ghi chú / Điều kiện AI & Rule Engine |
|---|:---:|---|---|
| **Leave Request (Yêu cầu nghỉ phép)**<br>Nghỉ phép năm, ốm, chế độ, WFH | 1-3 | 🤖 **AI Auto-Approve** / 🧑 **Manual (1 cấp)** | AI quét quỹ phép năm. Nghỉ < 3 ngày: Tự động cập nhật hệ thống. Nghỉ >= 3 ngày: Trưởng phòng duyệt để tiện sắp xếp công việc. |
| **Equipment/Asset Request (Cấp phát tài sản)**<br>Cấp laptop, tai nghe, văn phòng phẩm | 2-3 | 🤖 **AI Auto-Approve** / 🧑 **Manual (1 cấp)** | AI kiểm tra tồn kho. Văn phòng phẩm lặt vặt: Tự động duyệt. Thiết bị giá trị (Laptop): Admin / IT Helpdesk duyệt. |
| **Onboarding/Offboarding Request**<br>Cấp/thu hồi tài khoản email, máy móc | 3-4 | 🧑 **Manual (1-2 cấp)** | Trưởng phòng tạo yêu cầu -> Admin/IT cấp phát và xác nhận. Cần tuân thủ quy trình bảo mật nội bộ. |
| **Overtime (OT) Request**<br>Đăng ký làm thêm giờ, tính OT / nghỉ bù | 2 | 🧑 **Manual (1 cấp)** | AI đối chiếu giới hạn giờ làm thêm trong tháng. Trưởng phòng phê duyệt theo kế hoạch công việc dự án. |

#### II. Nhóm Tài chính - Kế toán (Finance & Accounting)
*Đặc thù: Luôn gắn liền với dòng tiền, ngân sách công ty. Cần Drools Rule Engine phân cấp duyệt theo hạn mức giá trị một cách chặt chẽ.*

| Loại Yêu cầu | Trọng số | Cơ chế xử lý | Ghi chú / Điều kiện AI & Rule Engine |
|---|:---:|---|---|
| **Payment Request (Đề nghị thanh toán)**<br>Chi tiền tạm ứng, mua sắm, thanh toán cho nhà cung cấp | 4-5 | 🧑 **Manual (2-3 cấp)** | AI OCR bóc tách hóa đơn, tự động so sánh với đề xuất. Drools kiểm tra hạn mức và định tuyến duyệt (Trưởng phòng -> Kế toán trưởng -> Giám đốc). |
| **Reimbursement Request (Hoàn ứng/Thanh toán)**<br>Hoàn lại tiền nhân viên đã ứng trước (tiếp khách, di chuyển) | 3-4 | 🧑 **Manual (1-2 cấp)** | AI hỗ trợ kiểm tra chéo hóa đơn bán lẻ, phát hiện hóa đơn trùng lặp/giả mạo. Trưởng phòng & Kế toán duyệt chi. |

#### III. Nhóm Công nghệ thông tin / Kỹ thuật (IT / Tech Support)
*Đặc thù: Quy trình chặt chẽ, liên quan đến tính bảo mật, toàn vẹn hệ thống và cấp quyền dữ liệu.*

| Loại Yêu cầu | Trọng số | Cơ chế xử lý | Ghi chú / Điều kiện AI & Rule Engine |
|---|:---:|---|---|
| **IT Support Ticket / Access Request**<br>Báo lỗi IT, xin cấp quyền truy cập phần mềm/dữ liệu (Jira, Server...) | 2-4 | 🤖 **AI Hỗ trợ** / 🧑 **Manual (1-2 cấp)** | Xin quyền truy cập Data/Server (Rủi ro cao): Trưởng phòng & Tech Lead duyệt. Báo lỗi IT thông thường: Tự động phân luồng cho IT Support. |
| **Software License Request**<br>Đề nghị mua bản quyền phần mềm mới | 4 | 🧑 **Manual (2 cấp)** | Drools kiểm tra ngân sách IT. Tech Lead và Kế toán duyệt để mua sắm. |

#### IV. Nhóm Vận hành - Mua sắm (Operations & Procurement)
*Đặc thù: Đảm bảo cơ sở vật chất và công cụ phục vụ kinh doanh, vận hành liên tục.*

| Loại Yêu cầu | Trọng số | Cơ chế xử lý | Ghi chú / Điều kiện AI & Rule Engine |
|---|:---:|---|---|
| **Purchase Requisition (Yêu cầu mua sắm)**<br>Mua sắm thiết bị, công cụ phòng ban, nguyên vật liệu dự án | 4-5 | 🧑 **Manual (2-3+ cấp)** | AI phân tích báo giá so với thị trường. Drools định tuyến duyệt dựa trên ngân sách bộ phận (Trưởng phòng -> Mua sắm -> Giám đốc). |
| **Facility Maintenance Request**<br>Báo cáo hỏng hóc văn phòng (điều hòa, bóng đèn, bàn ghế) | 1-2 | 🤖 **AI Auto-Approve** | AI phân loại mức độ khẩn cấp. Tự động đẩy ticket cho đội vận hành/bảo trì tòa nhà sửa chữa (Không cần duyệt phức tạp). |

---

## 4. Chi tiết Các Luồng Hoạt động (Workflows)

### Luồng 1: Khởi tạo và Phân loại Yêu cầu (Request Creation)
1. Nhân viên (Requester) điền thông tin form và upload hóa đơn/chứng từ lên **Web/Mobile**.
2. **AI Module** tự động đọc ảnh OCR, trích xuất con số và điền vào form (nếu có).
3. Người dùng xác nhận và bấm "Gửi yêu cầu".
4. Trạng thái chuyển thành `EVALUATING`.
5. **Backend (Django)** đóng gói dữ liệu yêu cầu, gọi sang **Drools KIE Server**.
6. **Drools** trả về quy tắc SLA và Danh sách người duyệt (Ví dụ: Cấp 1 -> Trưởng phòng, Cấp 2 -> Giám đốc tài chính).
7. Gắn danh sách duyệt vào Yêu cầu, chuyển trạng thái sang `PENDING_APPROVAL_L1`. Hệ thống gửi Push Notification cho Trưởng phòng.

### Luồng 2: Phê duyệt Đa cấp (Multi-level Approval)
1. Trưởng phòng nhận thông báo trên **Mobile App (Flutter)**. Mở app xem tóm tắt nội dung (đã được AI rút gọn).
2. Trưởng phòng quyết định:
   - **Phê duyệt:** Trạng thái chuyển sang `PENDING_APPROVAL_L2` (hoặc `APPROVED` nếu chỉ có 1 cấp).
   - **Từ chối:** Trạng thái chuyển thành `REJECTED`, quy trình kết thúc.
   - **Yêu cầu bổ sung:** Trạng thái về `NEEDS_INFO`, Requester phải cập nhật thêm giấy tờ.
3. Trong lúc phê duyệt, **AI Module** có thể cảnh báo "Yêu cầu có dấu hiệu vượt hạn mức phòng ban", giúp Trưởng phòng chú ý.
4. Mọi quyết định đều được **Audit Module** ghi log và ký SHA-256.

### Luồng 3: Thực hiện và Nghiệm thu (Execution & Acceptance)
1. Sau khi Yêu cầu được phê duyệt hoàn toàn (`APPROVED`), nó được chuyển sang phòng ban thực hiện (Ví dụ: Kế toán chi tiền, IT cấp laptop). Trạng thái: `IN_PROGRESS`.
2. Người thực hiện (Executor) hoàn thành công việc, đính kèm kết quả (ủy nhiệm chi, biên bản bàn giao) -> Bấm "Hoàn thành".
3. Trạng thái chuyển sang `WAITING_FOR_ACCEPTANCE`.
4. Người khởi tạo (Requester) kiểm tra và bấm "Nghiệm thu".
5. Quy trình kết thúc, trạng thái cuối cùng: `COMPLETED`.

### Luồng 4: Theo dõi SLA và Leo thang (SLA Monitoring & Escalation)
1. **Celery Worker** (chạy nền) quét các yêu cầu định kỳ (15 phút/lần).
2. Phát hiện Yêu cầu A nằm ở bước "Chờ Giám đốc duyệt" quá 24h (vi phạm SLA).
3. Hệ thống gửi thông báo Reminder (Nhắc nhở) cho Giám đốc.
4. Nếu quá 48h, hệ thống tự động Escalation (Leo thang) báo cáo lên Tổng giám đốc hoặc bộ phận Admin theo cấu hình, và ghi cảnh báo vi phạm tuân thủ vào Audit Log.

---

## 5. Tích hợp Công nghệ vào Các Tầng

- **Tầng Frontend (React.js):** 
  - Khai báo giao diện Workflow dưới dạng sơ đồ cây để người dùng xem yêu cầu của họ đang tắc ở đâu.
  - Sử dụng Form builder động tùy loại yêu cầu.
- **Tầng Mobile (Flutter):**
  - Tập trung tối ưu UX cho tính năng *Duyệt nhanh* (Quick Approve). Hỗ trợ Swipe (vuốt) phải để Duyệt, trái để Từ chối. Tích hợp sinh trắc học (FaceID/Fingerprint) khi duyệt các yêu cầu có rủi ro cao.
- **Tầng Backend (Django + FastAPI):**
  - Tách bạch rõ: logic quản lý state (`django-river`), logic lưu vết (`django-auditlog`), logic quy tắc (`Drools`), và tác vụ AI nặng (`FastAPI`).

Tài liệu này đóng vai trò như kim chỉ nam để triển khai các module trong cấu trúc thư mục đã tạo.
