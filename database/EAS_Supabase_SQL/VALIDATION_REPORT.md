# EAS 2.0.1 — Báo cáo kiểm thử lớp cơ sở dữ liệu

Kết quả: **98/98 kiểm tra/giai đoạn PASS; 0 FAIL**. Thời điểm lượt kiểm chính: `2026-09-22T02:47:44.192Z`.

Engine thực thi: `PostgreSQL 18.3 (PGlite 0.5.8) on wasm32-unknown-emscripten, compiled by emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 3.1.74 (1092ec30a3fb1d46b1782ff1b4db5094d3d06ae5), 32-bit`. SQL được cài và thực thi bằng engine PostgreSQL trong PGlite, không dùng mock parser.

Đối chiếu trực tiếp văn bản DOCX nguồn với catalog đã cài: **30/30 bảng, 260/260 cột, không thiếu hoặc thừa tên bảng/cột**. Bằng chứng từng bảng trong `source_coverage.json`; phép đối chiếu này không thay kiểm thử các quy tắc do service thực hiện.

| Hạng mục catalog | Số lượng thực tế |
|---|---:|
| Bảng nghiệp vụ | 30 |
| Cột | 260 |
| Khóa ngoại | 72 |
| CHECK constraints | 139 |
| Chỉ mục, gồm PK/UNIQUE và index truy vấn | 127 |
| Business triggers, không tính FK trigger nội bộ | 52 |
| RLS policies | 60 |

## Cách chạy và kết quả tái lập

Lượt chính chạy installer, fixture development, các thao tác hợp lệ/bị từ chối, kiểm constraint deferred, rollback fixture, seed độc lập và kiểm installer từ chối chạy lại. Các ca âm kiểm **SQLSTATE dự kiến**, không tính mọi exception bất kỳ là PASS.

Sau đó chạy lại **nguyên văn những file SQL bàn giao** trong DB tạm mới qua `validation/reproduce.mjs`: kết quả `PASS`, `86` thông báo assertion SQL PASS; các thao tác thành công còn lại thực thi trực tiếp và phải hoàn tất không lỗi. Số 86 thông báo SQL không phải một bộ 86 ca nghiệp vụ khác với lượt 98 kiểm tra/giai đoạn chính. Dữ liệu fixture rollback về 0 user/request; demo seed commit được trên DB trống; file verify chạy được trước và sau seed. Hash byte SHA256 của các vector seed khớp giá trị cung cấp.

## Giới hạn của kết quả

- Không kết nối hoặc thay đổi project Supabase của khách hàng. Các role `anon`, `authenticated`, `service_role` được dựng trong DB thử để kiểm grants/RLS; chưa phải xác minh toàn bộ cấu hình Data API của project thật.
- PGlite chạy một backend. Chưa kiểm đa kết nối, deadlock/race, isolation dưới tải, connection pooling hoặc hiệu năng dữ liệu lớn.
- Tệp fixture chỉ có metadata, không có object thật, chữ ký tải xuống hoặc virus scan. Không suy ra storage đã hoạt động từ PASS của FK/scan_state.
- Thao tác workflow trong fixture kiểm lớp dữ liệu; không gọi API, xác thực session, kiểm role theo scope, worker thật hoặc UI. Một số timestamp tương lai và hash audit request chỉ là dữ liệu cô lập cho kiểm constraint; các giá trị audit seed chuẩn có vector riêng.
- Không xác nhận mọi business command luôn phát audit/outbox/idempotency; điều đó cần integration test và fault injection trên backend.
- Không thay đổi 100 ca nghiệm thu trong tài liệu 04 thành PASS. Chưa kiểm backup/restore, object retention, vận hành/pháp lý hoặc go-live.

## Các ca/giai đoạn đã thực thi

