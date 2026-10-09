# Pull request: Enterprise Approval System — executable P0 baseline

## Mục tiêu

PR này chuyển repository từ bộ tài liệu/SQL rời rạc thành một baseline P0 có thể chạy và kiểm chứng: Django API, React web, worker, PostgreSQL/Supabase, Redis, ClamAV, mock enterprise data, CI và hồ sơ DATN có traceability.

Phạm vi P0 giữ đúng ba lifecycle đã chốt:

- `LEAVE/A`: gửi và phê duyệt;
- `ACCESS/B`: phê duyệt và thực hiện;
- `EQUIPMENT/C`: phê duyệt, thực hiện và nghiệm thu.

AI auto-approve, OCR, Drools, mobile native, workflow builder tổng quát và tích hợp ERP thật vẫn là P1, không được mô tả như chức năng đã triển khai.

## Thay đổi chính

### Backend và bảo mật

- Thêm Django API theo modular-monolith, tách module auth, catalog, domain validation, workflow, mock sources và health.
- Thêm CSRF, session server-side bằng Redis, Argon2, generic authentication error, rate limit, `auth_version` và security epoch để thu hồi phiên.
- Thêm authorization theo role/scope, separation of duties, state/version guard và fail-closed validation.
- Thêm idempotency, transaction, row lock, outbox, audit hash-chain RFC 8785 và correlation ID.
- Thêm private attachment adapter, MIME sniffing, ClamAV scan và fail-closed storage readiness.
- Thêm structured JSON logging và redaction cho password/token/key/DSN.

### Workflow P0

- Tạo draft trước khi upload file, sau đó submit trong transaction.
- Triển khai submit, approval/reject/needs-info, cancel, execution start/result, acceptance/rework và worker outbox/SLA.
- Giữ lifecycle A/B/C khác nhau; không đóng workflow B/C ngay sau approval.
- Chuẩn hóa validation LEAVE, ACCESS và EQUIPMENT, gồm boundary 10/50 triệu, ngày nghỉ tối đa 30 ngày và quote bắt buộc.

### Database và dữ liệu giả lập

- Hoàn thiện EAS schema 30 bảng, RLS, function, trigger, audit, seed và regression validation.
- Thêm 8 bounded-context mock schema: HR, assets, facilities, CRM, procurement, IT, finance và travel.
- Thêm 17 read-only mock API có authentication, role allowlist, cursor pagination, stable error envelope và query timeout.
- Thêm temporal overlap guard cho asset/facility và migration hardening quyền function/default privilege.
- Tạo hai runtime login riêng cho API/worker và readiness kiểm capability thay vì dựa vào tên role.

### Web, container và vận hành

- Thêm React/Vite responsive UI cho login, request creation, request list/detail, approval, execution và acceptance.
- Thêm keyboard skip-link, semantic label/live-region và Playwright + axe accessibility checks.
- Thêm Docker Compose cho web, API, worker, Redis và ClamAV; container non-root, read-only, drop capability và health check.
- Runtime secret/DSN được inject qua environment; `.env` thật bị loại khỏi Git index.
- Pin digest base image, cập nhật package bảo mật và loại Nginx image-filter không sử dụng.
- Thêm script bootstrap development không xóa dữ liệu có sẵn, E2E credential lifecycle có audit và logical backup/restore rehearsal.

### Documentation và CI

- Thêm SRS/design/API/test-plan DOCX, 68 Mermaid diagram, 100 acceptance test ID và RTM UC01–UC17.
- Thêm báo cáo phản biện hội đồng, Supabase verification, mock data platform, runtime/E2E/DR evidence và remediation plan.
- CI kiểm secret, Ruff, Python tests, pip-audit, SQL validation, npm audit/lint/build, Compose build/config và documentation consistency.

## Database migration và compatibility

- EAS installer là fail-closed và không được rerun như migration thông thường.
- Mock migrations hiện hành: `001`, `002`, `003`.
- Development bootstrap chỉ chạy khi project ref được xác nhận chính xác, config/request/audit đang rỗng và không có collision với demo UUID.
- Ứng dụng yêu cầu ba active config release khi `EAS_REQUIRE_ACTIVE_RELEASES=true`.
- API và worker phải dùng DSN least-privilege riêng; không dùng `postgres`, owner hoặc migration role khi chạy.

