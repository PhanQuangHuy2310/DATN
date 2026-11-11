# Báo cáo rà soát thao tác, form và luồng giao diện DATN

Ngày rà soát: 08/11/2026. Nền mã nguồn: `DATN_dangduy_da_kiem_thu_va_sua_on_dinh_2026-11-08.zip` (bản mới nhất có thể truy cập trong cuộc trò chuyện).

## Phạm vi thay đổi

Chỉ cập nhật `web_client`. Không chỉnh sửa API/backend, schema, Supabase, Redis, AI Service, worker, Docker, quyền nghiệp vụ hoặc hợp đồng dữ liệu. File `.env` không được đóng gói mới hay sửa đổi. Gói bản vá nhỏ có thể chép đè vào repository hiện hành; nên tạo nhánh Git trước khi áp dụng.

## Các lỗi và cải tiến đã áp dụng

| Phạm vi | Vấn đề cần khắc phục | Cách xử lý |
| --- | --- | --- |
| Form xác nhận dùng chung | Hai lần submit liên tiếp trong cùng frame có thể vượt qua trạng thái `busy` | Sử dụng khóa đồng bộ `useRef`, vô hiệu trường nhập trong lúc chờ |
| Dialog xác nhận | Popup có thể đóng trước khi callback bất đồng bộ hoàn tất | Chỉ đóng sau khi `await onConfirm` thành công, giữ form và lỗi nếu thất bại |
| Dialog dữ liệu | Người dùng bấm X/Escape trong lúc đang lưu | Chặn đóng khi `aria-busy=true`; sau khi hoàn tất thành công, component cha điều hướng/cập nhật |
| Tạo/gửi hồ sơ | Confirm gửi hồ sơ đóng trước khi có kết quả; lỗi không còn nhìn thấy | Giữ popup cho tới khi server xác nhận; lỗi hiển thị và giữ dữ liệu; khóa submit song song |
| Đính kèm hồ sơ | Chọn file sai định dạng hoặc quá 10 MB có thể tạo bản nháp trước rồi mới báo lỗi | Kiểm tra loại file, dung lượng và tổng số file trước khi gửi tạo nháp |
| Input số | Trường schema `number` bị ép `step=1` dù có thể nhận số thực | Chấp nhận `step=any` cho schema number, giữ số nguyên cho integer |
| Quyết định phê duyệt | Nếu mạng không rõ trạng thái, nhấn lại có nguy cơ phát sinh khóa idempotency khác | Giữ Idempotency-Key theo hồ sơ, phiên bản khóa và thao tác; nút bị khóa khi đang xử lý |
| Nộp kết quả thực thi | Hiển thị toast riêng cho bước upload + bước submit, dễ gây hiểu nhầm đã hoàn thành | Ẩn toast upload trung gian; chỉ xác nhận thành công của luồng xử lý chính |
| Đăng nhập và quên mật khẩu | Nút có thể bấm lặp; `noValidate` làm mất kiểm tra trường bắt buộc | Khóa trước request; sử dụng kiểm tra HTML hợp lệ; giữ lỗi đăng nhập trên form |
| Tạo người dùng | Có mật khẩu dùng chung được điền sẵn | Không đặt sẵn mật khẩu; bắt người quản trị nhập khi tạo người dùng |
| Form người dùng | Có thể đóng popup trong lúc lưu; nhập toàn khoảng trắng | Chuẩn hóa dữ liệu, kiểm tra trường bắt buộc, khóa đóng khi request còn chờ |
| Quy chế | Tạo/sửa/xóa có thể bấm lặp và đóng dialog lúc đang gửi | Khóa đồng bộ trước request và đóng modal sau kết quả thành công |
| Mẫu yêu cầu và quy trình | Submit không đợi server, `alert` gây ngắt mạch thao tác, có thể nhấn lưu hai lần | Lưu bất đồng bộ với khóa, lỗi inline, nút đang lưu, dialog chỉ đóng sau server xác nhận |
| Bật/tắt API tích hợp | Bấm liên tiếp dễ tạo hai yêu cầu toggle và hiển thị sai | Một thao tác tại một thời điểm, chỉ hiển thị thành công khi backend xác nhận |
| Ma trận RBAC | Thao tác bật tắt nhanh hoặc chuyển vai trò có thể chồng request/làm sai UI | Khóa theo vai trò/người dùng và trường quyền, không cập nhật nhầm tab cũ |
| Thông báo | Hai toast cho một hành động khi màn hình có toast riêng và lớp API cũng phát toast | Tùy chọn `toast:false` chỉ ẩn toast trùng; vẫn invalidate cache và phát tín hiệu dữ liệu thay đổi |
| HTTP 200 chứa `success:false` | Giao diện có thể báo thành công dù phản hồi nghiệp vụ ghi nhận thất bại | API chuyển thành lỗi cho mutation không silent, không phát tín hiệu thành công |

