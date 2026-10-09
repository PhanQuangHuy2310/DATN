# Chiến lược test case và RTM — EAS P0

**Mã:** EAS-TEST-GUIDE-01 · **Phiên bản:** 1.0 · **Ngày:** 09/10/2026
**Nguồn ca chi tiết:** `docs/04_Ke_hoach_va_ca_kiem_thu_v2.docx`
**Trạng thái:** `TC001–TC100 = NOT RUN` cho đến khi có execution record hợp lệ.

## 1. Tuyên bố trạng thái kiểm thử

| Suite | Phạm vi | Kết quả hiện có | Không được suy diễn |
|---|---|---|---|
| `DB-VAL` | Schema/constraint/trigger/RLS và fixture DB | 98/98 PASS trên PGlite single-backend; lượt tái lập có 86 assertion message | Không chứng minh API/UI, multi-session race, storage, scanner, DR hoặc UAT |
| `TC001–TC100` | Acceptance/security/NFR/ops của EAS P0 | Designed, `NOT RUN` | Không được ghi PASS chỉ vì expected result đã được viết |
| Source/application tests | Django/Web/worker/E2E | Chưa có implementation/bộ test chạy được | README trong `tests` không phải test evidence |

Mọi báo cáo phải tách ba suite trên; không cộng hoặc quy đổi 98 DB checks thành 100 acceptance cases.

## 2. Mục tiêu và phạm vi

### Trong P0

- auth/session/password/CSRF/rate limit;
- user, department, role, scope và security epoch;
- config release bất biến, rule allowlist và route 1–3 cấp;
- draft/revision, file private, scanner, quota;
- lifecycle A/B/C, SoD, decision, resubmit, withdraw;
- execution, acceptance, rework, reassign;
- SLA, outbox, notification, audit/checkpoint, idempotency;
- report, privacy/retention/legal hold;
- migration, performance, resilience, backup/restore, UAT, production smoke.

### Ngoài P0

Mobile FR20 và AI summary FR21. AI auto-approve/OCR/risk decision không thuộc P0. Nếu có CR cho AI summary, dùng namespace `TC-AI-*` riêng; AI không được thay đổi state, route hoặc decision.

## 3. Test levels và pipeline

| Cấp | Mục tiêu | Khi chạy |
|---|---|---|
| Static/spec | Link, Mermaid, API/schema diff, secret/SCA | Mọi PR |
| Unit/domain/property | Guard, state transition, rule boundaries, canonical hash | Mọi PR |
| DB contract/migration | Fresh install, upgrade, FK/CHECK/unique/RLS/trigger | PR có DB; main/RC |
| API contract | Status/error/schema/idempotency/auth matrix | Mọi PR/main |
| Component/integration | DB, storage, scanner, scheduler, worker | Main/RC |
| E2E UI | A/B/C critical path, conflict, accessibility | Main smoke; nightly full |
| Security | IDOR, CSRF, session, injection, file, DAST | Nightly và pre-release |
| Concurrency/fault | Race, deadlock, partial commit, stale lease | Nightly và pre-release |
| Performance/resilience | 20 VU profile, backlog/restart/failure | Pre-release |
| Migration/DR | Upgrade/rollback/DB-object point-in-time restore | Trước G4 |
| UAT/smoke | Khách hàng A/B/C; kiểm tra production giới hạn | G4/G5 |

Không dùng phần trăm code coverage làm gate duy nhất. Gate bắt buộc là 100% AC, transition, role/scope matrix và rule boundary có test. Nên mutation-test các authorization/state/rule guards. Flaky test là defect; quarantine phải có owner và hạn, không rerun để che lỗi.

## 4. Risk-based testing

Thang điểm: Probability `L=1, M=2, H=3, VH=4`; Impact `Medium=2, High=3, Critical=4`; Score = P×I.

