# Kế hoạch: Bộ tài liệu phân tích thiết kế theo DOCX + đối soát code/data/AI

| Thuộc tính | Giá trị |
|---|---|
| Mã | EAS-PLAN-2026-11-04-01 |
| Ngày mở | 04/11/2026 |
| Trạng thái | ACTIVE |
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
| 02 | `02_QUY_TRINH_NGHIEP_VU.md` | 1.1.2, 1.2.2, 2.2.1–2.2.7 (vòng đời, Template A/B/C) | TODO |
| 03 | `03_SO_DO_USE_CASE.md` | 2.2.8 + Phụ lục A | TODO |
| 04 | `04_SO_DO_ACTIVITY.md` | 2.2.9 + Phụ lục B | TODO |
| 05 | `05_SO_DO_SEQUENCE.md` | 2.2.10 + Phụ lục C | TODO |
| 06 | `06_SO_DO_KIEN_TRUC_VA_THANH_PHAN.md` | 2.3.1–2.3.6 | TODO |
| 07 | `07_SO_DO_TRANG_THAI.md` | Phụ lục D | TODO |
| 08 | `08_SO_DO_ERD.md` | 2.3.7 + Phụ lục E | TODO |
| 09 | `09_THIET_KE_CO_SO_DU_LIEU.md` | 1.4.3, 2.3.8 | TODO |
| 10 | `10_THIET_KE_GIAO_DIEN.md` | 2.4 | TODO |
| 11 | `11_THIET_KE_VA_HUAN_LUYEN_AI.md` | 1.3, 1.4.5, 3.2.11 | TODO |
| 12 | `12_SO_LECH_VA_QUYET_DINH.md` | Tổng hợp mọi lệch + khuyến nghị | TODO |

## 4. Nhật ký tiến trình

- 04/11/2026: trích DOCX xong (`scratchpad/docx/docx_body.md`, 74 ảnh). Đã đọc: Phần mở đầu, Chương 1, 2.1, 2.2.1–2.2.8 (dòng 1–432).
- 04/11/2026: đọc xong toàn bộ DOCX đến hết Phụ lục E (ER-13, img_074). Tiếp: xem ảnh sơ đồ, gom bằng chứng code/DB/AI, rồi viết 00→12.
- 04/11/2026: xem xong 50 ảnh sơ đồ (ghi chép: scratchpad/diagram_notes.md; bảng chú thích↔ảnh nằm trong 00). Bằng chứng live: scratchpad/live_catalog.txt, live_columns.txt. Viết xong 00, 01.
