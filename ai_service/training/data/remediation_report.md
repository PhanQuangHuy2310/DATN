# Báo cáo: mô hình xếp hạng người nhận việc thay (remediation-ranker-2)

Huấn luyện 2026-11-18T17:06:26+00:00, 4.6 giây, vòng tốt nhất 133.
Dữ liệu MÔ PHỎNG (không có lịch sử bàn giao thật); nhãn = bộ tiêu chí chuyên gia + nhiễu (xem docstring).
Tập test băm trước khi huấn luyện, lệch phân phối (phòng lớn hơn, nhiều việc hơn).

| Bộ chấm | dev top-1 | dev NDCG@3 | test top-1 | test NDCG@3 |
|---|---|---|---|---|
| xgboost_ranker | 0.874 | 0.965 | 0.898 | 0.956 |
| baseline_random | 0.203 | 0.492 | 0.117 | 0.256 |
| baseline_least_loaded | 0.424 | 0.698 | 0.328 | 0.590 |
| baseline_most_experienced | 0.422 | 0.691 | 0.269 | 0.487 |
| expert_rule_noise_free | 0.885 | 0.966 | 0.907 | 0.959 |

`expert_rule_noise_free` là trần tham chiếu: chính bộ tiêu chí gán nhãn khi không có nhiễu.
Mô hình chỉ học lại bộ tiêu chí đó; giá trị ở việc chạy trên tín hiệu thật và giải thích từng điểm.

Độ quan trọng (gain): same_department 46.26, same_team 37.73, due_in_window 31.35, is_superior 28.21, type_experience 28.03, open_items 22.66

## Bản 2 (19/11/2026): ràng buộc đơn điệu

Dò ca oái oăm trên lưới 8.112 cặp "đổi một đặc trưng, giữ nguyên phần còn lại" cho thấy bản 1 (không ràng buộc) có **7 cặp vi phạm
lẽ thường**, ví dụ thêm 1 việc đến hạn trong thời gian vắng mà điểm lại **tăng** (-3,826 → -3,714), hoặc thêm kinh nghiệm mà điểm giảm.
Sai lệch nhỏ nhưng khó giải thích với người dùng.

Bản 2 huấn luyện với `monotone_constraints` (`remediation_ranker.MONOTONE`): việc đến hạn, việc đang mở, là cấp trên chỉ được làm điểm
giảm; cùng phòng, cùng nhóm, kinh nghiệm chỉ được làm điểm tăng. Học lại từ phản hồi của quản lý cũng dùng cùng ràng buộc.

| | test top-1 | test NDCG@3 | dev top-1 | Cặp vi phạm đơn điệu |
|---|---|---|---|---|
| Bản 1 | 0,898 | 0,956 | 0,880 | 7 / 8.112 |
| **Bản 2** | **0,898** | **0,956** | 0,874 | **0 / 8.112** |

Kiểm thử: `tests/test_remediation_ranker.py` (đơn điệu trên lưới nhỏ, ranh giới của `suggest_action`, trường thiếu).
