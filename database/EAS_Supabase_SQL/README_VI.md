# EAS 2.0.1 — Bộ SQL PostgreSQL cho Supabase

Ngày phát hành: 22/09/2026. Căn cứ: sáu tài liệu EAS v2.0, đặc biệt `03_Du_lieu_va_API_v2.docx`, danh mục DB01–DB30. Đây là bộ cài đặt **lớp cơ sở dữ liệu của phạm vi P0**. Có đủ 30 bảng, 260 cột theo mô hình, khóa chính/ngoại, chỉ mục, ràng buộc, guard, quyền DB và dữ liệu tham chiếu tối thiểu. Không có placeholder trong script cài đặt.

## 1. Chọn đúng file

| File | Mục đích | Môi trường |
|---|---|---|
| `00_eas_supabase_schema.sql` | Cài toàn bộ schema, quyền và seed tham chiếu trong một transaction | Supabase/PostgreSQL mới, chưa có schema/role EAS |
| `02_verify_installation_READ_ONLY.sql` | Đọc và kiểm cấu trúc, seed, FK, guard, RLS, quyền | Sau khi cài; dùng được trên production |
| `03_database_regression_DEV_ONLY.sql` | Fixture tự tạo; kiểm dữ liệu hợp lệ/bị từ chối; ROLLBACK cuối file | DB thử nghiệm riêng, đã chạy 00 nhưng chưa chạy 01 |
| `01_demo_seed_DEV_ONLY.sql` | Hai phòng, 10 tài khoản, 12 phân quyền, ba cấu hình mẫu đã publish | Chỉ DB development trống; tùy chọn |
| `DATA_DICTIONARY.md`, `schema_catalog.json` | Danh mục đầy đủ cột, nullable, default, constraint và index | Tham chiếu developer/DA/DE |
| `source_coverage.json` | Đối chiếu trực tiếp tên bảng/cột với DOCX nguồn: 30 bảng, 260 cột, không thiếu/thừa | Bằng chứng bao phủ mô hình |
| `VALIDATION_REPORT.md`, `validation_results.json` | Kết quả đã chạy và phạm vi chưa kiểm chứng | Bằng chứng kiểm thử DB |
| `demo_canonical_hash_vectors.json` | Chuỗi byte chuẩn và hash của seed để đối chiếu | Fixture, không phải thư viện canonicalization |
| `validation/` | Chạy lại SQL bằng PostgreSQL WASM trong DB tạm | Máy developer có Node.js |
| `source_manifest.json`, `SHA256SUMS.txt` | Truy nguyên tài liệu nguồn và kiểm tra file bàn giao | Quản lý phiên bản |

## 2. Cài trên Supabase

1. Dùng project thử nghiệm trước. Mở **SQL Editor** bằng tài khoản quản trị DB `postgres`. Kiểm tra phiên bản PostgreSQL từ 15 trở lên. Script không cần extension.
2. Chạy **toàn bộ** `00_eas_supabase_schema.sql` một lần. Kết quả cuối phải có `EAS 2.0.1 installed`, `domain_tables = 30`. Không chạy từng đoạn vì có FK vòng và quyền phụ thuộc thứ tự.
3. Chạy `02_verify_installation_READ_ONLY.sql`. Kết quả đầu phải `PASS: EAS 2.0.1 schema checks`. Trong Table Editor/Database chọn schema **eas** để xem bảng.
4. Khi chỉ cần thử dữ liệu: trên DB development mới, chạy 03 trước, rồi tùy chọn 01. File 03 tự rollback dữ liệu nhưng sequence có thể tăng. File 01 cố ý từ chối khi đã có người dùng, release hoặc request; không dùng trên production.
5. Trước khi backend sử dụng production, nạp phòng/người/quyền thật, tạo password hash bằng backend, validate và publish cấu hình đã được duyệt cho cả ba loại, rồi gắn `request_type.active_release_id`. File 02 sẽ báo `REQUIRES_APPROVED_CONFIG_BEFORE_USE` khi chưa có cấu hình; đó là việc thiết lập còn thiếu, không phải lỗi cài bảng.

**Schema đã tồn tại:** bộ cài từ chối và rollback, không dùng `DROP`, không ghi đè dữ liệu và không giả vờ cập nhật bằng `CREATE TABLE IF NOT EXISTS`. Nếu gặp lỗi trong phiên giữ transaction, chạy `ROLLBACK;`, sửa nguyên nhân rồi cài lại trên DB mới. Nâng cấp một hệ thống đang có dữ liệu cần migration chênh lệch được review riêng.

