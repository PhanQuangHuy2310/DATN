-- Rollback 25: bỏ bảng bad case trong CSDL (AI quay về danh mục trong ai_service/data/bad_case_catalog.json).
-- CẢNH BÁO: xóa mọi bad case AI đã học và lý do thu hồi đã phân tích. Sao lưu trước nếu cần:
--   \copy eas.bad_case TO 'bad_case.csv' CSV HEADER
--   \copy eas.bad_case_evidence TO 'bad_case_evidence.csv' CSV HEADER
-- Mã nguồn vẫn chạy khi không có hai bảng này (chỉ dùng 12 bad case có sẵn, không học bad case mới).

BEGIN;
SELECT eas.lock_security(true);
DROP TRIGGER IF EXISTS bad_case_evidence_guard ON eas.bad_case_evidence;
DROP TABLE IF EXISTS eas.bad_case_evidence;
DROP TRIGGER IF EXISTS bad_case_guard ON eas.bad_case;
DROP TABLE IF EXISTS eas.bad_case;
DROP FUNCTION IF EXISTS eas.guard_bad_case_evidence();
DROP FUNCTION IF EXISTS eas.guard_bad_case();
UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;
