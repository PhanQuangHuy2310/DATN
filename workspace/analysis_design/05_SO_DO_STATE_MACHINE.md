# HỒ SƠ THIẾT KẾ TOÀN DIỆN CÁC SƠ ĐỒ MÁY TRẠNG THÁI (STATE MACHINE DIAGRAMS)
## DỰ ÁN: HỆ THỐNG TỰ ĐỘNG HÓA QUY TRÌNH XỬ LÝ YÊU CẦU NỘI BỘ ĐA CẤP (EAS)
### HỘI ĐỒNG THẨM ĐỊNH IT 15 NĂM KINH NGHIỆM: BA, PM, DEV, UI/UX, AI, QA, PO

---

## 1. NGUYÊN TẮC THIẾT KẾ MÁY TRẠNG THÁI HỮU HẠN (FINITE STATE MACHINE - FSM)

Theo tiêu chuẩn UML 2.5 State Machine Diagrams và đối soát trực tiếp mã nguồn động cơ chuyển trạng thái trong `api_core/workflow/service.py`, `api_core/workflow/ai_learning.py` và các Trigger ràng buộc trong `database/migrations/`, hệ thống EAS áp dụng các nguyên tắc thiết kế toán học khắt khe:
1. **Tính đóng của tập trạng thái (Completeness & Closure):** Mọi thực thể nghiệp vụ chỉ được phép tồn tại ở một trạng thái duy nhất trong tập hợp trạng thái hợp lệ đã định nghĩa.
2. **Chuyển trạng thái có điều kiện bảo vệ (Guarded Transitions):** Không có trạng thái nào chuyển đổi tự do. Mọi chuyển đổi bắt buộc phải có sự kiện kích hoạt (Event Trigger), vai trò tác nhân có thẩm quyền (Actor Guard) và điều kiện dữ liệu thỏa mãn (Data Condition).
3. **Tính đơn điệu của các trạng thái kết thúc (Terminal States Immutability):** Các trạng thái cuối cùng như `COMPLETED`, `REJECTED`, `WITHDRAWN`, `CANCELED` là bất biến tuyệt đối. Khi đã vào trạng thái kết thúc, thực thể không bao giờ được phép chỉnh sửa dữ liệu hoặc hồi sinh lại (No Zombie Transitions).
4. **Cơ chế kiểm soát phiên bản và ghi nhật ký đồng thời (Optimistic Locking & Audit Coupling):** Mọi lần chuyển đổi trạng thái bắt buộc phải tăng trường `version` của thực thể và ghi nhận một dòng sự kiện mới vào sổ cái kiểm toán `eas.audit_log` trong cùng một giao dịch ACID.

---

## 2. DANH MỤC TOÀN BỘ 8 SƠ ĐỒ MÁY TRẠNG THÁI TRONG HỆ THỐNG EAS

---

### SƠ ĐỒ 1: HÌNH 2.16 - MÁY TRẠNG THÁI VÒNG ĐỜI HỒ SƠ YÊU CẦU (REQUEST FSM - ST-01)
*Động cơ vòng đời hồ sơ lõi bao phủ toàn bộ 18 loại đơn và 3 mẫu vòng đời A, B, C.*

