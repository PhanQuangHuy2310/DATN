# CORS Security Report

## Status: PASS

Trạng thái trước khắc phục: **LOW**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [CORS_PLAN.md](../plans/CORS_PLAN.md).

## Findings

- Django và nginx không phát header `Access-Control-*` (curl với `Origin: https://evil.example`, cả GET lẫn preflight OPTIONS) → chỉ same-origin.
- ai_service (`main.py`): allowlist cụ thể (không `*`, không phản chiếu Origin), nhưng `allow_credentials=True` và `allow_headers=["*"]` không cần thiết cho dịch vụ server-to-server xác thực bằng header.

## What's at risk

Thấp: allowlist chỉ gồm localhost. Credentials + header tùy ý mở rộng bề mặt nếu allowlist bị cấu hình rộng ra sau này.

## What's already secure

Không wildcard; method tường minh `GET, POST, OPTIONS`; ai_service chỉ bind localhost.

## Recommendations

Tắt credentials, liệt kê header thực dùng.

## Verification results

- [x] Origin là allowlist tường minh
- [x] Không wildcard trong mã và trong header thực tế
- [x] Không phản chiếu Origin ngoài allowlist
- [x] Không có credentials (đã tắt)
- [x] Method chỉ gồm những gì API dùng
