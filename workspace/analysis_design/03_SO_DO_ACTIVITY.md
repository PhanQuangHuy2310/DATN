# HỒ SƠ THIẾT KẾ TOÀN DIỆN CÁC SƠ ĐỒ HOẠT ĐỘNG (ACTIVITY DIAGRAMS)
## DỰ ÁN: HỆ THỐNG TỰ ĐỘNG HÓA QUY TRÌNH XỬ LÝ YÊU CẦU NỘI BỘ ĐA CẤP (EAS)
### HỘI ĐỒNG THẨM ĐỊNH IT 15 NĂM KINH NGHIỆM: BA, PM, DEV, UI/UX, AI, QA, PO

---

## 1. NGUYÊN TẮC THIẾT KẾ QUY TRÌNH HOẠT ĐỘNG (BPMN / ACTIVITY)

Theo chuẩn hóa quy trình doanh nghiệp (BPMN 2.0 / UML 2.5 Activity Diagrams) và phản ánh trung thực mã nguồn động cơ luồng nghiệp vụ trong `api_core/workflow/service.py`, `api_core/workflow/ai_learning.py` và `api_core/worker.py`, các sơ đồ hoạt động tuân thủ các nguyên tắc cốt lõi:
1. **Phân rã làn trách nhiệm (Swimlanes):** Tách biệt rõ ràng ranh giới hành vi giữa Người dùng (Client), Cổng API Gateway, Dịch vụ lõi (Core Engine), Hệ thống AI, Cơ sở dữ liệu và Tác vụ nền (Worker).
2. **Xử lý rẽ nhánh điều kiện nghiêm ngặt (Decision Nodes):** Mọi nhánh rẽ đều có điều kiện bảo vệ (Guards) rõ ràng, không bao giờ có ngõ cụt (Dead-end) hoặc luồng lửng lơ.
3. **Đảm bảo tính trọn vẹn của giao dịch (ACID Transactions):** Các bước cập nhật trạng thái, ghi sổ cái kiểm toán và phát sinh sự kiện Outbox luôn được đóng gói trong một Database Transaction duy nhất.
4. **Phân biệt rành mạch 3 mẫu vòng đời (Lifecycle A/B/C):**
   - **Template A (Chỉ phê duyệt):** Phê duyệt xong -> Chuyển ngay `COMPLETED`.
   - **Template B (Phê duyệt & Thực hiện):** Phê duyệt xong -> Chờ thi công (`READY_FOR_EXECUTION`) -> Thực hiện xong -> `COMPLETED`.
   - **Template C (Phê duyệt, Thực hiện & Nghiệm thu):** Phê duyệt -> Thi công -> Chờ nghiệm thu (`WAITING_FOR_ACCEPTANCE`) -> Nghiệm thu đạt chuẩn -> `COMPLETED`.

---

## 2. DANH MỤC TẤT CẢ 10 SƠ ĐỒ HOẠT ĐỘNG TRONG HỆ THỐNG EAS

Toàn bộ 10 sơ đồ (4 sơ đồ trong Chương 2 và 6 sơ đồ trong Phụ lục B) được mô hình hóa chi tiết bằng mã nguồn Mermaid chuẩn:

---

### SƠ ĐỒ 1: HÌNH 2.5 - SƠ ĐỒ HOẠT ĐỘNG QUY TRÌNH TỔNG THỂ VÒNG ĐỜI YÊU CẦU (AD-01)
*Toàn cảnh hành trình của một hồ sơ từ khi khởi tạo, qua thẩm định AI, phê duyệt đa cấp, thi công chuyên môn, đến nghiệm thu độc lập và đóng hồ sơ.*

```mermaid
flowchart TD
    START((Bắt đầu)) --> REQ_DRAFT["1. Requester soạn đơn & đính kèm chứng từ (DRAFT)"]
    REQ_DRAFT --> REQ_SUBMIT["2. Requester gửi đơn (SUBMIT)"]
    
    REQ_SUBMIT --> AI_ASSESS{"3. Phân hệ AI thẩm định rủi ro ban đầu"}
    
    AI_ASSESS -- "Đạt chuẩn Auto-Approve\n(Template A, Risk <= 2, Đủ số dư)" --> AI_AUTO_APPROVE["4a. AI Tự động Phê duyệt (0 cấp duyệt)"]
    AI_AUTO_APPROVE --> CHECK_LC_AUTO{"Mẫu vòng đời"}
    CHECK_LC_AUTO -- Template A --> REQ_COMPLETE_AUTO["Hồ sơ hoàn tất (COMPLETED)"]
    
    AI_ASSESS -- "Cần con người thẩm định\n(Risk > 2 hoặc Template B, C)" --> APP_STAGE["4b. Chuyển vào Luồng Phê duyệt Đa cấp (IN_REVIEW)"]
    
    APP_STAGE --> APP_DECISION{"5. Quản lý ra quyết định"}
    
    APP_DECISION -- "TỪ CHỐI (Reject)" --> REQ_REJECT["Hồ sơ bị bác bỏ (REJECTED)"]
    REQ_REJECT --> END_FAIL((Kết thúc - Bị từ chối))

    APP_DECISION -- "YÊU CẦU BỔ SUNG (Needs Info)" --> REQ_NEEDS_INFO["Yêu cầu bổ sung chứng từ (NEEDS_INFO)"]
    REQ_NEEDS_INFO --> REQ_UPDATE["Requester cập nhật hồ sơ & nộp lại (Resubmit)"]
    REQ_UPDATE --> APP_STAGE

    APP_DECISION -- "CHẤP THUẬN (Approve)" --> CHECK_FINAL_STEP{"Là cấp duyệt cuối cùng?"}
    CHECK_FINAL_STEP -- "Chưa hết cấp" --> APP_NEXT_STEP["Chuyển cấp quản lý tiếp theo"]
    APP_NEXT_STEP --> APP_STAGE

    CHECK_FINAL_STEP -- "Đã duyệt đủ cấp" --> CHECK_LC_TYPE{"Kiểm tra mẫu vòng đời"}

    CHECK_LC_TYPE -- "Template A (Chỉ phê duyệt)" --> REQ_COMPLETE["Hồ sơ hoàn tất (COMPLETED)"]
    
    CHECK_LC_TYPE -- "Template B hoặc C (Cần thực hiện)" --> EXE_STAGE["6. Chuyển Bộ phận Chuyên trách Thi công (READY_FOR_EXECUTION)"]
    
    EXE_STAGE --> EXE_CLAIM["Executor nhận việc (Claim Lease)"]
    EXE_CLAIM --> EXE_DO["Executor tiến hành mua sắm / cấp phát / giải ngân"]
    
    EXE_DO --> EXE_ISSUE{"Có phát sinh vướng mắc?"}
    EXE_ISSUE -- Có sự cố --> EXE_BLOCKED["Báo vướng mắc (BLOCKED) - Ops Admin can thiệp"]
    EXE_BLOCKED --> EXE_DO
    
    EXE_ISSUE -- Xong việc --> EXE_SUBMIT["Executor nộp biên bản hoàn tất"]

    EXE_SUBMIT --> CHECK_ACCEPT_NEED{"Yêu cầu nghiệm thu độc lập?"}
    
    CHECK_ACCEPT_NEED -- "Template B: Không cần nghiệm thu" --> REQ_COMPLETE_B["Hồ sơ hoàn tất (COMPLETED)"]
    
    CHECK_ACCEPT_NEED -- "Template C: Bắt buộc nghiệm thu" --> ACC_STAGE["7. Chuyển Người nghiệm thu độc lập (WAITING_FOR_ACCEPTANCE)"]
    
    ACC_STAGE --> ACC_DECISION{"Acceptor thẩm định kết quả"}
    
    ACC_DECISION -- "KHÔNG ĐẠT (Rework)" --> ACC_REWORK["Yêu cầu thi công lại (READY_FOR_EXECUTION)"]
    ACC_REWORK --> EXE_CLAIM

    ACC_DECISION -- "ĐẠT CHUẨN (Accept)" --> REQ_COMPLETE_C["Hồ sơ hoàn tất viên mãn (COMPLETED)"]

    REQ_COMPLETE_AUTO --> END_SUCCESS((Kết thúc - Thành công))
    REQ_COMPLETE --> END_SUCCESS
    REQ_COMPLETE_B --> END_SUCCESS
    REQ_COMPLETE_C --> END_SUCCESS
```

