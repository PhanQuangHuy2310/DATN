# AI theo catalog v2: train lại, sửa tự duyệt và OCR, kiểm thử đầy đủ; sửa giao diện khi thu phóng

Nhánh `dat` → `main`. 10 commit (kể cả commit mô tả này). `main` hiện là gốc của `dat` nên **không có xung đột**.
**Không có migration database.** Khi deploy cần build lại image `ai-service`, `web`, `web-admin` (xem cuối).

## Tóm tắt

| Phần | Thay đổi | Ảnh hưởng người dùng |
|---|---|---|
| AI phân loại | Một pipeline train duy nhất theo 58 loại catalog v2, train lại model | Gợi ý loại yêu cầu đúng hơn: **89,8% → 95,3%** trên câu viết tay chưa dùng để train |
| AI tự duyệt | Sửa lỗi bỏ qua quy tắc theo loại | AI **không còn tự duyệt** nghỉ quá số phép / ≥ 3 ngày, phòng đã có người đặt, hoàn tiền > 2 triệu |
| AI OCR | Chạy PaddleOCR ở process riêng | Trước đây mọi lần gọi OCR trên Docker đều mất kết nối; nay đọc đúng 3/3 hóa đơn mẫu |
| Giao diện | Sửa vỡ bố cục ở zoom 125–150% | Bảng người dùng, ma trận phân quyền, header hiển thị đúng trên laptop có thu phóng |
| Cấu hình | Một file `.env.example` ở thư mục gốc | Bỏ 3 file mẫu cấu hình con |

## Chi tiết

### 1. AI phân loại yêu cầu (`100b240`)
- `ai_service/training/train.py` thay 13 script cũ. Dữ liệu sinh từ `training/data/request_corpus.json` với seed cố định, nên chạy lại cho cùng model. Model cũ chỉ bị thay khi mọi bước train xong.
- Model: TF-IDF (từ + ký tự không dấu, chịu được gõ không dấu) → Logistic Regression. Trả về mã catalog v2, nhóm, bộ phận xử lý, template, cờ `low_confidence` và 3 khả năng hàng đầu.
- Giao diện (`AiAssist.jsx`) chỉ gợi ý đổi loại khi AI chắc chắn **và** người dùng được tạo loại đó.
- Bổ sung mẫu câu cho các cặp loại hay nhầm (nghỉ phép / thôi việc, VPN / làm việc từ xa, máy chủ / laptop, sửa điều hòa / mua điều hòa…) và 116 câu viết tay mới ở split `dev`.

**Độ chính xác** (split `test`: 127 câu viết tay, không dùng để train hay chỉnh dữ liệu):

| | Trước | Sau |
|---|---|---|
| Đúng loại (top-1) | 89,8% | **95,3%** |
| Đúng trong 3 gợi ý | 98,4% | **99,2%** |
| Đúng nhóm | 91,3% | 96,1% |

6 câu `test` còn sai, ví dụ "xin mo vpn de lam viec o nha" → Làm việc từ xa (đúng: Cấp quyền), "Mượn 2 bạn bên kho phụ đóng hàng" → Mượn thiết bị (đúng: Hỗ trợ liên phòng ban). Lưu ý: danh sách câu `test` sai của lần train trước đã hiện trong báo cáo, nên con số 95,3% có thể hơi lạc quan. Mẫu câu mới được viết theo nghiệp vụ, không chép câu `test`.

Chấm điểm rủi ro (XGBoost master/finance/hr/it, dữ liệu mô phỏng có 3% nhiễu cố ý): accuracy 95,4–97,5%, lệch ≤ 1 bậc 99,7–100%.

### 2. AI tự duyệt bỏ qua quy tắc theo loại (`b81c706`)
API gửi mã catalog (`LEAVE`, `ROOM_BOOKING`, `REFUND_COMPENSATION`, `ATTENDANCE_ADJUSTMENT`), nhưng bảng quy tắc trong AI chỉ có tên cũ (`leave_short`, `room_booking`, `refund`). Kết quả là mọi đơn rơi vào quy tắc chung "duyệt nếu rủi ro thấp". Ngoài ra API luôn gửi số ngày nghỉ = 0.
- AI tra quy tắc theo mã catalog (mã cũ vẫn được ánh xạ).
- API gửi `days_requested` tính từ `start_date`..`end_date`.
- **Hành vi mới:** AI chuyển người duyệt nhiều hơn với Nghỉ phép, Đặt phòng họp, Hoàn tiền. Đây là đúng quy tắc đã ghi trong code. Nếu muốn nới quy tắc thì cần quyết định riêng.

