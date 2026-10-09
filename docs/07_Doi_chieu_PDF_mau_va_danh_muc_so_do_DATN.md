# Đối chiếu PDF mẫu và danh mục sơ đồ dùng cho DATN EAS

**Tài liệu mẫu đã đọc:** `Report_DATN_CNTT_Nhom09_v1.0.pdf`
**Quy mô mẫu:** 245 trang PDF, báo cáo TinyTalk, tạo ngày 21/04/2026
**Mục tiêu:** dùng cấu trúc và độ sâu của mẫu làm benchmark, không sao chép nội dung hoặc hình ảnh.

## 1. Những gì PDF mẫu yêu cầu trên thực tế

PDF mẫu tổ chức phần kỹ thuật theo ba lớp:

1. Chương phân tích và thiết kế: yêu cầu, actor, activity, use case, kiến trúc tổng thể/client, dữ liệu khái niệm–logic–vật lý.
2. Chương xây dựng/triển khai: giao diện, topology triển khai, môi trường, quy trình triển khai, kiểm thử và kết quả.
3. Phụ lục: mô tả activity theo bước, đặc tả use case, sequence chi tiết, kiến trúc dịch vụ, ERD theo miền, từ điển vật lý và evidence test.

### Thống kê benchmark từ danh mục hình của mẫu

| Nhóm | Quy mô trong PDF mẫu | Nhận xét benchmark |
|---|---:|---|
| Activity diagram | 8 | Mỗi nhóm chức năng có 1 hình và bảng mô tả bước ở phụ lục |
| Use-case diagram | 9 | Một hình tổng quát và các hình tách theo chức năng |
| Sequence diagram | 17 | Tách CRUD/hành vi thành các sequence riêng |
| Architecture | 3 | Tổng thể, client và AI service |
| ERD/lược đồ logic | Khoảng 24 | Một overview và nhiều hình theo miền vì có hơn 60 bảng |
| UI screenshots | 29 | Chỉ có giá trị khi ứng dụng thực sự chạy |
| Test/evidence figures | Hơn 20 | Gồm code unit test, bảng testcase và kết quả thực thi |

## 2. Bộ EAS sau khi đối chiếu

| Nhóm | EAS hiện có | Chất lượng bổ sung so với mẫu |
|---|---:|---|
| Use case | 9 sơ đồ + contract 16 UC P0 | Tách rõ actor nghiệp vụ, quản trị, background và workspace; có scope/SoD và ma trận actor–UC |
| Activity | 10 sơ đồ | Bao phủ lifecycle, config, identity, privacy và cutover; có test mapping |
| Sequence | 22 sơ đồ | Có transaction boundary, lock, idempotency, audit/outbox, race, restore và mã lỗi; tách draft/resubmit/issue/reassign |
| State machine | 8 sơ đồ | Mẫu không có nhóm riêng; EAS dùng làm nguồn kiểm state-transition |
| Architecture/DFD/Security/Deployment | 9 sơ đồ | Có logical container, component, DFD 0/1, trust boundary, deployment, module dependency, sitemap |
| ERD | 10 sơ đồ | 3 domain overview + 7 detailed domain ERD cho 30 bảng |
| Test design | 100 TC + RTM/risk/gate | Tách DB validation khỏi acceptance; có evidence contract và concurrency/fault/DR |
| Tổng Mermaid source | 68 | Có source version-control, ID duy nhất và được đưa vào quy trình render validation |

Số lượng không phải tiêu chí duy nhất. Bộ EAS ưu tiên mỗi hình có nguồn trace, phạm vi, assumption, test mapping và cảnh báo trạng thái implementation.

## 3. Điểm PDF mẫu làm tốt cần giữ

- Có mục lục, danh mục bảng/hình, từ viết tắt và thuật ngữ.
- Tách nội dung chính ngắn gọn khỏi phụ lục chi tiết.
- Mỗi activity/use case có đoạn giải thích trước hình và caption dưới hình.
- Sequence tách theo thao tác để hình không quá tải.
- Dữ liệu trình bày theo ba mức khái niệm, logic và vật lý.
- Có giao diện thực tế và evidence test, không chỉ mô tả lý thuyết.

## 4. Điểm EAS phải làm tốt hơn mẫu

- Không dùng ảnh sơ đồ mờ hoặc chỉ lưu ảnh; luôn giữ Mermaid source và SVG/PDF export.
- Không lặp caption chung chung như “Lược đồ logic 1”; mỗi hình có ID duy nhất và phạm vi miền.
- Không để sequence chỉ có happy path; phải có `alt` cho quyền, validation, concurrency và rollback.
- Không dùng UI làm nguồn quyền; server-side guard phải xuất hiện trong sequence/test.
- Không ghi test `Passed` nếu thiếu build, môi trường, actual result và evidence.
- Không dùng ERD overview quá dày thay cho các domain ERD đọc được.
- Không mô tả thành phần chưa triển khai như hiện trạng; dùng nhãn `Target design` cho đến khi có evidence.

## 5. Cấu trúc chương đề xuất cho báo cáo EAS

### Chương 1 — Cơ sở lý thuyết và công nghệ

- Quy trình phê duyệt doanh nghiệp, SoD/four-eyes, SLA và auditability.
- Workflow/state machine, optimistic concurrency và idempotency.
- Transactional outbox, immutable audit/hash chain.
- RBAC có scope, privacy/retention/legal hold.
- Django/PostgreSQL/private object storage và lựa chọn công nghệ.
- So sánh giải pháp tham khảo và khoảng trống EAS giải quyết.