| Risk | Mô tả | P | I | Score | Kiểm soát / TC chính |
|---|---|---:|---:|---:|---|
| R01 | Đọc/quyết định trái quyền, vi phạm SoD | 3 | 4 | 12 | RBAC/scope/404; TC023–026,032,040,051,058,068–069,073 |
| R02 | Hai quyết định hoặc side effect mâu thuẫn | 4 | 4 | 16 | version/idempotency/unique/barrier; TC034,038,042,045,054,056–060,097 |
| R03 | Commit một phần, thiếu audit/outbox | 3 | 4 | 12 | một transaction + fault injection; TC028,066,096 |
| R04 | Sai rule/ngưỡng/release | 3 | 3 | 9 | release bất biến + decision table; TC010–012,027,029,031,033,075,097 |
| R05 | Tệp độc hại hoặc liên kết chéo request | 4 | 3 | 12 | private storage/scan/FK/quota lock; TC014–020,050,076,079,094 |
| R06 | Mất/trùng SLA/outbox event | 4 | 3 | 12 | stage identity/dedupe/lease; TC061–067,087 |
| R07 | Audit bị sửa hoặc không verify được | 2 | 4 | 8 | append-only/hash/checkpoint; TC096 |
| R08 | Purge sai hoặc phá legal hold | 2 | 4 | 8 | case scope/dual control/dry-run; TC083–085 |
| R09 | Restore DB và object lệch mốc | 3 | 4 | 12 | versioning/manifest/reconcile; TC089–091 |
| R10 | Session/CSRF/injection compromise | 3 | 3 | 9 | hardened session/allowlist; TC001–006,071–077 |

R01–R06 và R09 phải hoàn tất trước khi chấp nhận release candidate.

## 5. Dữ liệu kiểm thử chuẩn

| Nhóm | Fixture đề xuất |
|---|---|
| Clock | `T0=2026-10-01T02:00:00Z`; chỉ fake clock trong TEST |
| Requester | R1/R2 ở hai phòng khác nhau |
| Approver | M1/M2; F1/F2 cho ngưỡng EQUIPMENT |
| Executor | E1/E2; actor bị disable X1 |
| Acceptor | R1 hoặc actor A1 có role; luôn khác executor |
| Admin/Audit | O1, PA1, AUD_SCOPE, AUD_OTHER, SU1 |
| Release | EQ1 active, EQ2 draft/published cạnh tranh |
| Amount | 9,999,999; 10,000,000; 50,000,000; 50,000,001 VND |
| File | CLEAN/QUEUED/ERROR/INFECTED; MIME thật/giả; 10MiB biên; file thứ 5/6 |
| Isolation | `run_id`, schema/test tenant và storage prefix riêng cho từng run |

Mỗi test tự tạo hoặc reset data; không phụ thuộc test trước. Dataset table-driven chỉ PASS khi mọi row có expected riêng và đều PASS. Không dùng production dump.

## 6. Mẫu test case cấp doanh nghiệp

```text
ID / Title:
Objective / Risk:
Trace: SRC, KD, FR/AC, BR/NFR, UC, API, entity, diagram transition
Level / Type / Priority / Gate:
Preconditions: build, config release, actor/scope, state, clock, dependency health
Test data:
Steps:
Expected per step: HTTP/error + state/version + DB rows + audit/outbox/idempotency
Postconditions / forbidden side effects:
Cleanup:
Automation owner / test path:
Execution: commit, image digest, DB/config version, environment, tester, UTC time
Actual result / Evidence:
Status: NOT RUN | PASS | FAIL | BLOCKED
Defect / Retest / Regression scope:
```

### Oracle bắt buộc cho command ghi

Ngoài HTTP response, phải assert:

1. request status/version/current revision/instance/step/attempt;
2. đúng một history record; không có row thừa;
3. participant và SLA đúng target/deadline;
4. audit actor/correlation/before-after/seq/prev_hash;
5. outbox event/dedupe và idempotency payload hash/response;
6. replay cùng key/cùng payload trả cùng kết quả;
7. cùng key/khác payload conflict;
8. không rò/ghi chéo request và transaction lỗi rollback toàn bộ.

## 7. Ma trận role và state áp cho mọi command

### Role/scope matrix

- đúng actor và đúng scope;
- authenticated nhưng sai role;
- đúng role nhưng sai department/type scope;
- participant lịch sử đã mất role;
- disabled user hoặc stale session/security epoch;
- service/worker account gọi command nghiệp vụ;
- duplicate/replay bởi cùng và khác actor.

### State/concurrency matrix

- trạng thái hợp lệ;
- từng trạng thái trước/sau không hợp lệ;
- terminal state;
- stale `expected_version`;
- same key/same payload và same key/different payload;
- hai command cạnh tranh dùng barrier và hai DB connection thật;
- lock timeout/deadlock retry hữu hạn; không dùng `sleep` để phỏng đoán race.

## 8. Danh mục 100 test case hiện hành

Các bước/expected đầy đủ vẫn nằm trong tài liệu 04. Danh mục này dùng để lập kế hoạch, dashboard và trace từ sơ đồ.

