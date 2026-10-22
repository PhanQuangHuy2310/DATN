# MASTER PROMPT THỰC THI CHO AI AGENT — PHÂN HỆ `api_core` (ENTERPRISE APPROVAL SYSTEM - EAS P0)

> **Hướng dẫn sử dụng:** Sao chép toàn bộ nội dung tài liệu này và dán trực tiếp cho AI Coding Agent (Codex / Antigravity / Claude Code / Cursor) tại thư mục gốc của repository `DATN`. Prompt này đã được đối soát chéo 100% giữa mã nguồn thực tế, bộ đặc tả v2.0, schema SQL v2.0.1 và bộ 68 sơ đồ cập nhật mới nhất trên Google Drive (đến ngày 21/10/2026).

## 1. VAI TRÒ, BỐI CẢNH VÀ KỶ LUẬT THỰC THI CỦA AI AGENT

Bạn là **Principal Fullstack & Backend Architect (15 năm kinh nghiệm xây dựng hệ thống Enterprise/ERP/Workflow quy mô lớn)**. Nhiệm vụ của bạn là hoàn thiện, sửa lỗi tiềm ẩn và mở rộng phân hệ **`api_core`** cho dự án Đồ án Tốt nghiệp **Enterprise Approval System (EAS — Phạm vi P0)**.

Bạn bắt buộc tuân thủ quy trình trong `.codex/skills/run-software-agency-lifecycle/SKILL.md`, `actions.md`, `README.md`, `api_core/README.md`, `docs/README.md`, `plans/` và `changelogs/`.

### 1.1. Nguyên tắc "Tài liệu Mới nhất Ưu tiên" (Latest Modified Time Wins)

Khi có bất kỳ sự khác biệt nào giữa các tài liệu trong dự án, bạn **BẮT BUỘC** áp dụng thứ tự ưu tiên theo mốc thời gian sửa đổi gần nhất đã được kiểm toán dưới đây:

| Thứ tự ưu tiên | Nguồn tài liệu / Hiện vật | Thời gian cập nhật | Quy tắc áp dụng cho `api_core` | 
| ----- | ----- | ----- | ----- | 
| **1 (Cao nhất)** | Bộ 5 tài liệu Sơ đồ chốt cuối trên Drive (`State-machine.docx`, `Sequence-Diagram`, `ER`, `Activity-Diagram`, `Usecase diagram`) & `docs/diagrams/*.md` | `19/10/2026` – `21/10/2026` | Chuẩn hóa tuyệt đối 8 State Machines (`ST-01`..`ST-08`), 22 Sequence (`SD-01`..`SD-22`), 10 Activity (`AD-01`..`AD-10`), 9 Use Case (`UC01`..`UC15`, `UC17`), 19 Architecture/ERD (`AR`, `DFD`, `SEC`, `DP`, `ER`). | 
| **2** | Source code & Biên bản Runtime r6 (`api_core/`, `plans/active/2026-10-09_dual_review_remediation.md`, `changelogs/2026-10-09_enterprise_baseline_release.md`, `docs/12_*.md`, `docs/13_*.md`) | `09/10/2026` (`13:38` – `14:43`) | Giữ nguyên kiến trúc **Django 5.2.18 Modular Monolith + Raw Parameterized SQL (`psycopg 3.3.6`) + Redis + ClamAV + Supabase Private Storage + 8 Mock Enterprise Schemas**. Không làm gãy 67 Django tests + 4 logger tests + 4 Playwright E2E tests đã PASS. | 
| **3** | Bộ 6 tài liệu Đặc tả v2.0 (`docs/00_*.docx` đến `05_*.docx`) & Gói Database SQL v2.0.1 (`database/EAS_Supabase_SQL/00_eas_supabase_schema.sql`, `DATA_DICTIONARY.md`) | `21/09/2026` – `09/10/2026` | Chuẩn hóa 30 bảng vật lý (`DB01`–`DB30`), 9 invariants (`INV01`–`INV09`), 15 business rules (`BR01`–`BR15`), 19 functional requirements (`FR01`–`FR19`), 10 NFRs (`NFR01`–`NFR10`), hợp đồng API & 100 test cases (`TC001`–`TC100`). | 
| **4 (Loại bỏ)** | `plan.md` (gốc), `plan.docx` (`16/09/2026`), `Nhóm 7 - Đề cương...docx` (`03/09/2026`) | `03/09/2026` – `21/09/2026` | **TUYỆT ĐỐI KHÔNG IMPLEMENT TRONG P0:** Không gọi FastAPI AI Service, không OCR, không XGBoost/LLM Auto-Approve, không OPA Rego, không Drools, không React Flow kéo thả tổng quát, không dùng `auth.users` của Supabase, không dùng các trạng thái cũ (`EVALUATING`, `AUTO_APPROVED`, `EXECUTED`, `EXECUTION_REJECTED`, `EXPIRED_SLA`, `ASSIGNED`). | 

### 1.2. Các Cấm Kỵ Tuyệt Đối (Hard Constraints)

1. **Không dùng Django ORM Models để sinh migration đè lên 30 bảng `eas.*`**: Toàn bộ 30 bảng miền ứng dụng (`eas.security_epoch` đến `eas.retention_hold`) đã được quản lý bởi `database/EAS_Supabase_SQL/00_eas_supabase_schema.sql` với 27 SQL functions/triggers bảo vệ invariant. Mọi truy vấn trong `api_core` phải sử dụng `django.db.connection.cursor()` với câu lệnh SQL tham số hóa (`%s`) tường minh, tuyệt đối không nối chuỗi SQL.

2. **Không giữ Database Lock khi gọi mạng (Network I/O)**: Mọi thao tác gọi Supabase Private Storage (`put_private_object`, `delete_private_object`, stream download) hoặc quét virus ClamAV (`scan_with_clamav`) bắt buộc thực hiện **ngoài** khối `transaction.atomic()`.

3. **Không phá vỡ tính tương thích ngược (Backward Compatibility)**: `web_client/src/App.jsx` và bộ 67 unit tests hiện hành đang gọi các route trong `api_core/`. Khi bổ sung hoặc chuẩn hóa các endpoint theo `03_Du_lieu_va_API_v2.docx`, bạn phải **giữ nguyên toàn bộ URL/payload hiện có** và đăng ký song song các URL alias/trường mở rộng của tài liệu 03.

4. **Không ghi khống trạng thái kiểm thử**: Chỉ đánh dấu `VERIFIED` hoặc `PASS` trong `plans/` và `changelogs/` sau khi bạn thực sự chạy lệnh kiểm thử và quan sát thấy kết quả `OK`. Mọi ca kiểm thử chưa chạy trên môi trường thật phải giữ nguyên `NOT RUN` hoặc `BLOCKED`.

5. **Không lộ Secret / PII**: Không bao giờ in `DATABASE_URL`, password, token, `SUPABASE_SECRET_KEY` hoặc nội dung nhạy cảm ra log hay lịch sử Git. Mọi log phải đi qua `api_core.logger` (`SensitiveDataFilter` + `JsonFormatter`).

## 2. KIẾN TRÚC TỔNG THỂ & QUY TRÌNH QUẢN TRỊ `plans/` + `changelogs/`

### 2.1. Cấu trúc Thư mục Mục tiêu của `api_core`

