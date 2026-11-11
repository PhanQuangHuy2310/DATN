# 00 — Hướng dẫn sử dụng bộ nội dung báo cáo hoàn chỉnh

| Thuộc tính | Giá trị |
|---|---|
| Đề tài | Hệ thống tự động hoá quy trình xử lý yêu cầu nội bộ đa cấp tuân thủ quy định doanh nghiệp (EAS — Enterprise Approval System) |
| Mục đích bộ tài liệu | Cung cấp **nội dung thay thế** cho các phần sai, thiếu hoặc chỉ có tiêu đề trong `Report_DATN_CNTT_Nhom07_v1.0.docx`. Mỗi tệp tương ứng một phần của báo cáo và dán được trực tiếp vào DOCX |
| Nguyên tắc | Mọi khẳng định đều có bằng chứng trong mã nguồn, lược đồ CSDL hoặc dữ liệu live (đọc ngày 04/11/2026). Chức năng chưa hiện thực chỉ xuất hiện ở mục "Hướng phát triển", không trình bày như đã có |
| Quyết định nghiệp vụ áp dụng | Theo khuyến nghị đã được chủ đầu tư chấp thuận ngày 04/11/2026 (xem §4) |
| Tài liệu đối soát (phụ lục) | `workspace/phan_tich_thiet_ke/00…12` — giải thích vì sao từng chỗ trong DOCX phải sửa |

## 1. Danh mục tệp và vị trí trong DOCX

| Tệp | Thay thế phần DOCX | Mức thay đổi |
|---|---|---|
| `01_PHAN_MO_DAU.md` | Phần mở đầu, mục 2.2, 3.1, 3.2, 5, 6 | Sửa các số liệu và công nghệ không đúng |
| `02_CHUONG_1_TONG_QUAN.md` | Chương 1 (1.1–1.4) | Viết lại 1.1.2, 1.2.2, 1.3, 1.4; giữ phần lý luận chung |
| `03_CHUONG_2_1_PHAN_TICH_YEU_CAU.md` | 2.1.1–2.1.4 | Viết lại toàn bộ |
| `04_CHUONG_2_2_QUY_TRINH_NGHIEP_VU.md` | 2.2.1–2.2.7 | Viết lại toàn bộ |
| `05_CHUONG_2_2_8_USE_CASE.md` | 2.2.8 + Phụ lục A | Viết lại; thêm đặc tả ca sử dụng |
| `06_CHUONG_2_2_9_ACTIVITY.md` | 2.2.9 + Phụ lục B | Viết lại; chú thích đúng |
| `07_CHUONG_2_2_10_SEQUENCE.md` | 2.2.10 + Phụ lục C | Viết lại; bổ sung 4 sơ đồ còn thiếu |
| `08_CHUONG_2_3_THIET_KE_HE_THONG.md` | 2.3.1–2.3.6 | Viết lại toàn bộ |
| `09_CHUONG_2_3_7_ERD.md` | 2.3.7 + Phụ lục E | Viết lại toàn bộ |
| `10_CHUONG_2_3_8_THIET_KE_BANG.md` | 2.3.8 (Bảng 2.10–2.16 đang là bảng giữ chỗ) | Viết mới |
| `11_CHUONG_2_4_GIAO_DIEN.md` | 2.4 (chỉ có tiêu đề) | Viết mới |
| `12_CHUONG_3_XAY_DUNG_TRIEN_KHAI.md` | 3.1, 3.2 (chỉ có tiêu đề) | Viết mới |
| `13_CHUONG_3_3_KIEM_THU_DANH_GIA.md` | 3.3 + Kết luận (chỉ có tiêu đề) | Viết mới, kèm kết quả chạy test thật |
| `14_PHU_LUC.md` | Phụ lục PL-1…PL-5 | Danh mục sơ đồ, ma trận truy vết, Model Card, tài liệu tham khảo |

## 2. Việc phải làm trên tệp DOCX (theo thứ tự)

