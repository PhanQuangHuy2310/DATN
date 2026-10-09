# Biên bản kiểm chứng runtime, E2E, DR và container EAS

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-DOC-13 |
| Ngày thực thi | 09/10/2026 |
| Build | `local-20261009-r6` |
| Môi trường | Docker Desktop; Supabase PostgreSQL tại `ap-southeast-2`; Chromium Playwright |
| Phạm vi | P0 development integration, runtime least privilege, E2E web/API, accessibility, backup/restore, image security |
| Kết luận | CONDITIONAL PASS cho development demo; production vẫn NO-GO theo mục 6 |

## 1. Cấu hình thực thi đã kiểm chứng

- Web/Nginx: `http://127.0.0.1:18080`, reverse proxy cùng origin tới Django.
- API: Gunicorn/Django chạy non-root, read-only filesystem, chỉ bind `127.0.0.1:8000`.
- Worker: image dùng chung domain code, DSN riêng thuộc nhóm `eas_worker`.
- Database: API và worker dùng hai login runtime không có quyền admin; kết nối qua Supabase session pooler.
- Redis và ClamAV đều có health check; năm container `web`, `api`, `worker`, `redis`, `clamav` chạy đồng thời.
- Ba active config release cho `LEAVE`, `ACCESS`, `EQUIPMENT` đã được bootstrap có audit trong môi trường development.
- Mật khẩu E2E không nằm trong repository: sinh ngẫu nhiên trong bộ nhớ, enable/disable bằng hai admin audit event và tăng `auth_version`/`security_epoch`.

Không ghi DSN, password, JWT hoặc Supabase key vào biên bản này.

## 2. Lỗi được phát hiện trong lần chạy trực tiếp và cách xử lý

| Phát hiện | Ảnh hưởng | Sửa chữa | Retest |
|---|---|---|---|
| Direct DB host chỉ có tuyến IPv6 từ container | API/worker không kết nối DB | Dùng Supabase session pooler và username role theo project ref | Readiness PASS |
| Nginx non-root không ghi được cache/run | Web crash loop | Gán UID/GID đúng cho `tmpfs` | Web HTTP 200 |
| ClamAV bị drop toàn bộ capability cần thiết khi khởi tạo | Scanner không healthy | Chỉ trả lại `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETGID`, `SETUID` | Container healthy |
| CSRF trusted origin không chứa cổng public `18080` | Login trả 403 | Cấu hình origin chính xác qua biến runtime | Invalid-login và login thật PASS |
| E2E đọc sai response envelope của mock API | Test báo lỗi dù API 200 | Assert `data.items` theo contract | E2E 4/4 PASS |
| Backup dùng ba tên schema cũ | Dump thiếu CRM/procurement/travel | Đóng danh sách theo runtime contract hiện hành và hậu kiểm đủ 9 schema | Restore rehearsal PASS |
| Restore target thiếu role được RLS policy tham chiếu | `pg_restore` dừng ở policy | Tạo bốn role NOLOGIN trước restore | Restore rehearsal PASS |
| Base image API/web có Critical/High CVE đã có bản vá | Không đủ điều kiện release | Pin digest mới, nâng package Alpine và loại image-filter dependency không dùng | 0 fixable Critical/High ở hai image |
| Readiness không phản ánh cấu hình Storage | Có thể báo ready khi upload chắc chắn lỗi | Thêm gate Storage/ClamAV; development phải tắt yêu cầu một cách tường minh | Unit test và readiness PASS |

## 3. Bằng chứng quality gate

