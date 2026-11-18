# Báo cáo: AI hiểu quy định có điều kiện ngữ cảnh (18/11/2026)

Lệnh: `.venv\Scripts\python ai_service\training\eval_regulation_compiler.py --final --llm-runs ai_service\training\data\regulation_rules_llm_runs.json`
Kết quả máy đọc: `regulation_compiler_results.json`.

## Bài toán

Quy định mới thường không chỉ có ngưỡng tiền/ngày mà còn có **điều kiện ngữ cảnh**, ví dụ Quy chế 05/2026:
"nghỉ phép khi đang giữ việc đến hạn trong 24 giờ chưa bàn giao", "điều chỉnh chấm công từ lần thứ 4 trong tháng",
"tạm ứng có dấu hiệu chia nhỏ hóa đơn". Trình biên dịch cũ (v1) chỉ đọc ngưỡng và tên loại nên biến Điều 1 thành
"chặn MỌI đơn nghỉ từ 1 ngày" và Điều 2 thành "chặn MỌI đơn chấm công" (chặn tràn).

## Dữ liệu đánh giá

| Tập | Số điều khoản | Vai trò |
|---|---|---|
| dev | 18 | dùng để phát triển v2 |
| test | 30 | viết + băm SHA-256 (`88c7e770…`) và commit (`565c96b`) **trước** khi viết v2; chấm một lần |
| demo | 5 | Quy chế 05/2026 của nhóm; đã đọc trước khi phát triển nên báo cáo riêng |

Mỗi điều khoản có đáp án là danh sách luật (phạm vi + điều kiện + hiệu lực). Một luật khớp khi khớp đủ các trường
`request_type, amount_gt, days_gt, due_within_hours, require_no_handover, repeat_count_gte, repeat_window, split_suspect, auto_approve`.
**Chặn tràn** = luật bắt buộc duyệt thủ công mà đáp án không có (thường do bỏ mất điều kiện, nên chặn cả loại).

## Kết quả trên tập test (30 điều khoản)

| Bộ máy | Khớp hoàn toàn | Precision | Recall | F1 | Chặn tràn | Bỏ sót kiểm soát | Đúng luồng B/C |
|---|---|---|---|---|---|---|---|
| v1 (cũ, mốc) | 13/30 | 0,464 | 0,481 | 0,473 | 13 | 14 | — |
| **v2 (luật + điều kiện ngữ cảnh)** | **29/30** | **1,000** | **0,963** | **0,981** | **0** | 1 | 1,00 |
| Gemini 3.5 Flash-Lite + kiểm tra bằng luật | 25/30 | 0,862 | 0,926 | 0,893 | 3 | 2 | 0,72 |
| Hybrid (v2, rỗng thì Gemini; chốt trước khi chấm) | 26/30 | 0,867 | 0,963 | 0,912 | 3 | 1 | 1,00 |

Gemini: 52/53 lần gọi thành công (1 lần trả mảng thay vì object, đã sửa bộ kiểm tra sau khi chấm); độ trễ trung vị 2,6 s, p95 5,5 s.

## Lỗi còn lại (không sửa rồi chấm lại trên cùng tập test)

- v2 sai T25 "…sau **khi** giải ngân phải nghiệm thu…": chữ "khi" của "sau khi" bị hiểu là mệnh đề điều kiện không hỗ trợ nên bỏ cả câu.
  Đã sửa sau khi chấm (bỏ qua "sau khi/trước khi"); bản sửa cần một tập giữ lại MỚI để đo, con số 29/30 ở trên là của bản trước khi sửa.
- Gemini chặn tràn ở T16 ("dưới 1 ngày được tự động duyệt" thành luật tự duyệt mọi đơn), T27 ("ngày đã quá 30 ngày" hiểu thành thời lượng
  đơn), T28 (điều kiện % bị bỏ, chặn cả loại chiết khấu) và bỏ sót T18 (mọi đề xuất trên 1 tỷ).

## Hạn chế

- Cùng một người viết dữ liệu đánh giá và trình biên dịch nên đây là đánh giá nội bộ, chưa phải đánh giá độc lập.
  Hội đồng có thể yêu cầu nhóm tự viết thêm điều khoản mới để chạy thử trực tiếp.
- Schema chỉ biểu diễn 3 loại điều kiện ngữ cảnh (đến hạn, lặp lại, chia nhỏ). Điều kiện khác (%, khu vực, hồi tố, cận trên) bị
  bỏ qua có chủ đích để không chặn tràn; quản trị viên vẫn thấy câu đó trong danh sách quy định để xử lý tay.
