-- =============================================================================
-- Rollback for repair_stuck_requests.sql ([M2])
-- =============================================================================
-- Lưu ý: repair_stuck_requests.sql chỉ sửa chữa tính nhất quán dữ liệu (kích hoạt
-- bước WAITING bị treo cho các hồ sơ PENDING_APPROVAL và đóng các sla_stage mồ côi
-- của hồ sơ đã kết thúc). File rollback này là no-op an toàn để đảm bảo quy ước
-- mỗi file trong database/migrations/ đều có file rollback tương ứng.
-- =============================================================================

BEGIN;
SELECT 1;
COMMIT;

