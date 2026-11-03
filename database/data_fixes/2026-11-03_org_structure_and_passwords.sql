-- =============================================================================
-- Data fix 2026-11-03 — Bổ sung đủ cơ cấu tổ chức + đặt mật khẩu theo yêu cầu
-- Chạy SAU migration 11. Dán toàn bộ vào Supabase SQL Editor → Run.
-- Một transaction; chạy lại an toàn (đã đủ thì không tạo thêm).
--
-- Cơ cấu đích:
--   Ban Tổng Giám Đốc (BOD): 1 giám đốc (manager_id NULL), 1 phó giám đốc (báo cáo giám đốc).
--   Mỗi phòng ban còn lại: 1 trưởng phòng (báo cáo GĐ/PGĐ), 3 trưởng nhóm (báo cáo
--   trưởng phòng), mỗi nhóm ít nhất 5 nhân viên (báo cáo trưởng nhóm).
-- Quy tắc "có rồi thì thôi":
--   * Trưởng phòng = người trong phòng đang báo cáo GĐ/PGĐ, ưu tiên APPROVER phạm vi phòng.
--   * Trưởng nhóm = người đã có cấp dưới dưới trưởng phòng, rồi tới người còn lại đang
--     báo cáo GĐ/PGĐ (được chuyển về dưới trưởng phòng); thiếu thì tạo mới.
--   * Nhân viên cũ giữ nhóm hiện tại nếu đã dưới trưởng nhóm, còn lại chia vào nhóm ít
--     người nhất; nhóm thiếu thì tạo mới cho đủ 5.
-- Vai trò tài khoản mới (khớp luồng duyệt DIRECT_MANAGER và chọn người thực hiện):
--   GĐ/PGĐ: REQUESTER, ACCEPTOR, APPROVER (toàn công ty)
--   Trưởng phòng: REQUESTER, ACCEPTOR, APPROVER (toàn công ty + phạm vi phòng)
--   Trưởng nhóm: REQUESTER, ACCEPTOR (toàn công ty), APPROVER (phạm vi phòng)
--   Nhân viên: REQUESTER, ACCEPTOR (toàn công ty), EXECUTOR (phạm vi phòng)
--   Trưởng nhóm có sẵn được cấp thêm APPROVER phạm vi phòng nếu chưa có.
-- Mật khẩu (theo yêu cầu chủ dự án): admin@eas.com và MỌI tài khoản còn lại được đặt
--   lại mật khẩu dùng chung; phiên đăng nhập cũ bị đăng xuất (auth_version + 1).
-- =============================================================================

BEGIN;
SET LOCAL lock_timeout = '15s';

DO $pre$
BEGIN
  IF NOT pg_has_role(current_user, 'eas_migration', 'MEMBER') THEN
    RAISE EXCEPTION 'Chạy bằng role là thành viên của eas_migration (SQL Editor mặc định: postgres).';
  END IF;
  IF to_regclass('eas.admin_account') IS NULL THEN
    RAISE EXCEPTION 'Chưa chạy migration 11 (thiếu eas.admin_account / account_type).';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM eas.department WHERE code = 'BOD') THEN
    RAISE EXCEPTION 'Không có phòng BOD (Ban Tổng Giám Đốc).';
  END IF;
END
$pre$;

SET LOCAL ROLE eas_migration;
SELECT eas.lock_security(true);

