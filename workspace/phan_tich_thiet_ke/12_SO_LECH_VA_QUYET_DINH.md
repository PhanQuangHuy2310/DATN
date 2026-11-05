# 12 — Sổ lệch tổng hợp, quyết định và việc cần làm

> Tổng hợp mọi lệch đã phát hiện ở các tệp 00–11.
>
> Cột **Quyết định** dùng các nhãn sau:
> - **Sửa DOCX**: hệ thống đúng hơn, báo cáo phải sửa;
> - **Sửa code**: DOCX hoặc tiêu chuẩn đúng hơn;
> - **Bỏ khỏi P0**: ghi là hướng phát triển;
> - **Chủ đầu tư chốt**: hai phương án đều hợp lý.
>
> Cột **Ưu tiên**:
> - **P0**: trước khi bàn giao báo cáo;
> - **P1**: nên làm trước khi dùng thật;
> - **P2**: hướng phát triển.

## A. Lỗi biên tập DOCX (không phụ thuộc code) — tất cả P0

| ID | Lỗi | Vị trí | Việc phải làm |
|---|---|---|---|
| A01 | 18 hình là ảnh lặp (MD5 trùng `img_006` / `img_007`) | Hình 2.10–2.27 | Thay bằng ảnh thật. 9 ảnh đã có sẵn ở phụ lục dưới chú thích sai: SD-04, SD-06, SD-08, AR-02, DFD-01, SEC-01, ER-01, ST-02, ST-07. 9 sơ đồ còn lại (SD-03, AR-01, AR-03, DFD-00, ST-01, ST-03, ST-06, ER-02, ER-03) vẽ theo Mermaid ở tệp 02 và 05–08 |
| A02 | 50/50 chú thích ảnh sơ đồ không khớp nội dung | Hình 2.1–2.9, PL-01…PL-41 | Đặt lại theo bảng `00` §3.2 |
| A03 | Đoạn mô tả Hình 2.10–2.21 chép từ Hình 2.1/2.2; Hình 2.22–2.27 không có mô tả | 2.2.10, 2.3.x | Viết lại theo tệp 05–08 |
| A04 | Bảng 2.10–2.16 là bản sao Bảng 2.1; không có từ điển dữ liệu | 2.3.8 | Thay bằng tệp 09 §3–4 |
| A05 | 2.4 và toàn bộ Chương 3 chỉ có tiêu đề | 2.4, 3.x | Dùng tệp 10, 11 làm nội dung khởi đầu |
| A06 | "16 UC" nhưng không có UC16 | 2.1.3 | Thêm UC16 Ủy quyền + UC18–24 (`01` §3) |
| A07 | Mã ST-04 dùng cho hai đối tượng; mã ER của ảnh khác mã ER của text | Phụ lục D, E | Đánh số lại (`07`, `08` §1) |
| A08 | DP-01 có ảnh nhưng không có chú thích; PL-1 tuyên bố 68 sơ đồ, thực có 50 | Phụ lục | Bổ sung chú thích; sửa tổng số |
| A09 | Ký pháp ERD trộn Chen và crow's foot; UC-REL-01 dùng use case để vẽ trình tự | Phụ lục A, E | Thống nhất ký pháp (`03` G4, `08`) |

## B. Lệch nghiệp vụ