```
api_core/
├── __init__.py
├── Dockerfile
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .env.worker.example
├── audit.py                     # Canonical JSON RFC 8785 (NFC) + SHA-256 + Chain Verifier
├── http.py                      # Correlation ID, JSON body parser, Error envelope chuẩn
├── logger.py                    # Redaction filter, JSON formatter, Changelog file writer
├── storage.py                   # MIME magic-byte sniffer, ClamAV stream, Private Storage HTTP client
├── worker.py                    # Outbox claim/lease/ACK/retry/dead/replay & SLA reminder/breach scanner
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── database.py              # Parser DATABASE_URL an toàn, sslmode, statement_timeout=30000, lock_timeout=5000
│   ├── settings.py              # Cấu hình Django, Redis cache, Argon2, Cookie/CSRF/HSTS
│   ├── urls.py                  # Root URL dispatcher
│   └── wsgi.py
├── health/
│   ├── __init__.py
│   ├── urls.py                  # /health/live, /health/ready
│   └── views.py                 # Kiểm tra capability DB role, 30 bảng, 3 active releases, 17 mock relations, Redis, Storage/ClamAV
├── catalog/
│   ├── __init__.py
│   ├── urls.py                  # /api/v1/meta/request-types
│   └── views.py
├── authn/
│   ├── __init__.py
│   ├── models.py                # Dataclasses: AuthUser, Actor
│   ├── service.py               # Argon2 verify, Password policy, Session binding Redis, require_actor decorator
│   ├── urls.py                  # /api/v1/auth/{csrf,login,logout,me,password,change-password}
│   └── views.py
├── domain/
│   ├── __init__.py
│   ├── routing.py               # RouteDecision, resolve_route (1-3 cấp, ngưỡng VND, SoD)
│   └── validation.py            # validate_payload, validate_draft_payload, validate_config_release_payload
├── workflow/
│   ├── __init__.py
│   ├── attachments.py           # Upload/link draft & execution evidence, metadata & private stream download
│   ├── config_service.py        # [MỚI/MỞ RỘNG] Clone, edit DRAFT, validate & publish config_release (UC02)
│   ├── ops_service.py           # [MỚI/MỞ RỘNG] OPS metadata list, Reassign actor (UC09), Outbox DEAD replay (UC14)
│   ├── reporting.py             # [MỚI/MỞ RỘNG] Notifications (UC13), Scoped Reports, Audit trail & Verify (UC15)
│   ├── service.py               # Core commands: draft, patch draft, submit/resubmit, approve/reject/needs_info, claim, issue, submit_execution, accept/rework, cancel/withdraw
│   ├── urls.py                  # Toàn bộ routes /api/v1/... (giữ route cũ + thêm alias chuẩn tài liệu 03)
│   └── views.py                 # HTTP controllers
├── mock_sources/
│   ├── __init__.py
│   ├── apps.py
│   ├── service.py               # 17 allowlisted resources từ 8 schema mock_*
│   ├── urls.py                  # /api/v1/mock/...
│   └── views.py
├── management/
│   └── commands/
│       ├── configure_e2e_user.py
│       ├── run_outbox_worker.py
│       ├── identity_import.py   # [MỚI] UC17: --manifest PATH --dry-run / --apply --operator USER --approval REF
│       ├── account_reset.py     # [MỚI] UC01/UC17: --user USER --operator USER --approval REF
│       ├── audit_verify.py      # [MỚI] UC15: --scope SCOPE [--checkpoint REF]
│       └── privacy_case.py      # [MỚI] Tài liệu 05 mục 11: --case CASE --action ACTION --approval REF
└── tests/
    ├── test_audit.py
    ├── test_authn.py
    ├── test_database_config.py
    ├── test_domain.py
    ├── test_health.py
    ├── test_mock_sources.py
    ├── test_storage.py
    ├── test_worker.py
    ├── test_workflow_api.py
    ├── test_workflow_service.py
    ├── test_ops_and_config.py   # [MỚI] Unit/Contract tests cho UC02, UC03 PATCH, UC05 Download, UC09 Reassign, UC10/11 Issue
    └── test_reporting_and_cli.py# [MỚI] Unit/Contract tests cho UC13 Notifications, UC15 Reports/Audit, UC17 CLI

```

### 2.2. Quy trình Cập nhật `plans/` và `changelogs/` Bắt Buộc

Mỗi khi thực hiện một đợt thay đổi trong `api_core`, bạn phải tuân thủ nghiêm ngặt vòng đời hồ sơ sau:

1. **Trước khi viết code (`plans/active/`)**:

   * Đọc `plans/active/2026-10-09_dual_review_remediation.md` và `plans/active/README.md`.

   * Cập nhật hoặc tạo file kế hoạch mới tại `plans/active/YYYY-MM-DD_api_core_full_remediation.md` (đồng thời thêm link vào `plans/active/README.md`) theo đúng cấu trúc bảng:

     * Thuộc tính: `Mã`, `Ngày mở`, `Trạng thái (IN PROGRESS)`, `Phạm vi`, `Quyền tiếp tục`.

     * Mục 1: Cơ chế hai cổng (**Cổng hướng dẫn** thiết kế/code + **Cổng hội đồng** phản biện/test phá lỗi).

     * Mục 2: Bảng Work breakdown (`Work item`, `Điểm mù/UC liên quan`, `Deliverable`, `Gate hội đồng`, `Trạng thái`).

2. **Trong và sau khi viết code (`plans/active/` & `plans/reports/`)**:

   * Ghi nhận từng vòng đối soát vào mục `Nhật ký đối soát` của file plan đang active.

   * Khi một kế hoạch trong `plans/active/` đã hoàn tất 100% các mục được giao, di chuyển file đó sang `plans/completed/` (không bao giờ sửa các file đã nằm trong `plans/completed/`) và tạo báo cáo tổng kết tại `plans/reports/`.

3. **Cập nhật Nhật ký Hệ thống & Phát hành (`changelogs/`)**:

   * Tạo hoặc cập nhật bản ghi phát hành tại `changelogs/YYYY-MM-DD_api_core_complete_p0.md` và thêm liên kết vào `changelogs/README.md`.

   * Tuân thủ 5 phân mục mức độ log trong `changelogs/`:

     * `changelogs/INFO/`: Ghi nhận các mốc khởi tạo, hoàn tất migration/test gate, đăng nhập/publish thành công.

     * `changelogs/WARN/`: Ghi nhận các tình huống retry thành công, rate limit, cấu hình fallback development (`EAS_REQUIRE_STORAGE=false`).

     * `changelogs/ERROR/`: Ghi nhận các lỗi command/validation/storage làm thất bại request đã được kiểm thử và xử lý.

     * `changelogs/DEBUG_TRACE/`: Chỉ dùng khi trace chi tiết ở local/staging; tắt ở production.

     * `changelogs/FATAL_CRITICAL/`: Ghi nhận các sự kiện dừng khẩn cấp (như phát hiện DB login có quyền superuser hoặc thiếu secret bắt buộc ở production).

## 3. QUY TẮC GIAO DỊCH, KHÓA (LOCK ORDER) & BẤT BIẾN DATABASE (DB01–DB30)

Mọi hàm ghi dữ liệu trong `api_core` phải tuân thủ tuyệt đối thứ tự khóa toàn cục trong `02_Phan_tich_thiet_ke_v2.docx` (Mục 8 & 9) và tương thích 100% với 27 PostgreSQL triggers trong `00_eas_supabase_schema.sql`:

### 3.1. Thứ tự Khóa Toàn cục (Global Lock Acquisition Order)

Trong một khối `with transaction.atomic(), connection.cursor() as cursor:` (mức cô lập mặc định `READ COMMITTED` của PostgreSQL):

1. **Bước 1 — Khóa `security_epoch` (`DB01`)**:

   * Với **mọi lệnh nghiệp vụ** (create draft, patch draft, submit, approve/reject/needs_info, cancel/withdraw, claim, issue, submit execution, accept/rework, reassign, upload attachment metadata, worker claim/ACK/SLA):
     Gọi ngay đầu transaction:

     ```
     SELECT eas.lock_security(false); -- Tương đương SELECT version FROM eas.security_epoch WHERE id=1 FOR SHARE
     
     ```

   * Với **mọi lệnh thay đổi định danh/quyền/mật khẩu** (change password, reset password, disable user, identity import, revoke participant read, privacy purge):
     Gọi ngay đầu transaction:

     ```
     SELECT eas.lock_security(true);  -- Tương đương SELECT version FROM eas.security_epoch WHERE id=1 FOR UPDATE
     
     ```

     Và tăng `version` đúng **một lần** cho cả transaction:

     ```
     UPDATE eas.security_epoch SET version = version + 1, updated_at = %s WHERE id = 1;
     
     ```

2. **Bước 2 — Khóa `request_type` (`DB05`) và `config_release` (`DB06`) (nếu có)**:

   * Khi `create_draft` hoặc `submit_request` (hoặc `resubmit`): khóa `FOR SHARE OF rt, cr`.

   * Khi `publish_config_release`: khóa `FOR UPDATE OF rt, cr`.

3. **Bước 3 — Khóa `request` (`DB07`)**:

   * Khóa `SELECT ... FROM eas.request WHERE id = %s FOR UPDATE` trước khi khóa hoặc sửa bất kỳ bảng con nào (`workflow_instance`, `approval_step`, `execution_attempt`, `attachment`, `sla_stage`).

   * **Lưu ý cực kỳ quan trọng về Trigger `eas.guard_request()`**:
     Trigger `eas.guard_request()` trên bảng `eas.request` kiểm tra:

     ```
     IF NEW IS DISTINCT FROM OLD AND (NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_at<OLD.updated_at) THEN
       RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='Request command requires version increment exactly once and monotonic updated_at';
     END IF;
     
     ```

     Do đó:

     * Mọi lệnh UPDATE trên `eas.request` có thay đổi bất kỳ cột nào **BẮT BUỘC** phải tăng `lock_version = lock_version + 1` và cập nhật `updated_at = now` (>= `OLD.updated_at`).

     * Các cột `id`, `code`, `requester_id`, `type_id`, `origin_request_id`, `created_at` là **bất biến** sau khi INSERT.

     * Trạng thái terminal (`COMPLETED`, `REJECTED`, `CANCELLED`) không bao giờ được UPDATE nữa.

     * Khi `status = 'COMPLETED'`, bắt buộc `completed_at IS NOT NULL` và `approved_at IS NOT NULL` (`completed_at >= approved_at`).

