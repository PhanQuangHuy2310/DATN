# Phản biện hội đồng, điểm mù và hướng xử lý EAS

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-DOC-11 |
| Phiên bản | 1.0 |
| Ngày đánh giá | 09/10/2026 |
| Góc nhìn | Hội đồng CNTT: nghiệp vụ, code, kiến trúc, database, use case, QA và vận hành |
| Trạng thái | Tài liệu chuẩn bị bảo vệ và backlog khắc phục; không thay actual test evidence |

## 1. Kết luận nếu chấm tại thời điểm hiện tại

Nếu bảo vệ ngay, dự án có thể được đánh giá cao ở SRS, mô hình dữ liệu và tư duy kiểm soát rủi ro, nhưng khó đạt điểm xuất sắc vì chưa có ứng dụng end-to-end. Mức hợp lý hiện tại khoảng **5,5–6,0/10**, phụ thuộc cách trình bày trung thực và khả năng demo database/backend foundation. Không nên xin điểm bằng số lượng 68 sơ đồ hoặc 100 test case khi 100 ca ứng dụng chưa chạy.

| Nhóm hội đồng soi | Đánh giá |
|---|---|
| Hiểu nghiệp vụ | Tốt, nếu giải thích rõ EAS ghi nhận phê duyệt/thực hiện chứ không thay HR/IAM/ERP |
| Thiết kế hệ thống | Tốt; modular monolith phù hợp hơn microservices ở P0 |
| Database | Khá mạnh; có invariant, RLS, audit/outbox/idempotency và verification thật |
| Logic code | Mới ở foundation/validation/routing; chưa có command transaction và auth |
| Use case/sơ đồ | Bao phủ rộng; phải giải thích UC16 là P1 và các hình là Target, chưa phải toàn bộ As-is |
| Test | Test design mạnh; execution evidence ứng dụng còn yếu |
| Khả năng triển khai | Chưa đạt vì secret/runtime role/config/UI/worker/storage/restore chưa đóng |
| Khả năng thương mại | Có hướng đi hợp lý nhưng chưa có khách hàng/pilot KPI và unit economics thực |

## 2. Ma trận điểm mù và xử lý