---

### SƠ ĐỒ 2: HÌNH 2.6 - SƠ ĐỒ HOẠT ĐỘNG QUY TRÌNH SOẠN THẢO VÀ GỬI YÊU CẦU (AD-02)
*Quy trình kiểm soát dữ liệu đầu vào, quét mã độc stream và đảm bảo tính nguyên tử chống nộp lặp.*

```mermaid
flowchart TD
    START((Bắt đầu)) --> CHOOSE_TYPE["Người dùng mở giao diện, chọn loại đơn trong Catalog"]
    CHOOSE_TYPE --> FETCH_RELEASE["Hệ thống tải Active Config Release & Form Schema tương ứng"]
    
    FETCH_RELEASE --> RENDER_FORM["Render form nhập liệu động và các trường ràng buộc"]
    RENDER_FORM --> USER_INPUT["Người dùng điền các thông tin và đính kèm tệp chứng từ"]

    USER_INPUT --> CLIENT_VAL{"Kiểm tra hợp lệ Client\n(Form Validation)"}
    CLIENT_VAL -- Thiếu trường bắt buộc --> SHOW_INLINE_ERR["Hiển thị cảnh báo đỏ tại trường bị thiếu"]
    SHOW_INLINE_ERR --> USER_INPUT

    CLIENT_VAL -- Hợp lệ --> CHECK_ATTACHMENT{"Có tệp đính kèm?"}
    
    CHECK_ATTACHMENT -- Có --> STREAM_UPLOAD["Tải tệp lên bộ đệm an toàn server"]
    STREAM_UPLOAD --> MAGIC_BYTES{"Kiểm tra Magic Bytes\n(Đúng định dạng PDF/JPG/PNG?)"}
    MAGIC_BYTES -- Giả mạo phần mở rộng --> REJECT_FILE["Từ chối tệp tin giả mạo"]
    REJECT_FILE --> USER_INPUT

    MAGIC_BYTES -- Hợp lệ --> CLAMAV_SCAN{"Quét mã độc Antivirus\n(ClamAV Stream Scan)"}
    CLAMAV_SCAN -- Phát hiện virus/malware --> ISOLATE_FILE["Cách ly tệp, ghi cảnh báo an ninh và từ chối"]
    ISOLATE_FILE --> USER_INPUT

    CLAMAV_SCAN -- Tệp sạch --> STORE_ENCRYPT["Lưu trữ mã hóa tệp và trả về UUID attachment"]
    STORE_ENCRYPT --> DRAFT_SAVED["Lưu bản ghi DRAFT nguyên tử"]
    CHECK_ATTACHMENT -- Không có --> DRAFT_SAVED

    DRAFT_SAVED --> SUBMIT_TRIGGER{"Người dùng bấm:\nNỘP ĐƠN (Submit)"}
    SUBMIT_TRIGGER -- Chỉ lưu nháp --> SAVE_EXIT((Đã lưu nháp an toàn))

    SUBMIT_TRIGGER -- Gửi đơn --> IDEMPOTENCY_FILTER{"Kiểm tra Idempotency-Key\ntrong Header"}
    IDEMPOTENCY_FILTER -- Trùng khóa đang xử lý --> WAIT_REPLAY["Trả về kết quả giao dịch trước, chống nộp đúp"]

    IDEMPOTENCY_FILTER -- Khóa mới hợp lệ --> START_TX["Bắt đầu DB Transaction (ACID)"]
    
    START_TX --> LOCK_COUNTER["Khóa hàng `eas.request_counter` FOR UPDATE để sinh mã đơn tuần tự"]
    LOCK_COUNTER --> SNAPSHOT_RELEASE["Snapshot toàn bộ Config Release Version và Rules tại thời điểm nộp"]
    SNAPSHOT_RELEASE --> CALL_AI_SCORER["Gọi AI Engine: Phân loại văn bản và tính điểm rủi ro"]
    CALL_AI_SCORER --> BUILD_ROUTE["Phân giải các cấp duyệt theo Ma trận thẩm quyền và Phòng ban"]
    BUILD_ROUTE --> RECORD_AUDIT["Ghi bản ghi Audit Log băm chuỗi SHA-256"]
    RECORD_AUDIT --> INSERT_OUTBOX["Thêm sự kiện phát tán thông báo vào Outbox"]
    
    INSERT_OUTBOX --> COMMIT_ALL{"Commit Transaction thành công?"}
    COMMIT_ALL -- Lỗi cơ sở dữ liệu --> ROLLBACK_ALL["Rollback toàn bộ, báo lỗi cho người dùng"]
    ROLLBACK_ALL --> USER_INPUT

    COMMIT_ALL -- Thành công --> EMIT_EVENT["Đơn chuyển SUBMITTED, phát tín hiệu cho Worker"]
    EMIT_EVENT --> END_SUCCESS((Nộp đơn thành công))
```