-- Danh sách tên dự phòng cho tài khoản mới (lúc chạy vẫn bỏ qua email đã có).
CREATE TEMP TABLE _pool (
  seq int PRIMARY KEY,
  display_name text NOT NULL,
  email text NOT NULL,
  used boolean NOT NULL DEFAULT false
) ON COMMIT DROP;
INSERT INTO _pool(seq, display_name, email) VALUES
  (1, 'Phạm Thị An', 'an.pham@eas.com'),
  (2, 'Bùi Hữu Bình', 'binh.bui@eas.com'),
  (3, 'Trịnh Khánh Châu', 'chau.trinh@eas.com'),
  (4, 'Nguyễn Văn Dũng', 'dung.nguyen2@eas.com'),
  (5, 'Vũ Ngọc Giang', 'giang.vu@eas.com'),
  (6, 'Dương Bảo Hạnh', 'hanh.duong@eas.com'),
  (7, 'Cao Anh Hiếu', 'hieu.cao@eas.com'),
  (8, 'Hoàng Thanh Hòa', 'hoa.hoang@eas.com'),
  (9, 'Đỗ Gia Khang', 'khang.do@eas.com'),
  (10, 'Mai Phương Khoa', 'khoa.mai@eas.com'),
  (11, 'Trần Quốc Lâm', 'lam.tran@eas.com'),
  (12, 'Võ Thu Linh', 'linh.vo@eas.com'),
  (13, 'Lý Tuấn Mạnh', 'manh.ly@eas.com'),
  (14, 'Hà Minh Nhi', 'nhi.ha@eas.com'),
  (15, 'Huỳnh Đức Phong', 'phong.huynh@eas.com'),
  (16, 'Hồ Hoài Quân', 'quan.ho@eas.com'),
  (17, 'Tô Thị Quyên', 'quyen.to@eas.com'),
  (18, 'Lê Hữu Sơn', 'son.le@eas.com'),
  (19, 'Đặng Khánh Tâm', 'tam.dang@eas.com'),
  (20, 'Đinh Văn Thư', 'thu.dinh@eas.com'),
  (21, 'Lương Ngọc Tiến', 'tien.luong@eas.com'),
  (22, 'Phan Bảo Trâm', 'tram.phan@eas.com'),
  (23, 'Ngô Anh Vinh', 'vinh.ngo@eas.com'),
  (24, 'Lâm Thanh Xuân', 'xuan.lam@eas.com'),
  (25, 'Phạm Gia Hải', 'hai.pham@eas.com'),
  (26, 'Bùi Phương Hương', 'huong.bui@eas.com'),
  (27, 'Trịnh Quốc Kiệt', 'kiet.trinh@eas.com'),
  (28, 'Nguyễn Thu Lộc', 'loc.nguyen@eas.com'),
  (29, 'Vũ Tuấn My', 'my.vu@eas.com'),
  (30, 'Dương Minh Nhung', 'nhung.duong@eas.com'),
  (31, 'Cao Đức Oanh', 'oanh.cao@eas.com'),
  (32, 'Hoàng Hoài Phát', 'phat.hoang@eas.com'),
  (33, 'Đỗ Thị Quang', 'quang.do@eas.com'),
  (34, 'Mai Hữu Sang', 'sang.mai@eas.com'),
  (35, 'Trần Khánh Thảo', 'thao.tran@eas.com'),
  (36, 'Võ Văn Toàn', 'toan.vo@eas.com'),
  (37, 'Lý Ngọc Uyên', 'uyen.ly@eas.com'),
  (38, 'Hà Bảo Việt', 'viet.ha@eas.com'),
  (39, 'Huỳnh Anh Vy', 'vy.huynh@eas.com'),
  (40, 'Hồ Thanh Yên', 'yen.ho@eas.com'),
  (41, 'Tô Gia An', 'an.to@eas.com'),
  (42, 'Lê Phương Bình', 'binh.le@eas.com'),
  (43, 'Đặng Quốc Châu', 'chau.dang@eas.com'),
  (44, 'Đinh Thu Dũng', 'dung.dinh@eas.com'),
  (45, 'Lương Tuấn Giang', 'giang.luong@eas.com'),
  (46, 'Phan Minh Hạnh', 'hanh.phan@eas.com'),
  (47, 'Ngô Đức Hiếu', 'hieu.ngo@eas.com'),
  (48, 'Lâm Hoài Hòa', 'hoa.lam@eas.com'),
  (49, 'Phạm Thị Khang', 'khang.pham@eas.com'),
  (50, 'Bùi Hữu Khoa', 'khoa.bui@eas.com'),
  (51, 'Trịnh Khánh Lâm', 'lam.trinh@eas.com'),
  (52, 'Nguyễn Văn Linh', 'linh.nguyen@eas.com'),
  (53, 'Vũ Ngọc Mạnh', 'manh.vu@eas.com'),
  (54, 'Dương Bảo Nhi', 'nhi.duong@eas.com'),
  (55, 'Cao Anh Phong', 'phong.cao@eas.com'),
  (56, 'Hoàng Thanh Quân', 'quan.hoang@eas.com'),
  (57, 'Đỗ Gia Quyên', 'quyen.do@eas.com'),
  (58, 'Mai Phương Sơn', 'son.mai@eas.com'),
  (59, 'Trần Quốc Tâm', 'tam.tran@eas.com'),
  (60, 'Võ Thu Thư', 'thu.vo@eas.com'),
  (61, 'Lý Tuấn Tiến', 'tien.ly@eas.com'),
  (62, 'Hà Minh Trâm', 'tram.ha@eas.com'),
  (63, 'Huỳnh Đức Vinh', 'vinh.huynh@eas.com'),
  (64, 'Hồ Hoài Xuân', 'xuan.ho@eas.com'),
  (65, 'Tô Thị Hải', 'hai.to@eas.com'),
  (66, 'Lê Hữu Hương', 'huong.le@eas.com'),
  (67, 'Đặng Khánh Kiệt', 'kiet.dang@eas.com'),
  (68, 'Đinh Văn Lộc', 'loc.dinh@eas.com'),
  (69, 'Lương Ngọc My', 'my.luong@eas.com'),
  (70, 'Phan Bảo Nhung', 'nhung.phan@eas.com'),
  (71, 'Ngô Anh Oanh', 'oanh.ngo@eas.com'),
  (72, 'Lâm Thanh Phát', 'phat.lam@eas.com'),
  (73, 'Phạm Gia Quang', 'quang.pham@eas.com'),
  (74, 'Bùi Phương Sang', 'sang.bui@eas.com'),
  (75, 'Trịnh Quốc Thảo', 'thao.trinh@eas.com'),
  (76, 'Nguyễn Thu Toàn', 'toan.nguyen@eas.com'),
  (77, 'Vũ Tuấn Uyên', 'uyen.vu@eas.com'),
  (78, 'Dương Minh Việt', 'viet.duong@eas.com'),
  (79, 'Cao Đức Vy', 'vy.cao@eas.com'),
  (80, 'Hoàng Hoài Yên', 'yen.hoang2@eas.com'),
  (81, 'Đỗ Thị An', 'an.do@eas.com'),
  (82, 'Mai Hữu Bình', 'binh.mai@eas.com'),
  (83, 'Trần Khánh Châu', 'chau.tran@eas.com'),
  (84, 'Võ Văn Dũng', 'dung.vo@eas.com'),
  (85, 'Lý Ngọc Giang', 'giang.ly@eas.com'),
  (86, 'Hà Bảo Hạnh', 'hanh.ha@eas.com'),
  (87, 'Huỳnh Anh Hiếu', 'hieu.huynh@eas.com'),
  (88, 'Hồ Thanh Hòa', 'hoa.ho@eas.com'),
  (89, 'Tô Gia Khang', 'khang.to@eas.com'),
  (90, 'Lê Phương Khoa', 'khoa.le@eas.com'),
  (91, 'Đặng Quốc Lâm', 'lam.dang@eas.com'),
  (92, 'Đinh Thu Linh', 'linh.dinh@eas.com'),
  (93, 'Lương Tuấn Mạnh', 'manh.luong@eas.com'),
  (94, 'Phan Minh Nhi', 'nhi.phan@eas.com'),
  (95, 'Ngô Đức Phong', 'phong.ngo@eas.com'),
  (96, 'Lâm Hoài Quân', 'quan.lam@eas.com'),
  (97, 'Phạm Thị Quyên', 'quyen.pham@eas.com'),
  (98, 'Bùi Hữu Sơn', 'son.bui@eas.com'),
  (99, 'Trịnh Khánh Tâm', 'tam.trinh@eas.com'),
  (100, 'Nguyễn Văn Thư', 'thu.nguyen@eas.com'),
  (101, 'Vũ Ngọc Tiến', 'tien.vu@eas.com'),
  (102, 'Dương Bảo Trâm', 'tram.duong@eas.com'),
  (103, 'Cao Anh Vinh', 'vinh.cao@eas.com'),
  (104, 'Hoàng Thanh Xuân', 'xuan.hoang@eas.com'),
  (105, 'Đỗ Gia Hải', 'hai.do@eas.com'),
  (106, 'Mai Phương Hương', 'huong.mai@eas.com'),
  (107, 'Trần Quốc Kiệt', 'kiet.tran@eas.com'),
  (108, 'Võ Thu Lộc', 'loc.vo@eas.com'),
  (109, 'Lý Tuấn My', 'my.ly@eas.com'),
  (110, 'Hà Minh Nhung', 'nhung.ha@eas.com'),
  (111, 'Huỳnh Đức Oanh', 'oanh.huynh@eas.com'),
  (112, 'Hồ Hoài Phát', 'phat.ho@eas.com'),
  (113, 'Tô Thị Quang', 'quang.to@eas.com'),
  (114, 'Lê Hữu Sang', 'sang.le@eas.com'),
  (115, 'Đặng Khánh Thảo', 'thao.dang@eas.com'),
  (116, 'Đinh Văn Toàn', 'toan.dinh@eas.com'),
  (117, 'Lương Ngọc Uyên', 'uyen.luong@eas.com'),
  (118, 'Phan Bảo Việt', 'viet.phan@eas.com'),
  (119, 'Ngô Anh Vy', 'vy.ngo@eas.com'),
  (120, 'Lâm Thanh Yên', 'yen.lam@eas.com'),
  (121, 'Phạm Gia An', 'an.pham2@eas.com'),
  (122, 'Bùi Phương Bình', 'binh.bui2@eas.com'),
  (123, 'Trịnh Quốc Châu', 'chau.trinh2@eas.com'),
  (124, 'Nguyễn Thu Dũng', 'dung.nguyen3@eas.com'),
  (125, 'Vũ Tuấn Giang', 'giang.vu2@eas.com'),
  (126, 'Dương Minh Hạnh', 'hanh.duong2@eas.com'),
  (127, 'Cao Đức Hiếu', 'hieu.cao2@eas.com'),
  (128, 'Hoàng Hoài Hòa', 'hoa.hoang2@eas.com'),
  (129, 'Đỗ Thị Khang', 'khang.do2@eas.com'),
  (130, 'Mai Hữu Khoa', 'khoa.mai2@eas.com'),
  (131, 'Trần Khánh Lâm', 'lam.tran2@eas.com'),
  (132, 'Võ Văn Linh', 'linh.vo2@eas.com'),
  (133, 'Lý Ngọc Mạnh', 'manh.ly2@eas.com'),
  (134, 'Hà Bảo Nhi', 'nhi.ha2@eas.com'),
  (135, 'Huỳnh Anh Phong', 'phong.huynh2@eas.com'),
  (136, 'Hồ Thanh Quân', 'quan.ho2@eas.com'),
  (137, 'Tô Gia Quyên', 'quyen.to2@eas.com'),
  (138, 'Lê Phương Sơn', 'son.le2@eas.com'),
  (139, 'Đặng Quốc Tâm', 'tam.dang2@eas.com'),
  (140, 'Đinh Thu Thư', 'thu.dinh2@eas.com'),
  (141, 'Lương Tuấn Tiến', 'tien.luong2@eas.com'),
  (142, 'Phan Minh Trâm', 'tram.phan2@eas.com'),
  (143, 'Ngô Đức Vinh', 'vinh.ngo2@eas.com'),
  (144, 'Lâm Hoài Xuân', 'xuan.lam2@eas.com'),
  (145, 'Phạm Thị Hải', 'hai.pham2@eas.com'),
  (146, 'Bùi Hữu Hương', 'huong.bui2@eas.com'),
  (147, 'Trịnh Khánh Kiệt', 'kiet.trinh2@eas.com'),
  (148, 'Nguyễn Văn Lộc', 'loc.nguyen2@eas.com'),
  (149, 'Vũ Ngọc My', 'my.vu2@eas.com'),
  (150, 'Dương Bảo Nhung', 'nhung.duong2@eas.com'),
  (151, 'Cao Anh Oanh', 'oanh.cao2@eas.com'),
  (152, 'Hoàng Thanh Phát', 'phat.hoang2@eas.com'),
  (153, 'Đỗ Gia Quang', 'quang.do2@eas.com'),
  (154, 'Mai Phương Sang', 'sang.mai2@eas.com'),
  (155, 'Trần Quốc Thảo', 'thao.tran2@eas.com'),
  (156, 'Võ Thu Toàn', 'toan.vo2@eas.com'),
  (157, 'Lý Tuấn Uyên', 'uyen.ly2@eas.com'),
  (158, 'Hà Minh Việt', 'viet.ha2@eas.com'),
  (159, 'Huỳnh Đức Vy', 'vy.huynh2@eas.com'),
  (160, 'Hồ Hoài Yên', 'yen.ho2@eas.com'),
  (161, 'Tô Thị An', 'an.to2@eas.com'),
  (162, 'Lê Hữu Bình', 'binh.le2@eas.com'),
  (163, 'Đặng Khánh Châu', 'chau.dang2@eas.com'),
  (164, 'Đinh Văn Dũng', 'dung.dinh2@eas.com'),
  (165, 'Lương Ngọc Giang', 'giang.luong2@eas.com'),
  (166, 'Phan Bảo Hạnh', 'hanh.phan2@eas.com'),
  (167, 'Ngô Anh Hiếu', 'hieu.ngo2@eas.com'),
  (168, 'Lâm Thanh Hòa', 'hoa.lam2@eas.com'),
  (169, 'Phạm Gia Khang', 'khang.pham2@eas.com'),
  (170, 'Bùi Phương Khoa', 'khoa.bui2@eas.com'),
  (171, 'Trịnh Quốc Lâm', 'lam.trinh2@eas.com'),
  (172, 'Nguyễn Thu Linh', 'linh.nguyen2@eas.com'),
  (173, 'Vũ Tuấn Mạnh', 'manh.vu2@eas.com'),
  (174, 'Dương Minh Nhi', 'nhi.duong2@eas.com'),
  (175, 'Cao Đức Phong', 'phong.cao2@eas.com'),
  (176, 'Hoàng Hoài Quân', 'quan.hoang2@eas.com'),
  (177, 'Đỗ Thị Quyên', 'quyen.do2@eas.com'),
  (178, 'Mai Hữu Sơn', 'son.mai2@eas.com'),
  (179, 'Trần Khánh Tâm', 'tam.tran2@eas.com'),
  (180, 'Võ Văn Thư', 'thu.vo2@eas.com'),
  (181, 'Lý Ngọc Tiến', 'tien.ly2@eas.com'),
  (182, 'Hà Bảo Trâm', 'tram.ha2@eas.com'),
  (183, 'Huỳnh Anh Vinh', 'vinh.huynh2@eas.com'),
  (184, 'Hồ Thanh Xuân', 'xuan.ho2@eas.com'),
  (185, 'Tô Gia Hải', 'hai.to2@eas.com'),
  (186, 'Lê Phương Hương', 'huong.le2@eas.com'),
  (187, 'Đặng Quốc Kiệt', 'kiet.dang2@eas.com'),
  (188, 'Đinh Thu Lộc', 'loc.dinh2@eas.com'),
  (189, 'Lương Tuấn My', 'my.luong2@eas.com'),
  (190, 'Phan Minh Nhung', 'nhung.phan2@eas.com'),
  (191, 'Ngô Đức Oanh', 'oanh.ngo2@eas.com'),
  (192, 'Lâm Hoài Phát', 'phat.lam2@eas.com'),
  (193, 'Phạm Thị Quang', 'quang.pham2@eas.com'),
  (194, 'Bùi Hữu Sang', 'sang.bui2@eas.com'),
  (195, 'Trịnh Khánh Thảo', 'thao.trinh2@eas.com'),
  (196, 'Nguyễn Văn Toàn', 'toan.nguyen2@eas.com'),
  (197, 'Vũ Ngọc Uyên', 'uyen.vu2@eas.com'),
  (198, 'Dương Bảo Việt', 'viet.duong2@eas.com'),
  (199, 'Cao Anh Vy', 'vy.cao2@eas.com'),
  (200, 'Hoàng Thanh Yên', 'yen.hoang3@eas.com');