| ID | Nội dung | DOCX | Hệ thống | Quyết định | Ưu tiên |
|---|---|---|---|---|---|
| B01 | Định nghĩa A/B/C | Gộp số cấp + thực thi + ngưỡng tiền | Lifecycle = hình dạng quy trình; số cấp do rule; rủi ro do trọng số | **Sửa DOCX** (`02` §2) | P0 |
| B02 | Ngưỡng tiền mâu thuẫn | 2M/20M; 5M/50M; 500k; quy chế 30M | Theo rule của từng loại đơn | **Chủ đầu tư chốt** bảng ngưỡng 5 loại tiêu biểu, rồi sửa DOCX | P0 |
| B03 | Tên trạng thái | SUBMITTED, IN_REVIEW, APPROVED, READY, SUBMITTED_ACCEPT | 9 trạng thái của code | **Sửa DOCX** (`02` §3) | P0 |
| B04 | Needs Info | Về DRAFT | Trạng thái NEEDS_INFO riêng | **Sửa DOCX** | P0 |
| B05 | Rework | → IN_PROGRESS | → READY_FOR_EXECUTION, attempt mới | **Sửa DOCX** (ảnh SD-06 / ST-04 đã đúng) | P0 |
| B06 | Nộp lại | Tiếp từ bước yêu cầu bổ sung | Duyệt lại từ bước 1 | **Sửa DOCX** (four-eyes trên nội dung mới) | P0 |
| B07 | R02 nghỉ > 2 ngày | 1 cấp | 2 cấp (QL → GĐ) | **Chủ đầu tư chốt** theo quy chế | P0 |
| B08 | R06 quyền quản trị IT | IT head → CISO | Theo ứng dụng nhạy cảm → QL → GĐ | Sửa DOCX theo "ứng dụng nhạy cảm"; **sửa cấu hình** (không phải code) dùng slot `IT_MANAGER`, `SECURITY` | P1 |
| B09 | R07 người yêu cầu trùng người duyệt | Chuyển lên cấp trên | Chặn gửi (409) | **Sửa code**: thay bằng quản lý của requester + audit | P1 |
| B10 | Rủi ro ≥ 4 → lên Giám đốc | Dùng điểm AI | Không có | **Bỏ khỏi P0**. Nếu làm: rule tất định trên trọng số đã lưu, chỉ được thêm cấp | P2 |
| B11 | Budget Quota Guard | Có | Không có | Bỏ khỏi P0 / P1 với toán tử `over_budget` | P1 |
| B12 | Duyệt song song | Có | Chỉ tuần tự | **Bỏ khỏi DOCX** | P0 |
| B13 | Ngưỡng SLA | 80/100/150%, quét 5 phút | 50/100%, quét 2 giây | **Chủ đầu tư chốt**; khuyến nghị 50/100 + L2 150% gửi OPS | P0 (DOCX), P1 (L2) |
| B14 | Người nhận khi quá hạn | Người xử lý + trưởng bộ phận (+BOD) | Chỉ người đang giữ việc | **Sửa code**: thêm quản lý trực tiếp; cấu hình nhắc / tự chuyển (D3) | P1 |
| B15 | Báo vướng có dừng SLA? | Text: dừng | Ảnh và code: không | **Sửa DOCX** | P0 |
| B16 | Admin xem nội dung hồ sơ | Bảng 2.7: Policy/Ops "Tất cả" | Chỉ metadata | **Sửa DOCX** (least privilege) | P0 |
| B17 | Quản lý cùng phòng xem hồ sơ | Text SD-10 có | Không (chỉ participant) | **Sửa DOCX** | P0 |
| B18 | Người nghiệm thu "độc lập" | Bắt buộc độc lập | 5 slot, gồm cả người tạo; acceptor ≠ executor | **Sửa DOCX** | P0 |
| B19 | Bằng chứng khi nộp kết quả | Bắt buộc biên bản / ảnh | Không bắt buộc tệp | **Sửa code**: C bắt buộc ≥ 1 tệp | P1 |
| B20 | Người duyệt kế tiếp vắng | Ảnh AD-03: báo lỗi | Chuyển delegate / quản lý | **Sửa DOCX** | P0 |
| B21 | Ủy quyền "cùng hoặc cao cấp hơn" | Có | Kiểm vai trò APPROVER đúng loại và phòng | **Sửa DOCX** (không có bảng cấp bậc) | P0 |
| B22 | Duyệt kép privacy | Có (AD-09, SD-14) | Một người, tham chiếu tự do | **Sửa code** | P1 |
| B23 | Bảo trì / go-live (AD-10) | Nghiệp vụ người dùng | Quy trình vận hành | Chuyển sang Chương 3 | P0 |
| B24 | Các quyết định D1–D9 (03/11/2026) | Chưa có | Chưa làm | Đưa vào DOCX ở dạng "đã chốt, đang triển khai" (`02` §8) | P0 |

## C. Lệch công nghệ — tất cả "Sửa DOCX", P0

