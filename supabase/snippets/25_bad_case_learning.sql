-- 25: Bảng bad case trong CSDL và học bad case mới từ lý do người duyệt thu hồi hồ sơ AI đã tự duyệt.
--
--   1. eas.bad_case: danh mục tình huống xấu mà AI dùng để KHÔNG tự duyệt và chuyển hồ sơ A sang B/C.
--      - BUILTIN: 12 tình huống có sẵn (bộ phát hiện viết trong ai_service/bad_cases.py), seed bên dưới;
--        admin chỉ được ngưng (RETIRED) hoặc bật lại.
--      - RULE: bad case AI học được từ lý do thu hồi, có điều kiện đo được (condition, tập đặc trưng cố định).
--      - SCOPE: mở rộng một bad case có sẵn sang loại đơn khác (base_code).
--      rationale = vì sao đó là bad case (tác hại), hiện cho người duyệt khi AI chuyển hồ sơ.
--      evaluation = AI tự đánh giá "đủ thường xuyên để thành bad case chưa" (từng tiêu chí, lý do thiếu,
--      câu hỏi cho admin). Trạng thái: CANDIDATE (chờ admin) -> ACTIVE (AI tự kích hoạt khi đủ, hoặc admin
--      duyệt) / REJECTED (admin không tạo; mở lại thành CANDIDATE khi có thêm nhiều ca); ACTIVE <-> RETIRED.
--   2. eas.bad_case_evidence: mỗi lý do thu hồi kèm kết luận của AI (khớp bad case có sẵn / kiểu mới / lý do
--      riêng của hồ sơ), đặc trưng của hồ sơ lúc đó và ứng viên được ghép vào. Chỉ thêm.
--
-- Cần migration 24 (eas.ai_feedback). Chạy được nhiều lần.
-- Rollback: database/migrations/rollback/25_bad_case_learning_rollback.sql

BEGIN;
SELECT eas.lock_security(true);

CREATE TABLE IF NOT EXISTS eas.bad_case (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code varchar(60) NOT NULL UNIQUE CHECK (code ~ '^BC_[A-Z0-9_]{2,57}$'),
  title varchar(200) NOT NULL CHECK (length(btrim(title)) >= 3),
  rationale varchar(2000) NOT NULL CHECK (length(btrim(rationale)) >= 5),
  condition_text varchar(1000),
  request_types text[] NOT NULL CHECK (cardinality(request_types) BETWEEN 1 AND 60),
  detector varchar(10) NOT NULL CHECK (detector IN ('BUILTIN', 'RULE', 'SCOPE')),
  base_code varchar(60) REFERENCES eas.bad_case(code) ON DELETE RESTRICT,
  condition jsonb CHECK (condition IS NULL OR jsonb_typeof(condition) = 'object'),
  verdict varchar(15) CHECK (verdict IN ('EXISTING_SCOPE', 'NEW_PATTERN', 'ONE_OFF')),
  feature varchar(40),
  risk smallint NOT NULL DEFAULT 3 CHECK (risk BETWEEN 1 AND 5),
  escalate_to char(1) NOT NULL DEFAULT 'B' CHECK (escalate_to IN ('B', 'C')),
  source varchar(10) NOT NULL CHECK (source IN ('CATALOG', 'AI', 'ADMIN')),
  state varchar(10) NOT NULL CHECK (state IN ('CANDIDATE', 'ACTIVE', 'REJECTED', 'RETIRED')),
  evaluation jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evaluation) = 'object'),
  activated_by varchar(10) CHECK (activated_by IN ('CATALOG', 'AI', 'ADMIN')),
  activated_at timestamptz,
  decided_by uuid REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  decided_at timestamptz,
  note varchar(500),
  created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
  CHECK (detector <> 'BUILTIN' OR source = 'CATALOG'),
  CHECK (detector <> 'SCOPE' OR base_code IS NOT NULL),
  CHECK (state <> 'ACTIVE' OR detector <> 'RULE' OR condition IS NOT NULL),
  CHECK (state NOT IN ('ACTIVE', 'RETIRED') OR activated_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS bad_case_state ON eas.bad_case(state, detector);
COMMENT ON TABLE eas.bad_case IS
  'Danh mục bad case AI dùng để chặn tự duyệt và chuyển A -> B/C: 12 bad case có sẵn + bad case học từ lý do thu hồi.';
COMMENT ON COLUMN eas.bad_case.rationale IS 'Vì sao là bad case (tác hại); hiện cho người duyệt khi AI chuyển hồ sơ.';
COMMENT ON COLUMN eas.bad_case.evaluation IS 'AI tự đánh giá đủ/chưa đủ để thành bad case: tiêu chí, lý do thiếu, câu hỏi cho admin.';

CREATE TABLE IF NOT EXISTS eas.bad_case_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  feedback_id uuid UNIQUE REFERENCES eas.ai_feedback(id) ON DELETE CASCADE,
  request_id uuid NOT NULL REFERENCES eas.request(id) ON DELETE CASCADE,
  bad_case_id uuid REFERENCES eas.bad_case(id) ON DELETE RESTRICT,
  type_code varchar(30) NOT NULL,
  requester_id uuid REFERENCES eas.app_user(id) ON DELETE SET NULL,
  approver_id uuid NOT NULL REFERENCES eas.app_user(id) ON DELETE RESTRICT,
  reason varchar(2000) NOT NULL CHECK (length(btrim(reason)) >= 5),
  verdict varchar(15) NOT NULL CHECK (verdict IN ('EXISTING', 'EXISTING_SCOPE', 'NEW_PATTERN', 'ONE_OFF')),
  confidence numeric(4, 3) CHECK (confidence BETWEEN 0 AND 1),
  feature varchar(40),
  feature_values jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(feature_values) = 'object'),
  analysis jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(analysis) = 'object'),
  created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX IF NOT EXISTS bad_case_evidence_case ON eas.bad_case_evidence(bad_case_id, created_at);