| Khoảng | Nội dung | Test case |
|---|---|---|
| TC001–006 | Auth/session | Đăng nhập; thông báo không lộ tài khoản; rate limit; hai timeout; disable/logout; password/reset |
| TC007–012 | Identity/config | Import nguyên tử; chặn cycle; scope không ngầm; publish; published immutable/clone; validate config |
| TC013–022 | Draft/file/form | Stale draft; upload/link; size/count/quota; MIME spoof; scanner fail closed; infected/IDOR; cross-request; unlink history; 3 form; field boundaries |
| TC023–026 | Read authorization | IDOR mọi bề mặt; OPS metadata; department snapshot; participant/read revocation |
| TC027–033 | Submit/routing | Snapshot; rollback audit/outbox; release race; idempotent replay; 1/2/3-level thresholds; order/SoD; unresolved route |
| TC034–042 | Approval/withdraw/reassign | One decision; reject reason; needs-info/resubmit; withdraw states/race; reassign giữ SLA/SoD; next actor unavailable; revoke-vs-approve |
| TC043–055 | Execution/acceptance | Unable; claim; double claim; reassign running; B complete; C wait; blocked; evidence ownership; acceptor; immutable result; rework; double accept; disabled executor |
| TC056–060 | Concurrency/idempotency | Concurrent create; reassign-vs-decision; replay after revoked read; expired key/tombstone; deadlock retry |
| TC061–070 | SLA/outbox/notification | Reminder; catch-up breach; close-before-scan; SLA continuity; stale lease; crash-before-ACK; finite retry/replay; private/read-idempotent; disabled recipient; integrity |
| TC071–079 | Security/API/storage | CSRF/cookie; fixation/secrets; role/mass assignment; stored XSS; injection; traversal; TLS/CORS/headers; rate/cursor; rescan/storage error |
| TC080–085 | UI/ops/privacy | 4 tabs/responsive; keyboard/zoom/form error; logging/health; retention config; legal hold/purge; data-subject rights/export |
| TC086–092 | NFR/release/DR | Standard load; backlog recovery; compatible migration; consistent restore; object mismatch; rollback with new data; cutover rehearsal |
| TC093–098 | Report/DB/audit/race | Denominator; composite FK; unique/check state; audit/checkpoint; publish-vs-submit; linked replacement scope |
| TC099 | UAT | Diễn tập A/B/C với khách hàng |
| TC100 | Production | Smoke giới hạn sau deploy |

### Danh sách tên chính xác để quản lý test repository

