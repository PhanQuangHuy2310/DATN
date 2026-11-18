# Học bad case mới từ lý do thu hồi tự duyệt: báo cáo huấn luyện và kiểm thử (18/11/2026)

Yêu cầu của trưởng nhóm:
- Người phê duyệt được từ chối hồ sơ mà AI đã tự duyệt và phải nêu lý do.
- AI lưu lý do làm cơ sở cho bad case mới.
- AI đánh giá lý do đó có xảy ra đủ thường xuyên để thành bad case không.
  - Nếu đủ: AI đưa vào CSDL.
  - Nếu chưa đủ: AI nêu vì sao chưa đủ và hỏi admin. Admin đồng ý thì đưa vào.
- Thêm một bảng bad case trong CSDL.
- Bổ sung lý do vì sao một tình huống được đánh giá là bad case.

## 1. Thiết kế

| Bước | Thành phần |
|---|---|
| Người duyệt thu hồi hồ sơ AI đã tự duyệt (trong 24 giờ) và bắt buộc ghi lý do (≥ 10 ký tự). Sau đó họ từ chối hoặc duyệt lại hồ sơ như bình thường. | `workflow/auto_approval.py` |
| Tín hiệu và đặc trưng của bản AI đã duyệt được chụp lại **trước** khi thu hồi tạo bản mới. Lý do và tín hiệu được lưu vào `eas.ai_feedback` (bộ nhớ ca theo người, migration 24). | `_snapshot_for_learning` |
| Sau khi lưu, AI phân tích lý do (mô hình chạy cục bộ, lý do **không** gửi ra dịch vụ ngoài) và kết luận một trong bốn trường hợp: (1) khớp bad case có sẵn, AI nêu vì sao đã bỏ sót; (2) khớp bad case có sẵn nhưng loại đơn chưa thuộc phạm vi, tạo ứng viên mở rộng; (3) kiểu rủi ro mới; (4) lý do riêng của hồ sơ. | `ai_service/bad_case_reason.py`, `POST /ai/bad-case/analyze-reason` |
| Đề xuất điều kiện đo được. Ngưỡng lấy từ chính hồ sơ bị thu hồi, và điều kiện phải bắt được hồ sơ đó. Đặc trưng: số giờ báo trước, ngày trong tháng, thứ trong tuần (chỉ khi lý do nêu rõ thứ), giờ gửi, số ngày, số tiền, số hồ sơ bị từ chối trong 30 ngày, cộng 11 tín hiệu ngữ cảnh có sẵn. | `propose_condition` |
| Gom lý do giống nhau vào cùng một ứng viên. Điều kiện gom: (a) cùng mã, hoặc cùng đặc trưng và cùng loại đơn, hoặc câu chữ đủ giống; và (b) **nếu ứng viên đã có điều kiện thì điều kiện đó phải bắt được hồ sơ mới**. | `analyze` |
| AI tự đánh giá "đủ để thành bad case chưa", rồi tự kích hoạt hoặc hỏi admin. | `api_core/workflow/bad_case_learning.py` |
| Bad case đang dùng được gửi kèm mỗi lần đánh giá tự duyệt. Hồ sơ dính bad case thì không được tự duyệt và chuyển A → B/C, kèm **"Vì sao là bad case"**. | `bad_cases.evaluate(learned=…, overrides=…)` |

### Tiêu chí "đủ thường xuyên" (tất cả đều phải đạt)