4. **Bước 4 — Khóa các bảng con theo thứ tự**:

   * `eas.workflow_instance` (`FOR UPDATE`) → `eas.approval_step` / `eas.execution_attempt` (`FOR UPDATE`) → `eas.sla_stage` (`FOR UPDATE`).

   * **Lưu ý Partial Unique Indexes**:

     * `one_active_instance`: Mỗi `request_id` chỉ có tối đa 1 `workflow_instance` có `state = 'ACTIVE'`. Phải đóng instance cũ (`COMPLETED`, `REJECTED`, `SUPERSEDED`, `CANCELLED` kèm `closed_at = now`) trước khi INSERT instance mới.

     * `one_active_step`: Mỗi `instance_id` chỉ có tối đa 1 `approval_step` có `state = 'ACTIVE'`. Phải đóng step hiện tại (`APPROVED`, `REJECTED`, `NEEDS_INFO`, `SKIPPED` kèm `closed_at = now`) trước khi chuyển step kế tiếp sang `ACTIVE` (`activated_at = now`).

     * `one_current_attempt`: Mỗi `instance_id` chỉ có tối đa 1 `execution_attempt` có `state IN ('READY', 'RUNNING', 'SUBMITTED')`. Khi `REWORK` hoặc `REASSIGN` lúc `RUNNING`, phải UPDATE attempt cũ sang `state = 'FINISHED'`, `closure_kind = 'REWORK' | 'REASSIGNED'`, `closed_at = now` **trước khi** INSERT attempt mới ở trạng thái `READY`.

     * `one_open_stage`: Mỗi `request_id` chỉ có tối đa 1 `sla_stage` có `closed_at IS NULL`. Phải UPDATE `closed_at = now` cho stage đang mở **trước khi** INSERT `sla_stage` mới.

5. **Bước 5 — Khóa `audit_head` (`DB24`) và Ghi `audit_event` (`DB22`) / `admin_event` (`DB23`)**:

   * Gọi `SELECT seq, last_hash FROM eas.lock_audit_head(%s)` với `scope_key = f"REQ:{request_id}"` hoặc `'ADMIN'`.

   * Tính `seq = head.seq + 1`, `prev_hash = head.last_hash`.

   * Chuẩn hóa JSON theo RFC 8785 (`api_core.audit.canonical_sha256(event)`), sau đó INSERT vào `eas.audit_event` hoặc `eas.admin_event`. Trigger `advance_request_audit` / `advance_admin_audit` sẽ tự động kiểm tra `NEW.seq = head.seq + 1`, `NEW.prev_hash = head.last_hash` và cập nhật `eas.audit_head`.

6. **Bước 6 — Ghi `outbox_event` (`DB26`) và `idempotency_record` (`DB28`)**:

   * Mọi sự kiện thông báo đẩy vào `eas.outbox_event` với `dedupe_key` duy nhất.

   * Lưu kết quả HTTP (`http_status` 200..299, `response_body`, `request_id`) vào `eas.idempotency_record`.

## 4. ĐẶC TẢ CHI TIẾT CÁC HẠNG MỤC CẦN SỬA LỖI & HOÀN THIỆN TRONG `api_core`

Thực hiện tuần tự từng nhiệm vụ từ **Task 1** đến **Task 8** dưới đây.

### TASK 1: Sửa 4 Lỗi Nghiệp Vụ & Trigger Trong `api_core/workflow/service.py`

#### 1.1. Sửa lỗi `UniqueViolation` trên `eas.request_participant` khi Resubmit (`UC07`, `SD-20`) & Bổ sung Acceptor

* **Vấn đề hiện tại**: Trong `submit_request` (`api_core/workflow/service.py`), câu lệnh `INSERT INTO eas.request_participant(request_id,user_id,joined_as) VALUES (%s,%s,%s)` không có `ON CONFLICT`, dẫn đến khi Resubmit một hồ sơ từ trạng thái `NEEDS_INFO` (Revision 2+), các user đã có trong `request_participant` ở Revision 1 sẽ gây lỗi `UniqueViolation (23505)`. Ngoài ra, `decision.acceptor_id` chưa được thêm vào danh sách `participants`.

* **Cách sửa chính xác**:

  1. Khi tổng hợp `participants` trong `submit_request`:

     ```
     participants: list[tuple[str, str]] = [(actor.id, "REQUESTER")]
     participants.extend((item, "APPROVER") for item in decision.approver_ids)
     if decision.executor_id:
         participants.append((decision.executor_id, "EXECUTOR"))
     if decision.acceptor_id:
         participants.append((decision.acceptor_id, "ACCEPTOR"))
     seen_users: set[str] = set()
     unique_participants: list[tuple[str, str]] = []
     for user_id, joined_as in participants:
         if user_id not in seen_users:
             seen_users.add(user_id)
             unique_participants.append((user_id, joined_as))
     
     ```

  2. Thay câu lệnh SQL INSERT bằng:

     ```
     INSERT INTO eas.request_participant(request_id, user_id, joined_as)
     VALUES (%s, %s, %s)
     ON CONFLICT (request_id, user_id) DO NOTHING
     
     ```

#### 1.2. Bảo toàn tệp đính kèm nháp khi chuyển sang `NEEDS_INFO` (`UC06`, `UC07`, `SD-04`, `SD-20`)

* **Vấn đề hiện tại**: Khi `submit_request` chạy thành công, các dòng trong `eas.draft_attachment` bị xóa để chuyển sang `eas.revision_attachment`. Nếu Approver chọn `NEEDS_INFO`, hồ sơ về trạng thái `NEEDS_INFO` để Requester sửa và gửi lại, nhưng `eas.draft_attachment` đang trống rỗng khiến Requester mất danh sách tệp đã chọn ở revision trước.

* **Cách sửa chính xác**:

  1. Trong `decide_approval`, khi `outcome == "NEEDS_INFO"`: sao chép lại các tệp `CLEAN` chưa xóa từ `eas.revision_attachment` của `current_revision_id` sang `eas.draft_attachment`:

     ```
     INSERT INTO eas.draft_attachment(request_id, attachment_id, added_by)
     SELECT r.id, ra.attachment_id, r.requester_id
     FROM eas.request r
     JOIN eas.revision_attachment ra ON ra.revision_id = r.current_revision_id AND ra.request_id = r.id
     JOIN eas.attachment a ON a.id = ra.attachment_id AND a.request_id = r.id
     WHERE r.id = %s AND a.scan_state = 'CLEAN' AND a.deleted_at IS NULL
     ON CONFLICT (request_id, attachment_id) DO NOTHING
     
     ```

  2. Trong `submit_request`, nếu `attachment_ids` không được truyền tường minh trong body nhưng hồ sơ đang là `DRAFT` hoặc `NEEDS_INFO` đã có tệp trong `eas.draft_attachment`, cho phép lấy danh sách `attachment_ids` từ `eas.draft_attachment` (nếu body truyền `"attachment_ids"` thì dùng danh sách truyền lên, kiểm tra tất cả đều thuộc `request_id`, `uploader_id = actor.id`, `scan_state = 'CLEAN'`, `deleted_at IS NULL`).

#### 1.3. Kiểm tra `viewed_release_id` (`CONFIG_CHANGED` - `UC04`, `TC029`) và Actor Bước Kế Tiếp (`ASSIGNEE_UNAVAILABLE` - `UC06`, `UC11`, `UC12`, `TC041`, `TC055`)

* **Kiểm tra `viewed_release_id` trong `submit_request`**:

  * Cho phép body của `submit_request` nhận thêm trường tùy chọn `"viewed_release_id"`.

  * Nếu `"viewed_release_id"` được gửi lên: chuẩn hóa UUID (`INVALID_RELEASE_ID`), và kiểm tra nếu `viewed_release_id != release_id` (active release hiện hành của `request_type`) thì raise `CommandError("CONFIG_CHANGED", status=409)`.

  * Nếu `existing_request_id` tồn tại và `"viewed_release_id"` không được truyền trong body, nhưng `draft_release_id` của request khác `release_id` hiện hành chỉ khi client yêu cầu strict check `viewed_release_id`: ưu tiên kiểm tra khi `"viewed_release_id"` có mặt trong body để không làm gãy các bài test cũ không gửi `"viewed_release_id"`.

