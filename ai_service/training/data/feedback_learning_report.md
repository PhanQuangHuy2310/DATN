# Báo cáo: vòng phản hồi "sai tối đa 1 lần" (18/11/2026)

Bộ 5 tập (`feedback_learning_episodes.json`, SHA-256 `4f1eeb4f…`, commit `b7da9b5`) viết TRƯỚC khi cài vòng phản hồi.
Chạy: `tests/live/test_ai_feedback_learning.py` trên Supabase local (migration 23 + 24). Kết quả máy đọc: `feedback_learning_results.json`.

## Cơ chế

| Phần | Cách học | Hiệu lực |
|---|---|---|
| 1. Ghi nhận | Mỗi lần người sửa quyết định của AI (thu hồi tự duyệt, đánh dấu "AI chuyển nhầm", chọn khác ứng viên đang đứng đầu, bỏ qua đề xuất) -> `eas.ai_feedback` kèm tín hiệu lúc đó | Ngay |
| 2. Bộ nhớ ca | Trước mỗi quyết định, so với ca đã bị sửa cùng người + cùng loại (chuyển nhầm: + cùng mã tình huống xấu; xếp hạng: cùng người xin nghỉ + cùng loại việc). Không bao giờ bỏ chuyển luồng khi có điều khoản quy định yêu cầu | Ngay, không huấn luyện lại |
| 3. Học dồn | Worker mỗi ngày (hoặc admin bấm): huấn luyện lại mô hình xếp hạng bằng lựa chọn thật của quản lý; thay mô hình CHỈ KHI top-1 trên tập test đã băm không giảm quá 0,01 và độ đúng trên lựa chọn thật không giảm; thống kê tỉ lệ chuyển luồng nhầm theo tình huống xấu và đề xuất chỉnh ngưỡng (không tự sửa) | Sau lần học dồn |
| 4. Câu chưa hiểu | Câu quy định có yêu cầu kiểm soát nhưng ngoài schema -> hàng chờ của admin kèm cách hiểu do Gemini đề xuất (đã kiểm tra bằng luật); admin duyệt -> AI học lại | Sau khi admin duyệt |

## Kết quả (một lượt chạy liền 5 tập)

| Tập | Lần sai (1) | Ca tương tự (2) | Ca đối chứng (3) |
|---|---|---|---|
| FB-01 thu hồi tự duyệt | AI tự duyệt WFH, quản lý thu hồi | Không tự duyệt lại, chuyển B (LEARNED_REVOKE) | Người khác vẫn được tự duyệt |
| FB-02 chuyển luồng nhầm | WFH bị chuyển B (BC_WFH_FREQUENT), quản lý đánh dấu nhầm | Giữ luồng A | Người khác cùng tình huống vẫn chuyển B |
| FB-03 chọn khác AI | Quản lý chọn ứng viên thứ 2 | Người đó đứng đầu lần sau (kể cả khi quản lý đổi ý so với lần trước) | Người xin nghỉ khác không bị ảnh hưởng |
| FB-04 câu chưa hiểu | Câu điều kiện % bị bỏ qua | Vào hàng chờ kèm gợi ý Gemini; duyệt xong có trong bộ luật | Câu ngưỡng tiền tự biên dịch, không vào hàng chờ |
| FB-05 học dồn có cổng | Lựa chọn thật được gom | ACCEPTED: top-1 tập test 0,897 -> 0,902, độ đúng trên lựa chọn thật 0,5 -> 0,5 | Không có phản hồi: NOT_ENOUGH_FEEDBACK |

**5/5 PASS · lặp lại lỗi: 0 · học tràn: 0.**

## Lỗi phát hiện trong quá trình chạy (đã sửa)

- Lượt chạy liền đầu tiên FB-03 lặp lại gợi ý cũ: hệ thống so lựa chọn của quản lý với thứ hạng GỐC của mô hình thay vì
  thứ hạng ĐÃ HIỂN THỊ (đã có bộ nhớ), nên khi quản lý đổi ý thì lựa chọn mới không được ghi. Đã sửa; lượt sau đạt.
- Học dồn mất khoảng 1-1,5 phút nên API admin chạy nền (trả 202), kết quả xem ở GET /admin/ai-engine/feedback.

## Hạn chế

- Bộ nhớ ca học theo người + loại, không tự khái quát sang người khác (chủ ý, để không học tràn). Khi nhiều người cùng bị
  sửa một kiểu, phần thống kê sẽ đề xuất chỉnh ngưỡng chung để admin quyết định.
- Một lựa chọn riêng lẻ của quản lý thường chưa đủ làm mô hình xếp hạng đổi thứ hạng sau học dồn; việc "không sai lại"
  do bộ nhớ ca đảm nhiệm, học dồn làm mô hình dần khớp với nhiều lựa chọn thật hơn.
- Tình huống hoàn toàn mới, không thuộc quy định nào và không giống ca nào, AI vẫn có thể sai lần đầu.