```text
TC001 Đăng nhập thành công
TC002 Thông báo đăng nhập không tiết lộ tài khoản
TC003 Giới hạn đăng nhập theo user và IP
TC004 Hết hạn phiên theo hai đồng hồ
TC005 Disable và logout hủy phiên
TC006 Đổi mật khẩu và reset có kiểm soát
TC007 Import tổ chức và role nguyên tử
TC008 Chặn chu kỳ và lỗi import
TC009 Scope không có giá trị ngầm
TC010 Publish release đầu tiên có audit
TC011 Published bất biến và clone
TC012 Validation cấu hình đầy đủ
TC013 Lưu nháp chống ghi đè
TC014 Upload hợp lệ và liên kết
TC015 Biên size số tệp và quota
TC016 Giả phần mở rộng và nội dung
TC017 Scanner lỗi phải đóng an toàn
TC018 Tệp bị nhiễm và tải trái phép
TC019 Chặn tệp khác hồ sơ
TC020 Bỏ tệp nháp không xóa lịch sử
TC021 Ba form hợp lệ
TC022 Biên dữ liệu biểu mẫu
TC023 IDOR qua mọi bề mặt đọc
TC024 OPS chỉ thấy metadata
TC025 Chuyển phòng không đổi snapshot
TC026 Quyền participant sau gán thay và thu hồi đọc
TC027 Submit tạo snapshot đầy đủ
TC028 Audit hoặc outbox lỗi rollback
TC029 Release đổi trong lúc soạn
TC030 Replay key và conflict payload
TC031 Ngưỡng một hai ba cấp
TC032 Thứ tự ba cấp và SoD
TC033 Không giải được tuyến
TC034 Một quyết định mỗi step
TC035 Reject và lý do
TC036 Needs info rồi duyệt lại từ đầu
TC037 Hủy theo trạng thái
TC038 Hủy cạnh tranh duyệt cuối
TC039 Gán thay người duyệt giữ SLA
TC040 Gán lại không trùng người đã duyệt
TC041 Actor kế tiếp mất quyền
TC042 Thu hồi quyền đồng thời với approve
TC043 Báo không thể nhận
TC044 Nhận việc thành công
TC045 Người khác và hai lần claim
TC046 Gán executor đang làm
TC047 Mẫu B hoàn tất khi nộp
TC048 Mẫu C chờ nghiệm thu
TC049 Báo vướng không dừng SLA
TC050 Bằng chứng phải thuộc executor hiện hành
TC051 Nghiệm thu đúng người
TC052 Không sửa kết quả đã nộp
TC053 Rework tạo vòng nhận việc mới
TC054 Không nghiệm thu hai lần
TC055 Rework khi executor bị khóa
TC056 Hai lệnh create cùng key
TC057 Cạnh tranh reassign và quyết định
TC058 Replay sau thu hồi quyền đọc
TC059 Key hết hạn và tombstone
TC060 Timeout deadlock và retry
TC061 Nhắc tại 50 phần trăm
TC062 Quét bù sau hạn
TC063 Đóng stage trước scan
TC064 SLA không reset khi claim gán thay
TC065 Lease cũ bị từ chối
TC066 Crash giữa notification và ACK
TC067 Retry hữu hạn và replay
TC068 Thông báo riêng tư và read idempotent
TC069 Recipient bị khóa trước delivery
TC070 Toàn vẹn SLA cùng hồ sơ
TC071 CSRF và thuộc tính cookie
TC072 Session fixation và secret
TC073 Giả role và mass assignment
TC074 Stored XSS ở trường plain text
TC075 Injection ở filter và rule
TC076 Path traversal và tên tệp
TC077 TLS CORS và header an toàn
TC078 Giới hạn API và cursor
TC079 Quét lại tệp và lỗi storage
TC080 Bốn tab và giao diện responsive
TC081 Bàn phím zoom và lỗi form
TC082 Log và health có thể vận hành
TC083 Cấu hình retention trước dữ liệu thật
TC084 Legal hold và purge có kiểm soát
TC085 Quyền chủ thể và export giới hạn
TC086 Tải chuẩn và phân bố nghiệp vụ
TC087 Khôi phục backlog và SLA độ trễ
TC088 Migration nâng cấp tương thích rollback
TC089 Restore tới mốc DB và object nhất quán
TC090 Phát hiện object lệch mốc backup
TC091 Rollback sau có dữ liệu mới
TC092 Cutover rehearsal toàn trình
TC093 Báo cáo và mẫu số
TC094 FK ghép của revision tệp và attempt
TC095 Unique và CHECK trạng thái
TC096 Audit chống sửa và checkpoint
TC097 Publish cạnh tranh submit
TC098 Thay phạm vi tạo hồ sơ liên kết
TC099 Diễn tập nghiệp vụ A B C cùng khách hàng
TC100 Smoke production sau triển khai
```

## 9. RTM từ use case và sơ đồ

| Requirement/UC | Activity | Sequence | TC chính |
|---|---|---|---|
| UC01 Auth/session | — | SD-01 | TC001–006,071–072 |
| UC02 Config release | — | SD-09 | TC010–012,029,075,097 |
| UC03 Draft/file | AD-02 | SD-02 | TC013–022,050,076,079 |
| UC04 Submit | AD-02 | SD-03 | TC027–033,056,094,097 |
| UC05 Read/evidence | — | SD-10 | TC023–026,068–069 |
| UC06 Decision | AD-03 | SD-04 | TC031–042,057–060 |
| UC07 Resubmit | AD-02/03 | SD-03/04 | TC029,031,036,097 |
| UC08 Withdraw | AD-01 | SD-05 | TC037–038,057,060 |
| UC09 Reassign | AD-05 | SD-07 | TC026,039–040,046,055,057,064 |
| UC10 Claim/unable | AD-04 | SD-06 | TC043–046 |
| UC11 Issue/result | AD-04 | SD-06 | TC047–050,052 |
| UC12 Accept/rework | AD-04 | SD-06 | TC048,051–055 |
| UC13 Notification | AD-06 | SD-08/10 | TC068–069 |
| UC14 SLA/delivery | AD-06 | SD-08 | TC061–070,082,087 |
| UC15 Report/audit | — | SD-10 | TC023–026,093,096 |
| UC16 AI Summary | Ngoài P0, namespace được giữ cho FR21/P1 | Chưa thiết kế As-is | Chỉ tạo `TC-AI-*` sau khi CR cho P1 được duyệt; không dùng TC001–TC100 để ngầm nghiệm thu AI |
| UC17 Identity/org | — | SD-01 (epoch effect) | TC005–009,042,073 |
| End-to-end A/B/C | AD-01 | SD-03/04/06 | TC099–100 |