CREATE TEMP TABLE _created (id uuid PRIMARY KEY, kind text NOT NULL) ON COMMIT DROP;

CREATE OR REPLACE FUNCTION pg_temp.grant_role(p_user uuid, p_role text, p_dept uuid)
RETURNS void LANGUAGE sql AS $f$
  INSERT INTO eas.role_membership(user_id, role, scope_kind, department_id, type_scope)
  SELECT p_user, p_role,
         CASE WHEN p_dept IS NULL THEN 'GLOBAL' ELSE 'DEPARTMENT' END, p_dept, 'ALL'
  WHERE NOT EXISTS (
    SELECT 1 FROM eas.role_membership m
    WHERE m.user_id = p_user AND m.role = p_role AND m.revoked_at IS NULL
      AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
      AND m.type_scope = 'ALL'
      AND (m.scope_kind = 'GLOBAL' OR m.department_id IS NOT DISTINCT FROM p_dept))
$f$;

CREATE OR REPLACE FUNCTION pg_temp.new_user(p_dept uuid, p_manager uuid, p_kind text)
RETURNS uuid LANGUAGE plpgsql AS $f$
DECLARE v_id uuid; v_seq int;
BEGIN
  SELECT p.seq INTO v_seq FROM _pool p
  WHERE NOT p.used AND NOT EXISTS (SELECT 1 FROM eas.app_user u WHERE u.email = p.email)
  ORDER BY p.seq LIMIT 1;
  IF v_seq IS NULL THEN
    RAISE EXCEPTION 'Hết tên dự phòng để tạo tài khoản mới.';
  END IF;
  UPDATE _pool SET used = true WHERE seq = v_seq;
  INSERT INTO eas.app_user(email, display_name, department_id, manager_id, is_active,
                           must_change_password, auth_version, password_hash, account_type)
  SELECT p.email, p.display_name, p_dept, p_manager, true, false, 0, 'argon2$argon2id$v=19$m=102400,t=2,p=8$RFdaNWx3UndBNmRIODJUMHM4aWx0OA$eY6k2qSLTgiYrLyQhXCo/2qwdQIe1KmKCJ1EmixVYFU', 'EMPLOYEE'
  FROM _pool p WHERE p.seq = v_seq
  RETURNING id INTO v_id;
  INSERT INTO _created(id, kind) VALUES (v_id, p_kind);

  PERFORM pg_temp.grant_role(v_id, 'REQUESTER', NULL);
  PERFORM pg_temp.grant_role(v_id, 'ACCEPTOR', NULL);
  IF p_kind IN ('DIRECTOR', 'DEPUTY', 'HEAD') THEN
    PERFORM pg_temp.grant_role(v_id, 'APPROVER', NULL);
  END IF;
  IF p_kind IN ('HEAD', 'LEAD') THEN
    PERFORM pg_temp.grant_role(v_id, 'APPROVER', p_dept);
  END IF;
  IF p_kind = 'STAFF' THEN
    PERFORM pg_temp.grant_role(v_id, 'EXECUTOR', p_dept);
  END IF;
  RETURN v_id;
