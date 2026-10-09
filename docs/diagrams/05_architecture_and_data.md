# Architecture, DFD, deployment và ERD — EAS P0

**Loại:** Target design P0 · **Không phải AS-IS application**
Hiện repository mới có implementation đáng kể ở tầng PostgreSQL/Supabase. Các container/component ứng dụng dưới đây là thiết kế phải triển khai và kiểm chứng.

## AR-01 — System context

```mermaid
flowchart LR
    EMP[Nhân viên / Requester]
    MGR[Approver]
    EXE[Executor]
    ACC[Acceptor]
    ADM[Policy / OPS / Identity Admin]
    AUD[Auditor / Data owner]
    EAS[[Enterprise Approval System P0]]
    MAIL[(In-app notification only)]
    OPS[Operations / Backup infrastructure]

    EMP -->|Tạo và theo dõi yêu cầu| EAS
    MGR -->|Quyết định được gán| EAS
    EXE -->|Thực hiện và nộp bằng chứng| EAS
    ACC -->|Nghiệm thu hoặc làm lại| EAS
    ADM -->|Cấu hình và điều phối có audit| EAS
    AUD -->|Báo cáo, audit, privacy case| EAS
    EAS -->|Thông báo trong ứng dụng| MAIL
    OPS <-->|Deploy, monitor, backup, restore| EAS
```

Không có ERP/HRM, payment, mobile push hoặc AI decision trong context P0.

## AR-02 — Logical containers

```mermaid
flowchart TB
    subgraph CLIENT[Client zone]
      WEB[Web Client tiếng Việt]
      ADMIN[Web Admin / Controlled CLI]
    end
    subgraph APP[Application zone]
      API[Django API Core modular monolith]
      JOB[Scheduler / Worker cùng domain code]
    end
    subgraph DATA[Data zone]
      DB[(PostgreSQL schema eas)]
      OBJ[(Private Object Storage)]
      SCAN[File Scanner]
      SES[(Session / cache store)]
    end
    subgraph CONTROL[Control and recovery zone]
      CHK[(External Audit Checkpoint)]
      BAK[(Encrypted DB and Object Backup)]
      OBS[Logs / Metrics / Alerts]
    end

    WEB -->|HTTPS JSON + session cookie + CSRF| API
    ADMIN -->|HTTPS hoặc signed management command| API
    API -->|Parameterized SQL and transaction| DB
    API -->|Private object API| OBJ
    API --> SES
    JOB --> DB
    JOB --> OBJ
    SCAN --> OBJ
    SCAN --> DB
    JOB --> CHK
    API --> OBS
    JOB --> OBS
    DB --> BAK
    OBJ --> BAK
```

Frontend không truy cập trực tiếp DB. `eas_api`, `eas_worker`, `eas_backup`, `eas_privacy` là technical DB roles tách quyền; không dùng service role như end-user authorization.

## AR-03 — API Core components

```mermaid
flowchart LR
    CTRL[HTTP Controllers / Serializers]
    AUTH[Session, CSRF, Rate Limit]
    AUTHZ[Authorization and Scope Predicate]
    CMD[Command Handlers]
    QRY[Query / Reporting]
    CFG[Config and Routing Domain]
    WF[Workflow Domain]
    FILE[Attachment Domain]
    SLA[SLA and Outbox Domain]
    AUD[Audit / Hash Chain]
    PRIV[Privacy / Retention]
    REPO[Repositories / Unit of Work]

    CTRL --> AUTH --> AUTHZ
    AUTHZ --> CMD
    AUTHZ --> QRY
    CMD --> CFG & WF & FILE & SLA & PRIV
    CFG --> AUD
    WF --> AUD
    FILE --> AUD
    SLA --> AUD
    PRIV --> AUD
    CFG --> REPO
    WF --> REPO
    FILE --> REPO
    SLA --> REPO
    AUD --> REPO
    PRIV --> REPO
    QRY --> REPO
```

Mọi command handler dùng cùng Unit of Work để domain, audit, outbox và idempotency commit nguyên tử.

## DFD-00 — Context data flow

```mermaid
flowchart LR
    U[Người dùng nghiệp vụ]
    A[Quản trị / Auditor]
    EAS((0. EAS))
    D1[(D1 Hồ sơ và cấu hình)]
    D2[(D2 Tệp private)]
    D3[(D3 Audit / checkpoint)]
    D4[(D4 Backup)]

    U -->|Credential, form, decision, result| EAS
    EAS -->|Danh sách, trạng thái, thông báo| U
    A -->|Config, reassign, verify, privacy instruction| EAS
    EAS -->|Report, evidence, audit result| A
    EAS <--> D1
    EAS <--> D2
    EAS --> D3
    D1 --> D4
    D2 --> D4
```

