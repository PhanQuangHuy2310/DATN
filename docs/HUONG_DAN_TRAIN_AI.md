# Hướng dẫn train AI cho EAS: làm gì, làm thế nào, không được làm gì

Tài liệu giao việc cho người phụ trách phân hệ AI. Đọc hết mục 1–3 trước khi chạy bất cứ thứ gì.
Cập nhật: 17/11/2026. Hạn chót đề xuất: 21/11/2026, trước buổi quay video demo.

---

## 1. Hướng đi: train cái gì, và vì sao

Buổi góp ý 16/11 thầy đã chỉ ra hai điểm. Hướng làm dưới đây bám theo đúng hai điểm đó.

1. **"AI ở đâu?"** Nếu AI chỉ gợi ý loại yêu cầu và chấm điểm theo trọng số do người đặt tay, hội đồng sẽ bảo đó là RPA hoặc BPM, không cần AI. Vì vậy **không dồn sức đẩy độ chính xác của bộ phân loại lên cho đẹp**.
2. **Giá trị thật mà thầy muốn thấy:** khi có **quy định mới**, hệ thống chỉ ra quy trình nào bị ảnh hưởng và đề xuất cấu hình mới (nâng mẫu vòng đời, tăng mức rủi ro). Theo định hướng của nhóm trưởng, phần này dùng **học máy nội bộ** (mô hình hồ sơ quy trình, mục 4.3), không gọi API AI bên ngoài.

Thứ tự ưu tiên:

| Ưu tiên | Hạng mục | Mục tiêu | Mục |
|---|---|---|---|
| 1 | **Phân tích tác động quy định** (tính năng mới) | Có bộ kịch bản kiểm thử và số đo; dùng được cho video demo | 4.3 |
| 2 | **Mô hình rủi ro** | Trình bày trung thực; thêm ngữ cảnh đúng ví dụ thầy đưa | 4.2 |
| 3 | **Bộ phân loại** | Sửa 2 điểm yếu đã đo được, không chạy theo con số | 4.1 |

---

## 2. Hiện trạng (đo ngày 17/11/2026)

| Thành phần | Cách hoạt động | Dữ liệu | Kết quả | Điểm yếu |
|---|---|---|---|---|
| Bộ phân loại 58 loại | TF-IDF + Logistic Regression | 37.701 câu tổng hợp + 775 câu thật + 1.200 câu bán tổng hợp + 622 câu do AI sinh | Viết tay 89,0%; phiếu IT thật 85,5%; câu ngoài phạm vi bị gắn cờ 75,3% | Mô hình cũ đạt 93,7% trên câu viết tay và gắn cờ 89% câu ngoài phạm vi, nay cả hai đều giảm |
| Mô hình rủi ro | 4 mô hình XGBoost | 91.500 yêu cầu **mô phỏng**, nhãn do **luật** của nhóm gán | Accuracy 96,6% | Mô hình chỉ học lại luật của nhóm. Đừng trình bày như "AI phát hiện rủi ro" |
| "AI học quy định" | **Không train**: biên dịch văn bản thành vài tham số (`amount_gt`, `days_gt`, `min_risk`, `auto_approve`) | — | — | Không đụng tới cấu trúc quy trình, chưa phải điều thầy cần |

Chi tiết nguồn dữ liệu xem Phụ lục C trong báo cáo, và `workspace/du_lieu_cong_khai/README.md`.

---

## 3. Quy tắc bắt buộc (vi phạm là hội đồng có quyền bác cả phần AI)

1. **Mọi dòng dữ liệu phải có `source` và `mapping`** (câu thật, bán tổng hợp hay do AI sinh). Không bịa nguồn, không ghi "lấy từ web X" khi không lấy từ đó.
2. **Không bao giờ train trên tập test**, cũng không chọn tham số trên tập test. Tập test gồm:
   - `request_eval_realistic.json` (split `test`)
   - `request_eval_short.json` (split `test`)
   - `request_eval_public.json` (toàn bộ)

   Tham số chỉ được chọn trên split `dev`.
3. **Không sửa câu hay nhãn trong tập test để tăng điểm.** Nếu thấy nhãn sai, ghi vào nhật ký và báo cả nhóm, không tự sửa.
4. **Câu do AI sinh không được giống câu test.** Script ghép dữ liệu đã tự loại câu có độ giống ≥ 0,6. Không tắt bước này.
5. **Báo cáo cả số giảm, không chỉ số tăng.** Ví dụ hiện tại: câu viết tay giảm từ 93,7% xuống 89,0%.
6. **Ghi lại mọi lần chạy** vào nhật ký thí nghiệm (mục 5.3). Con số nào không có trong nhật ký thì không đưa vào báo cáo.
7. Dữ liệu cá nhân thật (tên, email, số điện thoại) không được nằm trong dữ liệu train hay trong repo.

