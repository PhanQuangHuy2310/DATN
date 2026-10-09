# Enterprise Approval System (EAS)

EAS là hệ thống quản lý phê duyệt nội bộ cho một doanh nghiệp. Baseline P0 gồm ba loại hồ sơ:

- `LEAVE` — vòng đời A: gửi và phê duyệt.
- `ACCESS` — vòng đời B: phê duyệt và ghi nhận thực hiện.
- `EQUIPMENT` — vòng đời C: phê duyệt, thực hiện và nghiệm thu.

## Trạng thái trung thực

| Thành phần | Trạng thái |
|---|---|
| SRS/thiết kế/API/test plan | Có baseline v2.0; KD01–KD08 còn cần người có thẩm quyền ký |
| Database | SQL v2.0.1, 30 bảng; verification PASS trên PGlite và Supabase thật bằng read-only check |
| Backend | Đang triển khai foundation Django; chưa hoàn tất toàn bộ command A/B/C |
| Frontend/worker/storage/scanner | Chưa đủ để UAT end-to-end |
| Acceptance test TC001–TC100 | `NOT RUN` trừ bằng chứng DB riêng được ghi rõ |
| Production readiness | `NO-GO` |

Không dùng số lượng tài liệu hoặc sơ đồ để suy ra hệ thống đã triển khai. Xem [chỉ mục hồ sơ](docs/README.md) và [báo cáo thẩm định](docs/08_Bao_cao_tham_dinh_va_lo_trinh_thuong_mai.md).

## Kiến trúc P0

> Cập nhật thực thi 09/10/2026: stack development năm container, runtime role, active release, browser E2E và logical restore đã PASS. Xem [biên bản runtime/E2E/DR](docs/13_Bien_ban_kiem_chung_runtime_E2E_DR.md). Production vẫn `NO-GO` do credential/Git containment, Storage private và các acceptance/UAT còn mở.

P0 dùng modular monolith:

```text
React Web -> Django API/domain -> PostgreSQL (Supabase)
                            \-> private object storage + scanner
                            \-> worker dùng cùng domain code
```

AI auto-approve, OCR/risk scoring, Drools, Elasticsearch, mobile native, OPA, workflow builder tổng quát, approval song song và tích hợp ERP tự động không thuộc P0. Chúng chỉ được đưa vào roadmap bằng change request có business case và test tương ứng.

## Chạy backend foundation

1. Khi chạy độc lập, sao chép `api_core/.env.example` thành `api_core/.env`, thay toàn bộ placeholder và nạp file bằng process manager; Django không tự đọc file `.env`.
2. Dùng database login runtime chỉ thuộc nhóm `eas_api`; không dùng `postgres`, owner hoặc service-role key.
3. Kiểm tra cấu hình trước khi khởi động: `python scripts/validate_env.py --file api_core/.env --profile api`.
4. Cài và kiểm tra:

```bash
python -m venv .venv
.venv/Scripts/pip install -r api_core/requirements.txt
set EAS_ENV=test
.venv/Scripts/python manage.py test
```

Chạy local bằng Docker sau khi Docker daemon hoạt động. Docker Compose chỉ đọc `.env` ở thư mục gốc, không đọc `api_core/.env`:

```bash
./scripts/manage_env.ps1 init
# Thay mọi placeholder trong .env bằng credential đã rotate, sau đó:
./scripts/manage_env.ps1 validate
docker compose --env-file .env up --build
```

Kiểm tra nhanh mà không hiển thị secret: `./scripts/manage_env.ps1 status`. Kiểm tra toàn bộ template trong CI: `./scripts/manage_env.ps1 validate-templates`.

Hai frontend mặc định gọi API cùng origin qua Nginx. Khi chạy Vite riêng, đặt `VITE_API_BASE_URL=http://127.0.0.1:8000`; không thêm hậu tố `/api` hoặc `/api/v1` vì client đã truyền đường dẫn API đầy đủ.

Endpoints nền tảng:

- `GET /health/live` — process liveness, không truy cập database.
- `GET /health/ready` — kiểm schema EAS, ba request type, active release và runtime DB role.
- `GET /api/v1/meta/request-types` — metadata ba loại hồ sơ, không trả policy JSON hoặc dữ liệu cá nhân.

## An toàn credential

- Không commit `.env`, database password, `sb_secret_*`, service-role key hoặc personal access token.
- Frontend chỉ gọi Django API trong P0; không chứa privileged Supabase key.
- Các `.env` cũ đã từng xuất hiện trong Git history phải được rotate. Việc thêm `.gitignore` không vô hiệu credential cũ.
- Chỉ rewrite Git history sau khi có backup, nhánh được chỉ định và kế hoạch phối hợp với mọi clone.

## Nguồn tài liệu

- [Hồ sơ dự án](docs/README.md)
- [Database package](database/EAS_Supabase_SQL/README_VI.md)
- [Biên bản kiểm chứng Supabase](docs/09_Bien_ban_kiem_chung_Supabase.md)
- [Test case và RTM](docs/testing/01_test_case_and_rtm.md)