## DFD-01 — Level 1 business processes

```mermaid
flowchart TB
    EXT1[Requester]
    EXT2[Approver]
    EXT3[Executor / Acceptor]
    EXT4[Admin / Auditor]
    P1((1.0 Identity and Access))
    P2((2.0 Request and File))
    P3((3.0 Workflow Decision))
    P4((4.0 Execution and Acceptance))
    P5((5.0 SLA and Notification))
    P6((6.0 Audit, Report and Privacy))
    D1[(Users Roles Org)]
    D2[(Request Revision File)]
    D3[(Instance Step Attempt)]
    D4[(SLA Outbox Notification)]
    D5[(Audit Privacy Retention)]

    EXT1 --> P1 --> D1
    EXT1 --> P2
    EXT2 --> P3
    EXT3 --> P4
    EXT4 --> P1
    EXT4 --> P6
    P2 <--> D2
    P2 --> P3
    P3 <--> D3
    P3 --> P4
    P4 <--> D3
    P3 --> P5
    P4 --> P5
    P5 <--> D4
    P1 --> P6
    P2 --> P6
    P3 --> P6
    P4 --> P6
    P5 --> P6
    P6 <--> D5
```

## SEC-01 — Trust boundaries và threat surfaces

```mermaid
flowchart LR
    subgraph UNTRUST[Untrusted device / browser]
      B[Browser]
      F[Uploaded file and free text]
    end
    subgraph EDGE[HTTPS boundary]
      G[Reverse Proxy / Security Headers / Rate Limit]
    end
    subgraph TRUST[Application trust zone]
      A[Django API]
      W[Worker / Scheduler]
      V[Scanner adapter]
    end
    subgraph PRIV[Privileged data zone]
      D[(PostgreSQL)]
      O[(Private Object Storage)]
      S[(Secrets / Session)]
    end
    subgraph RECOVERY[Separate control zone]
      C[(Audit Checkpoint)]
      K[(Encrypted Backups)]
    end

    B -->|Cookie + CSRF + JSON| G --> A
    F -->|Quarantine only| O
    A -->|Least-privilege role| D
    A --> O
    A --> S
    W -->|Worker role, no business decision| D
    V -->|Read quarantine, write scan result| O
    V --> D
    W --> C
    D --> K
    O --> K
```

Threat review tối thiểu: credential/session theft, CSRF, IDOR, mass assignment, injection/XSS, malicious upload/path traversal, confused deputy, stale role, race, audit tamper, backup exfiltration và privacy purge misuse.

## DP-01 — Production deployment topology đề xuất

```mermaid
flowchart TB
    USER[Corporate Users]
    DNS[DNS / TLS Endpoint]
    RP[Reverse Proxy / WAF]
    APP1[Django API Instance 1]
    APP2[Django API Instance 2]
    WK1[Worker]
    SCH[Singleton Scheduler with DB lease]
    DBP[(PostgreSQL Primary)]
    DBR[(Replica / PITR Archive)]
    OBJ[(Versioned Private Object Storage)]
    SC[Scanner]
    OBS[Central Logs Metrics Alerts]
    BAK[(Off-host Encrypted Backup)]

    USER -->|TLS 1.2+| DNS --> RP
    RP --> APP1 & APP2
    APP1 --> DBP
    APP2 --> DBP
    WK1 --> DBP
    SCH --> DBP
    APP1 --> OBJ
    APP2 --> OBJ
    WK1 --> OBJ
    SC --> OBJ
    SC --> DBP
    APP1 --> OBS
    APP2 --> OBS
    WK1 --> OBS
    SCH --> OBS
    DBP -->|WAL / replication| DBR
    DBP --> BAK
    OBJ --> BAK
```

Topology thực tế, sizing, vùng lưu trữ và công cụ backup phải được điền tại KD05/KD06/KD08; hình này không phải bằng chứng hạ tầng đã tồn tại.

## ER-01 — Identity, configuration và request core