## Phương pháp và kết quả kiểm tra

- 100/100 bài test frontend dùng Node test runner đạt, gồm 11 trường hợp mới ở `web_client/e2e/production-interactions.test.mjs`.
- Dùng trình phân tích cú pháp TypeScript quét 65 file `.js`/`.jsx`, không phát hiện lỗi cú pháp. Kiểm kê 285 button, 12 form, 98 input, 59 select, 9 textarea và 20 dialog/modal component. Không phát hiện button nằm trong form có nguy cơ submit ngầm do thiếu thuộc tính `type`.
- 12 file `.js` qua `node --check`.
- 7 stylesheet CSS qua `tinycss2` không có lỗi cấu trúc cấp cao.
- Kiểm tra hash trước và sau: tất cả file ngoài `web_client` giữ nguyên.
- `npm ci` trong môi trường kiểm thử không thành công do không truy cập được registry npm (EAI_AGAIN / cache thiếu). **Do đó không xác nhận được Vite build, ESLint hay kiểm thử trình duyệt Playwright trên môi trường này.**
- Không có quyền truy cập dịch vụ Django / AI / Redis / Supabase trên máy Windows và tài khoản theo vai trò của người dùng. Chưa thể kết luận các luồng E2E với dữ liệu thật PASS.

## Checklist E2E cần chạy trên máy Windows

