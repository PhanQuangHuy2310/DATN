# Kế hoạch khắc phục kép: Giảng viên hướng dẫn và Hội đồng

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-10-09-01 |
| Ngày mở | 09/10/2026 |
| Trạng thái | IN PROGRESS |
| Phạm vi | P0 production-readiness, không gồm AI/Drools/mobile P1 |
| Quyền tiếp tục | Chủ dự án đã cho phép triển khai và đối soát liên tục |

## 1. Cơ chế hai cổng

1. **Cổng hướng dẫn:** đối chiếu SRS/thiết kế/schema, đề xuất thay đổi nhỏ có traceability, triển khai và viết test.
2. **Cổng hội đồng:** tìm cách phá bằng negative/boundary/auth/concurrency/recovery test; kiểm actual evidence; không chấp nhận tài liệu thay implementation.
3. Chỉ chuyển mục sang `VERIFIED` khi test đã chạy. Mục phụ thuộc môi trường ngoài giữ `BLOCKED` hoặc `NOT RUN`.

## 2. Work breakdown và bằng chứng

| Work item | Điểm mù liên quan | Deliverable | Gate hội đồng | Trạng thái |
|---|---|---|---|---|
| W01 Schema/payload/routing fail-closed | BL01–BL04, BL25–BL26 | Domain validation và routing | Boundary/negative tests | VERIFIED |
| W02 Runtime readiness/least privilege | BL05–BL08, BL11–BL12 | Capability checks, role SQL | Remote readiness | PARTIAL — code verified, remote blocked |
| W03 Auth/session/security boundary | BL13 | `/auth/csrf`, login/logout/me, Argon2, auth_version, rate limit | CSRF/generic error/rate-limit/revocation tests | IMPLEMENTED — integration pending |
| W04 RFC8785 audit | BL15 | Canonicalizer và database fixture vectors | Tất cả vector byte/hash khớp | VERIFIED |
| W05 Submit/approval transaction | BL14 | Draft, submit, approval decision, idempotency/audit/outbox | Real PostgreSQL transaction/concurrency | IMPLEMENTED — integration pending |
| W06 Private attachment/scanner | BL16 | Supabase Storage adapter, MIME sniff, ClamAV fail-closed | Storage/scanner integration | IMPLEMENTED — external integration pending |
| W07 Worker outbox/SLA | BL17 | Claim/lease/ACK/retry/dead/replay | Crash/retry/lease tests | IMPLEMENTED — unit verified; integration pending |
| W08 Web client/admin/a11y | BL18 | P0 responsive UI | Browser/a11y E2E | PARTIAL — client lint/build PASS; admin và E2E pending |
| W09 Incremental migration | BL19 | Versioned expand/contract migration | N/N-1 rehearsal | TODO |
| W10 Concurrency/fault injection | BL20 | Multi-session PostgreSQL suite | TC030/038/056/064 | TODO |
| W11 Restore/rollback | BL21 | Script và rehearsal record | TC089–092, actual RPO/RTO | TODO |
| W12 Credential containment | BL10 | Rotate và Git decontamination | Secret gate PASS | BLOCKED — cần credential rotation và nhánh Git được chỉ định |
| W13 Commercial validation | BL24 | Pilot KPI/unit economics evidence | Paid pilot data | BLOCKED — cần dữ liệu thị trường thực |
| W14 Synthetic enterprise sources | BL27 | 8 schema mock, seed, read API, design doc | SQL verify + API tests + Supabase evidence | PARTIAL — DB/role/API unit verified; deployed API E2E pending |

## 3. Nhật ký đối soát

### Vòng 1 — 09/10/2026

- Hội đồng phát hiện lỗi inclusive 30 ngày, UUID canonicalization, route operator/config, capability readiness và RTM UC16.
- Hướng dẫn sửa và thêm regression tests; 27 test nền tảng PASS.
- Hội đồng phát hiện thêm malformed property schema và invalid route threshold; đã sửa fail-closed.

### Vòng 2 — 09/10/2026