END
$f$;

DO $org$
DECLARE
  v_bod uuid := (SELECT id FROM eas.department WHERE code = 'BOD');
  v_dir uuid; v_dep uuid; v_head uuid; v_lead uuid;
  v_leads uuid[];
  d record; s record;
  v_need int;
BEGIN
  -- Giám đốc / phó giám đốc
  SELECT u.id INTO v_dir FROM eas.app_user u
  WHERE u.department_id = v_bod AND u.manager_id IS NULL AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false)
  ORDER BY u.created_at, u.email LIMIT 1;
  IF v_dir IS NULL THEN
    v_dir := pg_temp.new_user(v_bod, NULL, 'DIRECTOR');
  END IF;

  SELECT u.id INTO v_dep FROM eas.app_user u
  WHERE u.department_id = v_bod AND u.manager_id = v_dir AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false)
  ORDER BY u.created_at, u.email LIMIT 1;
  IF v_dep IS NULL THEN
    v_dep := pg_temp.new_user(v_bod, v_dir, 'DEPUTY');
  END IF;

  FOR d IN
    SELECT id, code FROM eas.department WHERE is_active AND id <> v_bod ORDER BY code
  LOOP
    -- Trưởng phòng
    v_head := NULL;
    SELECT u.id INTO v_head FROM eas.app_user u
    WHERE u.department_id = d.id AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false)
      AND u.manager_id IN (v_dir, v_dep)
    ORDER BY EXISTS (
               SELECT 1 FROM eas.role_membership m
               WHERE m.user_id = u.id AND m.role = 'APPROVER' AND m.scope_kind = 'DEPARTMENT'
                 AND m.department_id = d.id AND m.revoked_at IS NULL) DESC,
             u.created_at, u.email
    LIMIT 1;
    IF v_head IS NULL THEN
      v_head := pg_temp.new_user(d.id, v_dep, 'HEAD');
    END IF;

    -- Trưởng nhóm có sẵn (tối đa 3)
    SELECT array_agg(x.id ORDER BY x.pri, x.created_at, x.email) INTO v_leads
    FROM (
      SELECT u.id, u.created_at, u.email, 0 AS pri FROM eas.app_user u
      WHERE u.department_id = d.id AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false)
        AND u.manager_id = v_head
        AND EXISTS (SELECT 1 FROM eas.app_user r WHERE r.manager_id = u.id AND r.is_active)
      UNION ALL
      SELECT u.id, u.created_at, u.email, 1 FROM eas.app_user u
      WHERE u.department_id = d.id AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false)
        AND u.manager_id IN (v_dir, v_dep) AND u.id <> v_head
    ) x;
    v_leads := COALESCE(v_leads[1:3], ARRAY[]::uuid[]);

    UPDATE eas.app_user SET manager_id = v_head
    WHERE id = ANY(v_leads) AND manager_id IS DISTINCT FROM v_head;
    FOREACH v_lead IN ARRAY v_leads LOOP
      PERFORM pg_temp.grant_role(v_lead, 'APPROVER', d.id);
    END LOOP;
    WHILE cardinality(v_leads) < 3 LOOP
      v_leads := v_leads || pg_temp.new_user(d.id, v_head, 'LEAD');
    END LOOP;

    -- Nhân viên cũ chưa thuộc nhóm nào: chia vào nhóm ít người nhất
    FOR s IN
      SELECT u.id FROM eas.app_user u
      WHERE u.department_id = d.id AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false)
        AND u.id <> v_head AND u.id <> ALL(v_leads)
        AND u.manager_id IS DISTINCT FROM v_dir AND u.manager_id IS DISTINCT FROM v_dep
        AND NOT (u.manager_id IS NOT NULL AND u.manager_id = ANY(v_leads))
      ORDER BY u.created_at, u.email
    LOOP
      SELECT t.l INTO v_lead FROM unnest(v_leads) WITH ORDINALITY AS t(l, ord)
      ORDER BY (SELECT count(*) FROM eas.app_user r WHERE r.manager_id = t.l AND r.is_active), t.ord
      LIMIT 1;
      UPDATE eas.app_user SET manager_id = v_lead WHERE id = s.id;
    END LOOP;

    -- Bổ sung cho đủ 5 nhân viên mỗi nhóm
    FOREACH v_lead IN ARRAY v_leads LOOP
      SELECT 5 - count(*) INTO v_need FROM eas.app_user r WHERE r.manager_id = v_lead AND r.is_active;
      WHILE v_need > 0 LOOP
        PERFORM pg_temp.new_user(d.id, v_lead, 'STAFF');
        v_need := v_need - 1;
      END LOOP;
    END LOOP;
  END LOOP;
