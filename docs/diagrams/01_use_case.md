# Use-case model — EAS P0

**Model ID:** EAS-UCM-P0-01 · **Loại:** Target design P0 · **Nguồn:** SRS v2 mục 10
**Lưu ý:** Đây không phải mô tả ứng dụng đã triển khai; hiện mới có lớp database đáng kể.

## 1. UC-CTX-01 — System context

```mermaid
flowchart LR
    req[REQUESTER]
    app[APPROVER]
    exe[EXECUTOR]
    acc[ACCEPTOR]
    pol[POLICY_ADMIN]
    ops[OPS_ADMIN]
    aud[AUDITOR]
    idm[Identity operator]
    job[Scheduler / Worker]

    subgraph EAS[Enterprise Approval System — P0]
      uc01((UC01\nĐăng nhập / logout))
      uc03((UC03\nNháp và tệp))
      uc04((UC04\nSubmit lần đầu))
      uc05((UC05\nXem hồ sơ / bằng chứng))
      uc06((UC06\nQuyết định duyệt))
      uc07((UC07\nBổ sung / resubmit))
      uc08((UC08\nWithdraw))
      uc09((UC09\nReassign có kiểm soát))
      uc10((UC10\nClaim / unable))
      uc11((UC11\nIssue / nộp kết quả))
      uc12((UC12\nAccept / rework))
      uc13((UC13\nĐọc thông báo))
      uc14((UC14\nSLA / giao thông báo))
      uc15((UC15\nBáo cáo / audit))
      uc02((UC02\nConfig release))
      uc17((UC17\nDanh tính / tổ chức / quyền))
    end

    req --- uc01 & uc03 & uc04 & uc05 & uc07 & uc08 & uc13
    app --- uc01 & uc05 & uc06 & uc13
    exe --- uc01 & uc05 & uc10 & uc11 & uc13
    acc --- uc01 & uc05 & uc12 & uc13
    pol --- uc01 & uc02 & uc15
    ops --- uc01 & uc09 & uc15
    aud --- uc01 & uc05 & uc15
    idm --- uc17
    job --- uc14
```

## 2. UC-REL-01 — Quan hệ nghiệp vụ giữa các use case

```mermaid
flowchart TD
    UC03[UC03 — Tạo/sửa nháp và tệp]
    UC04[UC04 — Submit]
    UC06[UC06 — Approve / Reject / Needs info]
    UC07[UC07 — Bổ sung / Resubmit]
    UC08[UC08 — Withdraw]
    UC10[UC10 — Claim / Unable to claim]
    UC11[UC11 — Issue / Submit execution]
    UC12[UC12 — Accept / Rework]
    UC09[UC09 — Reassign]
    UC14[UC14 — SLA / Notification worker]

    UC03 -->|tiền điều kiện submit| UC04
    UC04 --> UC06
    UC06 -->|NEEDS_INFO| UC07
    UC07 -->|include: validate + snapshot + route lại| UC04
    UC04 -.->|extend khi chưa duyệt đủ| UC08
    UC06 -->|duyệt cuối B/C| UC10
    UC10 --> UC11
    UC11 -->|lifecycle C| UC12
    UC12 -->|REWORK: attempt mới| UC10
    UC09 -.->|điều phối actor chưa hoàn tất| UC06
    UC09 -.-> UC10
    UC09 -.-> UC12
    UC14 -.->|theo dõi stage, không đổi state| UC06
    UC14 -.-> UC10
    UC14 -.-> UC12
```

## 3. Ma trận actor–use case

`P` = primary actor; `S` = hỗ trợ/được đọc; `—` = không có quyền từ use case đó.

| UC | Requester | Approver | Executor | Acceptor | Policy | OPS | Auditor | System |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| UC01 Login/logout | P | P | P | P | P | P | P | — |
| UC02 Config release | — | — | — | — | P | — | S | — |
| UC03 Draft/attachment | P | — | — | — | — | — | — | scanner S |
| UC04 First submit | P | — | — | — | — | — | — | — |
| UC05 View/evidence | P* | P* | P* | P* | — | metadata | P* | — |
| UC06 Decision | — | P | — | — | — | — | — | — |
| UC07 Resubmit | P | — | — | — | — | — | — | — |
| UC08 Withdraw | P | — | — | — | — | — | — | — |
| UC09 Reassign | S | S | S | S | — | P | S | — |
| UC10 Claim/unable | — | — | P | — | — | S | — | — |
| UC11 Issue/result | — | — | P | — | — | S | — | — |
| UC12 Acceptance/rework | — | — | S | P | — | S | — | — |
| UC13 Notification | P* | P* | P* | P* | P* | P* | P* | worker S |
| UC14 SLA/delivery | — | — | — | — | — | S | S | P |
| UC15 Report/audit | S* | S* | S* | S* | admin-only | admin-only | P | — |
| UC17 Identity/org/role | — | — | — | — | — | — | S | identity P |

