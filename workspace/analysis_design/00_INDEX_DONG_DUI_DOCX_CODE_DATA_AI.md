# BẢNG ĐIỀU HÀNH & MỤC LỤC TỔNG THỂ PHÂN TÍCH THIẾT KẾ HỆ THỐNG EAS
## ĐỐI SOÁT TOÀN DIỆN: ĐỒ ÁN TỐT NGHIỆP (DOCX) ⟷ MÃ NGUỒN ⟷ CƠ SỞ DỮ LIỆU ⟷ MÔ HÌNH AI

---

## 1. THÀNH PHẦN HỘI ĐỒNG CHUYÊN MÔN IT (15 NĂM KINH NGHIỆM)

Bộ hồ sơ Phân tích & Thiết kế này được thiết lập và thẩm định bởi Hội đồng Chuyên gia IT liên ngành (Senior IT Department Board) với hơn 15 năm kinh nghiệm thực chiến trong các dự án Chuyển đổi số, Hệ thống Phê duyệt Nội bộ Doanh nghiệp (Enterprise Approval System - EAS), Ngân hàng & Fintech:

| STT | Vai Trò Chuyên Môn | Trách Nhiệm Thẩm Định & Góc Nhìn Chuyên Gia | Trọng Tâm Đóng Góp |
|:---:|:---|:---|:---|
| **1** | **Project Manager (PM)** | Giám sát phạm vi (Scope), tiến độ bàn giao, kiểm soát rủi ro kỹ thuật, phân bổ nguồn lực và chi phí triển khai hệ thống. | Bảo toàn tiến độ, không để phát sinh chi phí làm lại do lệch chuẩn. |
| **2** | **Product Owner (PO)** | Định hình tầm nhìn sản phẩm, giá trị nghiệp vụ thực tiễn, ưu tiên hóa Product Backlog (P0, P1, P2) và chuẩn nghiệm thu (Acceptance Criteria). | Đảm bảo hệ thống giải quyết triệt để nỗi đau vận hành của doanh nghiệp. |
| **3** | **Business Analyst (BA)** | Mô hình hóa toàn diện quy trình nghiệp vụ (BPMN), luật nghiệp vụ (Business Rules), ma trận thẩm quyền, phân tách nhiệm vụ (SoD) và đặc tả ca sử dụng (Use Cases). | Chuẩn hóa 18 loại yêu cầu, 3 mẫu vòng đời (A, B, C) và 25 luật định tuyến. |
| **4** | **Senior Developer (Backend & Frontend)** | Thiết kế kiến trúc Microservices/Monolith tinh gọn, bảo đảm tính toàn vẹn dữ liệu ACID, cơ chế Idempotency, Concurrency Control, Circuit Breaker và tối ưu API. | Triển khai Django REST, React/Vite, Supabase RLS, Redis Outbox & Zero-Trust. |
| **5** | **UI/UX Designer** | Thiết kế Design System đồng nhất giữa Cổng Nhân viên (Web Client :8080) và Cổng Quản trị (Web Admin :8081), luồng thao tác trực quan, Accessibility (WCAG). | Loại bỏ thao tác thừa, cảnh báo trực quan thời gian thực, responsive đa nền tảng. |
| **6** | **AI / MLOps Engineer** | Xây dựng pipeline phân loại văn bản (NLP), chấm điểm rủi ro (Gradient Boosting), bóc tách hóa đơn VAT (PaddleOCR), tóm tắt LLM và cơ chế học quy định tự động. | Ngăn chặn Data Leakage, kiểm chuẩn Calibration, gắn nhãn rủi ro và lease retrain. |
| **7** | **Quality Assurance Engineer (QA)** | Thiết lập khung kiểm soát chất lượng, định nghĩa Definition of Done (DoD), kiểm thử an toàn bảo mật (OWASP Top 10, IDOR, Injection) và khả năng kiểm toán. | Đảm bảo 100% test pass, kiểm tra tính toàn vẹn chuỗi băm SHA-256 Hash-chain. |
| **8** | **Test Engineer / Tester** | Thiết kế Test Scenarios, Test Cases biên (Boundary, Race condition, Failover), kiểm thử tự động hóa E2E bằng Playwright và kiểm thử tải hiệu năng. | Truy vết lỗi ngoại lệ, kiểm tra nộp đơn đồng thời, mất mạng và khôi phục sự cố. |