* **Kiểm tra `ASSIGNEE_UNAVAILABLE` trong `decide_approval`, `submit_execution`, `decide_acceptance`**:

  * Tạo hàm helper `_is_actor_valid_for_role(cursor, *, actor_id: str, role: str, department_id: str, type_id: str) -> bool`:

    ```
    SELECT EXISTS (
      SELECT 1 FROM eas.app_user u
      JOIN eas.role_membership rm ON rm.user_id = u.id
      WHERE u.id = %s AND u.is_active
        AND rm.role = %s AND rm.revoked_at IS NULL
        AND rm.valid_from <= statement_timestamp()
        AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
        AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = %s)
        AND (rm.type_scope = 'ALL' OR rm.type_id = %s)
    )
    
    ```

  * Trong `decide_approval` khi `outcome == "APPROVE"`:

    * Nếu còn `next_step`: lấy `next_step_id, next_assignee_id`. Kiểm tra `_is_actor_valid_for_role(cursor, actor_id=next_assignee_id, role="APPROVER", department_id=department_id, type_id=type_id)`. Nếu `False`, raise `CommandError("ASSIGNEE_UNAVAILABLE", status=409)` trước khi ghi decision!

    * Nếu là bước duyệt cuối của Lifecycle `B` hoặc `C`: kiểm tra `executor_id` có hợp lệ với `role="EXECUTOR"` không (và với Lifecycle `C`, kiểm tra thêm `acceptor_id` có hợp lệ với `role="ACCEPTOR"` và `acceptor_id != executor_id` không). Nếu không hợp lệ, raise `CommandError("ASSIGNEE_UNAVAILABLE", status=409)`.

  * Trong `submit_execution` khi `lifecycle == "C"`:

    * Kiểm tra `acceptor_id` trên `workflow_instance` còn active, hợp lệ với `role="ACCEPTOR"` và `acceptor_id != actor.id`. Nếu không, raise `CommandError("ASSIGNEE_UNAVAILABLE", status=409)`.

  * Trong `decide_acceptance` khi `outcome == "REWORK"`:

    * Sử dụng `planned_executor_id` của `workflow_instance` làm người nhận attempt mới (`attempt_no + 1`). Trước khi tạo attempt mới, kiểm tra `_is_actor_valid_for_role(cursor, actor_id=planned_executor_id, role="EXECUTOR", department_id=department_id, type_id=type_id)`. Nếu `False`, raise `CommandError("ASSIGNEE_UNAVAILABLE", status=409)` (để `OPS_ADMIN` dùng `UC09` đổi `PLANNED_EXECUTOR` rồi Acceptor mới bấm `REWORK` lại — đúng kịch bản `TC055` và `SD-06`).

#### 1.4. Kiểm tra Quyền Đọc trước khi Replay Idempotency (`BR12`, `NFR10`, `TC058`, `TC059`)

* Trong `_execute_idempotent` (`api_core/workflow/service.py`):

  * Ngay sau khi vào `with transaction.atomic(), connection.cursor() as cursor:`, gọi `cursor.execute("SELECT eas.lock_security(false)")`.

  * Khi tìm thấy bản ghi trong `eas.idempotency_record`:

    ```
    SELECT request_hash, http_status, response_body,
           expires_at > statement_timestamp() AS not_expired,
           tombstone_until > statement_timestamp() AS in_tombstone,
           request_id::text
    FROM eas.idempotency_record
    WHERE actor_id = %s AND command_scope = %s AND key = %s
    FOR UPDATE
    
    ```

    1. Nếu `not not_expired` hoặc `response_body is None`: raise `CommandError("IDEMPOTENCY_RESULT_EXPIRED", status=410)`.

    2. Nếu `request_hash != current_request_hash`: raise `CommandError("IDEMPOTENCY_KEY_REUSED", status=409)`.

    3. Nếu `existing_request_id` khác `None`: kiểm tra xem `actor_id` còn quyền đọc trên `existing_request_id` không (là `requester_id`, hoặc nằm trong `eas.request_participant` với `read_revoked_at IS NULL`, và tài khoản `is_active = TRUE`). Nếu `read_revoked_at IS NOT NULL` hoặc không còn quyền đọc, raise `CommandError("FORBIDDEN", status=403)` (hoặc `REQUEST_NOT_FOUND` 404). Tuyệt đối không trả lại `response_body` cũ nếu quyền đọc đã bị thu hồi (`TC058`)!

### TASK 2: Hoàn thiện Nhóm API Hồ Sơ, Lưu Nháp, Báo Vướng & Tải Tệp (`UC03`, `UC04`, `UC05`, `UC08`, `UC10`, `UC11`)

#### 2.1. Tạo Nháp & Cập nhật Nháp (`POST /api/v1/request-drafts`, `POST /api/v1/requests`, `PATCH /api/v1/requests/<uuid:request_id>`)

1. **Mở rộng `create_draft`**:

   * Chấp nhận `body` có `{"type_code": "..."}` và các trường tùy chọn `"title"`, `"origin_request_id"`.

   * Nếu có `"origin_request_id"`: chuẩn hóa UUID, kiểm tra request gốc tồn tại và thuộc cùng `requester_id = actor.id` (nếu không tồn tại hoặc khác owner thì raise `CommandError("ORIGIN_REQUEST_NOT_FOUND", status=404)`).

   * Nếu có `"title"`: chuẩn hóa NFC/trim, kiểm tra độ dài 5..150, không chứa HTML, lưu vào `draft_payload = {"title": clean_title}`.

2. **Bổ sung hàm `update_draft` (`PATCH /api/v1/requests/<uuid:request_id>` và `PATCH /api/v1/request-drafts/<uuid:request_id>`)**:

   * Yêu cầu `Idempotency-Key` header và `REQUESTER` role.

   * Body cho phép: `expected_version` (bắt buộc, int >= 0), `payload` (dict, tùy chọn), `amount_vnd` (int | None, tùy chọn), `viewed_release_id` (UUID string, tùy chọn), `attachment_ids` (list UUID tối đa 5 phần tử, tùy chọn).

   * Từ chối ngay bằng `CommandError("UNKNOWN_FIELD", status=422)` nếu trong `body` hoặc trong `payload` xuất hiện các trường cấm như `owner_id`, `requester_id`, `status`, `lock_version` (`TC013`, `TC073` Mass Assignment).

   * Viết hàm `validate_draft_payload(type_code, payload, form_schema, requester_id)` trong `api_core/domain/validation.py`: giống `validate_payload` nhưng **không** báo lỗi `REQUIRED` cho các trường chưa điền (vì nháp cho phép thiếu trường bắt buộc theo `01_SRS_v2.docx` mục 4), nhưng mọi trường đã điền phải đúng kiểu, đúng giới hạn `minLength`/`maxLength`/`minimum`/`maximum`/`enum`/`format`, không chứa HTML.

   * Trong transaction:

     * `SELECT eas.lock_security(false)`

     * Khóa `eas.request` (`FOR UPDATE`) kiểm tra `requester_id = actor.id`, `status IN ('DRAFT', 'NEEDS_INFO')`, `lock_version == expected_version` (sai version trả `409 VERSION_CONFLICT`).

     * Nếu có `attachment_ids`: xóa `eas.draft_attachment` cũ của `request_id` và INSERT lại các `attachment_id` mới (kiểm tra từng file thuộc `request_id`, `uploader_id = actor.id`, `scan_state = 'CLEAN'`, `deleted_at IS NULL`; nếu sai raise `CommandError("ATTACHMENT_INVALID", status=422)`). Lưu ý việc xóa khỏi `draft_attachment` không xóa dòng trong `eas.attachment` hay `eas.revision_attachment` (`TC020`).

     * UPDATE `eas.request SET draft_payload = %s, draft_amount_vnd = %s, draft_release_id = %s, lock_version = lock_version + 1, updated_at = %s WHERE id = %s`.

     * Ghi `_append_request_audit` với `action="DRAFT_UPDATED"`.

#### 2.2. Báo Không Thể Nhận Việc & Báo Vướng (`POST /api/v1/requests/<uuid:request_id>/issues` & `/execution/issues` — `UC10`, `UC11`, `SD-21`)

* Bổ sung hàm `report_execution_issue(*, actor: Actor, request_id: str, body: dict, idempotency_key: str, correlation_id: str) -> CommandResult`:

  * Body gồm: `expected_version` (int), `kind` (`"UNABLE_TO_CLAIM"` hoặc `"BLOCKED"`), `reason` (string, sau khi trim dài 10..2000 ký tự, không chứa HTML; nếu sai raise `CommandError("ISSUE_REASON_INVALID", status=422)`), và `attempt_id` (UUID tùy chọn; nếu không truyền thì lấy current attempt của active instance).

  * Trong transaction:

    * `SELECT eas.lock_security(false)`

    * Khóa `eas.request r`, `eas.workflow_instance i`, `eas.execution_attempt a` (`FOR UPDATE OF r, i, a`).

    * Kiểm tra `lock_version == expected_version`, `a.executor_id == actor.id`, `_authorize(cursor, actor_id=actor.id, role="EXECUTOR", department_id=department_id, type_id=type_id)`.

    * Nếu `kind == "UNABLE_TO_CLAIM"`: bắt buộc `r.status == "READY_FOR_EXECUTION"` và `a.state == "READY"` (nếu không trả `409 REQUEST_STATE_CONFLICT`).

    * Nếu `kind == "BLOCKED"`: bắt buộc `r.status == "IN_PROGRESS"` và `a.state == "RUNNING"` (nếu không trả `409 REQUEST_STATE_CONFLICT`).

    * INSERT vào `eas.execution_issue(id, request_id, attempt_id, actor_id, kind, reason, created_at)`.

    * **Không đổi `r.status` và không đóng/reset `eas.sla_stage`**, nhưng tăng `r.lock_version = r.lock_version + 1, updated_at = now` để ghi nhận command trên request.

    * Ghi `_append_request_audit` (`action=f"EXECUTION_ISSUE_{kind}"`, `target_type="execution_attempt"`, `target_id=attempt_id`).

    * INSERT vào `eas.outbox_event` (`event_type=f"EXECUTION_{kind}"`, `dedupe_key=f"issue:{issue_id}"`).

    * Trả HTTP `201` với `{"issue": {"id": issue_id, "kind": kind, "attempt_id": attempt_id}, "request": {"id": request_id, "status": status, "lock_version": lock_version + 1}}`.