`*` luôn phụ thuộc active account và predicate owner/participant/role + type + department snapshot. Một người có thể giữ nhiều role nhưng SoD vẫn được kiểm độc lập.

## 4. Use-case contract rút gọn

| UC | Trigger | Tiền điều kiện chính | Thành công | Ngoại lệ bắt buộc thể hiện |
|---|---|---|---|---|
| UC01 | Gửi credential/logout | Account được cấp | Session rotate/hủy, CSRF hợp lệ | Generic 401, 429, idle/absolute expiry |
| UC02 | Publish release | POLICY đúng type/scope; DRAFT | Published bất biến, active swap nguyên tử | Config invalid; version conflict; actor chưa hợp lệ khi submit |
| UC03 | Save/upload/select file | REQUESTER đúng type/phòng | DRAFT/NEEDS_INFO tăng version | stale version; 413/415; scan không CLEAN; quota |
| UC04 | Submit | Nháp đầy đủ; viewed release hiện hành | Revision + instance + 1–3 step + SLA | config changed; route/SoD; audit/outbox fail rollback |
| UC05 | List/detail/download | Active và owner/participant/auditor đúng scope | Chỉ dữ liệu được phép, download audit | 404 anti-enumeration; OPS chỉ metadata |
| UC06 | Quyết định step | ACTIVE step, đúng assignee | Next step hoặc trạng thái cuối đúng A/B/C | reason; assignee unavailable; 403/409/replay |
| UC07 | Resubmit | NEEDS_INFO | Revision/instance/route mới | release đổi; route/amount đổi; không tái dùng decision cũ |
| UC08 | Withdraw | Owner; trước duyệt đủ | CANCELLED + steps còn lại SKIPPED | Race với final approval; terminal không reopen |
| UC09 | Reassign | OPS đúng scope + reason | Actor mới, history giữ nguyên | target immutable; SoD/role/scope invalid |
| UC10 | Claim/unable | Attempt READY, đúng executor | RUNNING/IN_PROGRESS hoặc issue | two claims; wrong actor; issue không reset SLA |
| UC11 | Submit result | Attempt RUNNING | B completed; C waiting acceptance | tệp/owner sai; blocked không giả completion |
| UC12 | Accept/rework | C, attempt SUBMITTED, đúng acceptor | Completed hoặc attempt READY mới | acceptor=executor; repeat; planned executor unavailable |
| UC13 | Read notification | Recipient hiện tại | `read_at` đặt một lần | người khác 404; link kiểm quyền lại |
| UC14 | Scheduler/worker tick | Stage/outbox hợp lệ | Reminder/breach/delivery dedupe | stale lease; retry 1/5/15; DEAD + replay |
| UC15 | Query/verify | Đúng kênh và scope | Aggregate đúng mẫu số; PASS/FAIL/UNKNOWN | zero denominator; gap/checkpoint thiếu |
| UC17 | Dry-run/apply import | File đã duyệt; operator định danh | Một transaction + security epoch + audit | bất kỳ dòng lỗi → không apply phần |

## 5. Quy tắc review

- UC16 cố ý không có trong P0: trong nguồn cũ nó là AI/P1; không tái sử dụng ID cho chức năng khác.
- UC02/UC09/UC17 không trao quyền đọc payload request.
- UC14 không được approve, reassign hoặc thay đổi request status.
- Mọi use case ghi phải liên kết tới sequence tương ứng và test trong RTM.

## 6. UC-BIZ-01 — Use case nghiệp vụ lõi theo actor

```mermaid
flowchart LR
    R[REQUESTER]
    P[APPROVER]
    E[EXECUTOR]
    C[ACCEPTOR]
    subgraph CORE[Request Lifecycle Boundary]
      D((Soạn nháp và tệp))
      S((Submit / Resubmit))
      V((Xem hồ sơ))
      W((Withdraw))
      Q((Approve / Reject / Needs Info))
      CL((Claim / Báo không thể nhận))
      EX((Báo vướng / Nộp kết quả))
      AC((Accept / Rework))
      NT((Đọc thông báo))
    end
    R --- D & S & V & W & NT
    P --- V & Q & NT
    E --- V & CL & EX & NT
    C --- V & AC & NT
    S -.->|include| D
    Q -.->|extend: NEEDS_INFO| S
    EX -.->|lifecycle C| AC
    AC -.->|extend: REWORK| CL
```

## 7. UC-ADM-01 — Quản trị và quản trị dữ liệu

