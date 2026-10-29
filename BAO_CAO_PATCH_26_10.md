# Báo cáo patch EAS 26/10/2026

| Mục | Thực hiện | Xác minh |
|---|---|---|
| GET /requests + /ops/requests từng báo HTTP 500 | Ép kiểu null params, thêm tìm kiếm server-side | SQL placeholder/request 26=26, Ops 11=11; chưa DB live |
| Notifications HTTP 500 | Ép kiểu boolean `unread` rõ ràng | Cú pháp Python; chưa DB live |
| Filter optional ở báo cáo và policy | Ép kiểu text/uuid | Cú pháp Python; chưa DB live |
| Mật khẩu hiện/ẩn | PasswordField dùng chung 3 vị trí | Kiểm tra mã & cú pháp JSX |
| Mật khẩu 400 | Client-side validation, hiển thị lỗi 400/401 chính xác hơn | Chưa live E2E |
| Danh sách dài | Paginator server/client phù hợp endpoint, 10/20/50 | Kiểm tra mã tĩnh |
| Responsive Stitch | Bố cục dashboard, card, sidebar, table mobile, desktop | Chưa render browser |
| Scroll đến tác vụ | Navigation, Policy editor, detail tabs, pagination | Kiểm tra mã tĩnh |
| Git DLL >100 MB | `.gitignore` bổ sung `.venv-ai/` | Chưa làm sạch lịch sử local `dangduy` |
| Worker, AI Auth, Storage | Không sửa bừa các secret/role | Cần kiểm thử môi trường Windows |

**Kết quả test tĩnh:** 16/16 unittest thuộc `connection_tests` PASS; TypeScript JSX parser báo 0 lỗi; `compileall` Python PASS. **Không gọi Supabase và không chạy Vite build/browser trong container này.**