| ID | Vai trò / trang | Thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| E01 | Client | Đăng nhập đúng/sai/thiếu email | Kiểm tra đầu vào, báo lỗi đúng; không tạo phiên sai; nút không gửi trùng |
| E02 | Admin | Đăng nhập cổng admin | Chỉ đúng role truy cập, phân tách hoàn toàn client và admin |
| E03 | Client | Tạo yêu cầu không đủ trường bắt buộc | Chặn gửi, focus trường sai, giữ dữ liệu |
| E04 | Client | Tạo yêu cầu, lưu nháp 2 lần nhanh | Không sinh hai nháp; giao diện hiện nháp mới mà không F5 |
| E05 | Client | Đính kèm >10 MB, sai định dạng, >5 file | Báo đúng lỗi, không tạo dữ liệu thừa |
| E06 | Client | Mở popup gửi, bấm xác nhận nhiều lần | Chỉ gửi một lần; giữ dialog nếu lỗi; đóng và chuyển chi tiết hồ sơ khi thành công |
| E07 | Approver | Phê duyệt 2 lần, làm mạng chậm | Không có quyết định trùng; chỉ báo thành công khi server xác nhận |
| E08 | Approver | Từ chối / yêu cầu bổ sung | Lý do bắt buộc, ghi nhận đúng trạng thái và timeline |
| E09 | Approver | Tự phê duyệt | Backend chặn, frontend hiển thị lỗi, không bỏ qua cấp |
| E10 | Requester | Chỉnh sửa hồ sơ được yêu cầu bổ sung, gửi lại | Tạo đúng revision, thông báo cập nhật người duyệt |
| E11 | Executor | Nhận việc, báo vướng mắc, nộp kết quả | Đúng phân quyền, lưu kết quả, minh chứng, popup đóng khi thành công |
| E12 | Acceptor | Nghiệm thu / yêu cầu làm lại | Đúng trạng thái, chuyển người thực hiện; nhật ký ghi đầy đủ |
| E13 | Requester/Auditor | Xem hồ sơ hoàn thành & lịch sử | Dữ liệu mới, đúng quyền theo phạm vi |
| E14 | Admin | Tạo user thiếu email/vai trò/phòng ban/mật khẩu | Bị chặn; không tạo tài khoản chưa hợp lệ |
| E15 | Admin | Tạo/chỉnh user, khóa/mở khóa nhanh 2 lần | Không duplicate; modal tự đóng sau thành công; bảng cập nhật |
| E16 | Admin | Cấu hình ma trận RBAC nhiều trường nhanh | Không ghi đè nhầm role; cập nhật UI; phía server kiểm tra quyền |
| E17 | Policy Admin | Tạo/sửa/xóa quy chế | Dữ liệu lưu; chỉ một thông báo, modal đóng và bảng cập nhật |
| E18 | Policy Admin | Tạo/chỉnh mẫu yêu cầu thiếu tên/mã | Báo lỗi trong modal, giữ form; không có alert() trình duyệt |
| E19 | Ops Admin | Bật/tắt API tích hợp | Cập nhật ngay, không đảo trạng thái hai lần, liên quan form bị khóa đúng |
| E20 | Các vai trò | Click thông báo dẫn tới hồ sơ | Điều hướng đúng hồ sơ và tab/tiến trình, cập nhật đã đọc |
| E21 | Mọi cổng | Giữ trang >30 phút, chuyển tab, thử 429/503 | Không vòng lặp request; hiển thị lỗi và nút thử lại; trạng thái đúng |
| E22 | Mọi cổng | Responsive 375px, 768px, 1280px, 1920px | Không tràn, nút không bị che, popup có thể cuộn bên trong |
| E23 | Mọi cổng | Dùng tab/Enter/Escape | Focus, submit, đóng dialog hợp lý; không đóng khi đang xử lý |
| E24 | Mọi cổng | Giả lập mạng chậm 3G, mất mạng khi xác nhận | Không gửi lại mutation tự động; không thông báo hoàn thành nếu chưa rõ trạng thái |

Chạy E01–E13 trước trên tài khoản test tách biệt theo REQUESTER/APPROVER/EXECUTOR/ACCEPTOR/AUDITOR; E14–E19 trên tài khoản Admin/Policy Admin. Sử dụng môi trường staging hoặc dữ liệu thử, không thao tác xóa hay sửa RBAC trên production.

## Hướng dẫn áp dụng và kiểm tra

1. `git switch dangduy && git switch -c fix/production-ui-interactions` (hoặc một tên nhánh riêng chưa tồn tại).
2. Giải nén `EAS_production_frontend_interaction_patch.zip` vào gốc repository, ghi đè `web_client/`.
3. Tại `D:\Đồ án\DATN\web_client`: chạy `npm ci`, `npm test`, `npm run build`, `npm run lint`, sau đó chạy kiểm thử trình duyệt có cấu hình server phù hợp.
4. Chạy `start_frontend_local.cmd`, `start_admin_local.cmd`; làm E01–E24, quan sát Console/Network. Khi gặp lỗi lưu HTTP status, Response body, X-Correlation-ID, ảnh màn hình và dữ liệu thử.
5. Khi kiểm thử ghi dữ liệu thật, cần chạy `start_backend_local.cmd`, `start_ai_local.cmd`, `start_mock_local.cmd`, `start_worker_local.cmd`, Redis và các nguồn cần thiết, rồi xác nhận tất cả health check ở trạng thái thích hợp.

## Giới hạn / chưa nghiệm thu

Không thể tuyên bố hệ thống "không còn bất kỳ lỗi nào" chỉ qua kiểm thử tĩnh và unit tests. Các luồng tích hợp, tình huống hai người dùng đồng thời, kiểm thử trình duyệt responsive trên nhiều thiết bị, bảo mật và hiệu suất thực tế cần được nghiệm thu trên staging. Không chạy migration, thao tác database hoặc thay đổi phân quyền backend trong lần cập nhật frontend này. Những HTTP 429/503 do Redis hoặc backend không thể được giải quyết chỉ bằng sửa giao diện.
