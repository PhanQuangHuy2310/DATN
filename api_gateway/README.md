# Edge/API Gateway

P0 chỉ cần reverse proxy/TLS termination được cấu hình theo môi trường. Authorization nghiệp vụ vẫn nằm trong Django; proxy không được coi là nguồn quyền.

Yêu cầu tối thiểu trước production:

- TLS, request-size limit, timeout và rate limit cho login/upload.
- Forwarded-header allowlist và correlation ID.
- Không log cookie, Authorization header, query token hoặc payload nhạy cảm.
- Maintenance mode và health routing theo runbook.
- Cấu hình được pin/version; không dùng dashboard thủ công làm nguồn duy nhất.

Kong/service mesh không cần cho P0 nếu một reverse proxy đáp ứng các kiểm soát trên.
