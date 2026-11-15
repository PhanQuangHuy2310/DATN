# Duy trì đăng nhập (refresh token), AI hiểu câu ngắn và tự chuyển biểu mẫu, sửa ô số tiền, đặt lại mật khẩu, sửa AI học quy định, dọn dự án

Nhánh `dat` → `main`. 17 commit (kể cả các commit tài liệu), nằm sau merge PR #10. Đã thử gộp với `main`: không xung đột.
**Không có migration database.** Refresh token lưu trong Redis.

## Tóm tắt

| Phần | Thay đổi | Ảnh hưởng người dùng |
|---|---|---|
| Đăng nhập | Refresh token + ô "Ghi nhớ đăng nhập" | Không còn bị tự đăng xuất sau 30 phút. Giữ đăng nhập 7 ngày (hoặc tới khi đóng trình duyệt nếu bỏ chọn). Sau khi đăng xuất, email điền sẵn, mật khẩu do trình duyệt lưu. |
| AI phân loại | Học thêm câu rất ngắn | "bố mất" → Nghỉ phép đặc biệt (trước: Sửa chữa văn phòng). Câu ngắn đúng **96,7%**, câu đầy đủ đúng **93,7%** (top-3 100%). |
| Tạo yêu cầu | AI tự chuyển đúng biểu mẫu | Gõ "bố mất" ở bất kỳ biểu mẫu nào thì tự sang Nghỉ phép đặc biệt, giữ nội dung đã gõ, có nút quay lại. |
| Ô số tiền | Sửa lỗi đảo chữ số | Gõ 1500000000 ra đúng 1.500.000.000. Con trỏ không nhảy khi sửa giữa số. |
| Đặt lại mật khẩu | Admin xử lý tại trang Người dùng | Admin chọn hệ thống tự sinh mật khẩu tạm hoặc tự nhập, hoặc từ chối kèm lý do. Nhân viên nhận email. |
| AI học quy định | Worker gọi được dịch vụ AI | Hết lỗi "AI chưa học được quy định … giữ bộ luật cũ". Giao diện báo đúng lượt học thất bại. |
| Dọn dự án | Xóa mobile, mã chết, file trùng; gộp tài liệu | Repo gọn hơn (629 → 549 file). Không đổi hành vi ứng dụng. |

## Chi tiết

### 1. Refresh token (`b4f91c2`, `f511b51`)
- Khi đăng nhập, ngoài phiên cũ (30 phút không thao tác, tối đa 8 giờ), hệ thống đặt thêm cookie `eas_refresh`. Cookie này HttpOnly, SameSite=Lax, Secure ở production và chỉ được gửi tới `/api/v1/auth/`. Token lưu trong Redis dưới dạng băm SHA-256.
- `POST /api/v1/auth/refresh` cấp phiên mới và đổi sang token mới; token cũ dùng một lần.
  - Nếu token cũ bị gửi lại sau 30 giây, cả chuỗi token bị thu hồi (dấu hiệu bị đánh cắp).
  - Hai tab làm mới cùng lúc không bị đăng xuất: tab đến sau chờ 0,8 giây để cookie mới của tab kia được lưu rồi mới gửi lại.
- Token bị từ chối khi tài khoản bị khóa, khi đổi mật khẩu, khi admin reset mật khẩu hoặc thu hồi quyền (`auth_version` tăng), hoặc khi không còn quyền vào cổng đó. Giới hạn 30 lần/phút/IP.
- Người dùng tự đổi mật khẩu thì trình duyệt đang dùng nhận token mới. Đăng xuất thu hồi token.
- Web: gặp 401 thì tự làm mới phiên rồi gửi lại yêu cầu một lần. Yêu cầu bị chặn trước handler nên gửi lại cả lệnh ghi cũng an toàn.
- Mật khẩu **không** lưu vào localStorage. Chỉ lưu email và lựa chọn "Ghi nhớ"; mật khẩu giao cho trình quản lý mật khẩu của trình duyệt (Credential Management API).
- Cấu hình mới trong `.env.example` (`EAS_REFRESH_*`), đều có giá trị mặc định.

### 2. AI hiểu câu ngắn (`d9d04fe`)
- `request_corpus.json` có thêm mục `short`: 442 mẫu, đủ 58 loại (ví dụ `{nguoi_than} {qua_doi}`, `quên chấm công`).
- Bộ đánh giá mới `request_eval_short.json`: 244 câu viết tay, không trùng câu dùng để train.
- Tham số C được chọn theo câu viết tay `dev`. Split `test` chỉ dùng để báo cáo.

| Split `test` (chưa dùng để train hay chọn tham số) | Trước | Sau |
|---|---|---|
| Câu đầy đủ (127 câu), đúng loại | 95,3% | **93,7%** (top-3 99,2% → 100%) |
| Câu rất ngắn (184 câu), đúng loại | chưa đo (ví dụ "bố mất", "đau bụng" đều sai) | **96,7%** |

Câu đầy đủ giảm 2 câu (95,3% → 93,7%) để đổi lấy câu ngắn. Cả hai vẫn trên mức tối thiểu 90% đặt trong `test_ai_benchmark.py`.

