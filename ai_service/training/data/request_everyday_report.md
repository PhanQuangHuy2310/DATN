# Bộ phân loại yêu cầu: câu ngắn đời thường (19/11/2026)

## Vì sao làm

Người dùng chụp màn hình 3 câu bị AI đánh giá sai ngay dưới ô tiêu đề:

| Câu | AI cũ nói | Đúng |
|---|---|---|
| "Xin đi muộn" | Mượn thiết bị / đồ dùng, 86% (gợi ý chuyển biểu mẫu) | Điều chỉnh chấm công |
| "Về sớm" | "Chưa có loại nào khớp" (gợi ý tạo loại mới) | Điều chỉnh chấm công |
| "Vắng mặt" | Yêu cầu hỗ trợ IT, 61% | Nghỉ phép |

Nguyên nhân:
- Dữ liệu huấn luyện gần như không có các cách nói đi muộn / về sớm / đến trễ / vắng mặt.
- Đặc trưng ký tự của mô hình **bỏ dấu**, nên "muộn" (đi muộn), "mượn" (mượn đồ) và "muốn" cùng thành "muon". Không có dữ liệu để phân biệt thì mô hình chọn nghĩa "mượn".
- "Vắng mặt" bỏ dấu thành "vang mat", có n-gram "mat" giống "mật khẩu" (hỗ trợ IT).

## Cách đo (viết và băm SHA-256 trước khi sửa)

| Bộ | Số câu | Vai trò |
|---|---|---|
| `request_eval_everyday.json` (bộ 1, commit 4d6a0a3) | 233 câu trong danh mục + 10 câu ngoài danh mục | Dữ liệu huấn luyện được sửa **theo lỗi của bộ này**, nên số đo sau khi sửa là số đo sau-sự-kiện |
| `request_eval_everyday2.json` (bộ 2, commit 3cf5b6e) | 93 + 6 | Viết khác bộ 1, không câu nào trùng nguyên văn với dữ liệu huấn luyện. Trước khi chọn mô hình cuối chỉ xem số tổng, không xem từng câu sai |

Chương trình chấm: `training/eval_request_everyday.py`. Nó đi đúng đường của dịch vụ (`routers.classify.predict`: mô hình và bộ nhận biết nhu cầu mới). Các chỉ số:
- **đúng top-1**;
- **sai mà tự tin**: sai nhưng đủ chắc, nên giao diện sẽ gợi ý chuyển sang biểu mẫu sai;
- **báo nhầm nhu cầu mới**: câu có trong danh mục nhưng AI bảo "chưa có loại nào khớp";
- **câu ngoài danh mục được nhận ra**.

## Sửa gì

- `request_corpus.json` bổ sung khái niệm còn thiếu:
  - chấm công: đi muộn / về sớm / đến trễ / quẹt thẻ, với lý do và số phút;
  - nghỉ phép: vắng mặt;
  - tạm ứng đi công tác, deploy bản cập nhật, hủy quyền truy cập;
  - tuyên dương, booking KOL, gửi dữ liệu cho bên thứ ba, nhờ cập nhật dữ liệu, chi trả hợp đồng.

  Không chép câu của bộ 2. Có 3 câu của bộ 1 trùng nguyên văn với mẫu mới là chính 3 câu người dùng báo ("xin đi muộn", "về sớm", "vắng mặt"); 11 câu khác của bộ 1 đã trùng với mẫu có sẵn từ trước.
- `train.py`: **C cố định = 5** (xem bên dưới); thêm tùy chọn `--nlp-c` và `--nlp-accent-chars` (mặc định tắt).

## Kết quả (mô hình cũ → mô hình mới C=5)

| Bộ | Cũ | Mới |
|---|---:|---:|
| Viết tay — test (127) | 89,0% | 89,0% |
| Câu rất ngắn — test (184) | 94,6% | **95,7%** |
| Công khai — test, trong phạm vi (489) | 92,0% | **92,8%** |
| Phiếu IT thật — test (269) | 85,5% | **87,0%** |
| Công khai: sai mà tự tin | 20 | **19** |
| Câu ngoài phạm vi MASSIVE (300), nhận ra theo đường dịch vụ (mới / không hiểu / chưa chắc) | 86,3% | **87,0%** |
| Câu ngoài phạm vi MASSIVE, chỉ tính cờ độ tin cậy < 0,35 | 75,3% | 74,3% |
| **Bộ 2 (đời thường, kín):** đúng top-1 | 84,9% (79/93) | **88,2% (82/93)** |
| Bộ 2: sai mà tự tin / báo nhầm nhu cầu mới / ngoài danh mục nhận ra | 7 / 3 / 5 trên 6 | 6 / 3 / 5 trên 6 |
| Bộ 1 (sau-sự-kiện): đúng top-1 | 93,1% (217/233) | 99,1% (231/233) |
| Bộ 1: sai mà tự tin / báo nhầm nhu cầu mới | 7 / 6 | 1 / 1 |