1. **Xoá 18 hình lặp** (Hình 2.10–2.27 đang dùng chung hai ảnh `img_006`, `img_007`). Thay bằng sơ đồ trong các tệp 07, 08, 09.
2. **Gắn lại chú thích của 50 hình sơ đồ** theo tên sơ đồ in trên chính ảnh. Bảng đối chiếu: `phan_tich_thiet_ke/00_MUC_LUC_VA_PHUONG_PHAP.md` §3.2.
3. **Thay nội dung** từng mục theo bảng §1.
4. **Đánh lại số hình và bảng** theo danh mục §3; cập nhật Danh mục hình, Danh mục bảng và Mục lục tự động trong Word.
5. **Vẽ ảnh cho sơ đồ Mermaid**: dán khối Mermaid vào https://mermaid.live hoặc dùng `mmdc` (mermaid-cli) để xuất PNG 300 dpi; đặt chú thích "Nguồn: Nhóm tác giả".

## 3. Danh mục hình và bảng mới

### 3.1 Danh mục hình

| Số hình | Mã | Tên | Tệp | Ảnh có sẵn trong DOCX |
|---|---|---|---|---|
| 1.1 | — | Vòng đời 6 giai đoạn của yêu cầu nội bộ | 02 | Không (Mermaid) |
| 1.2 | — | Ba trục cấu hình độc lập: lifecycle – thẩm quyền – rủi ro | 02 | Không |
| 1.3 | — | Kiến trúc phân hệ AI | 02 | Không |
| 2.1 | UC-CTX-01 | Sơ đồ ngữ cảnh ca sử dụng | 05 | img_035 |
| 2.2 | UC-REL-01 | Quan hệ include/extend giữa các ca sử dụng | 05 | img_033 |
| 2.3 | UC-BIZ-01 | Ca sử dụng nghiệp vụ lõi theo tác nhân | 05 | img_036 |
| 2.4 | UC-ADM-01 | Quản trị và quản trị dữ liệu | 05 | img_037 |
| 2.5 | AD-01 | Vòng đời tổng thể xử lý một yêu cầu | 06 | img_011 |
| 2.6 | AD-02 | Gửi đơn và kiểm tra tự động | 06 | img_040 |
| 2.7 | AD-03 | Cấp trên xử lý phê duyệt | 06 | img_038 |
| 2.8 | AD-04 | Thực hiện và nghiệm thu | 06 | img_012 |
| 2.9 | SD-01 | Đăng nhập, phiên và đăng xuất | 07 | img_046 |
| 2.10 | SD-03 | Gửi / gửi lại hồ sơ nguyên tử | 07 | Không (Mermaid) |
| 2.11 | SD-04 | Duyệt, từ chối, yêu cầu bổ sung | 07 | img_047 |
| 2.12 | SD-06 | Nhận việc, nộp kết quả, nghiệm thu | 07 | img_048 |
| 2.13 | SD-08 | SLA và hàng đợi outbox | 07 | img_056 |
| 2.14 | AR-01 | Ngữ cảnh kiến trúc (C4 mức 1) | 08 | Không (Mermaid) |
| 2.15 | AR-02 | Container logic | 08 | img_073 |
| 2.16 | AR-03 | Thành phần của API Core | 08 | Không (Mermaid) |
| 2.17 | DFD-00 | Luồng dữ liệu mức ngữ cảnh | 08 | Không (Mermaid) |
| 2.18 | DFD-01 | Luồng dữ liệu mức 1 | 08 | img_070 (bổ sung tiến trình 7.0, 8.0) |
| 2.19 | ST-01 | Máy trạng thái hồ sơ yêu cầu | 08 | Không (Mermaid) |
| 2.20 | ST-02 | Máy trạng thái phiên quy trình | 08 | img_063 |
| 2.21 | ST-03 | Máy trạng thái bước phê duyệt | 08 | Không (Mermaid) |
| 2.22 | SEC-01 | Ranh giới tin cậy và bề mặt tấn công | 08 | img_066 (bổ sung Gemini) |
| 2.23 | ST-06 | Chặng theo dõi SLA | 08 | Không (Mermaid) |
| 2.24 | ST-07 | Sự kiện hàng đợi outbox | 08 | img_062 |
| 2.25 | ER-01 | ERD miền 1: Danh tính, cấu hình, hồ sơ | 09 | img_065 (cần sửa tên cột) |
| 2.26 | ER-02 | ERD miền 2: Quy trình, thực thi, tệp | 09 | Không (Mermaid) |
| 2.27 | ER-03 | ERD miền 3: SLA, sự kiện, kiểm toán | 09 | Không (Mermaid) |
| 2.28 | ER-04 | ERD miền 4: Quản trị, AI, vận hành | 09 | Không (Mermaid) |
| 2.29 | UI-01 | Sơ đồ điều hướng màn hình | 11 | Không (Mermaid) |
| 3.1 | DP-01 | Topology triển khai bằng Docker Compose (bản production đề xuất: img_069, đặt ở PL-40) | 12 | Không (Mermaid) |
| 3.2 | AI-01 | Luồng vận hành AI trong hệ thống | 12 | Không (Mermaid) |
| PL-01…PL-40 | | Các sơ đồ bổ trợ (UC, AD, SD, ST, ER chi tiết) | 14 §1 | Xem 14 §1 |