```mermaid
stateDiagram-v2
    [*] --> DRAFT : Khởi tạo đơn mới (CREATE_DRAFT)
    
    DRAFT --> DRAFT : Cập nhật nội dung / Đính kèm tệp
    DRAFT --> SUBMITTED : Nộp hồ sơ (SUBMIT / Idempotency OK)
    DRAFT --> CANCELED : Hủy bản nháp (DELETE_DRAFT)

    SUBMITTED --> COMPLETED : AI Auto-Approval (Template A, Risk <= 2)
    SUBMITTED --> IN_REVIEW : Chuyển luồng duyệt cấp 1 (SPAWN_STEPS)
    SUBMITTED --> WITHDRAWN : Người tạo đơn rút lại (WITHDRAW)

    IN_REVIEW --> IN_REVIEW : Quản lý cấp trung duyệt, chuyển cấp tiếp theo (STEP_APPROVED)
    IN_REVIEW --> NEEDS_INFO : Cấp trên yêu cầu làm rõ (REQUEST_INFO)
    IN_REVIEW --> REJECTED : Cấp trên bác bỏ (REJECT_REQUEST)
    IN_REVIEW --> WITHDRAWN : Người tạo đơn rút lại trước khi duyệt xong (WITHDRAW)

    NEEDS_INFO --> SUBMITTED : Người tạo đơn bổ sung và nộp lại (RESUBMIT)
    NEEDS_INFO --> WITHDRAWN : Người tạo đơn không muốn tiếp tục (WITHDRAW)

    IN_REVIEW --> COMPLETED : Duyệt xong cấp cuối cùng (Template A)
    IN_REVIEW --> READY_FOR_EXECUTION : Duyệt xong cấp cuối cùng (Template B hoặc C)

    READY_FOR_EXECUTION --> IN_PROGRESS : Chuyên viên tiếp nhận (CLAIM_LEASE)
    READY_FOR_EXECUTION --> BLOCKED : Báo sự cố không thể thi công (REPORT_ISSUE)
    
    BLOCKED --> READY_FOR_EXECUTION : Quản trị viên xử lý vướng mắc / Gán người khác (RESOLVE_ISSUE)
    
    IN_PROGRESS --> BLOCKED : Phát sinh vướng mắc trong lúc thi công
    IN_PROGRESS --> READY_FOR_EXECUTION : Hết hạn Lease thi công mà không hoàn tất (AUTO_RECLAIM)
    
    IN_PROGRESS --> COMPLETED : Chuyên viên nộp kết quả (Template B)
    IN_PROGRESS --> WAITING_FOR_ACCEPTANCE : Chuyên viên nộp kết quả (Template C)

    WAITING_FOR_ACCEPTANCE --> READY_FOR_EXECUTION : Nghiệm thu không đạt, bắt làm lại (REWORK)
    WAITING_FOR_ACCEPTANCE --> COMPLETED : Nghiệm thu đạt chuẩn, xác nhận hoàn thành (ACCEPT)

    COMPLETED --> [*]
    REJECTED --> [*]
    WITHDRAWN --> [*]
    CANCELED --> [*]
```

---

### SƠ ĐỒ 2: HÌNH 2.17 - MÁY TRẠNG THÁI CỦA MỘT LƯỢT PHÊ DUYỆT (APPROVAL STEP FSM - ST-02)
*Vòng đời của từng chặng duyệt trong ma trận thẩm quyền đa cấp.*

```mermaid
stateDiagram-v2
    [*] --> PENDING : Khởi tạo lộ trình duyệt (SPAWN_ROUTE)
    
    PENDING --> ACTIVE : Bước trước hoàn tất, kích hoạt bước hiện tại (ACTIVATE_STEP)
    PENDING --> SKIPPED : Cấp dưới duyệt vượt quyền hoặc điều kiện hạn mức bỏ qua bước này (SKIP_STEP)

    ACTIVE --> APPROVED : Người duyệt bấm Phê duyệt (APPROVE_STEP)
    ACTIVE --> REJECTED : Người duyệt bấm Từ chối (REJECT_STEP)
    ACTIVE --> NEEDS_INFO : Người duyệt yêu cầu làm rõ (REQUEST_INFO)
    ACTIVE --> REVOKED : Quyết định tự duyệt của AI bị thu hồi trong 24h (REVOKE_AI)
    ACTIVE --> ACTIVE : Quản trị viên điều chuyển người duyệt khác (REASSIGN_ASSIGNEE)

    NEEDS_INFO --> PENDING : Hồ sơ được bổ sung nộp lại, đưa bước duyệt về chờ kích hoạt
    
    APPROVED --> [*]
    REJECTED --> [*]
    SKIPPED --> [*]
    REVOKED --> [*]
```

---

### SƠ ĐỒ 3: HÌNH 2.18 - MÁY TRẠNG THÁI LẦN THỰC HIỆN CÔNG VIỆC (EXECUTION ATTEMPT FSM - ST-03)
*Vòng đời kiểm soát chuyên viên thi công và các lần thử nghiệm thu.*

