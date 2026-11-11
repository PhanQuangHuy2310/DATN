# SQL Injection Security Report

## Status: PASS

Trạng thái trước khắc phục: **PASS**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [SQL_INJECTION_PLAN.md](../plans/SQL_INJECTION_PLAN.md).

## Findings

- Mọi `cursor.execute` trong `api_core`, `ai_service`, scripts, management commands dùng placeholder `%s`/`%(name)s`.
- SQL dựng động: `administration/service.py:237-250, 464, 609-612` (tên bảng/cột lấy từ dict `TABLES` cố định, khóa `kind` được kiểm `kind in TABLES` ở view; mệnh đề lọc từ allowlist), `mock_sources/service.py:328-335` (`spec.relation`, `spec.search_columns` cố định). Giá trị luôn là tham số.
- SQL function: `EXECUTE format('... %I ...')` (định danh được quote). `EXECUTE $operation$...$operation$` chỉ có trong script hồi quy DEV với hằng số.

## What's at risk

Không có.

## What's already secure

Toàn bộ nêu trên; comment `NOSONAR python:S2077` đều kèm allowlist.

## Recommendations

Giữ quy tắc: định danh động chỉ lấy từ allowlist, không bao giờ từ request.

## Verification results

- [x] Mọi truy vấn dùng tham số
- [x] Không nối chuỗi/f-string với dữ liệu người dùng trong SQL
- [x] grep mẫu nguy hiểm chỉ ra các chỗ dùng allowlist đã rà