### 3. OCR làm worker AI bị kill (`abdc7a0`)
PaddleOCR giữ GIL nhiều giây. Với `--workers 2`, uvicorn không nhận được tín hiệu sống của worker nên kill nó giữa request ("Child process died"). Engine OCR nay chạy trong một process con của mỗi worker. Trên CPU, OCR mất khoảng 30–60 giây mỗi ảnh. Hiện chưa luồng nghiệp vụ nào gọi OCR.

### 4. Kiểm thử chức năng AI (`7247456`)
`test_ai_benchmark.py` (bản cũ dùng mã loại không còn tồn tại) được viết lại thành 37 kiểm tra trên service đang chạy, chỉ đọc, không ghi DB. Các nhóm kiểm tra: xác thực nội bộ, phân loại toàn bộ câu viết tay, độ trễ, rủi ro theo domain, 9 ca tự duyệt, tóm tắt, OCR 3 hóa đơn, chặn SSRF, quy định, ngữ cảnh hệ thống ngoài, route AI của API được bảo vệ.

```powershell
.\.venv\Scripts\python.exe test_ai_benchmark.py
```

### 5. Giao diện khi thu phóng (`3ffd192`)
- Bảng người dùng và ma trận phân quyền có bề rộng tối thiểu; khi thiếu chỗ thì cuộn ngang trong card, thay vì chữ vỡ từng ký tự và nút đè sang cột khác.
- Badge "Khóa cứng hệ thống" không còn đè công tắc.
- Header: tagline thương hiệu một dòng; tiêu đề trang kết thúc bằng "…"; ô tìm kiếm giãn theo chỗ trống. Ở ≤ 1200px chỉ hiện avatar, tên và chức vụ hiện khi rê chuột.
- Nút "Xem Sơ đồ tổ chức" có khoảng cách giữa icon và chữ.
- Đã kiểm tra bằng ảnh chụp ở 1920px, 1366px (zoom 100/125/150%) và 1024px.

### 6. Khác
- `1f188dd`: gộp mẫu cấu hình về `.env.example` gốc. `VITE_ADMIN_PORTAL_URL` trỏ đúng cổng 8081.
- `c258be5`: giữ kết nối DB 300 giây, tắt health check mỗi request (bật lại bằng `EAS_DB_CONN_HEALTH_CHECKS=true`), cache `/request-types` 60 giây.
- `d19f2b8`: `check_local.cmd` không còn báo lỗi sai (chờ `/health/ready` đủ lâu, đọc đúng biến `EAS_*` và Redis). README ghi đúng cổng web quản trị 8081.
- `7967da9`: sửa test header tải tệp bị lỗi do bước kiểm tra chế độ bảo trì.

## Kết quả kiểm thử

| Bộ test | Kết quả |
|---|---|
| Django `manage.py test` | 590 đạt (41 bỏ qua do thiếu thư viện AI trong venv API) |
| `tests/run_tests.py` | 183 đạt |
| Test AI (venv AI, gồm 11 ca quy tắc tự duyệt mới) | 34 đạt |
| `test_ai_benchmark.py` trên Docker | 37/37 |
| Web client `npm test` | 72 đạt; lint 0 lỗi; build `web_client`, `web_admin` đạt |
| ruff, compileall, `check_repository_secrets.py` | Sạch |

## Khi deploy
1. Không có migration.
2. Build lại: `docker compose --env-file .env build ai-service web web-admin`, rồi `docker compose --env-file .env up -d`. Model mới nằm trong `ai_service/models/` (mount vào container).
3. `.env` không cần thêm biến mới. Biến tùy chọn: `EAS_DB_CONN_HEALTH_CHECKS`, `EAS_DB_LOCK_TIMEOUT_MS`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