| ID | DOCX | Thực tế |
|---|---|---|
| C01 | React 18, Axios | React 19.3, Vite 8.3, `fetch` |
| C02 | Django REST Framework, ORM | Django 5.2 thuần, SQL tham số hoá psycopg 3, trigger PostgreSQL |
| C03 | Redis + Celery worker | Một tiến trình `run_outbox_worker` (SLA + outbox + AI learning), lease trong DB |
| C04 | Phiên lưu trong Redis (TTL 8 giờ) | Cookie ký 8 giờ; Redis giữ dấu rỗi 30 phút + throttle |
| C05 | Thu hồi phiên bằng xoá key Redis | Tăng `auth_version` |
| C06 | WebSocket / badge Redis | Polling |
| C07 | Argon2 / PBKDF2 | Chỉ Argon2 |
| C08 | GIN index JSONB, PgBouncer | 0 GIN; pool psycopg + pooler Supabase |
| C09 | Mobile: FCM, sinh trắc học, duyệt nhanh | Chỉ xem và thông báo |
| C10 | OCR Tesseract / TrOCR | PaddleOCR + Gemini Vision (chưa nối UI) |
| C11 | NLP Calibrated SGD; 14 đặc trưng; 15 artifact | Logistic Regression; 19 đặc trưng; 16 tệp |
| C12 | Kiến trúc "Microservices" | Modular monolith + 1 AI microservice |
| C13 | Quét virus bất đồng bộ QUEUED → SCANNING | Đồng bộ, chỉ lưu tệp sạch |
| C14 | Chữ ký số khi duyệt | Không có; quyết định bất biến + hash-chain |
| C15 | "Chặn 100% OWASP Top 10", "99.9% uptime", "< 200ms" | Chưa đo → đổi thành ASVS L2 và mục tiêu đo được (`01` §4) |
| C16 | URL/event trong text (`/reports/sla-compliance`, `/steps/{n}/reassign`, `ADMIN_REASSIGN_*`, `PROCESSED`, `version_no`) | `/reports/requests`, `/requests/{id}/reassign`, `ACTOR_REASSIGNED`, `SENT`, `lock_version` |
| C17 | Text SD-17: failover tự động sang standby | Ảnh và thực tế: cutover/rollback có kiểm soát; HA do Supabase |
| C18 | mock_* "tự cập nhật lịch / PO / phân quyền khi duyệt" | Chỉ đọc (đúng nguyên tắc chính DOCX nêu) |

## D. Chức năng DOCX mô tả nhưng chưa hiện thực

| ID | Chức năng | Quyết định | Ưu tiên |
|---|---|---|---|
| D01 | Audit checkpoint ra kho ngoài | Sửa code: lệnh `audit_checkpoint` hằng ngày | P1 |
| D02 | Legal hold: tạo / giải toả qua API | Sửa code: lệnh CLI tối thiểu | P1 |
| D03 | Giới hạn 5 tệp / quota | Sửa code: ≤ 5 tệp, ≤ 50 MiB mỗi hồ sơ | P1 |
| D04 | Dọn tệp mồ côi 30 ngày | Bỏ khỏi P0 | P2 |
| D05 | Đồng bộ LDAP/AD | Bỏ khỏi P0 (đã có `identity_import` CSV) | P2 |
| D06 | Chạy thử quy chế trên bộ hồ sơ mẫu | Một phần (route-preview); P1 lưu test vectors | P1 |
| D07 | Escalation L2 > 150% | P1 | P1 |
| D08 | Kiểm vượt định mức công tác (mock_travel) | P1 | P1 |
| D09 | OCR điền sẵn | P1 (`11` A5) | P1 |
| D10 | Màn hình xem lại trước khi gửi (D7) | Theo kế hoạch auto-assignment | P1 |

## E. Dữ liệu / triển khai live

| ID | Phát hiện | Việc | Ưu tiên |
|---|---|---|---|
| E01 | 0 người giữ AUDITOR | Gán cho một tài khoản kiểm soát (không phải admin) | P0 (demo kiểm toán) |
| E02 | `mock_hr.attendance` chưa có trên live, nên logic "vắng thì chuyển quản lý" đang tắt | **Đã xử lý 05/11:** bỏ migration mock 004. Trạng thái làm việc tính từ đơn nghỉ/công tác **đã duyệt** (`eas.user_leave_and_trips`) và giờ hành chính T2–T6 08:00–12:00, 13:30–17:30 (`eas.get_user_working_status`, migration 16); worker đọc được uỷ quyền `eas.approval_delegation` | ~~P1~~ Xong |
| E03 | `workflow_categories` và 9 view tương thích còn trong `eas` | DBA xác nhận trước khi chạy script xoá ngày 17/11/2026 | P1 |
| E04 | `app_user.username` di sản | Contract sau khi xác nhận không còn nơi đọc | P2 |
| E05 | Bộ luật AI: `ai_policy_version` 0 dòng; bản chạy ở tệp JSON | Một nguồn sự thật trong DB | P1 |
| E06 | Các bảng 0 dòng: `execution_issue`, `execution_attachment`, `approval_delegation`, `user_permissions` | Bổ sung kịch bản UAT trên bản sao local | P1 |

## F. AI

| ID | Phát hiện | Quyết định | Ưu tiên |
|---|---|---|---|
| F01 | Tự duyệt dùng trọng số tĩnh + luật, không dùng ML | **Sửa DOCX** (`11` K1) | P0 |
| F02 | UI gửi 4/19 đặc trưng; lifecycle và trọng số gán cứng sai | **Sửa code** `AiAssist.jsx` | P1 (nhỏ) |
| F03 | Số liệu độ chính xác trên dữ liệu tổng hợp | **Sửa DOCX**: ghi rõ phạm vi; thêm baseline luật | P0 |
| F04 | NLP 16 nhãn ↔ 58 loại | Ánh xạ / huấn luyện lại | P1 |
| F05 | `config.py` trỏ tới `label_encoder.pkl` không tồn tại | Xoá dòng cấu hình | P2 |
| F06 | Tự duyệt B/C (D5) | Theo kế hoạch auto-assignment; C vẫn cần nghiệm thu bởi người | P1 |

