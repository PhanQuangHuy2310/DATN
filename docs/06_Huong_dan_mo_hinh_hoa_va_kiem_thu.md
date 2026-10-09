# Hướng dẫn mô hình hóa và thiết kế kiểm thử EAS

**Mã tài liệu:** EAS-DOC-06
**Phiên bản:** 1.0
**Ngày:** 09/10/2026
**Chủ sở hữu:** BA/Tech Lead/QA Lead
**Trạng thái:** Baseline đề xuất, chờ KD01–KD08

## 1. Mục tiêu và nguyên tắc

Tài liệu này quy định cách tạo, đọc, review và duy trì use-case diagram, activity diagram, sequence diagram và test case cho EAS. Các sơ đồ chi tiết nằm trong thư mục `diagrams`; chiến lược kiểm thử và RTM nằm trong `testing`.

Nguyên tắc bắt buộc:

1. Mô tả đúng P0 trong DOCX v2 và schema v2.0.1; không đưa ý tưởng của `plan.md` vào luồng đang cam kết.
2. Mỗi sơ đồ có ID, mục tiêu, trigger, tiền/hậu điều kiện, nguồn truy vết và nhánh lỗi chính.
3. Mỗi command ghi dùng `expected_version` và `Idempotency-Key`; quyền và trạng thái phải được kiểm lại trong transaction.
4. Domain state, audit, outbox và idempotency phải cùng commit hoặc cùng rollback.
5. Mỗi transition có tối thiểu: happy path, sai quyền, sai trạng thái/version, replay idempotent và race test nếu có cạnh tranh.
6. Mermaid là nguồn version-control; hình xuất PNG/SVG chỉ là artefact trình bày.

## 2. Ranh giới và từ điển chuẩn

### 2.1 Actor

| Actor | Trách nhiệm | Không được phép suy diễn |
|---|---|---|
| REQUESTER | Tạo nháp, submit/resubmit, withdraw đúng trạng thái | Không tự duyệt |
| APPROVER | Quyết định step ACTIVE được gán | Không quyết định step khác hoặc hồ sơ ngoài scope |
| EXECUTOR | Claim, báo vướng, nộp kết quả attempt hiện hành | Không nghiệm thu kết quả của chính mình |
| ACCEPTOR | Accept/rework lifecycle C | Không thay đổi kết quả đã nộp |
| POLICY_ADMIN | Draft/validate/publish config release | Không mặc nhiên đọc nội dung request |
| OPS_ADMIN | Reassign, replay outbox có lý do | Không approve/reject thay nghiệp vụ |
| AUDITOR | Đọc đúng scope, verify audit/checkpoint/report | Không sửa log hoặc role |
| Scheduler/Worker | SLA scan, outbox lease/delivery | Không tạo quyết định nghiệp vụ |
| Identity operator | Import user/org/role qua command có kiểm soát | Không sửa DB tùy ý |

### 2.2 Trạng thái chuẩn

`DRAFT`, `NEEDS_INFO`, `PENDING_APPROVAL`, `READY_FOR_EXECUTION`, `IN_PROGRESS`, `WAITING_FOR_ACCEPTANCE`, `COMPLETED`, `REJECTED`, `CANCELLED`.

| Lifecycle | Sau duyệt cuối | Kết thúc |
|---|---|---|
| A — LEAVE | `COMPLETED` | Duyệt đủ |
| B — ACCESS | `READY_FOR_EXECUTION` | Executor nộp kết quả → `COMPLETED` |
| C — EQUIPMENT | `READY_FOR_EXECUTION` | Executor nộp → `WAITING_FOR_ACCEPTANCE`; accept → `COMPLETED`; rework → `READY_FOR_EXECUTION` |

### 2.3 Quy tắc nhất quán dùng trong mọi sơ đồ

- Chỉ một workflow instance `ACTIVE` và một approval step `ACTIVE` cho một request.
- 1–3 cấp duyệt tuần tự; requester không tự duyệt; một người không chiếm hai cấp.
- Revision, decision và kết quả đã nộp là bất biến; bổ sung tạo revision/instance mới.
- Scope phòng dùng snapshot và khớp đúng `department_id`; `NULL` không có nghĩa là toàn quyền.
- Người ngoài scope nhận `404` ở bề mặt đọc; hành động bị cấm nhận `403`.
- Lý do reject/needs-info/rework/withdraw dài 10–2000 ký tự.
- Tệp chỉ liên kết khi scan `CLEAN`, đúng request/uploader/quota; storage là private.
- SLA chỉ nhắc và ghi breach; không tự reassign hoặc bỏ cấp.
- Thông báo là eventual delivery; trạng thái nghiệp vụ đã commit không phụ thuộc việc notification đến ngay.

## 3. Cách vẽ use-case diagram

### 3.1 Khi nào dùng

Use-case diagram trả lời “ai có thể đạt mục tiêu nào qua EAS”. Nó không mô tả thứ tự API, transaction hoặc layout màn hình.

