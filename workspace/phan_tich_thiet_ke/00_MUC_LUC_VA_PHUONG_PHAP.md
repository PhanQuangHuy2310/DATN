# 00 — Mục lục, phương pháp và kết luận nhanh

| Thuộc tính | Giá trị |
|---|---|
| Nguồn đặc tả | `workspace/Report_DATN_CNTT_Nhom07_v1.0.docx` (1.139 khối, 74 ảnh, 26 bảng) |
| Đối chiếu với | mã nguồn `api_core/`, `ai_service/`, `web_client/`, `web_admin/`, `mobile_app/`, `api_gateway/`, `database/`, `supabase/`; CSDL Supabase live (chỉ đọc, 04/11/2026) |
| Kế hoạch | `plans/active/2026-11-04_workspace_analysis_design_reconciliation.md` (EAS-PLAN-2026-11-04-01) |
| Người soạn | Nhóm vai trò PM · PO · BA · Dev · UI/UX · AI Eng · Tester · QA |
| Ngày | 04/11/2026 |

## 1. Danh mục tài liệu (đúng thứ tự DOCX)

| # | Tệp | Phần DOCX | Nội dung |
|---|---|---|---|
| 00 | `00_MUC_LUC_VA_PHUONG_PHAP.md` | — | Mục lục, phương pháp, đối chiếu chú thích ↔ ảnh, kết luận nhanh |
| 01 | `01_PHAN_TICH_YEU_CAU.md` | 2.1 | Tác nhân, phân hệ, ca sử dụng P0, yêu cầu phi chức năng |
| 02 | `02_QUY_TRINH_NGHIEP_VU.md` | 1.1.2, 1.2.2, 2.2.1–2.2.7, 2.3.2–2.3.5 | Vòng đời 6 giai đoạn, Template A/B/C, BRE, SLA, RBAC |
| 03 | `03_SO_DO_USE_CASE.md` | 2.2.8 + Phụ lục A | 9 sơ đồ use case |
| 04 | `04_SO_DO_ACTIVITY.md` | 2.2.9 + Phụ lục B | 10 sơ đồ hoạt động |
| 05 | `05_SO_DO_SEQUENCE.md` | 2.2.10 + Phụ lục C | 22 sơ đồ tuần tự |
| 06 | `06_SO_DO_KIEN_TRUC_VA_THANH_PHAN.md` | 2.3.1, 2.3.6 | AR-01..03, DP-01, DFD-00/01, SEC-01 |
| 07 | `07_SO_DO_TRANG_THAI.md` | 2.3.1 + Phụ lục D | ST-01..ST-08 và vòng đời tệp đính kèm |
| 08 | `08_SO_DO_ERD.md` | 2.3.7 + Phụ lục E | ER-01..ER-13 |
| 09 | `09_THIET_KE_CO_SO_DU_LIEU.md` | 1.4.3, 2.3.8 | Từ điển dữ liệu, ràng buộc, trigger, RLS, dữ liệu live |
| 10 | `10_THIET_KE_GIAO_DIEN.md` | 2.4 | Thiết kế giao diện (DOCX chỉ có tiêu đề) |
| 11 | `11_THIET_KE_VA_HUAN_LUYEN_AI.md` | 1.3, 1.4.5, 3.2.11 | Mô hình, dữ liệu, huấn luyện, đánh giá, vận hành AI |
| 12 | `12_SO_LECH_VA_QUYET_DINH.md` | — | Sổ lệch tổng hợp, quyết định và việc cần làm |

## 2. Phương pháp

1. **Trích DOCX theo đúng thứ tự** bằng python-docx: tiêu đề, đoạn, bảng, ảnh và chú thích.
2. **Đọc từng ảnh sơ đồ** và chép lại nội dung: tác nhân, ca sử dụng, bước, thông điệp, trạng thái, thực thể.
3. **Đối chiếu ảnh với chú thích** bằng nội dung và mã MD5 của ảnh. Bước này phát hiện ảnh trùng và ảnh đặt sai chỗ.
4. **Tìm bằng chứng cho mỗi sơ đồ** ở ba nguồn:
   - mã nguồn, ghi `tệp:dòng`;
   - lược đồ CSDL: bảng, cột, CHECK, trigger;
   - dữ liệu live, chỉ đọc bằng role backend.
5. **Kết luận cho mỗi sơ đồ** theo bốn mục:
   - (a) DOCX nói gì;
   - (b) code/DB/AI thực tế làm gì;
   - (c) chỗ lệch;
   - (d) phán quyết, kèm sơ đồ chuẩn hoá bằng Mermaid khi cần.

Mức lệch:

| Mức | Ý nghĩa |
|---|---|
| **KHỚP** | DOCX và hệ thống thống nhất |
| **LỆCH NHẸ** | Khác tên gọi, hằng số hoặc cách trình bày; không đổi nghiệp vụ |
| **LỆCH NGHIỆP VỤ** | Khác hành vi nghiệp vụ; phải chọn một phương án |
| **THIẾU HIỆN THỰC** | DOCX mô tả nhưng hệ thống chưa có |
| **DOCX SAI/KHÔNG NÊN LÀM** | Nội dung DOCX sai kỹ thuật, mâu thuẫn nội bộ hoặc trái tiêu chuẩn |

Tiêu chuẩn đối chiếu:
- UML 2.5.1 (use case, activity, sequence, state machine);
- BPMN 2.0 (luồng nghiệp vụ);
- ký pháp ERD crow's foot (IE);
- COSO 2013 và nguyên tắc tách nhiệm (SoD, four-eyes);
- OWASP ASVS 4.0.3;
- ISO/IEC 25010 (chất lượng phần mềm);
- Model Cards / ML model reporting (báo cáo mô hình AI);
- Nghị định 13/2023/NĐ-CP (bảo vệ dữ liệu cá nhân).

Ràng buộc an toàn khi làm tài liệu này:
- chỉ chạy truy vấn đọc trên DB live;
- không in ra bất kỳ khoá hay mật khẩu nào;
- không sửa thư mục `workspace/analysis_design/` có sẵn.

## 3. Phát hiện quan trọng nhất về hình ảnh trong DOCX

### 3.1 18 hình ở Chương 2 là ảnh lặp

So mã MD5 cho thấy:
- Hình 2.10–2.19 là **cùng một ảnh** `img_006`.
- Hình 2.20–2.27 là **cùng một ảnh** `img_007`.

Như vậy các sơ đồ sau trong thân báo cáo **không có hình thật**:
- SD-03, SD-04, SD-06, SD-08;
- AR-01, AR-02, AR-03;
- DFD-00, DFD-01;
- ST-01, ST-02, ST-03, ST-06, ST-07;
- SEC-01;
- ER-01, ER-02, ER-03.

Ngoài ra, phần mô tả của Hình 2.10–2.21 được chép nguyên văn từ Hình 2.1/2.2.

### 3.2 Chú thích bị xáo trộn

Mỗi ảnh đều có tiêu đề in sẵn trong hình. Tiêu đề này cho biết ảnh thật sự là sơ đồ nào.

| Chú thích trong DOCX | Ảnh | Nội dung thật của ảnh |
|---|---|---|
| Hình 2.1 UC-CTX-01 | img_006 | UC-BIZ-02 |
| Hình 2.2 UC-REL-01 | img_007 | UC-APR-01 |
| Hình 2.3 UC-BIZ-01 | img_008 | UC-SYS-01 |
| Hình 2.4 UC-ADM-01 | img_009 | UC-BIZ-03 |
| Hình 2.5 AD-01 | img_010 | AD-07 |
| Hình 2.6 AD-02 | img_011 | AD-01 |
| Hình 2.7 AD-03 | img_012 | AD-04 |
| Hình 2.8 AD-04 | img_013 | AD-05 |
| Hình 2.9 SD-01 | img_014 | SD-11 |
| PL-01 UC-SYS-01 | img_033 | UC-REL-01 |
| PL-02 UC-BIZ-02 | img_034 | UC-CTL-01 |
| PL-03 UC-BIZ-03 | img_035 | UC-CTX-01 |
| PL-04 UC-APR-01 | img_036 | UC-BIZ-01 |
| PL-05 UC-CTL-01 | img_037 | UC-ADM-01 |
| PL-06 AD-05 | img_038 | AD-03 |
| PL-07 AD-06 | img_039 | AD-10 |
| PL-08 AD-07 | img_040 | AD-02 |
| PL-09 AD-08 | img_041 | AD-06 |
| PL-10 AD-09 | img_042 | AD-08 |
| PL-11 AD-10 | img_043 | AD-09 |
| PL-12 SD-02 | img_044 | SD-21 |
| PL-13 SD-05 | img_045 | SD-10 |
| PL-14 SD-07 | img_046 | SD-01 |
| PL-15 SD-09 | img_047 | **SD-04** (ảnh thật của Hình 2.11) |
| PL-16 SD-10 | img_048 | **SD-06** (ảnh thật của Hình 2.12) |
| PL-17 SD-11 | img_049 | SD-13 |
| PL-18 SD-12 | img_050 | SD-05 |
| PL-19 SD-13 | img_051 | SD-22 |
| PL-20 SD-14 | img_052 | SD-15 |
| PL-21 SD-15 | img_053 | SD-14 |
| PL-22 SD-16 | img_054 | SD-18 |
| PL-23 SD-17 | img_055 | SD-02 |
| PL-24 SD-18 | img_056 | **SD-08** (ảnh thật của Hình 2.13) |
| PL-25 SD-19 | img_057 | SD-09 |
| PL-26 SD-20 | img_058 | SD-17 |
| PL-27 SD-21 | img_059 | SD-07 |
| PL-28 SD-22 | img_060 | SD-16 |
| PL-29 ST-04 (tệp đính kèm) | img_061 | ST-04 **Execution attempt** (khác đối tượng) |
| PL-30 ST-05 (cảnh báo SLA) | img_062 | **ST-07** Outbox (ảnh thật của Hình 2.24) |
| PL-31 ST-08 (phiên xác thực) | img_063 | **ST-02** Workflow instance (ảnh thật của Hình 2.20) |
| PL-32 ER-04 | img_064 | ER-07 Execution & acceptance |
| PL-33 ER-05 | img_065 | **ER-01** (ảnh thật của Hình 2.25) |
| PL-34 ER-06 | img_066 | **SEC-01** (ảnh thật của Hình 2.22) |
| PL-35 ER-07 | img_067 | ER-04 Identity & organization |
| PL-36 ER-08 | img_068 | ER-10 Audit, idempotency & privacy |
| PL-37 ER-09 | img_069 | **DP-01** Deployment topology (không có trong danh mục) |
| PL-38 ER-10 | img_070 | **DFD-01** (ảnh thật của Hình 2.18) |
| PL-39 ER-11 | img_071 | ER-05 Request type, config & revision |
| PL-40 ER-12 | img_072 | ER-08 Attachment |
| PL-41 ER-13 | img_073 | **AR-02** (ảnh thật của Hình 2.15) |

