# Báo cáo thẩm định đồ án và lộ trình thương mại EAS

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | EAS-DOC-08 |
| Phiên bản | 1.0 |
| Ngày đánh giá | 09/10/2026 |
| Vai trò đánh giá | Giảng viên hướng dẫn/Reviewer BA-SA-Engineering-QA-DevOps |
| Baseline | DOCX v2.0, SQL v2.0.1, mã nguồn và cấu hình tại repository |
| Trạng thái | Đánh giá hiện trạng và kế hoạch khắc phục; không phải biên bản GO-LIVE |

## 1. Kết luận điều hành

EAS có nền tảng phân tích và thiết kế tốt hơn phần lớn đồ án sinh viên: phạm vi P0 rõ, mô hình trạng thái có chiều sâu, database có 30 bảng và nhiều invariant, tài liệu đã xét đến idempotency, outbox, audit chain, privacy, RPO/RTO và rollback. Tuy nhiên sản phẩm hiện tại **chưa phải một hệ thống hoàn chỉnh có thể bán hoặc đưa vào production**. Khoảng cách lớn nhất là mã ứng dụng, kiểm thử thực thi, bảo mật secret và gói vận hành.

Điểm hiện trạng theo bằng chứng là **4,9/10**. Điểm này không phủ nhận chất lượng thiết kế; nó phản ánh việc một sản phẩm thương mại phải chạy được, kiểm thử được, triển khai được và phục hồi được.

Chiến lược khả thi nhất không phải cạnh tranh như một nền tảng workflow tổng quát. EAS nên bắt đầu bằng một sản phẩm **approval operations cho doanh nghiệp Việt Nam 50–500 nhân sự**, triển khai nhanh ba quy trình LEAVE/ACCESS/EQUIPMENT, có audit, bằng chứng thực hiện và hỗ trợ private cloud/on-premise. Doanh thu ban đầu nên đến từ phí triển khai, cấu hình, đào tạo, tích hợp và bảo trì; chỉ chuyển sang SaaS đa tenant sau khi có ít nhất 3–5 khách hàng dùng thật và baseline vận hành ổn định.

## 2. Phạm vi và phương pháp đánh giá

Đã đánh giá:

- Sáu tài liệu DOCX v2.0, toàn bộ tài liệu Markdown và PDF tham chiếu trong `docs/`.
- `plan.md`, `actions.md`, cấu trúc service và các README gốc.
- SQL schema, seed, verification, regression, data dictionary và validation evidence.
- Cấu hình Docker, logging, test hiện có và tình trạng Git/secret.
- Kết nối read-only đến Supabase project thật do chủ dự án cung cấp.

Nguyên tắc chấm:

- “Có trong tài liệu” không đồng nghĩa “đã triển khai”.
- “Có test case” không đồng nghĩa “PASS”.
- Chỉ ghi PASS khi đã chạy và có môi trường/kết quả cụ thể.
- PDF mẫu chỉ là chuẩn chất lượng trình bày, không phải nguồn nghiệp vụ hay cấu trúc bắt buộc.

## 3. Bảng điểm hiện trạng

| Nhóm | Trọng số | Điểm /10 | Nhận xét |
|---|---:|---:|---|
| BA/SRS và quản lý phạm vi | 15% | 8,5 | Phạm vi, FR/BR/UC/NFR và quyết định mở khá đầy đủ; KD01–KD08 chưa có người ký |
| Kiến trúc và thiết kế | 15% | 8,0 | Modular monolith phù hợp P0; transaction, state, outbox tốt; tài liệu gốc ngoài `docs/` còn mâu thuẫn |
| Database | 15% | 8,5 | 30 bảng, guard, RLS, regression tốt; thiếu migration tăng dần và concurrency trên Postgres thật |
| Implementation | 20% | 1,0 | Hầu hết service chỉ có README; chưa có API/domain/UI/worker hoàn chỉnh |
| QA và bằng chứng | 15% | 2,0 | Có 100 test case chất lượng nhưng đều NOT RUN ở tầng ứng dụng/UAT |
| Security/privacy | 10% | 4,0 | Thiết kế tốt nhưng `.env` từng được commit; runtime DSN đang dùng quyền quản trị |
| DevOps/SRE | 5% | 1,5 | Có runbook trên giấy; thiếu image, CI, health check, backup/restore adapter và rehearsal |
| Sản phẩm/thương mại | 5% | 3,0 | Có pain point rõ nhưng chưa có ICP, packaging, pricing, pilot KPI và cost model |
| **Tổng có trọng số** | **100%** | **4,9** | **Chưa đủ điều kiện production hoặc bán như sản phẩm hoàn chỉnh** |