#### 2.3. Mở rộng Quyền Đọc Danh sách, Chi tiết, Lịch sử Revision & Tải Tệp Chống IDOR (`UC05`, `SD-10`, `TC023–026`)

1. **Predicate Quyền Đọc Chuẩn (`_can_read_request`)**:
   Một Actor `is_active` được quyền đọc đầy đủ một `request` khi thỏa mãn ít nhất một trong 3 điều kiện:

   * Là chủ hồ sơ: `r.requester_id = actor.id`.

   * Là người từng tham gia chưa bị thu hồi quyền đọc: `EXISTS (SELECT 1 FROM eas.request_participant p WHERE p.request_id = r.id AND p.user_id = actor.id AND p.read_revoked_at IS NULL)` và `r.status != 'DRAFT'`.

   * Là `AUDITOR` có quyền còn hiệu lực khớp với `type_id` của request và `department_id` của revision hiện hành (hoặc phòng của requester nếu chưa có revision), và `r.status != 'DRAFT'`:

     ```
     EXISTS (
       SELECT 1 FROM eas.role_membership rm
       WHERE rm.user_id = %s AND rm.role = 'AUDITOR'
         AND rm.revoked_at IS NULL
         AND rm.valid_from <= statement_timestamp()
         AND (rm.valid_to IS NULL OR rm.valid_to > statement_timestamp())
         AND (rm.scope_kind = 'GLOBAL' OR rm.department_id = COALESCE(v.department_id, u.department_id))
         AND (rm.type_scope = 'ALL' OR rm.type_id = r.type_id)
     )
     
     ```

   * **Quy tắc chống IDOR**: Nếu request không tồn tại **hoặc** actor không thỏa mãn predicate đọc trên, mọi endpoint theo ID (`GET /api/v1/requests/<id>`, `/revisions`, `/audit`, `/attachments/<id>`) **BẮT BUỘC trả `404 REQUEST_NOT_FOUND` (hoặc `NOT_FOUND`)**, tuyệt đối không trả `403` để tránh dò quét UUID (`TC023`)!

   * **Quy tắc hiển thị khi `NEEDS_INFO`**: Trong `GET /api/v1/requests/<id>`, nếu `r.status == 'NEEDS_INFO'`, chỉ khi `actor.id == r.requester_id` mới trả thêm `draft_payload` đang sửa; đối với `APPROVER`/`AUDITOR`/participant khác, trường `payload` chỉ trả `v.payload` của revision đã gửi gần nhất (`01_SRS_v2.docx` mục 3).

2. **Mở rộng `GET /api/v1/requests`**:

   * Hỗ trợ các tham số lọc tùy chọn: `tab` (`mine`, `approval`, `execution`, `acceptance`), `status`, `type_code`, `department_id`, `created_from`, `created_to`, `limit` (1..100, mặc định 20), `offset` (0..10000).

   * Khi `tab == "mine"`: lọc `r.requester_id = actor.id`.

   * Khi `tab == "approval"`: lọc các request có `approval_step` đang `state = 'ACTIVE'` và `assignee_id = actor.id`.

   * Khi `tab == "execution"`: lọc các request có `execution_attempt` đang `state IN ('READY', 'RUNNING')` và `executor_id = actor.id`.

   * Khi `tab == "acceptance"`: lọc các request có `workflow_instance` đang `state = 'ACTIVE'`, `lifecycle = 'C'`, `acceptor_id = actor.id` và `execution_attempt` có `state = 'SUBMITTED'`.

3. **Bổ sung `GET /api/v1/requests/<uuid:request_id>/revisions` và `GET /api/v1/requests/<uuid:request_id>/revisions/<uuid:revision_id>`**:

   * Kiểm tra predicate đọc đầy đủ (ngoài quyền trả `404`).

   * Trả danh sách các `request_revision` của `request_id` theo `revision_no DESC` kèm danh sách tệp trong `eas.revision_attachment`.

