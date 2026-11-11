# Access Control (IDOR) Security Report

## Status: PASS

Trạng thái trước khắc phục: **PASS**. Ngày kiểm toán: 01/11/2026, nghiệm thu: 02/11/2026. Kế hoạch tổng: [EAS-PLAN-2026-11-01-01](../../plans/completed/2026-11-01_vibe_check_security_audit.md). Kế hoạch sửa: [ACCESS_CONTROL_PLAN.md](../plans/ACCESS_CONTROL_PLAN.md).

## Findings

Rà toàn bộ route có ID tài nguyên:

| Route | Kiểm soát sở hữu |
|---|---|
| `GET /requests/{id}`, `/revisions*`, `/history`, `/audit` | `requester_id = actor` HOẶC participant chưa bị thu hồi (khi không phải DRAFT) HOẶC AUDITOR đúng phạm vi phòng ban/loại; không thấy → 404 |
| `GET /attachments/{id}`, `/download` | Cùng vị từ; thêm `scan_state='CLEAN'`; file nháp chỉ requester tải được |
| `PATCH/DELETE` nháp, tệp nháp | `FOR UPDATE` rồi so `requester_id == actor.id` → 403, cộng `_authorize` theo phạm vi role |
| Quyết định duyệt/thực thi/nghiệm thu | Khóa bước hiện hành, so người được giao + `_authorize` |
| `PATCH /notifications/{id}` | `WHERE id=%s AND recipient_id=%s` |
| `/admin/{kind}/{id}` | OPS_ADMIN GLOBAL; chặn tự sửa quyền quản trị của chính mình |
| `/config-releases/{id}` | POLICY_ADMIN đúng phạm vi loại |
| `/mock/*` | Danh sách theo `RESOURCE_ROLES` |

Xác thực và sở hữu là hai bước tách biệt. Không phát hiện IDOR.

## What's at risk

Không có rủi ro mới. Lưu ý thiết kế: endpoint đọc trả 404 (thay vì 403) khi không có quyền để không lộ sự tồn tại của tài nguyên. Đây là chủ đích, không phải lỗi.

## What's already secure

Toàn bộ bảng trên. Vị từ hiển thị được dùng thống nhất giữa danh sách, chi tiết, tệp đính kèm và audit.

## Recommendations

Không cần thay đổi. Khi thêm route có ID, tái sử dụng vị từ hiển thị hiện có.

## Verification results

- [x] Mọi route có ID kiểm tra sở hữu/phạm vi
- [x] Kiểm tra có ở cả GET và PUT/PATCH/DELETE
- [x] Sai sở hữu → 403 (ghi) / 404 (đọc, chủ đích)
- [x] Xác thực và sở hữu tách biệt