Supabase dùng các schema `auth`/`storage`/`public` cho chức năng khác. Bộ này chỉ tạo **eas** và năm nhóm quyền EAS; không chỉnh dữ liệu ở các schema đó. Không đưa `eas` vào danh sách schema expose của Data API.

## 3. Giữ đúng kiến trúc đăng nhập của tài liệu

Tài liệu quy định backend Django quản lý session và tài khoản `app_user`. Vì vậy **không đổi sang `auth.users` hoặc `auth.uid()` của Supabase**. Client gọi API backend; backend kiểm quyền đọc, scope phòng/loại, vai trò, phiên bản và trạng thái trước mỗi lệnh. Bảy vai trò nghiệp vụ nằm trong `role_membership`, không phải PostgreSQL roles.

| PostgreSQL role | Quyền chính | Cách dùng |
|---|---|---|
| `eas_migration` | Sở hữu schema và DDL | Triển khai/migration; không cấp cho runtime |
| `eas_api` | Dữ liệu nghiệp vụ qua backend; audit chỉ INSERT/SELECT | Login riêng của backend |
| `eas_worker` | Outbox/notification, scanner, SLA breach, checkpoint, cleanup idempotency | Login riêng của worker; không ghi quyết định duyệt/nghiệm thu |
| `eas_backup` | SELECT bảng/sequence | Backup logic theo runbook phù hợp RLS |
| `eas_privacy` | Purge theo case ERASE APPROVED và legal hold | Phiên thao tác riêng, có phê duyệt; không cấp cho API/worker |

Cả năm là **NOLOGIN, NOBYPASSRLS**. Quản trị tạo login kết nối với secret quản lý riêng, rồi cấp đúng một nhóm quyền tương ứng. Ví dụ `GRANT eas_api TO eas_backend_login;` chỉ chạy sau khi login này đã được tạo; giữ `INHERIT`, không cấp đồng thời migration/privacy. Không dùng login `postgres` hoặc Supabase `service_role` làm tài khoản runtime của ứng dụng.

RLS bật trên 30 bảng, chỉ cho nhóm backend/worker/privacy và backup được chỉ định; quyền SQL tiếp tục giới hạn thao tác. Policy cho nhóm backend tin cậy được phép truy cập toàn phạm vi DB vì quyền người dùng cuối được kiểm tại service theo thiết kế gốc. **Đây không phải bộ RLS theo từng người dùng cho frontend truy cập trực tiếp.** `anon`, `authenticated`, `service_role` không được cấp quyền schema/bảng/hàm EAS.

Mọi tài khoản demo có hash bắt đầu `!UNUSABLE_DEMO_`; chúng không đăng nhập được. Không có mật khẩu mặc định. Backend cần dùng Argon2 tương thích cấu hình thực tế, quy trình đổi mật khẩu và `auth_version` đúng SRS.

Các bảng session/migration của Django bị loại khỏi danh mục DB01–DB30 ngay trong tài liệu nguồn. Cài chúng bằng migration của **mã backend thực tế**. ORM phải ánh xạ đúng `eas.<table>` và `password_hash`; dùng state-only/unmanaged mapping hoặc migration state tương ứng để không tạo trùng 30 bảng đã cài. Không dùng nguyên model Django User mặc định rồi kỳ vọng khớp `app_user`. Tài liệu không cung cấp mã backend nên gói này không tạo giả các bảng framework.

## 4. Dữ liệu khởi tạo và phạm vi

Bộ cài production chỉ tạo:

- `security_epoch`: hàng `id=1`, `version=0`.
- `audit_head`: scope `ADMIN`, `seq=0`, hash 64 số 0.
- `request_type`: `LEAVE/A`, `ACCESS/B`, `EQUIPMENT/C`, UUID cố định trong SQL. Chưa có active release.

Không nạp người dùng hoặc publish chính sách chưa được khách hàng duyệt. Demo 01 có đầy đủ liên kết phòng, quản lý, role, resolver và SLA để thử mô hình; `DEMO_PORTAL/READ_BASIC` chỉ là danh mục truy cập giả. Cấu hình demo theo tuyến EQUIPMENT <10 triệu / 10–50 triệu / >50 triệu; ACCESS SLA thực hiện 12 giờ, EQUIPMENT 48 giờ, duyệt/nghiệm thu 24 giờ theo SRS. Seed có bốn `admin_event` và hash vector đi kèm.

P0 gồm hồ sơ A/B/C, duyệt tuần tự, thực hiện/nghiệm thu, tệp, SLA, thông báo nội bộ, audit, cấu hình, idempotency, privacy case và legal hold. Không thêm AI, mobile Android, tự cấp quyền IAM/ERP, thanh toán, quản lý kho tài sản hoặc tự động hóa HR ngoài P0.