4. **Bổ sung `GET /api/v1/attachments/<uuid:attachment_id>` và `GET /api/v1/attachments/<uuid:attachment_id>/download` (`UC05`, `SD-10`, `TC014`, `TC018`)**:

   * Tìm `attachment` theo `id` (chưa bị xóa `deleted_at IS NULL`) và kiểm tra actor có quyền đọc đầy đủ trên `attachment.request_id` không. Nếu không tồn tại hoặc không có quyền đọc request: trả `404 NOT_FOUND`.

   * Với `GET /api/v1/attachments/<id>`: trả metadata `{id, request_id, original_name, mime, size_bytes, scan_state, created_at, scanned_at}` (không bao giờ trả `storage_key`).

   * Với `GET /api/v1/attachments/<id>/download`:

     * Nếu `scan_state != 'CLEAN'`: trả `409 FILE_NOT_READY`.

     * Kiểm tra tệp đang được liên kết hợp lệ trong `revision_attachment`, `execution_attachment`, hoặc `draft_attachment` (nếu là `draft_attachment` thì chỉ `requester_id` mới được tải).

     * Bổ sung hàm `get_private_object(key: str) -> bytes` trong `api_core/storage.py` để tải byte từ Supabase Private Storage (nếu lỗi kết nối trả `503 STORAGE_UNAVAILABLE`).

     * Ghi `_append_request_audit` (`action="ATTACHMENT_DOWNLOADED"`, `target_type="attachment"`, `target_id=attachment_id`).

     * Trả `HttpResponse(data, content_type=mime)` với header `Content-Disposition: attachment; filename="<original_name>"`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Correlation-ID`.

### TASK 3: Triển khai Module Điều Phối `OPS_ADMIN` (`api_core/workflow/ops_service.py` — `UC09`, `UC14`, `AD-05`, `SD-07`, `SD-22`)

Tạo file `api_core/workflow/ops_service.py` để xử lý 3 nghiệp vụ đặc quyền của `OPS_ADMIN`:

1. **`GET /api/v1/ops/requests` (`list_ops_metadata` — `TC024`)**:

   * Yêu cầu role `OPS_ADMIN`.

   * Chỉ lọc các request mà `OPS_ADMIN` có `role_membership` hợp lệ (`scope_kind = 'GLOBAL'` hoặc `department_id = COALESCE(v.department_id, u.department_id)`, và `type_scope = 'ALL'` hoặc `type_id = r.type_id`).

   * **Chỉ trả các trường metadata điều phối được whitelist trong `01_SRS_v2.docx` mục 3**:
     `id`, `code`, `type_code`, `status`, `lock_version`, `department_id`, `active_step` (`id`, `step_no`, `assignee_id`), `current_attempt` (`id`, `attempt_no`, `executor_id`, `state`), `acceptor_id`, `planned_executor_id`, `sla` (`id`, `kind`, `started_at`, `due_at`, `breached_at`), `updated_at`.

   * **CẤM** trả `title`, `payload`, `draft_payload`, `amount_vnd`, `draft_amount_vnd`, `reason`, `result_note`, hay tên tệp!

2. **`POST /api/v1/requests/<uuid:request_id>/reassign` (`reassign_actor` — `UC09`, `SD-07`, `SD-22`, `TC039–041`, `TC046`, `TC055`, `TC057`)**:

   * Yêu cầu role `OPS_ADMIN` và `Idempotency-Key`.

   * Body gồm: `expected_version` (int), `target_kind` (`"APPROVAL_STEP"`, `"EXECUTOR"`, `"ACCEPTOR"`, `"PLANNED_EXECUTOR"`), `target_id` (UUID string của step/attempt/instance), `new_user_id` (UUID string), `reason` (string 10..2000 ký tự).

   * Trong transaction (`_execute_idempotent`):

     * `SELECT eas.lock_security(false)`

     * Khóa `eas.request r`, `eas.request_revision v`, `eas.workflow_instance i` (`FOR UPDATE OF r, i`).

     * Kiểm tra `OPS_ADMIN` có quyền đúng `v.department_id` và `r.type_id`.

     * Kiểm tra `r.lock_version == expected_version` (sai trả `409 VERSION_CONFLICT`).

     * Kiểm tra `new_user_id` đang `is_active = TRUE` trong `eas.app_user`.

     * Xử lý theo `target_kind`:

       * **Trường hợp `"APPROVAL_STEP"`**:

         * Khóa `eas.approval_step` (`WHERE id = %s AND instance_id = %s FOR UPDATE`).

         * Nếu step không ở trạng thái `ACTIVE` hoặc `WAITING`, hoặc đã có dòng trong `eas.approval_decision`: raise `CommandError("TARGET_IMMUTABLE", status=409)`.

         * Kiểm tra `new_user_id` có role `APPROVER` hợp lệ cho `(v.department_id, r.type_id)`.

         * Kiểm tra **Separation of Duties (SoD)** toàn tuyến (`BR02`, `TC040`): `new_user_id != r.requester_id`, `new_user_id` không trùng với bất kỳ `assignee_id` nào khác trong cùng `instance_id` (kể cả step đã `APPROVED` hay đang `WAITING`), và `new_user_id != i.planned_executor_id` (cũng như `executor_id` hiện hành). Nếu vi phạm, raise `CommandError("ASSIGNEE_INVALID", status=422)`.

         * UPDATE `eas.approval_step SET assignee_id = %s WHERE id = %s`. Giữ nguyên `eas.sla_stage` (không reset `due_at` — `TC039`).

       * **Trường hợp `"EXECUTOR"`**:

         * Khóa `eas.execution_attempt a` (`WHERE id = %s AND instance_id = %s FOR UPDATE`).

         * Nếu `a.state` không thuộc `('READY', 'RUNNING')` hoặc `r.status` không thuộc `('READY_FOR_EXECUTION', 'IN_PROGRESS')`: raise `CommandError("TARGET_IMMUTABLE", status=409)`.

         * Kiểm tra `new_user_id` có role `EXECUTOR` hợp lệ cho `(v.department_id, r.type_id)`.

         * Kiểm tra SoD: `new_user_id != r.requester_id`, `new_user_id` không nằm trong tập người đã/đang duyệt của `instance_id`, và `new_user_id != i.acceptor_id`. Nếu vi phạm, raise `CommandError("ASSIGNEE_INVALID", status=422)`.

         * Nếu `a.state == 'READY'`:
           UPDATE `eas.execution_attempt SET executor_id = %s WHERE id = %s` và UPDATE `eas.workflow_instance SET planned_executor_id = %s WHERE id = %s`. Giữ nguyên `sla_stage` và `r.status = 'READY_FOR_EXECUTION'`.

         * Nếu `a.state == 'RUNNING'` (`SD-07`, `TC046`):

           1. Đóng attempt cũ:

              ```
              UPDATE eas.execution_attempt
              SET state = 'FINISHED', closure_kind = 'REASSIGNED', closed_at = %s
              WHERE id = %s
              
              ```

           2. Tạo attempt mới `new_attempt_id = str(uuid4())`:

              ```
              INSERT INTO eas.execution_attempt(id, request_id, instance_id, attempt_no, executor_id, state)
              VALUES (%s, %s, %s, %s, %s, 'READY')
              
              ```

           3. Cập nhật `planned_executor_id` trên `workflow_instance` và chuyển `sla_stage` đang mở sang `new_attempt_id` (giữ nguyên `started_at` và `due_at` — thỏa mãn trigger `eas.guard_sla()`!):

              ```
              UPDATE eas.workflow_instance SET planned_executor_id = %s WHERE id = %s;
              UPDATE eas.sla_stage SET attempt_id = %s WHERE request_id = %s AND closed_at IS NULL;
              
              ```

           4. Đặt `next_status = 'READY_FOR_EXECUTION'`.

       * **Trường hợp `"ACCEPTOR"`**:

         * Chỉ áp dụng cho `i.lifecycle == 'C'` và `r.status IN ('PENDING_APPROVAL', 'READY_FOR_EXECUTION', 'IN_PROGRESS', 'WAITING_FOR_ACCEPTANCE')` khi chưa có `acceptance_decision` cho attempt hiện hành.

         * Kiểm tra `new_user_id` có role `ACCEPTOR` hợp lệ cho `(v.department_id, r.type_id)`, và `new_user_id` khác `i.planned_executor_id` cũng như khác `executor_id` của attempt hiện hành. Nếu sai raise `CommandError("ASSIGNEE_INVALID", status=422)`.

         * UPDATE `eas.workflow_instance SET acceptor_id = %s WHERE id = %s`.

       * **Trường hợp `"PLANNED_EXECUTOR"`**:

         * Dùng khi `r.status == 'WAITING_FOR_ACCEPTANCE'` (attempt hiện tại đang `SUBMITTED` và bất biến, nhưng `planned_executor_id` bị khóa trước khi Acceptor bấm `REWORK` — `TC055`, `SD-22`).

         * Kiểm tra `new_user_id` có role `EXECUTOR` hợp lệ và thỏa SoD (khác requester, khác approvers, khác acceptor).

         * UPDATE `eas.workflow_instance SET planned_executor_id = %s WHERE id = %s` (không sửa `executor_id` của attempt `SUBMITTED`).

     * Thêm `new_user_id` vào `eas.request_participant` (`ON CONFLICT (request_id, user_id) DO NOTHING`).

     * UPDATE `eas.request SET status = %s, lock_version = lock_version + 1, updated_at = %s WHERE id = %s`.

     * Ghi cả `_append_request_audit` (`action="ACTOR_REASSIGNED"`) VÀ `_append_admin_audit` (`action="ACTOR_REASSIGNED"`, `reason=reason`, `details={"target_kind": target_kind, "old_user_id": old_user_id, "new_user_id": new_user_id}`).

     * INSERT `eas.outbox_event` (`event_type="ACTOR_REASSIGNED"`).

3. **`POST /api/v1/ops/outbox/<uuid:event_id>/replay` (`replay_dead_outbox` — `UC14`, `SD-08`, `TC067`)**:

   * Yêu cầu role `OPS_ADMIN` và `Idempotency-Key`.

   * Body gồm: `reason` (string 10..2000 ký tự).

   * Trong transaction:

     * `SELECT eas.lock_security(false)`

     * Khóa `eas.outbox_event` (`WHERE id = %s FOR UPDATE`). Nếu không tồn tại trả `404 NOT_FOUND`.

     * Nếu `state != 'DEAD'`: raise `CommandError("EVENT_NOT_DEAD", status=409)`.

     * UPDATE `eas.outbox_event SET state = 'PENDING', attempts = 0, replay_count = replay_count + 1, available_at = %s, lease_token = NULL, lease_until = NULL, last_error_code = NULL WHERE id = %s`.

     * Ghi `eas.admin_event` (`action="OUTBOX_REPLAYED"`, `target_type="outbox_event"`, `target_id=event_id`, `reason=reason`).

### TASK 4: Triển khai Module Quản Trị Cấu Hình `config_release` (`api_core/workflow/config_service.py` — `UC02`, `AD-07`, `SD-09`, `TC010–012`, `TC097`)

Tạo file `api_core/workflow/config_service.py` cho role `POLICY_ADMIN`:

1. **`GET /api/v1/config-releases` & `GET /api/v1/config-releases/<uuid:release_id>`**:

   * Kiểm tra `POLICY_ADMIN` có quyền trên `type_id`. Trả danh sách hoặc chi tiết `config_release` (`id`, `type_code`, `version`, `state`, `lifecycle`, `form_schema`, `route_rules`, `actor_bindings`, `sla_profile`, `lock_version`, `content_sha256`, `created_at`, `published_at`).

2. **`POST /api/v1/config-releases` (`create_or_clone_release`)**:

   * Body: `{"type_code": "LEAVE|ACCESS|EQUIPMENT", "clone_from_release_id": "<uuid optional>"}` + `Idempotency-Key`.

   * Kiểm tra `POLICY_ADMIN` có scope cho `type_id`.

   * Lấy `next_version = COALESCE(MAX(version), 0) + 1` của `type_id`.

   * Nếu có `clone_from_release_id` (hoặc lấy `active_release_id` hiện tại của `request_type`): sao chép `form_schema`, `route_rules`, `actor_bindings`, `sla_profile` sang bản ghi mới với `state = 'DRAFT'`, `lock_version = 0`.

   * Ghi `eas.admin_event` (`action="CONFIG_DRAFT_CREATED"`).

3. **`PATCH /api/v1/config-releases/<uuid:release_id>` (`update_draft_release` — `TC011`)**:

   * Body: `expected_version` (int), `form_schema`, `route_rules`, `actor_bindings`, `sla_profile` + `Idempotency-Key`.

   * Khóa `eas.config_release` (`FOR UPDATE`).

   * Nếu `state == 'PUBLISHED'`: trả `409 RELEASE_IMMUTABLE` (`TC011`).

   * Nếu `lock_version != expected_version`: trả `409 VERSION_CONFLICT`.

   * Kiểm tra sơ bộ cấu trúc JSON (`validate_config_release_structure`), UPDATE bản ghi `DRAFT` và tăng `lock_version = lock_version + 1`.

4. **`POST /api/v1/config-releases/<uuid:release_id>/validate` (`validate_release_candidate` — `TC012`)**:

   * Kiểm tra toàn diện 4 JSON (`form_schema`, `route_rules`, `actor_bindings`, `sla_profile`) theo đúng các điều kiện trong trigger `eas.guard_release()` VÀ `api_core/domain/`:

     * Cả 4 JSON đều có `"schema_version": 1`.

     * `form_schema`: `type == "object"`, `additionalProperties is False`, `properties` hợp lệ, `required` là tập con của `properties`.

     * `route_rules`: có đúng 1 rule `"default": True` nằm ở cuối mảng `rules`; các rule có điều kiện phải có `priority` nguyên dương duy nhất, `when` chỉ chứa `amount_gt` / `amount_gte` với giá trị nguyên VND `0..1_000_000_000_000`; `approvers` dài 1..3 chỉ thuộc `{"DIRECT_MANAGER", "FINANCE", "DIRECTOR"}`; `id` duy nhất; `executor`/`acceptor` khớp đúng `lifecycle` (`A`: cả hai `None`; `B`: `EXECUTOR_IT` và `None`; `C`: `EXECUTOR_ASSET` và `REQUESTER`).

     * `sla_profile`: `clock == "CALENDAR_UTC"`, `reminder_fraction == 0.5`, `approval_hours` / `execution_hours` / `acceptance_hours` trong khoảng `1..720` hoặc `None` khớp với `lifecycle`.

   * Nếu có bất kỳ lỗi nào: trả `422 CONFIG_INVALID` kèm danh sách `fields`/`errors` (`TC012`).

   * Nếu hợp lệ: tính `validation_hash = canonical_sha256({"actor_bindings": actor_bindings, "form_schema": form_schema, "lifecycle": lifecycle, "route_rules": route_rules, "sla_profile": sla_profile, "type_code": type_code, "version": version})` (khớp chính xác cấu trúc `canonical_content` trong `database/EAS_Supabase_SQL/demo_canonical_hash_vectors.json`!) và trả `200 {"valid": True, "validation_hash": validation_hash, "lock_version": lock_version}`.

5. **`POST /api/v1/config-releases/<uuid:release_id>/publish` (`publish_config_release` — `TC010`, `TC097`)**:

   * Body: `expected_version` (int), `validation_hash` (str, tùy chọn nhưng nếu truyền phải khớp `content_sha256`), `reason` (str tùy chọn, mặc định `"Published configuration release."`) + `Idempotency-Key`.

   * Trong transaction:

     * `SELECT eas.lock_security(false)`

     * Khóa `eas.request_type rt` (`FOR UPDATE`) rồi khóa `eas.config_release cr` (`FOR UPDATE`).

     * Kiểm tra `cr.state == 'DRAFT'` (nếu đã `PUBLISHED` trả `409 RELEASE_IMMUTABLE`), `cr.lock_version == expected_version` (nếu lệch trả `409 VERSION_CONFLICT`).

     * Chạy lại validation đầy đủ; tính `content_sha256`. Nếu `validation_hash` được truyền mà khác `content_sha256`, trả `409 VALIDATION_STALE`.

     * UPDATE `eas.config_release SET state = 'PUBLISHED', published_by = %s, published_at = %s, content_sha256 = %s, lock_version = lock_version + 1 WHERE id = %s`.

     * UPDATE `eas.request_type SET active_release_id = %s WHERE id = %s`.

     * Ghi `eas.admin_event` (`action="CONFIG_RELEASE_PUBLISHED"`, `target_type="config_release"`, `target_id=release_id`, `type_id=type_id`, `details={"release_id": release_id, "content_sha256": content_sha256}`).

### TASK 5: Hoàn thiện Worker, Notifications, Báo Cáo & Audit Verification (`api_core/worker.py`, `api_core/workflow/reporting.py` — `UC13`, `UC14`, `UC15`)

1. **Nâng cấp `api_core/worker.py` (`UC14`, `SD-08`, `TC061–070`)**:

   * Trong `acknowledge_outbox(item: OutboxItem)`:

     * Kiểm tra từng `recipient_id` trước khi INSERT vào `eas.notification`:
       Người nhận phải đang `is_active = TRUE` trong `eas.app_user`, và nếu `item.request_id` khác `None` thì người nhận không bị thu hồi quyền đọc (`read_revoked_at IS NULL` trên `eas.request_participant`).

     * Nếu người nhận đã bị disable hoặc bị thu hồi quyền đọc (`TC069`): **không** INSERT vào `eas.notification`, mà ghi một bản ghi `eas.admin_event` (`actor_kind='SYSTEM'`, `action='NOTIFICATION_SKIPPED_INACTIVE_OR_REVOKED'`, `target_type='outbox_event'`, `target_id=item.id`, `reason='Recipient is inactive or read access was revoked.'`), sau đó vẫn cập nhật `eas.outbox_event SET state = 'SENT', sent_at = statement_timestamp()...` để hoàn tất gói tin an toàn!

   * Trong `process_sla_batch`:

     * Khi phát sinh `REMINDER` hoặc `BREACH`, ngoài việc INSERT vào `eas.sla_alert` và `eas.outbox_event`, ghi thêm bản ghi `eas.audit_event` (`actor_id=None`, `actor_kind='SYSTEM'`, `action=f'SLA_{kind}'`, `target_type='sla_stage'`, `target_id=stage_id`) để đảm bảo truy vết đầy đủ theo `AD-06` và `SD-08`.

2. **Triển khai Endpoints Thông báo (`UC13`, `SD-15`, `TC068`) trong `api_core/workflow/reporting.py`**:

   * `GET /api/v1/notifications`: chỉ lấy thông báo có `recipient_id = request.actor.id` (hỗ trợ `unread=true`, `limit`, `cursor`/`offset`), sắp xếp `created_at DESC, id DESC`.

   * `PATCH /api/v1/notifications/<uuid:notification_id>` (hoặc `POST .../read`):

     * Kiểm tra `recipient_id = request.actor.id` (nếu không tồn tại hoặc của người khác trả `404 NOT_FOUND`).

     * Cập nhật `read_at = COALESCE(read_at, statement_timestamp())` (chỉ cập nhật khi `read_at IS NULL` để không vi phạm trigger `eas.guard_notification()`, trả lại cùng giá trị `read_at` cho mọi lần gọi lặp lại).

3. **Triển khai Báo cáo theo Scope & Mẫu số (`GET /api/v1/reports/requests` — `UC15`, `SD-16`, `TC093`)**:

   * Tham số lọc: `type_code`, `department_id`, `created_from`, `created_to` (kiểm tra khoảng thời gian tối đa 366 ngày; nếu `created_to <= created_from` hoặc quá 366 ngày trả `422 PERIOD_INVALID`).

   * Áp dụng đúng predicate quyền đọc của `request.actor` trước khi aggregate (`r.status != 'DRAFT'`).

   * Đếm trên `DISTINCT r.id` (không đếm số revision):

     * `submitted`: tổng số request đã gửi (`r.current_revision_id IS NOT NULL`).

     * `approved`: số request có `r.approved_at IS NOT NULL`.

     * `completed`: số request có `r.status = 'COMPLETED'`.

     * `by_status`: dict đếm theo từng `status`.

     * `approved_rate`: `round(approved / submitted, 4)` nếu `submitted > 0` else `None`.

     * `completed_rate`: `round(completed / submitted, 4)` nếu `submitted > 0` else `None`.

4. **Triển khai Tra cứu & Xác minh Audit (`UC15`, `SD-13`, `TC096`)**:

   * `GET /api/v1/requests/<uuid:request_id>/audit`: kiểm tra quyền đọc đầy đủ (ngoài quyền trả `404`), trả danh sách `eas.audit_event` theo `seq ASC`.

   * `GET /api/v1/admin-events`: yêu cầu role `AUDITOR`, `POLICY_ADMIN`, hoặc `OPS_ADMIN` (lọc theo scope `department_id` / `type_id` tương ứng), trả danh sách `eas.admin_event` theo `seq DESC`.

   * `GET /api/v1/requests/<uuid:request_id>/audit/verify` (và hàm dùng chung `verify_audit_chain(scope_key: str)`):

     * Yêu cầu role `AUDITOR` đúng scope.

     * Đọc toàn bộ sự kiện của `scope_key` (`REQ:<uuid>` từ `eas.audit_event` hoặc `ADMIN` từ `eas.admin_event`) theo `seq ASC` cùng `eas.audit_head`.

     * Kiểm tra liên tục `seq == 1..N`, `prev_hash` của `seq=1` là `'0'*64`, `prev_hash` của `seq=k` bằng `hash` của `seq=k-1`, và tính lại `canonical_sha256(event_payload)` của từng sự kiện so với cột `hash`.

     * Kiểm tra khớp với `eas.audit_head` và `eas.audit_checkpoint` (nếu có). Trả `{"status": "PASS" | "FAIL" | "UNKNOWN", "checked_seq": max_seq, "head_hash": last_hash}`.

### TASK 6: Triển khai 4 Management Commands Quản Trị (`api_core/management/commands/` — `UC17`, `SD-11`, `SD-14`, Tài liệu 03 Mục 11)

1. **`identity_import.py` (`python manage.py identity_import --manifest PATH [--dry-run | --apply --operator USER --approval REF]` — `TC007–009`)**:

   * Đọc file JSON/CSV manifest chứa `departments`, `users`, `roles`.

   * Kiểm tra: mã phòng/username không rỗng, không trùng; FK tồn tại; không có chu kỳ `department.parent_id` hoặc `app_user.manager_id` (`TC008`); `role_membership` có `scope_kind = 'GLOBAL'` iff `department_id IS NULL`, `type_scope = 'ALL'` iff `type_id IS NULL` (`TC009`).

   * Nếu có bất kỳ lỗi nào: in báo cáo lỗi theo dòng và thoát với mã `sys.exit(2)` (`exit 2`), không ghi một phần dữ liệu.

   * Nếu `--dry-run`: in kế hoạch `create`/`update`/`disable` kèm `manifest_sha256` và thoát `0` mà không sửa DB.

   * Nếu `--apply`: mở 1 `transaction.atomic()`, gọi `SELECT eas.lock_security(true)`, áp dụng thay đổi, tăng `eas.security_epoch.version` đúng 1 lần, ghi `eas.admin_event` kèm `manifest_sha256` và `approval_ref`, xóa session cache của các user bị ảnh hưởng.

2. **`account_reset.py` (`python manage.py account_reset --user USERNAME --mode [disable|enable|reset-password] --operator USER --approval REF` — `TC005–006`)**:

   * Trong `transaction.atomic()`, gọi `SELECT eas.lock_security(true)`, khóa `eas.app_user FOR UPDATE`.

   * Tăng `auth_version = auth_version + 1`, cập nhật `is_active` hoặc `password_hash` (đọc mật khẩu tạm từ biến môi trường `EAS_TEMP_PASSWORD`, không nhận qua CLI flag để tránh lộ trên process list) + `must_change_password = True`.

   * Tăng `eas.security_epoch.version + 1`, ghi `eas.admin_event`.

3. **`audit_verify.py` (`python manage.py audit_verify --scope SCOPE [--checkpoint REF]` — `TC096`)**:

   * Gọi hàm `verify_audit_chain(scope_key)` và in kết quả JSON; trả exit code `0` nếu `PASS`, `2` nếu `FAIL`/`UNKNOWN`.

4. **`privacy_case.py` (`python manage.py privacy_case --case CASE_ID --action [dry-run|approve|reject|execute-erase] --approval REF` — `TC083–085`)**:

   * Kiểm tra `eas.privacy_case` và `eas.retention_hold` (nếu có legal hold đang mở `released_at IS NULL` thì từ chối với mã `BLOCKED_BY_HOLD` — `TC084`).

### TASK 7: Bảng Ánh Xạ Toàn Bộ URL Routes (`api_core/config/urls.py` & `api_core/workflow/urls.py`)

Đảm bảo tất cả các route dưới đây đều hoạt động và được mount dưới `/api/v1/` (cùng `/health/`):

| Nhóm | Route hiện có (Giữ nguyên cho `web_client` & 67 tests) | Route bổ sung / Alias chuẩn `03_Du_lieu_va_API_v2.docx` | Handler / Quyền | 
| ----- | ----- | ----- | ----- | 
| **Health** | `GET /health/live`  `GET /health/ready` | — | `health.views.live`, `ready` | 
| **Auth** | `GET /api/v1/auth/csrf`  `POST /api/v1/auth/login`  `POST /api/v1/auth/logout`  `GET /api/v1/auth/me`  `POST /api/v1/auth/password` | `POST /api/v1/auth/change-password`  `GET /api/v1/me` | `authn.views.*` (cho phép cả `current_password`/`old_password`) | 
| **Catalog** | `GET /api/v1/meta/request-types` | `GET /api/v1/request-types` | `catalog.views.request_types` | 
| **Draft & Submit** | `POST /api/v1/request-drafts`  `POST /api/v1/requests/submit` | `POST /api/v1/requests` (khi `method == POST`)  `PATCH /api/v1/requests/<uuid:request_id>`  `PATCH /api/v1/request-drafts/<uuid:request_id>`  `POST /api/v1/requests/<uuid:request_id>/submit` | `REQUESTER` + `Idempotency-Key` | 
| **Query & Revisions** | `GET /api/v1/requests`  `GET /api/v1/requests/<uuid:request_id>` | `GET /api/v1/requests/<uuid:request_id>/revisions`  `GET /api/v1/requests/<uuid:request_id>/revisions/<uuid:revision_id>` | Predicate quyền đọc chống IDOR (`404`) | 
| **Attachments** | `POST /api/v1/request-drafts/<uuid:request_id>/attachments`  `POST /api/v1/requests/<uuid:request_id>/execution/attachments` | `POST /api/v1/requests/<uuid:request_id>/attachments`  `GET /api/v1/attachments/<uuid:attachment_id>`  `GET /api/v1/attachments/<uuid:attachment_id>/download` | `REQUESTER` / `EXECUTOR` / Quyền đọc tệp `CLEAN` | 
| **Approval & Cancel** | `POST /api/v1/requests/<uuid:request_id>/approval-decisions`  `POST /api/v1/requests/<uuid:request_id>/cancel` | `POST /api/v1/requests/<uuid:request_id>/decisions`  `POST /api/v1/requests/<uuid:request_id>/withdraw` | `APPROVER` / `REQUESTER` + `Idempotency-Key` | 
| **Execution & Acceptance** | `POST /api/v1/requests/<uuid:request_id>/execution/start`  `POST /api/v1/requests/<uuid:request_id>/execution/submit`  `POST /api/v1/requests/<uuid:request_id>/acceptance-decisions` | `POST /api/v1/requests/<uuid:request_id>/claim`  `POST /api/v1/requests/<uuid:request_id>/issues`  `POST /api/v1/requests/<uuid:request_id>/execution/issues`  `POST /api/v1/requests/<uuid:request_id>/execution`  `POST /api/v1/requests/<uuid:request_id>/acceptance` | `EXECUTOR` / `ACCEPTOR` + `Idempotency-Key` | 
| **OPS Admin** | — | `GET /api/v1/ops/requests`  `POST /api/v1/requests/<uuid:request_id>/reassign`  `POST /api/v1/ops/outbox/<uuid:event_id>/replay` | `OPS_ADMIN` | 
| **Config Release** | — | `GET /api/v1/config-releases`  `POST /api/v1/config-releases`  `GET /api/v1/config-releases/<uuid:release_id>`  `PATCH /api/v1/config-releases/<uuid:release_id>`  `POST /api/v1/config-releases/<uuid:release_id>/validate`  `POST /api/v1/config-releases/<uuid:release_id>/publish` | `POLICY_ADMIN` | 
| **Notifications, Reports & Audit** | — | `GET /api/v1/notifications`  `PATCH /api/v1/notifications/<uuid:notification_id>`  `GET /api/v1/reports/requests`  `GET /api/v1/requests/<uuid:request_id>/audit`  `GET /api/v1/requests/<uuid:request_id>/audit/verify`  `GET /api/v1/admin-events` | Recipient / Scoped Reader / `AUDITOR` | 
| **Mock Sources** | `GET /api/v1/mock/<17 routes>` | — | `mock_sources.views.resource_list` | 

### TASK 8: Kiểm Thử Tự Động & Quality Gates Trước Khi Hoàn Tất (`api_core/tests/` & CI)

Sau khi hoàn thành code, bạn bắt buộc viết đầy đủ unit/contract tests trong `api_core/tests/test_ops_and_config.py` và `api_core/tests/test_reporting_and_cli.py`, sau đó chạy toàn bộ các lệnh kiểm tra chất lượng sau và đảm bảo **100% PASS**:

```
# 1. Kiểm tra ফরmat và lint bằng Ruff
ruff check api_core manage.py test_logger.py scripts
ruff format --check api_core manage.py test_logger.py scripts