## 4. Phát hiện ưu tiên

| ID | Mức | Phát hiện | Tác động | Hành động bắt buộc |
|---|---|---|---|---|
| F01 | Critical | `api_core/.env`, `web_admin/.env`, `web_client/.env` từng nằm trong Git history | Credential phải coi là đã lộ | Rotate DB password/keys phù hợp; không chỉ thêm `.gitignore`; đánh giá rewrite history sau khi có nhánh và backup |
| F02 | Critical | DSN backend hiện kết nối bằng vai trò quản trị PostgreSQL | Lỗi ứng dụng có thể tác động toàn DB | Tạo login runtime chỉ thuộc `eas_api`; tách `eas_worker`, `eas_migration`, `eas_privacy` |
| F03 | Blocker | Chưa có backend/frontend/worker chạy nghiệp vụ | Không thể UAT hoặc tạo giá trị | Xây vertical slice A trước, sau đó B/C; giữ modular monolith |
| F04 | High | README gốc mô tả AI, Drools, mobile, microservices trái baseline P0 | Hội đồng/đội dev hiểu sai, scope creep | Đồng bộ README và cấu trúc theo ADR01; chuyển P1 vào roadmap |
| F05 | High | Compose dùng image `latest`, mật khẩu mẫu và tắt security Elasticsearch | Supply-chain và triển khai không an toàn | Thay bằng Compose của modular monolith, pin image, health check, secret qua environment |
| F06 | High | 100 acceptance test chưa chạy | Không có căn cứ nghiệm thu | Tự động hóa P0 theo pyramid; lưu evidence CI; UAT riêng |
| F07 | High | SQL là bộ cài nguyên khối, chưa có migration delta ứng dụng | Không nâng cấp an toàn khi có dữ liệu | Chọn migration ownership, thêm expand/contract và kiểm N/N-1 |
| F08 | High | Chưa có private storage/scanner adapter | Không thể hoàn thành luồng tệp | Cài adapter, immutable object contract, MIME sniffing, AV scan, signed download |
| F09 | High | Chưa có CI/SBOM/image scan/secret scan | Rủi ro release không kiểm soát | Thêm pipeline lint, unit, integration, dependency/secret/image scan |
| F10 | High | KD01–KD08 chưa được ký | Policy và SLA chưa có thẩm quyền nghiệp vụ | Dùng profile hiện tại cho demo; phải có quyết định ký trước pilot dữ liệu thật |
| F11 | Medium | `test_logger.py` không chứa automated test; unittest chạy 0 case | Bằng chứng QA gây hiểu nhầm | Chuyển thành unit test thật, kiểm handler/filter và redaction |
| F12 | Medium | Chưa có cost model, ICP, pricing và sales motion | Khó tạo lợi nhuận | Dùng mô hình service-led product, đo giờ triển khai và contribution margin |

## 5. Điểm mạnh nên giữ

- Không dùng AI để tự quyết định phê duyệt ở P0; giảm rủi ro pháp lý và giải thích.
- Tách request/revision/workflow/step/attempt/acceptance, tránh ghi đè lịch sử.
- Thiết kế optimistic version, idempotency, audit và outbox theo cùng transaction.
- Quyền và separation of duties được mô hình hóa rõ hơn RBAC đơn giản.
- Database fail-closed cho nhiều invariant và tệp.
- Runbook đã nhận thức đúng rằng backup tồn tại chưa chứng minh restore được.
- Test catalog có negative, boundary, authorization, recovery và concurrency case.

## 6. Định vị sản phẩm có khả năng tạo doanh thu