| Gate | Actual result | Trạng thái |
|---|---|---|
| Backend/domain/API | 67 Django tests | PASS |
| Logging security | 4 tests về JSON/redaction/log injection | PASS |
| Ruff lint/format/compile | 57 Python files, không lỗi | PASS |
| Python dependency audit | Không có vulnerability đã biết trong requirements pin | PASS |
| Database package | 86 SQL assertions trên PostgreSQL 18.3 WASM | PASS |
| Frontend | ESLint PASS; Vite production build PASS; npm audit 0 vulnerability | PASS |
| Browser E2E | 4/4 Chromium: keyboard/skip-link, WCAG A/AA, generic auth error, readiness, login thật, dashboard, mock catalog, logout | PASS |
| Runtime readiness | 11/11 check: role, schema, config, mock sources, cache và requirement ngoại vi | PASS |
| Container runtime | 5/5 container chạy; API/Redis/ClamAV healthy; web HTTP 200 | PASS |
| Container CVE | `eas-api` và `eas-web`: 0 fixable Critical/High theo Docker Scout tại thời điểm chạy | PASS |
| Backup/restore | Dump 285.226 byte; 9 schema; 11 user; 3 active type; 3 asset; audit head khớp | PASS |
| Thời gian DR đo được | Dump 54,095 giây; restore 2,664 giây trên máy local | MEASURED, không phải production SLA |
| Docs | 16 Markdown trước biên bản này, 68 Mermaid, TC001–TC100 đủ mã, UC01–UC17 đủ RTM, 0 link hỏng | PASS |
| Secret gate | Không còn giá trị bí mật trong working-tree `.env`, nhưng ba file vẫn thuộc Git index/history | **FAIL/BLOCKER** |

## 4. Cách tái lập kiểm chứng

Các biến bí mật phải được inject từ secret manager/process environment, không ghi vào command history hoặc file tracked.

```powershell
# Sau khi stack đã được cấp runtime environment an toàn
docker compose config --quiet
docker compose up -d
Invoke-RestMethod http://127.0.0.1:18080/health/ready
./scripts/run_live_e2e.ps1
```

Diễn tập restore dùng một PostgreSQL 18 container tạm, chỉ đọc nguồn, tự xóa container và dump tạm trong `finally`:

```powershell
./scripts/rehearse_backup_restore.ps1 -SourceDatabaseUrl $env:EAS_ADMIN_DATABASE_URL
```

## 5. Diễn giải đúng phạm vi PASS

- Kết quả E2E chứng minh login/session/UI cơ bản và mock catalog qua stack thật; không đồng nghĩa toàn bộ TC001–TC100 đã PASS.
- Accessibility tự động bằng axe không thay thế kiểm thử screen reader thủ công, zoom/reflow và UAT với người dùng khuyết tật.
- Restore local chứng minh logical dump có thể phục hồi schema/data/audit head; chưa chứng minh PITR, object Storage restore hoặc RTO/RPO production.
- Storage được đặt `EAS_REQUIRE_STORAGE=false` riêng cho development vì secret key đã lộ phải rotate. Production mặc định fail-closed nếu thiếu URL/key hoặc ClamAV không reachable.
- Docker Scout là ảnh chụp theo cơ sở CVE tại thời điểm chạy; CI/release phải scan lại image digest, không tái sử dụng kết luận vô thời hạn.

## 6. Residual risk và quyết định go/no-go

Production vẫn **NO-GO** cho đến khi hoàn thành đồng thời:

1. Rotate DB password, Supabase secret/anon key đã xuất hiện trong chat/Git và chứng minh credential cũ bị từ chối.
2. Trên nhánh Git được chủ dự án chỉ định, gỡ ba `.env` khỏi index; phối hợp rewrite history nếu cần; secret gate phải PASS.
3. Cấp secret Storage mới qua secret manager, đặt `EAS_REQUIRE_STORAGE=true`, chạy upload/scan/download/delete E2E với bucket private.
4. Thực thi các acceptance case còn `NOT RUN`, đặc biệt concurrency command, worker crash/retry, migration N/N-1, privacy, reassign và UAT.
5. Chạy load/capacity test, PITR/object restore, screen-reader test và ký KD01–KD08/acceptance bởi người có thẩm quyền.

Mọi mục chưa hoàn thành đều có disposition rõ; không được đổi thành PASS chỉ dựa trên tài liệu hoặc unit test.