```mermaid
erDiagram
    DEPARTMENT ||--o{ DEPARTMENT : parent_of
    DEPARTMENT ||--o{ APP_USER : contains
    APP_USER ||--o{ ROLE_MEMBERSHIP : receives
    DEPARTMENT ||--o{ ROLE_MEMBERSHIP : scopes
    REQUEST_TYPE ||--o{ ROLE_MEMBERSHIP : type_scopes
    REQUEST_TYPE ||--o{ CONFIG_RELEASE : versions
    REQUEST_TYPE ||--o{ REQUEST : classifies
    CONFIG_RELEASE ||--o{ REQUEST_REVISION : snapshots
    APP_USER ||--o{ REQUEST : owns
    REQUEST ||--o{ REQUEST_REVISION : has
    REQUEST ||--o{ REQUEST_PARTICIPANT : grants_history_read
    APP_USER ||--o{ REQUEST_PARTICIPANT : participates
    REQUEST ||--o{ IDEMPOTENCY_RECORD : deduplicates
    SECURITY_EPOCH ||--o{ ROLE_MEMBERSHIP : linearizes_changes
```

## ER-02 — Workflow, execution và attachment

```mermaid
erDiagram
    REQUEST ||--o{ WORKFLOW_INSTANCE : runs
    REQUEST_REVISION ||--|| WORKFLOW_INSTANCE : drives
    WORKFLOW_INSTANCE ||--|{ APPROVAL_STEP : contains
    APPROVAL_STEP ||--o| APPROVAL_DECISION : decided_by
    WORKFLOW_INSTANCE ||--o{ EXECUTION_ATTEMPT : executes
    EXECUTION_ATTEMPT ||--o| ACCEPTANCE_DECISION : accepted_by
    EXECUTION_ATTEMPT ||--o{ EXECUTION_ISSUE : reports
    REQUEST ||--o{ ATTACHMENT : owns
    REQUEST ||--o{ DRAFT_ATTACHMENT : selects
    ATTACHMENT ||--o{ DRAFT_ATTACHMENT : linked_as_draft
    REQUEST_REVISION ||--o{ REVISION_ATTACHMENT : freezes
    ATTACHMENT ||--o{ REVISION_ATTACHMENT : linked_as_revision
    EXECUTION_ATTEMPT ||--o{ EXECUTION_ATTACHMENT : evidences
    ATTACHMENT ||--o{ EXECUTION_ATTACHMENT : linked_as_result
```

## ER-03 — SLA, event, audit và privacy

```mermaid
erDiagram
    REQUEST ||--o{ SLA_STAGE : tracks
    SLA_STAGE ||--o{ SLA_ALERT : emits
    REQUEST ||--o{ AUDIT_EVENT : records
    AUDIT_HEAD ||--o{ AUDIT_EVENT : chains
    AUDIT_HEAD ||--o{ AUDIT_CHECKPOINT : checkpoints
    REQUEST ||--o{ OUTBOX_EVENT : emits
    OUTBOX_EVENT ||--o{ NOTIFICATION : delivers
    APP_USER ||--o{ NOTIFICATION : receives
    APP_USER ||--o{ PRIVACY_CASE : subjects
    PRIVACY_CASE ||--o{ RETENTION_HOLD : controls
    REQUEST ||--o{ RETENTION_HOLD : protects
    AUDIT_HEAD ||--o{ ADMIN_EVENT : chains_admin
```

Ba ERD là logical/domain view. Tên cột, composite FK, partial unique, CHECK, trigger và RLS chính xác phải lấy từ tài liệu 03 và `00_eas_supabase_schema.sql`, không suy từ cardinality giản lược trong hình.

## AR-04 — Module dependency direction

```mermaid
flowchart TB
    UI[Presentation / HTTP]
    APP[Application Commands and Queries]
    DOM[Domain Model and Policies]
    PORT[Ports: Repository, Clock, Storage, Scanner, Notifier]
    INFRA[Infrastructure Adapters]
    DB[(PostgreSQL)]
    OBJ[(Object Storage / Scanner)]

    UI --> APP
    APP --> DOM
    APP --> PORT
    INFRA -. implements .-> PORT
    INFRA --> DB
    INFRA --> OBJ
    DOM -. no dependency .-> INFRA
```

Domain không phụ thuộc Django model side effect hoặc external service. Network call phải ở ngoài transaction giữ row lock; outbox là ranh giới giao bất đồng bộ.

## Diagram-to-evidence matrix