### 3.2 Danh mục bảng

| Số bảng | Tên | Tệp |
|---|---|---|
| 1.1 | Sáu giai đoạn vòng đời và trạng thái hệ thống tương ứng | 02 |
| 1.2 | Ba mẫu vòng đời A/B/C | 02 |
| 1.3 | Các thành phần AI trong hệ thống EAS | 02 |
| 1.4 | Tám hệ thống nghiệp vụ mô phỏng (schema mock) | 02 |
| 1.5 | Công nghệ sử dụng | 02 |
| 2.1 | Tác nhân của hệ thống | 03 |
| 2.2 | Danh mục ca sử dụng | 03 |
| 2.3 | Yêu cầu phi chức năng | 03 |
| 2.4 | Phân bổ 58 loại yêu cầu theo lifecycle | 04 |
| 2.5 | Bảng chuyển trạng thái hồ sơ | 08 |
| 2.6 | Bảng quyết định định tuyến (BRE) | 08 |
| 2.7 | Ma trận phân quyền | 08 |
| 2.8 | Cấu trúc bản ghi kiểm toán | 08 |
| 2.9 | Ma trận cảnh báo SLA | 08 |
| 2.10–2.16 | Thiết kế chi tiết các bảng theo 6 miền dữ liệu | 10 |
| 2.17 | Ánh xạ màn hình – vai trò | 11 |
| 3.1 | Công cụ và phiên bản | 12 |
| 3.2 | Kết quả kiểm thử tự động | 13 |
| 3.3 | Kết quả theo kịch bản kiểm thử | 13 |
| 3.4 | Đánh giá theo mục tiêu đề tài | 13 |

## 4. Quyết định nghiệp vụ áp dụng trong bộ tài liệu

| # | Nội dung | Quyết định |
|---|---|---|
| Q1 | Ngưỡng tiền | Theo cấu hình đang chạy: mua sắm 5.000.000 đ / 50.000.000 đ; thanh toán chi phí 20.000.000 đ; thiết bị 10.000.000 đ / 50.000.000 đ. Quy định công ty REG-002-3: từ 30.000.000 đ bắt buộc duyệt thủ công (không được tự duyệt) |
| Q2 | Nghỉ phép trên 2 ngày | 2 cấp: quản lý trực tiếp → giám đốc |
| Q3 | Mốc nhắc SLA | 50% thời hạn |
| Q4 | Leo thang mức 2 | ≥ 150% thời hạn, gửi quản trị vận hành (hướng phát triển; chưa hiện thực) |
| Q5 | Vai trò AUDITOR | Giao cho một tài khoản kiểm soát nội bộ riêng, khác tài khoản quản trị (cần gán trên dữ liệu live trước khi bảo vệ) |

## 5. Quy ước trình bày

- Thuật ngữ tiếng Anh giữ nguyên khi là tên trạng thái, tên bảng, tên cột hoặc tên API; lần đầu xuất hiện có giải thích tiếng Việt.
- Đường dẫn mã nguồn viết dạng `thư_mục/tệp.py:dòng` để giảng viên tra cứu được.
- Số liệu live ghi kèm ngày đo (04/11/2026).
- Chức năng chưa hiện thực được đánh dấu **(hướng phát triển)**.
