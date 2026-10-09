# Tiêu chuẩn chất lượng sơ đồ cho đồ án EAS

**Mã:** EAS-DOC-07B · **Phiên bản:** 1.0 · **Ngày:** 09/10/2026
**Tài liệu tham chiếu chất lượng:** `Report_DATN_CNTT_Nhom09_v1.0.pdf` (245 trang)
**Nguyên tắc:** Chỉ tham khảo mức độ hoàn thiện và cách chứng minh; không sao chép cấu trúc, nội dung hoặc nghiệp vụ TinyTalk.

## 1. Tiêu chí chất lượng rút ra từ tài liệu mẫu

Tài liệu mẫu thể hiện các điểm đáng học:

- sơ đồ có mã/tên/caption và nguồn rõ;
- phần chính trình bày bức tranh tổng quát, phần chi tiết có bảng giải thích;
- use case có actor, điều kiện, luồng chính, luồng phụ và kết quả;
- sequence được tách theo thao tác, tránh một hình chứa toàn hệ thống;
- dữ liệu được trình bày từ khái niệm đến logic và vật lý;
- kiểm thử có test case và bằng chứng kết quả;
- thuật ngữ, đánh số hình/bảng và mục lục được duy trì nhất quán.

EAS phải tốt hơn ở các điểm kỹ thuật mà tài liệu mẫu chưa nhấn mạnh: traceability đến requirement/API/entity/test, trạng thái kiểm thử trung thực, nhánh concurrency/failure, security/SoD, audit, idempotency, DR và source Mermaid có thể render lại.

## 2. Quality gate cho mỗi sơ đồ

Một sơ đồ chỉ được đánh dấu `REVIEWED` khi đạt toàn bộ:

| Nhóm | Tiêu chí bắt buộc |
|---|---|
| Nhận dạng | Có ID duy nhất, tên, version/baseline và loại `Target design` hoặc `As-is` |
| Phạm vi | Nêu mục tiêu, trigger, tiền/hậu điều kiện và nội dung ngoài phạm vi |
| Chính xác | Chỉ dùng actor/state/entity/API có trong baseline hoặc CR đã ký |
| Đọc được | Một hình có một mục tiêu; label ngắn; không giao cắt vô nghĩa; legend khi cần |
| Nhánh | Happy path cùng lỗi nghiệp vụ/quyền/version/race trọng yếu |
| Trách nhiệm | Lane/lifeline/component đúng owner; không biến module nội bộ thành microservice giả |
| Dữ liệu | Tên state/entity nhất quán với schema; không có liên kết chéo request |
| Kiểm soát | Quyền, SoD, transaction, audit/outbox/idempotency thể hiện tại nơi phù hợp |
| Trace | Liên kết UC/FR/BR/NFR/API/entity và ít nhất một TC cho mỗi transition quan trọng |
| Trình bày | Render Mermaid thành công; caption “Nguồn: Nhóm tác giả”; font/khổ hình đọc được |
| Review | BA + Tech Lead + QA; thêm Security/DBA/DevOps theo loại hình |

## 3. Bộ sơ đồ hiện có

| Nhóm | Số hình | Nội dung |
|---|---:|---|
| Use case | 9 | Context, quan hệ UC, core, admin, background và 4 góc nhìn actor/control |
| Activity | 10 | A/B/C, submit, decision, execution, reassign, SLA, config, identity, privacy, cutover |
| Sequence | 22 | Auth, file, submit, decision, race, execution, worker, governance, privacy và DR |
| State machine | 8 | Request, instance, step, attempt, attachment, SLA, outbox, config release |
| Kiến trúc/dữ liệu | 19 | Context, container, component, deployment, DFD, trust boundary, sitemap và 10 ERD |
| **Tổng** | **68** | Không tính bảng RTM, risk matrix và 100 test case |

Số lượng không phải tiêu chí duy nhất. Một hình trùng lặp hoặc sai baseline phải xóa dù làm tổng số giảm.

## 4. Chuẩn caption và thuyết minh

Khi đưa hình vào báo cáo, dùng mẫu:

```text
Hình 2.x. [Tên nghiệp vụ rõ nghĩa]
Nguồn: Nhóm tác giả, xây dựng từ EAS SRS v2.0 và schema v2.0.1.
Mục đích: [một câu].
Điểm cần đọc: [2–4 quyết định/guard quan trọng].
Truy vết: UCxx, FRxx, BRxx/NFRxx, TCxxx–yyy.
```

Không dùng caption chung chung như “Biểu đồ hệ thống”. Không ghi “Nguồn: Internet” cho hình do nhóm tự dựng. Nếu dùng chuẩn/ký hiệu của nguồn ngoài, trích dẫn chuẩn đó riêng, không biến nguồn ký hiệu thành nguồn nội dung nghiệp vụ.

## 5. Chuẩn thuyết minh theo loại hình

### Use case

Kèm bảng: ID, mục tiêu, actor, trigger, tiền điều kiện, luồng chính, luồng thay thế/ngoại lệ, hậu điều kiện, business rules và trace. SRS v2 đã có 16 use case P0; khi chuyển vào luận văn không được rút mất nhánh quyền và conflict.

### Activity

Kèm bảng bước có `STT`, `Lane/Owner`, `Action`, `Guard/Input`, `Output/State`, `Exception`, `TC`. Bước state change phải là kết quả sau commit, không phải sau thao tác bấm nút.

### Sequence

Kèm phần tiền điều kiện, participant, transaction boundary, response/error contract và postcondition. Với command ghi, phải có version/idempotency/quyền/state/audit/outbox; với worker phải có lease/dedupe/retry.

### State machine

Kèm transition table: From, Event, Guard, To, side effect, forbidden transitions và tests. Terminal state phải được chỉ rõ.

### Architecture/DFD/ERD

Kèm boundary, responsibility, data classification và assumption. ERD khái niệm dùng ở phần tổng quan; ERD logic theo miền và từ điển 30 bảng/260 cột dùng để chứng minh thiết kế chi tiết.

### Test case

Phải có actual result và evidence mới được PASS. Screenshot chỉ bổ trợ; log/query/correlation/build/config mới giúp tái lập. Không trộn `DB-VAL 98/98 PASS` với `TC001–TC100 NOT RUN`.

## 6. Chất lượng hình khi xuất báo cáo

- Ưu tiên SVG/PDF vector; nếu PNG thì tối thiểu 2000 px chiều ngang cho hình toàn trang.
- Font cuối cùng không nhỏ hơn 9 pt khi đặt vào khổ A4.
- Hình rộng dùng trang landscape, không thu nhỏ đến mức không đọc được.
- Màu phải còn phân biệt khi in xám; không dùng màu là tín hiệu duy nhất.
- Mỗi hình không quá khoảng 7–9 node chính nếu có thể tách hợp lý.
- Dùng cùng thuật ngữ tiếng Anh/Việt trên toàn báo cáo; state và mã kỹ thuật giữ nguyên tiếng Anh.
- Không chèn ảnh chụp Mermaid editor; xuất file sạch và giữ source `.md` trong repository.

## 7. Review checklist trước khi đưa vào bản nộp

1. Đối chiếu KD01–KD08 và CR mới nhất.
2. Chạy render toàn bộ Mermaid; không chấp nhận hình lỗi cú pháp.
3. Đối chiếu state với CHECK/trigger và API error contract.
4. Chạy RTM orphan check: requirement không có hình/test và hình không có requirement.
5. Kiểm tra tất cả caption, nguồn, đánh số và tham chiếu chéo.
6. Kiểm tra hình không tuyên bố component chưa triển khai là `As-is`.
7. Cập nhật trạng thái test từ execution record, không từ nội dung expected.
8. Review chéo bởi ít nhất BA, Tech Lead và QA; ký ngày/version review.

## 8. Những điều không lấy từ tài liệu mẫu

- Không dùng kiến trúc, actor, AI, database hay use case của TinyTalk cho EAS.
- Không sao chép thứ tự chương/phụ lục chỉ để giống hình thức.
- Không dùng số lượng trang/hình làm bằng chứng chất lượng.
- Không gắn `PASS` từ ảnh chụp hoặc mô tả kỳ vọng khi chưa chạy.
- Không vẽ công nghệ trong `plan.md` cũ nếu đã bị baseline v2 loại khỏi P0.
