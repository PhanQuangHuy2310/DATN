# Changelog: Nâng Cấp Chuẩn Production-Ready & SonarQube (docs/2.md)

**Ngày ghi nhận:** 24/10/2026  
**Phiên bản / Nhánh:** `origin/huy`  
**Tác giả:** Tech Lead & Autonomous IT Department  
**Phạm vi:** Backend (`api_core`), Dịch vụ Trí tuệ Nhân tạo (`ai_service`), Giao diện Người dùng (`web_client`), Cấu hình Container, Kiểm thử và CI/CD.

---

### 1. Tính năng & Cải tiến Mới (Features & Enhancements)
- **Tối ưu OCR Lazy Singleton Cache:** Chuyển đổi mô hình PaddleOCR trong `ai_service/routers/ocr.py` sang mô hình Singleton khởi tạo trễ (lazy initialization) với Thread Lock, giúp giảm ~800MB RAM khi hệ thống khởi động.
- **Observability & Correlation Tracing:** Bổ sung header `X-Correlation-ID` xuyên suốt các giao dịch giữa `api_core` và `ai_service`, phục vụ trace log và debug phân tán.
- **Giao diện Đa vai trò (RBAC) & AI UX:** Cung cấp hệ thống Perspective Tabs trên `web_client` cho cả 7 vai trò (`REQUESTER`, `APPROVER`, `EXECUTOR`, `ACCEPTOR`, `OPS_ADMIN`, `POLICY_ADMIN`, `AUDITOR`) và tích hợp các nút trợ lý AI trực quan.
- **Cấu hình SonarQube & Coverage:** Thiết lập `sonar-project.properties` và cập nhật CI/CD `.github/workflows/ci.yml` hỗ trợ nhánh `main`, `huy`, `dat`, xuất file `coverage.xml` tự động.

### 2. Tái Cấu Trúc Mã Nguồn (Refactoring & Code Quality)
- **SonarQube Cognitive Complexity (<= 15):**
  - Tách các hàm con độc lập cho `reassign_actor` trong `api_core/workflow/ops_service.py`.
  - Tách các hàm kiểm tra `route_rules` và actors trong `api_core/domain/validation.py`.
  - Đơn giản hóa điều kiện so khớp trong `api_core/domain/routing.py`.
  - Phân tách logic thực thi, tạo bản nháp, nghiệm thu trong `api_core/workflow/service.py`.
- **Worker Resilience & Graceful Shutdown:**
  - Bắt tín hiệu `SIGTERM` và `SIGINT` trong `run_outbox_worker.py` để kết thúc an toàn.
  - Gọi `close_old_connections()` định kỳ và xử lý lỗi mềm dẻo với `logger.exception`.
- **Phòng chống Tràn Bộ Nhớ Báo Cáo:**
  - Bổ sung `LIMIT 100000` cho câu truy vấn metric tại `api_core/workflow/reporting.py`.

### 3. Gia Cố Bảo Mật (Security Hardening)
- **Web Client Nginx:** Giới hạn kích thước tải lên `client_max_body_size 10m;` và thiết lập timeout proxy chuẩn.
- **Docker Non-Root User:** Tạo user `aiuser` (UID 10001) trong `ai_service/Dockerfile`.
- **Docker Compose:** Thiết lập `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]`, đưa Elasticsearch vào profile `search-optional` và ràng buộc cổng cục bộ `127.0.0.1:9200:9200`.

### 4. Kết Quả Kiểm Thử (Verification)
- 108 Django Unit/Integration tests: PASS.
- 11 AI Integration tests: PASS.
- 4 Logger security tests: PASS.
- 86 SQL assertions: PASS.
- 0 lint errors, 0 syntax errors, 100% Quality Gates PASS.