| ID | Mức | Điểm mù hội đồng có thể bắt | Xử lý | Trạng thái/bằng chứng |
|---|---|---|---|---|
| BL01 | High | “Tối đa 30 ngày lịch” bị code tính theo hiệu ngày, có thể cho 31 ngày inclusive | Dùng `(end-start)+1`, test biên 30/31 ngày | **FIXED**, `test_leave_range_is_inclusive_at_30_days` |
| BL02 | High | Tự bàn giao có thể bypass bằng cùng UUID khác kiểu chữ | Canonicalize cả requester/handover trước so sánh | **FIXED**, test UUID uppercase |
| BL03 | High | Code route hỗ trợ toán tử DB không chấp nhận | Thu hẹp về `amount_gt`, `amount_gte` đúng P0 | **FIXED**, negative test `amount_eq` |
| BL04 | High | Route code dựa hoàn toàn vào trigger để bắt default/duplicate/slot lạ | Fail-closed tại domain: final default, ID/priority unique, resolver allowlist | **FIXED**, regression tests |
| BL05 | Critical | Readiness blacklist tên `postgres`, có thể bỏ lọt superuser tên khác | Kiểm capability `rolsuper`, `rolbypassrls`, `rolcreaterole`, `rolcreatedb` | **FIXED**, test nonstandard superuser |
| BL06 | Critical | API login có thể đồng thời kế thừa worker/migration/privacy | Readiness yêu cầu member `eas_api` và không member ba nhóm xung đột | **FIXED**, membership conflict tests |
| BL07 | High | Chỉ kiểm `active_release_id IS NOT NULL` | Join release, yêu cầu PUBLISHED, đúng type/lifecycle | **FIXED**, invalid release test |
| BL08 | High | Template role có thể chạy nguyên password placeholder | Template abort trước DDL nếu placeholder chưa thay | **FIXED**, SQL guard |
| BL09 | Medium | UC01–15 rồi UC17 giống lỗi đánh số | Ghi UC16=FR21 AI Summary/P1 trong RTM; validator bắt UC01–17 | **FIXED**, docs gate |
| BL10 | Critical | `.env` và credential đã nằm trong Git/chat | Rotate; gỡ khỏi index/history theo nhánh được phép; secret gate | **OPEN/BLOCKER** |
| BL11 | Critical | Backend dùng DB admin | Tạo login chỉ thuộc `eas_api`; worker riêng | **OPEN/BLOCKER**, readiness fail-closed |
| BL12 | High | Chưa có active release | POLICY_ADMIN validate/publish profile đã duyệt; không seed mù | **OPEN/BLOCKER** |
| BL13 | Critical | Chưa có auth/session/rate limit/reset/revoke | Xây auth versioned session và TC001–009 | **OPEN** |
| BL14 | Critical | Chưa có command transaction submit/approve | Cài lock order, expected version, idempotency, audit/outbox atomically | **OPEN** |
| BL15 | High | Audit DB nhận hash nhưng backend chưa có RFC8785 implementation | Chọn thư viện JCS được kiểm vector, checkpoint và negative test | **OPEN** |
| BL16 | High | Chưa có storage/scanner adapter | Private object, immutable version, MIME sniffing, AV, signed stream | **OPEN** |
| BL17 | High | Chưa có worker outbox/SLA | Claim/lease/ACK/retry/dead/replay cùng test crash | **OPEN** |
| BL18 | High | Chưa có React UI/admin và accessibility evidence | Triển khai P0 responsive web, keyboard/screen-reader/browser tests | **OPEN** |
| BL19 | High | SQL installer không phải migration upgrade | Tạo migration tăng dần expand/contract và N/N-1 rehearsal | **OPEN** |
| BL20 | High | PGlite không chứng minh concurrency thật | Chạy multi-session PostgreSQL integration TC030/038/056/064 | **OPEN** |
| BL21 | High | Có backup runbook nhưng chưa restore rehearsal | Chạy TC089–092, đo actual RPO/RTO | **OPEN** |
| BL22 | Medium | 100 test case có thể bị trình bày như đã PASS | Giữ NOT RUN, tách 27 foundation tests khỏi acceptance TC | **CONTROLLED** |
| BL23 | Medium | EAS dễ bị hiểu là HR/IAM/procurement platform | Giữ boundary: EAS lưu quyết định/bằng chứng; thao tác ngoài là thủ công P0 | **DOCUMENTED** |
| BL24 | Medium | Pricing là giả định, chưa chứng minh lợi nhuận | Pilot 3–5 khách, đo CAC, effort, margin, conversion | **OPEN** |
| BL25 | High | Property schema sai kiểu có thể gây `TypeError`/HTTP 500 khi validate payload | Kiểm keyword, format, enum và bounds trước khi đọc payload | **FIXED**, malformed-schema regression test |
| BL26 | High | Ngưỡng route âm/thập phân có thể âm thầm không match và rơi về default | Chỉ nhận integer VND trong miền 0–1.000.000.000.000, sai thì fail-closed | **FIXED**, negative/fractional threshold test |

## 3. Câu hỏi nghiệp vụ

### Q01. Hệ thống giải quyết vấn đề gì?

**Trả lời phải có:** chuẩn hóa việc tiếp nhận, phê duyệt tuần tự, theo dõi thực hiện và lưu bằng chứng/audit cho yêu cầu nội bộ. Không trả lời chung chung là “số hóa doanh nghiệp”.

**Bẫy:** nói EAS tự tính phép, tự cấp quyền hoặc tự mua thiết bị. P0 chỉ ghi nhận, còn HR/IT/Asset thực hiện ở hệ thống/quy trình bên ngoài.

### Q02. Vì sao chọn đúng ba loại LEAVE, ACCESS, EQUIPMENT?

Ba loại đại diện ba vòng đời tăng dần A/B/C, đủ chứng minh approval-only, approval+execution và approval+execution+acceptance mà không mở workflow builder tổng quát. Đây là scope MVP cần KD01, không phải tuyên bố đáp ứng mọi quy trình.

### Q03. Ai chịu trách nhiệm nếu ACCESS đã được duyệt nhưng IT chưa cấp quyền?

EAS chuyển sang giai đoạn thực hiện, gán executor và theo dõi SLA. Approval không đồng nghĩa quyền đã được cấp. IT chịu trách nhiệm thao tác ngoài EAS và nộp kết quả/bằng chứng.

### Q04. EQUIPMENT đúng 50 triệu đi mấy cấp?

Hai cấp. Dưới 10 triệu một cấp; từ 10 triệu đến đúng 50 triệu hai cấp; lớn hơn 50 triệu ba cấp. Code có regression tại 9.999.999, 10.000.000, 50.000.000 và 50.000.001.

### Q05. Nghỉ 30 ngày được tính thế nào?

Tính inclusive cả ngày bắt đầu và ngày kết thúc. `10/10–08/11` là 30 ngày và hợp lệ; đến `09/11` là 31 ngày và bị từ chối. Không đánh đồng với ngày làm việc hoặc quỹ phép.