- Hướng dẫn bổ sung auth/session, RFC8785, draft/submit/approval và attachment boundary.
- Hội đồng phát hiện fixture config canonical không có object nguồn; test đã sửa để parse chính chuỗi canonical thay vì tạo dữ liệu giả.
- Hội đồng phát hiện EQUIPMENT không thể upload báo giá trước khi request tồn tại; bổ sung create-draft trước upload/submit.
- Hội đồng phát hiện không được đóng workflow instance sau approval đối với lifecycle B/C; chỉ lifecycle A được đóng ở bước đó.
- Gate hiện tại: 36 test PASS; lint đang được sửa và sẽ chạy lại trước khi cập nhật kết quả.

### Vòng 3 — 09/10/2026

- Hội đồng bác phương án nhét dữ liệu HR/tài sản/CRM vào `eas` vì làm sai bounded context và quyền sở hữu dữ liệu.
- Hướng dẫn tạo 8 schema nguồn giả lập độc lập: HR, asset, facilities, CRM, procurement, IT, finance và travel; chỉ cấp `SELECT` tối thiểu cho `eas_api`.
- Tham khảo phẩm chất API resource/module, sandbox, request ID, trạng thái và lỗi ổn định từ tài liệu Shopee; không sao chép API hoặc dữ liệu Shopee.
- Installer/seed đã PASS trên PostgreSQL WASM và Supabase PostgreSQL 17.6. Supabase có 8 schema, 23 bảng, 6 view; fixture đếm đúng và không có xung đột open loan.
- Backend có 17 endpoint lookup, authentication, cursor pagination, allowlist resource/column và error envelope. E2E bằng runtime role `eas_api` vẫn NOT RUN.
- Gate sau vòng 3: 59 backend/API tests PASS; Ruff PASS; frontend lint/build PASS; npm audit 0 vulnerability; docs gate PASS; secret gate vẫn FAIL đúng do ba `.env` tracked.

### Vòng 4 — 09/10/2026: đợt đối soát trực tiếp 1–2/5

- **Lần 1 — API resilience:** sửa correlation ID bị sinh lại ở nhánh lỗi, chuẩn hóa `SOURCE_UNAVAILABLE` 503, không log exception DB, escape wildcard tìm kiếm và đặt statement timeout 2 giây. Chạy trực tiếp 17/17 resource dưới `eas_api`: PASS.
- **Lần 2 — concurrency dữ liệu:** thay unique open-loan thô bằng temporal guard `[start,end)`, thêm guard đặt facility có row lock. Migration `001` triển khai Supabase PASS; hai connection chồng lấn cho một commit/một `23P01`, hai khoảng kề nhau cùng commit.

### Vòng 5 — 09/10/2026: đợt đối soát trực tiếp 3–5/5

- **Lần 3 — least privilege:** chặn requester khỏi leave balance toàn công ty, loan, customer/contract và budget; migration `002` thu hồi function execute của `PUBLIC` và khóa default privilege. Supabase: 0 public schema usage, 0 public executable function, 0 non-SELECT grant cho `eas_api`.
- **Lần 4 — operability:** readiness kiểm đủ 17 relation và migration 001–003; migration `003` chỉ cấp metadata read. Probe thật dưới `eas_api`: 8/8 readiness check PASS.
- **Lần 5 — HTTP/release gates:** từ chối query parameter lạ, `no-store` cho resource nhạy cảm; 66 backend/API test, 86 SQL assertion, mock SQL, Ruff, dependency audit, frontend lint/build/audit và docs gate đều PASS. Live Supabase đọc 17/17 resource, 39 hàng trong probe.
- Django HTTP smoke boot nối Supabase: `/health/live=ok`, `/health/ready=ready`, 9 readiness checks; tiến trình kiểm chứng đã được dừng sạch sau probe. Đây là dev-mode probe có admin override, không phải production deployment.
- Gate còn mở trung thực: secret gate FAIL do ba `.env` tracked; Docker image/runtime NOT RUN vì Docker daemon không hoạt động; HTTP E2E staging, browser accessibility, backup/restore và full TC001–TC100 vẫn NOT RUN.