```mermaid
stateDiagram-v2
    [*] --> READY : Đơn duyệt xong chuyển sang thi công (ENTER_EXECUTION)
    
    READY --> RUNNING : Chuyên viên bấm Tiếp nhận (CLAIM_LEASE)
    
    RUNNING --> READY : Hết hạn thời gian Lease 24h không nộp kết quả (LEASE_EXPIRED_RECLAIM)
    RUNNING --> BLOCKED : Chuyên viên báo vướng mắc hết hàng / sai quy cách (REPORT_OBSTACLE)
    
    BLOCKED --> RUNNING : Quản trị viên can thiệp xử lý sự cố (RESOLVE_OBSTACLE)
    BLOCKED --> READY : Quản trị viên điều chuyển sang chuyên viên khác (REASSIGN_EXECUTOR)

    RUNNING --> SUBMITTED : Chuyên viên nộp biên bản và chứng từ hoàn thành (SUBMIT_RESULT)

    SUBMITTED --> ACCEPTED : Nghiệm thu đạt chuẩn (ACCEPT_VERDICT)
    SUBMITTED --> REWORK : Nghiệm thu không đạt yêu cầu bàn giao (REWORK_VERDICT)
    
    REWORK --> READY : Khởi tạo lượt thử mới (ATTEMPT_SEQ + 1)

    ACCEPTED --> [*]
```

---

### SƠ ĐỒ 4: HÌNH 2.19 - MÁY TRẠNG THÁI BẢN PHÁT HÀNH CẤU HÌNH ĐỘNG (CONFIG RELEASE FSM - ST-07)
*Vòng đời quản lý phiên bản cấu hình quy chế (Semantic Versioning & Immutability).*

```mermaid
stateDiagram-v2
    [*] --> DRAFT : Clone bản phát hành đang hoạt động (CLONE_RELEASE)
    
    DRAFT --> DRAFT : Chỉnh sửa Form Schema / Route / SLA / Automation Weight
    DRAFT --> VALIDATED : Kiểm tra tính hợp lệ và Dry-run phân giải luồng thành công (VALIDATE_CONFIG)
    
    VALIDATED --> DRAFT : Phát hiện thiếu sót, quay lại chỉnh sửa (EDIT_MORE)
    VALIDATED --> PUBLISHED : Quản trị viên bấm Ban hành chính thức (PUBLISH_RELEASE)

    PUBLISHED --> SUPERSEDED : Có bản phát hành mới hơn được ban hành thay thế (NEW_RELEASE_PUBLISHED)
    SUPERSEDED --> ARCHIVED : Hết thời hạn lưu trữ lịch sử, lưu kho lưu trữ (ARCHIVE)

    ARCHIVED --> [*]
```

---

### SƠ ĐỒ 5: HÌNH PL-29 - MÁY TRẠNG THÁI TỆP ĐÍNH KÈM VÀ QUÉT ANTIVIRUS (ATTACHMENT FSM - ST-04)
*Vòng đời an ninh của tệp tin đính kèm từ khi nạp luồng byte đến lưu trữ an toàn.*

```mermaid
stateDiagram-v2
    [*] --> UPLOADED : Tiếp nhận luồng byte qua Gateway (STREAM_UPLOAD)
    
    UPLOADED --> SCANNING : Đổi tên UUID và chuyển giao ClamAV (DISPATCH_CLAMAV)
    
    SCANNING --> CLEAN : Quét không phát hiện mã độc (ANTIVIRUS_PASS)
    SCANNING --> INFECTED : Phát hiện Virus / Webshell / Malware (ANTIVIRUS_FAIL)

    INFECTED --> QUARANTINED : Cách ly tệp, ghi cảnh báo an ninh (QUARANTINE_FILE)
    QUARANTINED --> DELETED : Tự động xóa vĩnh viễn tệp nguy hại (PURGE_INFECTED)

    CLEAN --> LINKED : Đơn được lưu nháp hoặc nộp chính thức (ATTACH_TO_REQUEST)
    CLEAN --> DELETED : Quá 24h không liên kết vào đơn nào (PURGE_ORPHAN)

    LINKED --> DELETED : Người dùng xóa tệp hoặc Đơn bị hủy (DETACH_DELETE)

    DELETED --> [*]
```

---

### SƠ ĐỒ 6: HÌNH PL-30 - MÁY TRẠNG THÁI CẢNH BÁO VI PHẠM SLA (SLA ALERT FSM - ST-05)
*Tiến trình giám sát cam kết dịch vụ theo ngưỡng thời gian thời gian thực.*