---

### SƠ ĐỒ 3: HÌNH 2.7 - SƠ ĐỒ HOẠT ĐỘNG QUY TRÌNH CẤP TRÊN XỬ LÝ PHÊ DUYỆT ĐA CẤP (AD-03)
*Quy trình tiếp nhận, tra cứu rủi ro AI, giải quyết xung đột đồng thời và ra phán quyết.*

```mermaid
flowchart TD
    START((Bắt đầu)) --> NOTIF_RECEIVED["Quản lý nhận thông báo: Có đơn chờ duyệt"]
    NOTIF_RECEIVED --> OPEN_DETAIL["Mở trang chi tiết hồ sơ yêu cầu (:8080/requests/...)"]
    
    OPEN_DETAIL --> AUTH_CHECK{"Kiểm tra quyền duyệt:\nActor có thuộc Step ACTIVE?"}
    AUTH_CHECK -- Không có quyền --> SHOW_403["Báo lỗi 403 Forbidden: Không có quyền duyệt đơn này"]
    SHOW_403 --> END_DENIED((Dừng lại))

    AUTH_CHECK -- Đúng quyền --> SOD_CHECK{"Kiểm tra Phân tách nhiệm vụ:\nActor có phải Requester?"}
    SOD_CHECK -- Vi phạm SoD (Tự duyệt) --> SHOW_SOD_ERR["Báo lỗi nghiêm trọng: Không được tự duyệt đơn của chính mình!"]
    SHOW_SOD_ERR --> END_DENIED

    SOD_CHECK -- Hợp lệ --> LOAD_AI_BADGE["Hiển thị hồ sơ, kèm Badge rủi ro AI và bản tóm tắt Gemini"]
    LOAD_AI_BADGE --> MANAGER_REVIEW["Quản lý thẩm định chứng từ, tính hợp lý và ngân sách"]

    MANAGER_REVIEW --> DECIDE_ACTION{"Quản lý lựa chọn hành động"}

    DECIDE_ACTION -- YÊU CẦU BỔ SUNG --> INPUT_NEEDS_INFO["Nhập yêu cầu làm rõ cụ thể (Ghi chú bắt buộc)"]
    INPUT_NEEDS_INFO --> TX_NEEDS_INFO["Thực thi DB Transaction:\n- Chuyển đơn sang NEEDS_INFO\n- Tạm dừng đồng hồ SLA\n- Đẩy thông báo yêu cầu bổ sung vào Outbox\n- Ghi sổ cái kiểm toán"]
    TX_NEEDS_INFO --> END_DONE((Hoàn tất xử lý))

    DECIDE_ACTION -- TỪ CHỐI (REJECT) --> INPUT_REASON["Nhập lý do từ chối (Bắt buộc)"]
    INPUT_REASON --> TX_REJECT["Thực thi DB Transaction:\n- Chuyển đơn sang REJECTED\n- Đóng toàn bộ các bước duyệt còn lại\n- Đẩy thông báo bác bỏ vào Outbox\n- Ghi sổ cái kiểm toán"]
    TX_REJECT --> END_DONE

    DECIDE_ACTION -- PHÊ DUYỆT (APPROVE) --> OPTIONAL_NOTE["Nhập ý kiến phê duyệt (Không bắt buộc)"]
    OPTIONAL_NOTE --> TX_APPROVE["Thực thi DB Transaction:\n- Khóa hàng bước duyệt `FOR UPDATE`\n- Cập nhật Step hiện tại thành APPROVED\n- Ghi sổ cái kiểm toán"]

    TX_APPROVE --> EVAL_NEXT_STEP{"Kiểm tra cấu hình Route:\nCòn cấp duyệt tiếp theo?"}
    
    EVAL_NEXT_STEP -- Còn cấp duyệt --> SPAWN_NEXT_STEP["Kích hoạt bước duyệt tiếp theo (ACTIVE)\n& Đẩy thông báo cho cấp quản lý cao hơn"]
    SPAWN_NEXT_STEP --> END_DONE

    EVAL_NEXT_STEP -- Hết cấp duyệt --> EVAL_LIFECYCLE{"Kiểm tra Mẫu vòng đời"}
    
    EVAL_LIFECYCLE -- Template A (Chỉ phê duyệt) --> CLOSE_COMPLETED["Đơn chính thức chuyển COMPLETED\n& Thông báo hoàn tất cho Requester"]
    
    EVAL_LIFECYCLE -- Template B hoặc C --> ROUTE_EXECUTION["Chuyển đơn sang READY_FOR_EXECUTION\n& Đẩy thông báo cho Bộ phận chuyên trách"]
    
    CLOSE_COMPLETED --> END_DONE
    ROUTE_EXECUTION --> END_DONE
```

---

### SƠ ĐỒ 4: HÌNH 2.8 - SƠ ĐỒ HOẠT ĐỘNG QUY TRÌNH THỰC HIỆN VÀ NGHIỆM THU BÀN GIAO (AD-04)
*Quy trình bàn giao kỹ thuật, tiếp nhận việc độc quyền và nghiệm thu kết quả hai phía.*

