# Kế hoạch: Bộ tài liệu phân tích thiết kế theo DOCX + đối soát code/data/AI

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-11-04-01 |
| Ngày mở | 04/11/2026 |
| Trạng thái | DONE (chờ chủ đầu tư chốt Q1–Q5 ở tệp 12 §I) |
| Nguồn đặc tả | `workspace/Report_DATN_CNTT_Nhom07_v1.0.docx` (1.139 khối, 74 hình, 26 bảng) |
| Đầu ra | `workspace/phan_tich_thiet_ke/` (thư mục mới; `workspace/analysis_design/` có sẵn từ trước được giữ nguyên, không ghi đè) |

## 1. Yêu cầu

Theo thứ tự DOCX, soạn md cho từng phần phân tích thiết kế: mỗi **loại sơ đồ một file chứa tất cả sơ đồ loại đó**; thiết kế CSDL; huấn luyện AI. Đối soát DOCX ↔ code ↔ data ↔ AI: lệch ở đâu, phương án nào hợp lý hơn (theo tiêu chuẩn: UML 2.5, BPMN 2.0, COSO/SoD, OWASP ASVS, ISO 25010, ML model reporting), không bỏ sót trường hợp.

## 2. Phương pháp

1. Trích DOCX theo đúng thứ tự (tiêu đề, đoạn, bảng, hình + chú thích) → `scratchpad/docx/docx_body.md`, ảnh → `scratchpad/docx/media/`.
2. Đọc từng hình sơ đồ, chép lại nội dung (tác nhân, ca sử dụng, bước, thông điệp, trạng thái, thực thể).
3. Với mỗi sơ đồ: (a) nội dung theo DOCX; (b) bằng chứng code/DB/AI (file:dòng, bảng/cột, artifact); (c) lệch; (d) phán quyết + sơ đồ chuẩn hoá (Mermaid) phản ánh phương án hợp lý.
4. Mức lệch: **KHỚP** · **LỆCH NHẸ** (tên/hiển thị) · **LỆCH NGHIỆP VỤ** · **THIẾU HIỆN THỰC** · **DOCX SAI/KHÔNG NÊN LÀM**.
5. Không chạy thao tác ghi trên DB live; dữ liệu đọc từ live chỉ đọc hoặc bản sao.

## 3. Danh mục đầu ra (theo thứ tự DOCX)

| # | Tệp | Phần DOCX | Trạng thái |
|---|---|---|---|
| 00 | `00_MUC_LUC_VA_PHUONG_PHAP.md` | — | DONE |
| 01 | `01_PHAN_TICH_YEU_CAU.md` | 2.1 (tác nhân, phân hệ, UC P0, phi chức năng) | DONE |
| 02 | `02_QUY_TRINH_NGHIEP_VU.md` | 1.1.2, 1.2.2, 2.2.1–2.2.7 (vòng đời, Template A/B/C) | DONE |
| 03 | `03_SO_DO_USE_CASE.md` | 2.2.8 + Phụ lục A | DONE |
| 04 | `04_SO_DO_ACTIVITY.md` | 2.2.9 + Phụ lục B | DONE |
| 05 | `05_SO_DO_SEQUENCE.md` | 2.2.10 + Phụ lục C | DONE |
| 06 | `06_SO_DO_KIEN_TRUC_VA_THANH_PHAN.md` | 2.3.1–2.3.6 | DONE |
| 07 | `07_SO_DO_TRANG_THAI.md` | Phụ lục D | DONE |
| 08 | `08_SO_DO_ERD.md` | 2.3.7 + Phụ lục E | DONE |
| 09 | `09_THIET_KE_CO_SO_DU_LIEU.md` | 1.4.3, 2.3.8 | DONE |
| 10 | `10_THIET_KE_GIAO_DIEN.md` | 2.4 | DONE |
| 11 | `11_THIET_KE_VA_HUAN_LUYEN_AI.md` | 1.3, 1.4.5, 3.2.11 | DONE |
| 12 | `12_SO_LECH_VA_QUYET_DINH.md` | Tổng hợp mọi lệch + khuyến nghị | DONE |

## 4. Nhật ký tiến trình

- 04/11/2026: trích DOCX xong (`scratchpad/docx/docx_body.md`, 74 ảnh). Đã đọc: Phần mở đầu, Chương 1, 2.1, 2.2.1–2.2.8 (dòng 1–432).
- 04/11/2026: đọc xong toàn bộ DOCX đến hết Phụ lục E (ER-13, img_074). Tiếp: xem ảnh sơ đồ, gom bằng chứng code/DB/AI, rồi viết 00→12.
- 04/11/2026: xem xong 50 ảnh sơ đồ (ghi chép: scratchpad/diagram_notes.md; bảng chú thích↔ảnh nằm trong 00). Bằng chứng live: scratchpad/live_catalog.txt, live_columns.txt. Viết xong 00, 01.
- 04/11/2026: viết xong 02, 03, 04, 05. Tiếp: 06 kiến trúc.
- 04/11/2026: viết xong 06, 07, 08 (đã đối chiếu cột ERD với information_schema live). Tiếp: 09 CSDL.
- 04/11/2026: viết xong 09. Tiếp: 10 giao diện, 11 AI, 12 sổ lệch.
- 04/11/2026: viết xong 10, 11. Tiếp: 12 sổ lệch tổng hợp.
- 04/11/2026: viết xong 12. Hoàn tất bộ 13 tệp tại workspace/phan_tich_thiet_ke/. Việc tiếp theo phụ thuộc chủ đầu tư: chốt Q1–Q5, chọn hạng mục P0/P1 để sửa DOCX/code.
- 04/11/2026: phát hiện 00/01/02 bị mất khỏi đĩa (không do lệnh của phiên này); đã ghi lại đủ nội dung.
- 04/11/2026 (tiếp): theo yêu cầu 'viết lại thành chương báo cáo' + Q1–Q5 theo khuyến nghị → tạo workspace/bao_cao_hoan_chinh/00–14 (nội dung dán vào DOCX). Đối soát 2 lần: (1) script kiểm mọi đường dẫn/dòng/bảng/cột/mã lỗi/endpoint với code + catalog live; (2) render 61/61 khối Mermaid bằng mermaid 11.4.1 + Chromium, kiểm 64 tên hàm test trích dẫn. Test chạy lại: api_core 290/290, tests 153 (1 skip), web 64/64, coverage 62%.
- 04/11/2026 (tiếp): kiểm toán code/data/DB, kết quả ở docs/KIEM_TOAN_CODE_DATA_2026-11-04.md.
- 04/11/2026 (tiếp): sửa code kèm test (S1, L1–L4, M1 dự phòng) và thêm lệnh repair_workflow_consistency.
- 04/11/2026 (tiếp): thiết kế schema v2. Migration 14 (expand) và 15 (contract), mỗi file có rollback, cùng data fix TOP_LEVEL_APPROVER. Tài liệu: docs/THIET_KE_SCHEMA_EAS_V2.md; changelog: changelogs/2026-11-04_audit_fixes_schema_v2.md.
- Đã kiểm trên bản sao local. Bạn cần làm trên live: chạy 14, chạy lệnh repair, gán AUDITOR, sau ≥7 ngày chạy 15.
- 04/11/2026 (tiếp): đọc trực tiếp schema eas trên live. 9 view bí danh, eas_deprecated, 3 cặp bảng cùng chức năng. Viết lại migration 15 thành 15_schema_v2_consolidate.sql: gộp, dời sang eas_archive, không xoá dữ liệu. Thêm lệnh import_legacy_changelog. Đã kiểm trên bản sao dựng đúng hiện trạng live.
