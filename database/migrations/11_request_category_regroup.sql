-- Regroup request types into 10 categories, apply approved weights and
-- approval levels (= max approvers of the published route), rename, and
-- deactivate 8 duplicate types (history kept). Source: api_core/catalog/catalog_v2.json
-- Rollback: database/migrations/rollback/11_request_category_regroup_rollback.sql
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SET LOCAL ROLE eas_migration;

ALTER TABLE eas.request_type DROP CONSTRAINT request_type_category_valid;

UPDATE eas.request_type rt
SET name = v.name, category = v.category, risk_weight = v.risk_weight,
    approval_level = v.approval_level, is_active = v.is_active
FROM (VALUES
  ('ADVANCE_LARGE', 'Tạm ứng dự án lớn (>50tr)', 'FINANCE', 4, 3, true),
  ('ADVANCE_MEDIUM', 'Tạm ứng chi phí (10-50tr)', 'FINANCE', 3, 2, true),
  ('ADVANCE_SMALL', 'Tạm ứng chi phí (<10tr)', 'FINANCE', 2, 2, true),
  ('BUDGET_REALLOCATION', 'Điều chuyển & bổ sung ngân sách liên bộ phận', 'FINANCE', 5, 5, true),
  ('EQUIPMENT', 'Mua sắm thiết bị / tài sản', 'FINANCE', 3, 3, true),
  ('EXPENSE_CLAIM', 'Thanh toán chi phí', 'FINANCE', 3, 3, true),
  ('PURCHASE_REQUEST', 'Đề nghị mua sắm', 'FINANCE', 3, 3, true),
  ('REFUND_COMPENSATION', 'Hoàn tiền / Đền bù', 'FINANCE', 2, 1, true),
  ('REIMBURSEMENT', 'Quyết toán tạm ứng', 'FINANCE', 2, 2, true),
  ('SAAS_LICENSE_BUY', 'Mua bản quyền phần mềm mới', 'FINANCE', 3, 3, true),
  ('SUPPLIER_ONBOARDING', 'Thẩm định & phê duyệt nhà cung cấp mới', 'FINANCE', 3, 3, true),
  ('TAX_INVOICE_ISSUE', 'Phát hành / điều chỉnh hóa đơn VAT', 'FINANCE', 1, 1, true),
  ('VENDOR_PAYMENT', 'Thanh toán Hợp đồng Vendor', 'FINANCE', 5, 3, true),
  ('ACCESS', 'Cấp tài khoản & quyền truy cập', 'RESOURCE', 2, 2, true),
  ('LAPTOP_PROVISION', 'Cấp máy tính / thiết bị làm việc', 'RESOURCE', 2, 1, true),
  ('OFFICE_SUPPLIES', 'Cấp văn phòng phẩm', 'RESOURCE', 1, 1, true),
  ('ACCESS_FACILITY', 'Cấp thẻ ra vào', 'FACILITY', 2, 2, true),
  ('EQUIPMENT_BORROW', 'Mượn thiết bị / đồ dùng', 'FACILITY', 2, 2, true),
  ('ROOM_BOOKING', 'Đặt phòng họp', 'FACILITY', 1, 1, true),
  ('VISITOR_SECURITY_PASS', 'Thẻ an ninh khách & đối tác ra vào', 'FACILITY', 1, 1, true),
  ('BUSINESS_TRIP', 'Đăng ký đi công tác', 'HR', 3, 3, true),
  ('EMPLOYEE_ONBOARDING', 'Tiếp nhận nhân viên mới', 'HR', 3, 2, true),
  ('INTERNAL_TRANSFER', 'Điều chuyển nội bộ', 'HR', 3, 3, true),
  ('RECRUITMENT_REQ', 'Yêu cầu tuyển dụng nhân sự', 'HR', 4, 4, true),
  ('RESIGNATION', 'Thôi việc / Bàn giao', 'HR', 4, 3, true),
  ('TRAINING_COURSE', 'Đăng ký đào tạo & chứng chỉ nghề nghiệp', 'HR', 2, 2, true),
  ('ATTENDANCE_ADJUSTMENT', 'Điều chỉnh chấm công', 'TIME', 1, 1, true),
  ('LEAVE', 'Nghỉ phép', 'TIME', 1, 2, true),
  ('LEAVE_SPECIAL', 'Nghỉ phép đặc biệt', 'TIME', 2, 3, true),
  ('OVERTIME_REQ', 'Đăng ký làm thêm giờ (OT)', 'TIME', 2, 1, true),
  ('WFH_REQ', 'Làm việc từ xa (WFH)', 'TIME', 1, 1, true),
  ('DATA_UAT_EXPORT', 'Trích xuất dữ liệu / UAT', 'IT', 3, 2, true),
  ('FEATURE_RELEASE', 'Feature Request / Release', 'IT', 3, 2, true),
  ('IT_SUPPORT', 'Yêu cầu hỗ trợ IT', 'IT', 1, 1, true),
  ('PROD_DATA_ACCESS', 'Cấp quyền Dữ liệu nhạy cảm/Server', 'IT', 5, 3, true),
  ('SECURITY_INCIDENT_HOTFIX', 'Khắc phục sự cố bảo mật & Hotfix khẩn cấp', 'IT', 5, 5, true),
  ('SERVER_FIREWALL', 'Cấp Server / Firewall', 'IT', 3, 3, true),
  ('CONTRACT_APPROVAL', 'Duyệt hợp đồng', 'LEGAL', 5, 3, true),
  ('NDA_PRIVACY_CLEARANCE', 'Thẩm định NDA & chia sẻ dữ liệu đối tác', 'LEGAL', 2, 2, true),
  ('FLASH_SALE_VOUCHER', 'Flash Sale / Voucher', 'SALES', 4, 2, true),
  ('MARKETING_CAMPAIGN', 'Ngân sách chiến dịch Marketing & Sự kiện', 'SALES', 4, 4, true),
  ('SPECIAL_DISCOUNT', 'Phê duyệt chiết khấu thương mại đặc biệt', 'SALES', 3, 3, true),
  ('ASSET_DISPOSAL', 'Thanh lý & hủy tài sản cố định', 'ADMIN', 4, 4, true),
  ('FACILITY_REPAIR', 'Sửa chữa sự cố văn phòng', 'ADMIN', 2, 1, true),
  ('WAREHOUSE_TRANSFER', 'Luân chuyển kho', 'ADMIN', 3, 1, true),
  ('ASSET_PURCHASE', 'Mua sắm tài sản phòng ban', 'FINANCE', 4, 3, false),
  ('SOFTWARE_ACCESS', 'Cấp tài khoản / VPN', 'RESOURCE', 2, 2, false),
  ('ROOM_STUDIO', 'Mượn phòng họp / Studio', 'FACILITY', 1, 1, false),
  ('ROOM_VEHICLE', 'Mượn phòng họp / Xe công vụ', 'FACILITY', 1, 1, false),
  ('LEAVE_ANNUAL', 'Nghỉ phép dưới 3 ngày', 'TIME', 1, 1, false),
  ('LEAVE_LONG', 'Nghỉ phép từ 3 ngày', 'TIME', 3, 2, false),
  ('OVERTIME_APPROVAL', 'Đăng ký làm thêm giờ (OT)', 'TIME', 2, 1, false),
  ('FACILITY_MAINTENANCE', 'Sửa chữa cơ sở vật chất', 'ADMIN', 2, 1, false)
) AS v(code, name, category, risk_weight, approval_level, is_active)
WHERE rt.code = v.code;

DO $check$
BEGIN
  IF EXISTS (SELECT 1 FROM eas.request_type WHERE category <> ALL(ARRAY['FINANCE', 'RESOURCE', 'FACILITY', 'WORK', 'HR', 'TIME', 'IT', 'LEGAL', 'SALES', 'ADMIN'])) THEN
    RAISE EXCEPTION 'Some request types were not mapped to the 10 new categories';
  END IF;
END
$check$;

ALTER TABLE eas.request_type ADD CONSTRAINT request_type_category_valid
  CHECK (((category)::text = ANY ((ARRAY['FINANCE'::character varying, 'RESOURCE'::character varying, 'FACILITY'::character varying, 'WORK'::character varying, 'HR'::character varying, 'TIME'::character varying, 'IT'::character varying, 'LEGAL'::character varying, 'SALES'::character varying, 'ADMIN'::character varying])::text[])));

UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;

SELECT category, count(*) FILTER (WHERE is_active) AS active, count(*) FILTER (WHERE NOT is_active) AS inactive
FROM eas.request_type GROUP BY category ORDER BY category;