| Tiêu chí | Ngưỡng | Lý do chọn |
|---|---|---|
| Số lần thu hồi vì cùng kiểu lý do | ≥ 3 trong 90 ngày | Một lần có thể là ngẫu nhiên |
| Số người gửi khác nhau | ≥ 2 | Thói quen của một người đã có bộ nhớ ca theo người (migration 24) |
| Số người duyệt độc lập | ≥ 2 | Không phải tiêu chuẩn riêng của một quản lý |
| Kiểu chung | Đa số lý do được AI hiểu là kiểu chung, **hoặc** lặp lại ở ≥ 2 người gửi và ≥ 2 người duyệt | Một câu đơn lẻ khó phân biệt chung/riêng (xem mục 3) |
| Độ chắc rằng lý do không thuộc bad case có sẵn | Trung bình ≥ 50% | |
| Đo được bằng dữ liệu hệ thống | Có điều kiện | Không có điều kiện thì AI không tự nhận ra lần sau |
| Không chặn tràn lan | Điều kiện bắt ≤ 30% hồ sơ cùng loại trong 90 ngày (tính trên CSDL thật) | Tránh chặn cả loại đơn |

Khi chưa đủ, `eas.bad_case.evaluation` lưu từng tiêu chí đạt hoặc không đạt, câu tóm tắt "Chưa đủ vì: …" và câu hỏi cho admin. Ví dụ: "Có tạo bad case … để AI không tự duyệt và chuyển sang quy trình B các hồ sơ Làm việc từ xa khi số giờ báo trước ≤ 24 giờ không?"

Admin trả lời trên trang **Quy định → AI học từ phản hồi → Danh mục bad case**:
- Chọn "Có, tạo bad case". Admin sửa được tên, lý do vì sao là bad case và điều kiện JSON trước khi tạo.
- Hoặc chọn "Không tạo" và ghi lý do.

Ứng viên đã bị từ chối vẫn được ghi thêm bằng chứng. Khi có thêm 3 ca mới, AI mở lại ứng viên và hỏi lại admin.

### Bảng CSDL (migration 25)

**`eas.bad_case`**
- Lưu danh mục: 12 bad case có sẵn (BUILTIN, seed từ `data/bad_case_catalog.json`), bad case học được (RULE, có điều kiện) và bad case mở rộng phạm vi (SCOPE).
- `rationale` là lý do vì sao đó là bad case. Bad case có sẵn lấy tác hại trong danh mục. Bad case học được tổng hợp trích dẫn lý do của các người duyệt.
- Trigger:
  - Không cho xóa.
  - Bad case có sẵn chỉ được ngưng hoặc bật lại.
  - Chỉ cho các chuyển trạng thái hợp lệ.
  - Điều kiện của bad case đã kích hoạt không sửa được; muốn đổi thì ngưng và học bad case mới.

**`eas.bad_case_evidence`**
- Mỗi lý do thu hồi là một dòng: kết luận của AI, độ chắc, đặc trưng của hồ sơ lúc đó, giải thích.
- Chỉ được thêm, không sửa, không xóa.

Cả hai bảng bật RLS và chỉ cấp quyền cho các vai trò backend, như migration 24.

## 2. Huấn luyện bộ phân loại lý do

- **Mô hình:** TF-IDF (từ 1-2 gram + ký tự 2-5 gram, có bản không dấu) + hồi quy logistic.
- **Hai đầu dự đoán:**
  - Đầu nhãn: 12 mã bad case, NEW_PATTERN, ONE_OFF.
  - Đầu đặc trưng: số giờ báo trước, ngày cuối tháng, thứ, giờ gửi, số ngày, số tiền, số hồ sơ bị từ chối, hoặc không đo được.
- **Dữ liệu huấn luyện:** Gemini sinh câu chỉ từ mô tả trong danh mục, không thấy bộ test. Lượt 1 có 680 câu; lượt 2 có 718 câu ngắn, gồm các cặp tương phản giữa kiểu chung và lý do riêng. 30% số câu được thêm bản không dấu. Tổng cộng 1.796 câu.
- **Chọn tham số:** chỉ bằng kiểm định chéo 5 phần trên tập train.

### Quy trình chấm trung thực

