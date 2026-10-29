# EAS — Hotfix `/health/ready` 503 trên schema 32 bảng / 7 loại chưa có release

## Kết quả chẩn đoán từ máy bạn

- `eas` có **32 bảng**, bao gồm 30 bảng nghiệp vụ. `role`, `lifecycle` là bảng hỗ trợ hợp lệ.
- **10** loại đơn `is_active=true`; **7** loại mở rộng thiếu `active_release_id`.
- Ba loại P0 `LEAVE (A)`, `ACCESS (B)`, `EQUIPMENT (C)` có release hợp lệ theo kết quả chẩn đoán.

### Hai lỗi trong readiness cũ

1. `SELECT count(*) ... = 30` sai khi schema có bảng bổ sung. Thay bằng kiểm tra tập hợp **30 tên bảng bắt buộc**.
2. Readiness lấy tính hợp lệ **tất cả** loại `active` làm điều kiện chặn toàn bộ Backend. Với dữ liệu seed mở rộng chưa publish, những luồng P0 hoàn toàn chạy được vẫn bị đánh HTTP 503. **Readiness lõi** chỉ chặn khi thiếu loại P0 hoặc P0 chưa có release (nếu `EAS_REQUIRE_ACTIVE_RELEASES=true`); loại mở rộng chưa cấu hình được cảnh báo trong trường `catalog`, nhưng vẫn **bị chặn ở Backend khi tạo/gửi đơn**.

## Áp dụng

1. Sao lưu project và commit code hiện tại trước khi sửa.
2. Giải nén patch **vào thư mục cha chứa `DATN`**, ví dụ `D:\Đồ án`, để giữ đúng cấu trúc.
3. Giữ `EAS_REQUIRE_ACTIVE_RELEASES=true` trong `.env.database`.
4. Đảm bảo `EAS_REQUIRE_FULL_CATALOG_READY=false` (mặc định trong patch), hoặc bổ sung dòng này ở `.env.database` nếu trước đó đã bật chế độ strict.
5. Tắt Backend bằng Ctrl+C rồi chạy lại `start_backend_local.cmd`.

```bat
cd /d "D:\Đồ án\DATN"
.\.venv\Scripts\python.exe -m unittest discover -s tests_readiness -p "test_*.py" -v
.\.venv\Scripts\python.exe diagnose_readiness_readonly.py
curl.exe --noproxy "*" http://127.0.0.1:8000/health/ready
```

Với kết quả bạn vừa gửi, dự kiến HTTP 200 nếu các check khác tiếp tục đạt. Ví dụ rút gọn:

```json
{
  "status": "ready",
  "checks": {
    "schema_has_30_tables": true,
    "request_types_match_p0": true,
    "p0_active_types_configured": true
  },
  "catalog": {
    "status": "needs_configuration",
    "active_type_count": 10,
    "unconfigured_active_type_count": 7,
    "all_active_types_configured": false
  }
}
```

`checks` thực tế còn kiểm tra quyền kết nối, nguồn mock, Redis, Storage và ClamAV. **Không sửa dữ liệu Supabase, không gán release giả, không tự công bố hoặc mở loại yêu cầu**.

### Chế độ nghiêm ngặt (tùy chọn)

`EAS_REQUIRE_FULL_CATALOG_READY=true`: mọi loại `request_type.is_active=true` phải có release đã `PUBLISHED`. Đây là chế độ phù hợp trước khi chứng nhận toàn bộ danh mục dùng được. Nếu chưa cấu hình bảy loại, chế độ nghiêm ngặt cố ý trả 503.

### Muốn vận hành tất cả 10/18 loại đơn?

Policy Admin phải cấu hình, kiểm tra và publish `config_release` tương ứng từng loại với đúng `type_id`, `lifecycle`, JSON Schema, actor bindings, route rules và SLA. Backend vẫn kiểm tra quyền `REQUESTER`, phạm vi role, SoD và chỉ cho phép sử dụng release hợp lệ. Không dùng HTTP 200 từ health để khẳng định 7 loại đó đã xong.

### Cần kiểm tra trực tiếp trên Backend

Dùng `diagnose_readiness_readonly.py` để xem mã nào chưa cấu hình. `/health/ready` chỉ trả số lượng còn thiếu, tránh lộ danh mục nội bộ tới người chưa đăng nhập.