END
$org$;

-- Mật khẩu theo yêu cầu (chỉ đổi khi khác, để chạy lại không đăng xuất mọi người lần nữa).
UPDATE eas.app_user
SET password_hash = 'argon2$argon2id$v=19$m=102400,t=2,p=8$c2JmMmxjYXo5cU5qenRnTWdXdDVsSA$1EMu0l6qMwYDQndkiyUYf6T7TlYjErymnJfZpmXrkIE', auth_version = auth_version + 1, must_change_password = false
WHERE email = 'admin@eas.com' AND password_hash <> 'argon2$argon2id$v=19$m=102400,t=2,p=8$c2JmMmxjYXo5cU5qenRnTWdXdDVsSA$1EMu0l6qMwYDQndkiyUYf6T7TlYjErymnJfZpmXrkIE';

UPDATE eas.app_user
SET password_hash = 'argon2$argon2id$v=19$m=102400,t=2,p=8$RFdaNWx3UndBNmRIODJUMHM4aWx0OA$eY6k2qSLTgiYrLyQhXCo/2qwdQIe1KmKCJ1EmixVYFU', auth_version = auth_version + 1, must_change_password = false
WHERE email <> 'admin@eas.com' AND password_hash <> 'argon2$argon2id$v=19$m=102400,t=2,p=8$RFdaNWx3UndBNmRIODJUMHM4aWx0OA$eY6k2qSLTgiYrLyQhXCo/2qwdQIe1KmKCJ1EmixVYFU'
  -- Tài khoản hệ thống (vd ai.system@eas.com, migration 08) không bao giờ đăng nhập được.
  AND NOT COALESCE((to_jsonb(app_user) ->> 'is_system_account')::boolean, false);

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
SET CONSTRAINTS ALL IMMEDIATE;