## 5. Bất biến trong DB và phần backend phải thực hiện

| Chủ đề | DB bảo vệ | Backend/worker vẫn phải làm |
|---|---|---|
| Quan hệ | 72 FK RESTRICT; FK ghép ngăn tham chiếu chéo request; FK current revision deferred | Chọn current target đúng nghiệp vụ và kiểm quyền trước đọc |
| Workflow | Một instance ACTIVE, step ACTIVE, attempt hiện hành, stage mở; trạng thái/thời điểm; SoD actor của quyết định | Resolve tuyến, kiểm actor active và role còn hiệu lực, tạo/đóng toàn bộ side effect trong cùng transaction |
| Revision/release | Bất biến lịch sử; release published không sửa; một số kiểm tra cấu trúc JSON | JSON Schema đầy đủ, chuẩn hóa NFC/trim, ngày LEAVE, allowlist ACCESS, payload/amount đồng nhất, hash validate trước publish |
| File | FK cùng request, MIME allowlist, mỗi file 10 MiB, tổng 200 MiB, tối đa 5 file/tập, chỉ CLEAN, quote/evidence bắt buộc tại cuối transaction | Kiểm bytes/MIME thật, virus scan, private storage, tải xuống theo quyền, cleanup object ngoài DB |
| SLA | Subtype, target, một stage mở, deadline không bị gia hạn khi đổi người, alert dedupe | Tính giờ theo profile, reminder 50%, lịch chạy worker, đóng stage và đánh breached đúng thời điểm |
| Audit | Append only, seq/prev_hash và head cập nhật nguyên tử | Tính/kiểm SHA256 RFC8785 đúng profile; audit mọi lệnh; checkpoint ngoài quyền ghi ứng dụng |
| Outbox | Dedupe, số lần thử, lease fields, notification khớp request kể cả NULL | Claim/ACK/retry/replay, lease 60 giây, tạo notification và ACK trong cùng transaction |
| Idempotency | Unique actor/scope/key; response hết hạn 7 ngày, tombstone 30 ngày; guard cleanup | Tính request hash, replay trước state guard, HTTP 409/410, không lặp side effect |
| Privacy | Case phù hợp subject, role đặc quyền, hold đang mở chặn xóa lịch sử | Duyệt đúng thẩm quyền, manifest purge, audit ADMIN, xử lý object/backup/export/checkpoint theo chính sách đã duyệt |

CHECK/trigger không thay một service nghiệp vụ. SQL không tự gửi thông báo, không chạy scanner, không xác thực người dùng, không tạo REST API, không chứng minh tuân thủ pháp luật hoặc đủ điều kiện go-live.

## 6. Thứ tự transaction để không vướng FK/guard

Service dùng `READ COMMITTED`; khóa theo tài liệu: `security_epoch` → `request_type` khi submit/publish → `request` → con theo ID → `audit_head` → outbox/idempotency. Gọi `eas.lock_security(false)` trước lệnh nghiệp vụ; thay quyền/người/quản lý dùng `true`, tăng epoch **một lần cho transaction/import**. Trigger bổ sung khóa; nó không tự tăng epoch cho mỗi hàng. Không gọi dịch vụ mạng trong transaction giữ khóa.

Submit/resubmit: kiểm quyền và key → expected_version → cấu hình/actor → INSERT revision → INSERT revision_attachment → INSERT instance/steps/participants/SLA → UPDATE current_revision/status và tăng lock_version đúng 1 → audit/outbox/idempotency → COMMIT. Tệp revision phải chụp trước khi chuyển current_revision. FK vòng deferred được kiểm cuối transaction; FK chéo request vẫn bị từ chối.

Quyết định: INSERT decision khi target đang ACTIVE/SUBMITTED, sau đó đóng target, chuyển trạng thái và mở target tiếp theo. Đóng stage/attempt/instance cũ trước khi tạo hàng hiện hành mới để thỏa partial unique. Tệp kết quả được gắn khi attempt RUNNING; sau đó đổi sang SUBMITTED hoặc FINISHED trong cùng transaction. Cần 1–5 evidence khi kết thúc transaction.

RUNNING reassign: đóng attempt cũ với REASSIGNED → tạo READY mới → đổi `sla_stage.attempt_id` cùng instance, giữ stage ID/deadline → chuyển request về READY_FOR_EXECUTION. REWORK tạo attempt/stage mới. Không sửa executor của attempt đã RUNNING/SUBMITTED hoặc dữ liệu kết quả đã nộp.