```mermaid
stateDiagram-v2
    [*] --> NORMAL : Hồ sơ nộp vào hệ thống, bắt đầu đếm giờ (INIT_SLA)
    
    NORMAL --> NORMAL : Thời gian đã trôi qua < 80% hạn mức cam kết (IN_TARGET)
    NORMAL --> WARNING_SENT : Thời gian đạt từ 80% đến 99% hạn mức (REACH_80_PERCENT)
    
    WARNING_SENT --> RESOLVED : Cán bộ xử lý xong đơn trước hạn mức (RESOLVE_IN_TIME)
    WARNING_SENT --> BREACHED : Thời gian vượt quá 100% hạn mức cam kết (EXCEED_100_PERCENT)

    BREACHED --> ESCALATED : Hệ thống tự động kích hoạt quy trình Leo thang (TRIGGER_ESCALATION)
    
    ESCALATED --> RESOLVED : Cán bộ hoặc cấp trên xử lý xong hồ sơ trễ hạn (RESOLVE_LATE)

    NORMAL --> RESOLVED : Xử lý xong siêu tốc khi chưa chạm ngưỡng 80%
    
    RESOLVED --> [*]
```

---

### SƠ ĐỒ 7: HÌNH PL-31 - MÁY TRẠNG THÁI PHIÊN XÁC THỰC NGƯỜI DÙNG (AUTH SESSION FSM - ST-08)
*Vòng đời phiên làm việc an toàn, kiểm soát Kỷ nguyên An ninh (Security Epoch).*

```mermaid
stateDiagram-v2
    [*] --> CREATED : Đăng nhập thành công với Argon2id (LOGIN_SUCCESS)
    
    CREATED --> ACTIVE : Cấp phát Session Token và Cookie HttpOnly (ISSUE_COOKIE)
    
    ACTIVE --> ACTIVE : Thực hiện các thao tác trong thời gian hợp lệ (REQUEST_ACTIVITY)
    ACTIVE --> REFRESHED : Tự động gia hạn thời gian sống TTL khi người dùng thao tác liên tục
    
    ACTIVE --> EXPIRED : Không thao tác sau 8 giờ liên tục (IDLE_TIMEOUT)
    ACTIVE --> REVOKED : Người dùng bấm Đăng xuất chủ động (LOGOUT)
    
    ACTIVE --> TERMINATED_BY_EPOCH : Quản trị viên thay đổi phân quyền / Tước quyền (EPOCH_INCREMENTED)

    REFRESHED --> EXPIRED : Hết hạn thời gian tối đa
    REFRESHED --> TERMINATED_BY_EPOCH : Kỷ nguyên an ninh thay đổi

    EXPIRED --> [*]
    REVOKED --> [*]
    TERMINATED_BY_EPOCH --> [*]
```

---

### SƠ ĐỒ 8: BỔ SUNG MÁY TRẠNG THÁI TÁC VỤ HỌC MÁY AI (AI LEARNING JOB FSM - ST-09)
*Vòng đời kiểm soát tác vụ học quy định với khóa bảo trì tự động và xác minh mô hình.*

```mermaid
stateDiagram-v2
    [*] --> QUEUED : Admin cập nhật quy chế / Hệ thống kích hoạt học lại (ENQUEUE_JOB)
    
    QUEUED --> RUNNING : Worker chuyên trách tiếp nhận Lease độc quyền (CLAIM_JOB_LEASE)
    QUEUED --> FAILED : Quá tải hàng đợi hoặc lỗi cấu hình đầu vào (VALIDATION_ERROR)

    RUNNING --> SNAPSHOT_DONE : Bước 1: Chụp bộ quy định thành công (25%)
    SNAPSHOT_DONE --> LEARNED : Bước 2: Trích xuất luật và huấn luyện lại thành công (50%)
    
    LEARNED --> VERIFYING : Bước 3: Đẩy sang AI Service và chạy Bộ kiểm thử Vàng (75%)
    
    VERIFYING --> FAILED : Điểm F1-Score < 0.95 hoặc có vi phạm logic an toàn
    VERIFYING --> APPLIED : Bộ kiểm thử Vàng đạt chuẩn 100%, công bố phiên bản mới (100%)

    RUNNING --> FAILED : Worker bị crash hoặc timeout đứt quãng
    
    FAILED --> QUEUED : Tự động thử lại có giới hạn (Attempts < 3)
    FAILED --> UNRECOVERABLE : Quá số lần thử lại cho phép, giữ nguyên mô hình cũ an toàn

    APPLIED --> [*]
    UNRECOVERABLE --> [*]
```

---

