# PHẦN MỞ ĐẦU — các mục cần thay thế

> Mục 1 (Tính cấp thiết) và mục 4 (Phương pháp nghiên cứu) của bản DOCX đạt yêu cầu và được giữ nguyên, trừ một câu nêu ở §1 dưới đây.
> Các mục 2.2, 3.1, 3.2, 5 và 6 chứa số liệu hoặc công nghệ không khớp với sản phẩm, nên được viết lại như sau.

## 1. Sửa một câu ở mục "Tính cấp thiết"

**Câu gốc:** "… kiến trúc hệ thống vi dịch vụ (Microservices) …"

**Thay bằng:** "… kiến trúc mô-đun hoá kết hợp dịch vụ trí tuệ nhân tạo độc lập …"

Lý do: lõi nghiệp vụ của EAS là một khối ứng dụng mô-đun (modular monolith). Chỉ phân hệ AI được tách thành dịch vụ riêng.

## 2.2. Mục tiêu cụ thể

**Về mô hình hoá nghiệp vụ và quản trị quy trình.**
- Chuẩn hoá vòng đời yêu cầu nội bộ theo ba mẫu:
  - **A — chỉ phê duyệt**;
  - **B — phê duyệt rồi thực hiện**;
  - **C — phê duyệt, thực hiện rồi nghiệm thu độc lập**.
- Xây dựng động cơ luật nghiệp vụ (BRE). Policy Admin cấu hình số cấp duyệt (1–5 cấp) theo số tiền, số ngày hoặc ứng dụng liên quan, không phải sửa mã nguồn.
- Mỗi lần ban hành tạo ra một phiên bản quy chế bất biến.

**Về ứng dụng trí tuệ nhân tạo.** Xây dựng dịch vụ AI độc lập (FastAPI) gồm năm năng lực:
1. Gợi ý loại yêu cầu, phòng ban và mẫu vòng đời từ văn bản tiếng Việt (TF-IDF + hồi quy logistic).
2. Chấm điểm rủi ro tham khảo bằng bốn mô hình XGBoost: tổng quát, Tài chính, Nhân sự, CNTT.
3. Tự động phê duyệt có kiểm soát các yêu cầu rủi ro thấp. Quyết định dựa trên trọng số rủi ro của loại đơn và bộ luật quy định công ty, có quyền thu hồi trong 24 giờ.
4. Tóm tắt hồ sơ bằng mô hình ngôn ngữ lớn Gemini 1.5 Flash. Khi không có khoá API, hệ thống dùng tóm tắt trích xuất cục bộ.
5. Biên dịch văn bản quy định công ty thành bộ luật cho động cơ tự duyệt.

Ngoài ra, chức năng nhận dạng hoá đơn (PaddleOCR, Gemini Vision dự phòng) đã có ở dịch vụ AI và được xếp vào hướng phát triển tích hợp.

**Về kiến trúc kỹ thuật.** Hệ thống gồm:
- lõi nghiệp vụ `api_core` (Django 5.2, SQL tham số hoá trên PostgreSQL);
- dịch vụ AI `ai_service` (FastAPI);
- cổng Nginx (giới hạn tần suất nhiều tầng, mã tương quan Correlation ID, header bảo mật);
- tiến trình nền xử lý SLA, hàng đợi sự kiện (transactional outbox) và học quy định;
- cơ sở dữ liệu Supabase PostgreSQL gồm schema nghiệp vụ `eas` và 8 schema hệ thống mô phỏng;
- giao diện web (React 19) cho nhân viên và quản trị, cùng ứng dụng di động Flutter để theo dõi.

**Về kiểm soát tuân thủ và kiểm toán.**
- Cưỡng chế máy trạng thái và nguyên tắc tách nhiệm (SoD) ngay ở tầng cơ sở dữ liệu bằng trigger.
- Sổ cái kiểm toán dạng chuỗi băm (RFC 8785 Canonical JSON + SHA-256). Mọi sửa đổi lịch sử đều bị phát hiện khi kiểm chứng.

## 3.1. Đối tượng nghiên cứu

- **Nghiệp vụ:** vòng đời yêu cầu nội bộ; quy tắc phê duyệt đa cấp; nguyên tắc tách nhiệm và bốn mắt (COSO); nhật ký kiểm toán chống chối bỏ.
- **Công nghệ:**
  - máy trạng thái hữu hạn cưỡng chế ở CSDL;
  - mẫu transactional outbox;
  - cổng API Nginx;
  - học máy phân loại văn bản (TF-IDF, hồi quy logistic) và dự báo rủi ro (XGBoost);
  - chuẩn hoá JSON theo RFC 8785 và chuỗi băm SHA-256.

## 3.2. Phạm vi nghiên cứu

