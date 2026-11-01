-- Rollback of 11_request_category_regroup.sql: restores the 7 old categories
-- and each type's previous name, weight, approval level and active flag.
-- Run 12's rollback first if migration 12 was applied (new types use new categories).
BEGIN;
SET LOCAL ROLE eas_migration;
ALTER TABLE eas.request_type DROP CONSTRAINT request_type_category_valid;
UPDATE eas.request_type rt
SET name = v.name, category = v.category, risk_weight = v.risk_weight,
    approval_level = v.approval_level, is_active = v.is_active
FROM (VALUES
  ('ACCESS', 'Cấp quyền truy cập hệ thống', 'IT', 3, 2, true),
  ('ACCESS_FACILITY', 'Cấp quyền ra vào', 'FACILITY', 2, 2, true),
  ('ADVANCE_LARGE', 'Tạm ứng dự án lớn (>50tr)', 'FINANCE', 4, 3, true),
  ('ADVANCE_MEDIUM', 'Tạm ứng chi phí (10-50tr)', 'FINANCE', 3, 2, true),
  ('ADVANCE_SMALL', 'Tạm ứng chi phí (<10tr)', 'FINANCE', 2, 2, true),
  ('ASSET_DISPOSAL', 'Thanh lý & hủy tài sản cố định', 'ASSET', 4, 4, true),
  ('ASSET_PURCHASE', 'Mua sắm tài sản phòng ban', 'ASSET', 4, 3, true),
  ('ATTENDANCE_ADJUSTMENT', 'Đi muộn / Về sớm / Quên chấm công', 'HR', 3, 1, true),
  ('BUDGET_REALLOCATION', 'Điều chuyển & bổ sung ngân sách liên bộ phận', 'FINANCE', 5, 5, true),
  ('BUSINESS_TRIP', 'Công tác', 'HR', 3, 3, true),
  ('CONTRACT_APPROVAL', 'Duyệt hợp đồng', 'GENERAL', 5, 3, true),
  ('DATA_UAT_EXPORT', 'Trích xuất dữ liệu / UAT', 'IT', 3, 2, true),
  ('EMPLOYEE_ONBOARDING', 'Onboarding nhân viên', 'HR', 3, 2, true),
  ('EQUIPMENT', 'Mua sắm thiết bị', 'PROCUREMENT', 3, 3, true),
  ('EQUIPMENT_BORROW', 'Mượn thiết bị', 'ASSET', 2, 2, true),
  ('EXPENSE_CLAIM', 'Thanh toán chi phí', 'FINANCE', 3, 3, true),
  ('FACILITY_MAINTENANCE', 'Sửa chữa cơ sở vật chất', 'FACILITY', 2, 1, true),
  ('FACILITY_REPAIR', 'Sửa chữa sự cố văn phòng', 'FACILITY', 2, 1, true),
  ('FEATURE_RELEASE', 'Feature Request / Release', 'IT', 3, 2, true),
  ('FLASH_SALE_VOUCHER', 'Flash Sale / Voucher', 'GENERAL', 4, 2, true),
  ('INTERNAL_TRANSFER', 'Điều chuyển nội bộ & bổ nhiệm nhân sự', 'HR', 3, 3, true),
  ('IT_SUPPORT', 'Yêu cầu hỗ trợ IT', 'IT', 1, 1, true),
  ('LAPTOP_PROVISION', 'Cấp Laptop / Thiết bị', 'ASSET', 3, 1, true),
  ('LEAVE', 'Nghỉ phép thường niên', 'HR', 1, 2, true),
  ('LEAVE_ANNUAL', 'Nghỉ phép dưới 3 ngày', 'HR', 1, 1, true),
  ('LEAVE_LONG', 'Nghỉ phép từ 3 ngày', 'HR', 3, 2, true),
  ('LEAVE_SPECIAL', 'Nghỉ phép đặc biệt', 'HR', 2, 3, true),
  ('MARKETING_CAMPAIGN', 'Ngân sách chiến dịch Marketing & Sự kiện', 'GENERAL', 4, 4, true),
  ('NDA_PRIVACY_CLEARANCE', 'Thẩm định NDA & chia sẻ dữ liệu đối tác', 'GENERAL', 2, 2, true),
  ('OFFICE_SUPPLIES', 'Cấp văn phòng phẩm', 'PROCUREMENT', 1, 1, true),
  ('OVERTIME_APPROVAL', 'Đăng ký làm thêm giờ (OT)', 'HR', 2, 1, true),
  ('OVERTIME_REQ', 'Đăng ký làm thêm giờ (OT)', 'HR', 2, 1, true),
  ('PROD_DATA_ACCESS', 'Cấp quyền Dữ liệu nhạy cảm/Server', 'IT', 5, 3, true),
  ('PURCHASE_REQUEST', 'Đề nghị mua sắm', 'PROCUREMENT', 5, 3, true),
  ('RECRUITMENT_REQ', 'Yêu cầu tuyển dụng nhân sự (Headcount)', 'HR', 4, 4, true),
  ('REFUND_COMPENSATION', 'Hoàn tiền / Đền bù', 'FINANCE', 2, 1, true),
  ('REIMBURSEMENT', 'Hoàn ứng / Thanh toán chi phí', 'FINANCE', 2, 2, true),
  ('RESIGNATION', 'Thôi việc / Bàn giao', 'HR', 4, 3, true),
  ('ROOM_BOOKING', 'Đặt phòng họp', 'FACILITY', 1, 1, true),
  ('ROOM_STUDIO', 'Mượn phòng họp / Studio', 'FACILITY', 1, 1, true),
  ('ROOM_VEHICLE', 'Mượn phòng họp / Xe công vụ', 'FACILITY', 1, 1, true),
  ('SAAS_LICENSE_BUY', 'Mua bản quyền phần mềm mới', 'IT', 3, 3, true),
  ('SECURITY_INCIDENT_HOTFIX', 'Khắc phục sự cố bảo mật & Hotfix khẩn cấp', 'IT', 5, 5, true),
  ('SERVER_FIREWALL', 'Cấp Server / Firewall', 'IT', 3, 3, true),
  ('SOFTWARE_ACCESS', 'Cấp tài khoản / VPN', 'IT', 2, 2, true),
  ('SPECIAL_DISCOUNT', 'Phê duyệt chiết khấu thương mại đặc biệt', 'GENERAL', 3, 3, true),
  ('SUPPLIER_ONBOARDING', 'Thẩm định & phê duyệt nhà cung cấp mới', 'PROCUREMENT', 3, 3, true),
  ('TAX_INVOICE_ISSUE', 'Phát hành / điều chỉnh hóa đơn VAT', 'FINANCE', 1, 1, true),
  ('TRAINING_COURSE', 'Đăng ký đào tạo & chứng chỉ nghề nghiệp', 'HR', 2, 2, true),
  ('VENDOR_PAYMENT', 'Thanh toán Hợp đồng Vendor', 'FINANCE', 5, 3, true),
  ('VISITOR_SECURITY_PASS', 'Thẻ an ninh khách & đối tác ra vào', 'FACILITY', 1, 1, true),
  ('WAREHOUSE_TRANSFER', 'Luân chuyển kho', 'GENERAL', 3, 1, true),
  ('WFH_REQ', 'Làm việc từ xa (WFH)', 'HR', 1, 1, true)
) AS v(code, name, category, risk_weight, approval_level, is_active)
WHERE rt.code = v.code;
-- Types added after migration 11 (e.g. by 12) have no old category: park them
-- inactive under GENERAL so the old constraint can be restored.
UPDATE eas.request_type SET category = 'GENERAL', is_active = false
WHERE category NOT IN ('HR','IT','FACILITY','PROCUREMENT','ASSET','FINANCE','GENERAL');
ALTER TABLE eas.request_type ADD CONSTRAINT request_type_category_valid
  CHECK (((category)::text = ANY ((ARRAY['HR'::character varying, 'IT'::character varying, 'FACILITY'::character varying, 'PROCUREMENT'::character varying, 'ASSET'::character varying, 'FINANCE'::character varying, 'GENERAL'::character varying])::text[])));
UPDATE eas.security_epoch SET version=version+1, updated_at=statement_timestamp() WHERE id=1;
COMMIT;