### RTM bổ sung cho state và kiến trúc

| Artefact | Yêu cầu/invariant | TC chính |
|---|---|---|
| ST-01–04 | Request/instance/step/attempt state machine | TC027–060, TC094–095 |
| ST-05 | Attachment scan/link state | TC014–020, TC050, TC079 |
| ST-06–07 | SLA/outbox state | TC061–070, TC087 |
| ST-08 | Config release immutable lifecycle | TC010–012, TC029, TC097 |
| AR-01–03 | Scope và module boundaries | TC021, TC023–028, TC099 |
| DP-01 | Deployment, observability, backup | TC077, TC082, TC088–092, TC100 |
| DFD-00/01 | Data flows và privacy boundary | TC023–026, TC068–069, TC083–085 |
| SEC-01 | Trust boundary, session, RLS, privileged path | TC001–009, TC023–026, TC071–077 |
| ER-01–04 | 30-table domain relationships | DB-VAL-001–098, TC094–096 |

Mỗi nhánh `alt`/decision mới trong diagram phải thêm ít nhất một negative TC và cập nhật bảng này trong cùng change request.

## 10. Ca mẫu triển khai tự động

### TC028 — Audit hoặc outbox lỗi phải rollback

| Trường | Nội dung |
|---|---|
| Objective/Risk | Chứng minh không commit một phần khi audit hoặc outbox lỗi; R03 Critical |
| Preconditions | DRAFT hợp lệ, route resolve được, file CLEAN, release active; fault injection được kiểm soát |
| Steps | 1) Bật fault tại audit insert; submit với key K1. 2) Query domain/audit/outbox/idempotency. 3) Tắt fault và retry đúng K1. 4) Lặp lại với fault outbox/key K2. |
| Expected | Lần lỗi trả xác định; request vẫn DRAFT/cùng version; không revision/instance/step/SLA/audit/outbox/idempotency dở. Retry thành công tạo đúng một bộ record và PENDING_APPROVAL. |
| Evidence | API trace/correlation; transaction log đã che secret; query count trước/sau; audit chain verify |

### TC038 — Withdraw cạnh tranh duyệt cuối

| Trường | Nội dung |
|---|---|
| Objective/Risk | Chứng minh một kết quả commit và không vừa cancel vừa approved; R02 Critical |
| Preconditions | PENDING_APPROVAL ở final ACTIVE step; requester và approver có session riêng |
| Steps | Hai client chờ barrier; đồng thời gửi withdraw và approve với cùng expected_version nhưng key khác; lặp nhiều vòng với thứ tự lock đảo. |
| Expected | Chính xác một lệnh thành công; lệnh kia 409. Nếu withdraw thắng: CANCELLED, no decision. Nếu approve thắng: state theo A/B/C, không CANCELLED. Một audit/outbox cho outcome thắng; không dangling SLA. |
| Evidence | Timestamp/barrier trace, DB transaction IDs, state/history/audit/outbox queries |

### TC056 — Hai lệnh create cùng key

| Trường | Nội dung |
|---|---|
| Objective/Risk | Idempotency dưới concurrency; R02 |
| Steps | Hai connection đồng thời gửi cùng actor+endpoint+key+payload; sau đó replay tuần tự; cuối cùng đổi payload nhưng giữ key. |
| Expected | Một domain commit; hai caller nhận cùng status/body/request_id; replay không tạo row; payload khác nhận 409; audit/outbox chỉ một. |

### TC066 — Crash giữa notification và ACK

| Trường | Nội dung |
|---|---|
| Objective/Risk | Không mất/trùng notification khi worker chết; R03/R06 |
| Steps | Claim event; fault-inject process death tại các điểm trước insert, sau insert trước ACK và sau ACK; chờ lease hết; worker khác tiếp quản. |
| Expected | Cuối cùng event SENT và đúng một notification theo dedupe; stale lease không ACK; không gửi nội dung cho recipient đã disable. |

### TC089 — Restore DB/object nhất quán