- **Phạm vi tổ chức:** doanh nghiệp vừa và nhỏ với 8 phòng ban: Ban Giám đốc, Nhân sự, Tài chính – Kế toán, Kỹ thuật – CNTT, Kinh doanh, Marketing, Vận hành – Mua sắm, Pháp chế.
- **Phạm vi chức năng:**
  - danh mục **66 loại yêu cầu**, trong đó **58 loại đang hoạt động**: 9 loại mẫu A, 27 loại mẫu B, 22 loại mẫu C;
  - phân thành **12 nhóm lớn theo mục đích người gửi** (`eas.request_group`) với **61 mục chọn trên menu** (`eas.request_menu_item`, gồm 56 loại trực tiếp + 5 mục đặt sẵn `preset` cho Đi muộn, Về sớm, Quên chấm công, Nghỉ phép có lương `CO_LUONG`, Nghỉ không lương `KHONG_LUONG`; xem `docs/PHAN_LOAI_YEU_CAU.md`): Vắng mặt (`ABSENCE`); Chấm công & giờ làm (`WORKTIME`); Mượn & đặt chỗ (`BORROW`); Cấp phát & quyền truy cập (`PROVISION`); Tạm ứng & thanh toán (`PAYMENT`); Mua sắm & ngân sách (`PROCUREMENT`); Nhân sự & chế độ (`PEOPLE`); Hỗ trợ & sự cố (`SUPPORT`); Công việc & dự án (`WORK`); Văn bản & pháp chế (`LEGAL`); Kinh doanh & marketing (`SALES`); Kho & tài sản cố định (`ASSET`).
- **Phạm vi AI:** 7 nhóm API của dịch vụ AI:
  - phân loại;
  - rủi ro;
  - tự động phê duyệt;
  - tóm tắt;
  - nhận dạng hoá đơn;
  - quy định;
  - ngữ cảnh dữ liệu nghiệp vụ.
- **Phạm vi dữ liệu thực nghiệm** (đo ngày 04/11–05/11/2026 sau Schema v2 Migrations 14–17):
  - schema `eas` có **52 bảng hoạt động** (**0 view**) và hơn 1.600 bản ghi (138 tài khoản, 12 nhóm yêu cầu, 61 mục menu, 84 phiên bản quy chế, chuỗi băm kiểm toán nghiệp vụ & quản trị); kho lưu trữ chỉ-đọc `eas_archive` giữ nguyên toàn bộ bảng/cột di sản bị gộp;
  - 8 schema hệ thống ngoài mô phỏng (`mock_*`) được cô lập phía sau dịch vụ **Mock Systems API** (`mock_systems :8100`, role CSDL `eas_mock`) và căn chỉnh tổ chức theo EAS (`005_align_with_eas.sql`);
  - dữ liệu huấn luyện AI là dữ liệu tổng hợp (50.000 mẫu văn bản; 1.750.000 mẫu rủi ro).
- **Ngoài phạm vi:** chữ ký số theo Luật Giao dịch điện tử; phê duyệt song song; thông báo đẩy và đăng nhập sinh trắc trên di động; đồng bộ LDAP/AD. Các nội dung này thuộc hướng phát triển.

## 5. Ý nghĩa khoa học và thực tiễn

**Ý nghĩa khoa học.** Đề tài trình bày một thiết kế cụ thể, kiểm chứng được, cho bài toán phê duyệt đa cấp có kiểm soát nội bộ:
- toàn vẹn nghiệp vụ được đặt ở tầng CSDL (máy trạng thái, khoá ngoại kép `(id, request_id)`, bảng chỉ-ghi-thêm, khoá lạc quan);
- tách bạch ba trục cấu hình: hình dạng quy trình, ma trận thẩm quyền, mức rủi ro;
- tự động hoá bằng AI theo nguyên tắc "an toàn theo mặc định": AI chỉ được tự duyệt trong vùng rủi ro thấp đã được quy định cho phép, mọi quyết định đi qua cùng cơ chế kiểm soát như con người và có thể thu hồi.

**Ý nghĩa thực tiễn.** EAS thay quy trình giấy tờ và email bằng một luồng số hoá có:
- định tuyến tự động;
- nhắc hạn và cảnh báo quá hạn;
- ủy quyền khi vắng mặt;
- nhật ký không thể sửa.

Hiệu quả rút ngắn thời gian xử lý cần được đo khi triển khai thực tế. Báo cáo không công bố con số ước đoán (bản cũ ghi "60–70%" nhưng không có nguồn đo).

## 6. Bố cục của đồ án

- **Chương 1 — Tổng quan bài toán và cơ sở công nghệ:**
  - vòng đời yêu cầu nội bộ;
  - cơ sở lý thuyết về workflow, BRE, kiểm soát nội bộ và kiểm toán;
  - vai trò của AI;
  - các công nghệ được chọn.
- **Chương 2 — Phân tích và thiết kế hệ thống:**
  - phân tích yêu cầu;
  - mô hình hoá nghiệp vụ bằng sơ đồ ca sử dụng, hoạt động và tuần tự;
  - thiết kế kiến trúc, máy trạng thái, luật nghiệp vụ, phân quyền, kiểm toán, SLA;
  - thiết kế cơ sở dữ liệu và giao diện.
- **Chương 3 — Xây dựng, triển khai và đánh giá:**
  - môi trường phát triển;
  - hiện thực từng phân hệ và tích hợp AI;
  - kiểm thử tự động: 290 ca kiểm thử backend, 153 ca kiểm thử tích hợp, 64 ca kiểm thử giao diện;
  - đánh giá so với mục tiêu và hướng phát triển.
