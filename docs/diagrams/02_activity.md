# Activity diagrams — EAS P0

**Loại:** Target design P0 · **Nguồn:** SRS/SDD v2 + schema v2.0.1
Các activity dưới mô tả business flow. Chi tiết call/transaction nằm trong sequence diagrams.

## AD-01 — Vòng đời tổng thể A/B/C

```mermaid
flowchart TD
    S([Bắt đầu]) --> D[DRAFT]
    D -->|submit hợp lệ| P[PENDING_APPROVAL]
    D -->|withdraw| X[CANCELLED]
    P --> Q{Quyết định step ACTIVE}
    Q -->|NEEDS_INFO| N[NEEDS_INFO\ninstance SUPERSEDED]
    N -->|resubmit: revision + route mới| P
    N -->|withdraw| X
    Q -->|REJECT| R[REJECTED]
    Q -->|APPROVE chưa phải cấp cuối| P
    Q -->|APPROVE cấp cuối| L{Lifecycle}
    L -->|A / LEAVE| C[COMPLETED]
    L -->|B hoặc C| E[READY_FOR_EXECUTION]
    E -->|claim| I[IN_PROGRESS]
    I -->|submit result B| C
    I -->|submit result C| W[WAITING_FOR_ACCEPTANCE]
    I -->|OPS reassign RUNNING| E
    W -->|ACCEPT| C
    W -->|REWORK: attempt mới| E
    P -->|withdraw thắng race| X
    C --> Z([Kết thúc])
    R --> Z
    X --> Z
```

Không có cạnh rời trạng thái terminal. Không có `AUTO_APPROVED`, `EXECUTED` hay `EXECUTION_REJECTED`.

## AD-02 — Submit và resubmit

```mermaid
flowchart TD
    A([Requester chọn Submit]) --> B[API nhận key, payload hash, expected_version, viewed_release_id]
    B --> C{Session, CSRF, rate limit hợp lệ?}
    C -->|Không| E1[401 / 403 / 429; không ghi]
    C -->|Có| D[Khóa security, type, request theo thứ tự]
    D --> E{Owner/scope/state/version hợp lệ?}
    E -->|Không| E2[403/409; rollback]
    E -->|Có| F{Active release = viewed release?}
    F -->|Không| E3[409 CONFIG_CHANGED; giữ nháp]
    F -->|Có| G{Schema, amount, tệp CLEAN hợp lệ?}
    G -->|Không| E4[422/413/415; rollback]
    G -->|Có| H[Snapshot payload, department, release và attachment]
    H --> I[Resolve route 1–3 cấp tuần tự]
    I --> J{Actor active + role/scope + SoD?}
    J -->|Không| E5[422 ROUTE_UNRESOLVED / SOD_VIOLATION]
    J -->|Có| K[Create revision, instance, steps, participants, SLA]
    K --> L[Activate step 1]
    L --> M[Append audit + outbox + idempotency; tăng version]
    M --> N{Commit thành công?}
    N -->|Không| E6[Rollback toàn bộ; retry cùng key]
    N -->|Có| O[PENDING_APPROVAL]
    O --> P([Trả response đã commit])
```

## AD-03 — Quyết định duyệt

```mermaid
flowchart TD
    A([Approver gửi outcome]) --> B[Khóa request + current instance + ACTIVE step]
    B --> C{Đúng assignee, role/scope, state, version?}
    C -->|Không| X[403 hoặc 409; không ghi decision]
    C -->|Có| D{Outcome}
    D -->|REJECT| E{Reason 10–2000?}
    E -->|Không| X1[422 FIELD_INVALID]
    E -->|Có| R[Decision REJECT; request REJECTED]
    D -->|NEEDS_INFO| F{Reason 10–2000?}
    F -->|Không| X1
    F -->|Có| N[Decision NEEDS_INFO; instance SUPERSEDED; clone draft; request NEEDS_INFO]
    D -->|APPROVE| G{Actor kế tiếp / executor / acceptor còn hợp lệ?}
    G -->|Không| X2[409 ASSIGNEE_UNAVAILABLE]
    G -->|Có| H{Còn step?}
    H -->|Có| I[Step hiện tại APPROVED; activate step kế; PENDING_APPROVAL]
    H -->|Không| J{Lifecycle}
    J -->|A| K[COMPLETED]
    J -->|B/C| L[Create attempt READY; READY_FOR_EXECUTION]
    R --> M[Đóng SLA; audit + outbox + idempotency]
    N --> M
    I --> M
    K --> M
    L --> M
    M --> Z([Commit])
```