### 6.1 ICP đề xuất

Khách hàng mục tiêu đầu tiên:

- Doanh nghiệp Việt Nam 50–500 nhân sự.
- Đang duyệt qua email, chat hoặc spreadsheet và khó truy vết.
- Có bộ phận HR, IT và mua sắm nhưng chưa muốn mua một nền tảng quốc tế phức tạp.
- Cần triển khai private cloud/on-premise hoặc cần kiểm soát dữ liệu trong nước.
- Có người sở hữu quy trình và cam kết tham gia pilot 4–6 tuần.

Không nhắm ngay tới ngân hàng, bệnh viện, chính phủ hoặc tập đoàn đa quốc gia vì yêu cầu chứng nhận, tích hợp, multi-tenant, HA và procurement vượt P0.

### 6.2 Giá trị bán

Thông điệp sản phẩm: **“Chuẩn hóa phê duyệt nội bộ và bằng chứng thực hiện trong 4–6 tuần, có audit và triển khai riêng theo doanh nghiệp.”**

Không bán “AI” hay “workflow vô hạn”. Bán các kết quả đo được:

- Giảm thời gian chờ phê duyệt.
- Giảm hồ sơ thất lạc/không rõ trách nhiệm.
- Có bằng chứng ai duyệt, ai thực hiện, khi nào và theo policy nào.
- Có dashboard SLA và dữ liệu phục vụ kiểm toán nội bộ.
- Có quy trình triển khai, backup, restore và bàn giao rõ ràng.

### 6.3 Benchmark cạnh tranh