# 2. Chạy toàn bộ unit & contract tests của Django (EAS_ENV=test)
EAS_ENV=test python manage.py test -v 2

# 3. Chạy bộ kiểm thử bảo mật Logger
python -m unittest -v test_logger.py

# 4. Kiểm tra biên dịch bytecode Python
python -m compileall -q api_core manage.py test_logger.py

# 5. Kiểm tra tính hợp lệ của các file .env.example
python scripts/validate_env.py --file .env.example --profile compose --allow-placeholders
python scripts/validate_env.py --file api_core/.env.example --profile api --allow-placeholders
python scripts/validate_env.py --file api_core/.env.worker.example --profile worker --allow-placeholders

# 6. Kiểm tra tính toàn vẹn của hệ thống tài liệu, 68 sơ đồ Mermaid, TC001-TC100 và RTM UC01-UC17
python scripts/validate_docs.py

```

Cuối cùng, cập nhật kết quả thực tế (số lượng test PASS, các file đã thêm/sửa, các gate còn phụ thuộc môi trường ngoài) vào `plans/active/2026-10-09_dual_review_remediation.md` và `changelogs/2026-10-09_enterprise_baseline_release.md` (hoặc tạo bản ghi mới theo ngày thực thi) đúng chuẩn trung thực của dự án.