```mermaid
flowchart TD
    START((Bắt đầu)) --> POOL_AVAILABLE["Đơn ở trạng thái READY_FOR_EXECUTION xuất hiện trong Pool"]
    POOL_AVAILABLE --> EXE_VIEW["Chuyên viên kỹ thuật/mua sắm xem danh sách chờ xử lý"]
    
    EXE_VIEW --> EXE_CLICK_CLAIM["Chuyên viên bấm nút: TIẾP NHẬN (Claim)"]
    
    EXE_CLICK_CLAIM --> ATOMIC_CLAIM{"Hệ thống khóa hàng FOR UPDATE:\nĐã có ai nhận chưa?"}
    ATOMIC_CLAIM -- Đã bị nhận trước --> SHOW_CLAIMED_ERR["Thông báo: Đơn đã được chuyên viên khác tiếp nhận"]
    SHOW_CLAIMED_ERR --> POOL_AVAILABLE

    ATOMIC_CLAIM -- Nhận thành công --> SET_ATTEMPT_RUNNING["Tạo bản ghi `eas.execution_attempt`: RUNNING\n- Gán `executor_id = actor.id`\n- Đơn chuyển trạng thái IN_PROGRESS\n- Thiết lập Lease thời hạn thi công"]

    SET_ATTEMPT_RUNNING --> PROCESS_WORK["Chuyên viên thực hiện công việc thực tế\n(Mua hàng, cài đặt máy tính, tạo tài khoản)"]

    PROCESS_WORK --> CHECK_OBSTACLE{"Có sự cố vướng mắc?"}
    
    CHECK_OBSTACLE -- Bị nghẽn/Sự cố --> REPORT_OBSTACLE["Mở bản ghi `eas.execution_issue`:\n- Nhập loại sự cố (Hết hàng, Sai cấu hình)\n- Đơn chuyển sang trạng thái BLOCKED\n- Gửi cảnh báo khẩn cấp cho Quản trị viên"]
    REPORT_OBSTACLE --> ADMIN_RESOLVE{"Quản trị viên giải quyết vướng mắc"}
    ADMIN_RESOLVE -- Điều chuyển người khác --> REASSIGN_EXE["Gán lại chuyên viên mới"]
    REASSIGN_EXE --> SET_ATTEMPT_RUNNING
    ADMIN_RESOLVE -- Hủy vướng mắc --> PROCESS_WORK

    CHECK_OBSTACLE -- Thuận lợi hoàn tất --> SUBMIT_RESULT["Chuyên viên bấm: BÁO CÁO KẾT QUẢ\n- Tải lên biên bản bàn giao, hóa đơn, link cấu hình\n- Nhập ghi chú nghiệm thu"]

    SUBMIT_RESULT --> CHECK_LC_CATEGORY{"Kiểm tra mẫu vòng đời đơn"}
    
    CHECK_LC_CATEGORY -- Lifecycle B (Không nghiệm thu độc lập) --> B_COMPLETE["Đơn chính thức hoàn thành viên mãn (COMPLETED)\n- Đóng hồ sơ, thông báo cho Requester"]
    B_COMPLETE --> END_SUCCESS((Hoàn thành))

    CHECK_LC_CATEGORY -- Lifecycle C (Bắt buộc nghiệm thu) --> C_WAIT_ACCEPT["Đơn chuyển sang WAITING_FOR_ACCEPTANCE\n- Khóa hồ sơ, chuyên viên không được sửa\n- Gửi thông báo mời nghiệm thu cho Acceptor"]

    C_WAIT_ACCEPT --> ACC_INSPECT["Cán bộ nghiệm thu kiểm tra sản phẩm thực tế bàn giao"]
    ACC_INSPECT --> ACC_VERDICT{"Đánh giá chất lượng bàn giao"}

    ACC_VERDICT -- KHÔNG ĐẠT (Reject bàn giao) --> ACC_REWORK_REASON["Nhập biên bản không đạt & Lý do bắt làm lại"]
    ACC_REWORK_REASON --> TX_REWORK["Thực thi giao dịch:\n- Đóng lượt thi công cũ thất bại\n- Đơn quay về READY_FOR_EXECUTION\n- Tăng số lần thử nghiệm thu (`attempt_seq + 1`)"]
    TX_REWORK --> POOL_AVAILABLE

    ACC_VERDICT -- ĐẠT CHUẨN (Chấp thuận) --> ACC_SIGN_ACCEPT["Ký nhận biên bản bàn giao điện tử"]
    ACC_SIGN_ACCEPT --> TX_ACCEPT_SUCCESS["Thực thi giao dịch nguyên tử:\n- Tạo bản ghi `eas.acceptance_record`\n- Đơn chính thức chuyển sang COMPLETED\n- Ghi sổ cái kiểm toán đóng toàn bộ vòng đời"]
    TX_ACCEPT_SUCCESS --> END_SUCCESS
```

---

### SƠ ĐỒ 5: HÌNH PL-08 - QUY TRÌNH BAN HÀNH VÀ CẬP NHẬT QUY CHẾ MẪU ĐƠN ĐỘNG (AD-07)
*Cơ chế phát hành cấu hình động bất biến (Immutable Releases), chống xung đột dữ liệu.*