### 3.3 Số sơ đồ có hình thật

DOCX tuyên bố 68 sơ đồ (PL-1), nhưng chỉ có **50 ảnh sơ đồ duy nhất**. Các sơ đồ sau **không có ảnh ở bất kỳ đâu**:
- SD-03, SD-12, SD-19, SD-20;
- AR-01, AR-03, DFD-00;
- ST-01, ST-03, ST-05, ST-06, ST-08, cùng vòng đời tệp đính kèm;
- ER-02, ER-03 và một phần ER-06/09/11/12/13 theo đánh số của phần text.

Các tệp 03–08 viết lại **toàn bộ** sơ đồ, kể cả sơ đồ thiếu, bằng Mermaid. Nội dung lấy theo hệ thống thực tế đã đối soát.

> **Việc phải làm trên DOCX (bắt buộc trước khi bàn giao).** Thay 18 ảnh lặp. Sửa toàn bộ 50 chú thích theo bảng 3.2. Thay đoạn mô tả bị chép ở Hình 2.10–2.21. Bổ sung mô tả cho Hình 2.22–2.27.

## 4. Kết luận nhanh (chi tiết ở tệp 12)

| Hạng mục | Đánh giá |
|---|---|
| Lõi nghiệp vụ trong DB (FSM, SoD, hash-chain, outbox, RLS) | **Tốt hơn DOCX.** Code và ảnh sơ đồ (SD-04/05/06/07/22, ST-02/04/07) khớp nhau gần như 1:1. Phần **text** DOCX dùng tên trạng thái cũ và sai |
| Ngưỡng tiền/rủi ro A/B/C | DOCX tự mâu thuẫn ở 4 nơi: 2M/20M, 5M/50M, 500k, quy chế 30M. Code theo quy chế từng loại đơn, phải thống nhất lại |
| SLA | DOCX ghi 80/100/150%, quét 5 phút, email BOD. Ảnh AD-06/SD-08 và code dùng 50%/100%, chỉ thông báo trong ứng dụng → **cần chốt một phương án** |
| AI | DOCX mô tả AI chấm rủi ro bằng XGBoost để tự duyệt. Thực tế, quyết định tự duyệt dùng **trọng số rủi ro tĩnh theo loại đơn** cộng quy tắc. XGBoost chỉ là gợi ý hiển thị. Độ chính xác 93–100% là trên dữ liệu tổng hợp tự sinh nhãn bằng luật |
| Công nghệ | DOCX ghi Celery, React 18, Axios, Redis session, WebSocket, FCM/biometric, TrOCR/Tesseract, chữ ký số. Thực tế dùng outbox worker tự viết, React 19, fetch, signed-cookie + Redis idle key, không WebSocket, mobile tối giản, PaddleOCR + Gemini, không chữ ký số |
| CSDL | Đúng 30 bảng lõi như DOCX. Live có **49 bảng** (thêm 19 bảng từ migration 04–13 và admin upgrade). Tất cả bật RLS |
| DOCX phần 2.3.8, 2.4, Chương 3 | Chỉ có tiêu đề hoặc bảng giữ chỗ → tệp 09, 10, 11 viết mới hoàn toàn |
