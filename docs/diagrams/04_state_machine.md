# State-machine diagrams — EAS P0

**Loại:** Target design P0 · **Nguồn:** SRS/SDD v2 + CHECK/trigger trong schema v2.0.1
State machine là chuẩn kiểm tra chéo cho activity, sequence, API guard và state-transition tests.

## ST-01 — Request

```mermaid
stateDiagram-v2
    [*] --> DRAFT: create
    DRAFT --> PENDING_APPROVAL: submit
    DRAFT --> CANCELLED: withdraw
    PENDING_APPROVAL --> PENDING_APPROVAL: approve non-final
    PENDING_APPROVAL --> NEEDS_INFO: needs info
    NEEDS_INFO --> PENDING_APPROVAL: resubmit new revision
    NEEDS_INFO --> CANCELLED: withdraw
    PENDING_APPROVAL --> REJECTED: reject
    PENDING_APPROVAL --> CANCELLED: withdraw wins race
    PENDING_APPROVAL --> COMPLETED: final approve lifecycle A
    PENDING_APPROVAL --> READY_FOR_EXECUTION: final approve lifecycle B or C
    READY_FOR_EXECUTION --> IN_PROGRESS: claim
    IN_PROGRESS --> READY_FOR_EXECUTION: reassign running executor
    IN_PROGRESS --> COMPLETED: submit result lifecycle B
    IN_PROGRESS --> WAITING_FOR_ACCEPTANCE: submit result lifecycle C
    WAITING_FOR_ACCEPTANCE --> COMPLETED: accept
    WAITING_FOR_ACCEPTANCE --> READY_FOR_EXECUTION: rework
    COMPLETED --> [*]
    REJECTED --> [*]
    CANCELLED --> [*]
```

Terminal state không được reopen. `NEEDS_INFO` dùng instance mới khi resubmit.

## ST-02 — Workflow instance

```mermaid
stateDiagram-v2
    [*] --> ACTIVE: submit or resubmit
    ACTIVE --> COMPLETED: final approve
    ACTIVE --> REJECTED: reject
    ACTIVE --> SUPERSEDED: needs info
    ACTIVE --> CANCELLED: withdraw
    COMPLETED --> [*]
    REJECTED --> [*]
    SUPERSEDED --> [*]
    CANCELLED --> [*]
```

Mỗi request có tối đa một instance `ACTIVE`.

## ST-03 — Approval step

```mermaid
stateDiagram-v2
    [*] --> WAITING: route creation
    WAITING --> ACTIVE: previous step approved or first step
    ACTIVE --> APPROVED: approve
    ACTIVE --> REJECTED: reject
    ACTIVE --> NEEDS_INFO: request information
    WAITING --> SKIPPED: request reject or cancel or needs info
    ACTIVE --> SKIPPED: request cancel wins race
    APPROVED --> [*]
    REJECTED --> [*]
    NEEDS_INFO --> [*]
    SKIPPED --> [*]
```

Một instance có tối đa một step `ACTIVE`; mỗi step có tối đa một decision.

## ST-04 — Execution attempt

```mermaid
stateDiagram-v2
    [*] --> READY: final approval or rework or reassignment
    READY --> RUNNING: claim
    RUNNING --> SUBMITTED: submit lifecycle C result
    RUNNING --> FINISHED: lifecycle B success
    RUNNING --> FINISHED: OPS reassign with REASSIGNED closure
    SUBMITTED --> FINISHED: accept with ACCEPTED closure
    SUBMITTED --> FINISHED: rework with REWORK closure
    FINISHED --> [*]
```

Rework và RUNNING reassignment luôn tạo attempt mới `READY`; không tái mở attempt cũ.

## ST-05 — Attachment scan

```mermaid
stateDiagram-v2
    [*] --> QUEUED: upload complete
    QUEUED --> CLEAN: scanner pass
    QUEUED --> INFECTED: malware found
    QUEUED --> ERROR: timeout or scanner failure after retry
    ERROR --> QUEUED: authorized rescan
    CLEAN --> [*]: eligible for link or download
    INFECTED --> [*]: quarantined
```

Chỉ `CLEAN` được liên kết vào revision/attempt. Tệp lịch sử đang được tham chiếu không được tombstone tùy ý.

## ST-06 — SLA stage

```mermaid
stateDiagram-v2
    [*] --> OPEN: stage starts
    OPEN --> OPEN: reminder at 50 percent
    OPEN --> OPEN: breach recorded at due time
    OPEN --> CLOSED: target action completes
    CLOSED --> [*]
```

Reminder/breach là alert bất biến, không phải request state. Reassign giữ stage/deadline; rework tạo stage execution mới.

## ST-07 — Outbox event

```mermaid
stateDiagram-v2
    [*] --> PENDING: business transaction commit
    PENDING --> PROCESSING: worker claims lease
    PROCESSING --> SENT: notification insert and ACK commit
    PROCESSING --> PENDING: transient failure attempts 1 to 3
    PROCESSING --> PENDING: lease expires before ACK
    PROCESSING --> DEAD: fourth failure
    DEAD --> PENDING: OPS replay with reason
    SENT --> [*]
```

Lease token cũ không được insert/ACK; notification có dedupe theo event và recipient.

## ST-08 — Config release

```mermaid
stateDiagram-v2
    [*] --> DRAFT: create or clone published
    DRAFT --> DRAFT: edit and validate
    DRAFT --> PUBLISHED: atomic publish
    PUBLISHED --> [*]: immutable
```

Không sửa hoặc unpublish release đã xuất bản. Active pointer có thể chuyển sang release mới; instance cũ giữ snapshot release cũ.

## State-to-test matrix

| State machine | Test case chính |
|---|---|
| ST-01 Request | TC027–038, TC043–055, TC095 |
| ST-02 Instance | TC027, TC032, TC035–038, TC095 |
| ST-03 Approval step | TC031–042, TC095 |
| ST-04 Execution attempt | TC043–055, TC094–095 |
| ST-05 Attachment | TC014–020, TC050, TC079, TC094 |
| ST-06 SLA | TC039, TC049, TC061–064, TC070 |
| ST-07 Outbox | TC028, TC065–069, TC087 |
| ST-08 Config release | TC010–012, TC029, TC097 |