---

## 4. Việc cần làm

### 4.1. Bộ phân loại: sửa hai điểm yếu (khoảng 1 ngày)

**Việc 1: câu ngoài phạm vi.** Câu như "bật nhạc", "thời tiết hôm nay" phải bị gắn cờ, mục tiêu ≥ 85% (hiện 75,3%). Chọn một trong hai cách:
- **Cách A, đơn giản:** chỉnh ngưỡng `LOW_CONFIDENCE`. Hiện ngưỡng là 0,35, đặt ở `ai_service/routers/classify.py` và `train.py`, hai chỗ phải luôn giống nhau. Chọn ngưỡng trên một tập dev ngoài phạm vi lấy từ phần **train** của MASSIVE vi-VN, đúng 29 ý định đang dùng trong `02_build_eval.py`. Tuyệt đối không dùng phần test.
- **Cách B, tốt hơn nhưng tốn công:** thêm một lớp "không phải yêu cầu", huấn luyện bằng câu MASSIVE phần train. Cách này phải sửa thêm `routers/classify.py`, vì lớp mới không có trong catalog, và phải chạy lại `test_ai_benchmark.py`.

Dù chọn cách nào cũng phải đo lại cả bốn tập test, vì cách sửa này có thể làm giảm điểm câu viết tay.

**Việc 2: phân tích lỗi trên câu viết tay.** Mở `ai_service/training/data/training_report.md`, xem danh sách câu sai, rồi phân loại nguyên nhân:
- thiếu mẫu câu, thì bổ sung `request_corpus.json`;
- hai loại trùng nghĩa, thì ghi vào hạn chế;
- dữ liệu thật kéo lệch, thì giảm trọng số.

Không thêm câu giống hệt câu test vào corpus.

**Việc 3: rà soát dữ liệu dịch.** Lấy ngẫu nhiên 100 dòng trong `workspace/du_lieu_cong_khai/translate/*.tsv` và kiểm tra bản dịch cùng nhãn. Ghi số dòng sai vào nhật ký. Con số này đưa vào báo cáo dưới dạng "nhóm rà soát n mẫu, tỷ lệ sai x%".

Không cần làm:
- Không đổi sang mô hình lớn (BERT, PhoBERT) vào lúc này. Không đủ thời gian để đánh giá đàng hoàng, và đó cũng không phải điều thầy hỏi.
- Không cố đạt 100%.

### 4.2. Mô hình rủi ro: đúng hướng thay vì đẹp số (khoảng 1 ngày)

1. **Trình bày trung thực.** Gọi đúng tên là *"mô hình mô phỏng đánh giá của chuyên gia, học từ bộ luật của nhóm"*. Accuracy 96% chỉ chứng minh mô hình bắt chước luật tốt.
2. **Thêm ngữ cảnh, theo đúng ví dụ thầy đưa.** Xin nghỉ chiều nay bình thường là mức 2. Nhưng nếu người đó đang giữ một hồ sơ sắp hết hạn hoặc một khoản cần duyệt trong chiều nay, thì mức rủi ro không còn là 2. Đề xuất đặc trưng mới, lấy được từ dữ liệu EAS:
   - `pending_approvals_due_24h`: số việc người xin nghỉ đang phải duyệt hoặc xử lý, hết hạn trong 24 giờ.
   - `team_absence_ratio`: tỷ lệ người trong phòng đã nghỉ trùng ngày.
   - `has_critical_deadline`: có hồ sơ mức rủi ro ≥ 4 do người này phụ trách đang mở hay không.

   Thêm các đặc trưng này vào `build_risk_dataset` / `risk_features` trong `train.py` và `build_feature_vector` trong `routers/risk.py`. **Thứ tự cột ở hai chỗ phải khớp nhau.** Luật gán nhãn mới (ví dụ có deadline quan trọng thì +2) phải ghi rõ trong `label_policy` để hiện ra trong báo cáo.
3. **Giải thích được.** Mỗi lần chấm điểm phải trả kèm lý do, ví dụ "+2 vì đang giữ 3 hồ sơ hết hạn hôm nay", để người duyệt hiểu được. Hội đồng chấm điểm này cao hơn con số accuracy.
4. Nới trần số tiền của OFFICE_SUPPLIES trong `AMOUNT_PROFILE`, vì dữ liệu thật vượt mức giả định (Bảng PL-82).

### 4.3. Hồ sơ quy trình và tác động của quy định mới: học máy NỘI BỘ (đã có, 17/11/2026)