## AD-04 — Thực hiện và nghiệm thu

```mermaid
flowchart TD
    A[READY_FOR_EXECUTION / attempt READY] --> B{Executor action}
    B -->|Unable to claim| U[Ghi issue; giữ state và SLA]
    B -->|Claim| C[attempt RUNNING; request IN_PROGRESS]
    C --> D{Trong khi thực hiện}
    D -->|Blocked| V[Ghi issue; giữ IN_PROGRESS/SLA]
    V --> D
    D -->|OPS reassign| RR[Attempt cũ FINISHED/REASSIGNED; attempt mới READY; giữ deadline]
    RR --> A
    D -->|Submit result| E{Note + reference + 1–5 tệp CLEAN đúng uploader/request?}
    E -->|Không| X[422; giữ RUNNING]
    E -->|Có| F{Lifecycle}
    F -->|B| G[Attempt FINISHED/SUCCESS; request COMPLETED]
    F -->|C| H[Attempt SUBMITTED; request WAITING_FOR_ACCEPTANCE]
    H --> I{Acceptor khác executor quyết định}
    I -->|ACCEPT| J[Attempt FINISHED/ACCEPTED; COMPLETED]
    I -->|REWORK| K{Planned executor còn hợp lệ?}
    K -->|Không| Y[409; OPS đổi planned executor rồi retry]
    K -->|Có| L[Attempt cũ FINISHED/REWORK; tạo attempt READY; SLA execution mới]
    L --> A
    G --> Z([Kết thúc])
    J --> Z
```

## AD-05 — Reassign có kiểm soát

```mermaid
flowchart TD
    A([OPS chọn target + actor mới + reason]) --> B{OPS có scope type + department snapshot?}
    B -->|Không| X[403; không thay đổi]
    B -->|Có| C[Khóa request và target]
    C --> D{Target còn mutable?}
    D -->|Không| X1[409 TARGET_IMMUTABLE]
    D -->|Có| E{Actor mới active, role/scope và SoD hợp lệ?}
    E -->|Không| X2[422 ASSIGNEE_INVALID]
    E -->|Có| F{Target}
    F -->|ACTIVE/WAITING approval| G[Đổi assignee; giữ SLA]
    F -->|Executor READY| H[Đổi executor]
    F -->|Executor RUNNING| I[Kết thúc attempt REASSIGNED; tạo READY; giữ stage/deadline]
    F -->|Acceptor chưa quyết định| J[Đổi acceptor]
    F -->|Planned executor khi chờ accept| K[Chỉ đổi actor cho rework tương lai]
    G --> L[Add participant + admin/audit event + notification]
    H --> L
    I --> L
    J --> L
    K --> L
    L --> M([Commit; actor cũ mất quyền ghi])
```

## AD-06 — SLA, outbox và notification