COMMENT ON TABLE eas.bad_case_evidence IS
  'Lý do người duyệt thu hồi tự duyệt + kết luận của AI (khớp bad case có sẵn / kiểu mới / lý do riêng). Chỉ thêm.';

CREATE OR REPLACE FUNCTION eas.guard_bad_case() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='bad cases are never deleted; retire or reject them';
 END IF;
 IF NEW.code IS DISTINCT FROM OLD.code OR NEW.detector IS DISTINCT FROM OLD.detector
    OR NEW.source IS DISTINCT FROM OLD.source OR NEW.base_code IS DISTINCT FROM OLD.base_code THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='bad case identity is immutable';
 END IF;
 IF OLD.detector = 'BUILTIN'
    AND (to_jsonb(NEW) - ARRAY['state','note','decided_by','decided_at','updated_at','evaluation'])
    IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['state','note','decided_by','decided_at','updated_at','evaluation']) THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='built-in bad cases can only be retired or re-enabled';
 END IF;
 IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
      (OLD.state = 'CANDIDATE' AND NEW.state IN ('ACTIVE', 'REJECTED'))
   OR (OLD.state = 'REJECTED' AND NEW.state = 'CANDIDATE')
   OR (OLD.state = 'ACTIVE' AND NEW.state = 'RETIRED')
   OR (OLD.state = 'RETIRED' AND NEW.state = 'ACTIVE')) THEN
  RAISE EXCEPTION USING ERRCODE='23514', MESSAGE=format('bad case state %s -> %s not allowed', OLD.state, NEW.state);
 END IF;
 IF OLD.state IN ('ACTIVE', 'RETIRED') AND OLD.detector = 'RULE'
    AND NEW.condition IS DISTINCT FROM OLD.condition THEN
  RAISE EXCEPTION USING ERRCODE='23514',
    MESSAGE='condition of an activated bad case is immutable; retire it and learn a new one';
 END IF;
 NEW.updated_at := statement_timestamp();
 RETURN NEW;
END $$;
ALTER FUNCTION eas.guard_bad_case() OWNER TO eas_migration;
REVOKE EXECUTE ON FUNCTION eas.guard_bad_case() FROM PUBLIC;
DROP TRIGGER IF EXISTS bad_case_guard ON eas.bad_case;
CREATE TRIGGER bad_case_guard BEFORE UPDATE OR DELETE ON eas.bad_case
  FOR EACH ROW EXECUTE FUNCTION eas.guard_bad_case();

CREATE OR REPLACE FUNCTION eas.guard_bad_case_evidence() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'eas'
    AS $$