---

## 2. NGUYÊN TẮC VÀ PHƯƠNG PHÁP ĐỐI SOÁT

Hội đồng IT áp dụng phương pháp đối soát đa chiều (Triangulation Audit Method) giữa 3 nguồn dữ liệu độc lập:
1. **Tài liệu Báo cáo Đồ án tốt nghiệp:** File `workspace/Report_DATN_CNTT_Nhom07_v1.0.docx` (Bao gồm Phần mở đầu, Chương 1, Chương 2, Chương 3 và Phụ lục A - E).
2. **Hiện thực Mã nguồn & Cơ sở dữ liệu:** Toàn bộ repository (`api_core`, `web_client`, `web_admin`, `ai_service`, `database/migrations`, `tests`, `scripts`).
3. **Mô hình Trí tuệ nhân tạo & Dữ liệu:** Dữ liệu huấn luyện (`ai_service/data/training/`), mock data 8 hệ sinh thái (`mock_hr`, `mock_finance`,...), artifacts mô hình (`*.pkl`) và pipeline suy luận.

### Tiêu Chí Phân Loại Sự Sai Lệch (Discrepancy Severity Matrix)
- **LOẠI 1 - HỢP LÝ HÓA CÔNG NGHỆ (Architectural Evolution):** Codebase triển khai cao cấp hơn, an toàn hơn hoặc chặt chẽ hơn so với mô tả sơ khởi trong DOCX (Ví dụ: Thay vì để trình duyệt Web gọi trực tiếp Supabase qua Anon Key gây rò rỉ dữ liệu, Codebase trung gian hóa toàn bộ qua Backend Django với Authentication Cookie `HttpOnly` và Scoped RBAC).
- **LOẠI 2 - ĐỒNG BỘ CHUẨN XÁC (Perfect Alignment):** DOCX và Codebase thống nhất 100% về mặt logic (Ví dụ: 3 mẫu vòng đời A/B/C, 16 Use Cases P0, cấu trúc sổ cái kiểm toán Hash-Chain).
- **LOẠI 3 - CẦN LÀM RÕ & ĐIỀU CHỈNH ĐẶC TẢ (Specification Clarification):** Báo cáo DOCX nêu một số chỉ số lý thuyết (như AI Accuracy 100% trên dữ liệu Synthetic) cần được giải trình khoa học bằng kiểm định ngoại kiểm (Out-of-distribution) và hiệu chuẩn xác suất (Probability Calibration) trước khi bàn giao.

---

## 3. DANH MỤC TÀI LIỆU VÀ CÁC LOẠI SƠ ĐỒ THEO THỨ TỰ DOCX

Toàn bộ hệ thống 68 sơ đồ chuẩn hóa (theo Bảng 24 của DOCX) được tổ chức thành các chuyên đề độc lập, mỗi loại sơ đồ nằm trọn vẹn trong một file Markdown duy nhất, kèm đặc tả chi tiết và mã nguồn Mermaid trực quan:

```
workspace/analysis_design/
├── 00_INDEX_DONG_DUI_DOCX_CODE_DATA_AI.md           <-- [Tài liệu hiện tại] Mục lục & Bảng điều phối
├── 01_BAO_CAO_DOI_CHIEU_DAC_TA_HIEN_THUC.md         <-- Báo cáo đối soát tổng quan, phân tích khoảng cách (Gap Analysis)
├── 02_SO_DO_USE_CASE.md                             <-- TẤT CẢ 11 Sơ đồ Ca sử dụng (Chương 2 & Phụ lục A)
├── 03_SO_DO_ACTIVITY.md                             <-- TẤT CẢ 10 Sơ đồ Hoạt động nghiệp vụ (Chương 2 & Phụ lục B)
├── 04_SO_DO_SEQUENCE.md                             <-- TẤT CẢ 22 Sơ đồ Tuần tự & Xử lý ngoại lệ (Chương 2 & Phụ lục C)
├── 05_SO_DO_STATE_MACHINE.md                        <-- TẤT CẢ 8 Sơ đồ Máy trạng thái FSM (Chương 2 & Phụ lục D + AI Job)
├── 06_SO_DO_KIEN_TRUC_DU_LIEU_PHAN_TAN.md           <-- TẤT CẢ 9 Sơ đồ Kiến trúc, Container C4 & Luồng DL Outbox
├── 07_THIET_KE_CO_SO_DU_LIEU.md                     <-- TẤT CẢ 10 Sơ đồ ERD Miền + Từ điển dữ liệu chi tiết
├── 08_THIET_KE_HUAN_LUYEN_AI.md                     <-- Kiến trúc AI/ML, Pipeline huấn luyện, Bóc tách hóa đơn & Retrain Loop
├── 09_KIEM_THU_QA_RTM.md                            <-- Chiến lược QA, 7 cấp độ kiểm thử & Ma trận truy vết yêu cầu (RTM)
└── 10_DOI_CHIEU_LIEN_TUC_10_LAN.md                  <-- Biên bản đối chiếu chuyên sâu 10 vòng của Hội đồng IT
```