```mermaid
flowchart TD
    START((Bắt đầu)) --> ADMIN_ENTER["Policy Admin đăng nhập Cổng Quản trị (:8081)"]
    ADMIN_ENTER --> OPEN_RELEASE_WS["Truy cập Không gian Cấu hình Quy chế (:8081/workflows)"]
    
    OPEN_RELEASE_WS --> CLONE_RELEASE["1. Clone bản phát hành đang chạy (Active Release)\nđể tạo Bản nháp mới (DRAFT Release)"]
    
    CLONE_RELEASE --> EDIT_CONFIG["2. Chỉnh sửa cấu hình:\n- Biểu mẫu Form JSON Schema\n- Phân loại vòng đời A, B, C\n- Trọng số tự động hóa (Automation Weight)\n- Ma trận phê duyệt đa cấp và hạn mức tiền\n- Cam kết thời gian SLA từng chặng"]

    EDIT_CONFIG --> VALIDATE_SCHEMA{"3. Hệ thống kiểm tra hợp lệ cấu hình:\n- Schema JSON hợp chuẩn?\n- Các vai trò duyệt có tồn tại trong hệ thống?\n- Không có vòng lặp vô tận (Circular loop)?"}
    
    VALIDATE_SCHEMA -- Phát hiện lỗi logic --> HIGHLIGHT_ERR["Hiển thị lỗi cấu hình cần sửa"]
    HIGHLIGHT_ERR --> EDIT_CONFIG

    VALIDATE_SCHEMA -- Đạt chuẩn --> DRY_RUN_RESOLVE{"4. Chạy thử nghiệm phân giải luồng (Dry-run):\nKiểm tra trên 100% phòng ban hiện có"}
    
    DRY_RUN_RESOLVE -- Có phòng ban bị kẹt không tìm được người duyệt --> WARN_ORPHAN["Cảnh báo: Phòng ban X thiếu Trưởng phòng duyệt!"]
    WARN_ORPHAN --> EDIT_CONFIG

    DRY_RUN_RESOLVE -- Mọi phòng ban đều thông suốt --> READY_PUBLISH["Bản nháp chuyển sang trạng thái VALIDATED"]
    
    READY_PUBLISH --> CLICK_PUBLISH["5. Policy Admin bấm nút: BAN HÀNH (Publish)"]
    
    CLICK_PUBLISH --> ATOMIC_PUBLISH_TX["6. Thực thi Giao dịch Ban hành Nguyên tử:\n- Cập nhật Release cũ sang SUPERSEDED\n- Cập nhật Release mới sang PUBLISHED & ACTIVE\n- Ghi nhận lịch sử kiểm toán `admin_event`\n- Xóa Cache bộ đệm cấu hình trên Redis\n- Gửi thông báo cập nhật hệ thống cho người dùng"]

    ATOMIC_PUBLISH_TX --> PUBLISH_DONE((Ban hành thành công))
```

---

### SƠ ĐỒ 6: HÌNH PL-09 - QUY TRÌNH TIẾP NHẬN VÀ PHÂN PHỐI CÔNG VIỆC THỰC THI NỘI BỘ (AD-08)
*Cơ chế quản lý hàng đợi công việc, điều phối tải chuyên viên và thu hồi khi quá hạn.*

```mermaid
flowchart TD
    START((Bắt đầu)) --> REQ_APPROVED["Hồ sơ Lifecycle B/C hoàn tất duyệt"]
    REQ_APPROVED --> CATEGORIZE_SKILL["Phân loại chuyên môn yêu cầu:\n(IT Helpdesk, Mua sắm vật tư, Kế toán thanh toán)"]
    
    CATEGORIZE_SKILL --> ENQUEUE_DEPT_POOL["Đẩy hồ sơ vào Hàng đợi công việc của Phòng ban chuyên trách"]
    
    ENQUEUE_DEPT_POOL --> WORKER_HEARTBEAT["Chuyên viên trong bộ phận theo dõi bảng phân phối công việc"]
    
    WORKER_HEARTBEAT --> CLAIM_INTENT{"Chuyên viên thực hiện thao tác nhận việc"}
    
    CLAIM_INTENT --> DISTRIBUTED_LOCK{"Kiểm tra Redis Distributed Lock"}
    CLAIM_INTENT -- Tranh chấp cùng mili-giây --> LOCK_FAIL["Báo lỗi: Đã có chuyên viên khác nhận trước"]
    
    DISTRIBUTED_LOCK -- Lấy khóa thành công --> ASSIGN_LEASE["Gán quyền thực thi cho Chuyên viên (Lease có thời hạn)"]
    
    ASSIGN_LEASE --> START_EXECUTION["Bắt đầu tiến trình thi công công việc"]
    
    START_EXECUTION --> MONITOR_TIMER["Tiến trình nền System Worker giám sát thời hạn thi công"]
    
    MONITOR_TIMER --> LEASE_EXPIRED{"Chuyên viên có bỏ quên việc\n(Hết hạn Lease mà không cập nhật tiến độ)?"}
    
    LEASE_EXPIRED -- Hết hạn Lease không lý do --> REVOKE_CLAIM["Hệ thống tự động thu hồi lượt nhận việc (Auto-Reclaim)\n- Đưa hồ sơ trở lại Hàng đợi dùng chung\n- Ghi log cảnh báo trễ hạn của chuyên viên"]
    REVOKE_CLAIM --> ENQUEUE_DEPT_POOL

    LEASE_EXPIRED -- Tiến hành bình thường --> FINISH_EXECUTION["Chuyên viên hoàn tất công việc và nộp biên bản nghiệm thu"]
    FINISH_EXECUTION --> END_SUCCESS((Hoàn thành tiếp nhận))
```

---

### SƠ ĐỒ 7: HÌNH PL-10 - QUY TRÌNH KIỂM TOÁN ĐỊNH KỲ VÀ XÁC MINH CHUỖI HASH-CHAIN (AD-09)
*Quy trình đối soát tự động tính toàn vẹn của sổ cái mật mã học và chốt trạm Checkpoint.*