-- Tự kiểm tra cơ cấu
DO $verify$
DECLARE
  v_bod uuid := (SELECT id FROM eas.department WHERE code = 'BOD');
  v_dir uuid; v_dep uuid; d record; v_head uuid; n int; bad int;
BEGIN
  SELECT id INTO v_dir FROM eas.app_user
  WHERE department_id = v_bod AND manager_id IS NULL AND is_active AND account_type = 'EMPLOYEE'
  ORDER BY created_at, email LIMIT 1;
  SELECT id INTO v_dep FROM eas.app_user
  WHERE department_id = v_bod AND manager_id = v_dir AND is_active AND account_type = 'EMPLOYEE'
  ORDER BY created_at, email LIMIT 1;
  IF v_dir IS NULL OR v_dep IS NULL THEN RAISE EXCEPTION 'VERIFY: thiếu giám đốc/phó giám đốc'; END IF;

  FOR d IN SELECT id, code FROM eas.department WHERE is_active AND id <> v_bod LOOP
    v_head := NULL;
    SELECT u.id INTO v_head FROM eas.app_user u
    WHERE u.department_id = d.id AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false) AND u.manager_id IN (v_dir, v_dep)
    ORDER BY EXISTS (SELECT 1 FROM eas.role_membership m WHERE m.user_id = u.id AND m.role = 'APPROVER'
                     AND m.scope_kind = 'DEPARTMENT' AND m.department_id = d.id AND m.revoked_at IS NULL) DESC,
             u.created_at, u.email
    LIMIT 1;
    IF v_head IS NULL THEN RAISE EXCEPTION 'VERIFY: phòng % thiếu trưởng phòng', d.code; END IF;

    SELECT count(*) INTO n FROM eas.app_user l
    WHERE l.manager_id = v_head AND l.is_active
      AND (SELECT count(*) FROM eas.app_user r WHERE r.manager_id = l.id AND r.is_active) >= 5;
    IF n < 3 THEN RAISE EXCEPTION 'VERIFY: phòng % chỉ có % nhóm đủ 5 nhân viên', d.code, n; END IF;

    -- Trưởng nhóm phải duyệt được yêu cầu của nhân viên trong phòng (DIRECT_MANAGER).
    SELECT count(*) INTO bad FROM eas.app_user l
    WHERE l.manager_id = v_head AND l.is_active
      AND EXISTS (SELECT 1 FROM eas.app_user r WHERE r.manager_id = l.id AND r.is_active)
      AND NOT EXISTS (SELECT 1 FROM eas.role_membership m WHERE m.user_id = l.id AND m.role = 'APPROVER'
                      AND m.revoked_at IS NULL AND (m.valid_to IS NULL OR m.valid_to > statement_timestamp())
                      AND (m.scope_kind = 'GLOBAL' OR m.department_id = d.id));
    IF bad > 0 THEN RAISE EXCEPTION 'VERIFY: phòng % có % trưởng nhóm không có quyền duyệt', d.code, bad; END IF;
  END LOOP;

  IF EXISTS (SELECT 1 FROM eas.app_user WHERE email = 'admin@eas.com' AND password_hash <> 'argon2$argon2id$v=19$m=102400,t=2,p=8$c2JmMmxjYXo5cU5qenRnTWdXdDVsSA$1EMu0l6qMwYDQndkiyUYf6T7TlYjErymnJfZpmXrkIE') THEN
    RAISE EXCEPTION 'VERIFY: mật khẩu admin chưa đặt';
  END IF;