---

## 4. TỔNG HỢP MA TRẬN 68 SƠ ĐỒ THIẾT KẾ CỦA DỰ ÁN

| STT | Nhóm Sơ Đồ Thiết Kế | Số Lượng | Vị Trí Trong DOCX | Mã Định Danh Sơ Đồ Chi Tiết | File Markdown Chứa Sơ Đồ |
|:---:|:---|:---:|:---|:---|:---|
| **1** | **Use Case Diagrams** | **11** | Chương 2 + Phụ lục A | `UC-CTX-01`, `UC-REL-01`, `UC-BIZ-01`, `UC-ADM-01`, `UC-DET-01` .. `UC-DET-07` | `02_SO_DO_USE_CASE.md` |
| **2** | **Activity Diagrams** | **10** | Chương 2 + Phụ lục B | `AD-01` .. `AD-04`, `AD-07` .. `AD-12` | `03_SO_DO_ACTIVITY.md` |
| **3** | **Sequence Diagrams** | **22** | Chương 2 + Phụ lục C | `SD-01` .. `SD-22` (Bao phủ Submit, Race condition, AI, Outbox, PITR) | `04_SO_DO_SEQUENCE.md` |
| **4** | **State Machine Diagrams** | **8** | Chương 2 + Phụ lục D | `ST-01` .. `ST-08` (Request, Step, Attempt, Config, SLA, Attachment, Session, AI) | `05_SO_DO_STATE_MACHINE.md` |
| **5** | **Architecture & Data Flow** | **9** | Chương 2 + Phụ lục | `AR-01` .. `AR-05`, `SEC-01`, `DFD-00`, `DFD-01`, `CANARY-01` | `06_SO_DO_KIEN_TRUC_DU_LIEU_PHAN_TAN.md` |
| **6** | **Entity Relationship (ERD)** | **10** | Chương 2 + Phụ lục E | `ER-01` .. `ER-03` (Tổng quan) và `ER-04` .. `ER-13` (10 Miền dữ liệu chi tiết) | `07_THIET_KE_CO_SO_DU_LIEU.md` |
| **TỔNG** | **Toàn bộ hệ thống** | **68** | **Chương 2 & Phụ lục** | **Bao phủ 100% sơ đồ và cấu trúc dữ liệu theo đúng chuẩn IEEE/ISO 42010** | **Tất cả các file trên** |

---

## 5. CAM KẾT CHẤT LƯỢNG CỦA HỘI ĐỒNG IT

Hội đồng IT cam kết:
1. **Không bỏ sót bất kỳ Use Case, Activity, Sequence, State Machine hay ERD nào** được liệt kê trong file DOCX.
2. **Mọi sơ đồ Mermaid đều tuân thủ cú pháp tiêu chuẩn**, render trực quan, có chú thích các tác nhân, điều kiện tiên quyết và xử lý luồng ngoại lệ.
3. **Mọi kết luận đối soát đều có trích dẫn bằng chứng cụ thể** (đường dẫn file code, tên bảng database, tham số model AI).
4. **Bảo đảm tính nguyên vẹn và độc lập về bảo mật:** Hệ thống vận hành theo nguyên tắc phòng thủ đa tầng (Defense in Depth), bảo vệ quyền riêng tư dữ liệu cá nhân (GDPR & Nghị định 13/2023/NĐ-CP).