```mermaid
flowchart TD
    START((Khởi động chu kỳ kiểm toán)) --> CRON_AUDIT["Celery Beat kích hoạt định kỳ (Hàng ngày lúc 00:00)"]
    CRON_AUDIT --> LOCK_AUDIT_LEDGER["Khóa trạm kiểm soát, đọc bản ghi `eas.audit_head`"]
    
    LOCK_AUDIT_LEDGER --> LOAD_EVENTS["Đọc danh sách sự kiện mới phát sinh từ Checkpoint gần nhất"]
    
    LOAD_EVENTS --> INIT_CHAIN["Khởi tạo: Hash_Con_Lai = Last_Checkpoint_Hash"]
    
    INIT_CHAIN --> FOREACH_EVENT["Lặp qua từng sự kiện theo thứ tự `event_seq` tăng dần"]
    
    FOREACH_EVENT --> EXTRACT_CANONICAL["Chuẩn hóa Canonical JSON payload của sự kiện"]
    EXTRACT_CANONICAL --> CALC_SHA256["Tính toán: Expected_Hash = SHA256(Hash_Con_Lai + Payload + Timestamp)"]
    
    CALC_SHA256 --> VERIFY_MATCH{"Expected_Hash == Stored_Event_Hash?"}
    
    VERIFY_MATCH -- KHÔNG KHỚP (Phát hiện giả mạo) --> TAMPER_ALERT["BÁO ĐỘNG AN NINH ĐỎ!\n- Chuỗi kiểm toán đã bị can thiệp trái phép\n- Ghi nhận vị trí `event_seq` bị sửa lén\n- Khóa tài khoản nghi vấn và gửi SMS cho CISO/Auditor"]
    TAMPER_ALERT --> END_FAIL((Dừng khẩn cấp))

    VERIFY_MATCH -- TRÙNG KHỚP HOÀN TOÀN --> ADVANCE_HASH["Gán: Hash_Con_Lai = Expected_Hash"]
    ADVANCE_HASH --> CHECK_MORE{"Còn sự kiện tiếp theo?"}
    CHECK_MORE -- Còn sự kiện --> FOREACH_EVENT

    CHECK_MORE -- Đã duyệt hết sự kiện mới --> CREATE_CHECKPOINT["Tạo trạm kiểm soát mới (New Hash Checkpoint):\n- Ghi giá trị chốt cuối vào `eas.audit_head`\n- Ký số trạm kiểm soát bằng khóa bảo mật\n- Lưu bản sao Checkpoint ra vùng lưu trữ riêng biệt WORM"]

    CREATE_CHECKPOINT --> AUDIT_REPORT["Xuất báo cáo xác thực chuỗi băm hàng ngày: 100% VALID"]
    AUDIT_REPORT --> END_SUCCESS((Kết thúc phiên kiểm toán))
```

---

### SƠ ĐỒ 8: HÌNH PL-11 - QUY TRÌNH KIỂM TRA NGHIỆM THU VÀ ĐƯA PHẦN MỀM VÀO SỬ DỤNG (AD-10)
*Quy chuẩn nghiệm thu kỹ thuật (Definition of Done) trước khi bàn giao hệ thống vào vận hành chính thức.*

```mermaid
flowchart TD
    START((Bắt đầu quy trình nghiệm thu)) --> GATE_SECRET["1. Kiểm tra An toàn Khóa & Bí mật:\nChạy `python scripts/check_repository_secrets.py`"]
    GATE_SECRET --> SECRET_PASS{"SECRET_GATE == PASS?"}
    SECRET_PASS -- Thất bại --> REJECT_DEPLOY["Bác bỏ: Phát hiện API Key / Token lộ trong code"]

    SECRET_PASS -- Vượt qua --> GATE_CODE_QUALITY["2. Kiểm tra Chất lượng Mã nguồn & Format:\nChạy `ruff check` và `ruff format --check`"]
    GATE_CODE_QUALITY --> LINT_PASS{"Backend & Scripts sạch 100%?"}
    LINT_PASS -- Thất bại --> REJECT_DEPLOY

    LINT_PASS -- Vượt qua --> GATE_UNIT_TEST["3. Chạy Toàn bộ Bộ Kiểm thử Unit & Integration:\n- 448 Django tests\n- 153 System tests (`tests/run_tests.py`)\n- 64 Frontend tests (`web_client` npm test)"]
    GATE_UNIT_TEST --> UNIT_PASS{"100% Tests PASSED?"}
    UNIT_PASS -- Có bài test trượt --> REJECT_DEPLOY

    UNIT_PASS -- Vượt qua --> GATE_BUNDLE["4. Kiểm tra Phân lập Gói nguồn Client:\nChạy `python scripts/check_client_bundle.py`"]
    GATE_BUNDLE --> BUNDLE_PASS{"Gói Client không chứa mã nguồn Admin?"}
    BUNDLE_PASS -- Thất bại --> REJECT_DEPLOY

    BUNDLE_PASS -- Vượt qua --> GATE_BUILD["5. Kiểm tra Build Production độc lập:\n- `npm run build` trong `web_client`\n- `npm run build` trong `web_admin`"]
    GATE_BUILD --> BUILD_PASS{"Build thành công không lỗi (<400ms)?"}
    BUILD_PASS -- Thất bại --> REJECT_DEPLOY

    BUILD_PASS -- Vượt qua --> GATE_E2E_PLAYWRIGHT["6. Chạy Kiểm thử Trình duyệt Thật E2E (Playwright):\n- Đăng nhập 2 cổng độc lập (Client 8080 vs Admin 8081)\n- Thử nghiệm Circuit Breaker khóa tự động biểu mẫu\n- Thử nghiệm Semantic Versioning và AI Retrain"]
    GATE_E2E_PLAYWRIGHT --> E2E_PASS{"100% Kịch bản E2E PASSED?"}
    E2E_PASS -- Thất bại --> REJECT_DEPLOY

    E2E_PASS -- Vượt qua --> SIGN_OFF["7. HỘI ĐỒNG IT KÝ BIÊN BẢN NGHIỆM THU (QA SIGN-OFF):\n- Xác nhận hệ thống đạt chuẩn Production Ready\n- Bàn giao mã nguồn sạch và tài liệu phân tích thiết kế"]
    SIGN_OFF --> END_SUCCESS((Đưa vào vận hành chính thức))
    REJECT_DEPLOY --> END_FAIL((Yêu cầu sửa lỗi lại))
```

---

### SƠ ĐỒ 9: HÌNH PL-12 - QUY TRÌNH XỬ LÝ YÊU CẦU QUYỀN RIÊNG TƯ VÀ ẨN DANH HÓA DỮ LIỆU (AD-11)
*Quy chuẩn tuân thủ bảo vệ dữ liệu cá nhân theo GDPR và Nghị định 13/2023/NĐ-CP.*