Không tuyên bố AI là công nghệ lõi P0. AI summary chỉ trình bày ở hướng phát triển nếu CR/P1 được chấp thuận.

### Chương 2 — Phân tích và thiết kế

1. Bài toán, actor, phạm vi và ba lifecycle A/B/C.
2. FR/BR/NFR và ma trận quyền.
3. Use case: dùng các hình trong `01_use_case.md`.
4. Activity: chọn AD-01, AD-02, AD-03, AD-04 cho chương; AD-05–10 đưa phụ lục.
5. State machine: ST-01, ST-03, ST-04, ST-07 trong chương; phần còn lại ở phụ lục.
6. Kiến trúc: AR-01, AR-02, AR-03, SEC-01.
7. DFD: DFD-00 và DFD-01.
8. Dữ liệu: ER-01/02/03 overview; ER-04–10 chi tiết ở phụ lục.
9. Sequence: SD-03, SD-04, SD-06, SD-08 trong chương; các sequence khác ở phụ lục.

### Chương 3 — Xây dựng, triển khai và kiểm thử

- Cấu trúc source thực tế và module đã triển khai.
- API/UI screenshots phải lấy từ build thật.
- DP-01 cùng manifest/IaC thực tế.
- Migration/schema và kết quả DB validation.
- Chiến lược, risk matrix, RTM, testcase và kết quả.
- Performance, security, concurrency, restore và UAT evidence.
- Hạn chế: nêu rõ phần chưa triển khai/chưa test.

### Phụ lục

- A: Use-case contract 16 UC và activity step tables.
- B: Toàn bộ 18 sequence và 8 state machine.
- C: ERD chi tiết, data dictionary 30 bảng và API catalog.
- D: `TC001–TC100`, execution record và evidence index.
- E: Runbook deploy/rollback/restore, legal/privacy matrix.

## 6. Mẫu trình bày một sơ đồ trong luận văn

Mỗi hình nên có cấu trúc cố định:

```text
2.x.y. Tên sơ đồ

Đoạn 1: mục tiêu, actor và trigger.
Đoạn 2: happy path và quyết định chính.
Đoạn 3: ngoại lệ, transaction/security guard và hậu điều kiện.

[Hình SVG/PDF, chữ còn đọc được khi in A4]
Hình 2.x: <Tên chính xác> (Nguồn: Nhóm tác giả)

Truy vết: UCxx, FRxx, BRxx, API..., TCxxx–TCyyy.
```

Quy tắc bố cục:

- Một hình không vượt quá một trang A4; nếu chữ dưới 9pt thì tách hình.
- Activity dùng swimlane; sequence tối đa khoảng 6–8 lifeline/hình.
- Dùng một palette và font thống nhất; màu chỉ hỗ trợ, không mang nghĩa duy nhất.
- Caption đánh số tự động bằng Word/LaTeX; không gõ số hình thủ công.
- Cross-reference tự động tới hình/bảng/phụ lục.
- Xuất SVG hoặc PDF vector; PNG chỉ dùng cho screenshot giao diện/evidence.

## 7. Checklist hoàn thiện để thật sự vượt mẫu

### Có thể hoàn thành ngay từ thiết kế

- [x] Use case/activity/sequence/state có source và trace.
- [x] Architecture, DFD, security, deployment target design.
- [x] ERD theo miền và data dictionary 30 bảng từ tài liệu 03.
- [x] 100 acceptance test, RTM, risk, gate và evidence schema.
- [x] Cảnh báo mâu thuẫn `plan.md` và baseline v2.

### Chỉ hoàn thành sau khi ứng dụng tồn tại

- [ ] Screenshot UI thật cho bốn tab, form A/B/C, detail/timeline, admin, report và error states.
- [ ] API documentation sinh từ implementation/OpenAPI.
- [ ] Unit/integration/E2E source và coverage/mutation report.
- [ ] Evidence actual cho `TC001–TC100`.
- [ ] Performance/security/concurrency report trên môi trường đã ghi cấu hình.
- [ ] Deployment/IaC screenshot và URL/image digest/config IDs thật.
- [ ] Restore/cutover rehearsal, UAT signature và production smoke.

Không được tạo ảnh giả hoặc ghi PASS để làm báo cáo trông đầy đủ. Với DATN, việc nêu trung thực phạm vi đã triển khai và bằng chứng đo được có giá trị hơn số trang.

## 8. Danh mục file nguồn đưa vào luận văn

| Nội dung | File nguồn |
|---|---|
| Quy chuẩn và thuật ngữ | `06_Huong_dan_mo_hinh_hoa_va_kiem_thu.md` |
| Use case | `diagrams/01_use_case.md` |
| Activity | `diagrams/02_activity.md` |
| Sequence | `diagrams/03_sequence.md` |
| State machine | `diagrams/04_state_machine.md` |
| Architecture/DFD/ERD/deployment | `diagrams/05_architecture_and_data.md` |
| Test/RTM | `testing/01_test_case_and_rtm.md` |
| Baseline nghiệp vụ | DOCX `00`–`05` |
| Benchmark trình bày | `Report_DATN_CNTT_Nhom09_v1.0.pdf` |