### 3.2 Quy trình vẽ

1. Vẽ boundary `Enterprise Approval System P0`.
2. Đặt actor người ở ngoài boundary; actor hệ thống như Scheduler/Worker cũng ở ngoài.
3. Dùng đúng tên mục tiêu `UC01`–`UC15`, `UC17`; không đặt tên theo nút UI.
4. Dùng `<<include>>` khi hành vi luôn xảy ra; `<<extend>>` chỉ khi nhánh tùy điều kiện.
5. Gắn note cho guard quan trọng: scope, SoD, active step, lifecycle.
6. Review ma trận actor–UC trước khi chốt hình.

### 3.3 Tiêu chí review

- Không có actor “Admin” chung chung; POLICY, OPS, AUDITOR và identity operator phải tách.
- Không có AI, ERP/HRM, mobile hoặc external rule engine trong P0.
- UC quản trị không ngầm mở quyền đọc request.
- UC05/UC15 thể hiện quyền đọc theo predicate, không theo việc màn hình có link.

Xem sơ đồ chuẩn tại [01_use_case.md](./diagrams/01_use_case.md).

## 4. Cách vẽ activity diagram

### 4.1 Khi nào dùng

Activity diagram trả lời “công việc đi qua các quyết định và trạng thái nào”. Dùng swimlane theo trách nhiệm, decision node có guard trong dấu `[]`, và kết thúc rõ cho mọi nhánh.

### 4.2 Quy trình vẽ

1. Ghi trigger và trạng thái đầu.
2. Chia lane theo Requester, API/Domain, Approver, Executor, Acceptor, OPS/Worker.
3. Mỗi action dùng động từ; mỗi decision phải có các guard loại trừ nhau.
4. Ghi state mới ngay sau transaction commit, không ngay sau click UI.
5. Vẽ rollback/error path cho route unresolved, stale version, assignee unavailable và invalid file.
6. Kết thúc bằng hậu điều kiện có thể kiểm thử.

### 4.3 Checklist

- Có đủ A/B/C và nhánh reject/needs-info/withdraw/rework.
- Không nối `NEEDS_INFO` trở lại instance cũ; resubmit tạo revision và route mới.
- Reassign executor `RUNNING` kết thúc attempt cũ là `REASSIGNED`, tạo attempt `READY`, giữ SLA identity/deadline.
- Rework tạo attempt mới và SLA execution mới; người thực hiện phải claim lại.
- Scheduler không đổi domain state.

Xem [02_activity.md](./diagrams/02_activity.md).

## 5. Cách vẽ sequence diagram

### 5.1 Participant chuẩn

Chỉ đưa participant có trao đổi trong kịch bản: `Actor`, `Web`, `API`, `Authorization/Domain`, `PostgreSQL`, `Private Storage/Scanner`, `Scheduler`, `Outbox Worker`. EAS P0 là modular monolith Django; “Workflow Engine”, “Audit Service” hoặc “Notification Service” nên biểu diễn là module nội bộ, không giả thành microservice.

### 5.2 Quy ước Mermaid

- `alt/else/end`: nhánh loại trừ; `opt`: nhánh tùy chọn; `loop`: retry hữu hạn; `par`: chỉ dùng khi thực sự song song.
- `rect rgb(...)`: ranh giới transaction. Ghi `COMMIT`/`ROLLBACK` rõ.
- Mũi tên liền cho call đồng bộ, nét đứt cho response/event bất đồng bộ.
- Ghi lock order ở note: security → request → current target → idempotency/audit head.
- Không mô tả UI nhận thành công trước commit.

### 5.3 Thông tin tối thiểu của command sequence

Mỗi lệnh ghi phải thể hiện:

1. session/CSRF/rate limit khi áp dụng;
2. `Idempotency-Key`, payload hash, `expected_version`;
3. authorization + scope + state guard sau khi khóa;
4. domain write + audit + outbox + idempotency trong một transaction;
5. response từ kết quả đã commit hoặc replay;
6. notification xử lý sau commit, có lease/dedupe/retry/dead-letter.

Xem [03_sequence.md](./diagrams/03_sequence.md).

Các state machine dùng để khóa transition nằm tại [04_state_machine.md](./diagrams/04_state_machine.md); kiến trúc, DFD, deployment và ERD nằm tại [05_architecture_and_data.md](./diagrams/05_architecture_and_data.md).

## 6. Cách thiết kế test case

### 6.1 Mẫu bắt buộc