## G. An ninh và vệ sinh mã nguồn

| ID | Phát hiện | Việc | Ưu tiên |
|---|---|---|---|
| G01 | Gateway chuyển thẳng `/ai/*` ra ngoài (bảo vệ bằng secret) | **Đã gỡ 05/11** (kiểm toán S6): gateway không còn `/ai/`, Swagger AI, `/api/v1/mock/` | ~~P1~~ Xong |
| G02 | `@supabase/supabase-js` và `src/supabase.js` không dùng ở client/admin | **Đã xoá 05/11** ở cả `web_client` và `web_admin` (kiểm toán S8d) | ~~P1~~ Xong |
| G03 | Elasticsearch trong compose, không có code dùng | **Đã xoá 05/11** khỏi `docker-compose.yml` | ~~P2~~ Xong |
| G04 | Luồng dữ liệu tới Gemini chưa có trên SEC-01 | Bổ sung sơ đồ và đánh giá theo Nghị định 13/2023 | P0 (DOCX) |

## H. Điểm mạnh nên **giữ và nêu bật** trong DOCX (theo kinh nghiệm thẩm định)

1. FSM cưỡng chế ở **tầng CSDL** (`guard_request`, `guard_step`, trigger attempt): không thể bỏ qua dù gọi thẳng DB.
2. FK kép `(id, request_id)` cùng bảng append-only: chống lẫn dữ liệu giữa hồ sơ và chống sửa lịch sử.
3. Khoá `security_epoch` FOR SHARE / FOR UPDATE: tuần tự hoá thay đổi quyền với thao tác nghiệp vụ (SD-12).
4. Audit RFC 8785 + NFC + SHA-256 theo chuỗi từng hồ sơ: không có nút cổ chai khoá toàn cục.
5. Transactional outbox có lease, dedupe, DEAD, replay; một worker gánh mọi việc nền.
6. AI an toàn theo mặc định: chỉ A, trọng số ≤ 2, đủ guard như người duyệt, thu hồi 24 giờ, AI lỗi thì về người.
7. Học quy định tất định, khoá cổng nhân viên khi đang học: không có cửa sổ áp dụng nửa vời.
8. Tách tài khoản quản trị và vai trò nghiệp vụ bằng trigger; admin không đọc nội dung hồ sơ.
9. Mock ERP đọc qua **view đã lọc PII**, role chỉ đọc.

## I. Việc cần chủ đầu tư chốt (ảnh hưởng nội dung DOCX)

| # | Câu hỏi | Khuyến nghị của nhóm |
|---|---|---|
| Q1 | Bảng ngưỡng tiền chính thức cho các loại tiêu biểu (B02) | Dùng ngưỡng đang chạy: mua sắm 5M / 50M; chi phí 20M; ghi 30M của REG-002-3 là luật ép duyệt tay |
| Q2 | Nghỉ > 2 ngày: 1 hay 2 cấp (B07) | Giữ 2 cấp như live |
| Q3 | Ngưỡng nhắc SLA 50% hay 80% (B13) | 50% |
| Q4 | Có cần L2 > 150% không | Có; chỉ gửi OPS |
| Q5 | AUDITOR giao cho ai (E01) | Một tài khoản kiểm soát nội bộ riêng |

## J. Thứ tự thực hiện đề xuất

1. **P0 — sửa DOCX**: A01–A09, B01–B07, B12, B13 (sau khi chốt), B15–B18, B20–B21, B23–B24, C01–C18, F01, F03, G04.
   - Nguồn nội dung: tệp 00–11.
   - Ước lượng: 2–3 ngày công của BA + 1 ngày vẽ lại sơ đồ.
2. **P0 — dữ liệu demo**: E01.
3. **P1 — sửa code nhỏ** (mỗi việc dưới 0,5 ngày, có test): F02, G01, G02, D03, B19, B09.
4. **P1 — tính năng**: D01, D02, B14/D07, B22, E02, E05, D09 và kế hoạch auto-assignment D1–D9.
5. **P2**: các mục còn lại.

> Các việc sửa code chỉ được làm khi chủ đầu tư yêu cầu. Thay đổi CSDL live phải do chủ đầu tư chạy qua Supabase SQL Editor.