BEGIN
 RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='bad case evidence is append-only';
END $$;
ALTER FUNCTION eas.guard_bad_case_evidence() OWNER TO eas_migration;
REVOKE EXECUTE ON FUNCTION eas.guard_bad_case_evidence() FROM PUBLIC;
DROP TRIGGER IF EXISTS bad_case_evidence_guard ON eas.bad_case_evidence;
CREATE TRIGGER bad_case_evidence_guard BEFORE UPDATE OR DELETE ON eas.bad_case_evidence
  FOR EACH ROW EXECUTE FUNCTION eas.guard_bad_case_evidence();

-- 12 bad case có sẵn (ai_service/data/bad_case_catalog.json, phiên bản bad-case-catalog-1).
INSERT INTO eas.bad_case(code, title, rationale, condition_text, request_types, risk, escalate_to,
                         detector, source, state, activated_by, activated_at)
SELECT v.code, v.title, v.rationale, v.condition_text, v.request_types, v.risk, v.escalate_to,
       'BUILTIN', 'CATALOG', 'ACTIVE', 'CATALOG', statement_timestamp()
FROM (VALUES
  ('BC_DEADLINE_CONFLICT', 'Xin nghỉ/về sớm khi đang giữ việc đến hạn, chưa bàn giao',
   'Việc đến hạn bị bỏ dở, trễ cam kết với khách hàng/phòng khác.',
   'Người gửi giữ ít nhất 1 việc (bước duyệt, lượt thực hiện, nghiệm thu) đến hạn trong 24 giờ hoặc trong thời gian nghỉ, và đơn chưa có người nhận bàn giao.',
   ARRAY['LEAVE','LEAVE_SPECIAL','ATTENDANCE_ADJUSTMENT']::text[], 5, 'B'),
  ('BC_HANDOVER_OVERLOADED', 'Người nhận bàn giao đang quá tải hoặc cũng vắng',
   'Bàn giao trên giấy: người nhận không thể làm thay, việc vẫn trễ.',
   'Người được chỉ định nhận bàn giao có từ 3 việc đến hạn trong thời gian nghỉ, hoặc chính họ có lịch nghỉ/công tác đã duyệt trùng ngày.',
   ARRAY['LEAVE','LEAVE_SPECIAL']::text[], 4, 'B'),
  ('BC_TEAM_ABSENCE_PEAK', 'Phòng đã vắng nhiều người trùng ngày',
   'Phòng thiếu người trực, dịch vụ nội bộ gián đoạn.',
   'Tỉ lệ thành viên khác trong phòng đã có lịch nghỉ/công tác đã duyệt trùng ngày từ 40% trở lên.',
   ARRAY['LEAVE','LEAVE_SPECIAL']::text[], 4, 'B'),
  ('BC_REPEATED_EXEMPTION', 'Điều chỉnh chấm công lặp lại có hệ thống',
   'Lạm dụng ngưỡng miễn trừ để hợp thức hóa đi muộn/về sớm.',
   'Đây là lần điều chỉnh chấm công thứ 4 trở lên trong 30 ngày.',
   ARRAY['ATTENDANCE_ADJUSTMENT']::text[], 3, 'B'),
  ('BC_WFH_FREQUENT', 'Làm việc từ xa dày đặc trong tháng',
   'WFH trở thành mặc định, né chấm công và họp trực tiếp.',
   'Đây là đơn WFH thứ 8 trở lên trong tháng dương lịch.',
   ARRAY['WFH_REQ']::text[], 3, 'B'),
  ('BC_SPLIT_AMOUNT_EVASION', 'Chia nhỏ đề xuất tài chính để né ngưỡng',
   'Lách cấp duyệt cao (Kế toán trưởng, Giám đốc) bằng nhiều hồ sơ nhỏ.',
   'Từ 2 hồ sơ tài chính trong 7 ngày, tổng vượt ngưỡng trong khi hồ sơ này dưới ngưỡng.',
   ARRAY['EXPENSE_CLAIM','REFUND_COMPENSATION','ADVANCE_SMALL','ADVANCE_MEDIUM','ADVANCE_LARGE','REIMBURSEMENT','SALARY_ADVANCE']::text[], 5, 'C'),
  ('BC_DUPLICATE_INVOICE', 'Số hóa đơn đã được dùng ở hồ sơ khác',
   'Thanh toán hai lần cho một chứng từ.',
   'Số hóa đơn (invoice_number) đã xuất hiện ở hồ sơ thanh toán khác chưa bị hủy/từ chối trong 180 ngày.',
   ARRAY['EXPENSE_CLAIM','REIMBURSEMENT']::text[], 5, 'C'),
  ('BC_REFUND_FREQUENT', 'Hoàn tiền/đền bù dồn dập',
   'Rò rỉ tiền qua nhiều khoản hoàn nhỏ.',
   'Đây là hồ sơ hoàn tiền thứ 3 trở lên của người gửi trong 7 ngày.',
   ARRAY['REFUND_COMPENSATION']::text[], 4, 'B'),
  ('BC_DISCOUNT_REPEAT_CUSTOMER', 'Chiết khấu lặp lại cho cùng khách hàng',
   'Cộng dồn chiết khấu vượt biên lợi nhuận cho một khách.',
   'Đã có hồ sơ chiết khấu khác cho cùng tên khách hàng trong 7 ngày.',
   ARRAY['SPECIAL_DISCOUNT']::text[], 4, 'B'),
  ('BC_REQUESTER_ABSENT_ON_EVENT', 'Người đón khách/chủ trì họp vắng đúng ngày',
   'Khách vào toà nhà không có người tiếp; phòng bị giữ vô ích.',
   'Người gửi có lịch nghỉ/công tác đã duyệt hoặc đơn nghỉ đang chờ trùng ngày khách đến/ngày họp.',
   ARRAY['VISITOR_SECURITY_PASS','ROOM_BOOKING']::text[], 4, 'B'),
  ('BC_AI_REVOKED_HISTORY', 'Quyết định tự duyệt của AI cho người này từng bị thu hồi',
   'Người gửi đã từng lợi dụng tự duyệt; tiếp tục tự duyệt là lặp lại rủi ro.',
   'Có từ 2 lần quản lý thu hồi quyết định tự duyệt của AI trên hồ sơ của người gửi trong 90 ngày.',
   ARRAY['*']::text[], 3, 'B'),
  ('BC_OFF_HOURS_BULK', 'Gửi hàng loạt ngoài giờ hành chính',
   'Lợi dụng lúc vắng người kiểm soát để AI tự duyệt.',
   'Từ 3 hồ sơ của người gửi trong 7 ngày được gửi ngoài 08:00-17:30 thứ Hai-thứ Sáu hoặc ngày lễ, kể cả hồ sơ này.',
   ARRAY['EXPENSE_CLAIM','REFUND_COMPENSATION','ATTENDANCE_ADJUSTMENT','SPECIAL_DISCOUNT']::text[], 3, 'B')
) AS v(code, title, rationale, condition_text, request_types, risk, escalate_to)
ON CONFLICT (code) DO NOTHING;