| Trường | Nội dung |
|---|---|
| ID/Tên | ID bất biến và hành vi cần chứng minh |
| Trace | SRC/FR/AC/BR/UC/NFR/API/entity/diagram transition |
| Risk/Priority | Risk ID, Critical/High/Medium/Low, P0/P1/P2 |
| Level/Type | Unit, DB, API, integration, E2E, security, performance, DR, UAT |
| Preconditions | Release, actor/scope, state, clock, dependency health |
| Data | Fixture IDs và giá trị biên; không dùng dữ liệu thật |
| Steps | Hành động tái lập được, không phụ thuộc ca trước |
| Expected | HTTP/error, state, version, rows, audit/outbox/idempotency, side effect |
| Cleanup | Cách cô lập/reset, storage prefix, clock |
| Execution | Commit/image/config/DB version, môi trường, tester/time |
| Actual/Evidence | Kết quả từng bước, correlation/query/screenshot/log đã che bí mật |
| Status/Defect | NOT RUN/PASS/FAIL/BLOCKED và defect ID |

### 6.2 Kỹ thuật thiết kế

- Decision table: lifecycle × amount boundary × route × actor validity.
- Boundary value: `9,999,999`, `10,000,000`, `50,000,000`, `50,000,001` VND; 9/10/2000/2001 ký tự; 5/6 file; 10 MiB và quota 200 MiB.
- State transition: mỗi cạnh hợp lệ và mọi cạnh bị cấm.
- Pairwise: role × department scope × request type × endpoint.
- Concurrency: hai connection đồng bộ bằng barrier; không dùng `sleep` để đoán race.
- Fault injection: DB/audit/outbox/storage/scanner/worker failure ở từng commit boundary.
- Property-based: rule JSON allowlist, deterministic route, canonical hash, depth/size limit.
- Security abuse case: IDOR, CSRF, session fixation, mass assignment, stored XSS, injection, path traversal, malware.

### 6.3 Oracle cho một command thành công

Không chỉ assert HTTP 2xx. Cần kiểm đồng thời:

- request state/version và current relation;
- đúng một domain record mới, không duplicate;
- audit actor/correlation/before-after/sequence/previous hash;
- outbox event/dedupe key;
- idempotency result/payload hash;
- không có ghi chéo request hoặc lộ dữ liệu;
- replay cùng key trả cùng kết quả; key cùng nhưng payload khác trả conflict.

### 6.4 Trạng thái và bằng chứng

`PASS` chỉ hợp lệ khi actual result khớp expected và evidence đọc được. `BLOCKED` phải có blocker/owner/ETA. Không đổi `FAIL` thành `PASS` bằng waiver. Không đính token, password, cookie, nội dung cá nhân hoặc secret vào log/evidence.

Chi tiết tại [01_test_case_and_rtm.md](./testing/01_test_case_and_rtm.md).

## 7. Traceability và quản lý thay đổi

Chuỗi truy vết chuẩn:

```text
SRC → KD → FR/NFR/BR → AC → UC → Activity/Sequence transition
    → API + entity/invariant → TC → execution/evidence → defect/acceptance
```

Definition of Done cho thay đổi workflow:

- quyết định/scope đã có owner phê duyệt;
- state/event/API/schema và sơ đồ cùng version;
- mỗi nhánh mới có test dương, âm, quyền và race tương ứng;
- migration/rollback/runbook được cập nhật nếu cần;
- review BA + Tech Lead + QA + Security/Ops theo tác động;
- CI kiểm link, Mermaid syntax và test liên quan.

## 8. Chống nhầm baseline cũ

| Nội dung trong `plan.md` | Xử lý ở P0 |
|---|---|
| AI auto-approve/risk score/OCR | Loại khỏi P0; AI không được quyết định |
| AI summarize | FR21/P1, chỉ qua change request |
| OPA/Drools service | Không phải participant P0; route là rule JSON được kiểm tra trong domain |
| Mobile/biometric/push | FR20/P1 |
| ERP/HRM webhook | Ngoài hệ thống; thực hiện thủ công và lưu bằng chứng |
| Delegation/load balancer/auto-reassign | Thay bằng OPS reassign có lý do và audit |
| Parallel ANY/MAJORITY | Không dùng; chỉ 1–3 cấp tuần tự |
| General drag-drop builder | Thay bằng config release hữu hạn, schema allowlist |
| Digital signature | Không thuộc P0; audit hash không phải chữ ký số |

## 9. Quy trình review tài liệu

1. BA xác nhận actor, mục tiêu, business guard và thuật ngữ.
2. Tech Lead đối chiếu transaction, lock, invariant, API và failure mode.
3. DBA/Data Engineer đối chiếu FK/CHECK/unique/index/RLS và retention.
4. QA lập RTM, test oracle, boundary/race/fault và cổng nghiệm thu.
5. Security/Privacy review scope, SoD, file, audit và dữ liệu cá nhân.
6. Ops review worker, metric, retry, backup/restore và evidence.
7. PO ký các KD còn mở; chỉ sau đó baseline mới được gắn nhãn Approved.

Tiêu chuẩn hình/caption/review khi đưa vào đồ án được quy định tại [07_Tieu_chuan_chat_luong_so_do_DATN.md](./07_Tieu_chuan_chat_luong_so_do_DATN.md). PDF TinyTalk chỉ là benchmark về độ hoàn thiện, không quyết định cấu trúc hoặc nghiệp vụ EAS.