Audit: lấy head bằng `eas.lock_audit_head(scope)`, tạo event canonical với seq tiếp theo, tính hash rồi INSERT event; trigger tự nâng head. Không UPDATE head từ runtime. Profile cấu hình của gói được ghi trong hash vectors; backend phải thống nhất chính xác profile này. `validation_hash` còn phải ràng buộc version phần mềm và bộ ca biên; không đồng nhất nó một cách tùy tiện với `content_sha256`.

## 7. Các quyết định triển khai đã làm rõ

| Quyết định | Giá trị |
|---|---|
| Phiên bản | Cú pháp PostgreSQL >=15; đã chạy trên PostgreSQL 18.3/PGlite 0.5.8; cần chạy lại 02/03 trên phiên bản project đích |
| Mã request | `EAS-<năm Asia/Ho_Chi_Minh>-<sequence tối thiểu 6 số>`; sequence toàn cục không reset theo năm, có thể có khoảng trống |
| ID/timestamp/tiền | UUID `gen_random_uuid()` core; UTC timestamptz; BIGINT VND; amount là tổng dự toán, không nhân quantity lần nữa |
| resolved_route | JSON array 1–3 phần tử; mỗi phần tử `{step_no,assignee_id,resolver}` do backend resolve và validate; snapshot không đổi khi gán thay |
| Xóa lịch sử | FK RESTRICT, không cascade. Purge có case đã duyệt và thứ tự xóa rõ; không có job xóa mặc định |
| Lưu tệp | Chỉ metadata, không tạo bucket hoặc object; không giả định Supabase Storage cung cấp versioning S3 |
| object_version | Phải là version/generation thực mà adapter storage bảo đảm truy xuất bất biến; nếu dùng key bất biến để mô phỏng version, phải có contract và kiểm chứng overwrite/delete ở adapter trước go-live |
| Audit canonicalization | Không dùng `jsonb::text` thay RFC8785. Fixture vector có byte/hash kiểm được; production dùng encoder đã kiểm chuẩn |
| Nhóm trusted roles | RLS + SQL grants; schema owner vẫn là đặc quyền triển khai, không phải rào cản chống DBA độc hại |

Purge: đặt `SET LOCAL ROLE eas_privacy` và `SET LOCAL eas.privacy_case_id='UUID_CASE_DA_DUYET'` trong phiên được kiểm soát; khóa security/request, xác minh legal hold. Xóa notification trước outbox; links/decisions/issues/alerts trước cha; stage trước step/attempt; instance trước revision. Gỡ `request.current_revision_id` để cắt vòng rồi mới xóa revision. Xóa request con có `origin_request_id` trước request gốc nếu cùng phạm vi được duyệt. Xóa audit/checkpoint scope REQ trước request khi chính sách cho phép; **không xóa ADMIN** bằng luồng này. `app_user`, release và hồ sơ phê duyệt có retention riêng; không giả định xóa request là đã xóa hết dữ liệu cá nhân ở mọi nơi.

## 8. Kiểm thử và bằng chứng

`VALIDATION_REPORT.md` liệt kê kết quả thực tế. Các file SQL đã được thực thi bởi PostgreSQL engine, không chỉ kiểm cú pháp bằng chuỗi. Để chạy lại độc lập:

```bash
cd validation
npm ci
npm test
```

Runner tạo DB tạm trong bộ nhớ, cài schema, kiểm tra read-only, chạy regression và rollback, chạy demo rồi kiểm tra lại. Không cần Supabase key và không kết nối project của khách hàng.

Đã kiểm DB invariants, seed, phân quyền, các luồng dữ liệu chính và nhánh lỗi. **Chưa chạy trên một project Supabase thật; chưa có kiểm thử đa phiên đồng thời, tải, restore, worker/storage/API hoặc 100 ca nghiệm thu của tài liệu 04.** Vì vậy không đổi trạng thái những ca đó thành PASS và không dùng báo cáo này thay biên bản go-live.

## 9. Nguồn kỹ thuật chính thức

Đối chiếu ngày 22/09/2026; tài liệu EAS là nguồn yêu cầu nghiệp vụ, các trang dưới đây là nguồn cho cơ chế nền tảng.

- Supabase, Database roles: https://supabase.com/docs/guides/database/postgres/roles
- Supabase, Securing your API: https://supabase.com/docs/guides/api/securing-your-api
- Supabase, Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase, Custom schemas: https://supabase.com/docs/guides/api/using-custom-schemas
- PostgreSQL, Constraints: https://www.postgresql.org/docs/17/ddl-constraints.html
- PGlite, PostgreSQL WASM engine: https://pglite.dev/docs/about

Không suy ra giới hạn storage, SLA hạ tầng hoặc cấu hình project Supabase cụ thể từ schema SQL. Các mục đó phải được kiểm trên môi trường triển khai thực tế.
