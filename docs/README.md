# Hồ sơ tài liệu Enterprise Approval System

## Baseline được dùng

| Thuộc tính | Giá trị |
|---|---|
| Baseline nghiệp vụ | Bộ tài liệu v2.0 ngày 21/09/2026 (`00`–`05`) |
| Baseline dữ liệu | EAS database v2.0.1 |
| Phạm vi sơ đồ | P0: Web tiếng Việt, một doanh nghiệp, LEAVE/A, ACCESS/B, EQUIPMENT/C |
| Trạng thái | Thiết kế chờ các quyết định KD01–KD08 và bằng chứng kiểm thử thực thi |
| Nguồn ưu tiên khi mâu thuẫn | Quyết định đã ký → DOCX v2 → SQL v2.0.1 → tài liệu hướng dẫn này → `plan.md` cũ |

> `plan.md` là tài liệu ý tưởng nguồn, không phải baseline triển khai. AI auto-approve, OCR/risk scoring, OPA, mobile, ERP webhook, delegation tự động, approval song song và workflow builder tổng quát không thuộc P0. Không dùng các trạng thái cũ như `EVALUATING`, `AUTO_APPROVED`, `EXECUTED` hoặc `EXECUTION_REJECTED`.

## Danh mục

| Mã | Tài liệu | Mục đích |
|---|---|---|
| 00 | [Phạm vi và kế hoạch](./00_Pham_vi_va_ke_hoach_v2.docx) | Phạm vi, quyết định, kế hoạch, cổng chất lượng |
| 01 | [SRS](./01_SRS_v2.docx) | FR/BR/NFR, quyền và 16 use case P0 |
| 02 | [Phân tích và thiết kế](./02_Phan_tich_thiet_ke_v2.docx) | Kiến trúc, trạng thái, giao dịch, worker |
| 03 | [Dữ liệu và API](./03_Du_lieu_va_API_v2.docx) | 30 bảng, invariant, API và mã lỗi |
| 04 | [Kế hoạch và ca kiểm thử](./04_Ke_hoach_va_ca_kiem_thu_v2.docx) | 100 test case nghiệm thu, hiện chưa thực thi |
| 05 | [Vận hành, pháp lý và nghiệm thu](./05_Van_hanh_phap_ly_nghiem_thu_v2.docx) | Runbook, DR, pháp lý, go/no-go |
| 06 | [Hướng dẫn mô hình hóa và kiểm thử](./06_Huong_dan_mo_hinh_hoa_va_kiem_thu.md) | Quy chuẩn vẽ, review, traceability và test design |
| 06A | [Use case](./diagrams/01_use_case.md) | Actor, phạm vi hệ thống và quan hệ UC |
| 06B | [Activity](./diagrams/02_activity.md) | Luồng A/B/C, bổ sung, gán thay, SLA |
| 06C | [Sequence](./diagrams/03_sequence.md) | Tương tác dịch vụ, transaction và nhánh lỗi |
| 06D | [State machine](./diagrams/04_state_machine.md) | Trạng thái request, workflow, step, attempt, file, SLA, outbox, release |
| 06E | [Kiến trúc, DFD, deployment và ERD](./diagrams/05_architecture_and_data.md) | Context, container, component, bảo mật, triển khai và dữ liệu theo miền |
| 06E-GUIDE | [Danh mục và cách xuất 68 sơ đồ](./diagrams/README.md) | Xuất SVG, caption, bố cục A4 và quality gate |
| 06F | [Test case và RTM](./testing/01_test_case_and_rtm.md) | Chiến lược, mẫu ca, danh mục 100 TC, cổng nghiệm thu |
| 07 | [Đối chiếu PDF mẫu và danh mục DATN](./07_Doi_chieu_PDF_mau_va_danh_muc_so_do_DATN.md) | Benchmark 245 trang, cấu trúc luận văn và checklist evidence |
| 07B | [Tiêu chuẩn chất lượng sơ đồ DATN](./07_Tieu_chuan_chat_luong_so_do_DATN.md) | Quality gate, caption, thuyết minh, review và điều kiện đổi Target thành As-is |
| 08 | [Báo cáo thẩm định và lộ trình thương mại](./08_Bao_cao_tham_dinh_va_lo_trinh_thuong_mai.md) | Chấm điểm có bằng chứng, backlog P0, định vị, pricing giả định và roadmap pilot |
| 09 | [Biên bản kiểm chứng Supabase](./09_Bien_ban_kiem_chung_Supabase.md) | Kết quả read-only trên project thật, giới hạn bằng chứng và việc bảo mật bắt buộc |
| 10 | [Báo cáo thực thi nâng cấp](./10_Bao_cao_thuc_thi_nang_cap.md) | Thay đổi đã làm, kết quả gate, blocker và phạm vi chưa hoàn tất |
| 11 | [Phản biện hội đồng và điểm mù](./11_Phan_bien_hoi_dong_va_diem_mu.md) | 52 câu hỏi bảo vệ, ma trận điểm yếu, bản sửa và bằng chứng |
| 12 | [Nền tảng dữ liệu giả lập và API tích hợp](./12_Nen_tang_du_lieu_gia_lap_va_API_tich_hop.md) | 8 schema nguồn giả lập, API chỉ đọc, coverage request nội bộ và bằng chứng Supabase |
| 13 | [Biên bản runtime, E2E, DR và container](./13_Bien_ban_kiem_chung_runtime_E2E_DR.md) | Bằng chứng stack chạy thật, browser E2E, accessibility, restore rehearsal, image scan và residual risk |
| Mẫu | [Report DATN Nhóm 09](./Report_DATN_CNTT_Nhom09_v1.0.pdf) | Tài liệu tham chiếu bố cục và độ sâu, không phải nguồn nghiệp vụ EAS |

## Trạng thái thực tế cần hiểu đúng

- Các thư mục service hiện chủ yếu có README; chưa có backend/frontend/mobile/rules-engine hoàn chỉnh để nghiệm thu E2E.
- `tests/README.md` mô tả cấu trúc dự kiến; chưa có bộ E2E/integration chạy được.
- Database đã có schema, seed và regression SQL. Báo cáo hiện ghi **98/98 phép kiểm DB PASS trên PGlite một backend** và **86 thông báo assertion** ở lượt tái lập. Đây không phải 100 test case nghiệm thu trong tài liệu 04.
- 100 test case `TC001`–`TC100` phải giữ trạng thái `NOT RUN` cho đến khi có actual result, môi trường, release và evidence tương ứng.

## Quy tắc cập nhật

Mọi thay đổi workflow phải cập nhật trong cùng change request: FR/BR/UC, state/event, API/schema, use-case/activity/sequence, test case/RTM và runbook nếu ảnh hưởng vận hành. Không đóng thay đổi chỉ bằng việc sửa một sơ đồ.