1. **Bộ test 1** (72 câu viết tay, băm SHA-256 `eb01b749…`, commit `0c6b7ad`) được viết và băm trước khi sinh dữ liệu và cài mô hình. Nó chấm phiên bản 1 **một lần**. Kết quả xấu: mô hình đúng 69,4%, thua Gemini đoán thẳng (76,4%) và baseline từ khóa (81,9%). Baseline từ khóa do cùng người viết **sau khi** đã viết bộ test 1, nên điểm này bị thổi phồng; mục 3 chứng minh điều đó.
2. Sau khi xem lỗi của bộ test 1, **bộ test 2** (72 câu mới, băm `16cd8f18…`, commit `c9984d7`) được viết và băm **trước** khi làm phiên bản 2. Bộ test 2 là thước đo sạch duy nhất cho phiên bản 2. Bộ test 1 chỉ để tham khảo.

### Kết quả (độ chính xác đúng nhãn; macro-F1 trên 3 nhóm: có sẵn / kiểu mới / lý do riêng)

| Bộ máy | Test 2 (sạch) | Test 1 (đã dùng) |
|---|---|---|
| **Mô hình v2 (đang dùng)** | **70,8%** · F1 0,654 | 73,6% · F1 0,742 |
| Mô hình v1 | 61,1% · F1 0,601 | 69,4% · F1 0,716 |
| Baseline từ khóa | 45,8% · F1 0,463 | 81,9% · F1 0,802 |
| Gemini zero-shot (`gemini-3.5-flash-lite`) | 79,2% · F1 0,706 | 77,8% · F1 0,691 |

Chi tiết v2 trên test 2:

| Chỉ số | Kết quả |
|---|---|
| F1 nhóm "có sẵn" | 0,843 |
| F1 nhóm "kiểu mới" | 0,417 |
| F1 nhóm "lý do riêng" | 0,703 |
| Đúng mã bad case có sẵn | 91,7% (v1: 58,3%) |
| Đầu đoán đặc trưng, chạy thẳng trên 18 câu kiểu mới | 72,2% (v1: 72,2%) |

Kiểm định chéo đã chọn: thêm mã loại đơn vào đầu câu (CV 0,915, không thêm là 0,860). Đặc trưng "dấu hiệu chung/riêng" soạn tay **không** giúp (0,910) nên không dùng.

## 3. Nhận xét trung thực

- **Ranh giới "kiểu mới / lý do riêng" từ một câu đơn lẻ rất khó.** Cả mô hình lẫn Gemini chỉ đạt F1 0,417 ở nhóm "kiểu mới". Vì vậy hệ thống **không** để một câu đơn lẻ quyết định: kiểu chung được chứng minh bằng việc lặp lại ở nhiều người gửi và nhiều người duyệt, đúng tiêu chí "thường xảy ra" của trưởng nhóm. Lý do bị xếp nhầm sang "riêng" vẫn được gom và đánh giá như thường.
- **Baseline từ khóa giảm từ 81,9% xuống 45,8%** khi sang bộ test sạch, đúng như nghi ngờ rằng nó đã khớp theo bộ test 1. Đây là lý do cần bộ test thứ hai.
- **Gemini đoán thẳng cao hơn mô hình nội bộ 8,4 điểm** trên test 2, nhưng không được dùng: lý do thu hồi là văn bản tự do của quản lý, có thể chứa tên người và chi tiết nội bộ, mà quy định của dự án là không gửi dữ liệu cá nhân cho LLM. Muốn dùng thì cần bước che tên trước (để sau).
- **Thiên lệch đã biết:** với đơn WFH, mô hình hay nghiêng về BC_WFH_FREQUENT chỉ vì có chữ "WFH". Có thử luật quyết định hai bước (thuộc danh mục hay không → nhãn), nhưng kiểm định chéo cho thấy luật này kém hơn (0,906 so với 0,915) nên không dùng.
- **Thay đổi đưa ra sau khi đã thấy bộ test 2 hoặc kết quả chạy thật** (đều ghi lại ở đây, không có bộ test sạch thứ ba để đo lại):
  1. Đầu đoán đặc trưng học từ dữ liệu lượt 1. Kiểm định chéo trên các fold lượt 1: thêm lượt 2 làm kém đi (0,688 so với 0,738), vì nhãn đặc trưng của lượt 2 nhiễu.
  2. Chạy đầu đoán đặc trưng cả khi lý do bị xếp là "riêng". Đổi tiêu chí "kiểu chung" sang đa số lý do hoặc lặp lại ở nhiều người.
  3. Sau lần chạy thật thứ nhất:
     - Điều kiện đề xuất phải bắt được chính hồ sơ bị thu hồi. Một ca báo trước 26 ngày từng được đề xuất là "≤ 48 giờ".
     - Điều kiện "thứ trong tuần" chỉ đặt khi lý do nêu thứ.
  4. Sau lần chạy thật thứ hai:
     - Ràng buộc nhất quán khi gom ca. Lý do "ghi thiếu danh sách công việc" từng bị gom vào ứng viên "báo trước sát giờ" và đẩy ứng viên đó vượt ngưỡng.
     - Gom với độ giống câu chữ ≥ 0,15 khi điều kiện của ứng viên bắt được hồ sơ và lý do mới không có điều kiện riêng.
  5. Sau lần chạy thật thứ ba: tiêu chí độ chắc dùng xác suất "không thuộc danh mục có sẵn", thay cho xác suất của một nhãn đơn lẻ.