```mermaid
flowchart TD
    A([Scheduler tick mỗi 60s]) --> B[Chọn stage ứng viên]
    B --> C[Khóa request rồi stage; kiểm current target]
    C --> D{Stage còn OPEN?}
    D -->|Không| S[Skip]
    D -->|Có| E{now so với due/50%}
    E -->|now >= due| F[Insert BREACH unique; breached_at = due_at]
    E -->|50% <= now < due| G[Insert REMINDER unique]
    E -->|chưa tới 50%| S
    F --> H[Audit + outbox cùng transaction]
    G --> H
    H --> I([Commit])
    I --> J[Worker poll mỗi 5s; claim lease 60s]
    J --> K{Lease token còn hợp lệ và recipient active?}
    K -->|Không| L[NACK/skip an toàn]
    K -->|Có| M[Create notification dedupe + ACK]
    M --> N{Delivery transaction thành công?}
    N -->|Có| O([DONE])
    N -->|Không| P{attempt < 4?}
    P -->|Có| Q[Retry sau 1/5/15 phút]
    Q --> J
    P -->|Không| R[DEAD + alarm OPS]
    R --> T[OPS replay có reason; giữ event ID/dedupe]
    T --> J
```

## Mapping sang kiểm thử

| Activity | Test trọng yếu |
|---|---|
| AD-01 | TC031–038, TC043–055, TC095, TC099 |
| AD-02 | TC013–030, TC033, TC056, TC094, TC097 |
| AD-03 | TC032–042, TC057–060 |
| AD-04 | TC043–055, TC064, TC070 |
| AD-05 | TC026, TC039–042, TC046, TC055, TC057 |
| AD-06 | TC061–070, TC082, TC087 |

## AD-07 — Soạn, validate và publish cấu hình

```mermaid
flowchart TD
    A([POLICY_ADMIN bắt đầu]) --> B[Clone active release thành DRAFT]
    B --> C[Sửa field trong allowlist: form, route, actor mapping, SLA]
    C --> D[Validate JSON schema, operator, priority, default và 1–3 slot]
    D --> E{Hợp lệ?}
    E -->|Không| F[Trả lỗi field/rule; giữ DRAFT]
    F --> C
    E -->|Có| G[Chạy bộ input biên và xem expected route]
    G --> H{Kết quả được POLICY_ADMIN xác nhận?}
    H -->|Không| C
    H -->|Có| I[Publish với expected_version + key]
    I --> J{Quyền/version/hash còn hợp lệ?}
    J -->|Không| K[403/409/422; rollback]
    J -->|Có| L[PUBLISHED bất biến + atomic active-release swap]
    L --> M[Admin event + outbox + idempotency]
    M --> N([Commit và lưu release ID/hash])
```

## AD-08 — Import danh tính, tổ chức và quyền

```mermaid
flowchart TD
    A([Operator nhận file đã được chủ dữ liệu duyệt]) --> B[Parse CSV và canonical file hash]
    B --> C[Validate code/FK/role/scope/date]
    C --> D[Kiểm cycle department và manager]
    D --> E{Có bất kỳ lỗi dòng nào?}
    E -->|Có| F[Dry-run report lỗi; không apply phần]
    E -->|Không| G[Dry-run report create/update/disable]
    G --> H{Operator xác nhận đúng file hash?}
    H -->|Không| I([Dừng])
    H -->|Có| J[BEGIN + lock security_epoch]
    J --> K[Apply toàn bộ user/department/role]
    K --> L[Tăng security_epoch; invalidate session liên quan]
    L --> M[Admin event cho từng thay đổi]
    M --> N{Commit thành công?}
    N -->|Không| O[Rollback toàn bộ]
    N -->|Có| P([Kết thúc và lưu evidence])
```

## AD-09 — Privacy case, legal hold và purge