END
$verify$;

RESET ROLE;
COMMIT;

-- Báo cáo cơ cấu sau khi chạy (chỉ đọc)
WITH bod AS (SELECT id FROM eas.department WHERE code = 'BOD')
SELECT d.code AS phong_ban,
       h.display_name AS truong_phong,
       (SELECT count(*) FROM eas.app_user l WHERE l.manager_id = h.id AND l.is_active
          AND EXISTS (SELECT 1 FROM eas.app_user r WHERE r.manager_id = l.id AND r.is_active)) AS so_truong_nhom,
       (SELECT count(*) FROM eas.app_user r JOIN eas.app_user l ON l.id = r.manager_id
         WHERE l.manager_id = h.id AND r.is_active) AS so_nhan_vien,
       (SELECT count(*) FROM eas.app_user u WHERE u.department_id = d.id AND u.is_active) AS tong_tai_khoan
FROM eas.department d
CROSS JOIN bod
JOIN LATERAL (
  SELECT u.id, u.display_name FROM eas.app_user u
  WHERE u.department_id = d.id AND u.is_active AND u.account_type = 'EMPLOYEE' AND NOT COALESCE((to_jsonb(u) ->> 'is_system_account')::boolean, false)
    AND u.manager_id IN (SELECT id FROM eas.app_user WHERE department_id = bod.id AND account_type = 'EMPLOYEE')
  ORDER BY EXISTS (SELECT 1 FROM eas.role_membership m WHERE m.user_id = u.id AND m.role = 'APPROVER'
                   AND m.scope_kind = 'DEPARTMENT' AND m.department_id = d.id AND m.revoked_at IS NULL) DESC,
           u.created_at, u.email
  LIMIT 1) h ON true
WHERE d.is_active AND d.id <> bod.id
ORDER BY d.code;