## 3b. Phiên bản 3 (19/11/2026): ca oái oăm và phủ định đúng loại

**Thứ tự (để chấm trung thực):**

1. **Bộ test 3** (72 câu oái oăm viết tay: không dấu, viết tắt, trộn tiếng Anh, phủ định "không phải vì X mà vì Y", nhắc tên loại đơn nhưng không phải bad case của loại đó) được băm (`58a946a7…`, commit `c61b10f`) trước khi sinh dữ liệu và huấn luyện v3.
2. v2 được chấm trên bộ test 3, và **tôi đã xem danh sách lỗi của v2** trước khi làm v3. Lỗi chủ yếu là thiên lệch theo loại đơn (đơn WFH → BC_WFH_FREQUENT). Vì vậy bộ test 3 không hoàn toàn "mù" với hướng cải tiến; nó vẫn sạch về **câu chữ** (không câu nào trong dữ liệu sinh trùng hoặc gần giống ≥ 0,9 với cả 3 bộ test).
3. Dữ liệu lượt 3 (`bad_case_reasons_train3.json`, 659 câu, Gemini chỉ thấy mô tả danh mục), gồm hai phần:
   - 359 câu "đúng loại nhưng không phải bad case có sẵn" (kiểu mới / lý do riêng), viết theo văn phong oái oăm;
   - 300 câu oái oăm cho 12 bad case có sẵn.
4. Chọn cấu hình chỉ bằng kiểm định chéo trên tập train: C = 16, có mã loại đơn, không đặc trưng soạn tay; CV 0,912. Đầu đoán đặc trưng vẫn học từ lượt 1 như v2. Không chỉnh gì sau khi chấm.

**Kết quả** (đúng nhãn · macro-F1 3 nhóm):

| Bộ máy | Test 3 (oái oăm) | Test 2 | Test 1 (đã dùng) |
|---|---|---|---|
| **v3 (đang dùng)** | **76,4% · 0,730** | **75,0% · 0,700** | 76,4% · 0,781 |
| v2 | 70,8% · 0,665 | 70,8% · 0,654 | 73,6% · 0,742 |
| Baseline từ khóa | 48,6% · 0,489 | 45,8% · 0,463 | 81,9% · 0,802 |

- Trên test 3, so với v2: v3 sửa được 4 câu và không làm hỏng câu nào v2 đã đúng.
- Lỗi còn lại trên test 3 (17 câu):
  - 9 câu "kiểu mới" bị xếp sai: 3 câu thành BC_WFH_FREQUENT (vẫn thiên lệch theo chữ "WFH"), 3 câu thành "lý do riêng";
  - 6 câu "lý do riêng" bị xếp thành bad case có sẵn;
  - 1 câu nhầm giữa hai bad case có sẵn.