| Diagram | Bằng chứng cần có trước khi đổi nhãn thành AS-IS |
|---|---|
| AR-01/02 | Source tree, API routes, running service inventory |
| AR-03/04 | Package dependency tests, architecture decision record, code review |
| DFD-00/01 | Data inventory, endpoint trace, storage/log/backup mapping |
| SEC-01 | Threat model review, ASVS mapping, penetration evidence |
| DP-01 | IaC/compose manifests, network diagram, secrets/backup/monitoring evidence |
| ER-01/02/03 | Migration catalog, FK/CHECK/index/RLS validation trên PostgreSQL đích |

## ER-04 — Identity và organization chi tiết

```mermaid
erDiagram
    SECURITY_EPOCH {
      bigint epoch PK
      timestamptz updated_at
    }
    DEPARTMENT {
      uuid id PK
      uuid parent_id FK
      uuid manager_id FK
      text code UK
      text name
    }
    APP_USER {
      uuid id PK
      uuid department_id FK
      text username UK
      boolean is_active
    }
    ROLE_MEMBERSHIP {
      uuid id PK
      uuid user_id FK
      uuid department_scope_id FK
      uuid type_id FK
      text role_code
      timestamptz valid_from
      timestamptz valid_to
    }
    DEPARTMENT ||--o{ DEPARTMENT : parent
    DEPARTMENT ||--o{ APP_USER : contains
    APP_USER ||--o{ DEPARTMENT : manages
    APP_USER ||--o{ ROLE_MEMBERSHIP : has
    DEPARTMENT ||--o{ ROLE_MEMBERSHIP : department_scope
    SECURITY_EPOCH ||--o{ ROLE_MEMBERSHIP : linearization_guard
```

## ER-05 — Request type, config và revision chi tiết

```mermaid
erDiagram
    REQUEST_TYPE {
      uuid id PK
      text code UK
      char lifecycle
      uuid active_release_id FK
    }
    CONFIG_RELEASE {
      uuid id PK
      uuid type_id FK
      text state
      jsonb form_schema
      jsonb route_rules
      jsonb sla_profile
      char content_hash
    }
    REQUEST {
      uuid id PK
      uuid type_id FK
      uuid owner_id FK
      text status
      bigint version
      uuid current_revision_id FK
    }
    REQUEST_REVISION {
      uuid id PK
      uuid request_id FK
      uuid release_id FK
      int revision_no
      uuid department_id FK
      jsonb payload
    }
    REQUEST_TYPE ||--o{ CONFIG_RELEASE : versions
    REQUEST_TYPE ||--o{ REQUEST : classifies
    CONFIG_RELEASE ||--o{ REQUEST_REVISION : snapshots
    REQUEST ||--o{ REQUEST_REVISION : owns
    REQUEST_REVISION o|--|| REQUEST : current_revision
```

## ER-06 — Approval workflow chi tiết

```mermaid
erDiagram
    REQUEST ||--o{ WORKFLOW_INSTANCE : has
    REQUEST_REVISION ||--|| WORKFLOW_INSTANCE : drives
    WORKFLOW_INSTANCE ||--|{ APPROVAL_STEP : contains
    APPROVAL_STEP ||--o| APPROVAL_DECISION : receives
    REQUEST ||--o{ REQUEST_PARTICIPANT : records
    APP_USER ||--o{ REQUEST_PARTICIPANT : participates
    APP_USER ||--o{ APPROVAL_STEP : assigned
    APP_USER ||--o{ APPROVAL_DECISION : decides
    WORKFLOW_INSTANCE {
      uuid id PK
      uuid request_id FK
      uuid revision_id FK
      char lifecycle
      text state
    }
    APPROVAL_STEP {
      uuid id PK
      uuid instance_id FK
      int step_no
      uuid assignee_id FK
      text state
    }
    APPROVAL_DECISION {
      uuid id PK
      uuid step_id FK
      uuid actor_id FK
      text outcome
      text reason
    }
```

## ER-07 — Execution và acceptance chi tiết

```mermaid
erDiagram
    WORKFLOW_INSTANCE ||--o{ EXECUTION_ATTEMPT : creates
    APP_USER ||--o{ EXECUTION_ATTEMPT : executes
    EXECUTION_ATTEMPT ||--o{ EXECUTION_ISSUE : reports
    EXECUTION_ATTEMPT ||--o| ACCEPTANCE_DECISION : receives
    APP_USER ||--o{ ACCEPTANCE_DECISION : accepts
    EXECUTION_ATTEMPT {
      uuid id PK
      uuid instance_id FK
      int attempt_no
      uuid executor_id FK
      text state
      text closure
      text result_note
    }
    EXECUTION_ISSUE {
      uuid id PK
      uuid attempt_id FK
      text issue_kind
      text reason
    }
    ACCEPTANCE_DECISION {
      uuid id PK
      uuid attempt_id FK
      uuid actor_id FK
      text outcome
      text reason
    }
```