```mermaid
flowchart TD
    START((Bắt đầu)) --> PRIVACY_REQ["Nhân viên gửi yêu cầu quyền riêng tư:\n(Yêu cầu xuất dữ liệu hoặc Yêu cầu xóa/ẩn danh dữ liệu cá nhân)"]
    
    PRIVACY_REQ --> VERIFY_IDENTITY["1. Xác thực danh tính sinh trắc học / OTP chính chủ"]
    VERIFY_IDENTITY --> CHECK_LEGAL_HOLD{"2. Kiểm tra Ràng buộc Pháp lý & Kế toán:\nHồ sơ có đang trong diện Thanh tra hoặc Kỳ lưu trữ Thuế bắt buộc?"}
    
    CHECK_LEGAL_HOLD -- Đang thuộc diện bắt buộc lưu trữ --> REJECT_ERASURE["Từ chối xóa dữ liệu gốc theo quy định pháp luật hiện hành;\nChỉ cho phép xuất dữ liệu để người dùng kiểm tra"]
    REJECT_ERASURE --> EXPORT_FLOW["Tiến hành Xuất gói Dữ liệu Cá nhân"]

    CHECK_LEGAL_HOLD -- Đủ điều kiện xóa/ẩn danh --> CHOOSE_ACTION{"Lựa chọn loại thao tác"}

    CHOOSE_ACTION -- XUẤT DỮ LIỆU (Data Portability) --> EXPORT_FLOW
    EXPORT_FLOW --> COMPILE_PII["Thu thập toàn bộ dữ liệu thuộc về `actor_id`:\n(Thông tin tài khoản, danh sách đơn đã tạo, ý kiến duyệt)"]
    COMPILE_PII --> ENCRYPT_PACKAGE["Đóng gói file ZIP mã hóa AES-256 bằng mật khẩu riêng"]
    ENCRYPT_PACKAGE --> SEND_DOWNLOAD_LINK["Gửi đường link tải an toàn (Hết hạn sau 24h)"]
    SEND_DOWNLOAD_LINK --> END_SUCCESS((Hoàn tất xuất dữ liệu))

    CHOOSE_ACTION -- ẨN DANH HÓA (Right to be Forgotten) --> ANONYMIZATION_TX["Bắt đầu Giao dịch Ẩn danh hóa Dữ liệu:"]
    
    ANONYMIZATION_TX --> MASK_USER_TABLE["Ghi đè thông tin nhạy cảm trong `eas.app_user`:\n- Tên -> 'Ẩn danh'\n- Email -> 'anonymized_[hash]@eas.local'\n- Số điện thoại / CCCD -> Null\n- Xóa ảnh đại diện Avatar"]
    
    MASK_USER_TABLE --> PSEUDONYMIZE_LOGS["Bảo toàn Tính toàn vẹn Sổ cái Kiểm toán:\n- KHÔNG XÓA các dòng `eas.audit_log` (để tránh đứt gãy chuỗi băm Hash-chain)\n- Chỉ ẩn danh hóa trường định danh trong Payload hiển thị"]
    
    PSEUDONYMIZE_LOGS --> RECORD_PRIVACY_LOG["Ghi nhận sự kiện ẩn danh hóa vào `eas.privacy_compliance_log`"]
    
    RECORD_PRIVACY_LOG --> COMMIT_PRIVACY["Commit giao dịch an toàn"]
    COMMIT_PRIVACY --> END_SUCCESS
```

---

### SƠ ĐỒ 10: HÌNH PL-13 - QUY TRÌNH TỰ ĐỘNG HUẤN LUYỆN LẠI VÀ KIỂM CHỨNG MÔ HÌNH AI (AD-12)
*Tiến trình vòng lặp học máy (Active Learning Loop) với khóa bảo trì tự động và xác minh mô hình.*

```mermaid
flowchart TD
    START((Khởi động chu kỳ học máy)) --> TRIGGER_EVENT{"Sự kiện kích hoạt Huấn luyện AI"}
    
    TRIGGER_EVENT -- Quản trị viên cập nhật Quy chế mới --> EVENT_POLICY["Admin sửa quy định trên Cổng Quản trị"]
    TRIGGER_EVENT -- Dữ liệu mới tích lũy đủ 1000 đơn --> EVENT_DATA["Scheduler phát hiện dữ liệu drift đủ ngưỡng"]
    TRIGGER_EVENT -- Huấn luyện định kỳ hàng tuần --> EVENT_CRON["Lịch chạy định kỳ đêm Chủ Nhật"]

    EVENT_POLICY --> ENQUEUE_JOB["1. Khởi tạo tác vụ học máy trong `eas.ai_learning_job`:\nTrạng thái: QUEUED, Cấp phát Lease khóa độc quyền"]
    EVENT_DATA --> ENQUEUE_JOB
    EVENT_CRON --> ENQUEUE_JOB

    ENQUEUE_JOB --> LOCK_CLIENT_PORTAL["2. KÍCH HOẠT KHÓA BẢO TRÌ TỰ ĐỘNG (Auto-Lock Client):\n- Đặt cờ `client_maintenance_lock = true`\n- Cổng Nhân viên (:8080) tự động hiển thị màn hình chờ bảo trì\n- Tạm dừng cho phép nhân viên nộp đơn mới"]

    LOCK_CLIENT_PORTAL --> WORKER_CLAIM_JOB["3. Worker chuyên trách AI tiếp nhận Job (Trạng thái: RUNNING)"]
    
    WORKER_CLAIM_JOB --> STEP1_SNAPSHOT["BƯỚC 1: CHỤP BỘ QUY ĐỊNH (SNAPSHOT - 25%)\n- Chụp toàn văn các điều khoản quy định hiện hành\n- Băm chuỗi SHA-256 xác thực phiên bản snapshot"]

    STEP1_SNAPSHOT --> STEP2_LEARN["BƯỚC 2: TRÍCH XUẤT LUẬT & HUẤN LUYỆN (LEARN - 50%)\n- Trích xuất tự động các luật định mức, số ngày, thẩm quyền\n- Huấn luyện lại bộ phân loại TF-IDF + SGD\n- Tái chuẩn hóa mô hình chấm điểm Gradient Boosting"]

    STEP2_LEARN --> STEP3_APPLY["BƯỚC 3: ÁP DỤNG & KIỂM THỬ NGOÀI (APPLY - 75%)\n- Nạp bộ luật mới sang AI Service (`POST /ai/policy/rules`)\n- Chạy Bộ kiểm thử Vàng (Golden Test Suite - 100 kịch bản chuẩn)\n- Đánh giá chỉ số F1-Score, AUC-ROC và Calibration"]

    STEP3_APPLY --> GOLDEN_TEST_PASS{"Kiểm thử Vàng đạt chuẩn\n(F1 >= 95% và 0 lỗi nghiêm trọng)?"}
    
    GOLDEN_TEST_PASS -- Thất bại --> FAIL_SAFE_ROLLBACK["CƠ CHẾ DỰ PHÒNG AN TOÀN (Fail-Safe):\n- Job chuyển trạng thái FAILED\n- Giữ nguyên bộ luật và mô hình cũ đang an toàn\n- Mở khóa bảo trì Cổng nhân viên\n- Gửi cảnh báo khẩn cấp cho Quản trị viên AI"]
    FAIL_SAFE_ROLLBACK --> END_FAIL((Dừng lại))

    GOLDEN_TEST_PASS -- Đạt chuẩn xuất sắc --> STEP4_COMMIT["BƯỚC 4: HOÀN TẤT & CÔNG BỐ (APPLIED - 100%)\n- Ký số ban hành phiên bản quy định mới (v1.x -> v2.x)\n- Tạo thông báo hệ thống tóm tắt các điểm thay đổi\n- Cập nhật phiên bản mô hình hiệu lực trong Registry"]

    STEP4_COMMIT --> UNLOCK_CLIENT_PORTAL["4. MỞ KHÓA CỔNG NHÂN VIÊN (Unlock Client):\n- Đặt cờ `client_maintenance_lock = false`\n- Người dùng đăng nhập bình thường\n- Hiển thị Popup thông báo: 'Hệ thống đã cập nhật quy định mới'"]

    UNLOCK_CLIENT_PORTAL --> END_SUCCESS((Hoàn tất chu trình))
```