| # | Kiểm tra | Kết quả |
|---:|---|---|
| 1 | DDL install and commit | PASS |
| 2 | Bootstrap has 3 active demo releases and 10 unusable demo accounts | PASS |
| 3 | All 30 tables have RLS enabled | PASS |
| 4 | API cannot rewrite audit head directly | PASS |
| 5 | NULL-scoped duplicate membership rejected | PASS |
| 6 | GLOBAL membership with department rejected | PASS |
| 7 | Role date interval rejected | PASS |
| 8 | Department cycle detected at deferred check | PASS |
| 9 | Manager cycle detected at deferred check | PASS |
| 10 | Published release immutable | PASS |
| 11 | Active release cannot cross request type | PASS |
| 12 | Unknown request status rejected | PASS |
| 13 | Draft release must match type | PASS |
| 14 | Origin owner cannot differ | PASS |
| 15 | Money must not be placed on leave | PASS |
| 16 | Money upper bound enforced | PASS |
| 17 | Version increment required | PASS |
| 18 | Draft cancellation allowed | PASS |
| 19 | Terminal request cannot reopen | PASS |
| 20 | Deferred circular FKs validate after all submissions | PASS |
| 21 | Revision cannot cross release type | PASS |
| 22 | Current revision cannot cross request | PASS |
| 23 | Workflow revision cannot cross request | PASS |
| 24 | Workflow composite FK isolates request ownership | PASS |
| 25 | Only one ACTIVE instance per request | PASS |
| 26 | Approval step cannot cross request | PASS |
| 27 | Only one ACTIVE step per instance | PASS |
| 28 | Requester cannot approve own request | PASS |
| 29 | Same approver cannot occupy two steps | PASS |
| 30 | Wrong actor cannot decide current step | PASS |
| 31 | Approval decision cross-request FK | PASS |
| 32 | Reject requires reason length | PASS |
| 33 | Only one open SLA stage per request | PASS |
| 34 | SLA subtype requires exactly one correct target | PASS |
| 35 | SLA target cannot cross request | PASS |
| 36 | SLA deadline cannot be extended | PASS |
| 37 | SLA alert deduplication | PASS |
| 38 | SLA alert cannot cross request | PASS |
| 39 | Lifecycle A completes after approval | PASS |
| 40 | Second approval decision rejected | PASS |
| 41 | Revision immutable even for schema owner | PASS |
| 42 | Decision immutable even for schema owner | PASS |
| 43 | One current execution attempt per instance | PASS |
| 44 | Execution cannot exist on A | PASS |
| 45 | RUNNING executor cannot be overwritten | PASS |
| 46 | Execution issue cannot cross request | PASS |
| 47 | B finish without evidence rejected at commit boundary | PASS |
| 48 | Lifecycle B completes with evidence | PASS |
| 49 | Execution attempt composite FK rejects cross-request target | PASS |
| 50 | Evidence must be uploaded by executor | PASS |
| 51 | Submitted result cannot be changed | PASS |
| 52 | Wrong acceptor cannot accept | PASS |
| 53 | Acceptance decision cannot cross request | PASS |
| 54 | Executor cannot accept own work even after reassignment | PASS |
| 55 | REWORK creates new attempt without replacing prior result | PASS |
| 56 | RUNNING reassignment preserves SLA identity and deadline | PASS |
| 57 | Lifecycle C completes after acceptance with retained attempts | PASS |
| 58 | Unscanned file cannot be attached | PASS |
| 59 | Cross-request file attachment rejected | PASS |
| 60 | Path separator in original filename rejected | PASS |
| 61 | File larger than 10 MiB rejected | PASS |
| 62 | Unsupported MIME rejected | PASS |
| 63 | Sixth selected draft file rejected | PASS |
| 64 | Referenced attachment cannot be tombstoned | PASS |
| 65 | Historical revision cannot receive late files | PASS |
| 66 | Aggregate quota 200 MiB enforced under request lock | PASS |
| 67 | Audit append advances request head atomically | PASS |
| 68 | Audit previous hash mismatch rejected | PASS |
| 69 | API cannot delete audit event | PASS |
| 70 | Outbox dedupe key uniqueness | PASS |
| 71 | PROCESSING requires lease token and attempts | PASS |
| 72 | DEAD requires four attempts | PASS |
| 73 | Notification cannot discard event request scope | PASS |
| 74 | Notification duplicate delivery rejected | PASS |
| 75 | Notification first read cannot be removed | PASS |
| 76 | Idempotency scope uniqueness | PASS |
| 77 | Worker cannot approve a request | PASS |
| 78 | Idempotency response cannot clear before 7 days | PASS |
| 79 | Idempotency tombstone cannot delete before 30 days | PASS |
| 80 | Worker can claim outbox with valid lease | PASS |
| 81 | Worker can ACK outbox | PASS |
| 82 | Worker can store scanner result | PASS |
| 83 | anon cannot read private EAS data | PASS |
| 84 | authenticated cannot read private EAS data | PASS |
| 85 | service_role cannot read private EAS data | PASS |
| 86 | Backup role can read all request rows | PASS |
| 87 | Backup role cannot mutate | PASS |
| 88 | Privacy deletion needs case context | PASS |
| 89 | Open legal hold blocks authorized privacy deletion | PASS |
| 90 | Case for different subject cannot delete request | PASS |
| 91 | Released hold cannot be reopened by update | PASS |
| 92 | Approved privacy deletion works after hold release | PASS |
| 93 | All remaining deferred constraints pass | PASS |
| 94 | Three core lifecycles preserve complete final state | PASS |
| 95 | Regression fixture transaction rolled back | PASS |
| 96 | Demo seed standalone commit | PASS |
| 97 | Initial installer refuses rerun without mutation | PASS |
| 98 | Seed hash vectors SHA256 bytes match all supplied values | PASS |

## Điều kiện kiểm tiếp trên project đích

Chạy 00 và 02 trên project thử nghiệm Supabase thực; chạy 03 trên schema EAS trống trước demo. Sau đó chạy các ca concurrency, storage/scanner, API/RBAC, migration framework, backup/restore và NFR/UAT theo bộ tài liệu v2. Tài khoản runtime phải dùng đúng nhóm quyền; tách secret migration/privacy khỏi backend. Chỉ nghiệm thu go-live khi các bằng chứng ở lớp ứng dụng/hạ tầng đã được thu thập.