```mermaid
flowchart LR
    PA[POLICY_ADMIN]
    OA[OPS_ADMIN]
    AU[AUDITOR]
    IA[Identity operator]
    PO[Privacy operator / Data owner]
    subgraph GOV[Governance Boundary]
      CFG((Clone / Validate / Publish release))
      REA((Reassign actor))
      REP((Replay outbox DEAD))
      RPT((Xem báo cáo theo scope))
      VER((Verify audit / checkpoint))
      IDM((Dry-run / Apply org-role import))
      PRV((Xử lý privacy case))
      HLD((Legal hold / Purge có kiểm soát))
    end
    PA --- CFG
    OA --- REA & REP
    AU --- RPT & VER
    IA --- IDM
    PO --- PRV & HLD
    PRV -.->|include| HLD
```

`Privacy operator` là actor đặc quyền vận hành/pháp lý, chưa được formalize thành end-user role trong SRS; phải đóng KD06 và threat model trước production.

## 8. UC-SYS-01 — Tác vụ nền và hệ thống ngoài

```mermaid
flowchart LR
    SC[File Scanner]
    SJ[SLA Scheduler]
    OW[Outbox Worker]
    PS[Private Storage]
    CP[External Checkpoint Store]
    OP[OPS_ADMIN]
    subgraph SYS[Background Processing Boundary]
      FQ((Quarantine / Scan file))
      SS((Scan SLA stage))
      EV((Tạo reminder / breach event))
      LE((Claim lease / Deliver notification))
      DL((Dead-letter / Replay))
      HC((Xuất / Verify audit checkpoint))
    end
    SC --- FQ
    PS --- FQ
    SJ --- SS
    SS --> EV
    OW --- LE
    LE -.->|sau retry hữu hạn| DL
    OP --- DL
    CP --- HC
```

## 9. UC-BIZ-02 — Khởi tạo, gửi và quyết định yêu cầu

```mermaid
flowchart LR
    R[REQUESTER]
    P[APPROVER]
    O[OPS_ADMIN]
    subgraph SUBMIT[Submission and Approval Boundary]
      CR((Tạo request))
      DR((Lưu nháp))
      UP((Upload / chọn tệp CLEAN))
      SB((Submit))
      VW((Xem revision và route))
      AP((Approve))
      RJ((Reject có lý do))
      NI((Yêu cầu bổ sung))
      RS((Sửa và resubmit))
      WD((Withdraw))
      RA((Reassign step))
    end
    R --- CR & DR & UP & SB & VW & RS & WD
    P --- VW & AP & RJ & NI
    O --- RA
    CR --> DR
    SB -.->|include| UP
    NI -.->|extend| RS
    RS -.->|include: snapshot và route lại| SB
    RA -.->|extend khi actor unavailable| AP
```

## 10. UC-BIZ-03 — Thực hiện và nghiệm thu

```mermaid
flowchart LR
    E[EXECUTOR]
    A[ACCEPTOR]
    O[OPS_ADMIN]
    subgraph EXEC[Execution and Acceptance Boundary]
      VIEW((Xem hồ sơ đã duyệt))
      CLAIM((Claim việc))
      UNABLE((Báo không thể nhận))
      BLOCK((Báo vướng))
      EVID((Upload bằng chứng))
      SUB((Nộp kết quả))
      ACCEPT((Nghiệm thu))
      REWORK((Yêu cầu làm lại))
      REX((Reassign executor / acceptor))
    end
    E --- VIEW & CLAIM & UNABLE & BLOCK & EVID & SUB
    A --- VIEW & ACCEPT & REWORK
    O --- REX
    CLAIM -.->|extend| UNABLE
    SUB -.->|include| EVID
    SUB -.->|lifecycle C| ACCEPT
    ACCEPT -.->|alternative| REWORK
    REWORK -.->|attempt mới, phải claim| CLAIM
    REX -.-> CLAIM
    REX -.-> ACCEPT
```

## 11. UC-APR-01 — Góc nhìn Approver

```mermaid
flowchart LR
    A[APPROVER]
    subgraph APR[Approval Workspace]
      Q((Xem hàng chờ được gán))
      D((Xem revision / evidence / route / SLA))
      AP((Approve))
      RJ((Reject có lý do))
      NI((Needs Info có lý do))
      NT((Đọc thông báo))
    end
    A --- Q & D & AP & RJ & NI & NT
    AP -.->|guard| G1{ACTIVE step và đúng assignee}
    RJ -.->|guard| G1
    NI -.->|guard| G1
    G1 -.-> G2{Role, scope, SoD và version hợp lệ}
```

## 12. UC-CTL-01 — Góc nhìn kiểm soát nội bộ

```mermaid
flowchart LR
    O[OPS_ADMIN]
    P[POLICY_ADMIN]
    A[AUDITOR]
    I[Identity Operator]
    subgraph CONTROL[Control Plane]
      RA((Reassign có lý do))
      DL((Replay DEAD event))
      PB((Publish immutable config))
      RR((Scoped report))
      AV((Audit verification))
      IM((Atomic identity import))
      SE((Session/security epoch invalidation))
    end
    O --- RA & DL
    P --- PB
    A --- RR & AV
    I --- IM
    IM -.->|include| SE
```