### 3. AI tự chuyển biểu mẫu (`797798e`)
- AI phân loại sau 0,9 giây ngừng gõ tiêu đề hoặc lý do.
- AI **tự chuyển** khi biểu mẫu mới chỉ có tiêu đề/lý do và AI chắc chắn: ≥ 60%, hoặc ≥ 35% và gấp 3 lần lựa chọn thứ hai.
- Nếu người dùng đã điền trường khác (kể cả số tiền), AI chỉ gợi ý kèm nút chuyển hoặc bỏ qua.
- Không tự chuyển khi sửa bản nháp đã lưu.
- Logic nằm trong `web_client/src/aiTypeSwitch.js` (có test).

### 4. Ô số tiền (`e151a9f`)
Khi ô đang hiện "1.000" và người dùng gõ thêm "0", chuỗi "1.0000" bị `parseDigits` hiểu là số thập phân 1,0 nên mất chữ số. Bản sửa:
- Ô tiền chỉ lấy các chữ số người dùng gõ.
- `parseDigits` phân biệt "1.000" (dấu chấm phân cách hàng nghìn) với "50000000.0" (số do API trả về).

### 5. Các commit trước trong PR này
- `5792128`: worker có `EAS_AI_SERVICE_URL` và khóa nội bộ, nên job AI học quy định và tự duyệt chạy được.
- `84f4ad6`: admin xử lý yêu cầu đặt lại mật khẩu ngay tại trang Người dùng.
  - Hai cách cấp mật khẩu tạm (tự sinh hoặc admin tự nhập theo chính sách) và từ chối.
  - Mỗi yêu cầu chỉ gửi một email cho admin.
  - Không có mật khẩu mặc định cố định.
- `ab9be66`: trang Quản trị AI báo đúng lượt học thất bại và giải thích công cụ mô phỏng; sửa vỡ bố cục bảng mẫu yêu cầu và thông báo đổi mật khẩu.

### 6. Dọn dự án (`60a27d4`, `c486fd4`, `72a9213`, `d83b908`, `f49c399`)
Repo giảm từ 629 xuống 549 file, thư mục gốc từ 45 xuống 30 file. Không đổi hành vi ứng dụng.
- Xóa `mobile_app/` (Flutter), test hợp đồng Flutter và job CI `mobile` vì nhóm không làm mobile nữa.
- Bỏ `workspace/` khỏi git (42 file báo cáo nháp) và thêm vào `.gitignore`. File vẫn nằm trên máy.
- Xóa `ClientDashboard.jsx`, `AssignedWorkDashboard.jsx`: không còn được import ở đâu.
- Thư mục gốc:
  - Xóa 7 file lỗi thời hoặc trùng: 2 file `.ps1` trùng `.cmd`, `actions.md`, script kiểm danh mục 18 mã cũ, script đối chiếu luận văn, 2 công cụ mật khẩu trùng `set_temporary_admin_password.py`.
  - Chuyển 7 công cụ chẩn đoán và bảo trì vào `scripts/` (đã chạy thử từ vị trí mới); `test_logger.py` vào `api_core/tests/`; hướng dẫn kiểm thử vào `docs/`.
- Gộp tài liệu:
  - 7 file changelog gộp thành `CHANGELOG.md`.
  - Mỗi `security/plans/X_PLAN.md` gộp vào `security/reports/X_REPORT.md`.
- Sửa lỗi CI: `api_core/config/settings.py` chưa đạt `ruff format --check`.

## Kiểm thử
- Django `manage.py test api_core`: 426 đạt, trong đó 11 test refresh token mới và 5 test logger chuyển từ thư mục gốc vào.
- `tests/run_tests.py`: 186 đạt (41 bỏ qua do venv API không có thư viện AI, như trước; bớt 2 test Flutter đã xóa).
- Web `npm test`: 85 đạt. ESLint không có lỗi mới. `npm run build` đạt.
- `test_ai_benchmark.py` trên dịch vụ AI thật: **43/43**.
- Kiểm tra trên trình duyệt (bản sao CSDL tạm, không ghi vào Supabase): 23/23.
  - Cookie an toàn; xóa phiên rồi bấm tiếp hoặc tải lại trang vẫn giữ đăng nhập.
  - Gõ 1500000000; chèn và xóa giữa số.
  - "bố mất" tự chuyển biểu mẫu, giữ tiêu đề, giữ con trỏ; nút quay lại hoạt động.
  - Biểu mẫu đã nhập số tiền thì AI chỉ gợi ý.
  - Đăng xuất: email còn, token cũ bị từ chối; bỏ "Ghi nhớ" thì cookie hết khi đóng trình duyệt.
- Các lệnh lint của CI (`ruff check`, `ruff format --check`, `compileall`), `validate_docs`, quét bí mật, `docker compose config`, build `web_client` và `web_admin` đều đạt.

## Triển khai
1. Build lại image `api`, `worker`, `web`, `web-admin`: `docker compose --env-file .env up -d --build api worker web web-admin`
2. Khởi động lại `ai-service` để nạp model mới (thư mục models được mount): `docker compose restart ai-service`
3. Không cần chạy migration. Người dùng đang đăng nhập cần đăng nhập lại một lần để nhận refresh token.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