- Microsoft công bố Power Automate Premium ở mức **USD 15/người dùng/tháng**, nhưng giá thực tế còn phụ thuộc vùng, hợp đồng và hệ sinh thái Microsoft: [Power Automate pricing](https://www.microsoft.com/en-us/power-platform/products/power-automate/pricing).
- Pipefy có gói Starter miễn phí giới hạn, còn Business/Enterprise liên hệ sales; các tính năng như role-based access, private process, data recovery và SSO nằm ở lớp trả phí: [Pipefy pricing](https://www.pipefy.com/pricing/).
- Kissflow định giá theo giá trị và hướng tới enterprise thay vì công bố gói rẻ tự phục vụ: [Kissflow pricing](https://kissflow.com/pricing/).

Suy luận: EAS không nên cạnh tranh bằng số lượng tính năng. Lợi thế phù hợp là triển khai tiếng Việt, policy cố định dễ kiểm chứng, private deployment, chi phí dịch vụ minh bạch và tùy chỉnh tích hợp địa phương.

### 6.4 Packaging và giá thử nghiệm

Các mức dưới đây là **giả định để thử thị trường**, chưa phải báo giá:

| Gói | Nội dung | Giá giả định chưa VAT |
|---|---|---:|
| Pilot | 1 quy trình, tối đa 50 user, cấu hình/đào tạo, 6 tuần | 30–50 triệu VND một lần |
| Standard | 3 quy trình P0, tối đa 200 user, private cloud, báo cáo và hỗ trợ giờ hành chính | 80–150 triệu triển khai + 6–12 triệu/tháng |
| Enterprise Private | SSO/tích hợp theo CR, HA/DR theo hợp đồng, SLA và hỗ trợ nâng cao | Từ 200 triệu triển khai + từ 18 triệu/tháng |

Không giảm giá bằng cách bỏ security test, restore rehearsal hoặc audit. Giảm scope quy trình/tích hợp nếu ngân sách thấp.

### 6.5 Công thức lợi nhuận và guardrail

Theo dõi theo từng khách hàng:

```text
Doanh thu năm 1 = phí triển khai + 12 × MRR + phí CR/tích hợp
Chi phí trực tiếp = giờ triển khai × đơn giá nội bộ + cloud + hỗ trợ + commission + chi phí bên thứ ba
Contribution margin = (doanh thu - chi phí trực tiếp) / doanh thu
CAC payback = CAC / gross profit bình quân tháng
```

Guardrail trước mở rộng:

- Contribution margin năm 1 mục tiêu ≥35%; recurring margin ≥65%.
- Thời gian cấu hình một khách hàng Standard ≤20 ngày công.
- Pilot-to-paid conversion mục tiêu ≥40% sau tối thiểu 5 pilot.
- Không hứa SLA 24/7 khi chưa có đội trực và giá tương ứng.
- Chưa phát triển multi-tenant trước khi single-tenant deployment được tự động hóa và có khách trả tiền.

## 7. Roadmap đưa sản phẩm đến pilot trả phí

| Cổng | Thời lượng mục tiêu | Đầu ra bắt buộc | Điều kiện qua cổng |
|---|---:|---|---|
| R0 Security containment | 1–2 ngày | Rotate secret, runtime roles, ignore/scan secret | Không còn admin credential trong runtime/history mới |
| R1 Executable core | 2 tuần | Auth, org/role, health, request A submit/approve, audit/outbox | Unit/integration P0 slice PASS |
| R2 Full P0 | 3–4 tuần | A/B/C, tệp/scanner, SLA worker, notification, admin config | TC001–087 và 093–098 có automation/evidence theo phạm vi |
| R3 Operational readiness | 1–2 tuần | CI, images, staging, metrics, backup/restore, runbook thực | Restore rehearsal, security review, load profile đạt |
| R4 Design partner pilot | 4–6 tuần | 1 khách hàng, dữ liệu tối thiểu, đào tạo, KPI baseline | UAT ký, không S0/S1, rollback đã diễn tập |
| R5 Productization | Sau 3 khách trả phí | Installer, tenant isolation decision, billing/support playbook | Deployment lặp lại, margin và support load đạt guardrail |

## 8. KPI pilot

| KPI | Baseline cần đo | Mục tiêu thử nghiệm |
|---|---|---|
| Median approval lead time | 4 tuần trước pilot | Giảm ≥30% |
| Hồ sơ không rõ người xử lý | 4 tuần trước pilot | Giảm ≥80% |
| Hồ sơ quá SLA không có escalation | 4 tuần trước pilot | 0 |
| Tỷ lệ thao tác thành công | Telemetry pilot | ≥99,5%, loại lỗi validation hợp lệ |
| P95 command API | Load/staging và pilot | <2 giây theo NFR đã ký |
| Khả năng truy vết mẫu audit | Mẫu kiểm toán | 100% hồ sơ mẫu có actor/time/policy/evidence |
| Weekly active users/eligible users | Pilot | ≥60% ở nhóm có phát sinh nghiệp vụ |
| Ticket hỗ trợ do lỗi sản phẩm | Theo tuần | Giảm dần; không có S0/S1 mở |

## 9. Quyết định kiến trúc

Dùng Django 5.2 LTS modular monolith, PostgreSQL/Supabase làm hệ dữ liệu, worker dùng cùng domain code, React web và private object storage/scanner adapter. Django 5.2 là LTS và hỗ trợ PostgreSQL 14 trở lên theo tài liệu chính thức: [Django 5.2 release notes](https://docs.djangoproject.com/en/5.2/releases/5.2/).

Không đưa Drools, Elasticsearch, Redis, mobile native, AI service hoặc microservices vào P0 nếu chưa có requirement và bằng chứng lợi ích. Chỉ tách service khi có tải, vòng đời triển khai hoặc boundary dữ liệu độc lập được đo.

## 10. Điều kiện tuyên bố sẵn sàng production

Chỉ được ghi `GO` khi:

- Secret đã rotate; runtime không dùng `postgres`/owner/service role.
- KD01–KD08 có quyết định hợp lệ hoặc hợp đồng pilot ghi rõ profile được chấp nhận.
- Release image pin theo digest; SBOM, dependency/secret/image scan đạt policy.
- Tất cả P0 test bắt buộc có actual result và evidence; không S0/S1 mở.
- Storage/scanner, worker/outbox, backup/restore và rollback được diễn tập trên staging tương đương production.
- RPO/RTO được đo, không chỉ ghi mục tiêu.
- UAT và go/no-go có người chịu trách nhiệm ký.

Cho đến lúc đó, trạng thái đúng là **PRE-PRODUCTION / NO-GO**.