Định hướng của nhóm trưởng: phần này là **ML chạy trong hệ thống**, không gọi API AI bên ngoài. Mô hình tự đánh giá mẫu vòng đời A/B/C và trọng số rủi ro 1–5 của một loại yêu cầu, và khi có quy định mới thì chỉ ra loại nào cần nâng cấu hình. Mọi kết quả chỉ là đề xuất, quản trị viên duyệt mới áp dụng.

| Thành phần | Tệp |
|---|---|
| Mô hình | `ai_service/process_profile.py` (LR cho A/B/C, Ridge cho trọng số, định giá nghĩa vụ bằng hệ số không âm) |
| Huấn luyện + đánh giá | `ai_service/training/train_process_profile.py` → `models/process_profile.joblib`, `training/data/process_profile_report.md` |
| Dữ liệu | `training/data/process_profiles.json` (58 loại, nhãn do nhóm gán) |
| Đáp án kịch bản | `regulation_scenarios*.json` + `.sha256` (30 kịch bản, 3 bộ) |
| API | AI: `/ai/process-profile/assess`, `/regulation-impact`, `/info`; API core: `GET /api/v1/admin/regulations/<id>/impact`, `POST /api/v1/admin/ai-engine/process-profile` |
| Kiểm thử | `tests/test_process_profile.py`, `api_core/tests/test_process_profile_admin.py` |

**Quy tắc bắt buộc khi sửa mô hình này:**
1. **Không đưa người thực hiện, người nghiệm thu, cấp duyệt hay mô tả dạng tuyến duyệt vào đầu vào.** Chúng suy ra từ nhãn (lộ nhãn).
2. **Không sửa tệp đáp án đã băm.** Script tự từ chối chạy nếu SHA-256 lệch. Muốn sửa mô hình sau khi đã xem kết quả thì: viết bộ kịch bản MỚI + băm trước → sửa mô hình → chấm bộ mới một lần. Bộ cũ thành tập phát triển. (Đã làm 3 vòng: QD-01..10, QD-11..20, QD-21..30.)
3. Báo cáo kết quả cả khi thua mốc so sánh. Hiện tại: A/B/C hơn luật từ khóa (56,9% so với 51,7%), trọng số kém luật (MAE 0,91 so với 0,78), kịch bản giữ lại cuối 7/10, ngang luật.

**Bổ sung 17/11 (theo kịch bản AI của nhóm):**
- **Phân tích quy định bằng LLM** (`ai_service/regulation_llm.py`, router `/ai/regulation-llm/analyze`): truy xuất TF-IDF (12 loại + 3 quy định cũ gần nhất) → Gemini nhiệt độ 0, JSON → kiểm tra bằng luật (mã hợp lệ, chỉ tăng kiểm soát, trích dẫn phải có trong văn bản) → admin duyệt. Lỗi/thiếu key thì tự dùng mô hình nội bộ. Admin API mặc định dùng LLM, `?engine=ml` dùng mô hình nội bộ.
  Đánh giá: `ai_service\.venv-ai\Scripts\python ai_service\training\eval_regulation_llm.py` (gọi Gemini 30 lần; `--rescore` chấm lại không gọi API). Kết quả 17/11: LLM 25/30, nội bộ 18/30, luật 17/30; LLM đề xuất thừa ở 2/3 quy định không liên quan.
- **Tình huống xấu** (`ai_service/bad_cases.py` + `api_core/workflow/bad_case_signals.py`): né việc đến hạn 24h, chia nhỏ tạm ứng (> 20 triệu / 7 ngày), chấm công lần ≥ 4 / 30 ngày; SoD đã có ở trigger CSDL. Kiểm thử trực tiếp: `tests\live\test_bad_cases.py` (5/5 PASS trên sandbox).
- Không có quy trình loại D: chỉ A/B/C.

 bổ sung mô tả nghiệp vụ thật cho các loại đang chỉ có câu giữ chỗ (cải thiện trực tiếp nhất); viết thêm kịch bản cho các loại chưa có; giao diện admin hiển thị đề xuất và nút duyệt.

---

## 5. Cách chạy

### 5.1. Lệnh

```
train_ai_local.cmd                      :: train đầy đủ (~15–20 phút), tự sao lưu model cũ
train_ai_local.cmd -Only nlp            :: chỉ bộ phân loại
train_ai_local.cmd -Only risk           :: chỉ mô hình rủi ro (~1–4 phút)
train_ai_local.cmd -Only profile        :: chỉ mô hình hồ sơ quy trình (~1–3 phút)
train_ai_local.cmd -RebuildPublicData   :: dựng lại dữ liệu công khai rồi train (cần workspace\du_lieu_cong_khai)
train_ai_local.cmd -CheckOnly           :: chỉ thử model hiện có
train_ai_local.cmd -Restore <thời điểm> :: quay về bản sao lưu
```

