-- FOR DBA REVIEW ONLY. No automatic execution.
-- Source: plan.docx tables 25, 27, 28, 29. Preserve old LEAVE/ACCESS/EQUIPMENT.
-- Requirements: backup, authorization and UAT; run 01_request_catalog_expansion_REVIEW_BEFORE_RUN.sql first.
-- New request types are inserted INACTIVE and are NOT usable without policy publication.
BEGIN;
SET LOCAL statement_timeout = '10s';
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='eas.request_type'::regclass AND conname='type_p0') THEN
   RAISE EXCEPTION 'P0 type_p0 constraint is still active: review and execute prior migration only with authorized DBA';
 END IF;
END $$;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('LEAVE_ANNUAL','A',false,'Nghỉ phép dưới 3 ngày','Loại yêu cầu Nghỉ phép dưới 3 ngày; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','HR') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('LEAVE_LONG','A',false,'Nghỉ phép từ 3 ngày','Loại yêu cầu Nghỉ phép từ 3 ngày; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','HR') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('RESIGNATION','C',false,'Thôi việc / Bàn giao','Loại yêu cầu Thôi việc / Bàn giao; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','HR') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('OVERTIME_REQ','B',false,'Đăng ký làm thêm giờ (OT)','Loại yêu cầu Đăng ký làm thêm giờ (OT); yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','HR') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('WFH_REQ','A',false,'Làm việc từ xa (WFH)','Loại yêu cầu Làm việc từ xa (WFH); yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','HR') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('ROOM_VEHICLE','B',false,'Mượn phòng họp / Xe công vụ','Loại yêu cầu Mượn phòng họp / Xe công vụ; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','FACILITY') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('ADVANCE_SMALL','B',false,'Tạm ứng chi phí (<10tr)','Loại yêu cầu Tạm ứng chi phí (<10tr); yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','FINANCE') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('ADVANCE_MEDIUM','B',false,'Tạm ứng chi phí (10-50tr)','Loại yêu cầu Tạm ứng chi phí (10-50tr); yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','FINANCE') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('ADVANCE_LARGE','B',false,'Tạm ứng dự án lớn (>50tr)','Loại yêu cầu Tạm ứng dự án lớn (>50tr); yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','FINANCE') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('REIMBURSEMENT','B',false,'Hoàn ứng / Thanh toán chi phí','Loại yêu cầu Hoàn ứng / Thanh toán chi phí; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','FINANCE') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('VENDOR_PAYMENT','C',false,'Thanh toán Hợp đồng Vendor','Loại yêu cầu Thanh toán Hợp đồng Vendor; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','FINANCE') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('LAPTOP_PROVISION','C',false,'Cấp Laptop / Thiết bị','Loại yêu cầu Cấp Laptop / Thiết bị; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','ASSET') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('SOFTWARE_ACCESS','B',false,'Cấp tài khoản / VPN','Loại yêu cầu Cấp tài khoản / VPN; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','IT') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('PROD_DATA_ACCESS','C',false,'Cấp quyền Dữ liệu nhạy cảm/Server','Loại yêu cầu Cấp quyền Dữ liệu nhạy cảm/Server; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','IT') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('SAAS_LICENSE_BUY','C',false,'Mua bản quyền phần mềm mới','Loại yêu cầu Mua bản quyền phần mềm mới; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','IT') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('OFFICE_SUPPLIES','B',false,'Cấp văn phòng phẩm','Loại yêu cầu Cấp văn phòng phẩm; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','PROCUREMENT') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('ASSET_PURCHASE','C',false,'Mua sắm tài sản phòng ban','Loại yêu cầu Mua sắm tài sản phòng ban; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','ASSET') ON CONFLICT (code) DO NOTHING;
INSERT INTO eas.request_type(code,lifecycle,is_active,name,description,category) VALUES ('FACILITY_REPAIR','C',false,'Sửa chữa sự cố văn phòng','Loại yêu cầu Sửa chữa sự cố văn phòng; yêu cầu công bố quy chế hợp lệ trước khi sử dụng.','FACILITY') ON CONFLICT (code) DO NOTHING;
-- Fail safely if a preexisting type has a contradictory lifecycle.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM eas.request_type WHERE code IN ('LEAVE_ANNUAL','LEAVE_LONG','RESIGNATION','OVERTIME_REQ','WFH_REQ','ROOM_VEHICLE','ADVANCE_SMALL','ADVANCE_MEDIUM','ADVANCE_LARGE','REIMBURSEMENT','VENDOR_PAYMENT','LAPTOP_PROVISION','SOFTWARE_ACCESS','PROD_DATA_ACCESS','SAAS_LICENSE_BUY','OFFICE_SUPPLIES','ASSET_PURCHASE','FACILITY_REPAIR') AND (code,lifecycle) NOT IN (('LEAVE_ANNUAL','A'),('LEAVE_LONG','A'),('RESIGNATION','C'),('OVERTIME_REQ','B'),('WFH_REQ','A'),('ROOM_VEHICLE','B'),('ADVANCE_SMALL','B'),('ADVANCE_MEDIUM','B'),('ADVANCE_LARGE','B'),('REIMBURSEMENT','B'),('VENDOR_PAYMENT','C'),('LAPTOP_PROVISION','C'),('SOFTWARE_ACCESS','B'),('PROD_DATA_ACCESS','C'),('SAAS_LICENSE_BUY','C'),('OFFICE_SUPPLIES','B'),('ASSET_PURCHASE','C'),('FACILITY_REPAIR','C'))) THEN
   RAISE EXCEPTION 'One or more existing request types has the wrong lifecycle';
 END IF;
END $$;
COMMIT;
-- Future manual steps: OPS grants scoped membership; POLICY_ADMIN builds, validates and publishes releases; Ops activates types only after successful UAT.

