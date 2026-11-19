# Báo cáo: mô hình rủi ro có đặc trưng ngữ cảnh (18/11/2026)

Theo góp ý của thầy (16/11) và `docs/HUONG_DAN_TRAIN_AI.md` mục 4.2: "xin nghỉ chiều nay bình thường là mức 2, nhưng đang giữ
hồ sơ sắp hết hạn thì không còn là 2". Pipeline `catalog-v2-public-2-context`.

## Thay đổi

- Thêm 5 đặc trưng ngữ cảnh, tính từ CSDL ở `api_core/workflow/bad_case_signals.py` (cùng nghĩa ở `train.py` và `routers/risk.py`):
  `pending_work_due_24h`, `work_due_in_absence`, `handover_uncovered`, `team_absence_ratio`, `same_type_count_30d`.
- Luật gán nhãn mô phỏng thêm (chỉ nhóm vắng mặt ABSENCE): giữ việc đến hạn ≤24h mà bàn giao không làm thay được → tối thiểu 4 (+2);
  việc đến hạn trong thời gian vắng mà bàn giao không làm thay được +1; đồng nghiệp vắng trùng ngày ≥40% +1; lần thứ ≥4 cùng loại
  trong 30 ngày +1. Dữ liệu ngữ cảnh sinh cho MỌI loại để mô hình học được nó chỉ có tác dụng với nhóm vắng mặt.
- Mỗi lần chấm trả thêm `context_reasons` (vd. "+2, tối thiểu 4: đang giữ 3 việc hết hạn trong 24 giờ...").

Mô hình vẫn là **mô phỏng đánh giá của chuyên gia, học từ bộ luật của nhóm**; accuracy trên dữ liệu mô phỏng chỉ cho thấy mô hình bắt
chước luật tốt.

## Kết quả

Accuracy trên tập mô phỏng giữ lại (15%): Master 0,955 (trước 0,966, **giảm** do luật phức tạp hơn), Finance 0,959, HR 0,960, IT 0,973.
Bộ phân loại văn bản không đổi (viết tay test 0,890, câu ngắn test 0,946).

24 kịch bản ngữ cảnh viết + băm SHA-256 TRƯỚC khi huấn luyện lại (`risk_context_scenarios.json`, commit `e6a91d3`):

| Mô hình | Đúng | Lệch ≤1 bậc | Kịch bản ngữ cảnh làm đổi mức rủi ro |
|---|---|---|---|
| Trước (không có ngữ cảnh) | 10/24 | 15/24 | 0/14 |
| Sau | 18/24 | 23/24 | 8/14 |

Sai còn lại (không chỉnh rồi chấm lại trên cùng bộ kịch bản): RC04, RC05 (mức +1 nhỏ cho nghỉ phép), RC10 (thiếu 1 bậc), RC17 (WFH),
RC19, RC20 (công tác: mô hình gần như bỏ qua ngữ cảnh). Hướng cải thiện: tăng tỉ lệ mẫu ngữ cảnh cho nhóm vắng mặt rồi đánh giá trên
một bộ kịch bản MỚI băm trước.

Quyết định chặn tự duyệt và nâng luồng không dựa vào mô hình này: chúng do bộ phát hiện tình huống xấu (luật, tất định,
`ai_service/bad_cases.py`) đảm nhiệm; điểm rủi ro ML là thông tin tham khảo cho người duyệt.

## Lần 2 (19/11/2026): ngữ cảnh dày hơn cho nhóm vắng mặt

Làm đúng hướng ghi ở trên: **viết và băm bộ kịch bản MỚI trước** (`risk_context_scenarios2.json`, 30 ca, sha256 `02ab4324…`,
commit `b5a0817`), rồi mới đổi dữ liệu huấn luyện. Bộ 2 khác bộ 1:
- `risk_weight` đúng theo catalog (bộ 1 dùng LEAVE = 2 theo ví dụ của thầy, nằm ngoài phân phối train);
- nhiều ca ranh giới: vắng 40% so với 39%, lần thứ 4 so với lần thứ 3, việc gấp đã có người làm thay, dồn mọi cờ (kẹp ở 5);
- 6 ca ngữ cảnh trên loại **không** thuộc nhóm vắng mặt (OT, thanh toán, đào tạo, đặt phòng, thăng chức, lương): mức rủi ro phải giữ nguyên.

Thay đổi dữ liệu (`train.py`, `RISK_DATA_VERSION = "context-2"`), chỉ áp cho nhóm vắng mặt, các nhóm khác giữ phân phối cũ:
- gấp đôi số dòng;
- ngữ cảnh xuất hiện dày hơn (việc gấp 50% thay vì 25%);
- lấy mẫu sát ngưỡng: vắng 30–50%, lần thứ 2–6.

| Mô hình | Bộ 2 (mới) đúng | Bộ 2 lệch ≤1 | Bộ 2 ca ngữ cảnh đổi mức | Bộ 1 (đã xem) đúng |
|---|---|---|---|---|
| Lần 1 (18/11) | 26/30 | 29/30 | 13/17 | 18/24 |
| **Lần 2 (19/11)** | **29/30** | **30/30** | **16/17** | 21/24 |

- Bộ 2 sửa được: công tác khi giữ việc gấp (RD19: 3 → 5), công tác khi nửa nhóm vắng (RD21), WFH khi vừa có việc đến hạn vừa vắng đông (RD14).
- Sai còn lại: **RD06**, vắng **đúng 40%**, kỳ vọng 2 nhưng ra 1. Mô hình cây cắt ngưỡng gần 0,40 nên ca đúng ranh giới dễ lệch; không chỉnh rồi chấm lại.
- 6 ca loại ngoài nhóm vắng mặt: lần 1 và lần 2 đều đúng cả 6.
- Accuracy trên tập mô phỏng giữ lại: Master 0,957 (lần 1: 0,955), Finance 0,960, HR 0,970, IT 0,974.
- Bộ 1 đã được xem từ lần 1 nên con số 21/24 chỉ để tham khảo.