---

## 3. BẢNG ĐỐI SOÁT VÀ ĐÁNH GIÁ CHUYÊN MÔN CỦA HỘI ĐỒNG IT

| Mã Sơ Đồ | Tên Quy Trình Nghiệp Vụ | Hiện Thực Trong Codebase | Đánh Giá Rủi Ro Thực Tế | Giải Pháp Đã Áp Dụng (15 Năm Kinh Nghiệm) |
|:---:|:---|:---|:---|:---|
| **AD-01** | Vòng đời yêu cầu tổng thể | `api_core/workflow/service.py` | Nguy cơ nhầm lẫn luồng giữa đơn chỉ duyệt và đơn cần thi công thực tế. | Phân tách rạch ròi 3 mẫu vòng đời (Lifecycle A/B/C) trong `request_type`. |
| **AD-02** | Soạn thảo và gửi yêu cầu | `api_core/workflow/views.py` | Rủi ro nộp đơn đúp khi mạng giật lag hoặc người dùng click liên tục. | Bắt buộc kiểm soát `Idempotency-Key` và snapshot toàn bộ rules tại thời điểm nộp. |
| **AD-03** | Xử lý phê duyệt đa cấp | `api_core/workflow/service.py` | Rủi ro tự duyệt (Self-approval) và tranh chấp khi 2 sếp cùng bấm duyệt đồng thời. | Khóa hàng `FOR UPDATE`, kiểm tra SoD và từ chối ngay với mã lỗi 403 Forbidden. |
| **AD-04** | Thực hiện và nghiệm thu | `api_core/workflow/service.py` | Rủi ro 2 chuyên viên cùng làm 1 việc và Executor tự nghiệm thu đơn của mình. | Cơ chế Claim Lease độc quyền và bắt buộc Acceptor phải là nhân sự độc lập. |
| **AD-07** | Ban hành cấu hình quy chế | `api_core/workflow/config_service.py` | Rủi ro sửa trực tiếp cấu hình đang chạy làm đứt gãy các đơn đang duyệt dở dang. | Triển khai mô hình Immutable Config Release (Chỉ Clone bản nháp mới rồi Publish nguyên tử). |
| **AD-08** | Phân phối công việc thực thi | `api_core/workflow/ops_service.py` | Chuyên viên nhận việc rồi bỏ quên khiến hồ sơ bị tắc nghẽn kéo dài. | Cơ chế Auto-Reclaim khi hết hạn Lease thi công mà không có cập nhật tiến độ. |
| **AD-09** | Kiểm toán chuỗi băm | `api_core/audit.py` | Dữ liệu kiểm toán bị sửa lén trực tiếp trong Database bằng quyền root. | Chuỗi băm SHA-256 đan kết nối tiếp và đối soát chốt trạm Checkpoint độc lập. |
| **AD-10** | Nghiệm thu đưa phần mềm vào dùng | `.github/workflows/ci.yml` | Đưa code lỗi hoặc còn sót lỗ hổng bảo mật lên môi trường Production. | Thiết lập Quality Gates tự động 7 tầng, 100% test pass mới cho phép phát hành. |
| **AD-11** | Quyền riêng tư & Ẩn danh hóa | `api_core/administration/org_users_rbac.py` | Xóa dữ liệu làm gãy khóa ngoại và hỏng tính toàn vẹn của chuỗi băm kiểm toán. | Ẩn danh hóa thông tin định danh (PII Pseudonymization) nhưng bảo toàn chuỗi băm lịch sử. |
| **AD-12** | Huấn luyện lại và kiểm chứng AI | `api_core/workflow/ai_learning.py` | AI học quy định mới trong lúc người dùng vẫn nộp đơn dẫn đến xung đột quyết định. | Tự động kích hoạt Khóa bảo trì Cổng nhân viên (`client_maintenance_lock`) và chỉ mở khi đạt Bộ test Vàng. |
