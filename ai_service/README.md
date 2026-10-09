# AI Service — P1, chưa triển khai

AI không nằm trên đường quyết định hoặc tiêu chí nghiệm thu P0. Thư mục này chỉ giữ chỗ cho change request tương lai.

Nguyên tắc nếu P1 được duyệt:

- Chỉ tóm tắt/gợi ý, không auto-approve hoặc thay người có thẩm quyền.
- Output phải được đánh dấu là AI-generated và không được dùng làm nguồn sự thật.
- Có DPIA/threat model, data minimization, prompt-injection test và human review.
- Không gửi tệp/dữ liệu cá nhân tới nhà cung cấp ngoài khi KD06/hợp đồng chưa chấp thuận.
- Có cost cap, telemetry, kill switch và fallback không AI.

Không đưa service này vào Compose hoặc sơ đồ As-is của P0.
