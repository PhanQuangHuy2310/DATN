# EAS — Rà soát UI/UX frontend (08/11/2026)

## Phạm vi

Chỉ thay đổi giao diện trong `web_client/` (dùng chung cho cổng nhân viên và cổng Admin trong `web_admin/`). Không sửa API, business rule, database, Django, AI Service, Docker, cấu hình, phân quyền hoặc cách xác thực. Hệ thống vẫn sử dụng dữ liệu và API thật như bản gốc.

## Các cập nhật đã thực hiện

1. **Mật độ hiển thị / Design System:** bổ sung lớp *Product UX refinement* cuối `src/eas-theme.css` để thống nhất nền, đường viền, khoảng cách, chiều cao input/select/textarea, tiêu đề, bảng dữ liệu, card và thanh điều hướng ở cả hai cổng. Sửa màu chữ của control trước đây dùng nhầm màu viền (`--client-ink`).
2. **Danh sách hồ sơ:** mặc định dùng dạng bảng để dễ theo dõi nhiều hồ sơ; vẫn có nút chuyển sang Kanban. Hiển thị tìm kiếm và loại yêu cầu thường trực; các bộ lọc bổ sung được thu gọn bằng nút có `aria-expanded`/`aria-controls`, hiển thị số bộ lọc đang áp dụng. Khi thu gọn không xóa hoặc đặt lại bộ lọc.
3. **Tạo/chỉnh sửa hồ sơ:** giảm padding trong nhóm thông tin, form 2 cột trên desktop / 1 cột trên mobile; nút lưu nháp và gửi phê duyệt bám cạnh dưới vùng làm việc khi cuộn. Nhóm *Hỗ trợ hoàn thiện hồ sơ* chứa AI gợi ý và xem trước tuyến duyệt có thể mở khi cần, nhưng các component và xử lý nghiệp vụ vẫn giữ nguyên.
4. **Chi tiết hồ sơ:** chuyển tab không còn tự kéo trang xuống đột ngột; thanh tab bám phía trên khi xem nội dung dài, nhóm thao tác bên phải bám theo khi đủ chiều rộng; trên màn hình hẹp nhóm thao tác hiển thị phía trước nội dung, không bị mất.
5. **Responsive:** điều chỉnh cho desktop rộng, laptop, tablet và mobile. Ở kích thước nhỏ, bảng hồ sơ hiển thị thành thẻ 2 cột nhỏ với nội dung quan trọng ở trên, không làm tràn viewport. Form/nhóm filter tự chuyển số cột; dialog giới hạn chiều cao viewport.
6. **Khả năng sử dụng:** bổ sung lối tắt bàn phím “Bỏ qua điều hướng”, duy trì focus ring, giữ các nút thật, giảm hoạt ảnh cuộn do chuyển trang và phân trang.
7. **Đăng nhập:** ô email/mật khẩu và nút đăng nhập dùng kích cỡ vừa phải, góc bo đơn giản, không đổi logic đăng nhập.

## Thay đổi mã nguồn

- `web_client/src/eas-theme.css`: lớp thiết kế thống nhất và responsive cuối file.
- `web_client/src/components/clientDesign.jsx`: bộ lọc gọn/mở rộng có trợ năng.
- `web_client/src/components/ClientRequests.jsx`: mặc định dạng bảng; số bộ lọc đang áp dụng.
- `web_client/src/components/RequestEditor.jsx`: giao diện biểu mẫu, vùng hỗ trợ AI có thể mở rộng.
- `web_client/src/components/RequestDetail.jsx`: vị trí tab và bố cục xử lý.
- `web_client/src/components/ux.jsx`: cuộn phân trang tức thời, không tạo hiệu ứng kéo dài.
- `web_client/src/App.jsx`: chuyển trang không cuộn mượt gây khó chịu; skip-link.

Không sửa file `web_admin/src/main.jsx`, vì cổng Admin nhập trực tiếp `eas-theme.css` từ `web_client/src`, tự nhận toàn bộ thay đổi chung.

## Kiểm tra đã thực hiện

- `node --test e2e/*.test.mjs`: **85/85 bài kiểm thử đạt**.
- `tinycss2`: không có lỗi cú pháp cấp stylesheet hoặc declaration trong `eas-theme.css`.
- Đối chiếu byte giữa file ZIP ban đầu và bản sửa: các tệp ngoài `web_client` không thay đổi.

**Giới hạn:** Chưa xác minh được build Vite hoàn chỉnh hoặc kiểm tra trực quan trong trình duyệt có đăng nhập và dữ liệu thật trong môi trường phân tích này vì không tải được các gói Node trong lúc kiểm tra. Nên chạy thêm các bước dưới đây trên máy phát triển để nghiệm thu.

## Kiểm tra nghiệm thu sau khi chép code

```bat
cd /d "D:\Đồ án\DATN\web_client"
npm ci
npm run build
npm test
```

Kiểm tra cả hai cổng theo các kích thước **1440×900**, **1280×800**, **768×1024**, **390×844**, bao gồm chế độ sáng/tối. Thử vai trò Requester, Approver, Executor, Acceptor và các trang Admin được phân quyền:

- Tìm kiếm, lọc, mở/thu gọn bộ lọc, đặt lại, phân trang, đổi giữa bảng/Kanban.
- Chọn loại yêu cầu, nhập form, lưu bản nháp, mở hỗ trợ AI, xem tuyến duyệt, gửi phê duyệt và xử lý lỗi.
- Xem chi tiết hồ sơ, đổi tab, thực hiện thao tác đúng quyền, tải tài liệu.
- Kiểm tra menu responsive, biểu mẫu/chữ/nút không tràn màn hình, thoại không vượt chiều cao, focus bàn phím.

Lưu ý: sửa CSS không làm cho API chậm hoặc lỗi 503 trở nên nhanh hơn; việc này phải được khắc phục riêng tại backend/Redis/Supabase.