## 3. MA TRẬN CHUYỂN TRẠNG THÁI YÊU CẦU VÀ ĐỐI SOÁT MÃ NGUỒN (RTM MATRIX)

| Trạng Thái Ban Đầu | Sự Kiện Kích Hoạt | Trạng Thái Đích | Điều Kiện Bảo Vệ (Guard Condition) | Mã Nguồn Triển Khai |
|:---|:---|:---|:---|:---|
| `None` (Mới) | `CREATE_DRAFT` | `DRAFT` | Người dùng đã đăng nhập hợp lệ, chọn loại đơn có Active Release. | `api_core/workflow/views.py` |
| `DRAFT` | `SUBMIT` | `SUBMITTED` | Điền đủ các trường bắt buộc, có Idempotency-Key, tệp đính kèm sạch mã độc. | `api_core/workflow/service.py` |
| `SUBMITTED` | `AI_AUTO_APPROVE` | `COMPLETED` | Template A + Điểm rủi ro AI <= 2 + Hạn mức ngân sách OK + Circuit Breaker BẬT. | `api_core/workflow/service.py` |
| `SUBMITTED` | `SPAWN_STEPS` | `IN_REVIEW` | Không đủ điều kiện tự duyệt, phân giải ít nhất 1 cấp quản lý phê duyệt. | `api_core/workflow/service.py` |
| `SUBMITTED` / `IN_REVIEW` | `WITHDRAW` | `WITHDRAWN` | Người thực hiện phải là chính chủ (`owner_id`), đơn chưa duyệt xong hoàn toàn. | `api_core/workflow/service.py` |
| `IN_REVIEW` | `REJECT` | `REJECTED` | Người duyệt có vai trò hợp lệ, bắt buộc nhập lý do từ chối. | `api_core/workflow/service.py` |
| `IN_REVIEW` | `NEEDS_INFO` | `NEEDS_INFO` | Người duyệt yêu cầu bổ sung, bắt buộc nhập nội dung cần làm rõ. | `api_core/workflow/service.py` |
| `NEEDS_INFO` | `RESUBMIT` | `SUBMITTED` | Người tạo đơn bổ sung thông tin/tệp mới, tăng số `revision_number`. | `api_core/workflow/service.py` |
| `IN_REVIEW` | `APPROVE` (Final A) | `COMPLETED` | Cấp duyệt cuối cùng hoàn tất trên loại đơn Template A (Chỉ phê duyệt). | `api_core/workflow/service.py` |
| `IN_REVIEW` | `APPROVE` (Final B/C) | `READY_FOR_EXECUTION`| Cấp duyệt cuối cùng hoàn tất trên loại đơn Template B hoặc C. | `api_core/workflow/service.py` |
| `READY_FOR_EXECUTION` | `CLAIM` | `IN_PROGRESS` | Chuyên viên thuộc đúng bộ phận chuyên trách, chưa có ai nhận trước. | `api_core/workflow/service.py` |
| `IN_PROGRESS` | `REPORT_ISSUE` | `BLOCKED` | Chuyên viên phát sinh sự cố không thể tiếp tục (hết hàng, sai linh kiện). | `api_core/workflow/service.py` |
| `BLOCKED` | `RESOLVE_ISSUE` | `READY_FOR_EXECUTION`| Quản trị viên xử lý vướng mắc hoặc gán chuyên viên khác thi công. | `api_core/workflow/ops_service.py` |
| `IN_PROGRESS` | `SUBMIT_RESULT` (B) | `COMPLETED` | Chuyên viên nộp kết quả trên loại đơn Template B (Không cần nghiệm thu). | `api_core/workflow/service.py` |
| `IN_PROGRESS` | `SUBMIT_RESULT` (C) | `WAITING_FOR_ACCEPTANCE`| Chuyên viên nộp kết quả trên loại đơn Template C (Bắt buộc nghiệm thu). | `api_core/workflow/service.py` |
| `WAITING_FOR_ACCEPTANCE` | `REWORK` | `READY_FOR_EXECUTION`| Cán bộ nghiệm thu đánh giá không đạt, yêu cầu làm lại kèm lý do. | `api_core/workflow/service.py` |
| `WAITING_FOR_ACCEPTANCE` | `ACCEPT` | `COMPLETED` | Cán bộ nghiệm thu độc lập (khác Executor) ký nhận bàn giao đạt chuẩn. | `api_core/workflow/service.py` |
