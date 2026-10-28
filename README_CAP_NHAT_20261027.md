# DATN — bàn giao mã nguồn cập nhật 27/10/2026

**Đọc đầu tiên:** [Phân tích tài liệu & ma trận UC](docs/PHAN_TICH_NGHIEP_VU_VA_KET_QUA_CODE_20261027.md) và [kết quả kiểm thử](KIEM_THU_BAN_CAP_NHAT_20261027.md). Báo cáo Nhóm 07 gốc: `docs/source_materials/Report_DATN_CNTT_Nhom07_v1.0.docx`. Giữ các hướng dẫn nền tảng trong [START_HERE.md](START_HERE.md) và [hướng dẫn công bố quy chế](HUONG_DAN_CONG_BO_QUY_CHE_VA_CAP_QUYEN_20261027.md).

Bản nâng cấp này **không khởi tạo dự án mới và không xoá code cũ**. Nó gia cố workflow list đúng revision/state/scope, hợp đồng payload frontend–backend, đăng nhập rate-limit và idle timeout, cùng Flutter P1 quick-client; bổ sung test và truy vết tài liệu.

**Giới hạn rõ ràng:** Không có bằng chứng đã chạy Django E2E trên Supabase, không kiểm chứng NPM production build, Flutter build, storage scanner/worker, UAT TC001–TC100. Bản bàn giao **không thể tuyên bố hoàn thành 100% theo phạm vi rộng của báo cáo**. Ba loại LEAVE/ACCESS/EQUIPMENT là P0; mở rộng 18 loại theo plan và AI/mobile hoàn thiện là luồng nghiệp vụ phải được duyệt, test riêng.

**Bảo mật bản giao:** không đóng gói các file `.env` thật của ZIP cũ, không tự kết nối hoặc sửa Supabase, không công bố policy hoặc tự tạo người dùng/quyền. Hãy tự sao chép các file `*.env.example` vào `.env` rồi điền credential trên máy cá nhân/secret manager.

```powershell
# Terminal 1 — tại DATN trên Windows
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r api_core\requirements.txt
# Kiểm thử Django dùng profile cô lập; KHÔNG chạy test vào DB sản xuất.
$env:EAS_ENV = "test"
.\.venv\Scripts\python.exe manage.py test
Remove-Item Env:EAS_ENV
# Cấu hình kết nối chỉ dành cho môi trường dev/UAT được phép truy cập.
.\.venv\Scripts\python.exe connect_database.py
.\.venv\Scripts\python.exe connect_database.py --runserver

# Terminal 2
cd web_client
npm ci
npm test
npm run build
npm run dev
```

Ghi chú: Supabase cần account database runtime `eas_api`, đúng host/pooler/port/SSL, active release và membership. Khi chưa công bố hoặc chưa cấp REQUESTER, biểu mẫu sẽ báo blocker đúng thay vì tự tạo đơn. Để kiểm tra phần offline, chạy từ gốc `python -m pytest -q tests_report tests_business connection_tests tests_readiness` và `cd web_client && npm test`.