| Trường | Nội dung |
|---|---|
| Objective/Risk | Chứng minh RPO/RTO và mốc chung; R09 Critical |
| Steps | Ghi workload có file; lấy DB LSN/time + object manifest; phát sinh ghi mới; restore môi trường cô lập tới mốc; reconcile ID/version/size/SHA256; verify audit/checkpoint; đo RPO/RTO. |
| Expected | Không dangling reference/object; hash khớp; dữ liệu sau mốc được liệt kê để xử lý, không im lặng mất; RPO ≤15m/RTO ≤4h hoặc FAIL. |

### TC099 — UAT A/B/C

| Trường | Nội dung |
|---|---|
| Objective | PO/chủ quy trình xác nhận ba lifecycle và ngoại lệ trọng yếu bằng dữ liệu giả |
| Steps | A: LEAVE submit→approve→complete. B: ACCESS submit→approve→claim→result→complete. C: EQUIPMENT theo các ngưỡng, result→rework→claim lại→accept. Xen kẽ reject, needs-info và quyền sai. |
| Expected | Hành vi/nhãn/lịch sử/SLA/bằng chứng đúng baseline; người UAT ký actual result và issue list. Không dùng UAT để hợp thức hóa scope chưa ký. |

## 11. Entry/exit và quality gates

### SIT entry

- baseline/CR và design review hoàn tất;
- release candidate có commit/image/config/DB version;
- fresh migration + seed tái lập được;
- DB/storage/scanner/worker/clock/log/evidence endpoint khỏe;
- QA có actor/scope và quyền đọc evidence, không có secret production.

### G3 — trước UAT

- `TC001–TC087` và `TC093–TC098` PASS;
- không `NOT RUN`, `BLOCKED`, S0 hoặc S1 trong phạm vi gate;
- 100% AC/BR/NFR được trace và có evidence;
- NFR đạt profile KD05 đã ký.

### G4 — trước cutover

- `TC088–TC092` và `TC099` PASS;
- restore/cutover rehearsal có actual RPO/RTO;
- UAT, KD06, KD08, manifest/backup/rollback owner hoàn tất;
- không S0/S1; S2 chỉ waiver có PO+QA, workaround, owner và due date.

### G5 — sau deploy

- `TC100` PASS trên tài khoản/phòng kiểm tra đã duyệt;
- đối soát count/hash không mất dữ liệu;
- theo dõi ít nhất 60 phút: 5xx <0.1%, p95 đúng profile, backlog ≤120s, DEAD=0;
- release owner ký GO hoặc thực hiện rollback.

## 12. Severity và quản lý defect

| Severity | Định nghĩa |
|---|---|
| S0 | Rò/mất dữ liệu, quyết định trái quyền, audit/restore không tin cậy, sự cố an toàn nghiêm trọng |
| S1 | Core lifecycle bị chặn, route/state sai, duplicate side effect, không có workaround chấp nhận được |
| S2 | Chức năng phụ suy giảm, có workaround kiểm soát được |
| S3 | Trình bày/cosmetic, không làm sai nghiệp vụ hoặc accessibility bắt buộc |

Priority do release owner/PO/QA quyết định theo rủi ro và thời điểm, không tự đồng nhất với severity. Defect phải liên kết TC, build, evidence, impact, owner, fix version, retest và regression scope.

## 13. Nếu kích hoạt AI summary ở P1

Tạo CR và suite riêng tối thiểu:

- `TC-AI-001` summary đúng request/revision, tiếng Việt, không sửa nguồn;
- `TC-AI-002` factual grounding, không bịa amount/date/actor;
- `TC-AI-003` prompt injection trong field/PDF không đổi policy/tool/quyền;
- `TC-AI-004` authorization/privacy, không cross-request/department;
- `TC-AI-005` output malformed/oversize/unsafe fallback;
- `TC-AI-006` timeout/429/5xx fail-open về đọc thủ công, không block workflow;
- `TC-AI-007` model/prompt/config version và golden-set regression;
- `TC-AI-008` human evaluation factuality/coverage/harmlessness;
- `TC-AI-009` jailbreak/OCR poison/malicious PDF/unicode spoofing;
- `TC-AI-010` token budget, p95, rate limit, circuit breaker;
- `TC-AI-011` feedback/audit/retention không sửa lịch sử;
- `TC-AI-012` guard cấm AI approve/reject/resolve route hoặc đổi state.

Các TC AI không thay thế bất kỳ TC P0 nào và không được đưa vào gate P0 nếu CR chưa ký.