3 câu người dùng báo đều đúng sau khi sửa. Thời gian phân loại khoảng 22–25 ms/câu (không đổi), mô hình 17,8 MB.

**Đọc trung thực:**
- Lỗi cụ thể người dùng báo đã hết.
- Khả năng tổng quát hóa trên câu đời thường mới (bộ 2) chỉ tăng vừa phải, +3,3 điểm (3 câu).
- Bộ 2 vẫn còn 11 câu sai. Ví dụ "work from home thứ năm" → hỗ trợ IT; "thẻ nhân viên bị khóa không vào được cổng" → cấp quyền truy cập; "giảm 30% cho khách mua số lượng lớn" → đề nghị mua sắm.
- Câu ngoài danh mục "xin chỗ để xe máy trong hầm" bị gán "Mượn xe công vụ" với 87%.

## Các thử nghiệm không được chọn

1. **Tự chọn C như cũ (lưới 2/5/10/20, chọn theo 2 bộ dev).** Với dữ liệu mới, bộ chọn lấy C=20:
   - lợi: viết tay — test 90,6%, bộ 2 88,2%;
   - hại: mô hình tự tin quá mức. Câu ngoài phạm vi được nhận ra chỉ còn 74,3% (cũ 86,3%); câu công khai sai mà tự tin tăng lên 28; cờ độ tin cậy thấp trên MASSIVE còn 55,7%.

   Vì vậy C được cố định = 5. **Quyết định này đưa ra sau khi đã xem kết quả các bộ test**, nên là quyết định sau-sự-kiện. Tiêu chí chọn C bằng dev hiện không đo khả năng nhận ra câu ngoài phạm vi; cần một bộ dev ngoài phạm vi riêng mới chọn tự động đúng được.
2. **Thêm n-gram ký tự giữ dấu** (`--nlp-accent-chars on`), để tách "muộn / mượn / muốn" ngay cả khi thiếu dữ liệu.
   - Lần đầu (n-gram 2–4, 100 nghìn đặc trưng) bị **hết RAM** trên máy phát triển. Lần sau dùng 2–3 và 30 nghìn đặc trưng.
   - Bộ nhận biết nhu cầu mới phải hạ ngưỡng hệ số từ 0,5 xuống 0,35, hiệu chỉnh trên 2 bộ dev, để không báo nhầm nhiều hơn.
   - Kết quả: viết tay — test 90,6%, câu ngắn 96,7%, bộ 2 88,2%; nhưng câu ngoài phạm vi được nhận ra còn 85,0%, câu công khai sai mà tự tin 24.
   - Không hơn rõ bản C=5 thường, nên không dùng. Thử nghiệm này làm **sau khi đã xem lỗi của bộ 2**, nên số đo bộ 2 của nó là bán-kín.

Mô hình cuối khác bản C=5 đã chấm ở đúng một mẫu câu: "thu hồi quyền của thực tập sinh hết hạn" (9 từ) được rút thành 7 từ, vì test dữ liệu giới hạn câu rất ngắn ≤ 8 từ. Sau khi huấn luyện lại, mọi số đo giữ nguyên, riêng bộ 2 đúng thêm 1 câu ("em muốn nghỉ hẳn từ tháng sau"). Số trong bảng trên là của mô hình cuối.

## Còn yếu

- Từ không dấu nhiều nghĩa ("muon" = muộn / mượn / muốn) vẫn dựa vào ngữ cảnh trong dữ liệu. Câu rất ngắn không dấu và lạ có thể còn sai.
- Một số khái niệm sát nhau vẫn lẫn: thẻ ra vào và tài khoản; tạm ứng hội nghị và ngân sách sự kiện; chiết khấu và mua sắm.
- Bộ nhớ loại mới (`type_memory`) và nút "Tạo loại yêu cầu mới" vẫn là đường thoát khi AI chưa chắc.