### Q06. Vì sao requester không được duyệt yêu cầu của mình?

Để bảo đảm separation of duties. Guard tồn tại ở route resolver, approval step và decision trigger. Việc user có nhiều role không vô hiệu quy tắc SoD.

### Q07. Tại sao requester lại được nghiệm thu EQUIPMENT?

Theo profile KD04 đề xuất, requester là người xác nhận thiết bị bàn giao đúng yêu cầu, nhưng phải khác executor. Đây là quyết định nghiệp vụ cần chủ quy trình ký, không phải quy tắc phổ quát.

### Q08. Quá SLA có tự động duyệt không?

Không. SLA chỉ reminder/breach/escalation; tự duyệt sẽ thay thẩm quyền nghiệp vụ và tăng rủi ro. OPS có thể gán thay có reason/audit.

### Q09. Tại sao không dùng AI auto-approve?

Không có dữ liệu, thẩm quyền, explainability và risk acceptance để cho AI đổi trạng thái pháp lý/nghiệp vụ. AI Summary chỉ là P1, không thay actor quyết định.

### Q10. Dữ liệu cũ có đổi khi policy mới được publish không?

Không. Mỗi revision chụp `release_id`, department, payload và resolved route. Active release mới chỉ áp dụng cho lần submit/resubmit theo quy tắc được duyệt.

## 4. Câu hỏi use case và trạng thái

### Q11. Vì sao có request và request_revision?

`request` giữ trạng thái hiện hành và optimistic version; `request_revision` là snapshot bất biến của mỗi lần gửi. Nếu ghi đè một hàng sẽ mất lịch sử bổ sung và policy đã dùng.

### Q12. Vì sao UC16 không có trong P0?

UC16 được giữ cho FR21 AI Summary/P1 để không đổi namespace đã phát hành. P0 có 16 use case: UC01–UC15 và UC17. RTM ghi rõ UC16 ngoài P0.

### Q13. NEEDS_INFO khác DRAFT thế nào?

NEEDS_INFO là hồ sơ đã từng submit và có revision/workflow lịch sử; requester sửa vùng draft rồi resubmit thành revision mới. Không sửa revision cũ.

### Q14. APPROVE ở bước cuối có luôn thành COMPLETED không?

Không. Lifecycle A hoàn tất; B/C chuyển `READY_FOR_EXECUTION`. C chỉ COMPLETED sau acceptance.

### Q15. Rework có sửa attempt cũ không?

Không. Attempt đã nộp là lịch sử; REWORK đóng attempt và tạo attempt mới. Điều này giữ bằng chứng từng vòng.

### Q16. Withdraw cạnh tranh với approval cuối xử lý thế nào?

Hai command khóa cùng request. Lệnh lấy khóa trước và thỏa state/version commit; lệnh sau thấy version/state mới và trả conflict, không được có trạng thái lai.

### Q17. Gán thay executor đang RUNNING làm gì với SLA?

Đóng attempt cũ bằng `REASSIGNED`, tạo READY attempt mới và chuyển target của cùng SLA stage trong cùng instance, giữ nguyên deadline. Không gia hạn ngầm.

### Q18. Participant cũ còn đọc được không?

Theo KD04 đề xuất, participant lịch sử còn active giữ quyền đọc trừ khi quy trình thu hồi participant-read có audit hoặc user bị disable. Không suy quyền đọc chỉ từ role hiện tại.

## 5. Câu hỏi kiến trúc và logic code

### Q19. Vì sao modular monolith thay vì microservices?

P0 có một domain, một đội nhỏ và nhiều invariant cần transaction nguyên tử. Modular monolith giảm distributed transaction, deployment surface và chi phí vận hành. Tách service chỉ khi có boundary/tải/vòng đời độc lập được đo.

### Q20. Vì sao không dùng Drools?

Policy P0 hữu hạn 1–3 cấp và operator allowlist; JSON release được version hóa đủ dùng. Drools thêm runtime, security và failure mode nhưng chưa tạo giá trị tương xứng.

### Q21. Code và DB cùng validate có trùng lặp không?

Có chủ ý theo defense in depth. Code trả lỗi nghiệp vụ sớm; DB là hàng rào cuối chống bug/race/script trực tiếp. Hai lớp phải dùng cùng contract và có test drift.

### Q22. Vì sao route chỉ cho operator allowlist?

Để policy là dữ liệu khai báo, không biến thành code/eval. P0 chỉ dùng `amount_gt` và `amount_gte`; operator mới cần schema version/change request.