- Nhóm "kiểu mới" vẫn là điểm yếu nhất. Như mục 3: hệ thống không để một câu đơn lẻ quyết định, mà cần lặp lại ở nhiều người gửi và nhiều người duyệt.
- Đầu đoán đặc trưng không đổi so với v2 (cùng dữ liệu lượt 1).

## 4. Kiểm thử thật trên bản sao CSDL local (`tests/live/test_bad_case_learning.py`)

Kết quả: **4/4 PASS, hai lần chạy liên tiếp**, sau 5 lần chạy có lỗi đã sửa như mục 3. Chi tiết: `bad_case_learning_live_results.json`.

| Ca | Kịch bản | Kết quả |
|---|---|---|
| BL-01 | 3 người duyệt thu hồi 3 đơn WFH báo trước sát giờ của 3 người gửi, 3 cách viết khác nhau | Lần 1 và 2: ứng viên, AI hỏi admin. Lần 3: AI tự thêm `BC_NOTICE_HOURS_WFH_REQ` (≤ 24 giờ). Trước kiểm thử, trong 82 hồ sơ WFH 90 ngày không hồ sơ nào báo trước ≤ 24 giờ, nên tiêu chí độ phủ đạt. Người thứ tư (chưa từng bị thu hồi) gửi đơn sát giờ thì bị chuyển B, kèm "Vì sao là bad case: Người duyệt đã thu hồi … vì: …". Đơn báo trước 20 ngày của người khác vẫn được tự duyệt. |
| BL-02 | "Em ghi thiếu danh sách công việc…" | AI kết luận lý do riêng và nêu vì sao chưa đủ, hỏi admin. Admin từ chối, trạng thái REJECTED. |
| BL-03 | "Tháng này làm từ xa quá nhiều buổi" | Khớp BC_WFH_FREQUENT, không tạo bad case mới. AI nói vì sao bỏ sót: hồ sơ chưa vượt ngưỡng 8 đơn/tháng (mới 1). |
| BL-04 | "Tuần nào cũng xin WFH vào thứ Sáu" | Ứng viên với điều kiện "thứ Sáu", chưa đủ nên hỏi admin. Admin tạo, AI dùng ngay: đơn thứ Sáu của người khác chuyển B, đơn thứ Tư vẫn tự duyệt. |

Kiểm thử thật cũ, chạy lại:
- Chuyển quy trình: 4/6. Học từ phản hồi: 4/5, 0 lần lặp lỗi, 0 lần học tràn.
- 3 ca trượt (ESC-04, ESC-05, FB-03) cùng một nguyên nhân dữ liệu: trên bản sao local, an.pham@eas.com đang giữ 46 bước duyệt chưa đóng (15 việc đã quá hạn) tích lũy từ các phiên kiểm thử trước. Kế hoạch xử lý lấy 30 việc có hạn sớm nhất nên việc mới tạo bị đẩy ra ngoài.
- Mã nguồn phần đề xuất xử lý không đổi trong đợt này.

## 5. Tái lập

```
ai_service\.venv-ai\Scripts\python -I ai_service\training\gen_bad_case_reasons.py            # lượt 1 (cần GEMINI_API_KEY)
ai_service\.venv-ai\Scripts\python -I ai_service\training\gen_bad_case_reasons.py --v2       # lượt 2
ai_service\.venv-ai\Scripts\python -I ai_service\training\gen_bad_case_reasons.py --v3 --per-case 25   # lượt 3 (lưu từng lô, chạy lại để bù lô lỗi)
ai_service\.venv-ai\Scripts\python -I ai_service\training\train_bad_case_reason.py --version v3 --final --tests 1,2,3 [--compare <mô hình v2>]
```