Áp dụng model mới bằng `docker compose restart ai-service`, hoặc chạy lại `start_ai_local.cmd`. Sau mỗi lần train chạy thêm `test_ai_benchmark.py` (cần AI service đang chạy) để chắc các API vẫn trả lời đúng.

### 5.2. Thêm dữ liệu mới

- **Câu thật hoặc câu do AI sinh:** thêm vào `workspace/du_lieu_cong_khai/` (thư mục `translate/` hoặc `ai_generated/`) rồi chạy `-RebuildPublicData`. Không sửa tay `request_public_train.json`.
- **Mẫu câu tổng hợp:** sửa `ai_service/training/data/request_corpus.json`.
- **Loại yêu cầu mới:** phải có trong `api_core/catalog/catalog_v2.json` trước, nếu không `train.py` sẽ báo lỗi.

### 5.3. Nhật ký thí nghiệm (bắt buộc)

Tạo `workspace/sua_bao_cao/nhat_ky_train.md`. Mỗi lần chạy ghi một dòng:

| Ngày giờ | Thay đổi gì | C / trọng số | Viết tay test | Câu ngắn test | Phiếu IT thật | Ngoài phạm vi | Giữ hay bỏ | Lý do |
|---|---|---|---|---|---|---|---|---|
| 17/11 10:28 | Thêm câu thật + bán tổng hợp + AI sinh | 5 / 3 | 89,0% | 94,6% | 85,5% | 75,3% | Giữ | Câu thật +30 điểm |

Số liệu lấy từ phần tóm tắt cuối mỗi lần chạy, hoặc từ `ai_service/models/model_metadata.json`.

---

## 6. Tiêu chí nghiệm thu

| Hạng mục | Đạt khi |
|---|---|
| Bộ phân loại | Viết tay test ≥ 90%; phiếu IT thật ≥ 85%; câu ngoài phạm vi bị gắn cờ ≥ 85%; p95 qua HTTP ≤ 300 ms; nhật ký có đủ các lần chạy |
| Mô hình rủi ro | Có ít nhất 1 đặc trưng ngữ cảnh (mục 4.2); mỗi điểm số kèm lý do; báo cáo gọi đúng tên "mô phỏng theo luật" |
| Phân tích tác động quy định | 10–15 kịch bản có đáp án viết trước; báo cáo độ phủ, độ chính xác, thời gian so với làm tay; 1 kịch bản chạy trọn trên giao diện để quay video |
| Dữ liệu | Mọi dòng mới có `source`/`mapping`; đã rà soát 100 mẫu dịch; tập test không đổi |

---

## 7. Lịch đề xuất

| Ngày | Việc |
|---|---|
| 18/11 | Cả nhóm rà soát 30 kịch bản QD-01..QD-30 và nhãn A/B/C, trọng số của 58 loại (đã có); rà soát 100 mẫu dịch |
| 19/11 | Bổ sung mô tả nghiệp vụ cho các loại chỉ có câu giữ chỗ; viết bộ kịch bản mới + băm trước rồi mới chỉnh mô hình hồ sơ quy trình (4.3) |
| 20/11 | Giao diện so sánh trước/sau và duyệt áp dụng; sửa ngưỡng ngoài phạm vi (4.1) |
| 21/11 | Đặc trưng ngữ cảnh cho mô hình rủi ro (4.2); train lại; cập nhật nhật ký và Phụ lục C; quay video |

---

## 8. Câu hội đồng có thể hỏi

- **"Dữ liệu lấy ở đâu?"** Trả lời theo Phụ lục C (Bảng PL-71): 4 bộ công khai có giấy phép, giao dịch thật của cơ quan công ở Anh, phần còn thiếu do AI sinh và đã ghi rõ.
- **"Sao không dùng dữ liệu doanh nghiệp thật?"** Dữ liệu yêu cầu nội bộ chứa dữ liệu cá nhân (Nghị định 13/2023), không doanh nghiệp nào công bố.
- **"Accuracy 96% của mô hình rủi ro có ý nghĩa gì?"** Nó chỉ cho thấy mô hình bắt chước bộ luật tốt. Giá trị nằm ở chỗ tính thêm ngữ cảnh và giải thích được điểm số.
- **"AI ở đâu mà không phải RPA?"** Ở phần đọc hiểu quy định mới và đề xuất thay đổi quy trình. Phần này có số đo so với làm tay.
- **"Sao độ chính xác trên câu viết tay lại giảm?"** Đây là đánh đổi để mô hình khái quát tốt hơn trên yêu cầu thật (phiếu IT tăng từ 58,7% lên 85,5%). Nhóm báo cáo cả hai con số.