### Q23. Idempotency khác optimistic locking thế nào?

Idempotency xử lý retry cùng command/key sau mất response và không lặp side effect. Optimistic locking phát hiện client dùng version cũ. Cần cả hai và phải tra replay trước state guard theo hợp đồng.

### Q24. Tại sao không gọi scanner/email trong transaction?

Giữ network call trong DB lock gây timeout/deadlock và trạng thái không xác định. Transaction ghi outbox; worker thực hiện ngoài transaction với lease/retry/dedupe.

### Q25. Health live và ready khác nhau thế nào?

Live chỉ chứng minh process còn chạy. Ready kiểm schema, request types, active release và DB role least-privilege; fail thì load balancer không đưa traffic mới.

### Q26. Vì sao readiness kiểm capability thay vì tên role?

Một superuser có thể mang tên bất kỳ. Kiểm `rolsuper/BYPASSRLS/CREATEROLE/CREATEDB` và membership thực ngăn bypass bằng đổi tên.

### Q27. Có được bật `EAS_ALLOW_ADMIN_DB` ở production không?

Không. Settings production chủ động raise error nếu bật. Cờ chỉ hỗ trợ kiểm tra development có kiểm soát.

### Q28. XSS được xử lý bằng cách cấm HTML đã đủ chưa?

Chưa. Cấm HTML là business validation; frontend vẫn phải render text bằng escaping mặc định, dùng CSP và không đưa dữ liệu vào `dangerouslySetInnerHTML`.

### Q29. Vì sao chưa thể gọi backend là vertical slice hoàn chỉnh?

Hiện mới có health, metadata, validation và routing. Chưa có auth và write transaction tạo revision/workflow/audit/outbox. Phải trả lời trung thực để không bị hỏi demo một flow chưa tồn tại.

### Q30. Điểm lỗi nghiêm trọng nhất trong code hiện còn gì?

Khoảng trống command transaction/auth/audit canonicalization, không phải lỗi cú pháp. Đây là các blocker trước E2E.

## 6. Câu hỏi database

### Q31. Vì sao có 30 bảng, có phải over-engineering?

Số bảng không phải KPI. Việc tách bảng phục vụ bất biến lịch sử, SoD, attempt/revision, SLA/outbox/audit/privacy. Mỗi bảng phải truy được về FR/BR/UC/test; bảng không có trách nhiệm rõ thì phải bỏ.

### Q32. RLS `USING(true)` cho backend có vô nghĩa không?

Không phải RLS end-user. Đây là trusted-service role boundary; authorization người dùng nằm ở Django. Giá trị nằm ở việc `anon/authenticated/service_role` không có quyền schema và runtime role bị giới hạn SQL grant. Nếu client truy DB trực tiếp, thiết kế này không đủ.

### Q33. Tại sao không dùng Supabase Auth/Data API trực tiếp?

Baseline dùng Django session và `app_user`; client không expose schema `eas`. Một nguồn quyền giúp transaction/authorization nhất quán và tránh JWT role khác business role.

### Q34. `request_code` có thể bị hổng số không?

Có, vì sequence không rollback. Đây là hành vi đúng; code là định danh thân thiện, không phải số chứng từ pháp lý liên tục.

### Q35. Tại sao dùng `BIGINT` cho VND?

VND trong P0 là số nguyên, tránh sai số floating point; constraint giới hạn 1–1.000.000.000.000.

### Q36. Isolation READ COMMITTED có đủ không?

Đủ nếu mọi command tuân thủ lock order và row lock/unique constraint. SERIALIZABLE toàn hệ thống tăng retry/chi phí mà không thay thế thiết kế khóa.

### Q37. Lock order dùng để làm gì?

Giảm deadlock và bảo đảm kiểm quyền/state trên cùng snapshot: security epoch → request type khi cần → request → child theo ID → audit head → outbox/idempotency.

### Q38. Audit hash có chống DBA sửa dữ liệu không?

Không tuyệt đối. Application audit chain phát hiện nhiều sửa đổi, nhưng DBA đặc quyền có thể thay DB. Cần checkpoint ngoài quyền ứng dụng, backup và quyền vận hành tách biệt.

### Q39. Vì sao DB không tự tính RFC8785 hash?

`jsonb::text` không phải JCS/RFC8785. Backend phải canonicalize theo profile đã kiểm vector; DB kiểm sequence/prev hash và advance head nguyên tử.

### Q40. Xóa dữ liệu cá nhân mâu thuẫn append-only thế nào?

