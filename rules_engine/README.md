# Rules Engine — không dùng trong P0

P0 không sử dụng Drools/KIE Server. Luật tuyến được lưu trong `config_release`, giới hạn bởi JSON schema/operator allowlist và được resolve bởi Django domain code. Cách này giảm deployment surface và giữ transaction/authorization trong một boundary dễ kiểm chứng.

Chỉ xem xét external rules engine khi có change request chứng minh:

- Số lượng/quy mô policy vượt khả năng cấu hình hữu hạn.
- Có ownership, versioning, rollback và test vectors rõ ràng.
- Không dùng `eval` hoặc cho policy tự ghi dữ liệu.
- Failure mode đóng an toàn và không phá audit/idempotency.