DO $grants$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['bad_case', 'bad_case_evidence'] LOOP
    EXECUTE format('REVOKE ALL ON eas.%I FROM PUBLIC', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE ON eas.%I TO eas_api, eas_worker', t);
    EXECUTE format('GRANT SELECT ON eas.%I TO eas_backup', t);
    EXECUTE format('ALTER TABLE eas.%I ENABLE ROW LEVEL SECURITY', t);
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='eas' AND tablename=t AND policyname='backend_read') THEN
      EXECUTE format('CREATE POLICY backend_read ON eas.%I FOR SELECT TO eas_api, eas_worker USING (true)', t);
      EXECUTE format('CREATE POLICY backend_insert ON eas.%I FOR INSERT TO eas_api, eas_worker WITH CHECK (true)', t);
      EXECUTE format('CREATE POLICY backend_update ON eas.%I FOR UPDATE TO eas_api, eas_worker USING (true) WITH CHECK (true)', t);
      EXECUTE format('CREATE POLICY backup_read ON eas.%I FOR SELECT TO eas_backup USING (true)', t);
    END IF;
  END LOOP;
END
$grants$;

UPDATE eas.security_epoch SET version = version + 1, updated_at = statement_timestamp() WHERE id = 1;
COMMIT;

SELECT state, detector, count(*) FROM eas.bad_case GROUP BY 1, 2 ORDER BY 1, 2;
