-- Rollback 24: bỏ vòng phản hồi của AI.
-- CẢNH BÁO: xóa toàn bộ bộ nhớ ca (eas.ai_feedback) và hàng chờ duyệt điều khoản. Sao lưu trước nếu cần
-- giữ lịch sử: \copy eas.ai_feedback TO 'ai_feedback.csv' CSV HEADER
-- Mã nguồn vẫn chạy khi không có hai bảng này (bỏ qua bộ nhớ ca, không đưa câu lên hàng chờ).

BEGIN;
SELECT eas.lock_security(true);
DROP TABLE IF EXISTS eas.regulation_clause_review;
DROP TRIGGER IF EXISTS ai_feedback_guard ON eas.ai_feedback;
DROP TABLE IF EXISTS eas.ai_feedback;
DROP FUNCTION IF EXISTS eas.guard_ai_feedback();
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;