Append-only là quyền runtime thường, không phải quyền lưu vô hạn. Privacy purge dùng role/approved case/legal hold, xóa theo dependency và giữ suppression/evidence tối thiểu theo policy.

### Q41. Installer SQL có dùng để upgrade production không?

Không. Nó cài schema mới và từ chối rerun. Upgrade cần migration delta expand/contract, checksum, verification và rollback/roll-forward.

### Q42. 98 database check có nghĩa gì?

Là catalog DB-VAL-001–098; lần tái lập runner báo 86 SQL assertion tổng hợp. Không được gọi chúng là TC001–TC100 hoặc acceptance PASS.

## 7. Câu hỏi test, bảo mật và vận hành

### Q43. Có 100 test case, bao nhiêu ca đã PASS?

Ở tầng application/UAT: chưa có ca nào được phép đổi khỏi NOT RUN. Có 66 automated backend/API tests và database verification riêng; chúng không thay TC001–TC100.

### Q44. Vì sao test expected result thôi chưa đủ?

Cần actual result, release, environment, data fixture, timestamp và evidence. Nếu không, không tái lập được và dễ “test trên giấy”.

### Q45. Test concurrency nào quan trọng nhất?

Submit/retry cùng key, withdraw cạnh approval cuối, hai quyết định cùng step, quota upload đồng thời, outbox lease và reassignment. Phải chạy multi-connection PostgreSQL thật.

### Q46. Kiểm rollback command như thế nào?

Fault-inject audit/outbox ở cuối transaction rồi xác minh không có revision/step/SLA/participant/version tăng hoặc side effect dở dang; retry cùng key phải thành công đúng một lần.

### Q47. Vì sao secret gate đang FAIL?

Ba `.env` đã tracked và credential đã xuất hiện trong history/chat. `.gitignore` không gỡ lịch sử. Phải rotate rồi gỡ index/history theo nhánh và kế hoạch phối hợp.

### Q48. Anon key có phải secret không?

Anon/publishable key có thể xuất hiện ở client trong kiến trúc Supabase trực tiếp, nhưng EAS P0 không dùng đường đó. Secret/service-role/DB password luôn là privileged credential. Dù anon key không bí mật, vẫn không nên đưa vào app khi không cần.

### Q49. Backup thành công có chứng minh restore được không?

Không. Cần restore cô lập, DB/object cùng consistent point, kiểm audit/checkpoint, đối soát và đo RPO/RTO actual.

### Q50. Docker Compose chạy được có nghĩa production-ready không?

Không. Cần image digest, SBOM/scan, TLS/proxy, secret manager, storage/scanner, worker, telemetry, backup/restore và rollback rehearsal.

### Q51. Vì sao readiness hiện FAIL trên Supabase thật?

DSN đang dùng DB admin và ba request type chưa có active release. Đây là fail-closed đúng thiết kế, không nên đổi check thành PASS để đẹp demo.

### Q52. Làm sao chứng minh lợi nhuận?

Không thể bằng bảng giá dự kiến. Cần pilot trả phí, đo effort triển khai/support/cloud/CAC, conversion và contribution margin. Mục tiêu thương mại là giả thuyết cho tới khi có số liệu.

## 8. Kịch bản demo bảo vệ 12 phút

1. **1 phút:** vấn đề, ba lifecycle và boundary ngoài EAS.
2. **2 phút:** use case/state; giải thích revision/attempt và UC16/P1.
3. **2 phút:** kiến trúc modular monolith và trust boundary.
4. **2 phút:** ERD theo miền, transaction/lock/idempotency/audit/outbox.
5. **2 phút:** chạy 66 backend/API tests, database regression, mock-source verification và docs gate.
6. **1 phút:** chạy readiness để minh họa fail-closed admin/no active release.
7. **1 phút:** chỉ ra một lỗi 30/31 ngày đã được test bắt và sửa.
8. **1 phút:** NO-GO hiện tại, blocker và roadmap pilot.

Không demo bằng cách đưa secret lên màn hình, chạy seed trên project chưa phân loại hoặc sửa trạng thái test thủ công.

## 9. Thứ tự xử lý tiếp theo

1. Rotate credential, chỉ định nhánh và đóng secret gate.
2. Tạo runtime login least-privilege và active release được duyệt.
3. Xây auth/session rồi LEAVE/A command transaction hoàn chỉnh.
4. Tự động hóa TC001–042 theo risk, sau đó ACCESS/B và EQUIPMENT/C.
5. Cài storage/scanner và worker; chạy concurrency/fault injection.
6. Xây UI/admin, accessibility và E2E.
7. Staging, image/SBOM, load, restore/rollback, UAT và pilot trả phí.