## 4. Definition of Done

- Không còn defect Critical/High đã biết trong phạm vi code P0 mà chưa có disposition.
- Auth, A/B/C lifecycle, attachment, worker và UI chạy end-to-end trên staging.
- Concurrency, idempotency, fault injection, security, accessibility, migration, backup/restore và rollback có actual evidence.
- Secret gate, dependency, source, database, docs, container/image và readiness đều PASS.
- TC001–TC100 chỉ chuyển trạng thái từ NOT RUN bằng execution record có release/environment/timestamp/evidence.

Không diễn giải “không còn gì bới móc” thành không còn residual risk. Tiêu chí đúng là không còn rủi ro đã biết bị bỏ quên hoặc trạng thái bị khai khống.

## 5. Vòng 6 — runtime, E2E, DR và supply-chain

- Docker Desktop đã hoạt động; dựng đủ `web`, `api`, `worker`, `redis`, `clamav`. API/worker dùng hai login runtime least-privilege qua Supabase session pooler; readiness 11/11 PASS.
- Bootstrap active release vào project development không xóa user/phòng ban có sẵn; 11 user, 3 release, 3 active request type; mọi thay đổi nhạy cảm có audit.
- Playwright/axe chạy Chromium qua Nginx thật: 4/4 PASS, gồm CSRF/login/session/dashboard/mock API/logout, keyboard và WCAG A/AA. Credential fixture sinh ngẫu nhiên, không in/lưu, luôn disable trong `finally` và có audit hash-chain.
- Backup/restore rehearsal đã phát hiện rồi sửa danh sách schema cũ và role RLS bị thiếu. Lần cuối PASS: 9 schema, 11 user, 3 active type, 3 asset, audit head khớp; dump 54,095 giây, restore 2,664 giây.
- Docker Scout phát hiện 7 Critical/35 High ở API image và 7 Critical/33 High ở web image cũ. Đã pin base digest mới, upgrade Alpine, bỏ module image-filter không dùng; retest hai image còn 0 fixable Critical/High.
- Gate cuối vòng: 67 Django tests + 4 logger tests, 86 SQL assertions, Ruff, compile, dependency audit, frontend lint/build/audit, docs và E2E đều PASS.
- Working-tree `.env` đã được thay bằng placeholder. Secret gate vẫn **FAIL đúng** vì ba file còn tracked; không được thao tác Git trước khi chủ dự án chỉ định nhánh. Credential đã lộ vẫn phải rotate ở Supabase.
- Storage private chưa được nghiệm thu do không dùng lại secret đã lộ. Development đặt `EAS_REQUIRE_STORAGE=false` tường minh; production mặc định fail-closed.

### Trạng thái work item hiện hành (ghi đè các trạng thái cũ ở mục 2)

| Work item | Trạng thái hiện hành |
|---|---|
| W02 Runtime readiness/least privilege | VERIFIED trên development integration |
| W03 Auth/session/security boundary | VERIFIED cho browser flow đã tự động hóa |
| W06 Private attachment/scanner | PARTIAL — scanner healthy; Storage E2E blocked bởi credential rotation |
| W08 Web client/admin/a11y | PARTIAL — client browser/axe PASS; admin chuyên biệt và screen reader còn mở |
| W09 Incremental migration | TODO — chưa có N/N-1 rehearsal |
| W10 Concurrency/fault injection | PARTIAL — mock temporal concurrency PASS; command/worker fault suite còn mở |
| W11 Restore/rollback | PARTIAL — logical DB restore PASS; PITR/object restore/rollback release còn mở |
| W12 Credential containment | BLOCKED — local value redacted; rotation và Git decontamination chưa được phép hoàn tất |
| W14 Synthetic enterprise sources | VERIFIED cho DB, role, HTTP API và browser E2E |

Biên bản chi tiết: [EAS-DOC-13](../../docs/13_Bien_ban_kiem_chung_runtime_E2E_DR.md).