```mermaid
flowchart TD
    A([Tiếp nhận yêu cầu chủ thể]) --> B[Xác minh danh tính và tạo privacy_case/due_at]
    B --> C[Data owner phân loại quyền, căn cứ, ngoại lệ]
    C --> D{Có legal hold hoặc nghĩa vụ giữ?}
    D -->|Có| E[RESTRICT / từ chối có căn cứ và decision reference]
    D -->|Không| F[Build manifest DB/object/log/backup/checkpoint]
    F --> G[Dry-run phạm vi và FK dependency]
    G --> H{Người thứ hai review và phê duyệt?}
    H -->|Không| I([Không thực thi])
    H -->|Có| J[Đóng ghi phạm vi; account đặc quyền thực thi]
    J --> K[Purge/redact theo thứ tự dependency trong transaction]
    K --> L[Admin evidence tối thiểu + suppression manifest]
    L --> M[Reconcile không còn nội dung bị xóa]
    M --> N[Cập nhật backup-retention handling]
    N --> O[Phản hồi chủ thể và đóng case]
    E --> O
```

## AD-10 — Go/No-Go, cutover và rollback

```mermaid
flowchart TD
    A([Release candidate]) --> B{G3 PASS và không S0/S1?}
    B -->|Không| X[NO-GO; sửa và regression]
    B -->|Có| C[UAT + restore/cutover rehearsal]
    C --> D{G4, KD06, KD08 và manifest đầy đủ?}
    D -->|Không| X
    D -->|Có| E[Maintenance ON; drain write ≤60s]
    E --> F[Stop scheduler/worker; consistent DB/object checkpoint]
    F --> G[Deploy image + expand-compatible migration]
    G --> H[Pre-open smoke + reconcile]
    H --> I{Đạt?}
    I -->|Không| R[Rollback image N-1 hoặc restore theo quyết định]
    R --> S[Reconcile dữ liệu sau restore; smoke lại]
    S --> T{An toàn để mở?}
    T -->|Không| X
    T -->|Có| J[Maintenance OFF]
    I -->|Có| J
    J --> K[Theo dõi 60 phút và chạy TC100]
    K --> L{G5 đạt?}
    L -->|Không| R
    L -->|Có| M([GO + hypercare])
```

## Mapping bổ sung

| Activity | Test trọng yếu |
|---|---|
| AD-07 | TC010–012, TC029, TC075, TC097 |
| AD-08 | TC005–009, TC042, TC073 |
| AD-09 | TC083–085, TC089, TC096 |
| AD-10 | TC082, TC088–092, TC099–100 |

## Activity specification catalog

| ID | Trigger | Tiền điều kiện | Hậu điều kiện thành công | Ngoại lệ trọng yếu |
|---|---|---|---|---|
| AD-01 | Request được tạo | User/type active | Một terminal hợp lệ hoặc state đang xử lý | Không reopen terminal; lifecycle mismatch |
| AD-02 | Submit/resubmit | Draft đầy đủ, file CLEAN | Revision/instance/route/SLA nguyên tử | Config changed, route/SoD, rollback audit/outbox |
| AD-03 | Approver quyết định | ACTIVE step đúng assignee | Next step hoặc state cuối đúng lifecycle | Wrong actor/version, reason, assignee unavailable |
| AD-04 | Execution/acceptance action | Attempt current và actor hợp lệ | B completed; C accepted hoặc rework attempt mới | Cross-request file, double claim/accept, actor disabled |
| AD-05 | OPS reassign | Scope + reason + mutable target | Actor mới và history/audit đầy đủ | SoD/role/scope invalid, target immutable |
| AD-06 | Scheduler/worker tick | Open stage hoặc outbox event | Alert/notification tối đa một lần | Stale lease, retry exhausted, recipient disabled |
| AD-07 | POLICY publish | Valid DRAFT và test vectors | Immutable published release active | Invalid schema/rule/hash/version race |
| AD-08 | Identity apply | Approved file và successful dry-run | Atomic org/role update + epoch/audit | Any-row error, hierarchy cycle, partial apply |
| AD-09 | Approved privacy action | Verified subject/case/decision | Scoped purge/redact + suppression evidence | Legal hold, manifest drift, FK/object mismatch |
| AD-10 | Approved release window | G3/G4 và restore rehearsal | G5 or controlled rollback | Migration/smoke/reconcile/RPO-RTO failure |