## Bằng chứng kiểm thử đã chạy

| Gate | Kết quả |
|---|---|
| Django/backend/API | 67 tests PASS |
| Logging security | 4 tests PASS |
| Database validation | 86 SQL assertions PASS |
| Mock Supabase | 8 schema, 23 table, 6 view; 17/17 API resource PASS |
| Ruff/compile | PASS |
| Python dependency audit | Không có vulnerability đã biết |
| Frontend | ESLint/build PASS; npm audit 0 vulnerability |
| Browser E2E | Chromium 4/4 PASS, gồm login/session/dashboard/mock API/logout/WCAG |
| Runtime | 5 container chạy; readiness 11/11 PASS |
| Backup/restore | 9 schema, dữ liệu lõi/mock và audit head khớp; restore 2,664 giây |
| Image security | API và web có 0 fixable Critical/High tại thời điểm scan |
| Documentation | 68 Mermaid; TC001–TC100; UC01–UC17; 0 link hỏng |

Chi tiết môi trường và giới hạn bằng chứng nằm trong `docs/13_Bien_ban_kiem_chung_runtime_E2E_DR.md`.

## Cấu hình bắt buộc khi triển khai

- `EAS_API_DATABASE_URL`: Supabase pooler/direct DSN của API runtime login.
- `EAS_WORKER_DATABASE_URL`: DSN của worker runtime login.
- `EAS_DJANGO_SECRET_KEY`: secret ngẫu nhiên, cấp qua secret manager.
- `EAS_SUPABASE_URL`: project URL.
- `EAS_SUPABASE_SECRET_KEY`: backend-only key cho private Storage.
- `EAS_CSRF_TRUSTED_ORIGINS`: origin chính xác, gồm scheme/host/port public.
- `EAS_REQUIRE_STORAGE=true` và `EAS_REQUIRE_ACTIVE_RELEASES=true` trong production.

Không đặt bất kỳ giá trị thật nào trong repository, PR comment, issue, log hoặc frontend bundle.

## Residual risk / việc không được hiểu là đã hoàn tất

- Credential từng xuất hiện trong chat/Git phải được rotate; commit này không thể tự thu hồi credential trên Supabase.
- Lịch sử Git cũ có thể còn chứa secret. Không rewrite/force-push lịch sử nếu chưa phối hợp tất cả clone và xác nhận kế hoạch phục hồi.
- Private Storage E2E phải chạy lại bằng secret mới; development hiện cho phép tắt requirement một cách tường minh.
- TC001–TC100 không tự động chuyển thành PASS; các case chưa có execution record vẫn là `NOT RUN`.
- Còn cần migration N/N-1, command/worker fault injection đầy đủ, PITR/object restore, load test, screen-reader test, UAT và ký KD01–KD08.
- Production release vẫn là `NO-GO` cho đến khi các blocker trên được đóng hoặc được người có thẩm quyền chấp nhận bằng văn bản.

## Rollback

1. Không rollback bằng cách xóa audit hoặc sửa trực tiếp trạng thái request.
2. Roll back image theo digest release trước; giữ database forward-compatible theo expand/contract.
3. Nếu readiness fail, dừng traffic, giữ worker nếu cần drain outbox và thu thập correlation/log đã redaction.
4. Với migration mock, dùng rollback script tương ứng và chạy lại read-only verification.
5. Restore database chỉ thực hiện sang môi trường cô lập trước; xác minh schema count, business invariant và audit head trước cutover.

## Checklist cho reviewer

- [ ] Xác nhận scope P0/P1 và ba lifecycle A/B/C.
- [ ] Review authorization, SoD, state/version guard, idempotency và audit side effects.
- [ ] Review migration/role grant; xác nhận API/worker không dùng admin DSN.
- [ ] Kiểm CI secret gate, backend, database, frontend, container và docs.
- [ ] Xác nhận credential bị lộ đã rotate và credential cũ bị từ chối.
- [ ] Chạy Storage E2E với bucket private và `EAS_REQUIRE_STORAGE=true`.
- [ ] Xác nhận residual risk, rollback và release decision trước khi gắn nhãn production-ready.
