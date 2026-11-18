# Báo cáo: mô hình xếp hạng người nhận việc thay (remediation-ranker-1)

Huấn luyện 2026-11-17T19:48:44+00:00, 2.8 giây, vòng tốt nhất 116.
Dữ liệu MÔ PHỎNG (không có lịch sử bàn giao thật); nhãn = bộ tiêu chí chuyên gia + nhiễu (xem docstring).
Tập test băm trước khi huấn luyện, lệch phân phối (phòng lớn hơn, nhiều việc hơn).

| Bộ chấm | dev top-1 | dev NDCG@3 | test top-1 | test NDCG@3 |
|---|---|---|---|---|
| xgboost_ranker | 0.880 | 0.964 | 0.898 | 0.956 |
| baseline_random | 0.203 | 0.492 | 0.117 | 0.256 |
| baseline_least_loaded | 0.424 | 0.698 | 0.328 | 0.590 |
| baseline_most_experienced | 0.422 | 0.691 | 0.269 | 0.487 |
| expert_rule_noise_free | 0.885 | 0.966 | 0.907 | 0.959 |

`expert_rule_noise_free` là trần tham chiếu: chính bộ tiêu chí gán nhãn khi không có nhiễu.
Mô hình chỉ học lại bộ tiêu chí đó; giá trị ở việc chạy trên tín hiệu thật và giải thích từng điểm.

Độ quan trọng (gain): same_department 72.70, same_team 64.43, due_in_window 30.86, type_experience 27.23, open_items 22.05, is_superior 14.90
