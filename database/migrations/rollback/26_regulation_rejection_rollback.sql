-- Rollback 26: bỏ bảng quy định bị trả lại.
-- CẢNH BÁO: xóa danh sách bản bị trả lại và lỗi kèm theo. Sao lưu trước nếu cần:
--   \copy eas.regulation_rejection TO 'regulation_rejection.csv' CSV HEADER
-- Mã nguồn vẫn chạy khi không có bảng này: lỗi văn bản vẫn bị chặn khi ban hành, nhưng khi AI học thất bại thì
-- văn bản mới được giữ nguyên như trước (không quay hiệu lực, không lưu danh sách lỗi).

BEGIN;
SELECT eas.lock_security(true);
DROP TRIGGER IF EXISTS regulation_rejection_guard ON eas.regulation_rejection;
DROP TABLE IF EXISTS eas.regulation_rejection;
DROP FUNCTION IF EXISTS eas.guard_regulation_rejection();
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;