## ER-08 — Attachment và immutable link chi tiết

```mermaid
erDiagram
    REQUEST ||--o{ ATTACHMENT : owns
    APP_USER ||--o{ ATTACHMENT : uploads
    REQUEST ||--o{ DRAFT_ATTACHMENT : selects
    ATTACHMENT ||--o{ DRAFT_ATTACHMENT : draft_link
    REQUEST_REVISION ||--o{ REVISION_ATTACHMENT : freezes
    ATTACHMENT ||--o{ REVISION_ATTACHMENT : revision_link
    EXECUTION_ATTEMPT ||--o{ EXECUTION_ATTACHMENT : evidences
    ATTACHMENT ||--o{ EXECUTION_ATTACHMENT : execution_link
    ATTACHMENT {
      uuid id PK
      uuid request_id FK
      uuid uploaded_by FK
      text storage_key UK
      bigint size_bytes
      char sha256
      text scan_state
    }
```

## ER-09 — SLA, outbox và notification chi tiết

```mermaid
erDiagram
    REQUEST ||--o{ SLA_STAGE : tracks
    SLA_STAGE ||--o{ SLA_ALERT : emits
    REQUEST ||--o{ OUTBOX_EVENT : emits
    OUTBOX_EVENT ||--o{ NOTIFICATION : delivers
    APP_USER ||--o{ NOTIFICATION : receives
    SLA_STAGE {
      uuid id PK
      uuid request_id FK
      text stage_kind
      timestamptz started_at
      timestamptz due_at
      timestamptz closed_at
    }
    OUTBOX_EVENT {
      uuid id PK
      uuid request_id FK
      text event_type
      text state
      uuid lease_token
      int attempts
      text dedupe_key UK
    }
    NOTIFICATION {
      uuid id PK
      uuid event_id FK
      uuid recipient_id FK
      timestamptz read_at
    }
```

## ER-10 — Audit, idempotency và privacy chi tiết

```mermaid
erDiagram
    REQUEST ||--o{ AUDIT_EVENT : audits
    AUDIT_HEAD ||--o{ AUDIT_EVENT : chains
    AUDIT_HEAD ||--o{ ADMIN_EVENT : chains
    AUDIT_HEAD ||--o{ AUDIT_CHECKPOINT : proves
    REQUEST ||--o{ IDEMPOTENCY_RECORD : deduplicates
    APP_USER ||--o{ PRIVACY_CASE : subject
    PRIVACY_CASE ||--o{ RETENTION_HOLD : governs
    REQUEST ||--o{ RETENTION_HOLD : protects
    AUDIT_HEAD {
      text scope PK
      bigint last_seq
      char last_hash
    }
    AUDIT_EVENT {
      uuid id PK
      uuid request_id FK
      bigint seq
      char previous_hash
      char event_hash
    }
    IDEMPOTENCY_RECORD {
      uuid id PK
      text key
      char payload_hash
      smallint http_status
      timestamptz expires_at
    }
    PRIVACY_CASE {
      uuid id PK
      uuid subject_user_id FK
      text case_type
      text status
      timestamptz due_at
    }
```

## UI-01 — Sitemap chức năng P0

```mermaid
flowchart TD
    LOGIN[Đăng nhập]
    HOME[Trang chủ cá nhân]
    MINE[Tab Yêu cầu của tôi]
    APPROVE[Tab Cần phê duyệt]
    EXECUTE[Tab Cần thực hiện]
    ACCEPT[Tab Cần nghiệm thu]
    DETAIL[Chi tiết và timeline]
    FORM[Form LEAVE / ACCESS / EQUIPMENT]
    NOTI[Thông báo]
    POLICY[Policy Admin]
    OPS[OPS Điều phối]
    AUDIT[Audit / Report]
    LOGIN --> HOME
    HOME --> MINE & APPROVE & EXECUTE & ACCEPT & NOTI
    MINE --> FORM & DETAIL
    APPROVE --> DETAIL
    EXECUTE --> DETAIL
    ACCEPT --> DETAIL
    NOTI --> DETAIL
    HOME --> POLICY & OPS & AUDIT
```
