# AI Service

Thư mục này chứa mã nguồn của **Module Trợ lý AI (AI Assistant Module)**. 

Phân hệ này được xây dựng độc lập dựa trên FastAPI, giao tiếp với hệ thống chính thông qua REST API. Các chức năng chính bao gồm:
- **OCR (Optical Character Recognition):** Trích xuất thông tin tự động từ hóa đơn, chứng từ đính kèm để giảm thiểu việc nhập liệu thủ công.
- **Tóm tắt (Summarize):** Ứng dụng LLM để tóm tắt các yêu cầu dài hoặc phức tạp, hỗ trợ người phê duyệt ra quyết định nhanh hơn (đặc biệt hữu ích trên giao diện di động).
- **Phát hiện bất thường (Anomaly Detection):** Chấm điểm rủi ro (Risk Scoring) và tự động gắn cờ cảnh báo đối với các yêu cầu có dấu hiệu bất thường (ví dụ: chi tiêu vượt mức).
- **Tự động phê duyệt (Auto-Approve):** Thay mặt hệ thống duyệt ngay các yêu cầu có rủi ro thấp (ví dụ: mượn phòng họp, nghỉ phép ngắn ngày).
